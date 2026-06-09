# Handoff

## Summary

Block `1.11.0` is complete at `SPEC.md` T69. Root `sipx` is SIP/SDP/RTP/media primitives plus `SipUserAgent`/`SipUac`/`SipUas` and direct SIP-only examples; Harness/Mock/Timeline/Scenario/redaction live in `apps/harness` as `sipx_harness`. The `sipx` console command in `apps/cli` stays SIP/RTP-only with top-level `options`, `message`, `request`, `register`, `unregister`, `call`, and `listen`. UAS answer behavior uses `SipProvisionalResponse`. Optional PyAudio input remains lazy. Direct examples live under `sipx.examples`, use generic SIP env vars, default REGISTER/OPTIONS to public Mizu demo values, require explicit `SIPX_TARGET` for calls, bound call waits by `SIPX_TIMEOUT`, have no `argparse`, and report config/call/timeout errors as structured JSON. New 1.11 surfaces: `SipHooks`, `SipHandlers`, `SipCapabilities`, dataclass summaries, compact headers, and CLI `--print-message`.

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
- `sipx-cli` owns the `sipx` console command, which stays SIP/RTP-only and curl/httpx-like.
- `sipx-harness` remains product center for Harness/Actor/Scenario/Timeline/Verdict/Artifact APIs.
- `AsteriskRuntime` remains the first Asterisk implementation path.
- Maintained English files in current structure are source of truth; `IDEA.md` is historical only; no separate `/docs` tree.

## Recommended Next Task

After block `1.11.0`:

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
- `ruff format --check .`: pass, 114 files already formatted after targeted formatting of three files.
- `uv run ty check`: pass.
- `git diff --check`: pass/no output.
- CLI dry-run rendering: `sipx request ... --print-message --compact-headers` and `sipx call ... --print-message --compact-headers` pass without opening sockets.
- No-network examples: `sipx.examples.build_request` and `sipx.examples.handlers` pass.
- Live root examples: REGISTER/OPTIONS smoke returned `registered` and `200 OK`; call examples with explicit `SIPX_TARGET` returned structured `SipCallError` for `502 Bad Gateway`; missing `SIPX_TARGET` returned structured `ExampleConfigError`.
- `python -m pytest` skipped for block `1.11.0` per user direction; last full core test run was 92 pass after block `1.10.0`.
- Docker remains unavailable in this WSL environment, so opt-in Asterisk integration was not run locally.
