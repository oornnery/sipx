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

## Validation Policy

- For docs-only edits, run `git diff --check` at minimum.
- For Python code, run the narrow test first, then `ruff check .`, `ty check`, and relevant `pytest`.
- For parser/protocol changes, add malformed and round-trip tests.
- For Asterisk integration, guard tests behind explicit env/config and never require real secrets in repo.
