import asyncio
import os

import pytest

from sipx import AsyncClient, ClientConfig
from sipx_asterisk import AsteriskAriClient, AsteriskAriConfig


pytestmark = pytest.mark.skipif(
    os.getenv("SIPX_ASTERISK_INTEGRATION") != "1",
    reason="set SIPX_ASTERISK_INTEGRATION=1 and start docker/asterisk lab",
)


def _ari_config() -> AsteriskAriConfig:
    return AsteriskAriConfig(
        base_url=os.getenv("SIPX_ASTERISK_ARI_URL", "http://127.0.0.1:8088"),
        username=os.getenv("SIPX_ASTERISK_ARI_USER", "sipx"),
        password=os.getenv("SIPX_ASTERISK_ARI_PASSWORD", "sipx"),
        app=os.getenv("SIPX_ASTERISK_ARI_APP", "sipx"),
        timeout=2.0,
    )


def test_asterisk_lab_ari_is_reachable() -> None:
    asyncio.run(_asterisk_lab_ari_is_reachable())


async def _asterisk_lab_ari_is_reachable() -> None:
    client = AsteriskAriClient(_ari_config())

    info = await client.get("asterisk/info")

    assert isinstance(info, dict)
    assert "system" in info or "config" in info


def test_async_client_calls_asterisk_as_uas() -> None:
    asyncio.run(_async_client_calls_asterisk_as_uas())


async def _async_client_calls_asterisk_as_uas() -> None:
    host = os.getenv("SIPX_ASTERISK_SIP_HOST", "127.0.0.1")
    port = int(os.getenv("SIPX_ASTERISK_SIP_PORT", "5060"))
    config = ClientConfig(
        local_host="127.0.0.1",
        timeout=3.0,
        from_uri="sip:alice@sipx.local",
    )
    async with AsyncClient(config=config) as client:
        response = await client.invite(f"sip:1001@{host}:{port}")
        assert 200 <= response.status_code < 300

        call_id = response.headers.get("Call-ID")
        assert isinstance(call_id, str) and call_id

        await client.ack(call_id)
        bye_response = await client.bye(call_id)

        assert 200 <= bye_response.status_code < 300
        assert client.dialog(call_id) is None
