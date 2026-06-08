import asyncio
import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from sipx import (
    AsteriskAriClient,
    AsteriskAriConfig,
    AsteriskAriError,
    AsteriskAriHttpResponse,
    AsteriskBackend,
    AsteriskMediaPath,
    AsteriskMediaPortConfig,
    AsteriskWebSocketMediaPort,
    AudioFrame,
    BackendCapability,
    Timeline,
)

_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def test_asterisk_ari_config_builds_rest_and_event_urls() -> None:
    config = AsteriskAriConfig(
        base_url="http://127.0.0.1:8088",
        username="user",
        password="secret",
        app="sipx",
    )

    assert config.rest_url("channels", {"endpoint": "PJSIP/alice"}) == (
        "http://127.0.0.1:8088/ari/channels?endpoint=PJSIP%2Falice"
    )
    assert config.events_url() == "ws://127.0.0.1:8088/ari/events?app=sipx"
    assert config.authorization_header() == "Basic dXNlcjpzZWNyZXQ="
    assert "secret" not in config.events_url()


def test_asterisk_ari_client_sends_async_rest_request() -> None:
    asyncio.run(_send_async_rest_request())


async def _send_async_rest_request() -> None:
    calls: list[dict[str, Any]] = []

    async def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> AsteriskAriHttpResponse:
        calls.append(
            {
                "method": method,
                "url": url,
                "body": body,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        return AsteriskAriHttpResponse(
            status_code=200,
            body=b'{"id":"chan-1","name":"PJSIP/alice"}',
        )

    config = AsteriskAriConfig(
        base_url="http://127.0.0.1:8088",
        username="user",
        password="secret",
        app="sipx",
        timeout=1.5,
    )
    client = AsteriskAriClient(config, transport=transport)

    response = await client.post(
        "channels",
        query={"endpoint": "PJSIP/alice", "app": "sipx"},
        json_body={"variables": {"TRACE_ID": "run-1"}},
    )

    assert response == {"id": "chan-1", "name": "PJSIP/alice"}
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == (
        "http://127.0.0.1:8088/ari/channels?endpoint=PJSIP%2Falice&app=sipx"
    )
    assert json.loads(calls[0]["body"].decode()) == {"variables": {"TRACE_ID": "run-1"}}
    assert calls[0]["headers"]["Authorization"] == "Basic dXNlcjpzZWNyZXQ="
    assert calls[0]["timeout"] == 1.5


def test_asterisk_ari_client_raises_for_error_status() -> None:
    asyncio.run(_raise_for_error_status())


async def _raise_for_error_status() -> None:
    async def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> AsteriskAriHttpResponse:
        return AsteriskAriHttpResponse(status_code=404, body=b'{"message":"missing"}')

    client = AsteriskAriClient(transport=transport)

    with pytest.raises(AsteriskAriError) as raised:
        await client.get("channels/missing")

    assert raised.value.status_code == 404
    assert raised.value.body == b'{"message":"missing"}'


def test_asterisk_backend_records_ari_websocket_events_to_timeline() -> None:
    asyncio.run(_record_ari_websocket_events_to_timeline())


async def _record_ari_websocket_events_to_timeline() -> None:
    async def source():
        yield {
            "type": "StasisStart",
            "application": "sipx",
            "timestamp": "2026-06-08T00:00:00.000+0000",
            "channel": {"id": "chan-1"},
            "args": ["inbound"],
        }

    timeline = Timeline(run_id="ari-run")
    backend = AsteriskBackend(timeline=timeline, actor_id="pbx")

    events = [event async for event in backend.events(source())]

    assert backend.supports(BackendCapability.ASTERISK_ARI)
    assert events[0].type == "StasisStart"
    assert events[0].channel_id == "chan-1"
    assert timeline.events[0].category == "asterisk"
    assert timeline.events[0].name == "ari_event"
    assert timeline.events[0].actor_id == "pbx"
    assert timeline.events[0].data == {
        "type": "StasisStart",
        "application": "sipx",
        "timestamp": "2026-06-08T00:00:00.000+0000",
        "channel_id": "chan-1",
    }
    assert timeline.events[1].name == "stasis_started"
    assert timeline.events[1].data["channel_id"] == "chan-1"


def test_asterisk_backend_maps_control_methods_to_timeline() -> None:
    asyncio.run(_map_control_methods_to_timeline())


async def _map_control_methods_to_timeline() -> None:
    calls: list[tuple[str, str, dict[str, list[str]], bytes | None]] = []

    async def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> AsteriskAriHttpResponse:
        parsed = urlsplit(url)
        calls.append((method, parsed.path, parse_qs(parsed.query), body))
        if method == "POST" and parsed.path == "/ari/channels":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"chan-1","name":"PJSIP/alice","state":"Ring"}',
            )
        if method == "POST" and parsed.path == "/ari/channels/chan-1/play":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"play-1","target_uri":"channel:chan-1","media_uri":"sound:demo"}',
            )
        if method == "POST" and parsed.path == "/ari/bridges":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"bridge-1","bridge_type":"mixing"}',
            )
        return AsteriskAriHttpResponse(status_code=204)

    config = AsteriskAriConfig(app="sipx")
    client = AsteriskAriClient(config, transport=transport)
    timeline = Timeline(run_id="ari-control")
    backend = AsteriskBackend(client=client, timeline=timeline, actor_id="pbx")

    channel = await backend.originate(
        "PJSIP/alice",
        app_args="scenario-1",
        variables={"TRACE_ID": "run-1"},
        channel_id="chan-1",
    )
    await backend.answer_channel(channel.id)
    await backend.send_dtmf(channel.id, "12#")
    playback = await backend.play_channel(
        channel.id, "sound:demo", playback_id="play-1"
    )
    bridge = await backend.create_bridge(bridge_id="bridge-1")
    await backend.add_channel_to_bridge(bridge.id, channel.id)
    await backend.remove_channel_from_bridge(bridge.id, channel.id)
    await backend.hangup_channel(channel.id, reason="normal")

    assert channel.id == "chan-1"
    assert channel.state == "Ring"
    assert playback.id == "play-1"
    assert bridge.id == "bridge-1"
    assert calls[0] == (
        "POST",
        "/ari/channels",
        {
            "endpoint": ["PJSIP/alice"],
            "app": ["sipx"],
            "appArgs": ["scenario-1"],
            "channelId": ["chan-1"],
        },
        b'{"variables": {"TRACE_ID": "run-1"}}',
    )
    assert calls[2][2] == {"dtmf": ["12#"]}
    assert calls[-1] == (
        "DELETE",
        "/ari/channels/chan-1",
        {"reason": ["normal"]},
        None,
    )

    names = [event.name for event in timeline.events]
    assert names == [
        "ari_request",
        "channel_originated",
        "ari_request",
        "channel_answered",
        "ari_request",
        "dtmf_sent",
        "ari_request",
        "playback_started",
        "ari_request",
        "bridge_created",
        "ari_request",
        "bridge_channel_added",
        "ari_request",
        "bridge_channel_removed",
        "ari_request",
        "channel_hungup",
    ]
    assert timeline.events[1].data == {
        "channel_id": "chan-1",
        "name": "PJSIP/alice",
        "state": "Ring",
    }
    assert timeline.events[5].data == {"channel_id": "chan-1", "digits": "12#"}


def test_asterisk_backend_maps_known_ari_events_to_timeline() -> None:
    asyncio.run(_map_known_ari_events_to_timeline())


async def _map_known_ari_events_to_timeline() -> None:
    async def source():
        yield {
            "type": "ChannelDtmfReceived",
            "application": "sipx",
            "channel": {"id": "chan-1"},
            "digit": "5",
            "duration_ms": 160,
        }
        yield {
            "type": "PlaybackFinished",
            "application": "sipx",
            "playback": {
                "id": "play-1",
                "target_uri": "channel:chan-1",
                "media_uri": "sound:demo",
            },
        }
        yield {
            "type": "ChannelDestroyed",
            "application": "sipx",
            "channel": {"id": "chan-1"},
            "cause": 16,
            "cause_txt": "Normal Clearing",
        }

    timeline = Timeline(run_id="ari-events")
    backend = AsteriskBackend(timeline=timeline, actor_id="pbx")

    events = [event async for event in backend.events(source())]

    assert [event.type for event in events] == [
        "ChannelDtmfReceived",
        "PlaybackFinished",
        "ChannelDestroyed",
    ]
    mapped = [event for event in timeline.events if event.name != "ari_event"]
    assert [event.name for event in mapped] == [
        "dtmf_received",
        "playback_finished",
        "channel_destroyed",
    ]
    assert mapped[0].data == {
        "type": "ChannelDtmfReceived",
        "application": "sipx",
        "channel_id": "chan-1",
        "digit": "5",
        "duration_ms": 160,
    }
    assert mapped[1].data == {
        "type": "PlaybackFinished",
        "application": "sipx",
        "playback_id": "play-1",
        "target_uri": "channel:chan-1",
        "media_uri": "sound:demo",
    }
    assert mapped[2].data == {
        "type": "ChannelDestroyed",
        "application": "sipx",
        "channel_id": "chan-1",
        "cause": 16,
        "cause_txt": "Normal Clearing",
    }


def test_asterisk_media_config_selects_websocket_mvp() -> None:
    asyncio.run(_select_websocket_media_mvp())


async def _select_websocket_media_mvp() -> None:
    calls: list[tuple[str, str, dict[str, list[str]]]] = []

    async def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> AsteriskAriHttpResponse:
        parsed = urlsplit(url)
        calls.append((method, parsed.path, parse_qs(parsed.query)))
        return AsteriskAriHttpResponse(
            status_code=200,
            body=b'{"id":"media-1","name":"WebSocket/sipx","state":"Up"}',
        )

    config = AsteriskMediaPortConfig()
    assert config.path is AsteriskMediaPath.WEBSOCKET

    client = AsteriskAriClient(transport=transport)
    timeline = Timeline(run_id="media-path")
    backend = AsteriskBackend(client=client, timeline=timeline, actor_id="pbx")

    channel = await backend.create_websocket_media_channel(
        "WebSocket/sipx",
        media_config=config,
        channel_id="media-1",
    )

    assert backend.supports(BackendCapability.MEDIA)
    assert channel.id == "media-1"
    assert calls[0] == (
        "POST",
        "/ari/channels",
        {
            "endpoint": ["WebSocket/sipx"],
            "app": ["sipx"],
            "channelId": ["media-1"],
        },
    )
    assert timeline.events[-1].name == "media_channel_created"
    assert timeline.events[-1].data["path"] == "websocket_media"

    with pytest.raises(AsteriskAriError, match="MVP path"):
        await backend.create_media_port(
            config=AsteriskMediaPortConfig(path=AsteriskMediaPath.AUDIOSOCKET),
            incoming=_binary_source(b""),
            sender=lambda payload: None,
        )


def test_asterisk_websocket_media_port_sends_and_receives_frames() -> None:
    asyncio.run(_send_and_receive_media_frames())


async def _send_and_receive_media_frames() -> None:
    sent: list[bytes] = []
    closed: list[bool] = []
    timeline = Timeline(run_id="media-port")
    backend = AsteriskBackend(timeline=timeline, actor_id="pbx")
    port = await backend.create_media_port(
        incoming=_binary_source(b"\x01\x02\x03\x04"),
        sender=lambda payload: sent.append(payload),
        closer=lambda: closed.append(True),
        channel_id="chan-1",
        clock_ns=lambda: 123,
    )

    frame = await port.recv_frame()
    assert frame.pcm.tobytes() == b"\x01\x02\x03\x04"
    assert frame.sample_rate == 16000
    assert frame.channels == 1
    assert frame.duration_ms == 20
    assert frame.timestamp_ns == 123
    assert frame.source == "websocket"

    await port.send_frame(
        AudioFrame(
            pcm=memoryview(b"\x05\x06"),
            sample_rate=16000,
            channels=1,
            duration_ms=20,
            timestamp_ns=124,
            source="tts",
        )
    )
    await port.close()

    assert sent == [b"\x05\x06"]
    assert closed == [True]
    names = [(event.category, event.name) for event in timeline.events]
    assert names == [
        ("asterisk", "media_path_selected"),
        ("media", "frame_received"),
        ("media", "frame_sent"),
        ("media", "media_port_closed"),
    ]
    assert timeline.events[1].data["channel_id"] == "chan-1"
    assert timeline.events[1].data["byte_length"] == 4


def test_asterisk_websocket_media_port_connects_to_binary_websocket() -> None:
    asyncio.run(_connect_binary_websocket_media_port())


async def _connect_binary_websocket_media_port() -> None:
    received: dict[str, Any] = {}

    async def handle_client(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await _accept_websocket_client(reader, writer, received)
        _write_server_binary_frame(writer, b"\x10\x20")
        await writer.drain()

        opcode, payload = await _read_client_frame(reader)
        received["opcode"] = opcode
        received["payload"] = payload

        close_opcode, _ = await _read_client_frame(reader)
        received["close_opcode"] = close_opcode
        writer.write(b"\x88\x00")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    try:
        port_number = server.sockets[0].getsockname()[1]
        port = await AsteriskWebSocketMediaPort.connect(
            f"ws://127.0.0.1:{port_number}/media",
            config=AsteriskMediaPortConfig(frame_duration_ms=10),
            timeout=1.0,
            clock_ns=lambda: 999,
        )
        frame = await port.recv_frame()
        await port.send_frame(
            AudioFrame(
                pcm=memoryview(b"\x30\x40"),
                sample_rate=16000,
                channels=1,
                duration_ms=10,
                timestamp_ns=1000,
                source="tts",
            )
        )
        await port.close()
    finally:
        server.close()
        await server.wait_closed()

    assert frame.pcm.tobytes() == b"\x10\x20"
    assert frame.duration_ms == 10
    assert received["request_line"] == "GET /media HTTP/1.1"
    assert received["opcode"] == 0x2
    assert received["payload"] == b"\x30\x40"
    assert received["close_opcode"] == 0x8


def test_asterisk_ari_client_reads_websocket_events() -> None:
    asyncio.run(_read_websocket_events())


async def _read_websocket_events() -> None:
    received: dict[str, Any] = {}
    event_payload = {
        "type": "ChannelStateChange",
        "application": "sipx",
        "channel": {"id": "chan-ws-1"},
    }

    async def handle_client(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        request_line = (await reader.readline()).decode("ascii").strip()
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
            name, _, value = line.decode("ascii").partition(":")
            headers[name.lower()] = value.strip()
        received["request_line"] = request_line
        received["headers"] = headers

        accept = base64.b64encode(
            hashlib.sha1(
                f"{headers['sec-websocket-key']}{_WEBSOCKET_GUID}".encode("ascii")
            ).digest()
        ).decode("ascii")
        writer.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        await writer.drain()
        _write_server_text_frame(writer, json.dumps(event_payload).encode("utf-8"))
        writer.write(b"\x88\x00")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        config = AsteriskAriConfig(
            base_url=f"http://127.0.0.1:{port}",
            username="user",
            password="secret",
            app="sipx",
            timeout=1.0,
        )
        client = AsteriskAriClient(config)

        events = [event async for event in client.iter_events()]
    finally:
        server.close()
        await server.wait_closed()

    assert events[0].type == "ChannelStateChange"
    assert events[0].channel_id == "chan-ws-1"
    assert received["request_line"] == "GET /ari/events?app=sipx HTTP/1.1"
    assert received["headers"]["authorization"] == "Basic dXNlcjpzZWNyZXQ="


async def _binary_source(payload: bytes):
    yield payload


async def _accept_websocket_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    received: dict[str, Any],
) -> None:
    request_line = (await reader.readline()).decode("ascii").strip()
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in {b"\r\n", b"\n", b""}:
            break
        name, _, value = line.decode("ascii").partition(":")
        headers[name.lower()] = value.strip()
    received["request_line"] = request_line
    received["headers"] = headers

    accept = base64.b64encode(
        hashlib.sha1(
            f"{headers['sec-websocket-key']}{_WEBSOCKET_GUID}".encode("ascii")
        ).digest()
    ).decode("ascii")
    writer.write(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    await writer.drain()


async def _read_client_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    head = await reader.readexactly(2)
    opcode = head[0] & 0x0F
    length = head[1] & 0x7F
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), "big")
    mask = await reader.readexactly(4)
    payload = await reader.readexactly(length)
    return opcode, bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


def _write_server_binary_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    _write_server_frame(writer, 0x2, payload)


def _write_server_text_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    _write_server_frame(writer, 0x1, payload)


def _write_server_frame(
    writer: asyncio.StreamWriter,
    opcode: int,
    payload: bytes,
) -> None:
    if len(payload) < 126:
        header = bytes([0x80 | opcode, len(payload)])
    elif len(payload) < 65536:
        header = bytes([0x80 | opcode, 126]) + len(payload).to_bytes(2, "big")
    else:
        header = bytes([0x80 | opcode, 127]) + len(payload).to_bytes(8, "big")
    writer.write(header + payload)
