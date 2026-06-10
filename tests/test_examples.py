import asyncio
import json
import runpy
from pathlib import Path

from sipx import SipCall, SipCallError


ROOT_EXAMPLES = (
    Path("sipx/examples/register.py"),
    Path("sipx/examples/options.py"),
    Path("sipx/examples/invite_without_sdp.py"),
    Path("sipx/examples/invite_with_sdp.py"),
    Path("sipx/examples/metrics.py"),
    Path("sipx/examples/manipulation.py"),
    Path("sipx/examples/smoke_tests.py"),
    Path("sipx/examples/handlers.py"),
)


def test_v64_root_examples_expose_main_without_argparse() -> None:
    for path in ROOT_EXAMPLES:
        namespace = runpy.run_path(str(path))
        assert callable(namespace["main"])
        assert "argparse" not in path.read_text(encoding="utf-8")


def test_v64_root_examples_stay_sip_only() -> None:
    for path in ROOT_EXAMPLES + (Path("sipx/examples/common.py"),):
        text = path.read_text(encoding="utf-8")
        assert "sipx_harness" not in text
        assert "apps." not in text
        assert "SIPX_MIZU_" not in text
        assert "SIPX_PASSWORD" in text or path.name != "common.py"


def test_v65_invite_without_sdp_reports_sip_call_failures(monkeypatch, capsys) -> None:
    from sipx.examples import invite_without_sdp as example

    class FakeUserAgent:
        local_address = ("127.0.0.1", 5060)

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def initiate_call(self, **kwargs: object) -> None:
            raise SipCallError("INVITE failed with 502 Bad Gateway")

        async def hangup_call(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("failed INVITE must not send BYE")

    monkeypatch.setattr(example, "SipUserAgent", FakeUserAgent)
    monkeypatch.setenv("SIPX_TARGET", "sip:callee@example.com")

    asyncio.run(example.invite_without_sdp())

    assert json.loads(capsys.readouterr().out) == {
        "state": "failed",
        "error": {
            "type": "SipCallError",
            "message": "INVITE failed with 502 Bad Gateway",
        },
    }


def test_v65_call_examples_require_explicit_target(monkeypatch, capsys) -> None:
    from sipx.examples import invite_with_sdp as example

    monkeypatch.delenv("SIPX_TARGET", raising=False)

    class FakeUac:
        local_address = ("127.0.0.1", 5060)

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def call(self, *args: object, **kwargs: object) -> SipCall:
            raise SipCallError("INVITE failed with 503 Service Unavailable")

        async def hangup(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("failed INVITE must not send BYE")

    monkeypatch.setattr(example, "SipUac", FakeUac)

    asyncio.run(example.invite_with_sdp())

    output = json.loads(capsys.readouterr().out)
    assert output["state"] == "failed"
    assert output["error"]["type"] == "SipCallError"


def test_v65_call_examples_bound_call_wait_by_timeout(monkeypatch, capsys) -> None:
    from sipx.examples import invite_with_sdp as example

    monkeypatch.setenv("SIPX_TARGET", "sip:callee@example.com")
    monkeypatch.setenv("SIPX_TIMEOUT", "0.01")

    class SlowUac:
        local_address = ("127.0.0.1", 5060)

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def call(self, *args: object, **kwargs: object) -> SipCall:
            await asyncio.sleep(60)
            raise AssertionError("unreachable")

    monkeypatch.setattr(example, "SipUac", SlowUac)

    asyncio.run(example.invite_with_sdp())

    output = json.loads(capsys.readouterr().out)
    assert output["state"] == "failed"
    assert "TimeoutError" in output["error"]["type"]
