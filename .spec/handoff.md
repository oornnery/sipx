# Handoff

## Summary

Project planning environment was initialized from `IDEA.md`. Blocks `0.2.0` through `0.7.3` added initial product code: harness core, mock backend, scenario artifacts, minimal CLI, media primitives, redaction, SIP parser primitives, SDP audio offer/answer, RTP packet stats, RFC4733 DTMF, SIP dialog skeletons, INVITE/non-INVITE client transactions, REGISTER helper/flow, Digest auth helper, UAS INVITE skeleton, and BYE helper.

## Read First

1. `AGENTS.md`
2. `SPEC.md`
3. `DESIGN.md`
4. `TODO.md`
5. `.spec/state.md`
6. `.spec/checks.md`
7. `.spec/handoff.md`
8. `.mem/hot.md`
9. `.mem/decisions.md`
10. `.mem/open-loops.md`

## Current Direction

Build `sipx` as a Python Voice/SIP Harness:

- Harness core is product center.
- AsteriskBackend is first implementation path.
- NativeSipBackend is required for technical softphone and raw SIP/RTP validation.
- Scenario, expect, timeline, verdict, and artifacts come before full telephony feature breadth.
- Package/import name and CLI command are both `sipx`.
- Technical softphone should be built on `NativeSipBackend`, not Asterisk.
- Technical softphone should be headless first and support profiles, lab hooks, scenario recording, and replay.
- Mixed scenarios should support native actors and Asterisk actors in one timeline.
- PJSIP/PJSUA2 is optional future backend, not the native protocol-lab foundation.
- Maintained English files in the current structure are the implementation source of truth; `IDEA.md` is historical only; no separate `/docs` tree is used.
- Work should proceed in small commit blocks. Every block bumps version, updates `CHANGELOG.md`, `TODO.md`, `.spec/*`, and `.mem/*`, validates, then commits with explicit staged paths.

## Recommended Next Task

Continue after block `0.7.3`:

1. Add native SIP sockets/timers runtime shell.
2. Add strict UAC/UAS call runtime integration around existing sans-I/O primitives.
3. Add richer mock media events and an example scenario.
4. Choose first Asterisk media path.

## Do Not Do Yet

- Do not build full SIP stack before core harness abstractions.
- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.

## Latest Validation

- `python -m pytest`: pass, 51 tests.
- `python -m pytest tests/test_sip_auth_requests.py`: pass, 8 tests during block `0.7.3`.
- `ruff check .`: pass.
- `ruff format --check .`: pass, 53 files already formatted.
- `python -m ty check`: blocked, active interpreter has no `ty` module.
