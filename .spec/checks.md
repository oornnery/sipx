# Checks

## Known Commands

| Command | Purpose | Status |
| --- | --- | --- |
| `ruff format --check .` | formatting | pass after block `1.11.0` |
| `ruff check .` | lint | pass after block `1.11.0` |
| `uv run ty check` | type check | pass after block `1.11.0` |
| `pytest` | tests | skipped for block `1.11.0` per user; last pass after block `1.10.0` |
| `pre-commit run --all-files` | full local hooks | not run yet |

## Latest Results

| Date | Command | Result | Notes |
| --- | --- | --- | --- |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after 1.11 API/CLI/example updates. |
| 2026-06-09 | `ruff format --check .` | pass | 114 files already formatted after targeted formatting of CLI, handler example, and SIP headers. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after 1.11 request/helper/summary/hook surfaces. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after 1.11 validation. |
| 2026-06-09 | `ruff format --check .` | fail | Three files needed formatting after manual edits; fixed with targeted `ruff format`. |
| 2026-06-09 | `uv run --package sipx-cli sipx request ... --print-message --compact-headers` | pass | Rendered SIP OPTIONS with compact headers and explicit capabilities without opening a socket. |
| 2026-06-09 | `uv run --package sipx-cli sipx call ... --print-message --compact-headers` | pass | Rendered INVITE plus SDP with compact headers without opening SIP/RTP sockets. |
| 2026-06-09 | `uv run python -m sipx.examples.build_request` | pass | No-network request construction example ran. |
| 2026-06-09 | `uv run python -m sipx.examples.handlers` | pass | No-network decorator handler example ran. |
| 2026-06-09 | `uv run python -m sipx.examples.options` | pass | Live public Mizu run with `SIPX_LOCAL_HOST=172.26.249.223`; returned `200 OK`. |
| 2026-06-09 | `uv run python -m sipx.examples.smoke_tests` | pass | Live no-call smoke returned `register: registered` and OPTIONS `200 OK`. |
| 2026-06-09 | `uv run python -m sipx.examples.invite_without_sdp` | pass/behavior | With explicit demo target and short timeout, returned structured `SipCallError` for `502 Bad Gateway`. |
| 2026-06-09 | `uv run python -m sipx.examples.invite_with_sdp` | pass/behavior | With explicit demo target, returned structured `SipCallError`; without `SIPX_TARGET`, returned structured `ExampleConfigError`. |
| 2026-06-09 | `uv run python -m sipx.examples.metrics` | pass/behavior | With explicit demo target, returned structured `SipCallError` and `rtp: null`. |
| 2026-06-09 | `uv run python -m sipx.examples.manipulation` | pass/behavior | With explicit demo target, returned structured `SipCallError`. |
| 2026-06-09 | `SIPX_RUN_CALL=1 uv run python -m sipx.examples.smoke_tests` | pass/behavior | REGISTER/OPTIONS pass; call branch returned structured `SipCallError`. |
| 2026-06-09 | `git diff --check` | pass/no output | Final whitespace check after latest checks/handoff/decision updates. |
| 2026-06-09 | `python -m pytest` | pass | 92 core tests after moving root examples to `sipx.examples` and adding V65/B30-B32 coverage. |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after root example move and timeout/error handling. |
| 2026-06-09 | `ruff format --check .` | pass | 109 files already formatted after root example move and timeout/error handling. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after typing timeout regression coroutine as `SipCall`. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after root example move and V65 updates. |
| 2026-06-09 | `uv run ty check` | fail | Timeout regression test coroutine returned `None` where `await_call` expected `SipCall`; recorded B32 and fixed annotation. |
| 2026-06-09 | `python -m pytest tests/test_examples.py` | pass | 5 example tests for root module paths, no app deps, explicit `SIPX_TARGET`, structured errors, and bounded waits. |
| 2026-06-09 | `uv run python -m sipx.examples.register` | pass | Live public Mizu run with `SIPX_LOCAL_HOST=172.26.249.223`; returned `registered`. |
| 2026-06-09 | `uv run python -m sipx.examples.options` | pass | Live public Mizu run with `SIPX_LOCAL_HOST=172.26.249.223`; returned `200 OK`. |
| 2026-06-09 | `uv run python -m sipx.examples.invite_without_sdp` | pass/behavior | With explicit demo self-target, returned structured `SipCallError` for `502 Bad Gateway`; before fix this was traceback B30. |
| 2026-06-09 | `uv run python -m sipx.examples.invite_with_sdp` | pass/behavior | With explicit demo self-target, returned structured `SipCallError` for `502 Bad Gateway`; without `SIPX_TARGET`, returned structured `ExampleConfigError`. |
| 2026-06-09 | `uv run python -m sipx.examples.metrics` | pass/behavior | With explicit demo self-target and `SIPX_TIMEOUT=3`, returned structured `ExampleCallTimeout` and `rtp: null`. |
| 2026-06-09 | `uv run python -m sipx.examples.manipulation` | pass/behavior | With explicit demo self-target, returned structured `SipCallError` for `502 Bad Gateway`. |
| 2026-06-09 | `uv run python -m sipx.examples.smoke_tests` | pass | Live no-call smoke returned `register: registered` and OPTIONS `200 OK`. |
| 2026-06-09 | `SIPX_RUN_CALL=1 uv run python -m sipx.examples.smoke_tests` | pass/behavior | With explicit demo self-target and `SIPX_TIMEOUT=3`, returned structured call failure; before timeout fix shell command timed out at 60s B31. |
| 2026-06-09 | `git diff --check` | pass/no output | Final whitespace check after checks/handoff updates. |
| 2026-06-09 | `python -m pytest` | pass | 89 core tests after T67/T68 configurable UAS provisionals and root Mizu examples. |
| 2026-06-09 | `python -m pytest apps` | pass | 65 passed, 3 skipped after T67/T68. |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after T67/T68. |
| 2026-06-09 | `ruff format --check .` | pass | 110 files already formatted after T67/T68. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after `SipProvisionalResponse` API and root examples. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after T67/T68 before final checks update. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.10.0-provisionals` | pass | Built root `sipx-1.10.0` and all app package sdists/wheels outside repo. |
| 2026-06-09 | `uv lock` | pass | Updated lockfile root package from `sipx v1.9.0` to `sipx v1.10.0`. |
| 2026-06-09 | `python -m pytest tests/test_uac_uas.py tests/test_examples.py` | pass | 31 focused tests for `SipProvisionalResponse`, UAS provisional sequences, and root examples. |
| 2026-06-09 | `ruff check sipx/ua.py sipx/uas.py sipx/uac.py sipx/sip/requests.py sipx/__init__.py sipx/examples tests/test_uac_uas.py tests/test_examples.py` | pass | Focused lint clean for changed SIP/example surfaces. |
| 2026-06-09 | `ruff format --check sipx/ua.py sipx/uas.py sipx/uac.py sipx/sip/requests.py sipx/__init__.py sipx/examples tests/test_uac_uas.py tests/test_examples.py` | pass | 17 focused files already formatted after targeted formatting. |
| 2026-06-09 | `python -m pytest apps/scenarios/tests/test_examples_templates.py` | pass | 7 example import/secret-scan tests after README/example doc updates. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after final docs/state updates. |
| 2026-06-09 | `python -m pytest` | pass | 83 core tests after T59/T65/T66 SIP/RTP CLI, lazy PyAudio, and pure-Python Mizu examples. |
| 2026-06-09 | `python -m pytest apps` | pass | 65 passed, 3 skipped after T59/T65/T66. |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after T59/T65/T66. |
| 2026-06-09 | `ruff format --check .` | pass | 99 files already formatted after T59/T65/T66. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after narrowing CLI/Mizu audio modes and optional RTP sessions. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after T59/T65/T66. |
| 2026-06-09 | `uv run --package sipx-cli sipx --help` | pass | Top-level commands are `options`, `message`, `request`, `register`, `unregister`, `call`, `listen`. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-cli-rtp` | pass | Built root and all app package sdists/wheels outside repo after T59/T65/T66. |
| 2026-06-09 | `uv lock` | pass | Refreshed lockfile after `sipx-cli` dependency narrowed to root `sipx`. |
| 2026-06-09 | `python -m pytest tests/test_media.py tests/test_uac_uas.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py` | pass | 60 focused tests for PyAudio, UAC/UAS media, CLI surface, and examples. |
| 2026-06-09 | `ruff check apps/cli/src/sipx_cli/main.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py apps/scenarios/examples/mizu sipx/media/pyaudio.py sipx/media/frame.py sipx/media/__init__.py sipx/__init__.py sipx/uac.py sipx/uas.py tests/test_media.py tests/test_uac_uas.py` | pass | Focused lint clean for changed Python surfaces. |
| 2026-06-09 | `ruff format --check apps/cli/src/sipx_cli/main.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py apps/scenarios/examples/mizu sipx/media/pyaudio.py sipx/media/frame.py sipx/media/__init__.py sipx/__init__.py sipx/uac.py sipx/uas.py tests/test_media.py tests/test_uac_uas.py` | pass | Focused formatting clean after targeted `ruff format apps/cli/src/sipx_cli/main.py`. |
| 2026-06-09 | `uv run ty check` | fail | CLI/Mizu argparse audio values were not narrowed to Literals and RTP snapshots called optional session lookup twice. Recorded B29; fixed with explicit narrowing. |
| 2026-06-09 | `python -m pytest` | pass | 81 core tests after T58 completion and softphone package removal. |
| 2026-06-09 | `python -m pytest apps` | pass | 64 passed, 3 skipped after removing `apps/softphone` package/tests. |
| 2026-06-09 | `ruff check .` | pass | Full lint clean after T58 completion. |
| 2026-06-09 | `ruff format --check .` | pass | 90 files already formatted after T58 completion. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after `SipUserAgent.__aenter__` preserves concrete `Self`. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-uac-uas` | pass | Built root and all remaining app package sdists/wheels; `sipx-softphone` absent. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after T58 completion. |
| 2026-06-09 | `uv run ty check` | fail | Inherited async context typed `SipUac`/`SipUas` as base `SipUserAgent`; mixed test dict inferred `int` values. Recorded B26; fixed with `Self` return and test annotation. |
| 2026-06-09 | `python -m pytest tests/test_uac_uas.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py` | pass | 51 focused tests after B26 type fix. |
| 2026-06-09 | `python -m pytest apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py` | pass | 26 tests after CLI UAC/UAS mocks and scenario example move. |
| 2026-06-09 | `ruff check apps/cli/src/sipx_cli/main.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py apps/scenarios/examples/sip/call_with_dtmf.py apps/scenarios/examples/sip/mizu_call.py apps/scenarios/examples/sip/sip_cli_flow.py` | pass | Touched CLI/example Python lint clean. |
| 2026-06-09 | `ruff format --check apps/cli/src/sipx_cli/main.py apps/cli/tests/test_cli.py apps/scenarios/tests/test_examples_templates.py apps/scenarios/examples/sip/call_with_dtmf.py apps/scenarios/examples/sip/mizu_call.py apps/scenarios/examples/sip/sip_cli_flow.py` | pass | 6 touched Python files already formatted. |
| 2026-06-09 | `uv lock` | pass | Removed `sipx-softphone v0.1.0` from lockfile after workspace package removal. |
| 2026-06-09 | `ruff format --check apps/cli/src/sipx_cli/main.py apps/cli/tests/test_cli.py apps/cli/pyproject.toml FORMAT.md` | blocked | Ruff Markdown formatting is experimental without preview; Python/TOML checks reran separately and `git diff --check` covers whitespace. |
| 2026-06-09 | `python -m pytest` | pass | 81 core tests after call-level synthetic RTP and V59 bind/advertise split. |
| 2026-06-09 | `python -m pytest apps` | pass | 71 passed, 3 skipped after call-level synthetic RTP and V59 bind/advertise split. |
| 2026-06-09 | `ruff check .` | pass | No lint violations after final call-audio validation. |
| 2026-06-09 | `ruff format --check .` | pass | 93 files already formatted after final call-audio validation. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after final call-audio validation. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-call-audio` | pass | Built root and all app package sdists/wheels outside repo. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after final call-audio validation. |
| 2026-06-09 | `python -m pytest tests/test_uac_uas.py tests/test_rtp.py` | pass | 40 tests including call-level synthetic RTP and V59 bind/advertise split. |
| 2026-06-09 | `python -m pytest` | pass | 79 core tests after `RtpAudioSession` and high-level UAC/UAS helpers. |
| 2026-06-09 | `python -m pytest apps` | pass | 71 passed, 3 skipped after `RtpAudioSession` and high-level UAC/UAS helpers. |
| 2026-06-09 | `ruff check .` | pass | No lint violations after final validation. |
| 2026-06-09 | `ruff format --check .` | pass | 93 files already formatted after final validation. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after RTP UDP address normalization. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-rtp-audio` | pass | Built root and all app package sdists/wheels outside repo. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after final validation. |
| 2026-06-09 | `python -m pytest tests/test_rtp.py` | pass | 15 tests including `RtpAudioSession` loopback noise/silence and parse-error metrics. |
| 2026-06-09 | `python -m pytest tests/test_uac_uas.py` | pass | 23 tests including high-level `SipUac` register/call and `SipUas` answer/wait-hangup helpers. |
| 2026-06-09 | `python -m pytest` | pass | 73 core tests after split `sipx.uac`/`sipx.uas` modules. |
| 2026-06-09 | `python -m pytest apps` | pass | 71 passed, 3 skipped after split `sipx.uac`/`sipx.uas` modules. |
| 2026-06-09 | `ruff check .` | pass | No lint violations in final validation. |
| 2026-06-09 | `ruff format --check .` | pass | 91 files already formatted in final validation. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after split modules. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-final` | pass | Built root and all app package sdists/wheels outside repo after split modules. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors in final validation. |
| 2026-06-09 | `python -m pytest tests/test_uac_uas.py` | pass | 20 tests including split `sipx.uac`/`sipx.uas` module regression. |
| 2026-06-09 | `python -m pytest` | pass | 72 core tests after RTP metrics/jitter buffer block. |
| 2026-06-09 | `python -m pytest apps` | pass | 71 passed, 3 skipped after RTP metrics/jitter buffer block. |
| 2026-06-09 | `ruff check .` | pass | No lint violations after formatting. |
| 2026-06-09 | `ruff format --check .` | pass | 89 files already formatted after targeted `ruff format`. |
| 2026-06-09 | `uv run ty check` | pass | Type check passes after new RTP/media exports. |
| 2026-06-09 | `uv lock` | pass | Lockfile metadata resolved after version bump to `1.9.0`. |
| 2026-06-09 | `uv build --all-packages --out-dir /tmp/opencode/sipx-build-1.9.0-rtp-metrics` | pass | Built root and all app package sdists/wheels outside repo. |
| 2026-06-09 | `git diff --check` | pass/no output | No whitespace errors after block `1.9.0`. |
| 2026-06-09 | `python -m pytest tests/test_rtp.py tests/test_media.py` | pass | 18 tests covering G.711, synthetic silence/noise, RTP jitter metrics, `RtpMetrics`, and `RtpJitterBuffer`. |
| 2026-06-08 | `git diff --check` | pass/no output | Repo root has untracked `sipx/`, so this does not cover new untracked docs. |
| 2026-06-08 | `rg -n "[ \\t]$" <new docs>` | pass/no output | New files have no trailing whitespace. |
| 2026-06-08 | `grep` tool trailing whitespace scan | pre-existing issue | Matches only in existing `IDEA.md`; not modified. |
| 2026-06-08 | `rg` Portuguese-term scan on maintained docs | pass except `example.com` | Docs are English; matches were only `example.com` domains. |
| 2026-06-08 | `git diff --check` | pass/no output | After README/spec/design/todo/memory updates. |
| 2026-06-08 | `rg` Portuguese-term scan on maintained current-structure docs | pass except `example.com` | Detailed docs consolidated into `DESIGN.md`; matches are SIP example domains and previous check note. |
| 2026-06-08 | `rg -n "[ \\t]$" <maintained current-structure docs>` | pass/no output | No trailing whitespace in maintained docs. |
| 2026-06-08 | `git diff --check` | pass/no output | After detailed docs were consolidated into current structure. |
| 2026-06-08 | `glob docs/**` | pass/no files | No separate `/docs` tree remains. |
| 2026-06-08 | final current-structure Portuguese-term scan | pass except `example.com` | Maintained docs are English; matches are SIP example domains and prior check notes. |
| 2026-06-08 | final current-structure trailing whitespace scan | pass/no output | `README.md`, `SPEC.md`, `DESIGN.md`, `TODO.md`, `.spec/*`, `.mem/*`. |
| 2026-06-08 | final `git diff --check` | pass/no output | Consolidation complete. |
| 2026-06-08 | `python -m pytest` | fail | Active `pytest` lacked async plugin for `pytest.mark.asyncio`; recorded as `SPEC.md` §B B1 and changed tests to `asyncio.run`. |
| 2026-06-08 | `ruff check .` | fail | Unused import in `sipx/cli/main.py`; removed. |
| 2026-06-08 | `python -m pytest` | pass | 8 tests passed after async test adjustment. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after import fix. |
| 2026-06-08 | `ruff format --check .` | fail | 4 files needed formatting; fixed with `ruff format .`. |
| 2026-06-08 | `ruff format .` | pass | 4 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 8 tests passed after formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 22 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; active environment is missing the declared dev tool. |
| 2026-06-08 | `python -m pytest` | fail | Redaction text replacement assumed every regex had a capture group; recorded as `SPEC.md` §B B2 and fixed. |
| 2026-06-08 | `ruff check .` | pass | No lint issues during block `0.3.0` before redaction fix. |
| 2026-06-08 | `ruff format --check .` | fail | 2 files needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | `ruff format sipx/security/redaction.py tests/test_media.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 15 tests passed after redaction fix. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after redaction fix. |
| 2026-06-08 | `ruff format --check .` | pass | 31 files already formatted. |
| 2026-06-08 | `python -m pytest` | pass | 22 tests passed for SIP parser block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for SIP parser block. |
| 2026-06-08 | `ruff format --check .` | fail | 3 SIP files needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | `ruff format sipx/sip/message.py sipx/sip/uri.py tests/test_sip_message.py` | pass | 3 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 22 tests passed after SIP formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after SIP formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 36 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `python -m pytest` | pass | 26 tests passed for SDP block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for SDP block. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/sdp/parser.py` needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | `ruff format sipx/sdp/parser.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 26 tests passed after SDP formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after SDP formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 41 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `python -m pytest` | pass | 32 tests passed for RTP/DTMF block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for RTP/DTMF block. |
| 2026-06-08 | `ruff format --check .` | fail | `tests/test_rtp.py` needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | `ruff format tests/test_rtp.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 32 tests passed after RTP formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after RTP formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 46 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `python -m pytest` | pass | 38 tests passed for SIP transaction/dialog block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for SIP transaction/dialog block. |
| 2026-06-08 | `ruff format --check .` | fail | 3 SIP transaction/dialog files needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | `ruff format sipx/sip/dialog.py sipx/sip/transaction.py tests/test_sip_transaction_dialog.py` | pass | 3 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 38 tests passed after SIP transaction/dialog formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 49 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `python -m pytest` | pass | 41 tests passed for SIP auth/register block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for SIP auth/register block. |
| 2026-06-08 | `ruff format --check .` | fail | 2 auth/register files needed formatting; fixed with targeted `ruff format`. |
| 2026-06-08 | auth helper grep | pass | Password is only used inside Digest HA1 calculation; MD5 uses `usedforsecurity=False`. |
| 2026-06-08 | `ruff format sipx/sip/transaction.py tests/test_sip_auth_requests.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 41 tests passed after auth/register formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after auth/register formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 52 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `python -m pytest tests/test_sip_transaction_dialog.py` | pass | 11 tests passed for UAS INVITE and BYE block before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 46 tests passed for UAS INVITE and BYE block before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for UAS INVITE and BYE block before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/sip/transaction.py` and `tests/test_sip_transaction_dialog.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/sip/transaction.py tests/test_sip_transaction_dialog.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 46 tests passed after UAS INVITE and BYE formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after UAS INVITE and BYE formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 52 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors in unstaged diff after formatting. |
| 2026-06-08 | `python -m pytest tests/test_sip_auth_requests.py` | pass | 8 tests passed for REGISTER client flow before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 51 tests passed for REGISTER client flow before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for REGISTER client flow before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/sip/register.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/sip/register.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 51 tests passed after REGISTER client flow formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after REGISTER client flow formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 53 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors in unstaged diff after REGISTER formatting. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 4 loopback UDP tests passed for real Native SIP runtime before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 55 tests passed for real Native SIP runtime before lint/format fixes. |
| 2026-06-08 | `ruff check .` | fail | Unused `SipMessage` import in `sipx/backends/native.py`; no product invariant change needed. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/backends/native.py` and `sipx/sip/transport.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/backends/native.py sipx/sip/transport.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 55 tests passed after real Native SIP runtime formatting/lint fix. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after native runtime lint fix. |
| 2026-06-08 | `ruff format --check .` | pass | 55 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after native runtime block. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 5 loopback UDP tests passed for strict INVITE/ACK/BYE call runtime before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 56 tests passed for strict call runtime before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for strict call runtime before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `tests/test_native_sip_backend.py` needed formatting. |
| 2026-06-08 | `ruff format tests/test_native_sip_backend.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 56 tests passed after strict call runtime formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after strict call runtime formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 55 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after strict call runtime block. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 6 loopback UDP tests passed for CANCEL runtime before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 57 tests passed for CANCEL runtime. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for CANCEL runtime. |
| 2026-06-08 | `ruff format --check .` | pass | 55 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after CANCEL runtime block. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 8 loopback UDP tests passed for REGISTER orchestration before full validation. |
| 2026-06-08 | `python -m pytest` | pass | 59 tests passed for REGISTER orchestration before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for REGISTER orchestration before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/backends/native.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/backends/native.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 59 tests passed after REGISTER orchestration formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after REGISTER orchestration formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 55 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after REGISTER orchestration block. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | fail | Timer code referenced `asyncio` without importing it; recorded as SPEC §B B3 and fixed. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 9 native SIP loopback tests passed after `asyncio` import fix. |
| 2026-06-08 | `python -m pytest` | pass | 60 tests passed for retransmission timers before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for retransmission timers before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/backends/native.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/backends/native.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest` | pass | 60 tests passed after retransmission timer formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after retransmission timer formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 55 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after retransmission timer block. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_backend.py` | pass | 5 no-Asterisk tests passed for ARI client and WebSocket event consumer before full validation. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for Asterisk ARI client block before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/backends/asterisk.py` and `tests/test_asterisk_backend.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/backends/asterisk.py tests/test_asterisk_backend.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_backend.py` | pass | 5 no-Asterisk tests passed after formatting. |
| 2026-06-08 | `python -m pytest` | pass | 65 tests passed after Asterisk ARI client/event block. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after Asterisk ARI client/event block. |
| 2026-06-08 | `ruff format --check .` | pass | 57 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after Asterisk ARI client/event block. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_backend.py` | pass | 7 no-Asterisk tests passed for ARI control/timeline mapping before full validation. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for Asterisk ARI control/timeline mapping before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/backends/asterisk.py` and `tests/test_asterisk_backend.py` needed formatting for T10 changes. |
| 2026-06-08 | `ruff format sipx/backends/asterisk.py tests/test_asterisk_backend.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_backend.py` | pass | 7 no-Asterisk tests passed after formatting. |
| 2026-06-08 | `python -m pytest` | pass | 67 tests passed after Asterisk ARI control/timeline mapping block. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after Asterisk ARI control/timeline mapping block. |
| 2026-06-08 | `ruff format --check .` | pass | 57 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after Asterisk ARI control/timeline mapping block. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_backend.py` | pass | 10 no-Asterisk tests passed for WebSocket media MVP. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after WebSocket media MVP. |
| 2026-06-08 | `ruff format --check .` | pass | 57 files already formatted after WebSocket media MVP. |
| 2026-06-08 | `python -m pytest` | pass | 70 tests passed after WebSocket media MVP state/design updates. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after WebSocket media MVP state/design updates. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_stasis_example.py` | pass | 3 no-Asterisk tests passed for inbound Stasis example before formatting. |
| 2026-06-08 | `ruff check .` | fail | Unused `Any` import in `tests/test_asterisk_stasis_example.py`; removed. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/examples/asterisk_stasis.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/examples/asterisk_stasis.py` | pass | 1 file reformatted. |
| 2026-06-08 | `python -m pytest tests/test_asterisk_stasis_example.py` | pass | 3 no-Asterisk tests passed after formatting/import fix. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after Stasis example import fix. |
| 2026-06-08 | `ruff format --check .` | pass | 60 files already formatted. |
| 2026-06-08 | `python -m pytest` | pass | 73 tests passed after Stasis example state/design updates. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after Stasis example state/design updates. |
| 2026-06-08 | `python -m pytest tests/test_native_softphone.py` | pass | 4 loopback UDP tests passed for headless native softphone before formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed for headless native softphone before formatting. |
| 2026-06-08 | `ruff format --check .` | fail | `sipx/softphone/native.py` and `tests/test_native_softphone.py` needed formatting. |
| 2026-06-08 | `ruff format sipx/softphone/native.py tests/test_native_softphone.py` | pass | 2 files reformatted. |
| 2026-06-08 | `python -m pytest tests/test_native_softphone.py` | pass | 4 loopback UDP tests passed after formatting. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after softphone formatting. |
| 2026-06-08 | `ruff format --check .` | pass | 63 files already formatted. |
| 2026-06-08 | `python -m pytest` | pass | 77 tests passed after softphone state/design updates. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after softphone state/design updates. |
| 2026-06-08 | `python -m pytest tests/test_native_sip_backend.py` | pass | 16 loopback UDP tests passed for native SIP lab hooks. |
| 2026-06-08 | `python -m pytest tests/test_native_softphone.py` | pass | 5 loopback UDP tests passed with softphone lab hook passthrough. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed for lab hook block. |
| 2026-06-08 | `ruff format --check .` | pass | 63 files already formatted after native backend formatting. |
| 2026-06-08 | `python -m pytest` | pass | 85 tests passed after lab hook state/design updates. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after lab hook block. |
| 2026-06-08 | `python -m pytest tests/test_recorder_reports_profiles.py tests/test_protocol_fuzz.py tests/test_cli.py tests/test_harness_scenario.py tests/test_asterisk_integration.py` | pass | 17 passed, 2 skipped for recorder/report/profile/mixed/fuzz and guarded Asterisk integration. |
| 2026-06-08 | `python -m pytest` | pass | 99 passed, 2 skipped after 1.0.0 roadmap completion. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after 1.0.0 roadmap completion. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after 1.0.0 roadmap completion. |
| 2026-06-08 | final `python -m pytest` | pass | 99 passed, 2 skipped. Asterisk integration tests are skipped unless `SIPX_ASTERISK_INTEGRATION=1`. |
| 2026-06-08 | final `ruff check .` | pass | All checks passed. |
| 2026-06-08 | final `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | final `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; blocker unchanged. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors before commit. |
| 2026-06-08 | `docker compose -f docker/asterisk/docker-compose.yml config` | blocked | `docker` command is unavailable in this WSL environment. |
| 2026-06-08 | `uv run sipx --help` | pass | Project builds with hatchling and console script resolves from repo root. |
| 2026-06-08 | `python -m pytest tests/test_cli.py` | pass | 4 CLI tests passed, including build metadata regression. |
| 2026-06-08 | `python -m pytest` | pass | 100 passed, 2 skipped after CLI packaging fix. |
| 2026-06-08 | `ruff check .` | pass | All checks passed after CLI packaging fix. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `python -m ty check` | blocked | `/usr/sbin/python: No module named ty`; system interpreter blocker unchanged. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics surfaced now that uv can run `ty`; not part of CLI packaging fix. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after CLI packaging fix. |
| 2026-06-08 | `python -m pytest tests/test_cli.py` | pass | 7 CLI tests passed after operational CLI additions. |
| 2026-06-08 | `ruff check sipx/cli/main.py tests/test_cli.py` | pass | Focused lint for operational CLI changes. |
| 2026-06-08 | `ruff format --check sipx/cli/main.py tests/test_cli.py` | pass | 2 changed CLI files already formatted. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.0.1` to `1.1.0`. |
| 2026-06-08 | `uv run sipx --help` | pass | Help now lists `scenario`, `replay`, `profile`, `phone`, `register`, `unregister`, `call`, and `listen`. |
| 2026-06-08 | `python -m pytest` | pass | 103 passed, 2 skipped after CLI/workflow block. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after CLI/workflow block. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv build` | pass | Built `dist/sipx-1.1.0.tar.gz` and `dist/sipx-1.1.0-py3-none-any.whl`; generated artifacts removed after validation. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after CLI/workflow block before docs/state updates. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics remain; not addressed in this block. |
| 2026-06-08 | `docker compose -f docker/asterisk/docker-compose.yml config` | blocked | Docker command unavailable in this WSL environment. |
| 2026-06-08 | `python3 -c <read pyproject version>` | pass | Release workflow version source resolves to `1.1.0`. |
| 2026-06-08 | final `uv run sipx --help` | pass | Commands include `scenario`, `replay`, `profile`, `phone`, `register`, `unregister`, `call`, and `listen`. |
| 2026-06-08 | final `python -m pytest` | pass | 103 passed, 2 skipped. |
| 2026-06-08 | final `ruff check .` | pass | All lint checks passed. |
| 2026-06-08 | final `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors after docs/state updates. |
| 2026-06-08 | workflow trailing-whitespace grep | pass/no output | No trailing whitespace in `.github/workflows/*.yml`. |
| 2026-06-08 | release tag comparison shell command | pass/no output | Exact publish-workflow command accepts `v1.1.0` from `pyproject.toml`. |
| 2026-06-08 | final `uv build --out-dir /tmp/opencode/sipx-build-1.1.0-final` | pass | Built final `1.1.0` sdist and wheel outside the repo. |
| 2026-06-08 | `uv run sipx register` | fail-fast expected | Exits with local config error; no `SipUdpError` timeout. |
| 2026-06-08 | `uv run sipx register --help` | pass | Shows `--aor`, `--registrar`, auth flags, remote flags, and examples. |
| 2026-06-08 | `python -m pytest tests/test_cli.py` | pass | 10 CLI tests passed after B5/V27 fix. |
| 2026-06-08 | `ruff check sipx/cli/main.py tests/test_cli.py` | pass | Focused lint for B5/V27 fix. |
| 2026-06-08 | `ruff format --check sipx/cli/main.py tests/test_cli.py` | pass | Focused format check for B5/V27 fix. |
| 2026-06-08 | `uv run sipx --help` | pass | Console script works after `1.1.1` bump. |
| 2026-06-08 | `python -m pytest` | pass | 106 passed, 2 skipped after B5/V27 fix. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after B5/V27 fix. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing diagnostics remain; B5/V27 fix did not add a new diagnostic. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors before check/state log updates. |
| 2026-06-08 | `uv build --out-dir /tmp/opencode/sipx-build-1.1.1-final` | pass | Built final `1.1.1` sdist and wheel outside the repo. |
| 2026-06-08 | `uv run sipx --help` | pass | Help lists raw SIP `options`, `message`, and `request` commands. |
| 2026-06-08 | `uv run sipx request --help` | pass | Shows `--from/--aor`, `-H/--header`, `-d/--data`, `--body-file`, `--include`, and examples. |
| 2026-06-08 | `uv run sipx options sip:pbx.example.com` | fail-fast expected | Exits with local missing-From error before network access. |
| 2026-06-08 | `python -m pytest tests/test_cli.py` | pass | 15 CLI tests passed after raw SIP request commands. |
| 2026-06-08 | `python -m pytest` | pass | 111 passed, 2 skipped after raw SIP request commands. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after raw SIP request commands. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing diagnostics remain; raw SIP CLI did not add a new diagnostic. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors before final build. |
| 2026-06-08 | `uv build --out-dir /tmp/opencode/sipx-build-1.2.0-final` | pass | Built final `1.2.0` sdist and wheel outside the repo. |
| 2026-06-08 | focused Digest tests | pass | `tests/test_native_sip_backend.py::test_native_sip_backend_retries_invite_with_digest_auth` and `tests/test_cli.py::test_cli_request_retries_digest_challenge` passed. |
| 2026-06-08 | real proxy `sipx call` with credentials | authenticated then declined | Retried the Digest challenge and reached `603 Declined` instead of previous `401 Unauthorized`; command secret was not persisted. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.2.0` to `1.2.1`. |
| 2026-06-08 | `uv run sipx --help` | pass | Console script works after `1.2.1` bump. |
| 2026-06-08 | `uv run sipx request --help` | pass | Help shows Digest auth flags `--username` and `--password`. |
| 2026-06-08 | `python -m pytest` | pass | 113 passed, 2 skipped after Digest retry block. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after Digest retry block. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics remain; Digest retry block did not resolve the baseline. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors before validation log update. |
| 2026-06-08 | secret/account/proxy grep | pass/no matches | Repo files do not contain the real proxy test password, account, destination, or proxy host. |
| 2026-06-08 | `uv build --out-dir /tmp/opencode/sipx-build-1.2.1-final` | pass | Built final `1.2.1` sdist and wheel outside the repo. |
| 2026-06-08 | focused stale Digest CSeq tests | pass | INVITE and raw request retries ignore stale pre-auth challenge retransmissions before accepting CSeq 2 responses. |
| 2026-06-08 | `python -m pytest` | pass | 113 passed, 2 skipped after CSeq-scoped Digest retry matching. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after CSeq-scoped Digest retry matching. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv run sipx --help` | pass | Console script still resolves after CSeq fix. |
| 2026-06-08 | `uv run sipx request --help` | pass | Request help still shows Digest auth flags. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics remain after CSeq fix; no new diagnostics remain from the test adjustment. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors after CSeq fix before state log update. |
| 2026-06-08 | `uv build --out-dir /tmp/opencode/sipx-build-1.2.1-final` | pass | Rebuilt final `1.2.1` sdist and wheel after CSeq fix. |
| 2026-06-08 | `python -m pytest tests/test_cli.py::test_cli_request_debug_sip_prints_redacted_packets tests/test_cli.py::test_cli_call_debug_sip_passes_wire_handler` | pass | Debug SIP output prints TX/RX packet markers and redacts authorization headers. |
| 2026-06-08 | `ruff check sipx/backends/native.py sipx/cli/main.py tests/test_cli.py` | pass | Focused lint for strict-mode wire event callback and CLI debug output. |
| 2026-06-08 | `ruff format --check sipx/backends/native.py sipx/cli/main.py tests/test_cli.py` | pass | Focused debug SIP files already formatted before state updates. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics remain; debug SIP changes did not add a new diagnostic. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.2.1` to `1.3.0`. |
| 2026-06-08 | `python -m pytest` | pass | 115 passed, 2 skipped after debug SIP block. |
| 2026-06-08 | `ruff check .` | pass | All lint checks passed after debug SIP block. |
| 2026-06-08 | `ruff format --check .` | pass | 70 files already formatted. |
| 2026-06-08 | `uv run sipx --help` | pass | Console script works after `1.3.0` bump. |
| 2026-06-08 | `uv run sipx request --help` | pass | Help shows `--debug-sip` for raw SIP commands. |
| 2026-06-08 | `uv run sipx call --help` | pass | Help shows `--debug-sip` for phone call command. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing diagnostics remain after final debug SIP validation. |
| 2026-06-08 | `git diff --check` | pass/no output | No whitespace errors before final build. |
| 2026-06-08 | secret/account/proxy grep | pass/no matches | Repo files do not contain the real proxy test password, account, destination, or proxy host. |
| 2026-06-08 | `uv build --out-dir /tmp/opencode/sipx-build-1.3.0-final` | pass | Built final `1.3.0` sdist and wheel outside the repo. |
| 2026-06-08 | `python -m pytest tests/test_native_softphone.py::test_native_softphone_runs_outbound_call_and_hangup tests/test_native_softphone.py::test_native_softphone_rejects_missing_sdp_answer tests/test_cli.py::test_cli_places_top_level_call` | pass | Softphone outbound call negotiates SDP, missing SDP answer fails, and CLI media flags reach config. |
| 2026-06-08 | `ruff check sipx/backends/native.py sipx/softphone/native.py sipx/cli/main.py tests/test_native_softphone.py tests/test_cli.py` | pass | Focused lint for SDP negotiation and media CLI changes. |
| 2026-06-08 | `ruff format sipx/backends/native.py tests/test_native_softphone.py` | pass | Reflowed SDP backend/test changes. |
| 2026-06-08 | `ruff format --check sipx/backends/native.py sipx/softphone/native.py sipx/cli/main.py tests/test_native_softphone.py tests/test_cli.py` | pass | Focused SDP files already formatted after reformat. |
| 2026-06-08 | `uv run ty check` | fail | 29 existing typing diagnostics remain; SDP changes did not add a new diagnostic count. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.3.0` to `1.4.0`. |
| 2026-06-08 | `python -m pytest tests/test_llm.py tests/test_examples_templates.py` | pass | Focused LLM/example tests; live LLM validation skipped unless `SIPX_LLM_API_KEY` is set. |
| 2026-06-08 | focused LLM/template lint/format | pass | `ruff check` and `ruff format --check` passed for OpenAI-compatible/template files. |
| 2026-06-08 | `uv lock` | pass | Updated lockfile project version from `1.4.0` to `1.5.0`. |
| 2026-06-08 | `uv run ty check` | fail | 29 baseline diagnostics remained before type hardening; backpropagated as B8/V33. |
| 2026-06-08 | focused type-hardening tests | pass | 34 passed across Asterisk backend, media, SDP, softphone, expectations, and recorder/profile tests. |
| 2026-06-08 | `uv run ty check` | pass | Dynamic call, mapping, URI, SDP direction, and media-frame typing diagnostics fixed. |
| 2026-06-08 | final `python -m pytest` | pass | 121 passed, 3 skipped after `1.5.0` LLM/template/type-hardening changes. |
| 2026-06-08 | final `ruff check .` | pass | All lint checks passed after `1.5.0` changes. |
| 2026-06-08 | final `ruff format --check .` | pass | 77 files already formatted after `1.5.0` changes. |
| 2026-06-08 | final `uv run ty check` | pass | Configured type-check gate passes. |
| 2026-06-08 | final `uv run sipx --help` | pass | Console script works after `1.5.0` changes. |
| 2026-06-08 | final `uv run sipx call --help` | pass | Help shows media and debug SIP flags. |
| 2026-06-08 | final `uv run sipx request --help` | pass | Help shows raw SIP auth/debug/body/header flags. |
| 2026-06-08 | final `git diff --check` | pass/no output | No whitespace errors after `1.5.0` changes. |
| 2026-06-08 | final `uv build --out-dir /tmp/opencode/sipx-build-1.5.0-final` | pass | Built final `1.5.0` sdist and wheel outside the repo. |
| 2026-06-08 | final secret-pattern scan | pass/no matches | Scanned code, tests, examples, docs, state, memory, TOML, and YAML for inline provider keys, SIP auth headers, and private proxy markers. |
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
