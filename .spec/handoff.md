# Handoff

## Summary

Block `1.21.0` added abstract `Transport` base class in `sipx.transport.base` with async `send`, `receive`, `close`, and properties `local_address`/`transport_type`; `TransportConfig` dataclass with common config defaults; mock transport tests in `tests/test_transport_base.py`. All 96 core tests (90 existing + 6 new), ruff lint/format, and type check pass.

## Read First

1. `AGENTS.md`
2. `FORMAT.md`
3. `SPEC.md`
4. `DESIGN.md`
5. `TODO.md`
6. `.spec/state.md`
7. `.spec/checks.md`
8. `.spec/handoff.md`
9. `.mem/hot.md`
10. `.mem/decisions.md`
11. `.mem/open-loops.md`

## Current Direction

- Root `sipx` stays SIP protocol/runtime/RTP media core plus direct SIP-only examples.
- `SipUac` and `SipUas` own high-level outbound/inbound SIP phone ergonomics.
- RTP wire events expose tx/rx `RtpWireEvent` for all audio modes; `debug_wire_rtp()` available in `sipx.examples.common`.
- `sipx-cli` owns the `sipx` console command, which stays SIP/RTP-only and curl/httpx-like.
- `sipx-harness` remains product center for Harness/Actor/Scenario/Timeline/Verdict/Artifact APIs.
- `AsteriskRuntime` remains the first Asterisk implementation path.
- Maintained English files in current structure are source of truth; `IDEA.md` is historical only; no separate `/docs` tree.

## Recommended Next Task

After block `1.19.0`:

1. Decide license before public distribution and Asterisk/commercial positioning.
2. Start `docker/asterisk` and run opt-in Asterisk integration tests.
3. Add live SIP inspector events.
4. Add recordings/transcripts, retention policy, and richer media artifacts.
5. Add RFC4733 RTP DTMF send and advanced RTP/media runtime behavior.
6. Decide whether OpenAI-compatible LLM support is enough for now or introduce a provider protocol before vendor-specific adapters.

## Do Not Do Yet

- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.
- Do not add native audio dependencies to root default install.

## Latest Validation

- `ruff check .`: pass.
- `ruff format --check .`: pass.
- `uv run ty check`: pass.
- `git diff --check`: pass/no output.
- `pytest`: 90 pass.
