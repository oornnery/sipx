# FORMAT

## Purpose

- `FORMAT.md` defines compact `SPEC.md` shape.
- `SPEC.md` is project contract: goals, constraints, interfaces, invariants, tasks, bug history.
- Keep entries testable, grep-able, and short.

## Style

- Use English.
- Prefer caveman compression for `SPEC.md` and spec-adjacent notes.
- Drop filler words when meaning survives.
- Preserve paths, identifiers, commands, versions, URLs, env vars, and quoted strings verbatim.
- Do not hide uncertainty; use `?` or `UNKNOWN`.
- Escape literal pipe in tables as `\|`.

## Symbols

```text
→ leads to / becomes / on
∴ therefore / because
∀ every / for all
∃ exists / some
! must / required
? optional / unknown
⊥ forbidden / never / nil
≠ not equal
∈ in
∉ not in
≤ at most
≥ at least
& and
| or
§ section reference
```

## Sections

```text
## §G  goals: product identity and top-level outcome
## §C  constraints: rules, boundaries, non-goals
## §I  interfaces: APIs, commands, packages, docs, CI surfaces
## §V  invariants: testable rules that prevent drift/bugs
## §T  tasks: executable work rows
## §B  bugs/backprops: failure memory and invariant links
```

## §G Goals

Shape:

```text
G<n>: <goal statement>
```

Rule:

- Goals describe why project exists or what product is.
- Goals are stable; do not use for implementation detail.

Example:

```text
G1: `sipx` workspace = Python Voice/SIP toolkit.
```

## §C Constraints

Shape:

```text
C<n>: <constraint statement>
```

Rule:

- Constraints define boundaries, dependencies, package ownership, and non-goals.
- Use `⊥` for forbidden behavior.

Example:

```text
C1: runtime Python `>=3.14` per `pyproject.toml`.
```

## §I Interfaces

Shape:

```text
<kind>: <name> → <shape or behavior>
```

Kinds:

```text
api, runtime, cfg, doc, cmd, ci, proto, pkg
```

Examples:

```text
api: `SipUac` → high-level outbound `register`, `unregister`, `call`.
cmd: `sipx call <uri> --audio none|silence|noise|pyaudio` → SIP call + RTP metrics.
pkg: root `sipx` → SIP protocol/runtime package only.
```

## §V Invariants

Shape:

```text
V<n>: <testable rule>
```

Rules:

- Invariant ! catch recurring bug or product drift.
- Invariant ! be assertable by tests, scans, or clear review.
- Avoid vague wording like "should be correct".
- Cite interfaces or constraints when useful.

Examples:

```text
V1: root `sipx` ⊥ export Harness, Mock, Timeline, Scenario, LLM, softphone, Asterisk, CLI, or app examples.
V2: RTP audio modes ! `none|silence|noise|pyaudio`; `silence|noise` open no media device.
```

## §T Tasks

Table shape:

```text
id|status|task|cites
---|---|---|---
T<n>|<status>|<task>|<refs>
```

Statuses:

```text
x done; verification passed
~ in progress
. todo
```

Rules:

- Task cites relevant `G`, `C`, `I`, `V`, or prior task refs.
- Mark `x` only after focused verification passes.
- Keep task text outcome-oriented, not implementation diary.

Example:

```text
T1|x|add G.711 PCMU/PCMA encode/decode without `audioop`|C11,V12
```

## §B Backprops

Table shape:

```text
id|date|cause|fix
---|---|---|---
B<n>|YYYY-MM-DD|<root cause>|<fix or V ref>
```

Rules:

- Add §B row for every meaningful failed verification or user bug.
- Add/point to §V when failure class should never recur.
- If mechanical one-off, use `no new §V` in fix.
- Cause names root cause, not just symptom.

Example:

```text
B1|2026-06-09|test mocked removed public symbol after API migration|V53
```

## Edit Rules

- Spec edits are surgical.
- Keep numbering monotonic; never reuse ids.
- Do not reorder old rows unless fixing malformed format.
- Do not persist secrets, private hosts, private accounts, phone numbers, tokens, or raw private snippets.
- Prefer current code over stale state files when conflict exists; then update state or report drift.
