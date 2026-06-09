import asyncio
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit

from sipx import Timeline
from sipx_asterisk import (
    AsteriskAriClient,
    AsteriskAriHttpResponse,
    AsteriskBackend,
    handle_inbound_stasis_start,
    minimal_asterisk_stasis_config,
)


def test_minimal_asterisk_stasis_config_uses_placeholders() -> None:
    snippets = minimal_asterisk_stasis_config()

    assert set(snippets) == {"http.conf", "ari.conf", "extensions.conf"}
    assert "bindaddr = 127.0.0.1" in snippets["http.conf"]
    assert "[sipx]" in snippets["ari.conf"]
    assert "password = ${ARI_PASSWORD}" in snippets["ari.conf"]
    assert "Stasis(sipx,inbound,${EXTEN})" in snippets["extensions.conf"]
    assert "secret" not in "\n".join(snippets.values()).lower()


def test_inbound_stasis_example_answers_and_bridges_media() -> None:
    asyncio.run(_answer_and_bridge_media())


async def _answer_and_bridge_media() -> None:
    calls: list[tuple[str, str, dict[str, list[str]], bytes | None]] = []

    async def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> AsteriskAriHttpResponse:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        calls.append((method, parsed.path, query, body))
        if method == "POST" and parsed.path == "/ari/bridges":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"sipx-bridge-SIP-alice-0001","bridge_type":"mixing"}',
            )
        if method == "POST" and parsed.path == "/ari/channels":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"sipx-media-SIP-alice-0001","name":"WebSocket/sipx-media","state":"Up"}',
            )
        if method == "POST" and parsed.path == "/ari/channels/SIP:alice-0001/play":
            return AsteriskAriHttpResponse(
                status_code=200,
                body=b'{"id":"play-1","target_uri":"channel:SIP:alice-0001","media_uri":"sound:hello-world"}',
            )
        return AsteriskAriHttpResponse(status_code=204)

    async def source():
        yield {
            "type": "StasisStart",
            "application": "sipx",
            "channel": {"id": "sipx-media-SIP-alice-0001", "state": "Up"},
            "args": ["media"],
        }
        yield {
            "type": "StasisStart",
            "application": "sipx",
            "channel": {"id": "SIP:alice-0001", "name": "PJSIP/alice", "state": "Ring"},
            "args": ["inbound", "1234"],
        }

    timeline = Timeline(run_id="stasis-example")
    backend = AsteriskBackend(
        client=AsteriskAriClient(transport=transport),
        timeline=timeline,
        actor_id="pbx",
    )

    session = await handle_inbound_stasis_start(backend, source=source())

    assert session is not None
    assert session.channel.id == "SIP:alice-0001"
    assert session.media_channel.id == "sipx-media-SIP-alice-0001"
    assert session.bridge.id == "sipx-bridge-SIP-alice-0001"
    assert session.playback is not None
    assert session.playback.id == "play-1"
    assert session.args == ("inbound", "1234")

    assert calls == [
        ("POST", "/ari/channels/SIP:alice-0001/answer", {}, None),
        (
            "POST",
            "/ari/bridges",
            {"type": ["mixing"], "bridgeId": ["sipx-bridge-SIP-alice-0001"]},
            None,
        ),
        (
            "POST",
            "/ari/channels",
            {
                "endpoint": ["WebSocket/sipx-media"],
                "app": ["sipx"],
                "appArgs": ["media"],
                "channelId": ["sipx-media-SIP-alice-0001"],
            },
            None,
        ),
        (
            "POST",
            "/ari/bridges/sipx-bridge-SIP-alice-0001/addChannel",
            {"channel": ["SIP:alice-0001"]},
            None,
        ),
        (
            "POST",
            "/ari/bridges/sipx-bridge-SIP-alice-0001/addChannel",
            {"channel": ["sipx-media-SIP-alice-0001"]},
            None,
        ),
        (
            "POST",
            "/ari/channels/SIP:alice-0001/play",
            {"media": ["sound:hello-world"]},
            None,
        ),
    ]

    names = [event.name for event in timeline.events]
    assert "stasis_inbound_started" in names
    assert "stasis_inbound_ready" in names
    ready = timeline.events[names.index("stasis_inbound_ready")]
    assert ready.data == {
        "channel_id": "SIP:alice-0001",
        "bridge_id": "sipx-bridge-SIP-alice-0001",
        "media_channel_id": "sipx-media-SIP-alice-0001",
        "args": ["inbound", "1234"],
        "playback_id": "play-1",
    }


def test_inbound_stasis_example_returns_none_without_matching_event() -> None:
    asyncio.run(_return_none_without_matching_event())


async def _return_none_without_matching_event() -> None:
    async def source():
        yield {
            "type": "ChannelStateChange",
            "application": "sipx",
            "channel": {"id": "chan-1"},
        }

    session = await handle_inbound_stasis_start(AsteriskBackend(), source=source())

    assert session is None
