# Checks

## Known Commands

| Command | Purpose | Status |
| --- | --- | --- |
| `ruff format --check .` | formatting | pass |
| `ruff check .` | lint | pass |
| `uv run ty check` | type check | pass |
| `pytest tests/test_transport_base.py` | transport base tests | 6 pass |
| `pytest tests/test_transport_registry.py` | transport registry tests | 8 pass |
| `pre-commit run --all-files` | full local hooks | not run yet |

## Latest Results

| Date | Command | Result | Notes |
| --- | --- | --- | --- |
| 2026-06-13 | `uv run pytest -q` (block 3.5.0) | pass | 507 core pass incl. retransmission tests. |
| 2026-06-13 | `uv run ruff check` / `ruff format` / `ty check` (3.5.0) | pass | Clean after §17 retransmission. |
| 2026-06-13 | `uv run pytest -q` (block 3.4.0) | pass | 504 core pass incl. rport/learned-address/non-2xx-ACK/CANCEL tests. |
| 2026-06-13 | `uv run ruff check` / `ruff format` / `ty check` (3.4.0) | pass | Clean after P1 part-1 client changes. |
| 2026-06-13 | `uv run pytest -q` (block 3.3.0) | pass | 498 core pass. |
| 2026-06-13 | `uv run pytest apps -q` (block 3.3.0) | pass | 71 pass, 3 opt-in skips incl. 6 new FastAPI tests. |
| 2026-06-13 | `uv run ruff check .` / `ruff format --check .` / `ty check` (3.3.0) | pass | Clean after FastAPI app block. |
| 2026-06-13 | `uv run pytest -q` (block 3.2.0) | pass | 498 pass after P0 security + extensions rename + provisional removal. |
| 2026-06-13 | `uv run ruff check .` / `ruff format .` / `ty check` (3.2.0) | pass | Clean after security/reorg block. |
| 2026-06-13 | `uv run ruff check .` (blocks 3.1.2-3.1.4) | pass | All checks passed. |
| 2026-06-13 | `uv run ruff format --check .` (blocks 3.1.2-3.1.4) | pass | 152 files already formatted. |
| 2026-06-13 | `uv run ty check` (blocks 3.1.2-3.1.4) | pass | Clean; docs/examples only, no type surface change. |
| 2026-06-13 | `uv run pytest` (block 3.1.0) | pass | 503 core pass incl. new `Response.history` multi-provisional + 401-challenge tests. |
| 2026-06-13 | `uv run pytest apps` (block 3.1.0) | pass | 65 pass, 3 opt-in skips after `Response.history` addition. |
| 2026-06-13 | `uv run ruff check .` (block 3.1.0) | pass | All checks passed. |
| 2026-06-13 | `uv run ruff format --check .` (block 3.1.0) | pass | 146 files already formatted. |
| 2026-06-13 | `uv run ty check` (block 3.1.0) | pass | Clean after `Response.history` + `_send_and_receive` rewrite. |
| 2026-06-12 | `uv run pytest tests apps` (block 3.0.0) | pass | 567 pass, 3 opt-in skips after full legacy removal, CLI rewrite, and AsyncClient request/ack/bye additions. |
| 2026-06-12 | `uv run ruff check .` (block 3.0.0) | pass | Clean after legacy removal. |
| 2026-06-12 | `uv run ruff format --check .` (block 3.0.0) | pass | 146 files formatted. |
| 2026-06-12 | `uv run ty check` (block 3.0.0) | pass | Clean after legacy removal and CLI rewrite. |
| 2026-06-12 | `uv run --package sipx-cli sipx --help` (block 3.0.0) | pass | New surface: options, message, request, register, unregister. |
| 2026-06-12 | `python -c "import sipx"` (block 3.0.0) | pass | 101 root exports; no legacy symbols. |
| 2026-06-12 | `uv run pytest` (block 2.0.0) | pass | 525 core tests pass after AsyncClient overhaul, example V64 fixes, and type fixes. |
| 2026-06-12 | `uv run pytest apps` (block 2.0.0) | pass | 65 pass, 3 skip after rewriting stale CLI test fakes to drive real `SipUserAgent.request()`. |
| 2026-06-12 | `uv run ruff check .` (block 2.0.0) | pass | Clean after auto-fixes; uncommitted `[tool.ruff] preview = true` was removed (caused 154 preview-only findings). |
| 2026-06-12 | `uv run ruff format --check .` (block 2.0.0) | pass | 168 files formatted; overhaul commits had 26 unformatted files, now fixed. |
| 2026-06-12 | `uv run ty check` (block 2.0.0) | pass | Fixed 19 diagnostics in client/protocol/rfc/transport/tests from the overhaul. |
| 2026-06-12 | `uv run pytest --cov=sipx --cov-fail-under=90` | fail | 82% total (87% excluding `sipx/examples/*`); overhaul plan target of 90% not reached. Biggest gaps: `sipx/legacy.py` 77%, example scripts 19-36%. |
| 2026-06-12 | `python -c "from sipx import AsyncClient, Request, Response"` | pass | Root exports fixed; previously `Request`/`Response`/`ClientConfig` were missing from `sipx/__init__.py`. |
| 2026-06-12 | `pytest tests/test_transport_tls.py` | pass | 12 tests pass for TlsTransport and TlsConfig implementation. |
| 2026-06-12 | `ruff check sipx/transport/tls.py tests/test_transport_tls.py` | pass | All lint checks pass for TLS transport implementation. |
| 2026-06-12 | `ruff format --check sipx/transport/tls.py tests/test_transport_tls.py` | pass | Format clean for TLS transport files. |
| 2026-06-12 | `pytest tests/test_transport_registry.py` | pass | 8 tests pass for TransportRegistry and create_transport factory. |
| 2026-06-12 | `ruff check sipx/transport/registry.py sipx/transport/tls.py` | pass | All lint checks pass for new registry and TLS stub. |
| 2026-06-12 | `ruff format --check .` | pass | Format clean after registry and TLS stub additions. |
| 2026-06-12 | `uv run ty check` | pass | Type-check gate passes after registry and TLS stub additions. |
| 2026-06-12 | `git diff --check` | pass/no output | No whitespace errors after registry and TLS stub additions. |
| 2026-06-10 | `pytest` | pass | 90 core tests pass after RTP wire event hooks. |
| 2026-06-10 | `ruff check .` | pass | All lint checks pass after RTP wire event hooks. |
| 2026-06-10 | `ruff format --check .` | pass | Format clean after RTP wire event hooks. |
| 2026-06-10 | `uv run ty check` | pass | Type-check gate passes after RTP wire event hooks. |
| 2026-06-10 | `git diff --check` | pass/no output | No whitespace errors. |
| 2026-06-10 | RTP hook functional test | pass | TX/RX `RtpWireEvent` captured and printed correctly with session loopback. |
| --- | --- | --- | --- |
| 2026-06-09 | `pytest tests/test_uac_uas.py tests/test_examples.py` | pass | 32 focused tests after switching `event_hooks["response"]` to `event_hooks["wire"]` for direction-aware capture. |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after event_hooks refactor. |
| 2026-06-09 | `ruff format --check .` | pass | 113 files already formatted after event_hooks refactor. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after event_hooks refactor. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after event_hooks refactor.
| 2026-06-08 | `docker --version` | blocked | Docker command is unavailable in this WSL environment; Asterisk integration remains opt-in and unrun. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.5.0` to `1.6.0`. |
| 2026-06-08 | runnable examples smoke | pass | `uv run python examples/llm/semantic_smoke.py`, `examples/native/sip_cli_flow.py`, `call_with_dtmf.py --help`, `mizu_call.py register --help`, and `uv run sipx call --help` passed. |
| 2026-06-08 | focused DTMF/LLM/examples tests | pass | `tests/test_native_softphone.py::test_native_softphone_runs_outbound_call_and_hangup`, CLI DTMF test, example tests, and LLM tests passed after B9 fix. |
| 2026-06-08 | final `python -m pytest` | pass | 124 passed, 3 skipped after `1.6.0` generic LLM naming, runnable examples, and SIP INFO DTMF changes. |
| 2026-06-08 | final `ruff check .` | pass | All lint checks passed after `1.6.0` changes. |
| 2026-06-08 | final `ruff format --check .` | pass | 79 files already formatted after `1.6.0` changes. |
| 2026-06-08 | final `uv run ty check` | pass | Configured type-check gate passes after `1.6.0` changes. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors after `1.6.0` changes. |
| 2026-06-08 | final `uv build --out-dir /tmp/opencode/sipx-build-1.6.0-final` | pass | Built final `1.6.0` sdist and wheel outside the repo. |
| 2026-06-08 | final secret/provider-name scan | pass/no matches | No private proxy markers, inline LLM keys, SIP auth headers, or provider-specific names in code/tests/examples/docs/TOML/YAML. |
| 2026-06-08 | final `docker --version` | blocked | Docker command is unavailable in this WSL environment; Asterisk integration remains opt-in and unrun. |
| 2026-06-08 | `python -m pytest tests/test_llm.py tests/test_examples_templates.py` | pass | 8 passed, 1 skipped after LLM env default regression. |
| 2026-06-08 | minimal LLM env default smoke | pass | `SIPX_LLM_API_KEY=test-key` builds `LLMChatClient.from_env()` with default base URL, model, and timeout. |
| 2026-06-08 | final `python -m pytest` | pass | 125 passed, 3 skipped after `1.6.1` LLM env default fix. |
| 2026-06-08 | final `ruff check .` | pass | All lint checks passed after `1.6.1` fix. |
| 2026-06-08 | final `ruff format --check .` | pass | 79 files already formatted after `1.6.1` fix. |
| 2026-06-08 | final `uv run ty check` | pass | Configured type-check gate passes after `1.6.1` fix. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors after `1.6.1` fix. |
| 2026-06-08 | final `uv build --out-dir /tmp/opencode/sipx-build-1.6.1-final` | pass | Built final `1.6.1` sdist and wheel outside the repo. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.6.1` to `1.7.0`. |
| 2026-06-08 | focused SIP-flow audit tests | pass | `tests/test_examples_templates.py tests/test_llm.py`: 11 passed, 1 skipped after auth-redaction audit fix. |
| 2026-06-08 | runnable LLM/native example smoke | pass | Direct LLM smoke and SIP-flow audit skipped cleanly without key; native CLI flow printer emitted runnable commands. |
| 2026-06-08 | final `python -m pytest` | pass | 128 passed, 3 skipped after `1.7.0` SIP-flow audit example. |
| 2026-06-08 | final `ruff check .` | pass | All lint checks passed after `1.7.0` changes. |
| 2026-06-08 | final `ruff format --check .` | pass | 80 files already formatted after `1.7.0` changes. |
| 2026-06-08 | final `uv run ty check` | pass | Configured type-check gate passes after `1.7.0` changes. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors after `1.7.0` changes. |
| 2026-06-08 | final `uv build --out-dir /tmp/opencode/sipx-build-1.7.0-final` | pass | Built final `1.7.0` sdist and wheel outside the repo. |
| 2026-06-08 | final secret/provider-name scan | pass/no matches | No private proxy markers, inline LLM keys, SIP auth headers, or provider-specific names in code/tests/examples/docs/TOML/YAML. |
| 2026-06-09 | real proxy `sipx call --debug-sip` | pass | Authenticated INVITE reached `200 OK`; first BYE received `401`; authenticated BYE retry received `200 OK`; no real secret/account/proxy values persisted. |
| 2026-06-09 | `uv lock` | pass | Updated lockfile project version from `1.7.0` to `1.7.1`. |
| 2026-06-09 | `python -m pytest tests/test_native_softphone.py::test_v38_native_softphone_retries_bye_with_digest_auth` | pass | Loopback regression verifies challenged BYE retries with Digest and password is not emitted in Authorization. |
| 2026-06-09 | `python -m pytest tests/test_native_softphone.py tests/test_native_sip_backend.py` | pass | 24 native SIP/softphone tests passed after BYE Digest retry fix. |
| 2026-06-09 | focused BYE fix lint/format | pass | `ruff check` and `ruff format --check` passed for native backend, softphone, and regression test. |
| 2026-06-09 | final `python -m pytest` | pass | 129 passed, 3 skipped after `1.7.1` BYE Digest retry fix. |
| 2026-06-09 | final `ruff check .` | pass | All lint checks passed after `1.7.1` fix. |
| 2026-06-09 | final `ruff format --check .` | pass | 80 files already formatted after `1.7.1` fix. |
| 2026-06-09 | final `uv run ty check` | pass | Configured type-check gate passes after `1.7.1` fix. |
| 2026-06-09 | final `git diff --check` | pass/no output | No whitespace errors after `1.7.1` fix. |
| 2026-06-09 | final private marker/auth scan | pass/no matches | No real proxy/account/password/destination markers or unredacted SIP auth headers found in repo files. |
| 2026-06-09 | final `uv build --out-dir /tmp/opencode/sipx-build-1.7.1-final` | pass | Built final `1.7.1` sdist and wheel outside the repo. |
| 2026-06-09 | `uv init --package --build-backend hatch ... apps/*` | pass | Created `apps/llm`, `apps/softphone`, `apps/asterisk`, `apps/cli`, `apps/scenarios`, `apps/stt`, and `apps/tts` package skeletons, then replaced stubs with real package contents. |
| 2026-06-09 | `uv lock` | pass | Updated lockfile for root `sipx` `1.8.0` and workspace app packages. |
| 2026-06-09 | workspace CLI smoke | pass | `uv run --package sipx-cli sipx --help` and `sipx call --help` resolve through `apps/cli`. |
| 2026-06-09 | moved examples smoke | pass | Moved LLM examples skip cleanly without key; moved native CLI flow prints `uv run --package sipx-cli sipx ...` commands. |
| 2026-06-09 | root boundary smoke | pass | Root `sipx` import no longer exposes `LLMChatClient`, `AsteriskBackend`, or `NativeSoftphone`. |
| 2026-06-09 | final `python -m pytest` | pass | 129 passed, 3 skipped after `1.8.0` workspace split. |
| 2026-06-09 | final `ruff check .` | pass | All lint checks passed after workspace split. |
| 2026-06-09 | final `ruff format --check .` | pass | 82 files already formatted after workspace split. |
| 2026-06-09 | final `uv run ty check` | pass | Type-check gate passes after app packages were added to root dev workspace dependencies. |
| 2026-06-09 | final `git diff --check` | pass/no output | No whitespace errors after workspace split. |
| 2026-06-09 | final private marker/auth scan | pass/no matches | Scanned code, apps, tests, docs, and TOML for private proxy/account/password/destination markers, personal author stub, and unredacted SIP auth headers. |
| 2026-06-09 | final `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.8.0-final-docs` | pass | Built root package plus all seven app package sdists/wheels outside the repo after docs/workflow updates. |
| 2026-06-09 | `uv lock` | pass | Updated lockfile project version from `1.8.0` to `1.8.1`. |
| 2026-06-09 | focused SIP/core/app tests | pass | `python -m pytest tests/test_uac_uas.py apps/softphone/tests/test_sip_softphone.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py`: 51 passed after SIP naming/provisional timeout work. |
| 2026-06-09 | root core `python -m pytest` | pass | Root pytest now collects only `tests/`; 82 core tests passed with backend/SIP ABC contract tests. |
| 2026-06-09 | explicit app tests | pass | `python -m pytest apps/cli/tests/test_cli.py apps/softphone/tests/test_sip_softphone.py`: 26 app tests passed by explicit path. |
| 2026-06-09 | `uv run ty check` | fail | Generic `**kwargs` SIP role ABC signatures caused invalid method override diagnostics; recorded as SPEC B14/V46 and fixed with explicit signatures. |
| 2026-06-09 | final `uv run ty check` | pass | Configured type-check gate passes after explicit SIP role ABC signatures. |
| 2026-06-09 | final `ruff check .` | pass | All lint checks passed after ABC/test-boundary changes. |
| 2026-06-09 | final `ruff format --check .` | pass | 83 files already formatted after ABC/test-boundary changes. |
| 2026-06-09 | final `git diff --check` | pass/no output | No whitespace errors after ABC/test-boundary changes. |
| 2026-06-09 | final name/auth scan | pass/no matches | No `NativeSip`/`NativeSoftphone` Python/TOML references and no unredacted SIP auth/private markers in Python files. |
| 2026-06-09 | final `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.8.1-final` | pass | Built root package plus all seven app package sdists/wheels outside the repo. |
| 2026-06-09 | `uv lock` | pass | Added `sipx-harness` workspace member to lockfile. |
| 2026-06-09 | focused harness migration tests | partial fail | Root `python -m pytest` passed 66; `apps/harness/tests` passed 16; CLI/softphone collection failed because softphone test still imported `Timeline` from root `sipx`; Asterisk collection failed due `AsteriskRuntime` import/export indentation bug. Recorded SPEC B15/B16. |
| 2026-06-09 | focused harness migration retry | pass | `apps/harness/tests` passed 17 including package-boundary regression; CLI/softphone passed 26; Asterisk app tests passed 13. |
| 2026-06-09 | `ruff format .` | pass | 84 files left unchanged after docs/runtime rename cleanup. |
| 2026-06-09 | `python -m pytest` | pass | 66 root SIP/protocol tests passed; root pytest remains core-only. |
| 2026-06-09 | `python -m pytest apps` | pass | 67 app tests passed, 3 skipped; integration/LLM live tests remain opt-in. |
| 2026-06-09 | `ruff check .` | pass | All lint checks passed after `sipx-harness` split and runtime naming cleanup. |
| 2026-06-09 | `ruff format --check .` | pass | 84 files already formatted. |
| 2026-06-09 | `uv run ty check` | pass | Type-check gate passes after harness split. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after harness split. |
| 2026-06-09 | secret/auth marker scan | pass/no matches | Python, Markdown, and TOML scan found no unredacted SIP auth headers, inline LLM keys, ARI password assignments, or literal password assignments. |
| 2026-06-09 | public `backend` name scan | pass except packaging | Python scan has no generic backend API names; only `build-backend` packaging metadata remains. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.8.1-harness` | pass | Built root plus `sipx-asterisk`, `sipx-cli`, `sipx-harness`, `sipx-llm`, `sipx-scenarios`, `sipx-softphone`, `sipx-stt`, and `sipx-tts` sdists/wheels outside repo. |
| 2026-06-09 | empty directory scan | pass | `find . -path ./.git -prune -o -type d -empty -print` returned no empty directories after removing stale `sipx/core`, `sipx/backends`, and `apps/softphone/examples/native`. |
| 2026-06-09 | focused media/redaction tests | pass | `tests/test_media.py`, `tests/test_redaction.py`, `apps/stt/tests/test_stt_protocol.py`, and `apps/asterisk/tests/test_asterisk_runtime.py`: 17 passed after moving speech protocols and tightening redaction. |
| 2026-06-09 | `python -m pytest` | pass | 66 root tests passed; root no longer exports STT/TTS speech protocols. |
| 2026-06-09 | `python -m pytest apps` | pass | 69 app tests passed, 3 skipped; STT/TTS protocol tests are under app packages. |
| 2026-06-09 | `ruff check .` | pass | All lint checks passed after root media boundary fix. |
| 2026-06-09 | `ruff format --check .` | pass | 87 files already formatted. |
| 2026-06-09 | `uv run ty check` | pass | Type-check gate passes after STT/TTS move. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after STT/TTS move before checks log update. |
| 2026-06-09 | root speech protocol scan | pass/no matches | No `SttEngine`, `SttStream`, `TranscriptEvent`, `TtsEngine`, `sipx.media.speech`, or `source="tts"` remains under root `sipx`. |
| 2026-06-09 | secret/auth marker scan | pass/no matches | Python and Markdown scans found no unredacted SIP auth headers, inline LLM keys, ARI password assignments, or literal password assignments. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.8.1-boundary` | pass | Built root plus all app package sdists/wheels outside repo after root media boundary fix. |
| 2026-06-09 | `python -m pytest` | pass | 64 root tests passed after moving generic redaction out of root `sipx`. |
| 2026-06-09 | `python -m pytest apps` | pass | 71 app tests passed, 3 skipped; redaction tests now live under `apps/harness/tests`. |
| 2026-06-09 | `ruff check .` | pass | All lint checks passed after moving redaction to `sipx_harness`. |
| 2026-06-09 | `ruff format --check .` | pass | 86 files already formatted. |
| 2026-06-09 | `uv run ty check` | pass | Type-check gate passes after removing root `sipx.security`. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after redaction move before checks log update. |
| 2026-06-09 | empty directory scan | pass/no output | No empty directories remain after removing `sipx/security`. |
| 2026-06-09 | root redaction boundary scan | pass/no matches | No `sipx.security`, root `Redactor`, root `default_redactor`, or `sipx/security/**` remains. |
| 2026-06-09 | secret/auth marker scan | pass/no matches | Python and Markdown scans found no unredacted SIP auth headers, inline LLM keys, ARI password assignments, or literal password assignments. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.8.1-redaction` | pass | Built root plus all app package sdists/wheels outside repo after moving redaction to `sipx_harness`. |

## Validation Policy

- For docs-only edits, run `git diff --check` at minimum.
- For Python code, run the narrow test first, then `ruff check .`, `uv run ty check`, and relevant `pytest`.
- For parser/protocol changes, add malformed and round-trip tests.
- For Asterisk integration, guard tests behind explicit env/config and never require real secrets in repo.
