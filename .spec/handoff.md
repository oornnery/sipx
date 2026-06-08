# Handoff

## Summary

Project planning environment was initialized from `IDEA.md`. Blocks `0.2.0` through `0.9.0` added initial product code: harness core, mock backend, scenario artifacts, minimal CLI, media primitives, redaction, SIP parser primitives, SDP audio offer/answer, RTP packet stats, RFC4733 DTMF, SIP dialog skeletons, INVITE/non-INVITE client transactions, REGISTER helper/flow, Digest auth helper, UAS INVITE skeleton, BYE helper, real UDP Native SIP transport/backend, strict INVITE/ACK/BYE call flow, CANCEL runtime, REGISTER over-UDP orchestration, transaction retransmission timers, and the first Asterisk ARI control-plane client/event backend. SPEC T21 and T9 are complete.

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

Continue after block `0.9.0`:

1. Implement Asterisk ARI channel/bridge/playback/hangup/DTMF timeline mapping for SPEC T10.
2. Choose first Asterisk media path before SPEC T11.
3. Add richer mock media events and an example scenario.
4. Decide artifact retention policy before real recordings/transcripts.
5. Add lab hooks for controlled malformed behavior.

## Do Not Do Yet

- Do not build full SIP stack before core harness abstractions.
- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.

## Latest Validation

- `python -m pytest`: pass, 65 tests.
- `python -m pytest tests/test_asterisk_backend.py`: pass, 5 no-Asterisk ARI client/event tests during block `0.9.0`.
- `python -m pytest tests/test_native_sip_backend.py`: pass, 9 loopback UDP tests during block `0.8.4`.
- `ruff check .`: pass.
- `ruff format --check .`: pass, 57 files already formatted.
- `python -m ty check`: blocked, active interpreter has no `ty` module.
