# Handoff

## Summary

Latest blocks `3.1.2`-`3.1.4` (core review Phase 1, docs only): added RFC-referencing module docstrings to every module that lacked one and fixed the misleading `protocol/__init__.py`/`rfc/__init__.py` docstrings; added six runnable `AsyncClient` examples (`options`, `unregister`, `call`, `info_dtmf`, `server`, `hooks_history`) covered by `tests/test_examples.py`; refreshed `README.md` to drop false claims, document `response.history`, and add an honest "AsyncClient status and RFC limitations" section. `.omo` was untracked. Phase 2 (unify duplicated `sip/`+`protocol/` stacks, remove `rfc/` orphan) and Phase 3 (security/RFC hardening: response correlation by branch+source, CRLF sanitization, `Content-Length`, §17 timers/retransmission, CANCEL, PRACK, Digest SHA-256) are written up as awaiting-OK open loops O16/O17 — do not start them without user direction. Stray untracked `qa_tls_scenarios.py` is left for the user to decide. Validation: 503 core tests, ruff lint/format, `uv run ty check` all pass.

Block `3.0.0` removed the legacy API entirely per explicit user direction ("nao precisa de nada legacy"). `sipx/legacy.py`, all legacy root exports, `SipCallSummary`/`call_summary`, `docs/old-api-snapshot/`, `tests/test_uac_uas.py`, legacy root examples, and `apps/scenarios/examples/mizu/` are gone. `AsyncClient` is the only client runtime and gained `request()` (generic method), in-dialog `ack()`/`bye()` from tracked `Dialog` state, and a `dialog()` accessor. The `sipx` CLI was rewritten on `AsyncClient` with commands `options`, `message`, `request`, `register`, `unregister`; the legacy `call`/`listen` RTP softphone commands were removed because `AsyncClient` has no media/RTP orchestration. RTP/media primitives (`sipx.rtp`, `sipx.media`, `sipx.sdp`) and the sans-I/O `sipx.sip` layer remain. Validation: 567 tests pass (core + apps, 3 opt-in skips), ruff lint/format clean, `uv run ty check` clean.

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
- RTP/media primitives stay exported from root but are not orchestrated by `AsyncClient` yet.
- `sipx-cli` owns the `sipx` console command, which is AsyncClient-based and curl/httpx-like.
- `sipx-harness` remains product center for Harness/Actor/Scenario/Timeline/Verdict/Artifact APIs.
- `AsteriskRuntime` remains the first Asterisk implementation path.
- Maintained English files in current structure are source of truth; `IDEA.md` is historical only; no separate `/docs` tree.

## Recommended Next Task

After blocks `3.1.2`-`3.1.4`:

1. Get user OK on core-review Phase 2 (reorg) and Phase 3 P0 security fixes (open loops O16/O17) before touching protocol code; both are breaking/sensitive.
2. Run live smoke of the new examples against the public Mizu demo (`python -m sipx.examples.options`, `.call`, `.info_dtmf`, etc.).
3. Decide whether `AsyncClient` should gain SDP offer/answer + RTP session orchestration to restore softphone-style call/listen ergonomics.
4. Decide license before public distribution and Asterisk/commercial positioning.
5. Start `docker/asterisk` and run opt-in Asterisk integration tests (now AsyncClient invite/ack/bye based).

## Do Not Do Yet

- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.
- Do not add native audio dependencies to root default install.

## Latest Validation

- `uv run pytest -q`: 503 core pass (blocks 3.1.2-3.1.4).
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass (152 files).
- `uv run ty check`: pass.
