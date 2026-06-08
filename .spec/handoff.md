# Handoff

## Summary

Project planning environment was initialized from `IDEA.md`. Blocks `0.2.0` through `0.9.5` added initial product code: harness core, mock backend, scenario artifacts, minimal CLI, media primitives, redaction, SIP parser primitives, SDP audio offer/answer, RTP packet stats, RFC4733 DTMF, SIP dialog skeletons, INVITE/non-INVITE client transactions, REGISTER helper/flow, Digest auth helper, UAS INVITE skeleton, BYE helper, real UDP Native SIP transport/backend, strict INVITE/ACK/BYE call flow, CANCEL runtime, REGISTER over-UDP orchestration, transaction retransmission timers, Asterisk ARI control-plane client/event backend, Asterisk channel/bridge/playback/hangup/DTMF timeline mapping, WebSocket media MVP, inbound `Stasis(sipx)` example, headless native technical softphone, and lab-only native SIP hooks. SPEC T21-T23, T9-T11, and T15 are complete.

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

Continue after block `0.9.5`:

1. Add recorder/export scenario from timeline + user actions for SPEC T24.
2. Add reports with timeline, SIP, RTP, transcript, and verdict for SPEC T25.
3. Add profile config for strict/lab/account/media overrides for SPEC T29.
4. Add richer mock media events and an example scenario.
5. Decide artifact retention policy before real recordings/transcripts.

## Do Not Do Yet

- Do not build full SIP stack before core harness abstractions.
- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.

## Latest Validation

- `python -m pytest`: pass, 85 tests.
- `python -m pytest tests/test_native_sip_backend.py`: pass, 16 loopback UDP tests during block `0.9.5`.
- `python -m pytest tests/test_native_softphone.py`: pass, 5 loopback UDP softphone tests during block `0.9.5`.
- `python -m pytest tests/test_asterisk_stasis_example.py`: pass, 3 no-Asterisk Stasis example tests during block `0.9.3`.
- `python -m pytest tests/test_asterisk_backend.py`: pass, 10 no-Asterisk ARI/media tests during block `0.9.2`.
- `ruff check .`: pass.
- `ruff format --check .`: pass, 63 files already formatted.
- `python -m ty check`: blocked, active interpreter has no `ty` module.
