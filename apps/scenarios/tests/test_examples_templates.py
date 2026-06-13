import re
import runpy
from pathlib import Path


EXAMPLE_ROOTS = (
    Path("apps/llm/examples"),
    Path("apps/scenarios/examples"),
    Path("apps/asterisk/examples"),
)


def _example_files() -> list[Path]:
    return [path for root in EXAMPLE_ROOTS for path in root.rglob("*.py")]


def _example_paths() -> list[Path]:
    return [
        path
        for root in EXAMPLE_ROOTS
        for path in root.rglob("*")
        if path.suffix in {".py", ".md", ".toml"}
    ]


def test_examples_import_without_required_secrets() -> None:
    for path in _example_files():
        namespace = runpy.run_path(str(path))
        assert namespace


def test_examples_do_not_contain_inline_private_credentials() -> None:
    for path in _example_paths():
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"api_key\s*=\s*['\"][^'\"]+", text)
            assert not re.search(
                r"Authorization\s*[:=]\s*['\"]?(?!\[REDACTED\])[^'\"\s]+",
                text,
            )
            assert not re.search(r"password\s*=\s*['\"][^'\"]+", text)


def test_llm_examples_use_generic_environment_key_only() -> None:
    for path in _example_files():
        text = path.read_text(encoding="utf-8")
        if "LLMChatClient" in text or "SIPX_LLM" in text:
            assert "SIPX_LLM_API_KEY" in text
            assert not re.search(r"SIPX_LLM_API_KEY\s*=\s*[A-Za-z0-9_-]{10,}", text)


def test_runnable_examples_expose_main() -> None:
    for path in (
        "apps/llm/examples/semantic_smoke.py",
        "apps/llm/examples/sip_flow_audit.py",
        "apps/scenarios/examples/sip/sip_cli_flow.py",
    ):
        namespace = runpy.run_path(path)
        assert callable(namespace["main"])


def test_sip_flow_audit_parses_fenced_json() -> None:
    namespace = runpy.run_path("apps/llm/examples/sip_flow_audit.py")
    parsed = namespace["_parse_json_object"](
        '```json\n{"summary":"ok","risk_score":10}\n```'
    )

    assert parsed == {"summary": "ok", "risk_score": 10}


def test_sip_flow_audit_deterministic_sample_is_clean() -> None:
    namespace = runpy.run_path("apps/llm/examples/sip_flow_audit.py")
    result = namespace["_deterministic_audit"](namespace["SAMPLE_TRACE"])

    assert result["critical_findings"] == []
    assert result["signals"]["invite_has_sdp_offer"]
    assert result["signals"]["dtmf_info"]


def test_sip_flow_audit_flags_only_unredacted_auth() -> None:
    namespace = runpy.run_path("apps/llm/examples/sip_flow_audit.py")

    redacted = namespace["_deterministic_audit"]("Authorization: [REDACTED]")
    unredacted = namespace["_deterministic_audit"]('Authorization: Digest nonce="n1"')

    assert redacted["critical_findings"] == []
    assert unredacted["critical_findings"] == [
        "trace contains an unredacted authorization header"
    ]
