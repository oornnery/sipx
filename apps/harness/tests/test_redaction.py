from sipx_harness import Redactor


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
    assert "a=crypto: [REDACTED]" in redacted
