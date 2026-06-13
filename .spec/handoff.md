# Handoff

## Summary

Block `3.3.0` added the `apps/fastapi` workspace package (`sipx-fastapi`): a FastAPI REST service with lifespan-managed `AsyncClient`, endpoints for `/health`, `/sip/options`, `/sip/register`, `/sip/unregister`, `/sip/message`, and `/sip/request`, env-based `SIPX_*` config, README, and tests. Root `README.md` now documents the FastAPI app and `sipx/extensions/`. P1 RFC items (§17 timers, auto-ACK for non-2xx INVITE, CANCEL, real Via sent-by + rport) remain deferred and documented in README/TODO.

Block `3.2.0` completed P0 security (strict response correlation, CR/LF sanitization, Content-Length everywhere, TCP reassembly cap) and Phase 2 partial reorg (`sipx/rfc/` → `sipx/extensions/`, protocol type exports). Block `3.0.0` removed the legacy API; `AsyncClient` is the only client runtime.

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
- `AsyncClient` is the only client runtime; no legacy `SipUserAgent`/`SipUac`/`SipUas` surface exists.
- `sipx-cli` owns the curl-like `sipx` console command.
- `sipx-fastapi` demonstrates REST integration with lifespan-managed `AsyncClient`.
- `sipx-harness` remains product center for Harness/Actor/Scenario/Timeline/Verdict/Artifact APIs.
- `sipx/extensions/*` holds standalone extension handlers (test-only, not wired into `AsyncClient`).

## Recommended Next Task

1. Implement P1 RFC items when scope allows: §17 timers/retransmission, auto-ACK for non-2xx INVITE, CANCEL, real Via sent-by + rport.
2. P2: PRACK/100rel in client path, Digest SHA-256, dialog tag matching.
3. Decide whether `AsyncClient` should gain SDP/RTP orchestration for softphone-style call/listen ergonomics.
4. Decide license before public distribution.

## Validation

Run before committing:

```bash
uv sync --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pytest apps
uv run --package sipx-fastapi sipx-fastapi --help  # or uvicorn smoke
```
