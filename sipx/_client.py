from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ._auth import DigestCredentials, build_authorization_header, parse_challenge
from ._fsm import CallFSM, CallState
from ._sdp import build_audio_sdp
from ._sip import (
    SIPHeaders,
    SIPMessage,
    build_request,
    build_response,
    header_params,
    parse_sip_message,
)
from ._transport import Addr, SIPTransport, TransportResponse

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Call:
    client: "Client"
    call_id: str
    target_uri: str
    from_uri: str
    from_tag: str
    branch: str
    invite_cseq: int
    cseq: int
    fsm: CallFSM = field(default_factory=CallFSM)
    remote_tag: Optional[str] = None
    sdp: Optional[str] = None
    created_at: datetime = field(default_factory=_now)
    connected_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    terminated_by: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    last_response: Optional[TransportResponse] = None

    @property
    def state(self) -> CallState:
        return self.fsm.state

    def next_cseq(self) -> int:
        self.cseq += 1
        return self.cseq

    @property
    def duration(self) -> float:
        if not self.connected_at:
            return 0.0
        reference = self.terminated_at or _now()
        return max(0.0, (reference - self.connected_at).total_seconds())

    async def bye(self, timeout: Optional[float] = None) -> TransportResponse:
        return await self.client._send_bye(self, timeout=timeout)


@dataclass(slots=True)
class Event:
    name: str
    client: "Client"
    message: SIPMessage


@dataclass(slots=True)
class CallEvent(Event):
    call: Call


@dataclass(slots=True)
class CallHangupEvent(CallEvent):
    by_remote: bool


@dataclass(slots=True)
class SDPNegotiatedEvent(CallEvent):
    sdp: str


@dataclass(slots=True)
class OptionResponseEvent(Event):
    response: TransportResponse


class Client:
    """High-level SIP client orchestrating transport, parsing, and events."""

    _event_handlers: Dict[str, List[Callable[[Event], Any]]] = {}

    def __init__(
        self,
        addr: Addr,
        *,
        protocol: str = "UDP",
        local_addr: Optional[Addr] = None,
        identity: str = "sipx",
        display_name: Optional[str] = None,
        remote_uri: Optional[str] = None,
        user_agent: str = "sipx/0.1",
        credentials: Optional[DigestCredentials] = None,
    ) -> None:
        self.addr = addr
        self.protocol = protocol.upper()
        if self.protocol not in {"UDP", "TCP"}:
            raise ValueError("protocol must be 'UDP' or 'TCP'")
        self._requested_local = local_addr or ("0.0.0.0", 0)
        self.identity = identity
        self.display_name = display_name
        self.remote_uri = remote_uri or f"sip:{addr[0]}:{addr[1]}"
        self.user_agent = user_agent
        self.credentials = credentials

        self._transport: Optional[SIPTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = False
        self._local_addr: Optional[Addr] = None
        self._local_uri: Optional[str] = None
        self._via_host: Optional[str] = None
        self._calls: Dict[str, Call] = {}
        self._cseq = 1
        self._nonce_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "Client":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._transport = SIPTransport(
            on_message=self._on_transport_message, protocol=self.protocol
        )
        await self._transport.start(self._requested_local)
        bound = self._transport.local_address() or self._requested_local
        self._local_addr = bound
        host = self._determine_local_host(bound)
        self._via_host = host
        self._local_uri = f"sip:{self.identity}@{host}:{bound[1]}"
        self._started = True
        logger.debug(f"Client started on {bound} via {self._local_uri}")

    async def close(self) -> None:
        if not self._started:
            return
        assert self._transport is not None
        await self._transport.stop()
        self._transport = None
        self._started = False
        self._local_addr = None
        self._local_uri = None
        self._via_host = None
        self._calls.clear()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    @classmethod
    def event_handler(
        cls, name: str
    ) -> Callable[[Callable[[Event], Any]], Callable[[Event], Any]]:
        def decorator(func: Callable[[Event], Any]) -> Callable[[Event], Any]:
            cls._event_handlers.setdefault(name, []).append(func)
            return func

        return decorator

    async def _emit_event(self, name: str, event: Event) -> None:
        handlers = list(self._event_handlers.get(name, []))
        if not handlers:
            return
        awaitables: List[Awaitable[Any]] = []
        for handler in handlers:
            try:
                result = handler(event)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(f"Handler for {name} raised")
                continue
            if inspect.isawaitable(result):
                awaitables.append(result)  # type: ignore[arg-type]
        if awaitables:
            results = await asyncio.gather(*awaitables, return_exceptions=True)
            for outcome in results:
                if isinstance(outcome, Exception):
                    logger.error(f"Async handler for {name} raised", exc_info=outcome)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def local_uri(self) -> str:
        if not self._local_uri:
            raise RuntimeError("Client not started")
        return self._local_uri

    @property
    def local_address(self) -> Addr:
        if not self._local_addr:
            raise RuntimeError("Client not started")
        return self._local_addr

    # ------------------------------------------------------------------
    # Public SIP API
    # ------------------------------------------------------------------
    async def options(
        self,
        uri: Optional[str] = None,
        *,
        timeout: Optional[float] = 5.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> TransportResponse:
        self._ensure_started()
        target_uri = uri or self.remote_uri
        call_id = self._generate_call_id()
        from_tag = self._generate_tag()
        cseq = self._next_cseq()
        base_headers = self._base_headers(
            method="OPTIONS",
            uri=target_uri,
            call_id=call_id,
            from_tag=from_tag,
            cseq=cseq,
        )
        if headers:
            base_headers.update(headers.items())
        request = build_request("OPTIONS", target_uri, base_headers)
        response = await self._send(request, wait_response=True, timeout=timeout)
        raw = (
            response.response_raw
            or f"SIP/2.0 {response.status_code or 0} {response.status_text or ''}\r\n\r\n"
        )
        try:
            parsed = parse_sip_message(raw)
        except ValueError:
            logger.warning("Failed to parse OPTIONS response; skipping event dispatch")
        else:
            await self._emit_event(
                "OptionResponse",
                OptionResponseEvent(
                    name="OptionResponse",
                    client=self,
                    message=parsed,
                    response=response,
                ),
            )
        return response

    async def register(
        self,
        *,
        username: Optional[str] = None,
        domain: Optional[str] = None,
        expires: int = 300,
        timeout: Optional[float] = 5.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> TransportResponse:
        self._ensure_started()
        user = username or (self.credentials.username if self.credentials else self.identity)
        if not user:
            raise ValueError("username required for REGISTER")
        host = domain or self.addr[0]
        request_uri = f"sip:{host}"
        to_uri = f"sip:{user}@{host}"
        call_id = self._generate_call_id()
        from_tag = self._generate_tag()
        cseq = self._next_cseq()
        branch = self._generate_branch()

        base_headers = self._base_headers(
            method="REGISTER",
            uri=request_uri,
            call_id=call_id,
            from_tag=from_tag,
            cseq=cseq,
            branch=branch,
            to_override=f"<{to_uri}>",
        )
        contact = f"<sip:{user}@{self._assert_via_host()}:{self.local_address[1]}>"
        base_headers["Contact"] = contact
        base_headers["Expires"] = str(expires)
        if headers:
            base_headers.update(headers.items())

        request = build_request("REGISTER", request_uri, base_headers)
        response = await self._send(request, wait_response=True, timeout=timeout)
        if response.status_code in {401, 407} and self.credentials and response.response_raw:
            message = parse_sip_message(response.response_raw)
            www_auth = message.get("WWW-Authenticate")
            proxy_auth = message.get("Proxy-Authenticate")
            auth_header = www_auth or proxy_auth
            if auth_header:
                challenge = parse_challenge(auth_header)
                key = f"{call_id}:REGISTER"
                nc = self._nonce_counts.get(key, 0) + 1
                self._nonce_counts[key] = nc
                header_value = build_authorization_header(
                    "REGISTER",
                    request_uri,
                    challenge,
                    self.credentials,
                    nonce_count=nc,
                    qop=challenge.get("qop", "auth"),
                )
                header_name = "Authorization" if www_auth else "Proxy-Authorization"
                base_headers = self._base_headers(
                    method="REGISTER",
                    uri=request_uri,
                    call_id=call_id,
                    from_tag=from_tag,
                    cseq=cseq,
                    branch=self._generate_branch(),
                    to_override=f"<{to_uri}>",
                )
                base_headers["Contact"] = contact
                base_headers["Expires"] = str(expires)
                base_headers[header_name] = header_value
                if headers:
                    base_headers.update(headers.items())
                request = build_request("REGISTER", request_uri, base_headers)
                response = await self._send(
                    request, wait_response=True, timeout=timeout
                )
        return response

    async def message(
        self,
        content: str,
        uri: Optional[str] = None,
        *,
    content_type: str = "text/plain",
    wait_response: bool = False,
    timeout: Optional[float] = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[TransportResponse]:
        self._ensure_started()
        target_uri = uri or self.remote_uri
        effective_timeout = (
            timeout if timeout is not None else (10.0 if wait_response else None)
        )
        call_id = self._generate_call_id()
        from_tag = self._generate_tag()
        cseq = self._next_cseq()
        base_headers = self._base_headers(
            method="MESSAGE",
            uri=target_uri,
            call_id=call_id,
            from_tag=from_tag,
            cseq=cseq,
        )
        base_headers["Content-Type"] = content_type
        if headers:
            base_headers.update(headers.items())
        request = build_request("MESSAGE", target_uri, base_headers, body=content)
        response = await self._send(
            request, wait_response=wait_response, timeout=effective_timeout
        )
        if (
            wait_response
            and response.status_code in {401, 407}
            and self.credentials
            and response.response_raw
        ):
            auth_message = parse_sip_message(response.response_raw)
            www_auth = auth_message.get("WWW-Authenticate")
            proxy_auth = auth_message.get("Proxy-Authenticate")
            auth_header = www_auth or proxy_auth
            if auth_header:
                challenge = parse_challenge(auth_header)
                key = f"{call_id}:MESSAGE"
                nc = self._nonce_counts.get(key, 0) + 1
                self._nonce_counts[key] = nc
                header_value = build_authorization_header(
                    "MESSAGE",
                    target_uri,
                    challenge,
                    self.credentials,
                    nonce_count=nc,
                    qop=challenge.get("qop", "auth"),
                )
                header_name = "Authorization" if www_auth else "Proxy-Authorization"
                retry_headers = self._base_headers(
                    method="MESSAGE",
                    uri=target_uri,
                    call_id=call_id,
                    from_tag=from_tag,
                    cseq=cseq,
                )
                retry_headers["Content-Type"] = content_type
                retry_headers[header_name] = header_value
                if headers:
                    retry_headers.update(headers.items())
                retry_request = build_request(
                    "MESSAGE", target_uri, retry_headers, body=content
                )
                response = await self._send(
                    retry_request, wait_response=True, timeout=effective_timeout
                )
        return response if wait_response else None

    async def invite(
        self,
        uri: str,
        *,
        timeout: Optional[float] = 10.0,
        sdp: bool | str | None = None,
        media: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Call:
        self._ensure_started()
        call_id = self._generate_call_id()
        from_tag = self._generate_tag()
        branch = self._generate_branch()
        cseq = self._next_cseq()

        base_headers = self._base_headers(
            method="INVITE",
            uri=uri,
            call_id=call_id,
            from_tag=from_tag,
            cseq=cseq,
            branch=branch,
            override_via=self._via_header(branch),
        )
        body = ""
        if sdp:
            offer = (
                sdp
                if isinstance(sdp, str)
                else build_audio_sdp(
                    self._assert_via_host(), self.local_address[1] + 10000
                )
            )
            body = offer
            base_headers["Content-Type"] = "application/sdp"
        if headers:
            base_headers.update(headers.items())

        request = build_request("INVITE", uri, base_headers, body=body)
        call = Call(
            client=self,
            call_id=call_id,
            target_uri=uri,
            from_uri=self.local_uri,
            from_tag=from_tag,
            branch=branch,
            invite_cseq=cseq,
            cseq=cseq,
        )
        call.details.update(
            {"call_id": call_id, "from_tag": from_tag, "target_uri": uri}
        )
        call.details.setdefault("requests", []).append(
            {"method": "INVITE", "raw": request}
        )
        self._calls[call_id] = call

        response = await self._send(request, wait_response=True, timeout=timeout)
        call.last_response = response
        if response.timed_out:
            call.fsm.advance_to(CallState.FAILED, reason="timeout")
            raise TimeoutError("INVITE timed out")
        if response.response_raw:
            await self._handle_response(parse_sip_message(response.response_raw))
        return call

    async def _send_bye(
        self, call: Call, *, timeout: Optional[float] = None
    ) -> TransportResponse:
        self._ensure_started()
        cseq = call.next_cseq()
        to_value = f"<{call.target_uri}>"
        if call.remote_tag:
            to_value = f"{to_value};tag={call.remote_tag}"
        headers = self._base_headers(
            method="BYE",
            uri=call.target_uri,
            call_id=call.call_id,
            from_tag=call.from_tag,
            cseq=cseq,
            to_override=to_value,
        )
        request = build_request("BYE", call.target_uri, headers)
        call.details.setdefault("requests", []).append(
            {"method": "BYE", "raw": request}
        )
        response = await self._send(request, wait_response=True, timeout=timeout)
        call.last_response = response
        if not response.timed_out:
            call.fsm.advance_to(CallState.TERMINATED)
            call.terminated_at = _now()
            call.terminated_by = call.terminated_by or "local"
            await self._emit_event(
                "CallHangup",
                CallHangupEvent(
                    name="CallHangup",
                    client=self,
                    message=parse_sip_message(
                        response.response_raw or self._empty_ok()
                    ),
                    call=call,
                    by_remote=False,
                ),
            )
        return response

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------
    async def _send(
        self,
        data: str,
        *,
        wait_response: bool,
        timeout: Optional[float],
    ) -> TransportResponse:
        if not self._transport:
            raise RuntimeError("Client not started")
        snippet_prefix = "\n" if len(data) < 4000 else ""
        logger.debug(f"Sending message:{snippet_prefix}{data}")
        response = await self._transport.send(
            data,
            self.addr,
            wait_response=wait_response,
            timeout=timeout,
        )
        if response.response_raw:
            prefix = "\n" if len(response.response_raw) < 4000 else ""
            logger.debug(f"Received response:{prefix}{response.response_raw}")
        elif response.status_code is not None:
            logger.debug(
                f"Response status: {response.status_code} {response.status_text}"
            )
        return response

    async def _on_transport_message(self, raw: str, addr: Addr) -> None:
        try:
            message = parse_sip_message(raw)
        except ValueError:
            logger.warning(f"Failed to parse SIP message from {addr}")
            return
        if message.is_request:
            await self._handle_request(message, addr)
        else:
            await self._handle_response(message)

    # ------------------------------------------------------------------
    # Incoming responses
    # ------------------------------------------------------------------
    async def _handle_response(self, message: SIPMessage) -> None:
        call_id = message.get("Call-ID")
        if call_id:
            call = self._calls.get(call_id)
        else:
            call = None
        cseq_header = message.get("CSeq", "")
        cseq_method = cseq_header.split(" ", 1)[1].upper() if " " in cseq_header else ""
        status_code = message.status_code or 0

        if status_code in {401, 407} and self.credentials:
            await self._handle_auth_challenge(message)
            return

        if not call:
            return

        call.details.setdefault("responses", []).append(
            {
                "status_code": status_code,
                "status_text": message.status_text,
                "headers": dict(message.headers.items()),
                "body": message.body,
                "received_at": _now(),
            }
        )
        if status_code < 200:
            if call.state == CallState.INITIATING:
                call.fsm.advance_to(CallState.PROCEEDING)
        elif 200 <= status_code < 300:
            if cseq_method == "INVITE":
                change = call.fsm.advance_to(CallState.CONNECTED)
                if change.current == CallState.CONNECTED:
                    call.connected_at = call.connected_at or _now()
                to_header = message.get("To", "") or ""
                params = header_params(to_header)
                if params.get("tag"):
                    call.remote_tag = params["tag"]
                body = message.body.strip()
                if body and call.sdp != body:
                    call.sdp = body
                    await self._emit_event(
                        "SDPNegotiated",
                        SDPNegotiatedEvent(
                            name="SDPNegotiated",
                            client=self,
                            message=message,
                            call=call,
                            sdp=body,
                        ),
                    )
                await self._send_ack(call)
            elif cseq_method == "BYE":
                await self._finalize_call(call, message, by_remote=False)
        else:
            if call.state == CallState.TERMINATED:
                logger.debug(
                    f"Ignoring final response {status_code} for terminated call {call_id}"
                )
                return
            if call.state == CallState.FAILED:
                logger.debug(
                    f"Ignoring final response {status_code} for failed call {call_id}"
                )
                return
            if call.state == CallState.CONNECTED and cseq_method == "INVITE":
                logger.debug(
                    f"Ignoring non-success INVITE response {status_code} for connected call {call_id}"
                )
                return
            call.fsm.advance_to(CallState.FAILED, reason=str(status_code))
            await self._finalize_call(call, message, by_remote=False)

    async def _handle_auth_challenge(self, message: SIPMessage) -> None:
        call_id = message.get("Call-ID")
        if not call_id or call_id not in self._calls or not self.credentials:
            return
        call = self._calls[call_id]
        auth_header = message.get("WWW-Authenticate") or message.get(
            "Proxy-Authenticate"
        )
        if not auth_header:
            return
        challenge = parse_challenge(auth_header)
        nc = self._nonce_counts.get(call_id, 0) + 1
        self._nonce_counts[call_id] = nc
        header_value = build_authorization_header(
            "INVITE",
            call.target_uri,
            challenge,
            self.credentials,
            nonce_count=nc,
            qop=challenge.get("qop", "auth"),
        )
        new_cseq = call.next_cseq()
        new_branch = self._generate_branch()
        headers = self._base_headers(
            method="INVITE",
            uri=call.target_uri,
            call_id=call.call_id,
            from_tag=call.from_tag,
            cseq=new_cseq,
            branch=new_branch,
            override_via=self._via_header(new_branch),
        )
        call.invite_cseq = new_cseq
        headers[
            "Authorization"
            if "www-authenticate" in auth_header.lower()
            else "Proxy-Authorization"
        ] = header_value
        request = build_request("INVITE", call.target_uri, headers, body=call.sdp or "")
        call.details.setdefault("retries", []).append(
            {"authorization": header_value, "raw": request}
        )
        response = await self._send(request, wait_response=True, timeout=10.0)
        call.last_response = response
        if response.response_raw:
            await self._handle_response(parse_sip_message(response.response_raw))

    async def _send_ack(self, call: Call) -> None:
        if not call.remote_tag:
            return
        headers = self._base_headers(
            method="ACK",
            uri=call.target_uri,
            call_id=call.call_id,
            from_tag=call.from_tag,
            cseq=call.invite_cseq,
            to_override=f"<{call.target_uri}>;tag={call.remote_tag}",
        )
        request = build_request("ACK", call.target_uri, headers)
        await self._send(request, wait_response=False, timeout=None)

    async def _finalize_call(
        self, call: Call, message: SIPMessage, *, by_remote: bool
    ) -> None:
        if call.state != CallState.TERMINATED:
            call.fsm.advance_to(CallState.TERMINATED)
        call.terminated_at = call.terminated_at or _now()
        call.terminated_by = call.terminated_by or ("remote" if by_remote else "local")
        await self._emit_event(
            "CallHangup",
            CallHangupEvent(
                name="CallHangup",
                client=self,
                message=message,
                call=call,
                by_remote=by_remote,
            ),
        )

    # ------------------------------------------------------------------
    # Incoming requests
    # ------------------------------------------------------------------
    async def _handle_request(self, message: SIPMessage, addr: Addr) -> None:
        method = (message.method or "").upper()
        if method == "BYE":
            await self._handle_remote_bye(message, addr)
        elif method == "OPTIONS":
            await self._respond_simple(
                message,
                addr,
                200,
                "OK",
                {
                    "Allow": "INVITE, ACK, CANCEL, OPTIONS, BYE, INFO, MESSAGE",
                    "Accept": "application/sdp, application/dtmf-relay, text/plain",
                },
            )
        elif method in {"ACK", "CANCEL"}:
            await self._respond_simple(message, addr, 200, "OK")
        else:
            await self._respond_simple(message, addr, 501, "Not Implemented")

    async def _handle_remote_bye(self, message: SIPMessage, addr: Addr) -> None:
        call_id = message.get("Call-ID")
        call = self._calls.get(call_id, None) if call_id else None
        if call:
            if call.state != CallState.TERMINATED:
                call.fsm.advance_to(CallState.TERMINATED)
            call.terminated_at = call.terminated_at or _now()
            already_remote = call.terminated_by == "remote"
            call.terminated_by = "remote"
            if not already_remote:
                await self._emit_event(
                    "CallHangup",
                    CallHangupEvent(
                        name="CallHangup",
                        client=self,
                        message=message,
                        call=call,
                        by_remote=True,
                    ),
                )
        await self._respond_simple(message, addr, 200, "OK")

    async def _respond_simple(
        self,
        request: SIPMessage,
        addr: Addr,
        status_code: int,
        reason: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        headers = SIPHeaders(
            [
                ("Via", request.get("Via", "")),
                ("From", request.get("From", "")),
                ("To", request.get("To", "")),
                ("Call-ID", request.get("Call-ID", "")),
                ("CSeq", request.get("CSeq", "")),
                ("Server", self.user_agent),
            ]
        )
        if extra_headers:
            headers.update(extra_headers.items())
        response = build_response(status_code, reason, headers)
        if not self._transport:
            return
        await self._transport.send(response, addr, wait_response=False, timeout=None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "Client not started; use 'async with Client(...)' or await start()"
            )

    def _next_cseq(self) -> int:
        value = self._cseq
        self._cseq += 1
        return value

    def _generate_call_id(self) -> str:
        host = self._assert_via_host()
        return f"{uuid.uuid4().hex}@{host}"

    def _generate_tag(self) -> str:
        return uuid.uuid4().hex[:8]

    def _generate_branch(self) -> str:
        return f"z9hG4bK{uuid.uuid4().hex[:8]}"

    def _via_header(self, branch: str) -> str:
        host = self._assert_via_host()
        return f"SIP/2.0/{self.protocol} {host}:{self.local_address[1]};branch={branch}"

    def _base_headers(
        self,
        *,
        method: str,
        uri: str,
        call_id: str,
        from_tag: str,
        cseq: int,
        branch: Optional[str] = None,
        override_via: Optional[str] = None,
        to_override: Optional[str] = None,
    ) -> SIPHeaders:
        self._ensure_started()
        via_value = override_via or self._via_header(branch or self._generate_branch())
        display = f'"{self.display_name}" ' if self.display_name else ""
        from_value = f"{display}<{self.local_uri}>;tag={from_tag}"
        to_value = to_override or f"<{uri}>"
        headers = SIPHeaders(
            [
                ("Via", via_value),
                ("Max-Forwards", "70"),
                ("From", from_value),
                ("To", to_value),
                ("Call-ID", call_id),
                ("CSeq", f"{cseq} {method}"),
                ("Contact", f"<{self.local_uri}>"),
                ("User-Agent", self.user_agent),
            ]
        )
        return headers

    def _assert_via_host(self) -> str:
        if not self._via_host:
            raise RuntimeError("Client not started")
        return self._via_host

    def _empty_ok(self) -> str:
        return "SIP/2.0 200 OK\r\nContent-Length: 0\r\n\r\n"

    def _determine_local_host(self, bound: Addr) -> str:
        host = bound[0]
        if host not in {"0.0.0.0", "::"}:
            return host
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(self.addr)
                host = sock.getsockname()[0]
        except OSError:
            try:
                host = socket.gethostbyname(socket.gethostname())
            except OSError:
                host = "127.0.0.1"
        return host


__all__ = [
    "Client",
    "Call",
    "CallEvent",
    "CallHangupEvent",
    "OptionResponseEvent",
    "SDPNegotiatedEvent",
]
