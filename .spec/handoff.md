# Handoff

## Summary

Block `3.6.0` added P2 RFC: PRACK/100rel (RFC 3262) auto-sent for reliable provisionals via `AsyncClient._maybe_send_prack`, Digest SHA-256/SHA-256-sess (RFC 8760) in `AuthFlow`, and UAC dialog From/To tag matching (RFC §12.2.2; UAS stays Call-ID-only). The full P0/P1/P2 security/RFC hardening roadmap is now complete.

Block `3.5.0` added P1 RFC part 2: RFC 3261 §17 retransmission in `AsyncClient._await_response` (UDP T1/T2 backoff bounded by `timeout`, INVITE stops after first provisional, TCP/TLS never retransmit, `ClientConfig.retransmit` toggle).

Block `3.4.0` added P1 RFC part 1 to `AsyncClient`: rport (RFC 3581) on outgoing UDP Via with `learned_address`, non-2xx INVITE auto-ACK (RFC §17.1.1.3), `cancel(call_id)` (RFC §9), and CSeq-method-scoped response correlation.

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

Security/RFC hardening (P0/P1/P2) is complete. Open items now are product decisions, not protocol work:

1. Decide whether `AsyncClient` should gain SDP/RTP orchestration for softphone-style call/listen ergonomics.
2. Decide license before public distribution.
3. Decide the fate of the untracked `qa_tls_scenarios.py` (move into `apps/`/`tests/`, formalize, or delete).
4. Optional: full removal of the `sip/` sans-I/O toolkit (breaking; no safe migration yet).
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
