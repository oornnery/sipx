"""Shared utilities for SIP transports."""

from __future__ import annotations

from typing import Optional


def parse_content_length(headers: bytes) -> Optional[int]:
    """
    Parse Content-Length from SIP headers.

    Supports both full form (Content-Length:) and compact form (l:).

    Args:
        headers: Raw header bytes

    Returns:
        Content-Length value or None if not found
    """
    for line in headers.split(b"\r\n"):
        lower = line.lower()
        if lower.startswith(b"content-length:") or lower.startswith(b"l:"):
            try:
                value = line.split(b":", 1)[1].strip()
                return int(value)
            except (IndexError, ValueError):
                pass
    return None
