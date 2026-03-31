"""Native asynchronous SIP Client using async transports directly."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Callable, Optional, Union

from .._events import EventContext, Events
from .._utils import logger
from ..fsm import AsyncTimerManager, StateManager
from ..models._auth import AuthParser, SipAuthCredentials
from ..models._message import MessageParser, Request, Response
from ..transports import TransportAddress, TransportConfig
from ._base import (
    _build_auth_header,
    _create_async_transport,
    _detect_auth_challenge,
    _ensure_required_headers,
    _extract_host_port,
    _get_default_from_uri,
)


class AsyncClient:
    """
    Native asynchronous SIP client using async transports directly.

    Uses ``AsyncUDPTransport``/``AsyncTCPTransport``/``AsyncTLSTransport``
    with ``await transport.send()`` and ``await transport.receive()``.
    No threading — runs entirely in the asyncio event loop.

    Example::

        async with AsyncClient() as client:
            client.auth = ("alice", "secret")
            r = await client.register("sip:alice@pbx.com")
            r = await client.invite("sip:bob@pbx.com", body=sdp)
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 0,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
    ) -> None:
        self.config = TransportConfig(local_host=local_host, local_port=local_port)
        self.transport_protocol = transport.upper()
        self._transport = _create_async_transport(self.transport_protocol, self.config)
        self._state_manager = StateManager()
        self._events = events
        self._auto_auth = auto_auth
        self._closed = False
        self._reregister_task: Optional[asyncio.Task] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

        if isinstance(auth, tuple) and len(auth) == 2:
            self._auth: Optional[SipAuthCredentials] = SipAuthCredentials(
                username=str(auth[0]), password=str(auth[1])
            )
        elif isinstance(auth, SipAuthCredentials):
            self._auth = auth
        else:
            self._auth = None

    # --- Properties ---

    @property
    def events(self) -> Optional[Events]:
        return self._events

    @events.setter
    def events(self, v: Optional[Events]) -> None:
        self._events = v

    @property
    def auth(self) -> Optional[SipAuthCredentials]:
        return self._auth

    @auth.setter
    def auth(self, credentials: Optional[Union[SipAuthCredentials, tuple]]) -> None:
        if isinstance(credentials, tuple) and len(credentials) == 2:
            self._auth = SipAuthCredentials(
                username=str(credentials[0]), password=str(credentials[1])
            )
        elif isinstance(credentials, SipAuthCredentials):
            self._auth = credentials
        else:
            self._auth = None

    @property
    def local_address(self) -> TransportAddress:
        return self._transport.local_address

    @property
    def transport(self):
        return self._transport

    @property
    def is_closed(self) -> bool:
        return self._closed

    # --- Core request (native async with retransmission) ---

    async def request(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        **kwargs,
    ) -> Optional[Response]:
        """Send a SIP request and await the response (native async)."""
        if host is None:
            host, extracted_port = _extract_host_port(uri)
            port = port if port is not None else extracted_port
        else:
            port = port if port is not None else 5060

        request = Request(
            method=method, uri=uri, headers=headers or {}, content=content
        )
        _ensure_required_headers(
            method=request.method,
            uri=request.uri,
            headers=request.headers,
            local_addr=self._transport.local_address,
            transport_protocol=self.transport_protocol,
            auth=self._auth,
        )
        request.headers["Content-Length"] = str(
            len(request.content) if request.content else 0
        )

        destination = TransportAddress(
            host=host, port=port, protocol=self.transport_protocol
        )
        transaction = self._state_manager.create_transaction(request)

        # Wire async timer manager for retransmission
        timer_manager = AsyncTimerManager()
        transaction.timer_manager = timer_manager
        transaction.transport = self.transport_protocol
        transaction._retransmit_fn = lambda: asyncio.ensure_future(
            self._transport.send(request.to_bytes(), destination)
        )

        context = EventContext(
            request=request,
            destination=destination,
            transaction_id=transaction.id,
            transaction=transaction,
        )
        if self._events:
            request = self._events._call_request_handlers(request, context)

        logger.debug(
            ">>> SENDING %s (%s -> %s:%s)",
            method,
            self._transport.local_address,
            host,
            port,
        )

        try:
            await self._transport.send(request.to_bytes(), destination)

            parser = MessageParser()
            final_response = None
            deadline = time.monotonic() + self._transport.config.read_timeout

            while time.monotonic() < deadline:
                try:
                    response_data, source = await asyncio.wait_for(
                        self._transport.receive(), timeout=0.5
                    )
                except (asyncio.TimeoutError, Exception):
                    if transaction.is_terminated():
                        break
                    continue

                response = parser.parse(response_data)
                if not isinstance(response, Response):
                    continue

                response.raw = response_data
                response.request = request
                response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                logger.debug(
                    "<<< RECEIVED %s %s", response.status_code, response.reason_phrase
                )
                self._state_manager.update_transaction(transaction.id, response)
                context.response = response
                context.source = source
                _detect_auth_challenge(response, context)

                if self._events:
                    response = self._events._call_response_handlers(response, context)

                if response.status_code >= 200:
                    final_response = response
                    break
                if final_response is None:
                    final_response = response

            if final_response is None:
                logger.warning("Request timed out")
                return None

            if (
                self._auto_auth
                and self._auth
                and final_response.status_code in (401, 407)
            ):
                retry = await self.retry_with_auth(final_response)
                if retry:
                    final_response = retry

            return final_response

        except Exception as e:
            logger.error("Request failed: %s", e)
            return None
        finally:
            timer_manager.cancel_all()

    # --- Auth retry (native async) ---

    async def retry_with_auth(
        self, response: Response, auth: Optional[SipAuthCredentials] = None
    ) -> Optional[Response]:
        credentials = auth or self._auth
        if not credentials or response.status_code not in (401, 407):
            return None
        request = response.request
        if not request:
            return None

        challenge = AuthParser.parse_from_headers(response.headers)
        if not challenge:
            return None

        host, port = _extract_host_port(request.uri)
        auth_header = _build_auth_header(
            challenge, credentials, request.method, request.uri
        )
        header_name = (
            "Proxy-Authorization" if response.status_code == 407 else "Authorization"
        )
        request.headers[header_name] = auth_header

        if "CSeq" in request.headers:
            parts = request.headers["CSeq"].split()
            if len(parts) == 2:
                request.headers["CSeq"] = f"{int(parts[0]) + 1} {parts[1]}"

        if "Via" in request.headers:
            new_branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
            request.headers["Via"] = re.sub(
                r"branch=z9hG4bK[^;,\s]+",
                f"branch={new_branch}",
                request.headers["Via"],
            )

        destination = TransportAddress(
            host=host, port=port, protocol=self.transport_protocol
        )
        try:
            await self._transport.send(request.to_bytes(), destination)
            parser = MessageParser()
            deadline = time.monotonic() + self._transport.config.read_timeout

            while time.monotonic() < deadline:
                try:
                    data, source = await asyncio.wait_for(
                        self._transport.receive(), timeout=0.5
                    )
                except (asyncio.TimeoutError, Exception):
                    continue
                resp = parser.parse(data)
                if not isinstance(resp, Response):
                    continue
                resp.raw = data
                resp.request = request
                resp.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }
                if self._events:
                    ctx = EventContext(request=request, response=resp, source=source)
                    resp = self._events._call_response_handlers(resp, ctx)
                if resp.status_code >= 200:
                    return resp
            return None
        except Exception as e:
            logger.error("Auth retry failed: %s", e)
            return None

    # --- SIP methods (all native async) ---

    async def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        body: Optional[str] = None,
        **kwargs,
    ) -> Optional[Response]:
        if from_uri is None:
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )
        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        if body:
            headers["Content-Type"] = "application/sdp"
        return await self.request(
            method="INVITE", uri=to_uri, headers=headers, content=body, **kwargs
        )

    async def register(
        self, aor: str, registrar: Optional[str] = None, expires: int = 3600, **kwargs
    ) -> Optional[Response]:
        if registrar is None:
            registrar, _ = _extract_host_port(aor)
        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{aor}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{aor}>"
        headers["Contact"] = (
            f"<sip:{self._transport.local_address.host}:{self._transport.local_address.port}>;expires={expires}"
        )
        return await self.request(
            method="REGISTER", uri=aor, host=registrar, headers=headers, **kwargs
        )

    async def options(self, uri: str, **kwargs) -> Optional[Response]:
        return await self.request(method="OPTIONS", uri=uri, **kwargs)

    async def ack(self, response: Response, **kwargs) -> None:
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        host = kwargs.pop("host", None)
        port = kwargs.pop("port", 5060)
        if host is None:
            host, port = _extract_host_port(request.uri)
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} ACK"
        headers["Via"] = request.headers.get("Via")
        ack = Request(method="ACK", uri=request.uri, headers=headers)
        dest = TransportAddress(host=host, port=port, protocol=self.transport_protocol)
        await self._transport.send(ack.to_bytes(), dest)

    async def bye(
        self, response: Optional[Response] = None, **kwargs
    ) -> Optional[Response]:
        if response is None:
            raise ValueError("Response is required")
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = (
            f"{int((request.headers.get('CSeq') or '1').split()[0]) + 1} BYE"
        )
        return await self.request(
            method="BYE", uri=request.uri, headers=headers, **kwargs
        )

    async def cancel(self, response: Response, **kwargs) -> Optional[Response]:
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = request.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} CANCEL"
        headers["Via"] = request.headers.get("Via")
        return await self.request(
            method="CANCEL", uri=request.uri, headers=headers, **kwargs
        )

    async def message(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        content: str = "",
        content_type: str = "text/plain",
        **kwargs,
    ) -> Optional[Response]:
        if from_uri is None:
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )
        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        headers["Content-Type"] = content_type
        return await self.request(
            method="MESSAGE", uri=to_uri, headers=headers, content=content, **kwargs
        )

    async def subscribe(
        self, uri: str, event: str = "presence", expires: int = 3600, **kwargs
    ) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        headers["Expires"] = str(expires)
        return await self.request(
            method="SUBSCRIBE", uri=uri, headers=headers, **kwargs
        )

    async def notify(
        self, uri: str, event: str = "presence", content: Optional[str] = None, **kwargs
    ) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        if content:
            headers["Content-Type"] = "application/pidf+xml"
        return await self.request(
            method="NOTIFY", uri=uri, headers=headers, content=content, **kwargs
        )

    async def refer(self, uri: str, refer_to: str, **kwargs) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        headers["Refer-To"] = f"<{refer_to}>"
        return await self.request(method="REFER", uri=uri, headers=headers, **kwargs)

    async def info(
        self,
        uri: str,
        content: Optional[str] = None,
        content_type: str = "application/dtmf-relay",
        **kwargs,
    ) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        if content:
            headers["Content-Type"] = content_type
        return await self.request(
            method="INFO", uri=uri, headers=headers, content=content, **kwargs
        )

    async def update(
        self, uri: str, sdp_content: Optional[str] = None, **kwargs
    ) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        if sdp_content:
            headers["Content-Type"] = "application/sdp"
        return await self.request(
            method="UPDATE", uri=uri, headers=headers, content=sdp_content, **kwargs
        )

    async def prack(self, response: Response, **kwargs) -> Optional[Response]:
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["RAck"] = (
            f"{response.headers.get('RSeq', '1')} {request.headers.get('CSeq', '1 INVITE')}"
        )
        return await self.request(
            method="PRACK", uri=request.uri, headers=headers, **kwargs
        )

    async def publish(
        self,
        uri: str,
        event: str = "presence",
        content: Optional[str] = None,
        expires: int = 3600,
        **kwargs,
    ) -> Optional[Response]:
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        headers["Expires"] = str(expires)
        if content:
            headers["Content-Type"] = "application/pidf+xml"
        return await self.request(
            method="PUBLISH", uri=uri, headers=headers, content=content, **kwargs
        )

    async def unregister(self, aor: str, **kwargs) -> Optional[Response]:
        if self._reregister_aor == aor:
            self.disable_auto_reregister()
        return await self.register(aor=aor, expires=0, **kwargs)

    # --- Auto re-registration (native async) ---

    def enable_auto_reregister(
        self, aor: str, interval: int, callback: Optional[Callable] = None
    ) -> None:
        self._reregister_aor = aor
        self._reregister_interval = interval
        self._reregister_callback = callback
        if self._reregister_task:
            self._reregister_task.cancel()
        self._reregister_task = asyncio.create_task(self._reregister_loop())

    def disable_auto_reregister(self) -> None:
        if self._reregister_task:
            self._reregister_task.cancel()
            self._reregister_task = None
        self._reregister_aor = None
        self._reregister_interval = None
        self._reregister_callback = None

    async def _reregister_loop(self) -> None:
        while not self._closed and self._reregister_aor and self._reregister_interval:
            try:
                await asyncio.sleep(self._reregister_interval)
                r = await self.register(
                    aor=self._reregister_aor, expires=self._reregister_interval + 30
                )
                if self._reregister_callback and r:
                    self._reregister_callback(r)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)

    # --- Lifecycle ---

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._reregister_task:
            self._reregister_task.cancel()
        await self._transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncClient(local={self.local_address}, transport={self.transport_protocol})"
