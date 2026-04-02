"""Native asynchronous SIP Client using async transports directly."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Callable, Optional, Union

from .._events import Events
from .._types import SIPTimeoutError
from .._utils import logger
from ..fsm import AsyncTimerManager, StateManager
from ..models._auth import SipAuthCredentials
from ..models._message import MessageParser, Request, Response
from ..transports import TransportAddress, TransportConfig
from ._base import (
    SIPClientBase,
    ForkTracker,
    _ack_and_bye_forked_async,
    _create_async_transport,
)


class AsyncSIPClient(SIPClientBase):
    """
    Native asynchronous SIP client using async transports directly.

    Inherits shared business logic (properties, header building,
    SIP method helpers) from :class:`SIPClientBase`.

    Example::

        async with AsyncSIPClient() as client:
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
        auto_dns: bool = True,
        fork_policy: str = "first",
    ) -> None:
        config = TransportConfig(local_host=local_host, local_port=local_port)
        transport_protocol = transport.upper()
        _transport = _create_async_transport(transport_protocol, config)

        super().__init__(
            config=config,
            transport_protocol=transport_protocol,
            transport=_transport,
            events=events,
            auth=auth,
            auto_auth=auto_auth,
            auto_dns=auto_dns,
            fork_policy=fork_policy,
        )

        self._state_manager = StateManager()

        # Re-registration support (async: asyncio.Task)
        self._reregister_task: Optional[asyncio.Task] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    async def _resolve_dns(self, host: str):
        """Resolve hostname via async SIP DNS SRV (lazy init)."""
        if self._resolver is None:
            from ..dns._async import AsyncSipResolver

            self._resolver = AsyncSipResolver()
        targets = await self._resolver.resolve(host, self.transport_protocol)
        return targets[0] if targets else None

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
        request, destination, context, transaction = self._prepare_request_message(
            method=method,
            uri=uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )
        host = destination.host
        port = destination.port
        # Auto DNS resolution for non-IP hostnames
        if self._auto_dns and not self._is_ip(host):
            resolved = await self._resolve_dns(host)
            if resolved:
                destination = TransportAddress(
                    host=resolved.host,
                    port=resolved.port,
                    protocol=self.transport_protocol,
                )
                context.destination = destination
                host = destination.host
                port = destination.port

        # Rebind request target after async DNS resolution if needed
        transaction.request = request

        # Wire async timer manager for retransmission
        timer_manager = AsyncTimerManager()
        transaction.timer_manager = timer_manager
        transaction.transport = self.transport_protocol
        transaction._retransmit_fn = lambda: asyncio.ensure_future(
            self._transport.send(request.to_bytes(), destination)
        )

        # Trigger initial state timers (Timer A/E for retransmission)
        transaction._on_state_change(transaction.state, transaction.state)

        self._log_outgoing_request(method, uri, host, port, request)

        try:
            await self._transport.send(request.to_bytes(), destination)

            parser = MessageParser()
            final_response = None
            deadline = time.monotonic() + self._transport.config.read_timeout
            fork_tracker = ForkTracker() if method == "INVITE" else None
            fork_deadline: float | None = None

            while time.monotonic() < deadline:
                try:
                    response_data, source = await asyncio.wait_for(
                        self._transport.receive(), timeout=0.5
                    )
                except (asyncio.TimeoutError, SIPTimeoutError, OSError):
                    if not self._should_continue_waiting(
                        transaction=transaction,
                        fork_deadline=fork_deadline,
                        now=time.monotonic(),
                    ):
                        break
                    continue

                response, prack_req = self._process_received_response(
                    request=request,
                    response_data=response_data,
                    source=source,
                    parser=parser,
                    context=context,
                    uri=uri,
                )
                if response is None:
                    continue

                if prack_req is not None:
                    await self._transport.send(prack_req.to_bytes(), destination)
                    logger.debug(
                        ">>> Auto PRACK to %s:%s",
                        destination.host,
                        destination.port,
                    )

                self._state_manager.update_transaction(transaction.id, response)

                final_response, fork_deadline, should_break = (
                    self._collect_response_result(
                        method=method,
                        response=response,
                        final_response=final_response,
                        fork_tracker=fork_tracker,
                        fork_deadline=fork_deadline,
                        now=time.monotonic(),
                    )
                )
                if should_break:
                    break

            final_response, extra_forks = self._resolve_fork_final_response(
                final_response, fork_tracker
            )
            if self._fork_policy == "first" and extra_forks:
                logger.debug(
                    "Forking: %d extra legs detected — auto-ACK+BYE",
                    len(extra_forks),
                )
                for extra in extra_forks:
                    await _ack_and_bye_forked_async(self._transport, extra, destination)

            if final_response is None:
                logger.warning("Request timed out")
                return None

            if self._should_auto_retry_auth(final_response):
                retry = await self.retry_with_auth(final_response)
                if retry:
                    final_response = retry

            return self._finalize_response(final_response)

        except (OSError, SIPTimeoutError, ValueError) as e:
            logger.error("Request failed: %s", e, exc_info=True)
            return None
        finally:
            timer_manager.cancel_all()

    # --- Auth retry (native async) ---

    async def retry_with_auth(
        self, response: Response, auth: Optional[SipAuthCredentials] = None
    ) -> Optional[Response]:
        request, destination = self._build_auth_retry_request(response, auth=auth)
        if request is None or destination is None:
            return None

        try:
            logger.debug(
                ">>> AUTH RETRY %s (%s -> %s:%s)",
                request.method,
                self._transport.local_address,
                destination.host,
                destination.port,
            )
            logger.debug(request.to_string())

            await self._transport.send(request.to_bytes(), destination)
            parser = MessageParser()
            deadline = time.monotonic() + self._transport.config.read_timeout
            final_response: Optional[Response] = None

            while time.monotonic() < deadline:
                try:
                    data, source = await asyncio.wait_for(
                        self._transport.receive(), timeout=0.5
                    )
                except (asyncio.TimeoutError, SIPTimeoutError, OSError):
                    continue

                final_response, done = self._handle_auth_retry_message(
                    request=request,
                    response_data=data,
                    source=source,
                    parser=parser,
                    final_response=final_response,
                )
                if done:
                    break

            return final_response
        except (OSError, SIPTimeoutError, ValueError, re.error) as e:
            logger.error("Auth retry failed: %s", e, exc_info=True)
            return None

    async def ack(self, response: Optional[Response] = None, **kwargs) -> None:
        ack_request, dest = self._build_ack(response, **kwargs)
        await self._transport.send(ack_request.to_bytes(), dest)

    async def bye(
        self, response: Optional[Response] = None, **kwargs
    ) -> Optional[Response]:
        uri, headers = self._build_bye_headers(response, **kwargs)
        result = await self.request(method="BYE", uri=uri, headers=headers, **kwargs)
        self._dialog.clear()
        return result

    async def refer_and_wait(
        self,
        uri: str,
        refer_to: str,
        timeout: float = 30.0,
        **kwargs,
    ) -> Request | Response | None:
        """Send REFER and wait for the transfer result via NOTIFY (RFC 3515).

        Args:
            uri: Target URI (the transferee).
            refer_to: Transfer destination URI.
            timeout: Maximum seconds to wait for a final NOTIFY.
            **kwargs: Extra parameters forwarded to :meth:`refer`.

        Returns:
            The last ``NOTIFY`` :class:`Request` received, or ``None``.
        """
        r = await self.refer(uri, refer_to, **kwargs)
        if r is None or r.status_code not in (200, 202):
            return r

        from ..session import ReferSubscription

        sub = ReferSubscription(refer_to=refer_to)
        deadline = time.monotonic() + timeout
        last_notify: Optional[Request] = None

        while time.monotonic() < deadline:
            try:
                data, src = await asyncio.wait_for(
                    self._transport.receive(), timeout=1.0
                )
            except (asyncio.TimeoutError, SIPTimeoutError, OSError):
                continue

            msg = MessageParser.parse(data)
            if not isinstance(msg, Request) or msg.method != "NOTIFY":
                continue
            if "refer" not in msg.headers.get("Event", "").lower():
                continue

            await self._transport.send(msg.ok().to_bytes(), src)
            last_notify = msg
            logger.debug(
                "<<< NOTIFY (refer) body=%r sub_state=%r",
                msg.content_text[:60] if msg.content else "",
                msg.headers.get("Subscription-State", ""),
            )

            sipfrag = msg.content_text if msg.content else ""
            sub_state = msg.headers.get("Subscription-State", "")
            if sub.update(sipfrag, sub_state):
                break

        return last_notify

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
            except (OSError, SIPTimeoutError, ValueError) as e:
                logger.warning("Async re-registration error: %s", e, exc_info=True)
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
        return f"AsyncSIPClient(local={self.local_address}, transport={self.transport_protocol})"
