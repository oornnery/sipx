"""Convert sipx Response objects into JSON-safe payloads."""

from __future__ import annotations

from typing import Any

from sipx.models import Response


def response_payload(response: Response) -> dict[str, Any]:
    """Serialize a SIP response for REST output."""
    headers = {
        key: value if isinstance(value, str) else list(value)
        for key, value in response.headers.items()
    }
    body = None
    if response.body is not None:
        body = response.body.decode("utf-8", errors="replace")
    history = [
        {
            "status_code": item.status_code,
            "reason": item.reason,
            "headers": {
                key: value if isinstance(value, str) else list(value)
                for key, value in item.headers.items()
            },
        }
        for item in response.history
    ]
    return {
        "status_code": response.status_code,
        "reason": response.reason,
        "headers": headers,
        "body": body,
        "history": history,
    }
