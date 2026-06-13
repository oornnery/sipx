"""SIP wire-format helpers: value sanitization and header parsing.

Used by ``Request`` serialization and ``AsyncClient`` response correlation
to reject header/URI injection and match replies to the correct transaction.

References:
    RFC 3261 §7.3 - Header field format (no CR/LF in values)
    RFC 3261 §17.1.3 - Matching responses to client transactions (Via branch)
"""

from __future__ import annotations

from sipx.exceptions import ProtocolError


def sanitize_sip_token(value: str, *, field: str = "value") -> str:
    """Reject CR/LF in SIP header values, URIs, and method names."""
    if "\r" in value or "\n" in value:
        raise ProtocolError(
            f"CR/LF not allowed in SIP {field}",
            rfc_ref="RFC 3261 §7.3",
        )
    return value


def extract_branch_from_via(via: str) -> str | None:
    """Return the ``branch`` parameter from a Via header value."""
    for param in via.split(";")[1:]:
        name, _, val = param.strip().partition("=")
        if name.lower() == "branch":
            return val.strip()
    return None


def extract_top_via_branch(headers: dict[str, str | list[str]]) -> str | None:
    """Return the branch from the topmost Via header in *headers*."""
    via = headers.get("Via")
    if via is None:
        return None
    if isinstance(via, list):
        via = via[0] if via else ""
    if not isinstance(via, str) or not via:
        return None
    return extract_branch_from_via(via)


def extract_cseq_parts(cseq: str) -> tuple[str, str] | None:
    """Split ``CSeq`` into ``(sequence_number, method)``."""
    number, sep, method = cseq.partition(" ")
    if not sep or not method:
        return None
    return number.strip(), method.strip()
