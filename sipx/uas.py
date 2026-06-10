# RFC 3261 UAS role: receive INVITE, optionally send 0+ provisional `1xx`,
# send one final response, receive ACK, then own confirmed dialog lifecycle.
# SDP answer bodies follow RFC 3264/RFC 8866; RTP media follows RFC 3550/3551.

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Literal
from uuid import uuid4

from sipx.rtp.audio import RtpAudioMode, RtpAudioSession, RtpAudioSessionConfig
from sipx.rtp.sink import RtpSink
from sipx.media import PyAudioInputSource, ensure_pyaudio_available
from sipx.sdp import SessionDescription
from sipx.sip.message import DEFAULT_MAX_MESSAGE_SIZE
from sipx.sip.transport import UdpAddress
from sipx.sip.uri import SipUri
from sipx.ua import (
    EventHooks,
    SipCall,
    SipCallState,
    SipProvisionalResponse,
    SipRetransmissionPolicy,
    SipUserAgent,
)


class SipUasError(RuntimeError):
    pass


SipAnswerAudioMode = Literal["none", "silence", "noise", "pyaudio"]


class SipUas(SipUserAgent):
    """SIP user-agent server role."""

    def __init__(
        self,
        *,
        aor: SipUri | str | None = None,
        username: str | None = None,
        password: str | None = None,
        contact_user: str | None = None,
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
        event_hooks: EventHooks | None = None,
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
            event_hooks=event_hooks,
            compact_headers=compact_headers,
        )
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not 0 <= media_port <= 65535:
            raise ValueError("media_port must be between 0 and 65535")
        if jitter_buffer_ms < 0:
            raise ValueError("jitter_buffer_ms must be non-negative")
        if not codecs:
            raise ValueError("at least one codec is required")
        self.aor = _optional_sip_uri(aor)
        self.username = username
        self.password = password
        self.contact_user = contact_user
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

    async def start(self) -> SipUas:
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
            raise SipUasError("SIP UAS must be started before contact is known")
        host, port = self.local_address
        return SipUri(
            scheme="sip",
            user=self.contact_user
            or (self.aor.user if self.aor is not None else None)
            or "sipx",
            host=host,
            port=port,
        )

    async def answer(
        self,
        *,
        local_tag: str | None = None,
        with_media: bool = True,
        audio: SipAnswerAudioMode = "none",
        provisionals: Sequence[SipProvisionalResponse] | None = None,
    ) -> SipCall:
        if audio not in {"none", "silence", "noise", "pyaudio"}:
            raise ValueError("audio must be none, silence, noise, or pyaudio")
        if audio == "pyaudio":
            ensure_pyaudio_available()
        if audio != "none":
            with_media = True
        rtp: RtpSink | None = None
        rtp_session: RtpAudioSession | None = None
        media_port: int | None = None
        if with_media:
            if audio == "none":
                rtp = await self._open_rtp_sink()
                media_port = rtp.local_address[1]
            else:
                rtp_session = await self._open_rtp_session()
                media_port = rtp_session.local_address[1]
        try:
            call = await self.accept_call(
                local_tag=local_tag or _tag("local"),
                contact=self.contact,
                timeout=self.timeout,
                provisionals=provisionals,
                media_port=media_port,
                media_connection_address=self.rtp_advertise_host,
                supported_codecs=self.codecs,
                telephone_event=self.telephone_event,
            )
        except Exception:
            if rtp is not None:
                rtp.close()
            if rtp_session is not None:
                await rtp_session.close()
            raise
        if rtp is not None and call.local_sdp is not None:
            self._rtp_sinks[call.call_id] = rtp
        elif rtp is not None:
            rtp.close()
        if rtp_session is not None and call.local_sdp is not None:
            self._rtp_sessions[call.call_id] = rtp_session
            if audio == "silence" or audio == "noise":
                self._start_synthetic_rtp(call, rtp_session, audio)
            elif audio == "pyaudio":
                self._start_pyaudio_rtp(call, rtp_session)
        elif rtp_session is not None:
            await rtp_session.close()
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

    async def wait_hangup(self, call: SipCall) -> None:
        await self.answer_bye(call, timeout=self.timeout)
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
        rtp_event_hooks: dict[str, list[Any]] | None = None
        if "rtp" in self.event_hooks:
            rtp_event_hooks = {"rtp": self.event_hooks.get("rtp", [])}
        return await RtpAudioSession.open(
            RtpAudioSessionConfig(
                local_host=host,
                local_port=self.media_port,
                codec=codec,
                payload_type=_payload_type(codec),
                jitter_buffer_ms=self.jitter_buffer_ms,
                max_jitter_buffer_ms=max(200, self.jitter_buffer_ms),
                event_hooks=rtp_event_hooks,
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


def _sip_uri(value: SipUri | str) -> SipUri:
    return value if isinstance(value, SipUri) else SipUri.parse(value)


def _optional_sip_uri(value: SipUri | str | None) -> SipUri | None:
    return None if value is None else _sip_uri(value)


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
