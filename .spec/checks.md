# Checks

## Known Commands

| Command | Purpose | Status |
| --- | --- | --- |
| `ruff format --check .` | formatting | not run yet |
| `ruff check .` | lint | not run yet |
| `ty check` | type check | not run yet |
| `pytest` | tests | not run yet |
| `pre-commit run --all-files` | full local hooks | not run yet |

## Latest Results

| Date | Command | Result | Notes |
| --- | --- | --- | --- |
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

## Validation Policy

- For docs-only edits, run `git diff --check` at minimum.
- For Python code, run the narrow test first, then `ruff check .`, `ty check`, and relevant `pytest`.
- For parser/protocol changes, add malformed and round-trip tests.
- For Asterisk integration, guard tests behind explicit env/config and never require real secrets in repo.
