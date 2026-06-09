from __future__ import annotations

import os

from sipx import AsteriskBackend, LLMChatClient, Timeline
from sipx.examples.asterisk_stasis import handle_inbound_stasis_start


async def run_asterisk_llm_template(backend: AsteriskBackend) -> str | None:
    """Answer one inbound Stasis call and ask an OpenAI-compatible LLM for a label."""
    session = await handle_inbound_stasis_start(backend)
    if session is None:
        return None

    if not os.getenv("SIPX_LLM_API_KEY"):
        if isinstance(backend.timeline, Timeline):
            backend.timeline.record(
                "llm",
                "skipped",
                data={
                    "provider": _provider_name(),
                    "reason": "SIPX_LLM_API_KEY not set",
                },
            )
        return None

    client = LLMChatClient.from_env()
    label = await client.complete(
        f"Return a short routing label for inbound args: {','.join(session.args)}",
        system="Return only one lowercase routing label.",
        max_tokens=12,
    )
    if isinstance(backend.timeline, Timeline):
        backend.timeline.record(
            "llm",
            "routing_label",
            data={"provider": _provider_name(), "label": label.strip().lower()},
        )
    return label.strip().lower()


def _provider_name() -> str:
    return os.getenv("SIPX_LLM_PROVIDER", "openai-compatible")
