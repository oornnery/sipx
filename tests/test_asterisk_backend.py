import asyncio
import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pytest

from sipx import (
    AsteriskAriClient,
    AsteriskAriConfig,
    AsteriskAriError,
    AsteriskAriHttpResponse,
    AsteriskBackend,
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


def _write_server_text_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    if len(payload) < 126:
        header = bytes([0x81, len(payload)])
    elif len(payload) < 65536:
        header = bytes([0x81, 126]) + len(payload).to_bytes(2, "big")
    else:
        header = bytes([0x81, 127]) + len(payload).to_bytes(8, "big")
    writer.write(header + payload)
