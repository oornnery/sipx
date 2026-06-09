from __future__ import annotations

from uuid import uuid4


def new_call_id(prefix: str = "call") -> str:
    return f"{prefix}-{uuid4().hex}"


def new_branch(prefix: str = "branch") -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def new_tag(prefix: str = "tag") -> str:
    return f"{prefix}-{uuid4().hex}"
