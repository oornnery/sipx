"""Generators for SIP Call-ID, Via branch, and tag identifiers.

Produces globally-unique Call-IDs, RFC 3261 transaction branch IDs prefixed
with the mandatory ``z9hG4bK`` magic cookie, and From/To tags.

References:
    RFC 3261 §8.1.1.4 - Call-ID
    RFC 3261 §8.1.1.7 - Via (branch parameter, z9hG4bK magic cookie)
    RFC 3261 §19.3 - Tags
"""

from __future__ import annotations

from uuid import uuid4


def new_call_id(prefix: str = "call") -> str:
    return f"{prefix}-{uuid4().hex}"


def new_branch(prefix: str = "branch") -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def new_tag(prefix: str = "tag") -> str:
    return f"{prefix}-{uuid4().hex}"
