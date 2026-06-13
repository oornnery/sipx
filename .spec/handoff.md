# Handoff

## Summary

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

After block `3.0.0`:

1. Run live smoke of the new examples against the public Mizu demo (`python -m sipx.examples.register` etc.).
2. Decide whether `AsyncClient` should gain SDP offer/answer + RTP session orchestration to restore softphone-style call/listen ergonomics.
3. Decide whether the 90% coverage target from the overhaul plan still stands; if so, add tests or exclude `sipx/examples/*` from the gate.
4. Decide license before public distribution and Asterisk/commercial positioning.
5. Start `docker/asterisk` and run opt-in Asterisk integration tests (now AsyncClient invite/ack/bye based).

## Do Not Do Yet

- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.
- Do not add native audio dependencies to root default install.

## Latest Validation

- `uv run pytest tests apps`: 567 pass, 3 opt-in skips.
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass (146 files).
- `uv run ty check`: pass.
- `uv run --package sipx-cli sipx --help`: new AsyncClient-based surface works.
