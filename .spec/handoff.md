# Handoff

## Summary

Project planning environment was initialized from `IDEA.md`. Blocks `0.2.0` through `1.6.1` added initial product code: harness core, mock backend, scenario artifacts, CLI run/export/replay/profile/phone/raw-SIP commands, reports, profiles, mixed actor binding, media primitives, redaction, SIP parser primitives, SDP audio offer/answer, RTP packet stats, RFC4733 DTMF, SIP dialog skeletons, INVITE/non-INVITE client transactions, REGISTER helper/flow, Digest auth helper, UAS INVITE skeleton, BYE helper, real UDP Native SIP transport/backend, strict INVITE/ACK/BYE call flow, CANCEL runtime, REGISTER over-UDP orchestration, INVITE Digest retry, transaction retransmission timers, parser fuzz tests, Asterisk ARI control-plane client/event backend, Asterisk channel/bridge/playback/hangup/DTMF timeline mapping, WebSocket media MVP, inbound `Stasis(sipx)` example, Docker Asterisk lab, headless native technical softphone, lab-only native SIP hooks, package-manager console script execution, GitHub CI/release workflows, fail-fast phone CLI config validation, curl-like SIP request commands, redacted packet debug output, native softphone SDP negotiation, simple `LLMChatClient` templates/tests, fixed LLM env defaults, in-dialog SIP INFO DTMF, runnable native examples, and passing `uv run ty check` type validation. SPEC T1-T43 plus V24-V35/B4-B10 are complete.

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
- GitHub workflows now target the current project: Python 3.14, `pyproject.toml` version, uv, ruff, pytest, package build, Docker Asterisk integration, and PyPI trusted publishing.

## Recommended Next Task

Continue after block `1.5.0`:

1. Decide license before public distribution and Asterisk/commercial positioning.
2. Start `docker/asterisk` and run opt-in Asterisk integration tests.
3. Add recordings/transcripts, retention policy, and richer media artifacts.
4. Add RTP media send/receive, RFC4733 DTMF over RTP, then live SIP inspector and advanced RTP/media runtime behavior.
5. Decide whether OpenAI-compatible LLM support is enough for now or introduce a provider protocol before vendor-specific adapters.

## Do Not Do Yet

- Do not build full SIP stack before core harness abstractions.
- Do not couple public API to Asterisk.
- Do not write real Asterisk secrets/config with credentials.
- Do not use AI semantic assertions as the only pass/fail check.

## Latest Validation

- `uv run sipx --help`: pass; commands include `options`, `message`, `request`, `profile`, `phone`, `register`, `unregister`, `call`, and `listen`.
- `uv run sipx request --help`: pass; help includes `--username`, `--password`, and `--debug-sip` flags.
- `uv run sipx call --help`: pass; help includes `--debug-sip`, media host/port, and codec flags.
- `python -m pytest`: pass, 124 passed, 3 skipped after `1.6.0` LLM/template, runnable example, and SIP INFO DTMF changes.
- Focused LLM/template tests: pass; fake OpenAI-compatible transport tests pass, live LLM smoke skipped when `SIPX_LLM_API_KEY` is absent, and templates import without secrets.
- Focused SDP tests: pass; outbound softphone call negotiates SDP and missing SDP answer is rejected.
- Focused debug tests: pass; phone and raw SIP `--debug-sip` output includes packet markers and redacts authorization headers.
- Focused Digest tests: pass; INVITE and raw request Digest retry regressions are covered, including stale pre-auth challenge retransmissions ignored by CSeq.
- Real proxy call: Digest challenge retried; proxy returned `603 Declined` instead of previous `401 Unauthorized`; no real secret/account/proxy values are persisted in repo files.
- `python -m pytest tests/test_recorder_reports_profiles.py tests/test_protocol_fuzz.py tests/test_cli.py tests/test_harness_scenario.py tests/test_asterisk_integration.py`: pass, 17 passed, 2 skipped.
- `python -m pytest tests/test_native_sip_backend.py`: pass, 16 loopback UDP tests during block `0.9.5`.
- `python -m pytest tests/test_native_softphone.py`: pass, 5 loopback UDP softphone tests during block `0.9.5`.
- `python -m pytest tests/test_asterisk_stasis_example.py`: pass, 3 no-Asterisk Stasis example tests during block `0.9.3`.
- `python -m pytest tests/test_asterisk_backend.py`: pass, 10 no-Asterisk ARI/media tests during block `0.9.2`.
- `ruff check .`: pass.
- `ruff format --check .`: pass, 79 files already formatted.
- `uv build --out-dir /tmp/opencode/sipx-build-1.6.0-final`: pass, built sdist and wheel outside the repo.
- `python -m ty check`: blocked, active interpreter has no `ty` module.
- `uv run ty check`: pass after type-hardening fixes.
- Runnable examples: pass for direct LLM semantic smoke, native CLI flow printer, call-with-DTMF help, Mizu register help, and `sipx call --help`.
- `docker compose -f docker/asterisk/docker-compose.yml config`: blocked, Docker unavailable in WSL environment.
