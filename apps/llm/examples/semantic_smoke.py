from __future__ import annotations

import asyncio
import os

from sipx_harness import Harness, Verdict, scenario
from sipx_llm import LLMChatClient


@scenario("llm_semantic_smoke", provider="openai-compatible")
async def scenario(h: Harness) -> Verdict:
    if not os.getenv("SIPX_LLM_API_KEY"):
        h.timeline.record(
            "llm",
            "skipped",
            data={
                "provider": _provider_name(),
                "reason": "SIPX_LLM_API_KEY not set",
            },
        )
        return Verdict.skipped(reason="SIPX_LLM_API_KEY not set")

    client = LLMChatClient.from_env()
    answer = await client.complete(
        "Classify this SIP result as accepted or rejected: 603 Declined.",
        system="Return one lowercase word.",
        max_tokens=8,
    )
    h.timeline.record(
        "llm",
        "classified",
        data={"provider": _provider_name(), "result": answer.strip().lower()},
    )
    return Verdict.passed(reason="LLM semantic classification completed")


def _provider_name() -> str:
    return os.getenv("SIPX_LLM_PROVIDER", "openai-compatible")


def main() -> int:
    verdict = asyncio.run(Harness().run(scenario))
    reason = f": {verdict.reason}" if verdict.reason else ""
    print(f"{verdict.status}{reason}")
    return 0 if verdict.status in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
