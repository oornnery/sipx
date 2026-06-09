from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


REDACTED = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class Redactor:
    secret_keys: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "api_key",
                "ari_password",
                "ari_token",
                "authorization",
                "password",
                "proxy_authorization",
                "secret",
                "sdp_crypto",
                "token",
            }
        )
    )
    text_patterns: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: (
            re.compile(r"(?im)^(\s*(?:Authorization|Proxy-Authorization)):\s*.+$"),
            re.compile(r"(?im)^(\s*(?:ARI-Password|Password|Token)):\s*.+$"),
            re.compile(r"(?im)^(\s*a=crypto):.*$"),
        )
    )

    def redact(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: REDACTED if self._is_secret_key(str(key)) else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, Sequence) and not isinstance(
            value, bytes | bytearray | str
        ):
            return [self.redact(item) for item in value]
        return value

    def redact_text(self, value: str) -> str:
        redacted = value
        for pattern in self.text_patterns:
            redacted = pattern.sub(self._redact_text_match, redacted)
        return redacted

    def _redact_text_match(self, match: re.Match[str]) -> str:
        if match.lastindex:
            return f"{match.group(1)}: {REDACTED}"
        return REDACTED

    def _is_secret_key(self, key: str) -> bool:
        normalized = key.strip().lower().replace("-", "_")
        return normalized in self.secret_keys or any(
            token in normalized for token in ("password", "secret", "token")
        )


default_redactor = Redactor()
