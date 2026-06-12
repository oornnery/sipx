# Handoff

## Summary

Block `1.25.0` implemented full `TlsTransport` in `sipx.transport.tls` with `ssl.SSLContext` support, extending `TcpTransport` with TLS encryption and certificate validation per RFC 3261 §26.2 and RFC 5922; `TlsConfig` dataclass with `certfile`, `keyfile`, `ca_certs`, `verify_mode`, and `check_hostname` fields; 12 tests in `tests/test_transport_tls.py` covering import, subclass verification, transport type, config dataclass, TLS connection, send/receive over TLS, close behavior, and certificate validation modes. All tests, ruff lint/format, and type check pass.

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

After block `1.19.0`:

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
- `ruff format --check .`: pass.
- `uv run ty check`: pass.
- `git diff --check`: pass/no output.
- `pytest`: 110 pass (90 existing + 8 registry tests + 12 TLS transport tests).
