import asyncio
import os

import pytest

from sipx import (
    NativeSipBackend,
    NativeSipCallState,
    NativeSipRetransmissionPolicy,
    SipUri,
)
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


def test_native_sip_backend_calls_asterisk_as_uas() -> None:
    asyncio.run(_native_sip_backend_calls_asterisk_as_uas())


async def _native_sip_backend_calls_asterisk_as_uas() -> None:
    host = os.getenv("SIPX_ASTERISK_SIP_HOST", "127.0.0.1")
    port = int(os.getenv("SIPX_ASTERISK_SIP_PORT", "5060"))
    caller = NativeSipBackend(
        retransmission_policy=NativeSipRetransmissionPolicy(
            initial_interval=0.1,
            max_interval=0.2,
            max_attempts=3,
        )
    )
    try:
        await caller.start()
        contact = SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}")

        call = await caller.initiate_call(
            remote=(host, port),
            target=SipUri.parse(f"sip:1001@{host}:{port}"),
            caller=SipUri.parse("sip:alice@sipx.local"),
            contact=contact,
            call_id="sipx-asterisk-native-1",
            branch="z9hG4bK-sipx-asterisk-native",
            from_tag="sipx-native",
            ack_branch="z9hG4bK-sipx-asterisk-ack",
            timeout=3.0,
        )
        response = await caller.hangup_call(
            call,
            branch="z9hG4bK-sipx-asterisk-bye",
            timeout=3.0,
        )

        assert call.state is NativeSipCallState.TERMINATED
        assert 200 <= response.status_code < 300
    finally:
        await caller.stop()
