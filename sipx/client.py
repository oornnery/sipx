from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ._transport import Addr, SIPTransport, TransportResponse


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SIPMessage:
    start_line: str
    headers: Dict[str, str]
    body: str
    raw: str


@dataclass(slots=True)
class Event:
    name: str
    client: "Client"
    message: SIPMessage


@dataclass(slots=True)
class CallEvent(Event):
    call: "Call"


@dataclass(slots=True)
class OptionResponseEvent(Event):
    response: TransportResponse


@dataclass(slots=True)
class CallHangupEvent(CallEvent):
    by_remote: bool


@dataclass(slots=True)
class SDPNegotiatedEvent(CallEvent):
    sdp: str


def _parse_sip_message(raw: str) -> SIPMessage:
    header_block, _, body = raw.partition("\r\n\r\n")
    if not _:
        header_block, _, body = raw.partition("\n\n")
    header_lines = (
        header_block.split("\r\n")
        if "\r\n" in header_block
        else header_block.split("\n")
    )
    header_lines = [line for line in header_lines if line is not None]
    start_line = header_lines[0] if header_lines else ""
    headers: Dict[str, str] = {}
    for line in header_lines[1:]:
        if not line.strip():
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return SIPMessage(start_line=start_line, headers=headers, body=body, raw=raw)


def _header_params(value: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    if ";" not in value:
        return params
    for part in value.split(";")[1:]:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().lower()] = val.strip()
        else:
            params[part.lower()] = ""
    return params


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
    remote_tag: Optional[str] = None
    sdp: Optional[str] = None
    status: str = "initiating"
    created_at: datetime = field(default_factory=_now)
    connected_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    terminated_by: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    last_response: Optional[TransportResponse] = None

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


class Client:
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
        self._transport: Optional[SIPTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = False
        self._local_addr: Optional[Addr] = None
        self._local_uri: Optional[str] = None
        self._via_cache: Optional[str] = None
        self._calls: Dict[str, Call] = {}
        self._cseq = 1

    @classmethod
    def event_handler(
        cls, name: str
    ) -> Callable[[Callable[[Event], Any]], Callable[[Event], Any]]:
        def decorator(func: Callable[[Event], Any]) -> Callable[[Event], Any]:
            cls._event_handlers.setdefault(name, []).append(func)
            return func

        return decorator

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
            on_message=self._on_transport_message,
            protocol=self.protocol,
        )
        await self._transport.start(self._requested_local)
        bound = self._transport.local_address() or self._requested_local
        self._local_addr = bound
        host = self._determine_local_host(bound)
        self._via_cache = host
        self._local_uri = f"sip:{self.identity}@{host}:{bound[1]}"
        self._started = True

    async def close(self) -> None:
        if not self._started:
            return
        assert self._transport is not None
        await self._transport.stop()
        self._transport = None
        self._started = False
        self._local_addr = None
        self._local_uri = None
        self._via_cache = None

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

    async def message(
        self,
        content: str,
        uri: Optional[str] = None,
        *,
        content_type: str = "text/plain",
        wait_response: bool = False,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[TransportResponse]:
        await self._ensure_started()
        target_uri = uri or self.remote_uri
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
        extra = {"Content-Type": content_type}
        if headers:
            extra.update(headers)
        request = self._render_request(
            "MESSAGE", target_uri, base_headers, content, extra
        )
        assert self._transport is not None
        response = await self._transport.send(
            request,
            self.addr,
            wait_response=wait_response,
            timeout=timeout,
        )
        return response if wait_response else None

    async def options(
        self,
        uri: Optional[str] = None,
        *,
        timeout: Optional[float] = 5.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> TransportResponse:
        await self._ensure_started()
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
        request = self._render_request("OPTIONS", target_uri, base_headers, "", headers)
        assert self._transport is not None
        response = await self._transport.send(
            request,
            self.addr,
            wait_response=True,
            timeout=timeout,
        )
        raw_message = response.response_raw
        if not raw_message:
            code = response.status_code or 0
            text = response.status_text or ""
            raw_message = f"SIP/2.0 {code} {text}\r\n\r\n"
        await self._emit_event(
            "OptionResponse",
            OptionResponseEvent(
                name="OptionResponse",
                client=self,
                message=_parse_sip_message(raw_message),
                response=response,
            ),
        )
        return response

    async def invite(
        self,
        uri: str,
        *,
        timeout: Optional[float] = 10.0,
        sdp: Optional[bool | str] = None,
        media: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Call:
        await self._ensure_started()
        call_id = self._generate_call_id()
        from_tag = self._generate_tag()
        branch = self._generate_branch()
        cseq = self._next_cseq()
        body = ""
        base_headers = self._base_headers(
            method="INVITE",
            uri=uri,
            call_id=call_id,
            from_tag=from_tag,
            cseq=cseq,
            branch=branch,
            override_via=f"SIP/2.0/{self.protocol} {self._via_host()}:{self.local_address[1]};branch={branch}",
        )
        extra_headers: Dict[str, str] = {}
        if sdp:
            body = self._build_sdp(media)
            extra_headers["Content-Type"] = "application/sdp"
        if headers:
            extra_headers.update(headers)
        request = self._render_request("INVITE", uri, base_headers, body, extra_headers)
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
            {
                "call_id": call_id,
                "from_tag": from_tag,
                "target_uri": uri,
            }
        )
        call.details.setdefault("requests", []).append(
            {"method": "INVITE", "raw": request}
        )
        self._calls[call_id] = call
        assert self._transport is not None
        response = await self._transport.send(
            request,
            self.addr,
            wait_response=True,
            timeout=timeout,
        )
        call.last_response = response
        if response.timed_out:
            raise TimeoutError("INVITE timed out")
        if response.response_raw:
            message = _parse_sip_message(response.response_raw)
            await self._handle_response_message(message, self.addr)
        return call

    async def _send_bye(
        self, call: Call, *, timeout: Optional[float] = None
    ) -> TransportResponse:
        await self._ensure_started()
        cseq = call.next_cseq()
        to_value = f"<{call.target_uri}>"
        if call.remote_tag:
            to_value = f"{to_value};tag={call.remote_tag}"
        base_headers = self._base_headers(
            method="BYE",
            uri=call.target_uri,
            call_id=call.call_id,
            from_tag=call.from_tag,
            cseq=cseq,
            to_override=to_value,
        )
        request = self._render_request("BYE", call.target_uri, base_headers, "", None)
        call.details.setdefault("requests", []).append(
            {"method": "BYE", "raw": request}
        )
        assert self._transport is not None
        response = await self._transport.send(
            request,
            self.addr,
            wait_response=True,
            timeout=timeout,
        )
        call.last_response = response
        if not response.timed_out:
            call.terminated_at = _now()
            call.terminated_by = call.terminated_by or "local"
            call.status = "terminated"
            await self._emit_event(
                "CallHangup",
                CallHangupEvent(
                    name="CallHangup",
                    client=self,
                    message=_parse_sip_message(response.response_raw or ""),
                    call=call,
                    by_remote=False,
                ),
            )
        return response

    async def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "Client not started; use 'async with Client(...)' or await start()"
            )

    def _next_cseq(self) -> int:
        value = self._cseq
        self._cseq += 1
        return value

    def _generate_call_id(self) -> str:
        host = self._via_host()
        return f"{uuid.uuid4().hex}@{host}"

    def _generate_tag(self) -> str:
        return uuid.uuid4().hex[:8]

    def _generate_branch(self) -> str:
        return f"z9hG4bK{uuid.uuid4().hex[:8]}"

    def _via_host(self) -> str:
        if not self._via_cache:
            raise RuntimeError("Client not started")
        return self._via_cache

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
    ) -> List[tuple[str, str]]:
        if not self._started:
            raise RuntimeError("Client not started")
        branch = branch or self._generate_branch()
        via_value = override_via or (
            f"SIP/2.0/{self.protocol} {self._via_host()}:{self.local_address[1]};branch={branch}"
        )
        display = f'"{self.display_name}" ' if self.display_name else ""
        from_value = f"{display}<{self.local_uri}>;tag={from_tag}"
        to_value = to_override or f"<{uri}>"
        headers: List[tuple[str, str]] = [
            ("Via", via_value),
            ("Max-Forwards", "70"),
            ("From", from_value),
            ("To", to_value),
            ("Call-ID", call_id),
            ("CSeq", f"{cseq} {method}"),
            ("Contact", f"<{self.local_uri}>"),
            ("User-Agent", self.user_agent),
        ]
        return headers

    def _render_request(
        self,
        method: str,
        uri: str,
        base_headers: List[tuple[str, str]],
        body: str,
        extra_headers: Optional[Dict[str, str]],
    ) -> str:
        headers = list(base_headers)
        if extra_headers:
            for key, value in extra_headers.items():
                replaced = False
                for index, (existing_key, _) in enumerate(headers):
                    if existing_key.lower() == key.lower():
                        headers[index] = (key, value)
                        replaced = True
                        break
                if not replaced:
                    headers.append((key, value))
        body_text = body or ""
        content_length = len(body_text.encode("utf-8"))
        if not any(key.lower() == "content-length" for key, _ in headers):
            headers.append(("Content-Length", str(content_length)))
        header_lines = "\r\n".join(f"{key}: {value}" for key, value in headers)
        return f"{method} {uri} SIP/2.0\r\n{header_lines}\r\n\r\n{body_text}"

    def _build_sdp(self, media: Optional[str]) -> str:
        host = self._via_host()
        port = self.local_address[1] + 10000
        session = media or "sipx-session"
        lines = [
            "v=0",
            f"o=- {int(_now().timestamp())} 1 IN IP4 {host}",
            f"s={session}",
            f"c=IN IP4 {host}",
            "t=0 0",
            f"m=audio {port} RTP/AVP 0 8 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:8 PCMA/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=fmtp:101 0-16",
            "a=sendrecv",
        ]
        return "\r\n".join(lines) + "\r\n"

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

    async def _on_transport_message(self, raw: str, addr: Addr) -> None:
        message = _parse_sip_message(raw)
        if message.start_line.upper().startswith("SIP/2.0"):
            await self._handle_response_message(message, addr)
        else:
            await self._handle_request_message(message, addr)

    async def _handle_response_message(self, message: SIPMessage, addr: Addr) -> None:
        parts = message.start_line.split(" ", 2)
        if len(parts) < 2:
            return
        try:
            status_code = int(parts[1])
        except ValueError:
            return
        status_text = parts[2] if len(parts) > 2 else ""
        cseq_header = message.headers.get("cseq", "")
        cseq_method = cseq_header.split(" ", 1)[1].upper() if " " in cseq_header else ""
        call_id = message.headers.get("call-id")
        if call_id:
            call = self._calls.get(call_id)
        else:
            call = None

        if call:
            entry = {
                "status_code": status_code,
                "status_text": status_text,
                "headers": dict(message.headers),
                "body": message.body,
                "received_at": _now(),
            }
            call.details.setdefault("responses", []).append(entry)
            call.details["last_status_code"] = status_code
            call.details["last_status_text"] = status_text
            if cseq_method == "INVITE":
                if status_code < 200:
                    call.status = "proceeding"
                elif 200 <= status_code < 300:
                    call.status = "connected"
                    call.connected_at = call.connected_at or _now()
                    to_header = message.headers.get("to", "")
                    params = _header_params(to_header)
                    if params.get("tag"):
                        call.remote_tag = params["tag"]
                    body = message.body.strip()
                    if body:
                        if call.sdp != body:
                            call.sdp = body
                            call.details["sdp"] = body
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
                    await self._ack_call(call)
            elif cseq_method == "BYE" and status_code >= 200:
                if call.status != "terminated":
                    call.status = "terminated"
                    call.terminated_at = _now()
                    call.terminated_by = call.terminated_by or "local"
                    await self._emit_event(
                        "CallHangup",
                        CallHangupEvent(
                            name="CallHangup",
                            client=self,
                            message=message,
                            call=call,
                            by_remote=False,
                        ),
                    )

        # Non call-specific handling (e.g., OPTIONS) is handled elsewhere

    async def _handle_request_message(self, message: SIPMessage, addr: Addr) -> None:
        parts = message.start_line.split()
        if not parts:
            return
        method = parts[0].upper()
        if method == "BYE":
            call_id = message.headers.get("call-id")
            call = self._calls.get(call_id) if call_id else None
            if call:
                call.status = "terminated"
                call.terminated_at = _now()
                call.terminated_by = "remote"
                call.details.setdefault("incoming", []).append(
                    {
                        "method": "BYE",
                        "headers": dict(message.headers),
                        "body": message.body,
                        "received_at": _now(),
                    }
                )
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
            await self._send_simple_response(message, addr, 200, "OK")
        elif method == "OPTIONS":
            await self._send_simple_response(
                message,
                addr,
                200,
                "OK",
                {
                    "Allow": "INVITE, ACK, CANCEL, OPTIONS, BYE, INFO, MESSAGE",
                    "Accept": "application/sdp, application/dtmf-relay, text/plain",
                },
            )
        elif method == "ACK":
            return
        elif method == "CANCEL":
            await self._send_simple_response(message, addr, 200, "OK")
        else:
            # For unsupported methods, answer with 501
            await self._send_simple_response(message, addr, 501, "Not Implemented")

    async def _send_simple_response(
        self,
        request: SIPMessage,
        addr: Addr,
        status_code: int,
        reason: str,
        extra_headers: Optional[Dict[str, str]] = None,
        body: str | None = None,
    ) -> None:
        headers = [
            ("Via", request.headers.get("via", "")),
            ("From", request.headers.get("from", "")),
            ("To", request.headers.get("to", "")),
            ("Call-ID", request.headers.get("call-id", "")),
            ("CSeq", request.headers.get("cseq", "")),
        ]
        if extra_headers:
            for key, value in extra_headers.items():
                headers.append((key, value))
        body_text = body or ""
        headers.append(("Content-Length", str(len(body_text.encode("utf-8")))))
        header_lines = "\r\n".join(
            f"{key}: {value}" for key, value in headers if key and value
        )
        response = (
            f"SIP/2.0 {status_code} {reason}\r\n{header_lines}\r\n\r\n{body_text}"
        )
        if not self._transport:
            return
        await self._transport.send(
            response,
            addr,
            wait_response=False,
            timeout=None,
        )

    async def _ack_call(self, call: Call) -> None:
        if not call.remote_tag:
            return
        to_value = f"<{call.target_uri}>;tag={call.remote_tag}"
        base_headers = self._base_headers(
            method="ACK",
            uri=call.target_uri,
            call_id=call.call_id,
            from_tag=call.from_tag,
            cseq=call.invite_cseq,
            to_override=to_value,
        )
        request = self._render_request("ACK", call.target_uri, base_headers, "", None)
        if not self._transport:
            return
        await self._transport.send(
            request,
            self.addr,
            wait_response=False,
            timeout=None,
        )

    async def _emit_event(self, name: str, event: Event) -> None:
        handlers = list(self._event_handlers.get(name, []))
        if not handlers:
            return
        awaitables: List[Awaitable[Any]] = []
        for handler in handlers:
            try:
                result = handler(event)
            except Exception:
                logger.exception("Handler for event %s raised", name)
                continue
            if inspect.isawaitable(result):
                awaitables.append(result)  # type: ignore[arg-type]
        if awaitables:
            results = await asyncio.gather(*awaitables, return_exceptions=True)
            for outcome in results:
                if isinstance(outcome, Exception):
                    logger.error(
                        "Async handler for event %s raised", name, exc_info=outcome
                    )


__all__ = [
    "Client",
    "Call",
    "CallEvent",
    "CallHangupEvent",
    "OptionResponseEvent",
    "SDPNegotiatedEvent",
    "SIPMessage",
    "TransportResponse",
]
