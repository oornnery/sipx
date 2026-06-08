from __future__ import annotations

from collections.abc import AsyncIterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sipx.backends.asterisk import (
    AsteriskAriEvent,
    AsteriskBackend,
    AsteriskBridge,
    AsteriskChannel,
    AsteriskMediaPortConfig,
    AsteriskPlayback,
)


@dataclass(frozen=True, slots=True)
class InboundStasisExampleConfig:
    app: str = "sipx"
    bridge_type: str = "mixing"
    bridge_id_prefix: str = "sipx-bridge"
    media_channel_id_prefix: str = "sipx-media"
    media_endpoint: str = "WebSocket/sipx-media"
    media_app_arg: str = "media"
    greeting_media: str | None = "sound:hello-world"
    media: AsteriskMediaPortConfig = field(default_factory=AsteriskMediaPortConfig)

    def __post_init__(self) -> None:
        if not self.app:
            raise ValueError("app is required")
        if not self.bridge_type:
            raise ValueError("bridge_type is required")
        if not self.bridge_id_prefix:
            raise ValueError("bridge_id_prefix is required")
        if not self.media_channel_id_prefix:
            raise ValueError("media_channel_id_prefix is required")
        if not self.media_endpoint:
            raise ValueError("media_endpoint is required")
        if not self.media_app_arg:
            raise ValueError("media_app_arg is required")


@dataclass(frozen=True, slots=True)
class InboundStasisSession:
    channel: AsteriskChannel
    bridge: AsteriskBridge
    media_channel: AsteriskChannel
    playback: AsteriskPlayback | None
    args: tuple[str, ...] = ()

    def to_timeline_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "channel_id": self.channel.id,
            "bridge_id": self.bridge.id,
            "media_channel_id": self.media_channel.id,
            "args": list(self.args),
        }
        if self.playback is not None:
            data["playback_id"] = self.playback.id
        return data


async def handle_inbound_stasis_start(
    backend: AsteriskBackend,
    *,
    source: AsyncIterable[str | bytes | Mapping[str, Any]] | None = None,
    config: InboundStasisExampleConfig | None = None,
) -> InboundStasisSession | None:
    cfg = config or InboundStasisExampleConfig()
    async for event in backend.events(source):
        if not _is_inbound_stasis_start(event, cfg):
            continue
        return await _build_inbound_session(backend, event, cfg)
    return None


def minimal_asterisk_stasis_config(
    *,
    app: str = "sipx",
    ari_user: str = "sipx",
    context: str = "sipx-inbound",
    bindaddr: str = "127.0.0.1",
    bindport: int = 8088,
) -> dict[str, str]:
    if not app:
        raise ValueError("app is required")
    if not ari_user:
        raise ValueError("ari_user is required")
    if not context:
        raise ValueError("context is required")
    if bindport <= 0:
        raise ValueError("bindport must be positive")
    return {
        "http.conf": (
            f"[general]\nenabled = yes\nbindaddr = {bindaddr}\nbindport = {bindport}\n"
        ),
        "ari.conf": (
            "[general]\n"
            "enabled = yes\n"
            "pretty = no\n\n"
            f"[{ari_user}]\n"
            "type = user\n"
            "read_only = no\n"
            "password = ${ARI_PASSWORD}\n"
        ),
        "extensions.conf": (
            f"[{context}]\n"
            "exten => _X.,1,NoOp(sipx inbound)\n"
            f" same => n,Stasis({app},inbound,${{EXTEN}})\n"
            " same => n,Hangup()\n"
        ),
    }


async def _build_inbound_session(
    backend: AsteriskBackend,
    event: AsteriskAriEvent,
    config: InboundStasisExampleConfig,
) -> InboundStasisSession:
    channel_id = event.channel_id
    if channel_id is None:
        raise ValueError("StasisStart event is missing channel id")
    args = _event_args(event)
    safe_channel_id = _safe_identifier(channel_id)
    bridge_id = f"{config.bridge_id_prefix}-{safe_channel_id}"
    media_channel_id = f"{config.media_channel_id_prefix}-{safe_channel_id}"

    _record_example_event(
        backend,
        "stasis_inbound_started",
        {"channel_id": channel_id, "args": list(args)},
    )
    await backend.answer_channel(channel_id)
    bridge = await backend.create_bridge(
        bridge_type=config.bridge_type,
        bridge_id=bridge_id,
    )
    media_channel = await backend.create_websocket_media_channel(
        config.media_endpoint,
        media_config=config.media,
        app_args=config.media_app_arg,
        channel_id=media_channel_id,
    )
    await backend.add_channel_to_bridge(bridge.id, channel_id)
    await backend.add_channel_to_bridge(bridge.id, media_channel.id)
    playback = None
    if config.greeting_media is not None:
        playback = await backend.play_channel(channel_id, config.greeting_media)

    session = InboundStasisSession(
        channel=event_channel(event),
        bridge=bridge,
        media_channel=media_channel,
        playback=playback,
        args=args,
    )
    _record_example_event(
        backend,
        "stasis_inbound_ready",
        session.to_timeline_data(),
    )
    return session


def event_channel(event: AsteriskAriEvent) -> AsteriskChannel:
    channel = event.raw.get("channel")
    if not isinstance(channel, Mapping):
        raise ValueError("StasisStart event is missing channel payload")
    return AsteriskChannel.from_payload(channel)


def _is_inbound_stasis_start(
    event: AsteriskAriEvent,
    config: InboundStasisExampleConfig,
) -> bool:
    if event.type != "StasisStart":
        return False
    if event.application != config.app:
        return False
    args = _event_args(event)
    if args and args[0] == config.media_app_arg:
        return False
    return event.channel_id is not None


def _event_args(event: AsteriskAriEvent) -> tuple[str, ...]:
    raw_args = event.raw.get("args")
    if not isinstance(raw_args, list):
        return ()
    return tuple(str(item) for item in raw_args)


def _safe_identifier(value: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in value
    )
    return safe.strip("-") or "channel"


def _record_example_event(
    backend: AsteriskBackend,
    name: str,
    data: Mapping[str, Any],
) -> None:
    if backend.timeline is None:
        return
    backend.timeline.record(
        "asterisk",
        name,
        actor_id=backend.actor_id,
        data=dict(data),
    )
