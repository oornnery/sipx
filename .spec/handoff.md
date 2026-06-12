# Handoff

## Summary

Block `2.0.0` finished and validated the AsyncClient overhaul (`.omo/plans/sipx-overhaul.md`). Root `sipx` now ships an httpx-like `AsyncClient` over `sipx/protocol/*`, `sipx/transport/*` (UDP+rport, TCP, TLS, registry), and `sipx/rfc/*` (PRACK, DNS, events, presence, MESSAGE, outbound). The old `SipUserAgent`/`SipUac`/`SipUas` API lives in `sipx/legacy.py` and is still exported from root; `sipx/ua.py`, `sipx/uac.py`, `sipx/uas.py` were deleted. `docs/migration.md` documents the migration. This block also closed the validation debt the overhaul left behind: missing root exports (`Request`/`Response`/`ClientConfig`), examples using a nonexistent `wire` hook and argparse (V64 violation), 6 stale CLI tests, 19 type errors, 26 unformatted files, missing `cryptography` test dep, and an uncommitted `[tool.ruff] preview = true` experiment that broke lint. Open: coverage is 82% vs the plan's 90% target (87% excluding `sipx/examples/*`).

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

After block `2.0.0`:

1. Decide whether the 90% coverage target from the overhaul plan still stands; if so, add tests for `sipx/legacy.py` (77%) or exclude `sipx/examples/*` from the gate.
2. Migrate `apps/cli` and `apps/scenarios` from `sipx.legacy` to `AsyncClient`, or explicitly decide legacy stays the runtime for CLI phone/call ergonomics (AsyncClient has no media/RTP path yet).
3. Run live smoke of the new examples against the public Mizu demo (`python -m sipx.examples.register` etc.).
4. Decide license before public distribution and Asterisk/commercial positioning.
5. Start `docker/asterisk` and run opt-in Asterisk integration tests.

## Do Not Do Yet

- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.
- Do not add native audio dependencies to root default install.

## Latest Validation

- `uv run pytest`: 525 pass.
- `uv run pytest apps`: 65 pass, 3 skip.
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass (168 files).
- `uv run ty check`: pass.
- `uv run pytest --cov=sipx --cov-fail-under=90`: fail at 82% (plan target not reached; 87% excluding examples).
