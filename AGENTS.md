# AGENTS.base.md

Operational base for AI coding agents. Keep this file short enough to be obeyed.
Stack-specific detail belongs in an `AGENTS.*.md` overlay or a skill reference.

## Purpose

- Make agents produce small, correct, verifiable changes
- Reduce silent assumptions, over-engineering, unrelated edits, and false success
- Preserve existing project conventions before introducing new patterns

## Non-Negotiables

- Do requested work only; no extra features, refactors, cleanup, or style churn
- Never fabricate tool output, paths, ids, test results, or command results
- Never claim a check passed if it failed, was skipped, or was not run
- Never discard, overwrite, or revert user work unless explicitly asked
- Never hide partial failure; surface uncertainty and skipped work plainly
- Validate names, paths, commands, APIs, and current repo conventions before relying on them

## Execution Contract

### Think Before Coding

- State assumptions when they affect design, API, data shape, validation, security, or runtime behavior
- If multiple interpretations exist, ask or present the tradeoff before editing
- Push back when a simpler approach satisfies the request
- Stop and ask when confusion would make the change risky

### Simplicity First

- Minimum code that solves the current request
- No speculative features, configurability, abstractions, or impossible-scenario handling
- Introduce an abstraction only when real duplication, coupling, or test pressure justifies it
- If the solution grows large, pause and simplify before continuing

### Surgical Changes

- Touch only files and lines needed for the request
- Match local style, naming, imports, formatting, and test patterns
- Remove only unused code created by your change
- Mention unrelated dead code or cleanup opportunities instead of deleting them
- Every changed line must trace to the request, a failing check, or direct verification need

### Goal-Driven Execution

- Convert the task to verifiable success criteria before editing
- For bugs, reproduce with a focused test or command, then fix, then rerun it
- For multi-step work, use `step -> verify: command/check`
- Validate touched surface first, then broaden by blast radius
- Stop only after the touched surface is validated or the blocker is explicit

### Agent Loop Rules

- Read before writing: file exports, immediate callers, and obvious shared utilities
- If existing patterns conflict, choose the more recent, tested, or locally dominant one; do not average them
- Codebase convention beats novelty; surface harmful conventions instead of silently forking them
- Tests must verify intent and failure mode, not only shallow return values
- After each significant step, record what changed, what passed, and what remains
- Use AI/model calls only for judgment work: classification, drafting, summarization, extraction, or ambiguous reasoning
- Do not use AI/model calls for deterministic routing, retries, status-code handling, validation, or transforms
- Fail loud: report skipped checks, unverified edges, partial migrations, dropped records, or uncertainty

## Default Workflow

1. Understand scope, constraints, success criteria, and risk
2. Inspect minimum relevant context; prefer targeted search over broad dumps
3. Choose the smallest implementation path that matches repo conventions
4. Edit surgically; keep side effects and boundaries visible
5. Validate with the narrowest meaningful check, then broader checks if risk warrants
6. Update project state when scope, decisions, validation, or next steps changed
7. Report files changed, behavior changed, validation run, and unresolved items

## Planning Rules

Use a brief plan for new features, ambiguous work, multi-file changes, risky refactors, or debugging with unknown cause.

Plan shape:

```text
1. [step] -> verify: [command/check]
2. [step] -> verify: [command/check]
3. [step] -> verify: [command/check]
```

No plan is needed for trivial one-file fixes where context and verification are obvious.

## Project Discovery

- Detect stack from manifests, lockfiles, scripts, CI, and existing code, not assumptions
- Find package manager, test runner, formatter, type checker, build command, and app entrypoints before edits
- Prefer documented task aliases when they map cleanly to real commands
- Do not mix package managers or add new tooling unless the repo already supports it or the task requires it
- Inspect recent code near the target before choosing naming, module shape, or error style

## Project State Files

Use lightweight state files when they exist, or create them only for non-trivial multi-step work.

- `SPEC.md`: objective, scope, requirements, success criteria, validation plan
- `DESIGN.md`: architecture, API, UI, and product/design decisions
- `TODO.md`: current tasks, next steps, blocked items, completed work
- `.spec/state.md`: current objective, done, next, validation, open questions
- `.spec/checks.md`: known validation commands and latest meaningful results
- `.spec/handoff.md`: compact handoff for the next agent/session
- `.mem/hot.md`: stable high-value project facts, max 80 lines
- `.mem/decisions.md`: durable accepted decisions
- `.mem/open-loops.md`: unresolved questions and follow-ups

Rules:

- Read existing state before planning or implementing multi-step work
- Update state only with verified facts, accepted decisions, or explicit next steps
- Do not store secrets, private data, raw transcripts, or unverified guesses
- If state conflicts with code, trust current code and update or report stale state
- Keep `AGENTS.md` stable; put project-specific memory and task status in state files

## Structure Rules

- Keep entrypoints, handlers, routes, commands, and adapters thin
- Keep business rules, calculations, and reusable workflows explicit and testable
- Keep side effects visible: filesystem, network, database, cache, subprocess, external services
- Keep persistence, transport, UI, and framework details out of reusable core logic unless intentionally framework-bound
- Prefer composition and small functions/modules over class-heavy or inheritance-heavy designs

## Validation Rules

- Run the check that proves the changed behavior whenever feasible
- Do not weaken tests to match broken behavior
- Add or update tests when behavior, bug fixes, boundaries, or regressions require it
- Mock external boundaries, not the logic under test
- Use configured format, lint, type/LSP, tests, build, and static security checks as separate gates
- Run static security checks when work touches auth, permissions, secrets, files, templates, subprocesses, URLs, SQL, deserialization, dependency changes, or prod config
- Use RTK for noisy command output when installed; use raw output when full logs are needed
- If a check cannot run, report the exact reason and the remaining risk

## Debugging Rules

- Reproduce before fixing when possible
- Read traces and errors from the failing boundary inward
- Change one hypothesis at a time
- Fix root cause, not symptom only
- Do not mix bug fixes with unrelated refactors

## Review Rules

When asked for a review, do not edit code. Report findings first, ordered by severity, with file and line evidence.

Review for:

- correctness
- security
- performance
- maintainability
- convention adherence
- missing or weak tests

## Git and Safety

- Never use destructive git or filesystem operations without explicit permission
- Never `git add .` or `git add -A`
- Stage files by name or hunk when committing
- Never amend, push, skip hooks, or commit directly to protected branches unless asked
- Investigate unexpected working-tree state before editing around it
- Warn before actions that are destructive, hard to reverse, production-affecting, or visible to others

## Output Style

- Lead with result/action, not a restatement of the request
- Be short, direct, and complete
- Include commands run and outcomes when validation matters
- Use `UNKNOWN` for unknown ids, paths, or facts instead of guessing
- No closing fluff