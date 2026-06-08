import json
from pathlib import Path

from sipx import ArtifactKind, ArtifactStore, Redactor


def test_redactor_redacts_secret_mapping_values() -> None:
    redacted = Redactor().redact(
        {
            "Authorization": "Bearer token",
            "nested": {"password": "secret"},
            "safe": "visible",
        }
    )

    assert redacted == {
        "Authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
        "safe": "visible",
    }


def test_redactor_redacts_sensitive_text_lines() -> None:
    redacted = Redactor().redact_text(
        "INVITE sip:1000@example.com\nAuthorization: Bearer secret\na=crypto:1 key\n"
    )

    assert "Bearer secret" not in redacted
    assert "a=crypto:1 key" not in redacted
    assert "Authorization: [REDACTED]" in redacted


def test_artifact_store_redacts_json_before_write(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    artifact = store.write_json(
        "verdict.json",
        {"token": "secret", "safe": "visible"},
        kind=ArtifactKind.VERDICT,
    )

    data = json.loads(artifact.path.read_text())
    assert data == {"safe": "visible", "token": "[REDACTED]"}
