import re
import runpy
from pathlib import Path


def test_examples_import_without_required_secrets() -> None:
    for path in Path("examples").rglob("*.py"):
        namespace = runpy.run_path(str(path))
        assert namespace


def test_examples_do_not_contain_inline_private_credentials() -> None:
    for path in Path("examples").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"api_key\s*=\s*['\"][^'\"]+", text)
            assert not re.search(r"Authorization\s*[:=]\s*['\"]?[^'\"\s]+", text)
            if path.name != "mizu_call.py" and path.name != "harness.toml":
                assert not re.search(r"password\s*=\s*['\"][^'\"]+", text)


def test_llm_examples_use_generic_environment_key_only() -> None:
    for path in Path("examples").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "LLMChatClient" in text or "SIPX_LLM" in text:
            assert "SIPX_LLM_API_KEY" in text
            assert not re.search(r"SIPX_LLM_API_KEY\s*=\s*[A-Za-z0-9_-]{10,}", text)


def test_runnable_examples_expose_main() -> None:
    for path in (
        "examples/llm/semantic_smoke.py",
        "examples/native/call_with_dtmf.py",
        "examples/native/mizu_call.py",
        "examples/native/sip_cli_flow.py",
    ):
        namespace = runpy.run_path(path)
        assert callable(namespace["main"])
