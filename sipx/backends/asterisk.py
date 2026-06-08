from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import ssl as ssl_module
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sipx.core.capabilities import BackendCapability
from sipx.core.timeline import Timeline
from sipx.media.frame import AudioFrame

_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_EVENT_BYTES = 1_048_576


class AsteriskAriError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class AsteriskMediaPath(StrEnum):
    WEBSOCKET = "websocket_media"
    AUDIOSOCKET = "audiosocket"
    EXTERNAL_MEDIA_RTP = "external_media_rtp"


@dataclass(frozen=True, slots=True)
class AsteriskMediaPortConfig:
    path: AsteriskMediaPath | str = AsteriskMediaPath.WEBSOCKET
    codec: str = "slin16"
    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20
    direction: str = "both"
    max_frame_bytes: int = _MAX_EVENT_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", AsteriskMediaPath(self.path))
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        if self.max_frame_bytes <= 0:
            raise ValueError("max_frame_bytes must be positive")
        if self.direction not in {"in", "out", "both"}:
            raise ValueError("direction must be in, out, or both")
        if not self.codec:
            raise ValueError("codec is required")

    def to_timeline_data(self) -> dict[str, int | str]:
        return {
            "path": self.path.value,
            "codec": self.codec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "frame_duration_ms": self.frame_duration_ms,
            "direction": self.direction,
        }


@dataclass(frozen=True, slots=True)
class AsteriskAriConfig:
    base_url: str = "http://127.0.0.1:8088"
    username: str = "sipx"
    password: str = ""
    app: str = "sipx"
    timeout: float = 5.0

    def __post_init__(self) -> None:
        parts = urlsplit(self.base_url)
        if parts.scheme not in {"http", "https", "ws", "wss"}:
            raise ValueError("base_url must use http, https, ws, or wss")
        if not parts.netloc:
            raise ValueError("base_url must include a host")
        if not self.username:
            raise ValueError("username is required")
        if not self.app:
            raise ValueError("app is required")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    def authorization_header(self) -> str:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode(
            "ascii"
        )
        return f"Basic {token}"

    def rest_url(
        self,
        path: str,
        query: Mapping[str, object] | None = None,
    ) -> str:
        parts = urlsplit(self.base_url)
        scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
        return _build_ari_url(parts, scheme, path, query)

    def events_url(self, query: Mapping[str, object] | None = None) -> str:
        parts = urlsplit(self.base_url)
        scheme = "wss" if parts.scheme in {"https", "wss"} else "ws"
        event_query = {"app": self.app}
        event_query.update(dict(query or {}))
        return _build_ari_url(parts, scheme, "events", event_query)


@dataclass(frozen=True, slots=True)
class AsteriskAriHttpResponse:
    status_code: int
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AsteriskAriEvent:
    type: str
    raw: Mapping[str, Any]
    application: str | None = None
    timestamp: str | None = None
    channel_id: str | None = None
    bridge_id: str | None = None

    @classmethod
    def from_payload(cls, payload: str | bytes | Mapping[str, Any]) -> AsteriskAriEvent:
        data = _decode_event_payload(payload)
        event_type = data.get("type")
        if not isinstance(event_type, str) or not event_type:
            raise AsteriskAriError("ARI event payload is missing type")
        return cls(
            type=event_type,
            raw=data,
            application=_string_or_none(data.get("application")),
            timestamp=_string_or_none(data.get("timestamp")),
            channel_id=_nested_id(data.get("channel")),
            bridge_id=_nested_id(data.get("bridge")),
        )

    def to_timeline_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type}
        if self.application is not None:
            data["application"] = self.application
        if self.timestamp is not None:
            data["timestamp"] = self.timestamp
        if self.channel_id is not None:
            data["channel_id"] = self.channel_id
        if self.bridge_id is not None:
            data["bridge_id"] = self.bridge_id
        return data


@dataclass(frozen=True, slots=True)
class AsteriskChannel:
    id: str
    raw: Mapping[str, Any]
    name: str | None = None
    state: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> AsteriskChannel:
        return cls(
            id=_required_id(payload, "channel"),
            raw=dict(payload),
            name=_string_or_none(payload.get("name")),
            state=_string_or_none(payload.get("state")),
        )

    def to_timeline_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"channel_id": self.id}
        if self.name is not None:
            data["name"] = self.name
        if self.state is not None:
            data["state"] = self.state
        return data


@dataclass(frozen=True, slots=True)
class AsteriskBridge:
    id: str
    raw: Mapping[str, Any]
    bridge_type: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> AsteriskBridge:
        return cls(
            id=_required_id(payload, "bridge"),
            raw=dict(payload),
            bridge_type=_string_or_none(payload.get("bridge_type")),
        )

    def to_timeline_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"bridge_id": self.id}
        if self.bridge_type is not None:
            data["bridge_type"] = self.bridge_type
        return data


@dataclass(frozen=True, slots=True)
class AsteriskPlayback:
    id: str
    raw: Mapping[str, Any]
    target_uri: str | None = None
    media_uri: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> AsteriskPlayback:
        return cls(
            id=_required_id(payload, "playback"),
            raw=dict(payload),
            target_uri=_string_or_none(payload.get("target_uri")),
            media_uri=_string_or_none(payload.get("media_uri")),
        )

    def to_timeline_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"playback_id": self.id}
        if self.target_uri is not None:
            data["target_uri"] = self.target_uri
        if self.media_uri is not None:
            data["media_uri"] = self.media_uri
        return data


HttpTransport = Callable[
    [str, str, bytes | None, Mapping[str, str], float],
    AsteriskAriHttpResponse | Awaitable[AsteriskAriHttpResponse],
]
BinarySender = Callable[[bytes], None | Awaitable[None]]
CloseCallback = Callable[[], None | Awaitable[None]]


class AsteriskWebSocketMediaPort:
    def __init__(
        self,
        *,
        config: AsteriskMediaPortConfig | None = None,
        incoming: AsyncIterable[bytes],
        sender: BinarySender,
        closer: CloseCallback | None = None,
        timeline: Timeline | None = None,
        actor_id: str | None = None,
        channel_id: str | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.config = config or AsteriskMediaPortConfig()
        if self.config.path is not AsteriskMediaPath.WEBSOCKET:
            raise ValueError("AsteriskWebSocketMediaPort requires websocket media path")
        self.timeline = timeline
        self.actor_id = actor_id
        self.channel_id = channel_id
        self._incoming = incoming.__aiter__()
        self._sender = sender
        self._closer = closer
        self._clock_ns = clock_ns
        self._closed = False

    @classmethod
    async def connect(
        cls,
        url: str,
        *,
        config: AsteriskMediaPortConfig | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 5.0,
        timeline: Timeline | None = None,
        actor_id: str | None = None,
        channel_id: str | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> AsteriskWebSocketMediaPort:
        connection = await _open_websocket_connection(
            url,
            headers=headers or {},
            timeout=timeout,
        )
        return cls(
            config=config,
            incoming=connection.binary_messages(timeout=timeout),
            sender=connection.send_binary,
            closer=connection.close,
            timeline=timeline,
            actor_id=actor_id,
            channel_id=channel_id,
            clock_ns=clock_ns,
        )

    async def recv_frame(self) -> AudioFrame:
        self._raise_if_closed()
        payload = await anext(self._incoming)
        if len(payload) > self.config.max_frame_bytes:
            raise AsteriskAriError("Asterisk WebSocket media frame exceeds size limit")
        frame = AudioFrame(
            pcm=memoryview(payload),
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            duration_ms=self.config.frame_duration_ms,
            timestamp_ns=self._clock_ns(),
            source="websocket",
        )
        self._record_media_event("frame_received", frame)
        return frame

    async def send_frame(self, frame: AudioFrame) -> None:
        self._raise_if_closed()
        if frame.sample_rate != self.config.sample_rate:
            raise ValueError("frame sample_rate does not match media port")
        if frame.channels != self.config.channels:
            raise ValueError("frame channels do not match media port")
        result = self._sender(frame.pcm.tobytes())
        if isinstance(result, Awaitable):
            await result
        self._record_media_event("frame_sent", frame)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._closer is not None:
            result = self._closer()
            if isinstance(result, Awaitable):
                await result
        self._record_timeline(
            "media_port_closed",
            self.config.to_timeline_data(),
        )

    def _record_media_event(self, name: str, frame: AudioFrame) -> None:
        data = self.config.to_timeline_data()
        data.update(frame.to_dict())
        self._record_timeline(name, data)

    def _record_timeline(self, name: str, data: Mapping[str, Any]) -> None:
        if self.timeline is None:
            return
        event_data = dict(data)
        if self.channel_id is not None:
            event_data["channel_id"] = self.channel_id
        self.timeline.record(
            "media",
            name,
            actor_id=self.actor_id,
            data=event_data,
        )

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise AsteriskAriError("Asterisk WebSocket media port is closed")


class AsteriskAriClient:
    def __init__(
        self,
        config: AsteriskAriConfig | None = None,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        self.config = config or AsteriskAriConfig()
        self._transport = transport or _stdlib_http_transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> Any:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": self.config.authorization_header(),
        }
        if json_body is not None:
            body = json.dumps(json_body, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"

        response = self._transport(
            method.upper(),
            self.config.rest_url(path, query),
            body,
            headers,
            self.config.timeout,
        )
        if isinstance(response, Awaitable):
            response = await response
        if not 200 <= response.status_code < 300:
            raise AsteriskAriError(
                f"ARI request failed with HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.body,
            )
        if not response.body:
            return None
        return json.loads(response.body.decode("utf-8"))

    async def get(
        self,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
    ) -> Any:
        return await self.request("GET", path, query=query)

    async def post(
        self,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> Any:
        return await self.request("POST", path, query=query, json_body=json_body)

    async def delete(
        self,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
    ) -> Any:
        return await self.request("DELETE", path, query=query)

    async def iter_events(
        self,
        source: AsyncIterable[str | bytes | Mapping[str, Any]] | None = None,
    ) -> AsyncIterator[AsteriskAriEvent]:
        messages = source if source is not None else self.websocket_messages()
        async for payload in messages:
            yield AsteriskAriEvent.from_payload(payload)

    async def websocket_messages(self) -> AsyncIterator[str]:
        async for message in _read_websocket_text_messages(
            self.config.events_url(),
            headers={"Authorization": self.config.authorization_header()},
            timeout=self.config.timeout,
        ):
            yield message


class AsteriskBackend:
    """Asterisk ARI control-plane backend.

    Media path and high-level call mapping are intentionally left to later blocks.
    """

    capabilities = frozenset(
        {
            BackendCapability.ASTERISK_ARI,
            BackendCapability.CALL_CONTROL,
            BackendCapability.MEDIA,
            BackendCapability.TIMELINE,
        }
    )

    def __init__(
        self,
        config: AsteriskAriConfig | None = None,
        *,
        client: AsteriskAriClient | None = None,
        timeline: Timeline | None = None,
        actor_id: str | None = None,
    ) -> None:
        self.config = config or (
            client.config if client is not None else AsteriskAriConfig()
        )
        self.client = client or AsteriskAriClient(self.config)
        self.timeline = timeline
        self.actor_id = actor_id

    def supports(self, capability: BackendCapability | str) -> bool:
        return BackendCapability(capability) in self.capabilities

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> Any:
        response = await self.client.request(
            method,
            path,
            query=query,
            json_body=json_body,
        )
        if self.timeline is not None:
            self.timeline.record(
                "asterisk",
                "ari_request",
                actor_id=self.actor_id,
                data={"method": method.upper(), "path": path},
            )
        return response

    async def originate(
        self,
        endpoint: str,
        *,
        app_args: str | None = None,
        variables: Mapping[str, object] | None = None,
        channel_id: str | None = None,
    ) -> AsteriskChannel:
        query: dict[str, object] = {"endpoint": endpoint, "app": self.config.app}
        if app_args:
            query["appArgs"] = app_args
        if channel_id:
            query["channelId"] = channel_id
        payload = await self.request(
            "POST",
            "channels",
            query=query,
            json_body={"variables": dict(variables)} if variables else None,
        )
        channel = AsteriskChannel.from_payload(_require_mapping(payload, "channel"))
        self._record_timeline("channel_originated", channel.to_timeline_data())
        return channel

    async def answer_channel(self, channel_id: str) -> None:
        await self.request("POST", f"channels/{channel_id}/answer")
        self._record_timeline("channel_answered", {"channel_id": channel_id})

    async def hangup_channel(
        self, channel_id: str, *, reason: str | None = None
    ) -> None:
        query = {"reason": reason} if reason else None
        await self.request("DELETE", f"channels/{channel_id}", query=query)
        data = {"channel_id": channel_id}
        if reason:
            data["reason"] = reason
        self._record_timeline("channel_hungup", data)

    async def play_channel(
        self,
        channel_id: str,
        media: str,
        *,
        playback_id: str | None = None,
    ) -> AsteriskPlayback:
        query: dict[str, object] = {"media": media}
        if playback_id:
            query["playbackId"] = playback_id
        payload = await self.request("POST", f"channels/{channel_id}/play", query=query)
        playback = AsteriskPlayback.from_payload(_require_mapping(payload, "playback"))
        data = playback.to_timeline_data()
        data["channel_id"] = channel_id
        self._record_timeline("playback_started", data)
        return playback

    async def send_dtmf(self, channel_id: str, digits: str) -> None:
        if not digits:
            raise ValueError("digits are required")
        await self.request(
            "POST", f"channels/{channel_id}/dtmf", query={"dtmf": digits}
        )
        self._record_timeline(
            "dtmf_sent",
            {"channel_id": channel_id, "digits": digits},
        )

    async def create_bridge(
        self,
        *,
        bridge_type: str = "mixing",
        bridge_id: str | None = None,
    ) -> AsteriskBridge:
        query: dict[str, object] = {"type": bridge_type}
        if bridge_id:
            query["bridgeId"] = bridge_id
        payload = await self.request("POST", "bridges", query=query)
        bridge = AsteriskBridge.from_payload(_require_mapping(payload, "bridge"))
        self._record_timeline("bridge_created", bridge.to_timeline_data())
        return bridge

    async def add_channel_to_bridge(self, bridge_id: str, channel_id: str) -> None:
        await self.request(
            "POST",
            f"bridges/{bridge_id}/addChannel",
            query={"channel": channel_id},
        )
        self._record_timeline(
            "bridge_channel_added",
            {"bridge_id": bridge_id, "channel_id": channel_id},
        )

    async def remove_channel_from_bridge(self, bridge_id: str, channel_id: str) -> None:
        await self.request(
            "POST",
            f"bridges/{bridge_id}/removeChannel",
            query={"channel": channel_id},
        )
        self._record_timeline(
            "bridge_channel_removed",
            {"bridge_id": bridge_id, "channel_id": channel_id},
        )

    async def create_websocket_media_channel(
        self,
        endpoint: str,
        *,
        media_config: AsteriskMediaPortConfig | None = None,
        app_args: str | None = None,
        variables: Mapping[str, object] | None = None,
        channel_id: str | None = None,
    ) -> AsteriskChannel:
        config = media_config or AsteriskMediaPortConfig()
        self._ensure_websocket_media_path(config)
        channel = await self.originate(
            endpoint,
            app_args=app_args,
            variables=variables,
            channel_id=channel_id,
        )
        data = channel.to_timeline_data()
        data.update(config.to_timeline_data())
        self._record_timeline("media_channel_created", data)
        return channel

    async def create_media_port(
        self,
        *,
        config: AsteriskMediaPortConfig | None = None,
        websocket_url: str | None = None,
        incoming: AsyncIterable[bytes] | None = None,
        sender: BinarySender | None = None,
        closer: CloseCallback | None = None,
        channel_id: str | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> AsteriskWebSocketMediaPort:
        media_config = config or AsteriskMediaPortConfig()
        self._ensure_websocket_media_path(media_config)
        self._record_timeline("media_path_selected", media_config.to_timeline_data())
        if websocket_url is not None:
            return await AsteriskWebSocketMediaPort.connect(
                websocket_url,
                config=media_config,
                headers={"Authorization": self.config.authorization_header()},
                timeout=self.config.timeout,
                timeline=self.timeline,
                actor_id=self.actor_id,
                channel_id=channel_id,
                clock_ns=clock_ns,
            )
        if incoming is None or sender is None:
            raise AsteriskAriError(
                "incoming and sender are required when websocket_url is not provided"
            )
        return AsteriskWebSocketMediaPort(
            config=media_config,
            incoming=incoming,
            sender=sender,
            closer=closer,
            timeline=self.timeline,
            actor_id=self.actor_id,
            channel_id=channel_id,
            clock_ns=clock_ns,
        )

    async def events(
        self,
        source: AsyncIterable[str | bytes | Mapping[str, Any]] | None = None,
    ) -> AsyncIterator[AsteriskAriEvent]:
        async for event in self.client.iter_events(source):
            self._record_timeline("ari_event", event.to_timeline_data())
            self._record_mapped_ari_event(event)
            yield event

    def _record_mapped_ari_event(self, event: AsteriskAriEvent) -> None:
        name = _ARI_EVENT_TIMELINE_NAMES.get(event.type)
        if name is None:
            return
        self._record_timeline(name, _ari_event_timeline_data(event))

    def _ensure_websocket_media_path(self, config: AsteriskMediaPortConfig) -> None:
        if config.path is AsteriskMediaPath.WEBSOCKET:
            return
        raise AsteriskAriError(
            f"Asterisk media path {config.path.value!r} is planned; "
            "MVP path is 'websocket_media'"
        )

    def _record_timeline(self, name: str, data: Mapping[str, Any]) -> None:
        if self.timeline is None:
            return
        self.timeline.record(
            "asterisk",
            name,
            actor_id=self.actor_id,
            data=dict(data),
        )


_ARI_EVENT_TIMELINE_NAMES = {
    "BridgeCreated": "bridge_created",
    "BridgeDestroyed": "bridge_destroyed",
    "ChannelDestroyed": "channel_destroyed",
    "ChannelDtmfReceived": "dtmf_received",
    "ChannelEnteredBridge": "bridge_channel_entered",
    "ChannelLeftBridge": "bridge_channel_left",
    "ChannelStateChange": "channel_state_changed",
    "PlaybackFinished": "playback_finished",
    "PlaybackStarted": "playback_started",
    "StasisEnd": "stasis_ended",
    "StasisStart": "stasis_started",
}


def _build_ari_url(
    parts: Any,
    scheme: str,
    path: str,
    query: Mapping[str, object] | None,
) -> str:
    base_path = parts.path.rstrip("/")
    ari_root = base_path if base_path.endswith("/ari") else f"{base_path}/ari"
    url_path = f"{ari_root}/{path.strip('/')}"
    query_string = urlencode(dict(query or {}), doseq=True)
    return urlunsplit((scheme, parts.netloc, url_path, query_string, ""))


async def _stdlib_http_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> AsteriskAriHttpResponse:
    return await asyncio.to_thread(
        _sync_http_request, method, url, body, headers, timeout
    )


def _sync_http_request(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> AsteriskAriHttpResponse:
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return AsteriskAriHttpResponse(
                status_code=response.status,
                body=response.read(),
                headers=dict(response.headers.items()),
            )
    except HTTPError as exc:
        return AsteriskAriHttpResponse(
            status_code=exc.code,
            body=exc.read(),
            headers=dict(exc.headers.items()),
        )
    except URLError as exc:
        raise AsteriskAriError(f"ARI request failed: {exc.reason}") from exc


@dataclass(slots=True)
class _WebSocketConnection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    async def text_messages(self, *, timeout: float) -> AsyncIterator[str]:
        async for opcode, payload in self._messages(timeout=timeout):
            if opcode == 0x1:
                yield payload.decode("utf-8")

    async def binary_messages(self, *, timeout: float) -> AsyncIterator[bytes]:
        async for opcode, payload in self._messages(timeout=timeout):
            if opcode == 0x2:
                yield payload

    async def send_binary(self, payload: bytes) -> None:
        await _write_websocket_frame(self.writer, 0x2, payload)

    async def close(self) -> None:
        if not self.writer.is_closing():
            await _write_websocket_frame(self.writer, 0x8, b"")
        self.writer.close()
        await self.writer.wait_closed()

    async def _messages(self, *, timeout: float) -> AsyncIterator[tuple[int, bytes]]:
        while True:
            opcode, payload = await _read_websocket_frame(self.reader, timeout)
            if opcode == 0x8:
                break
            if opcode == 0x9:
                await _write_websocket_frame(self.writer, 0xA, payload)
                continue
            yield opcode, payload


async def _open_websocket_connection(
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: float,
) -> _WebSocketConnection:
    parts = urlsplit(url)
    if parts.scheme not in {"ws", "wss"}:
        raise AsteriskAriError("WebSocket URL must use ws or wss")
    if parts.hostname is None:
        raise AsteriskAriError("WebSocket URL must include a host")

    port = parts.port or (443 if parts.scheme == "wss" else 80)
    ssl_context = ssl_module.create_default_context() if parts.scheme == "wss" else None
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(parts.hostname, port, ssl=ssl_context),
        timeout=timeout,
    )
    key = await _send_websocket_handshake(writer, url, headers, timeout)
    await _read_websocket_handshake(reader, timeout, key)
    return _WebSocketConnection(reader=reader, writer=writer)


async def _read_websocket_text_messages(
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: float,
) -> AsyncIterator[str]:
    connection = await _open_websocket_connection(
        url,
        headers=headers,
        timeout=timeout,
    )
    try:
        async for message in connection.text_messages(timeout=timeout):
            yield message
    finally:
        await connection.close()


async def _send_websocket_handshake(
    writer: asyncio.StreamWriter,
    url: str,
    headers: Mapping[str, str],
    timeout: float,
) -> str:
    parts = urlsplit(url)
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    request_lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "Connection: Upgrade",
        "Upgrade: websocket",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    request_lines.extend(f"{name}: {value}" for name, value in headers.items())
    writer.write(("\r\n".join(request_lines) + "\r\n\r\n").encode("ascii"))
    await asyncio.wait_for(writer.drain(), timeout=timeout)
    return key


async def _read_websocket_handshake(
    reader: asyncio.StreamReader,
    timeout: float,
    key: str,
) -> None:
    status = await asyncio.wait_for(reader.readline(), timeout=timeout)
    if b" 101 " not in status:
        raise AsteriskAriError("ARI WebSocket handshake failed")
    headers: dict[str, str] = {}
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if line in {b"\r\n", b"\n", b""}:
            break
        name, _, value = line.decode("ascii").partition(":")
        headers[name.lower()] = value.strip()
    if headers.get("upgrade", "").lower() != "websocket":
        raise AsteriskAriError("ARI WebSocket handshake missing upgrade header")
    expected = base64.b64encode(
        hashlib.sha1(f"{key}{_WEBSOCKET_GUID}".encode("ascii")).digest()
    ).decode("ascii")
    if headers.get("sec-websocket-accept") != expected:
        raise AsteriskAriError("ARI WebSocket handshake accept mismatch")


async def _read_websocket_frame(
    reader: asyncio.StreamReader,
    timeout: float,
) -> tuple[int, bytes]:
    head = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    length = head[1] & 0x7F
    if length == 126:
        length = int.from_bytes(
            await asyncio.wait_for(reader.readexactly(2), timeout=timeout),
            "big",
        )
    elif length == 127:
        length = int.from_bytes(
            await asyncio.wait_for(reader.readexactly(8), timeout=timeout),
            "big",
        )
    if length > _MAX_EVENT_BYTES:
        raise AsteriskAriError("ARI WebSocket event exceeds size limit")
    mask = (
        await asyncio.wait_for(reader.readexactly(4), timeout=timeout)
        if masked
        else b""
    )
    payload = await asyncio.wait_for(reader.readexactly(length), timeout=timeout)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


async def _write_websocket_frame(
    writer: asyncio.StreamWriter,
    opcode: int,
    payload: bytes,
) -> None:
    mask = secrets.token_bytes(4)
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 65536:
        header += bytes([0x80 | 126]) + length.to_bytes(2, "big")
    else:
        header += bytes([0x80 | 127]) + length.to_bytes(8, "big")
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    writer.write(header + mask + masked)
    await writer.drain()


def _decode_event_payload(payload: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise AsteriskAriError("ARI event payload must be a JSON object")
    return data


def _ari_event_timeline_data(event: AsteriskAriEvent) -> dict[str, Any]:
    data = event.to_timeline_data()
    raw = event.raw
    _copy_nested(data, raw, "playback", "id", "playback_id")
    _copy_nested(data, raw, "playback", "target_uri", "target_uri")
    _copy_nested(data, raw, "playback", "media_uri", "media_uri")
    for key in ("digit", "duration_ms", "state", "cause", "cause_txt"):
        if key in raw:
            data[key] = raw[key]
    return data


def _copy_nested(
    data: dict[str, Any],
    raw: Mapping[str, Any],
    parent_key: str,
    source_key: str,
    target_key: str,
) -> None:
    parent = raw.get(parent_key)
    if isinstance(parent, Mapping) and parent.get(source_key) is not None:
        data[target_key] = parent[source_key]


def _require_mapping(payload: object, name: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise AsteriskAriError(f"ARI {name} response must be a JSON object")
    return payload


def _required_id(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get("id")
    if not value:
        raise AsteriskAriError(f"ARI {name} response is missing id")
    return str(value)


def _nested_id(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return _string_or_none(value.get("id"))


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
