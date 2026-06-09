# RFC 3261 UAC role: build/send REGISTER, INVITE, ACK, BYE, and SIP INFO;
# accept 0+ INVITE provisional `1xx` before one final response.
# SDP offers follow RFC 3264/RFC 8866; RTP audio follows RFC 3550/3551.

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Literal
from uuid import uuid4

from sipx.rtp.audio import RtpAudioMode, RtpAudioSession, RtpAudioSessionConfig
from sipx.rtp.sink import RtpSink
from sipx.media import PyAudioInputSource, ensure_pyaudio_available
from sipx.sdp import SessionDescription, create_audio_offer
from sipx.sip.message import DEFAULT_MAX_MESSAGE_SIZE
from sipx.sip.register import RegisterClientState
from sipx.sip.transport import SipWireEvent, UdpAddress
from sipx.sip.uri import SipUri
from sipx.ua import (
    SipCall,
    SipCallState,
    SipHandlers,
    SipHooks,
    SipRetransmissionPolicy,
    SipUserAgent,
)


class SipUacError(RuntimeError):
    pass


SipCallAudioMode = Literal["none", "silence", "noise", "pyaudio"]


class SipUac(SipUserAgent):
    """SIP user-agent client role."""

    def __init__(
        self,
        *,
        aor: SipUri | str | None = None,
        registrar: SipUri | str | None = None,
        remote: UdpAddress | None = None,
        username: str | None = None,
        password: str | None = None,
        contact_user: str | None = None,
        expires: int = 3600,
        timeout: float = 1.0,
        media_host: str | None = None,
        rtp_bind_host: str | None = None,
        rtp_advertise_host: str | None = None,
        media_port: int = 0,
        jitter_buffer_ms: int = 60,
        codecs: tuple[str, ...] = ("PCMU", "PCMA"),
        telephone_event: bool = True,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
        mode: str = "strict",
        timeline: Any | None = None,
        actor_id: str | None = None,
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        retransmission_policy: SipRetransmissionPolicy | None = None,
        lab_hooks: SipHooks | None = None,
        handlers: SipHandlers | None = None,
        wire_event_handler: Callable[[SipWireEvent], None] | None = None,
        compact_headers: bool = False,
    ) -> None:
        super().__init__(
            local_host=local_host,
            local_port=local_port,
            mode=mode,
            timeline=timeline,
            actor_id=actor_id,
            max_message_size=max_message_size,
            retransmission_policy=retransmission_policy,
            lab_hooks=lab_hooks,
            handlers=handlers,
            wire_event_handler=wire_event_handler,
            compact_headers=compact_headers,
        )
        if expires <= 0:
            raise ValueError("expires must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not 0 <= media_port <= 65535:
            raise ValueError("media_port must be between 0 and 65535")
        if jitter_buffer_ms < 0:
            raise ValueError("jitter_buffer_ms must be non-negative")
        if not codecs:
            raise ValueError("at least one codec is required")
        self.aor = _optional_sip_uri(aor)
        self.registrar = _optional_sip_uri(registrar)
        self.remote = remote
        self.username = username
        self.password = password
        self.contact_user = contact_user
        self.expires = expires
        self.timeout = timeout
        self.rtp_bind_host = rtp_bind_host or media_host
        self.rtp_advertise_host = rtp_advertise_host or media_host
        self.media_port = media_port
        self.jitter_buffer_ms = jitter_buffer_ms
        self.codecs = codecs
        self.telephone_event = telephone_event
        self._rtp_sinks: dict[str, RtpSink] = {}
        self._rtp_sessions: dict[str, RtpAudioSession] = {}
        self._rtp_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> SipUac:
        await super().start()
        return self

    async def stop(self) -> None:
        for task in self._rtp_tasks.values():
            task.cancel()
        for task in self._rtp_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._rtp_tasks.clear()
        for sink in self._rtp_sinks.values():
            sink.close()
        self._rtp_sinks.clear()
        for session in self._rtp_sessions.values():
            await session.close()
        self._rtp_sessions.clear()
        await super().stop()

    @property
    def contact(self) -> SipUri:
        if not self.endpoint.is_started:
            raise SipUacError("SIP UAC must be started before contact is known")
        host, port = self.local_address
        return SipUri(
            scheme="sip",
            user=self.contact_user
            or (self.aor.user if self.aor is not None else None)
            or "sipx",
            host=host,
            port=port,
        )

    async def register(self, *, call_id: str | None = None) -> RegisterClientState:
        call_id = call_id or _id("register")
        state = await self.register_account(
            remote=self._require_remote(),
            registrar=self._require_registrar(),
            aor=self._require_aor(),
            contact=self.contact,
            call_id=call_id,
            branch=_branch("register"),
            from_tag=_tag("from"),
            expires=self.expires,
            timeout=self.timeout,
            username=self.username,
            password=self.password,
            auth_branch=_branch("register-auth"),
        )
        self._record("registered", data={"call_id": call_id, "state": state.value})
        return state

    async def unregister(self, *, call_id: str | None = None) -> RegisterClientState:
        call_id = call_id or _id("unregister")
        state = await self.unregister_account(
            remote=self._require_remote(),
            registrar=self._require_registrar(),
            aor=self._require_aor(),
            contact=self.contact,
            call_id=call_id,
            branch=_branch("unregister"),
            from_tag=_tag("from"),
            timeout=self.timeout,
            username=self.username,
            password=self.password,
            auth_branch=_branch("unregister-auth"),
        )
        self._record("unregistered", data={"call_id": call_id, "state": state.value})
        return state

    async def call(
        self,
        target: SipUri | str,
        *,
        call_id: str | None = None,
        caller: SipUri | str | None = None,
        contact: SipUri | str | None = None,
        with_media: bool = True,
        audio: SipCallAudioMode = "none",
    ) -> SipCall:
        if audio not in {"none", "silence", "noise", "pyaudio"}:
            raise ValueError("audio must be none, silence, noise, or pyaudio")
        if audio == "pyaudio":
            ensure_pyaudio_available()
        if audio != "none":
            with_media = True
        target_uri = _sip_uri(target)
        caller_uri = _sip_uri(caller) if caller is not None else self._require_aor()
        contact_uri = _sip_uri(contact) if contact is not None else self.contact
        call_id = call_id or _id("call")
        rtp: RtpSink | None = None
        rtp_session: RtpAudioSession | None = None
        body = b""
        content_type: str | None = None
        if with_media:
            if audio == "none":
                rtp = await self._open_rtp_sink()
                media_address = rtp.local_address
            else:
                rtp_session = await self._open_rtp_session()
                media_address = rtp_session.local_address
            offer = create_audio_offer(
                connection_address=self.rtp_advertise_host or media_address[0],
                port=media_address[1],
                codecs=self.codecs,
                telephone_event=self.telephone_event,
            )
            body = offer.to_sdp().encode("utf-8")
            content_type = "application/sdp"
        try:
            call = await self.initiate_call(
                remote=self._remote_for(target_uri),
                target=target_uri,
                caller=caller_uri,
                contact=contact_uri,
                call_id=call_id,
                branch=_branch("invite"),
                from_tag=_tag("from"),
                ack_branch=_branch("ack"),
                timeout=self.timeout,
                body=body,
                content_type=content_type,
                username=self.username,
                password=self.password,
                auth_branch=_branch("invite-auth"),
            )
        except Exception:
            if rtp is not None:
                rtp.close()
            if rtp_session is not None:
                await rtp_session.close()
            raise
        if rtp is not None:
            self._rtp_sinks[call.call_id] = rtp
        if rtp_session is not None:
            self._rtp_sessions[call.call_id] = rtp_session
            if audio == "silence" or audio == "noise":
                self._start_synthetic_rtp(call, rtp_session, audio)
            elif audio == "pyaudio":
                self._start_pyaudio_rtp(call, rtp_session)
        return call

    async def hangup(self, call: SipCall) -> None:
        if call.state is SipCallState.TERMINATED:
            return
        await self.hangup_call(
            call,
            branch=_branch("bye"),
            timeout=self.timeout,
            username=self.username,
            password=self.password,
            auth_branch=_branch("bye-auth"),
        )
        await self._close_media(call.call_id)

    async def send_dtmf(
        self,
        call: SipCall,
        digits: str,
        *,
        duration_ms: int = 160,
    ) -> None:
        await self.send_dtmf_info(
            call,
            digits,
            duration_ms=duration_ms,
            timeout=self.timeout,
        )

    async def _open_rtp_sink(self) -> RtpSink:
        host = self.rtp_bind_host or self.local_address[0]
        return await RtpSink.open(host=host, port=self.media_port)

    async def _open_rtp_session(self) -> RtpAudioSession:
        host = self.rtp_bind_host or self.local_address[0]
        codec = self.codecs[0].upper()
        return await RtpAudioSession.open(
            RtpAudioSessionConfig(
                local_host=host,
                local_port=self.media_port,
                codec=codec,
                payload_type=_payload_type(codec),
                jitter_buffer_ms=self.jitter_buffer_ms,
                max_jitter_buffer_ms=max(200, self.jitter_buffer_ms),
            )
        )

    def rtp_session(self, call: SipCall) -> RtpAudioSession | None:
        return self._rtp_sessions.get(call.call_id)

    def _close_rtp_sink(self, call_id: str) -> None:
        sink = self._rtp_sinks.pop(call_id, None)
        if sink is not None:
            sink.close()

    async def _close_media(self, call_id: str) -> None:
        task = self._rtp_tasks.pop(call_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._close_rtp_sink(call_id)
        session = self._rtp_sessions.pop(call_id, None)
        if session is not None:
            await session.close()

    def _start_synthetic_rtp(
        self,
        call: SipCall,
        session: RtpAudioSession,
        audio: RtpAudioMode,
    ) -> None:
        remote = _remote_rtp(call.remote_sdp)
        if remote is None:
            return
        self._rtp_tasks[call.call_id] = asyncio.create_task(
            _send_synthetic_until_cancelled(session, audio=audio, remote=remote)
        )

    def _start_pyaudio_rtp(
        self,
        call: SipCall,
        session: RtpAudioSession,
    ) -> None:
        remote = _remote_rtp(call.remote_sdp)
        if remote is None:
            return
        self._rtp_tasks[call.call_id] = asyncio.create_task(
            _send_pyaudio_until_cancelled(session, remote=remote)
        )

    def _require_aor(self) -> SipUri:
        if self.aor is None:
            raise SipUacError("SIP UAC requires aor/from identity")
        return self.aor

    def _require_registrar(self) -> SipUri:
        if self.registrar is None:
            raise SipUacError("SIP UAC requires registrar")
        return self.registrar

    def _require_remote(self) -> UdpAddress:
        if self.remote is not None:
            return self.remote
        registrar = self._require_registrar()
        return registrar.host, registrar.port or 5060

    def _remote_for(self, target: SipUri) -> UdpAddress:
        if self.remote is not None:
            return self.remote
        if self.registrar is not None:
            return self.registrar.host, self.registrar.port or 5060
        return target.host, target.port or 5060


def _sip_uri(value: SipUri | str) -> SipUri:
    return value if isinstance(value, SipUri) else SipUri.parse(value)


def _optional_sip_uri(value: SipUri | str | None) -> SipUri | None:
    return None if value is None else _sip_uri(value)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _branch(prefix: str) -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def _tag(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _payload_type(codec: str) -> int:
    if codec == "PCMA":
        return 8
    return 0


def _remote_rtp(sdp: SessionDescription | None) -> UdpAddress | None:
    if sdp is None or sdp.audio is None or sdp.audio.port <= 0:
        return None
    return sdp.connection_address, sdp.audio.port


async def _send_synthetic_until_cancelled(
    session: RtpAudioSession,
    *,
    audio: RtpAudioMode,
    remote: UdpAddress,
) -> None:
    while True:
        await session.send_synthetic(mode=audio, frames=1, remote=remote)


async def _send_pyaudio_until_cancelled(
    session: RtpAudioSession,
    *,
    remote: UdpAddress,
) -> None:
    source = PyAudioInputSource(frame_duration_ms=session.config.ptime_ms)
    source.start()
    try:
        while True:
            await session.send_frame(source.next_frame(), remote=remote)
    finally:
        source.close()
