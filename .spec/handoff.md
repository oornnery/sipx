# Handoff

## Summary

**4.0.0** is published on [PyPI](https://pypi.org/project/sipx/4.0.0/) (wheel + sdist). Release pipeline: push `master` → CI → `create-release.yml` publishes GitHub release → `release.yml` publishes root `sipx` to PyPI. API rename: `AuthDigest` + `Settings` (`AuthFlow`/`ClientConfig` deprecated aliases). Root `README.md` documents core `sipx` + `sipx.examples` only.

Block `3.7.0` fixed hostname response correlation (`_remote_matches`), added `cancel.py`, CLI `--no-rport`/`--no-retransmit`, FastAPI `/sip/invite` + `/sip/cancel`. P0/P1/P2 RFC hardening is complete. `AsyncClient` is the only client runtime.

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
- `AsyncClient` is the only client runtime; public API uses `AuthDigest` and `Settings`.
- `sipx-cli` owns the curl-like `sipx` console command.
- `sipx-fastapi` demonstrates REST integration with lifespan-managed `AsyncClient`.
- `sipx-harness` remains product center for Harness/Actor/Scenario/Timeline/Verdict/Artifact APIs.
- `sipx/extensions/*` holds standalone extension handlers (test-only, not wired into `AsyncClient`).

## Recommended Next Task

1. Decide license before broader public distribution.
2. Decide fate of untracked `qa_tls_scenarios.py`.
3. Optional live smoke: FastAPI app and root examples against a cooperative SIP peer.
4. Optional: SDP/RTP orchestration on `AsyncClient` for softphone-style ergonomics.

## Validation

Run before committing:

```bash
uv sync --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

## Release

Bump `pyproject.toml` version, push `master`, wait for CI, then confirm GitHub release + PyPI publish. Manual retry: Actions → **Publish Package** → `workflow_dispatch` with tag `vX.Y.Z`.
