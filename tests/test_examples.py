import runpy
from pathlib import Path


ROOT_EXAMPLES = (
    Path("sipx/examples/register.py"),
    Path("sipx/examples/invite.py"),
    Path("sipx/examples/message.py"),
    Path("sipx/examples/subscribe.py"),
    Path("sipx/examples/options.py"),
    Path("sipx/examples/call.py"),
    Path("sipx/examples/info_dtmf.py"),
    Path("sipx/examples/unregister.py"),
    Path("sipx/examples/server.py"),
    Path("sipx/examples/hooks_history.py"),
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


def test_root_examples_use_async_client_only() -> None:
    for path in ROOT_EXAMPLES:
        text = path.read_text(encoding="utf-8")
        assert "AsyncClient" in text
        assert "SipUserAgent" not in text
        assert "SipUac" not in text
        assert "SipUas" not in text
