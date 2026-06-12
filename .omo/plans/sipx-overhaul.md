# sipx Complete Overhaul: httpx-like SIP Library

## TL;DR

> **Quick Summary**: Transform the root `sipx` package into an httpx-like async SIP library with comprehensive RFC compliance, SOLID architecture, 90%+ test coverage, and production-ready documentation.
>
> **Deliverables**:
> - httpx-like `AsyncClient` API (replaces `SipUac`/`SipUas`)
> - Layered architecture: Transport → Protocol → API
> - RFC compliance matrix with test evidence
> - 90%+ test coverage (TDD approach)
> - Rewritten examples with new API
> - Comprehensive API documentation
>
> **Estimated Effort**: XL (Large-scale architectural overhaul)
> **Parallel Execution**: YES - 10 waves with 2-7 tasks per wave (some waves forced sequential by dependencies)
> **Critical Path (feature path)**: Task 1 → Task 5 → Task 10 → Task 14 → Task 9 → Task 12 → Task 13 → Task 15 → Task 16 → Task 17 → Task 18 → Task 19 → Task 22 → Task 23 → Task 32 → F1-F4 → user okay

---

## Context

### Original Request
User requested a complete overhaul of the sipx SIP library to make it:
- httpx-like (the library should be to SIP what httpx is to HTTP)
- RFC compliant (Core + Presence + Messaging + NAT/Security/Outbound)
- SOLID architecture (layered + plugin-based + event-driven)
- 90%+ test coverage
- Improved documentation and specs
- Balanced file sizes (not too big, not too fragmented)

### Interview Summary
**Key Discussions**:
- API Design: AsyncClient only (async-first, no sync wrapper)
- UAC/UAS: Concepts maintained internally, exposed via AsyncClient API
- RFC Scope: Core (3261, 3262, 3263, 3264, 3265, 3581) + Presence (3856 + 3858 only; 3857 out of scope) + Messaging (3428) + NAT/Security as integration hooks + RFC 5626 Outbound (full implementation)
- Architecture: Layered (Transport → Protocol → API) + Plugin-based + Event-driven
- Implementation: Parallel (API + architecture together), small incremental commits
- Examples: Rewrite from scratch with new API
- Tests: 90%+ coverage, TDD approach
- Breaking changes: Acceptable, no deprecated code
- Python: 3.14+ (matches current `requires-python`)
- Scope: Root `sipx` package primarily (app packages may be modified ONLY for API migration as specified in Task 15/32)

**Research Findings**:
- Current codebase: 34 core files, god modules (`ua.py` 1664 lines, `uac.py` 421, `uas.py` 337, `rtp/audio.py` 345)
- Barrel-heavy exports (mega `__init__.py` files)
- Duplication: `uac.py` and `uas.py` mirror each other; `sip/requests.py` and `sip/transaction.py` share helpers
- Current API: Flat namespace, async-first, event hooks awkward/overloaded
- Test coverage: 81% (90 tests), gaps in examples/ua/uac/uas, no shared fixtures
- Documentation: Strong product/spec, sparse API docstrings (212 defs vs 8 triple-quotes)
- httpx patterns: Client/AsyncClient symmetry, Request/Response first-class, Transport low-level, Auth generator-based, typed exception hierarchy

### Metis Review
**Identified Gaps** (addressed):
- First shippable milestone: Single plan with logical waves (not separate phases)
- Sync Client vs AsyncClient: AsyncClient only (SIP is event-driven)
- Media boundary: Signaling library with media abstractions/hooks (not full ICE/STUN/TURN/SRTP implementations)
- SIP multi-response model: Response object with provisional response streaming
- RFC compliance matrix: Will be created as `.spec/rfc-compliance.md`
- Use cases priority: REGISTER, INVITE, MESSAGE, SUBSCRIBE/NOTIFY
- Breaking changes: Everything can break (API, imports, examples, tests, docs)
- Python versions: 3.14+ (asyncio only)
- External dependencies: Minimal (cryptography for TLS/Digest auth, dnspython for RFC 3263 NAPTR/SRV resolution)
- Explicitly out of scope: Proxy/B2BUA, complete media stack, WebRTC, sync Client

---

## Work Objectives

### Core Objective
Transform the root `sipx` package (SIP/RTP runtime) into an httpx-like async SIP library with comprehensive RFC compliance for core signaling, SOLID architecture, 90%+ test coverage, and production-ready documentation.

### Concrete Deliverables
- `sipx.AsyncClient` class (httpx-like API)
- `sipx.Request` and `sipx.Response` first-class objects
- `sipx.Transport` pluggable interface (UDP/TCP/TLS)
- Event hooks system (pre/post interception)
- Generator-based auth flow (401/407 challenge handling)
- Typed exception hierarchy
- RFC compliance matrix (`.spec/rfc-compliance.md`)
- 90%+ test coverage with TDD approach
- Rewritten examples using new API
- Comprehensive API docstrings

### Definition of Done
- [x] `python -c "from sipx import AsyncClient, Request, Response"` exits 0
- [ ] `pytest --cov=sipx --cov-fail-under=90` exits 0
- [x] `ruff check .` exits 0
- [x] `ruff format --check .` exits 0
- [x] `uv run ty check` exits 0
- [ ] All examples in `sipx/examples/` run successfully with new API (import/`main` presence verified by `tests/test_examples.py`; live network run against Mizu demo still pending)
- [x] `.spec/rfc-compliance.md` contains MUST/SHOULD/MAY per targeted RFC with test evidence
- [x] All public API objects have docstrings

### Must Have
- httpx-like `AsyncClient` API with `invite()`, `register()`, `message()`, `subscribe()` methods
- First-class `Request` and `Response` objects
- Pluggable transport layer (UDP/TCP/TLS)
- Event hooks for request/response interception
- Generator-based auth flow for 401/407 challenges
- Typed exception hierarchy (`SipError`, `TransportError`, `TimeoutError`, etc.)
- RFC compliance for Core (3261, 3262, 3263, 3264, 3265, 3581) - **Note**: RFC 3264 basic SDP support means parsing/generating SDP, not full offer/answer negotiation logic (which is out of scope)
- RFC compliance for Presence (3856 + 3858 only; 3857 out of scope) - **Note**: RFC 3857 (watcher info) is out of scope for this overhaul
- RFC compliance for Messaging (3428)
- RFC compliance for Outbound (5626) - full implementation
- NAT/Security as integration hooks (not full implementations)
- RFC 5626 Outbound (full implementation: instance-id, reg-id, Path headers, keepalives, flow tokens)
- 90%+ test coverage
- Comprehensive API docstrings
- Rewritten examples with new API
- **RFC annotations in source files** (each RFC implementation must cite RFC section in docstring or comment)

### Must NOT Have (Guardrails)
- Sync `Client` (async-only)
- Proxy/B2BUA behavior
- Complete media stack implementation (ICE/STUN/TURN/SRTP as full protocol stacks)
- WebRTC compatibility
- Generic plugin framework (until concrete extension points are proven)
- Changes to `sipx-harness` are out of scope EXCEPT for import-only migration (same as other app packages)
- Changes to app packages (`apps/*`) are allowed ONLY when necessary for API migration (e.g., updating imports from old API to new API) to keep workspace tests/imports passing after root API removal
- Deprecated code or backward compatibility shims
- Vague acceptance criteria like "docs improved" or "RFC compliant"
- Manual SIP server setup for core CI acceptance

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION DURING EXECUTION** - ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.
> 
> **Exception**: Final Verification Wave (F1-F4) requires explicit user approval after all automated checks pass.
> This is a post-verification handoff, not part of the automated verification process.

### Test Decision
- **Infrastructure exists**: YES (pytest, pytest-asyncio, pytest-cov)
- **Automated tests**: TDD (test-first approach)
- **Framework**: pytest with pytest-asyncio
- **TDD workflow**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Library/Module**: Use Bash (python REPL) - Import, call functions, compare output
- **API/Backend**: Use Bash (curl) - Send requests, assert status + response fields (for integration tests with fake SIP server)
- **Protocol tests**: Use fake SIP peers, fake clocks, and deterministic transports

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.
> **Exception**: Waves with only 1-2 tasks are dependency-forced (e.g., Wave 1.5, 4, 5, 6a-6d, 9, 10) and cannot be parallelized further without breaking dependency chains.

```
Wave 1 (Start Immediately - foundation + scaffolding):
├── Task 1: New directory structure + core types [quick]
├── Task 2: Exception hierarchy [quick]
├── Task 3: RFC compliance matrix doc [writing]
└── Task 4: Transport interface (abstract base) [quick]

Wave 1.5 (After Tasks 1 and 4 - models):
└── Task 5: Request/Response models [quick]

Wave 2 (After Wave 1.5 - concrete transports + protocol layer + SDP parsing):
├── Task 6: UDP transport refactor (depends: 4) [unspecified-high]
├── Task 7: TCP transport implementation (depends: 4) [unspecified-high]
├── Task 10: Transaction state machines refactor (depends: 5) [deep]
├── Task 11: Dialog state machine refactor (depends: 5) [deep]
├── Task 12: Auth flow (generator-based) (depends: 5) [unspecified-high]
├── Task 13: Event hooks system (depends: 5) [quick]
└── Task 30: SDP parsing/generation (RFC 3264 basic support) (depends: 5) [unspecified-high]

Wave 3 (After Wave 2 - TLS + provisional responses + rport):
├── Task 8: TLS transport abstraction (depends: 4, 7) [unspecified-high]
├── Task 14: Provisional response streaming (depends: 5, 10) [unspecified-high]
└── Task 31: RFC 3581 rport verification/implementation (depends: 6, 7) [quick]

Wave 4 (After Wave 3 - transport registry + RFC 3262):
├── Task 9: Transport registry/factory (depends: 6, 7, 8) [quick]
└── Task 20: RFC 3262 PRACK (depends: 10, 14) [unspecified-high]

Wave 5 (After Wave 4 - AsyncClient core + RFC 3263):
├── Task 15: AsyncClient core (depends: 9, 13) [deep]
└── Task 21: RFC 3263 DNS resolution (depends: 9) [unspecified-high]

Wave 6a (After Wave 5 - UAC methods):
└── Task 16: UAC methods (invite, register, message) (depends: 15, 10, 11) [unspecified-high]

Wave 6b (After Wave 6a - UAS handlers):
└── Task 17: UAS handlers (on_invite, on_message) (depends: 16, 15, 11) [unspecified-high]

Wave 6c (After Wave 6b - config merge):
└── Task 18: Config merge (client defaults + request overrides) (depends: 17, 15) [quick]

Wave 6d (After Wave 6c - lifecycle):
└── Task 19: AsyncClient context manager + lifecycle (depends: 18, 15) [quick]

Wave 7 (After Wave 6 - RFC expansion):
├── Task 22: RFC 3265/6665 Event notification (depends: 11, 17) [unspecified-high]
├── Task 24: RFC 3428 MESSAGE (depends: 16) [unspecified-high]
└── Task 25: RFC 5626 Outbound (depends: 16, 17) [unspecified-high]

Wave 8 (After Wave 7 - presence + examples):
├── Task 23: RFC 3856 + 3858 Presence (depends: 22) [unspecified-high]
├── Task 27: Examples rewrite (register, invite, message, subscribe) (depends: 15-19) [unspecified-high]
└── Task 29: Migration guide (old API → new API) (depends: 15-19) [writing]

Wave 9 (After Wave 8 - docstrings + RFC compliance matrix update):
├── Task 26: API docstrings (all public objects) (depends: 15-19, 23) [writing]
└── Task 28: RFC compliance matrix update (with test evidence) (depends: 20-25, 30, 31, 23) [writing]

Wave 10 (After Wave 9 - cleanup):
└── Task 32: Delete old API files and migrate remaining imports (depends: 16, 17, 18, 19) [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── F1. Plan compliance audit (oracle)
├── F2. Code quality review (unspecified-high)
├── F3. Real manual QA (unspecified-high)
└── F4. Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path (feature path): Task 1 → Task 5 → Task 10 → Task 14 → Task 9 → Task 12 → Task 13 → Task 15 → Task 16 → Task 17 → Task 18 → Task 19 → Task 22 → Task 23 → Task 32 → F1-F4 → user okay
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 7 (Wave 2)
```

### Dependency Matrix (full)

| Task | Depends on | Blocks | Wave |
|------|------------|--------|------|
| 1 | - | 5 | 1 |
| 2 | - | 10, 11, 12, 13, 14, 30 | 1 |
| 3 | - | 28 | 1 |
| 4 | - | 5, 6, 7, 8 | 1 |
| 5 | 1, 4 | 10, 11, 12, 13, 14 | 1.5 |
| 6 | 4 | 9 | 2 |
| 7 | 4 | 8, 9 | 2 |
| 8 | 4, 7 | 9 | 3 |
| 9 | 6, 7, 8 | 15, 21 | 4 |
| 10 | 5 | 14, 16, 20 | 2 |
| 11 | 5 | 16, 17, 22 | 2 |
| 12 | 5, 2 | 15 | 2 |
| 13 | 5 | 15 | 2 |
| 14 | 5, 10 | 20 | 3 |
| 15 | 9, 12, 13 | 16, 17, 18, 19, 26, 27, 29 | 5 |
| 16 | 15, 10, 11 | 24, 25 | 6a |
| 17 | 15, 16, 11 | 18, 22, 25 | 6b |
| 18 | 15, 17 | 26, 27, 29 | 6c |
| 19 | 15, 18 | 26, 27, 29, 32 | 6d |
| 20 | 10, 14 | 28 | 4 |
| 21 | 9 | 28 | 5 |
| 22 | 11, 17 | 23, 28 | 7 |
| 23 | 22 | 28 | 8 |
| 24 | 16 | 28 | 7 |
| 25 | 16, 17 | 28 | 7 |
| 26 | 15, 18, 19, 23 | F1-F4 | 9 |
| 27 | 15, 18, 19 | F1-F4 | 8 |
| 28 | 20, 21, 22, 23, 24, 25, 30, 31 | F1-F4 | 9 |
| 29 | 15, 18, 19 | F1-F4 | 8 |
| 30 | 5, 2 | 28 | 2 |
| 31 | 6, 7 | 28 | 3 |
| 32 | 16, 17, 18, 19, 26, 27, 28, 29 | F1-F4 | 10 |

### Agent Dispatch Summary

- **1**: **4** - T1-T4 → `quick`
- **1.5**: **1** - T5 → `quick`
- **2**: **7** - T6-T7 → `unspecified-high`, T10-T11 → `deep`, T12 → `unspecified-high`, T13 → `quick`, T30 → `unspecified-high`
- **3**: **3** - T8 → `unspecified-high`, T14 → `unspecified-high`, T31 → `quick`
- **4**: **2** - T9 → `quick`, T20 → `unspecified-high`
- **5**: **2** - T15 → `deep`, T21 → `unspecified-high`
- **6a-6d**: **4** - T16-T17 → `unspecified-high`, T18-T19 → `quick` (sequential execution)
- **7**: **3** - T22 → `unspecified-high`, T24-T25 → `unspecified-high`
- **8**: **3** - T23 → `unspecified-high`, T27 → `unspecified-high`, T29 → `writing`
- **9**: **2** - T26 → `writing`, T28 → `writing`
- **10**: **1** - T32 → `quick`
- **FINAL**: **4** - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**
> **FORMAT**: Task labels MUST use bare numbers: `1.`, `2.`, `3.` — NOT `T1.`, `Task 1.`, `Phase 1:`.
> The /start-work progress counter requires exact format. Deviation = progress shows 0/0.
> Final Verification Wave labels MUST use `F1.`, `F2.`, etc. — NOT `T-F1.`, `F-1.`, `Final 1.`.

- [x] 1. New directory structure + core types

  **What to do**:
  - Create new directory structure: `sipx/transport/`, `sipx/protocol/`, `sipx/rfc/`, `sipx/types.py`
  - Define core type aliases in `sipx/types.py`: `SipMethod`, `StatusCode`, `HeaderName`, `HeaderValue`, `Uri`
  - Create `sipx/transport/__init__.py`, `sipx/protocol/__init__.py`, `sipx/rfc/__init__.py` (empty barrels for now)
  - Update `sipx/__init__.py` to export new types (but keep old API for now)
  - Write tests for type definitions in `tests/test_types.py`

  **Must NOT do**:
  - Do NOT move or refactor existing code yet (only add new structure in parallel)
  - Do NOT remove old API yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT create generic plugin framework

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (simple scaffolding)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5 (needs directory structure)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sipx/__init__.py` - Current barrel exports (pattern to follow)
  - `pyproject.toml` - Python 3.14+ requirement
  - httpx `_types.py` - Type alias pattern (e.g., `HeaderTypes = Union[...]`)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_types.py`
  - [ ] `pytest tests/test_types.py` → PASS (3 tests, 0 failures)
  - [ ] `python -c "from sipx.types import SipMethod, StatusCode, Uri"` → exit 0
  - [ ] `ruff check sipx/types.py sipx/transport/ sipx/protocol/ sipx/rfc/` → exit 0
  - [ ] Directory structure exists: `sipx/transport/`, `sipx/protocol/`, `sipx/rfc/`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import core types
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.types import SipMethod, StatusCode, HeaderName, HeaderValue, Uri; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: All types importable
    Evidence: .omo/evidence/task-1-import-types.txt

  Scenario: Type aliases are correct
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.types import SipMethod; assert SipMethod == str; print('SipMethod is str')"
      2. Assert: exit code 0, stdout contains "SipMethod is str"
    Expected Result: Type aliases resolve to expected types
    Evidence: .omo/evidence/task-1-type-aliases.txt
  ```

  **Commit**: YES
  - Message: `feat(core): add new directory structure and core type aliases`
  - Files: `sipx/types.py`, `sipx/transport/__init__.py`, `sipx/protocol/__init__.py`, `sipx/rfc/__init__.py`, `tests/test_types.py`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: `pytest tests/test_types.py && ruff check sipx/types.py`
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

- [x] 2. Exception hierarchy

  **What to do**:
  - Create `sipx/exceptions.py` with typed exception hierarchy:
    - `SipError` (base exception)
    - `TransportError` (network/transport failures)
    - `TimeoutError` (transaction timeouts)
    - `ProtocolError` (malformed SIP messages)
    - `AuthError` (authentication failures)
    - `DialogError` (dialog state violations)
    - `TransactionError` (transaction state violations)
  - Each exception should have structured attributes: `message`, `details` (optional dict), `rfc_ref` (optional RFC citation)
  - Write tests in `tests/test_exceptions.py` covering all exception types and attributes

  **Must NOT do**:
  - Do NOT replace existing exceptions yet (keep `SipCallError`, `SipRegisterError` for now)
  - Do NOT add excessive exception subclasses (keep hierarchy flat and focused)
  - Do NOT add exception chaining logic yet (that's for later waves)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (simple exception definitions)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 10, 11, 12, 13, 14, 30 (protocol layer needs exceptions)
  - **Blocked By**: None (can start immediately)

  **References**:
  - httpx `_exceptions.py` - Exception hierarchy pattern (e.g., `HTTPError` → `RequestError` → `TransportError`)
  - `sipx/ua.py:SipCallError` - Current exception pattern (to understand what exists)
  - `sipx/sip/transaction.py:SipTransactionError` - Current transaction exception

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_exceptions.py`
  - [ ] `pytest tests/test_exceptions.py` → PASS (7 tests, 0 failures)
  - [ ] `python -c "from sipx.exceptions import SipError, TransportError, TimeoutError"` → exit 0
  - [ ] All exceptions inherit from `SipError`
  - [ ] All exceptions have `message`, `details`, `rfc_ref` attributes

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import exception hierarchy
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.exceptions import SipError, TransportError, TimeoutError, ProtocolError, AuthError, DialogError, TransactionError; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: All exceptions importable
    Evidence: .omo/evidence/task-2-import-exceptions.txt

  Scenario: Exception attributes work correctly
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.exceptions import TransportError; e = TransportError('timeout', details={'host': 'example.com'}, rfc_ref='RFC 3261 §17.1.1'); assert e.message == 'timeout'; assert e.details == {'host': 'example.com'}; assert e.rfc_ref == 'RFC 3261 §17.1.1'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Exception attributes accessible and correct
    Evidence: .omo/evidence/task-2-exception-attributes.txt

  Scenario: Exception hierarchy is correct
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.exceptions import SipError, TransportError; assert issubclass(TransportError, SipError); print('TransportError is subclass of SipError')"
      2. Assert: exit code 0, stdout contains "TransportError is subclass of SipError"
    Expected Result: Inheritance hierarchy correct
    Evidence: .omo/evidence/task-2-exception-hierarchy.txt
  ```

  **Commit**: YES
  - Message: `feat(core): add typed exception hierarchy for SIP errors`
  - Files: `sipx/exceptions.py`, `tests/test_exceptions.py`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: `pytest tests/test_exceptions.py && ruff check sipx/exceptions.py`
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

- [x] 3. RFC compliance matrix doc

  **What to do**:
  - Create `.spec/rfc-compliance.md` with compliance matrix for all targeted RFCs:
    - RFC 3261 (SIP core)
    - RFC 3262 (PRACK)
    - RFC 3263 (DNS)
    - RFC 3264 (SDP offer/answer)
    - RFC 3265 (Event notification)
    - RFC 3581 (rport)
    - RFC 3856 (Presence)
    - RFC 3858 (Presence Information Data Format)
    - RFC 3428 (MESSAGE)
    - RFC 5626 (Outbound)
  - For each RFC, create a table with columns: Requirement | MUST/SHOULD/MAY | Status (Implemented/Partial/Planned) | Test Evidence
  - Start with "Planned" status for all requirements (will be updated as tasks complete)
  - Include RFC citations (links to RFC documents)

  **Must NOT do**:
  - Do NOT claim "full compliance" without test evidence
  - Do NOT skip any targeted RFC
  - Do NOT add implementation details (this is a planning doc)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none (documentation task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 28 (final compliance matrix update)
  - **Blocked By**: None (can start immediately)

  **References**:
  - Research findings from `bg_bfcc0c77` - RFC compliance checklist with MUST/SHOULD per RFC
  - `SPEC.md` - Current RFC references in spec
  - RFC 3261, 3262, 3263, 3264, 3265, 3581, 3856, 3858, 3428, 5626 - Official RFC documents

  **Acceptance Criteria**:
  - [ ] File created: `.spec/rfc-compliance.md`
  - [ ] All 10 targeted RFCs present in matrix
  - [ ] Each RFC has table with Requirement | MUST/SHOULD/MAY | Status | Test Evidence columns
  - [ ] All requirements start with "Planned" status
  - [ ] RFC citations included (links to RFC docs)
  - [ ] `ruff format --check .spec/rfc-compliance.md` → exit 0 (if markdown formatter configured)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: RFC compliance matrix file exists and is valid
    Tool: Bash (file check)
    Steps:
      1. Run: test -f .spec/rfc-compliance.md && echo "File exists"
      2. Assert: stdout contains "File exists"
      3. Run: grep -c "RFC 3261" .spec/rfc-compliance.md
      4. Assert: count > 0 (RFC 3261 mentioned)
      5. Run: grep -c "RFC 3581" .spec/rfc-compliance.md
      6. Assert: count > 0 (RFC 3581 mentioned)
    Expected Result: File exists and contains all targeted RFCs
    Evidence: .omo/evidence/task-3-rfc-matrix-exists.txt

  Scenario: RFC matrix has correct table structure
    Tool: Bash (grep check)
    Steps:
      1. Run: grep -c "| Requirement |" .spec/rfc-compliance.md
      2. Assert: count >= 10 (one table per RFC)
      3. Run: grep -c "| MUST/SHOULD/MAY |" .spec/rfc-compliance.md
      4. Assert: count >= 10 (one table per RFC)
    Expected Result: Each RFC has properly formatted table
    Evidence: .omo/evidence/task-3-rfc-matrix-structure.txt
  ```

  **Commit**: YES
  - Message: `docs(rfc): add RFC compliance matrix with targeted RFCs`
  - Files: `.spec/rfc-compliance.md`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: none (documentation only)
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

- [x] 4. Transport interface (abstract base)

  **What to do**:
  - Create `sipx/transport/base.py` with abstract `Transport` class:
    - `send(data: bytes, remote: tuple[str, int]) -> None` (async)
    - `receive() -> AsyncIterator[tuple[bytes, tuple[str, int]]]` (async generator)
    - `close() -> None` (async)
    - `local_address: tuple[str, int]` (property)
    - `transport_type: Literal["udp", "tcp", "tls"]` (property)
  - Define `TransportConfig` dataclass with common config: `local_host`, `local_port`, `timeout`, `max_message_size`
  - Write tests in `tests/test_transport_base.py` using a mock transport implementation

  **Must NOT do**:
  - Do NOT implement concrete transports yet (UDP/TCP/TLS are separate tasks)
  - Do NOT add connection pooling or retry logic (that's for concrete transports)
  - Do NOT add TLS/certificate handling (that's for TLS transport)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (abstract interface definition)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Tasks 5, 6, 7, 8 (concrete transports implement this interface)
  - **Blocked By**: None (can start immediately)

  **References**:
  - httpx `_transports/base.py` - Transport interface pattern (`handle_request`, `handle_async_request`)
  - `sipx/sip/transport.py:SipUdpEndpoint` - Current UDP transport (to understand what exists)
  - Python `abc.ABC` and `abc.abstractmethod` - Abstract base class pattern

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_transport_base.py`
  - [ ] `pytest tests/test_transport_base.py` → PASS (5 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.base import Transport, TransportConfig"` → exit 0
  - [ ] `Transport` is abstract (cannot instantiate directly)
  - [ ] All methods are async
  - [ ] `TransportConfig` is a dataclass with expected fields

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import transport interface
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.base import Transport, TransportConfig; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Transport interface importable
    Evidence: .omo/evidence/task-4-import-transport.txt

  Scenario: Transport is abstract
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.base import Transport; t = Transport(); print('ERROR: should not instantiate')" 2>&1
      2. Assert: exit code != 0, stderr contains "TypeError" or "abstract"
    Expected Result: Cannot instantiate abstract Transport
    Evidence: .omo/evidence/task-4-transport-abstract.txt

  Scenario: TransportConfig is dataclass
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.base import TransportConfig; c = TransportConfig(local_host='0.0.0.0', local_port=5060); assert c.local_host == '0.0.0.0'; assert c.local_port == 5060; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TransportConfig works as dataclass
    Evidence: .omo/evidence/task-4-transport-config.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): add abstract Transport interface and TransportConfig`
  - Files: `sipx/transport/base.py`, `tests/test_transport_base.py`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: `pytest tests/test_transport_base.py && ruff check sipx/transport/base.py`
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

- [x] 5. Request/Response models

  **What to do**:
  - Create `sipx/models.py` with first-class `Request` and `Response` classes:
    - `Request`: `method: SipMethod`, `uri: Uri`, `headers: dict[HeaderName, HeaderValue]`, `body: bytes | None`, `transport: Transport | None`
    - `Response`: `status_code: StatusCode`, `reason: str`, `headers: dict[HeaderName, HeaderValue]`, `body: bytes | None`, `request: Request | None`
  - Create `sipx/config.py` with `ClientConfig` dataclass:
    - `transport: str = "udp"` - default transport protocol (matches existing sipx behavior)
    - `local_host: str = "0.0.0.0"` - default local bind address (matches existing sipx behavior)
    - `local_port: int = 0` - default local port (0 = auto-assign, matches existing sipx behavior)
    - `timeout: float = 30.0` - default timeout in seconds (matches existing sipx behavior)
    - `max_message_size: int = 65535` - max SIP message size (matches existing sipx behavior)
    - `user_agent: str = "sipx/2.0"` - User-Agent header value (new httpx-like API)
    - `from_uri: str | None = None` - default From URI (optional, can be overridden per-request)
    - `contact_uri: str | None = None` - default Contact URI (optional, can be overridden per-request)
  - Add helper methods:
    - `Request.build(method, uri, **headers) -> Request` (builder pattern)
    - `Response.from_request(request, status_code, reason, **headers) -> Response`
  - Write tests in `tests/test_models.py` covering construction, serialization, and helper methods
  - Write tests in `tests/test_config.py` covering config creation

  **Must NOT do**:
  - Do NOT remove old `SipRequest`/`SipResponse` yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT add SIP-specific parsing logic (that's for protocol layer)
  - Do NOT add streaming or async iteration (that's for later waves)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (data model definitions)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1.5 (after Tasks 1 and 4)
  - **Blocks**: Tasks 10, 11, 12, 13, 14 (protocol layer uses Request/Response)
  - **Blocked By**: Task 1 (needs type aliases), Task 4 (needs Transport type)

  **References**:
  - httpx `_models.py` - Request/Response pattern (e.g., `Request(method, url, headers, content)`)
  - `sipx/sip/message.py:SipRequest` - Current SIP request model (to understand what exists)
  - `sipx/sip/message.py:SipResponse` - Current SIP response model

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_models.py`
  - [ ] Test file created: `tests/test_config.py`
  - [ ] `pytest tests/test_models.py` → PASS (8 tests, 0 failures)
  - [ ] `pytest tests/test_config.py` → PASS (5 tests, 0 failures)
  - [ ] `python -c "from sipx.models import Request, Response"` → exit 0
  - [ ] `python -c "from sipx.config import ClientConfig"` → exit 0
  - [ ] `Request` and `Response` are dataclasses
  - [ ] `ClientConfig` is a dataclass with expected fields
  - [ ] Helper methods work correctly
  - [ ] All attributes are type-annotated

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import Request/Response models
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.models import Request, Response; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Models importable
    Evidence: .omo/evidence/task-5-import-models.txt

  Scenario: Import ClientConfig
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.config import ClientConfig; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: ClientConfig importable
    Evidence: .omo/evidence/task-5-import-config.txt

  Scenario: Request construction works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.models import Request; r = Request(method='INVITE', uri='sip:bob@example.com', headers={'From': 'alice'}, body=None); assert r.method == 'INVITE'; assert r.uri == 'sip:bob@example.com'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Request construction works
    Evidence: .omo/evidence/task-5-request-construction.txt

  Scenario: Response.from_request helper works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.models import Request, Response; req = Request(method='INVITE', uri='sip:bob@example.com', headers={}, body=None); resp = Response.from_request(req, 200, 'OK', headers={'To': 'bob'}); assert resp.status_code == 200; assert resp.request == req; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Response.from_request helper works
    Evidence: .omo/evidence/task-5-response-helper.txt
  ```

  **Commit**: YES
  - Message: `feat(core): add first-class Request/Response models and ClientConfig`
  - Files: `sipx/models.py`, `sipx/config.py`, `tests/test_models.py`, `tests/test_config.py`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: `pytest tests/test_models.py tests/test_config.py && ruff check sipx/models.py sipx/config.py`
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

- [x] 6. UDP transport refactor

  **What to do**:
  - Create `sipx/transport/udp.py` with `UdpTransport` class implementing `Transport` interface:
    - Refactor existing `SipUdpEndpoint` logic from `sipx/sip/transport.py`
    - Implement `send()`, `receive()`, `close()`, `local_address`, `transport_type`
    - Use `asyncio.DatagramTransport` and `asyncio.DatagramProtocol`
    - Add proper error handling with new exception hierarchy (`TransportError`)
  - Write tests in `tests/test_transport_udp.py` using fake UDP sockets

  **Must NOT do**:
  - Do NOT modify existing `sipx/sip/transport.py` yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT add connection pooling or retry logic (UDP is connectionless)
  - Do NOT add NAT traversal logic (that's for RFC 5626 Outbound task)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (transport implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 10, 11, 12, 13, 30)
  - **Blocks**: Task 9 (registry needs concrete transports)
  - **Blocked By**: Task 4 (needs Transport interface)

  **References**:
  - `sipx/sip/transport.py:SipUdpEndpoint` - Current UDP implementation (refactor source)
  - `sipx/transport/base.py:Transport` - Abstract interface to implement
  - Python `asyncio.DatagramTransport` - Asyncio UDP transport API
  - RFC 3261 §18.1 - SIP transport layer requirements

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_transport_udp.py`
  - [ ] `pytest tests/test_transport_udp.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.udp import UdpTransport"` → exit 0
  - [ ] `UdpTransport` implements all `Transport` methods
  - [ ] `transport_type` returns `"udp"`
  - [ ] Proper error handling with `TransportError`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import UdpTransport
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: UdpTransport importable
    Evidence: .omo/evidence/task-6-import-udp.txt

  Scenario: UdpTransport implements Transport interface
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; from sipx.transport.base import Transport; assert issubclass(UdpTransport, Transport); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: UdpTransport is subclass of Transport
    Evidence: .omo/evidence/task-6-udp-implements-transport.txt

  Scenario: UdpTransport transport_type is correct
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; from sipx.transport.base import TransportConfig; config = TransportConfig(local_host='127.0.0.1', local_port=0); t = UdpTransport(config); assert t.transport_type == 'udp'; print('OK')" 2>&1
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: transport_type returns "udp"
    Evidence: .omo/evidence/task-6-udp-transport-type.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): implement UdpTransport with asyncio.DatagramTransport`
  - Files: `sipx/transport/udp.py`, `tests/test_transport_udp.py`
  - Pre-commit: `pytest tests/test_transport_udp.py && ruff check sipx/transport/udp.py`

- [x] 7. TCP transport implementation

  **What to do**:
  - Create `sipx/transport/tcp.py` with `TcpTransport` class implementing `Transport` interface:
    - Implement `send()`, `receive()`, `close()`, `local_address`, `transport_type`
    - Use `asyncio.StreamReader` and `asyncio.StreamWriter`
    - Add connection management (connect, reconnect, connection state)
    - Implement SIP message framing (Content-Length-based)
    - Add proper error handling with `TransportError`
  - Write tests in `tests/test_transport_tcp.py` using fake TCP connections

  **Must NOT do**:
  - Do NOT add TLS support yet (that's for TLS transport task)
  - Do NOT add connection pooling (that's for transport registry)
  - Do NOT add retry logic (that's for client layer)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (transport implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 10, 11, 12, 13, 30)
  - **Blocks**: Task 8 (TLS transport needs TCP), Task 9 (registry needs concrete transports)
  - **Blocked By**: Task 4 (needs Transport interface)

  **References**:
  - `sipx/transport/base.py:Transport` - Abstract interface to implement
  - Python `asyncio.StreamReader`/`asyncio.StreamWriter` - Asyncio TCP API
  - RFC 3261 §18.3 - TCP transport requirements
  - RFC 4168 - SIP over TCP best practices

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_transport_tcp.py`
  - [ ] `pytest tests/test_transport_tcp.py` → PASS (12 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.tcp import TcpTransport"` → exit 0
  - [ ] `TcpTransport` implements all `Transport` methods
  - [ ] `transport_type` returns `"tcp"`
  - [ ] Connection management works (connect, send, receive, close)
  - [ ] SIP message framing works (Content-Length-based)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import TcpTransport
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tcp import TcpTransport; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TcpTransport importable
    Evidence: .omo/evidence/task-7-import-tcp.txt

  Scenario: TcpTransport implements Transport interface
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tcp import TcpTransport; from sipx.transport.base import Transport; assert issubclass(TcpTransport, Transport); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TcpTransport is subclass of Transport
    Evidence: .omo/evidence/task-7-tcp-implements-transport.txt

  Scenario: TcpTransport transport_type is correct
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tcp import TcpTransport; from sipx.transport.base import TransportConfig; config = TransportConfig(local_host='127.0.0.1', local_port=0); t = TcpTransport(config); assert t.transport_type == 'tcp'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: transport_type returns "tcp"
    Evidence: .omo/evidence/task-7-tcp-transport-type.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): implement TcpTransport with asyncio streams`
  - Files: `sipx/transport/tcp.py`, `tests/test_transport_tcp.py`
  - Pre-commit: `pytest tests/test_transport_tcp.py && ruff check sipx/transport/tcp.py`

- [x] 8. TLS transport abstraction

  **What to do**:
  - Create `sipx/transport/tls.py` with `TlsTransport` class implementing `Transport` interface:
    - Extend `TcpTransport` with TLS support
    - Add `TlsConfig` dataclass: `certfile`, `keyfile`, `ca_certs`, `verify_mode`, `check_hostname`
    - Use `ssl.SSLContext` for TLS configuration
    - Implement certificate validation and hostname checking
    - Add proper error handling with `TransportError` for TLS failures
  - Write tests in `tests/test_transport_tls.py` using fake TLS connections

  **Must NOT do**:
  - Do NOT implement full certificate management (that's out of scope)
  - Do NOT add client certificate authentication (that's for later if needed)
  - Do NOT implement DTLS (that's for SRTP, out of scope)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (transport implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 14, 31)
  - **Blocks**: Task 9 (registry needs TLS transport)
  - **Blocked By**: Task 4 (needs Transport interface), Task 7 (extends TcpTransport)

  **References**:
  - `sipx/transport/tcp.py:TcpTransport` - Base class to extend
  - `sipx/transport/base.py:Transport` - Abstract interface to implement
  - Python `ssl.SSLContext` - TLS configuration API
  - RFC 3261 §26.2 - SIPS URI scheme and TLS requirements
  - RFC 5922 - SIP domain certificate validation

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_transport_tls.py`
  - [ ] `pytest tests/test_transport_tls.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.tls import TlsTransport, TlsConfig"` → exit 0
  - [ ] `TlsTransport` implements all `Transport` methods
  - [ ] `transport_type` returns `"tls"`
  - [ ] `TlsConfig` is a dataclass with expected fields
  - [ ] Certificate validation works (with fake certs in tests)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import TlsTransport and TlsConfig
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tls import TlsTransport, TlsConfig; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TlsTransport and TlsConfig importable
    Evidence: .omo/evidence/task-8-import-tls.txt

  Scenario: TlsTransport implements Transport interface
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tls import TlsTransport; from sipx.transport.base import Transport; assert issubclass(TlsTransport, Transport); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TlsTransport is subclass of Transport
    Evidence: .omo/evidence/task-8-tls-implements-transport.txt

  Scenario: TlsConfig is dataclass
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.tls import TlsConfig; c = TlsConfig(certfile=None, keyfile=None, ca_certs=None, verify_mode=True, check_hostname=True); assert c.verify_mode == True; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: TlsConfig works as dataclass
    Evidence: .omo/evidence/task-8-tls-config.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): implement TlsTransport with ssl.SSLContext`
  - Files: `sipx/transport/tls.py`, `tests/test_transport_tls.py`
  - Pre-commit: `pytest tests/test_transport_tls.py && ruff check sipx/transport/tls.py`

- [x] 9. Transport registry/factory

  **What to do**:
  - Create `sipx/transport/registry.py` with `TransportRegistry` class:
    - `register(transport_type: str, transport_class: type[Transport]) -> None`
    - `create(transport_type: str, config: TransportConfig) -> Transport`
    - `get_supported_types() -> list[str]`
  - Register default transports: `"udp"` → `UdpTransport`, `"tcp"` → `TcpTransport`, `"tls"` → `TlsTransport`
  - Add factory function: `create_transport(transport_type: str, config: TransportConfig) -> Transport`
  - Write tests in `tests/test_transport_registry.py`

  **Must NOT do**:
  - Do NOT add plugin loading or dynamic discovery (keep it simple)
  - Do NOT add transport pooling or lifecycle management (that's for client layer)
  - Do NOT add transport selection logic (that's for DNS resolution task)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (simple factory pattern)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (sequential after Wave 3)
  - **Blocks**: Task 15 (AsyncClient needs transport registry), Task 21 (DNS resolution needs registry)
  - **Blocked By**: Task 6 (needs UdpTransport), Task 7 (needs TcpTransport), Task 8 (needs TlsTransport)

  **References**:
  - `sipx/transport/udp.py:UdpTransport` - UDP transport to register
  - `sipx/transport/tcp.py:TcpTransport` - TCP transport to register
  - `sipx/transport/tls.py:TlsTransport` - TLS transport to register
  - `sipx/transport/base.py:Transport` - Transport interface

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_transport_registry.py`
  - [ ] `pytest tests/test_transport_registry.py` → PASS (8 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.registry import TransportRegistry, create_transport"` → exit 0
  - [ ] Default transports registered: `"udp"`, `"tcp"`, `"tls"`
  - [ ] `create_transport("udp", config)` returns `UdpTransport` instance
  - [ ] `get_supported_types()` returns `["udp", "tcp", "tls"]`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import transport registry
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.registry import TransportRegistry, create_transport; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Transport registry importable
    Evidence: .omo/evidence/task-9-import-registry.txt

  Scenario: Default transports are registered
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.registry import TransportRegistry; registry = TransportRegistry(); types = registry.get_supported_types(); assert 'udp' in types; assert 'tcp' in types; assert 'tls' in types; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: All default transports registered
    Evidence: .omo/evidence/task-9-default-transports.txt

  Scenario: create_transport factory works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.registry import create_transport; from sipx.transport.base import TransportConfig; from sipx.transport.udp import UdpTransport; config = TransportConfig(local_host='127.0.0.1', local_port=0); t = create_transport('udp', config); assert isinstance(t, UdpTransport); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Factory creates correct transport instance
    Evidence: .omo/evidence/task-9-factory-creates-transport.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): add TransportRegistry and create_transport factory`
  - Files: `sipx/transport/registry.py`, `tests/test_transport_registry.py`
  - Pre-commit: `pytest tests/test_transport_registry.py && ruff check sipx/transport/registry.py`

- [x] 10. Transaction state machines refactor

  **What to do**:
  - Create `sipx/protocol/transaction.py` with refactored transaction state machines:
    - `ClientTransaction` (base class for INVITE and non-INVITE client transactions)
    - `ServerTransaction` (base class for INVITE and non-INVITE server transactions)
    - Refactor existing `InviteClientTransaction`, `NonInviteClientTransaction`, `InviteServerTransaction` from `sipx/sip/transaction.py`
    - Use new `Request`/`Response` models from `sipx/models.py`
    - Use new exception hierarchy from `sipx/exceptions.py`
    - Add proper state transitions with `TransactionError` on invalid transitions
  - Write tests in `tests/test_protocol_transaction.py` covering all state transitions

  **Must NOT do**:
  - Do NOT modify existing `sipx/sip/transaction.py` yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT add dialog management (that's for dialog state machine task)
  - Do NOT add transport layer logic (that's for transport layer)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: none (complex state machine refactor)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 11, 12, 13)
  - **Blocks**: Task 14 (provisional streaming needs transactions), Task 16 (UAC methods need transactions), Task 20 (PRACK needs transactions)
  - **Blocked By**: Task 5 (needs Request/Response models)

  **References**:
  - `sipx/sip/transaction.py` - Current transaction implementation (refactor source)
  - `sipx/models.py:Request`, `sipx/models.py:Response` - New models to use
  - `sipx/exceptions.py:TransactionError` - New exception to use
  - RFC 3261 §17 - Transactions (client and server, INVITE and non-INVITE)
  - RFC 6026 - Transaction processing updates

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_protocol_transaction.py`
  - [ ] `pytest tests/test_protocol_transaction.py` → PASS (20 tests, 0 failures)
  - [ ] `python -c "from sipx.protocol.transaction import ClientTransaction, ServerTransaction"` → exit 0
  - [ ] All state transitions work correctly (Calling → Proceeding → Completed → Terminated)
  - [ ] Invalid transitions raise `TransactionError`
  - [ ] Timers work correctly (Timer A, B, D, E, F, G, H, I, J, K)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import transaction state machines
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.transaction import ClientTransaction, ServerTransaction; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Transaction classes importable
    Evidence: .omo/evidence/task-10-import-transactions.txt

  Scenario: Client transaction state transitions work
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.transaction import ClientTransaction; from sipx.models import Request; req = Request(method='INVITE', uri='sip:bob@example.com', headers={}, body=None); t = ClientTransaction(req); assert t.state == 'Calling'; t.receive_response(100, 'Trying', {}, None); assert t.state == 'Proceeding'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: State transitions work correctly
    Evidence: .omo/evidence/task-10-transaction-states.txt

  Scenario: Invalid state transition raises TransactionError
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.protocol.transaction import ClientTransaction
from sipx.models import Request
from sipx.exceptions import TransactionError

req = Request(method='INVITE', uri='sip:bob@example.com', headers={}, body=None)
t = ClientTransaction(req)
t.receive_response(200, 'OK', {}, None)
assert t.state == 'Terminated', f"Expected 'Terminated', got {t.state}"

try:
    t.receive_response(180, 'Ringing', {}, None)
    print('ERROR: should raise TransactionError')
except TransactionError:
    print('OK')
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Invalid transition raises TransactionError
    Evidence: .omo/evidence/task-10-transaction-invalid-transition.txt
  ```

  **Commit**: YES
  - Message: `feat(protocol): refactor transaction state machines with new models`
  - Files: `sipx/protocol/transaction.py`, `tests/test_protocol_transaction.py`
  - Pre-commit: `pytest tests/test_protocol_transaction.py && ruff check sipx/protocol/transaction.py`

- [x] 11. Dialog state machine refactor

  **What to do**:
  - Create `sipx/protocol/dialog.py` with refactored dialog state machine:
    - Refactor existing `Dialog` class from `sipx/sip/dialog.py`
    - Use new `Request`/`Response` models from `sipx/models.py`
    - Use new exception hierarchy from `sipx/exceptions.py`
    - Add proper state transitions with `DialogError` on invalid transitions
    - Implement dialog matching rules (RFC 3261 §12.2)
    - Add route set management (Record-Route, Route headers)
  - Write tests in `tests/test_protocol_dialog.py` covering all state transitions and dialog matching

  **Must NOT do**:
  - Do NOT modify existing `sipx/sip/dialog.py` yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT add transaction management (that's for transaction state machines)
  - Do NOT add session timers (that's for RFC 4028, out of scope)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: none (complex state machine refactor)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 10, 12, 13)
  - **Blocks**: Tasks 16, 17, 22 (UAC/UAS methods, event notification need dialogs)
  - **Blocked By**: Task 5 (needs Request/Response models)

  **References**:
  - `sipx/sip/dialog.py` - Current dialog implementation (refactor source)
  - `sipx/models.py:Request`, `sipx/models.py:Response` - New models to use
  - `sipx/exceptions.py:DialogError` - New exception to use
  - RFC 3261 §12 - Dialogs (creation, state, route set, target refresh)
  - RFC 4028 - Session Timers (for future reference, not implementing now)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_protocol_dialog.py`
  - [ ] `pytest tests/test_protocol_dialog.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx.protocol.dialog import Dialog"` → exit 0
  - [ ] Dialog creation works (from INVITE request/response)
  - [ ] Dialog state transitions work (Early → Confirmed → Terminated)
  - [ ] Dialog matching works (Call-ID, From tag, To tag)
  - [ ] Route set management works (Record-Route, Route headers)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import dialog state machine
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.dialog import Dialog; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Dialog class importable
    Evidence: .omo/evidence/task-11-import-dialog.txt

  Scenario: Dialog creation from INVITE works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.dialog import Dialog; from sipx.models import Request, Response; req = Request(method='INVITE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'From': 'alice;tag=from123', 'To': 'bob'}, body=None); resp = Response(200, 'OK', headers={'Call-ID': 'abc123', 'From': 'alice;tag=from123', 'To': 'bob;tag=to456'}, body=None, request=req); d = Dialog.from_invite(req, resp); assert d.state == 'Confirmed'; assert d.call_id == 'abc123'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Dialog creation works
    Evidence: .omo/evidence/task-11-dialog-creation.txt

  Scenario: Dialog state transitions work
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.dialog import Dialog; from sipx.models import Request, Response; req = Request(method='INVITE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'From': 'alice;tag=from123', 'To': 'bob'}, body=None); resp_180 = Response(180, 'Ringing', headers={'Call-ID': 'abc123', 'From': 'alice;tag=from123', 'To': 'bob;tag=to456'}, body=None, request=req); d = Dialog.from_invite(req, resp_180); assert d.state == 'Early'; resp_200 = Response(200, 'OK', headers={'Call-ID': 'abc123', 'From': 'alice;tag=from123', 'To': 'bob;tag=to456'}, body=None, request=req); d.update(resp_200); assert d.state == 'Confirmed'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: State transitions work (Early → Confirmed)
    Evidence: .omo/evidence/task-11-dialog-states.txt
  ```

  **Commit**: YES
  - Message: `feat(protocol): refactor dialog state machine with new models`
  - Files: `sipx/protocol/dialog.py`, `tests/test_protocol_dialog.py`
  - Pre-commit: `pytest tests/test_protocol_dialog.py && ruff check sipx/protocol/dialog.py`

- [x] 12. Auth flow (generator-based)

  **What to do**:
  - Create `sipx/protocol/auth.py` with generator-based auth flow (httpx-style):
    - `AuthFlow` class with `auth_flow(request: Request) -> Generator[Request, Response, None]`
    - Implement Digest authentication (RFC 2617, RFC 7616)
    - Handle 401/407 challenge/response automatically
    - Support multiple authentication schemes (Digest, Basic if needed)
    - Add proper error handling with `AuthError`
  - Write tests in `tests/test_protocol_auth.py` covering auth flow, challenge handling, and error cases

  **Must NOT do**:
  - Do NOT modify existing `sipx/sip/auth.py` yet (keep both old and new during transition - removal happens in Task 32 (Wave 10))
  - Do NOT add OAuth or other complex auth schemes (keep it simple)
  - Do NOT add credential storage or management (that's for client layer)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (auth implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 10, 11, 13)
  - **Blocks**: Task 15 (AsyncClient needs auth flow)
  - **Blocked By**: Task 5 (needs Request/Response models)

  **References**:
  - `sipx/sip/auth.py` - Current auth implementation (refactor source)
  - httpx `_auth.py` - Generator-based auth pattern
  - `sipx/models.py:Request`, `sipx/models.py:Response` - New models to use
  - `sipx/exceptions.py:AuthError` - New exception to use
  - RFC 2617 - HTTP Digest Authentication
  - RFC 7616 - HTTP Digest Access Authentication (updated)
  - RFC 3261 §22 - SIP Digest Authentication

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_protocol_auth.py`
  - [ ] `pytest tests/test_protocol_auth.py` → PASS (12 tests, 0 failures)
  - [ ] `python -c "from sipx.protocol.auth import AuthFlow"` → exit 0
  - [ ] Auth flow generator works (yields request, receives response, retries with auth)
  - [ ] 401/407 challenge handling works
  - [ ] Digest authentication works (qop=auth, algorithm=MD5)
  - [ ] Proper error handling with `AuthError`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import auth flow
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.auth import AuthFlow; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AuthFlow importable
    Evidence: .omo/evidence/task-12-import-auth.txt

  Scenario: Auth flow generator works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.auth import AuthFlow; from sipx.models import Request, Response; auth = AuthFlow(username='alice', password='secret'); req = Request(method='REGISTER', uri='sip:example.com', headers={}, body=None); flow = auth.auth_flow(req); req1 = next(flow); assert req1 == req; resp_401 = Response(401, 'Unauthorized', headers={'WWW-Authenticate': 'Digest realm=\"example.com\", nonce=\"abc123\"'}, body=None, request=req); req2 = flow.send(resp_401); assert 'Authorization' in req2.headers; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Auth flow generator works (yields, receives 401, retries with auth)
    Evidence: .omo/evidence/task-12-auth-flow-generator.txt

  Scenario: Digest authentication works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.auth import AuthFlow; from sipx.models import Request, Response; auth = AuthFlow(username='alice', password='secret'); req = Request(method='REGISTER', uri='sip:example.com', headers={}, body=None); flow = auth.auth_flow(req); req1 = next(flow); resp_401 = Response(401, 'Unauthorized', headers={'WWW-Authenticate': 'Digest realm=\"example.com\", nonce=\"abc123\", qop=\"auth\"'}, body=None, request=req); req2 = flow.send(resp_401); auth_header = req2.headers['Authorization']; assert 'Digest' in auth_header; assert 'username=\"alice\"' in auth_header; assert 'realm=\"example.com\"' in auth_header; assert 'nonce=\"abc123\"' in auth_header; assert 'response=' in auth_header; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Digest authentication generates correct Authorization header
    Evidence: .omo/evidence/task-12-digest-auth.txt
  ```

  **Commit**: YES
  - Message: `feat(protocol): implement generator-based auth flow for Digest authentication`
  - Files: `sipx/protocol/auth.py`, `tests/test_protocol_auth.py`
  - Pre-commit: `pytest tests/test_protocol_auth.py && ruff check sipx/protocol/auth.py`

- [x] 13. Event hooks system

  **What to do**:
  - Create `sipx/protocol/hooks.py` with event hooks system (httpx-style):
    - `EventHooks` type: `dict[str, list[Callable]]`
    - Hook types: `"request"` (before send), `"response"` (after receive), `"provisional"` (1xx responses)
    - `run_hooks(hooks: EventHooks, event: str, *args) -> None`
    - Support sync and async hooks
    - Add proper error handling (hooks should not break flow)
  - Write tests in `tests/test_protocol_hooks.py` covering hook registration, execution, and error handling

  **Must NOT do**:
  - Do NOT add middleware or plugin system (keep it simple)
  - Do NOT add hook ordering guarantees (document that order is registration order, but not guaranteed across async boundaries)
  - Do NOT add hook return value processing (hooks are side-effect only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (simple hook system)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 10, 11, 12)
  - **Blocks**: Task 15 (AsyncClient needs event hooks)
  - **Blocked By**: Task 5 (needs Request/Response models)

  **References**:
  - httpx `event_hooks` - Event hooks pattern
  - `sipx/ua.py:event_hooks` - Current event hooks implementation (refactor source)
  - `sipx/models.py:Request`, `sipx/models.py:Response` - New models to use

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_protocol_hooks.py`
  - [ ] `pytest tests/test_protocol_hooks.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.protocol.hooks import EventHooks, run_hooks"` → exit 0
  - [ ] Hook registration works
  - [ ] Hook execution works (sync and async)
  - [ ] Hook errors do not break flow
  - [ ] Multiple hooks per event work

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import event hooks
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.hooks import EventHooks, run_hooks; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Event hooks importable
    Evidence: .omo/evidence/task-13-import-hooks.txt

  Scenario: Hook registration and execution works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.protocol.hooks import run_hooks
import asyncio

called = []

def hook1(req):
    called.append('hook1')

def hook2(req):
    called.append('hook2')

hooks = {'request': [hook1, hook2]}
asyncio.run(run_hooks(hooks, 'request', None))
assert called == ['hook1', 'hook2'], f"Expected ['hook1', 'hook2'], got {called}"
print('OK')
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Hooks execute in order
    Evidence: .omo/evidence/task-13-hooks-execute.txt

  Scenario: Hook errors do not break flow
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.protocol.hooks import run_hooks
import asyncio

called = []

def hook1(req):
    raise ValueError('error')

def hook2(req):
    called.append('hook2')

hooks = {'request': [hook1, hook2]}
asyncio.run(run_hooks(hooks, 'request', None))
assert called == ['hook2'], f"Expected ['hook2'], got {called}"
print('OK')
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Hook error does not prevent other hooks from running
    Evidence: .omo/evidence/task-13-hooks-error-tolerance.txt
  ```

  **Commit**: YES
  - Message: `feat(protocol): implement event hooks system for request/response interception`
  - Files: `sipx/protocol/hooks.py`, `tests/test_protocol_hooks.py`
  - Pre-commit: `pytest tests/test_protocol_hooks.py && ruff check sipx/protocol/hooks.py`

- [x] 14. Provisional response streaming

  **What to do**:
  - Create `sipx/protocol/provisional.py` with provisional response streaming:
    - `ProvisionalStream` class with `async for response in stream` pattern
    - Integrate with `ClientTransaction` to receive 1xx responses
    - Add filtering by status code (e.g., only 180 Ringing)
    - Add timeout support (stop streaming after timeout)
    - Add proper error handling with `TimeoutError`
  - Write tests in `tests/test_protocol_provisional.py` covering streaming, filtering, and timeout

  **Must NOT do**:
  - Do NOT add PRACK handling (that's for RFC 3262 task)
  - Do NOT add early media handling (that's out of scope)
  - Do NOT add response modification (streaming is read-only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (async streaming implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 8)
  - **Blocks**: Task 20 (PRACK needs provisional streaming)
  - **Blocked By**: Task 5 (needs Request/Response models), Task 10 (needs ClientTransaction)

  **References**:
  - `sipx/protocol/transaction.py:ClientTransaction` - Transaction to integrate with
  - `sipx/models.py:Response` - Response model to stream
  - `sipx/exceptions.py:TimeoutError` - Timeout exception to use
  - RFC 3261 §17.1.1 - INVITE client transaction (provisional responses)
  - Python `async for` pattern - Async iteration

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_protocol_provisional.py`
  - [ ] `pytest tests/test_protocol_provisional.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.protocol.provisional import ProvisionalStream"` → exit 0
  - [ ] Streaming works (`async for response in stream`)
  - [ ] Filtering by status code works
  - [ ] Timeout works (stops streaming after timeout)
  - [ ] Integration with `ClientTransaction` works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import provisional stream
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.protocol.provisional import ProvisionalStream; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: ProvisionalStream importable
    Evidence: .omo/evidence/task-14-import-provisional.txt

  Scenario: Provisional streaming works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.protocol.provisional import ProvisionalStream
from sipx.models import Response
import asyncio

async def test():
    stream = ProvisionalStream()
    asyncio.create_task(stream.feed(Response(100, 'Trying', {}, None)))
    asyncio.create_task(stream.feed(Response(180, 'Ringing', {}, None)))
    asyncio.create_task(stream.feed(Response(200, 'OK', {}, None)))
    
    responses = []
    async for resp in stream:
        responses.append(resp.status_code)
        if resp.status_code >= 200:
            break
    
    assert responses == [100, 180, 200], f"Expected [100, 180, 200], got {responses}"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Streaming receives provisional responses in order
    Evidence: .omo/evidence/task-14-provisional-streaming.txt

  Scenario: Provisional filtering works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.protocol.provisional import ProvisionalStream
from sipx.models import Response
import asyncio

async def test():
    stream = ProvisionalStream(status_codes=[180])
    asyncio.create_task(stream.feed(Response(100, 'Trying', {}, None)))
    asyncio.create_task(stream.feed(Response(180, 'Ringing', {}, None)))
    asyncio.create_task(stream.feed(Response(200, 'OK', {}, None)))
    
    responses = []
    async for resp in stream:
        responses.append(resp.status_code)
        if resp.status_code >= 200:
            break
    
    assert responses == [180, 200], f"Expected [180, 200], got {responses}"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Filtering by status code works (only 180 and final)
    Evidence: .omo/evidence/task-14-provisional-filtering.txt
  ```

  **Commit**: YES
  - Message: `feat(protocol): implement provisional response streaming with async iteration`
  - Files: `sipx/protocol/provisional.py`, `tests/test_protocol_provisional.py`
  - Pre-commit: `pytest tests/test_protocol_provisional.py && ruff check sipx/protocol/provisional.py`

- [x] 15. AsyncClient core

  **What to do**:
  - Create `sipx/client.py` with `AsyncClient` class (httpx-like API):
    - Constructor: `AsyncClient(transport: str = "udp", config: ClientConfig | None = None, event_hooks: EventHooks | None = None, auth: AuthFlow | None = None)`
    - Lifecycle: `async def __aenter__()`, `async def __aexit__()`, `async def aclose()`
    - Properties: `is_closed`, `transport`, `config`
    - Use `TransportRegistry` to create transport
    - Integrate `EventHooks` for request/response interception
    - Integrate `AuthFlow` for automatic authentication
    - **Snapshot old API**: Copy `sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py` to `docs/old-api-snapshot/` (for Task 29 migration guide)
    - **Grep old API imports**: Search entire repo for imports of `sipx.uac`, `sipx.uas`, `sipx.ua` and document all occurrences (including `apps/cli/src/sipx_cli/main.py`, `apps/scenarios/examples/mizu/mizu_common.py`, `apps/scenarios/examples/sip/call_with_dtmf.py`, `apps/harness/tests/test_recorder_reports_profiles.py`, `apps/asterisk/tests/test_asterisk_integration.py`)
    - **NOTE**: Old API files (`sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py`) will be deleted in Task 32 after UAC/UAS methods are fully implemented. App import migration will also happen in Task 32.
  - Write tests in `tests/test_client.py` covering lifecycle, transport selection, and basic operations

  **Must NOT do**:
  - Do NOT add UAC/UAS methods yet (those are separate tasks)
  - Do NOT add config merge logic yet (that's for config merge task)
  - Do NOT add handler decorators yet (that's for UAS handlers task)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: none (core API implementation)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (sequential after Wave 4)
  - **Blocks**: Tasks 16, 17, 18, 19 (UAC/UAS methods, config, lifecycle need AsyncClient)
  - **Blocked By**: Task 9 (needs TransportRegistry), Task 12 (needs AuthFlow), Task 13 (needs EventHooks), Task 5 (needs ClientConfig)

  **References**:
  - httpx `AsyncClient` - httpx async client pattern
  - `sipx/transport/registry.py:TransportRegistry` - Transport factory to use
  - `sipx/protocol/hooks.py:EventHooks` - Event hooks to integrate
  - `sipx/protocol/auth.py:AuthFlow` - Auth flow to integrate
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_client.py`
  - [ ] `pytest tests/test_client.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx import AsyncClient"` → exit 0
  - [ ] `python -c "from sipx import Request, Response"` → exit 0 (top-level exports)
  - [ ] AsyncClient lifecycle works (create, enter context, exit context, close)
  - [ ] Transport selection works (udp/tcp/tls)
  - [ ] Event hooks integration works
  - [ ] Auth flow integration works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import AsyncClient
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx import AsyncClient; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient importable
    Evidence: .omo/evidence/task-15-import-client.txt

  Scenario: AsyncClient lifecycle works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    async with AsyncClient() as client:
        assert not client.is_closed, "Client should not be closed inside context"
        assert client.transport.transport_type == 'udp', f"Expected 'udp', got {client.transport.transport_type}"
    assert client.is_closed, "Client should be closed after exiting context"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient lifecycle works (create, use, close)
    Evidence: .omo/evidence/task-15-client-lifecycle.txt

  Scenario: AsyncClient transport selection works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    async with AsyncClient(transport='tcp') as client:
        assert client.transport.transport_type == 'tcp', f"Expected 'tcp', got {client.transport.transport_type}"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Transport selection works
    Evidence: .omo/evidence/task-15-client-transport-selection.txt
  ```

  **Commit**: YES
  - Message: `feat(api): implement AsyncClient core with transport, hooks, and auth integration`
  - Files: `sipx/client.py`, `sipx/__init__.py`, `tests/test_client.py`
  - Pre-commit: `pytest tests/test_client.py && ruff check sipx/client.py`

- [x] 16. UAC methods (invite, register, message, options, subscribe)

  **What to do**:
  - Add UAC methods to `AsyncClient` in `sipx/client.py`:
    - `async def invite(uri: str, **kwargs) -> Response` - Send INVITE request (basic API, no SDP offer/answer)
    - `async def register(uri: str, **kwargs) -> Response` - Send REGISTER request
    - `async def message(uri: str, body: str | bytes, **kwargs) -> Response` - Send MESSAGE request (basic API, simple content handling)
    - `async def options(uri: str, **kwargs) -> Response` - Send OPTIONS request
    - `async def subscribe(uri: str, event: str, **kwargs) -> Response` - Send SUBSCRIBE request (basic API, no full state machine)
  - **Note**: These are basic API methods. Full RFC-compliant behavior (SUBSCRIBE/NOTIFY state machines, MESSAGE with proper content handling, etc.) is implemented in Tasks 22-24.
  - Integrate with `ClientTransaction` and `Dialog` for state management
  - Use `AuthFlow` for automatic authentication on 401/407
  - Write tests in `tests/test_client_uac.py` covering all UAC methods

  **Must NOT do**:
  - Do NOT add UAS handlers (that's for UAS handlers task)
  - Do NOT add SDP offer/answer logic (that's out of scope for now)
  - Do NOT add media handling (that's out of scope)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (UAC method implementation)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6a (sequential - edits sipx/client.py)
  - **Blocks**: Task 17 (UAS handlers need UAC methods first), Tasks 24, 25 (RFC 3428 MESSAGE, RFC 5626 Outbound need UAC methods)
  - **Blocked By**: Task 15 (needs AsyncClient core), Task 10 (needs ClientTransaction), Task 11 (needs Dialog), Task 5 (needs ClientConfig)

  **References**:
  - `sipx/client.py:AsyncClient` - Client to extend with UAC methods
  - `sipx/protocol/transaction.py:ClientTransaction` - Transaction to use
  - `sipx/protocol/dialog.py:Dialog` - Dialog to use
  - `sipx/protocol/auth.py:AuthFlow` - Auth flow to use
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - RFC 3261 §10 - Registrations (REGISTER)
  - RFC 3261 §13 - Initiating a Session (INVITE)
  - RFC 3428 - MESSAGE method

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_client_uac.py`
  - [ ] `pytest tests/test_client_uac.py` → PASS (20 tests, 0 failures)
  - [ ] `python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'invite')"` → exit 0
  - [ ] All UAC methods work (invite, register, message, options, subscribe)
  - [ ] Transaction management works
  - [ ] Dialog management works
  - [ ] Auth flow integration works (401/407 handling)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import AsyncClient with UAC methods
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'invite'); assert hasattr(AsyncClient, 'register'); assert hasattr(AsyncClient, 'message'); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient has UAC methods
    Evidence: .omo/evidence/task-16-import-uac-methods.txt

  Scenario: invite method works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    async with AsyncClient() as client:
        print('invite method exists')
        assert callable(client.invite), "invite method should be callable"
        print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: invite method is callable
    Evidence: .omo/evidence/task-16-invite-method.txt

  Scenario: register method works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    async with AsyncClient() as client:
        print('register method exists')
        assert callable(client.register), "register method should be callable"
        print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: register method is callable
    Evidence: .omo/evidence/task-16-register-method.txt
  ```

  **Commit**: YES
  - Message: `feat(api): add UAC methods (invite, register, message, options, subscribe) to AsyncClient`
  - Files: `sipx/client.py`, `tests/test_client_uac.py`
  - Pre-commit: `pytest tests/test_client_uac.py && ruff check sipx/client.py`

- [x] 17. UAS handlers (on_invite, on_message)

  **What to do**:
  - Add UAS handler decorators to `AsyncClient` in `sipx/client.py`:
    - `def on_invite(handler: Callable[[Request], Awaitable[Response]]) -> None` - Register INVITE handler
    - `def on_message(handler: Callable[[Request], Awaitable[Response]]) -> None` - Register MESSAGE handler
    - `def on_options(handler: Callable[[Request], Awaitable[Response]]) -> None` - Register OPTIONS handler
    - `def on_subscribe(handler: Callable[[Request], Awaitable[Response]]) -> None` - Register SUBSCRIBE handler
  - Integrate with `ServerTransaction` and `Dialog` for state management
  - Add handler dispatch logic in transport receive loop
  - Write tests in `tests/test_client_uas.py` covering handler registration and dispatch

  **Must NOT do**:
  - Do NOT add handler priority or ordering (keep it simple)
  - Do NOT add handler middleware (keep it simple)
  - Do NOT add SDP offer/answer logic (that's out of scope for now)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (UAS handler implementation)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6b (sequential - edits sipx/client.py)
  - **Blocks**: Task 18 (config merge needs UAS handlers first), Tasks 22, 25 (RFC 3265/6665 Event notification, RFC 5626 Outbound need UAS handlers)
  - **Blocked By**: Task 16 (needs UAC methods first), Task 15 (needs AsyncClient core), Task 11 (needs Dialog)

  **References**:
  - `sipx/client.py:AsyncClient` - Client to extend with UAS handlers
  - `sipx/protocol/transaction.py:ServerTransaction` - Transaction to use
  - `sipx/protocol/dialog.py:Dialog` - Dialog to use
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - RFC 3261 §13 - UAS behavior (receiving INVITE)
  - RFC 3428 - MESSAGE method (UAS behavior)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_client_uas.py`
  - [ ] `pytest tests/test_client_uas.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'on_invite')"` → exit 0
  - [ ] All UAS handlers work (on_invite, on_message, on_options, on_subscribe)
  - [ ] Handler registration works
  - [ ] Handler dispatch works
  - [ ] Transaction management works
  - [ ] Dialog management works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import AsyncClient with UAS handlers
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'on_invite'); assert hasattr(AsyncClient, 'on_message'); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient has UAS handlers
    Evidence: .omo/evidence/task-17-import-uas-handlers.txt

  Scenario: on_invite handler registration works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
from sipx.models import Response
import asyncio

async def test():
    async with AsyncClient() as client:
        @client.on_invite
        async def handle_invite(request):
            return Response(200, 'OK', {}, None)
        print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: on_invite decorator works
    Evidence: .omo/evidence/task-17-on-invite-handler.txt

  Scenario: on_message handler registration works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
from sipx.models import Response
import asyncio

async def test():
    async with AsyncClient() as client:
        @client.on_message
        async def handle_message(request):
            return Response(200, 'OK', {}, None)
        print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: on_message decorator works
    Evidence: .omo/evidence/task-17-on-message-handler.txt
  ```

  **Commit**: YES
  - Message: `feat(api): add UAS handler decorators (on_invite, on_message, on_options, on_subscribe) to AsyncClient`
  - Files: `sipx/client.py`, `tests/test_client_uas.py`
  - Pre-commit: `pytest tests/test_client_uas.py && ruff check sipx/client.py`

- [x] 18. Config merge (client defaults + request overrides)

  **What to do**:
  - Add config merge logic to `sipx/config.py`: client defaults merge with per-request overrides
  - Integrate `ClientConfig` into `AsyncClient` constructor (use ClientConfig from Task 5)
  - Write tests in `tests/test_config.py` covering config merge logic
  - **Note**: ClientConfig dataclass is already created in Task 5, this task focuses on merge logic and integration

  **Must NOT do**:
  - Do NOT add config validation (keep it simple for now)
  - Do NOT add config file loading (keep it programmatic)
  - Do NOT add environment variable support (keep it explicit)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (simple config dataclass)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6c (sequential - edits sipx/client.py)
  - **Blocks**: Task 19 (lifecycle needs config merge first)
  - **Blocked By**: Task 17 (needs UAS handlers first), Task 15 (needs AsyncClient to integrate with), Task 5 (needs ClientConfig)

  **References**:
  - httpx `Client` config - httpx client config pattern
  - `sipx/client.py:AsyncClient` - Client to integrate config with
  - Python `dataclasses` - Dataclass pattern
  - `sipx/uac.py:SipUac` - Existing UAC implementation with similar defaults (local_host, local_port, timeout)
  - `sipx/sip/transport.py:SipUdpEndpoint` - Existing transport with max_message_size default
  - Interview decision: "Config merge (client defaults + request overrides)" - user explicitly requested httpx-like config merge pattern

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_config.py`
  - [ ] `pytest tests/test_config.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.config import ClientConfig"` → exit 0
  - [ ] `ClientConfig` is a dataclass with expected fields
  - [ ] Config merge logic works (defaults + overrides)
  - [ ] AsyncClient integrates with ClientConfig

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import ClientConfig
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.config import ClientConfig; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: ClientConfig importable
    Evidence: .omo/evidence/task-18-import-config.txt

  Scenario: ClientConfig is dataclass with defaults
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.config import ClientConfig; c = ClientConfig(); assert c.transport == 'udp'; assert c.local_host == '0.0.0.0'; assert c.timeout == 30.0; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: ClientConfig has correct defaults
    Evidence: .omo/evidence/task-18-config-defaults.txt

  Scenario: Config merge works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.config import ClientConfig; defaults = ClientConfig(); overrides = {'timeout': 60.0, 'user_agent': 'custom/1.0'}; merged = defaults.merge(overrides); assert merged.timeout == 60.0; assert merged.user_agent == 'custom/1.0'; assert merged.transport == 'udp'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Config merge works (defaults + overrides)
    Evidence: .omo/evidence/task-18-config-merge.txt
  ```

  **Commit**: YES
  - Message: `feat(api): add ClientConfig with merge logic for defaults and overrides`
  - Files: `sipx/config.py`, `sipx/client.py`, `tests/test_config.py`
  - Pre-commit: `pytest tests/test_config.py && ruff check sipx/config.py sipx/client.py`

- [x] 19. AsyncClient context manager + lifecycle

  **What to do**:
  - Enhance `AsyncClient` lifecycle management in `sipx/client.py`:
    - Ensure `__aenter__` creates transport and starts receive loop
    - Ensure `__aexit__` closes transport and cancels receive loop
    - Add `aclose()` method for explicit cleanup
    - Add `is_closed` property
    - Add proper error handling during lifecycle (transport errors, cleanup errors)
  - Write tests in `tests/test_client_lifecycle.py` covering context manager, cleanup, and error handling

  **Must NOT do**:
  - Do NOT add connection pooling (keep it simple)
  - Do NOT add reconnection logic (keep it simple)
  - Do NOT add graceful shutdown with pending requests (keep it simple for now)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (lifecycle management)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6d (sequential - edits sipx/client.py)
  - **Blocks**: 26, 27, 29, 32 (lifecycle is required for final tasks)
  - **Blocked By**: Task 18 (needs config merge first), Task 15 (needs AsyncClient core)

  **References**:
  - httpx `AsyncClient` lifecycle - httpx async client lifecycle pattern
  - `sipx/client.py:AsyncClient` - Client to enhance
  - `sipx/transport/base.py:Transport` - Transport to manage
  - `sipx/exceptions.py:TransportError` - Transport errors to handle

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_client_lifecycle.py`
  - [ ] `pytest tests/test_client_lifecycle.py` → PASS (12 tests, 0 failures)
  - [ ] `python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'aclose')"` → exit 0
  - [ ] Context manager works (`async with AsyncClient() as client`)
  - [ ] `aclose()` method works
  - [ ] `is_closed` property works
  - [ ] Error handling during lifecycle works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: AsyncClient context manager works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    async with AsyncClient() as client:
        assert not client.is_closed, "Client should not be closed inside context"
    assert client.is_closed, "Client should be closed after exiting context"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Context manager works (enter, use, exit)
    Evidence: .omo/evidence/task-19-context-manager.txt

  Scenario: aclose method works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    client = AsyncClient()
    await client.__aenter__()
    assert not client.is_closed, "Client should not be closed after __aenter__"
    await client.aclose()
    assert client.is_closed, "Client should be closed after aclose"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: aclose method works
    Evidence: .omo/evidence/task-19-aclose-method.txt

  Scenario: is_closed property works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
import asyncio

async def test():
    client = AsyncClient()
    assert client.is_closed, "Client should be closed before __aenter__"
    await client.__aenter__()
    assert not client.is_closed, "Client should not be closed after __aenter__"
    await client.__aexit__(None, None, None)
    assert client.is_closed, "Client should be closed after __aexit__"
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: is_closed property tracks lifecycle correctly
    Evidence: .omo/evidence/task-19-is-closed-property.txt
  ```

  **Commit**: YES
  - Message: `feat(api): enhance AsyncClient lifecycle with context manager and cleanup`
  - Files: `sipx/client.py`, `tests/test_client_lifecycle.py`
  - Pre-commit: `pytest tests/test_client_lifecycle.py && ruff check sipx/client.py`

- [x] 20. RFC 3262 PRACK (provisional response acknowledgment)

  **What to do**:
  - Create `sipx/rfc/prack.py` implementing RFC 3262:
    - `PrackHandler` class to handle reliable provisional responses (1xx with Require: 100rel)
    - Integrate with `ProvisionalStream` from Task 14
    - Send PRACK requests for reliable 1xx responses
    - Handle RSeq and RAck headers
    - Add proper error handling with `ProtocolError`
  - Write tests in `tests/test_rfc_prack.py` covering PRACK generation, RSeq tracking, and error cases

  **Must NOT do**:
  - Do NOT add early media handling (out of scope)
  - Do NOT add SDP offer/answer in PRACK (keep it simple)
  - Do NOT modify existing provisional streaming (integrate, don't change)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (RFC implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 9)
  - **Blocks**: Task 28 (RFC compliance matrix needs PRACK evidence)
  - **Blocked By**: Task 10 (needs ClientTransaction), Task 14 (needs ProvisionalStream)

  **References**:
  - `sipx/protocol/transaction.py:ClientTransaction` - Transaction to use
  - `sipx/protocol/provisional.py:ProvisionalStream` - Provisional stream to integrate with
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/exceptions.py:ProtocolError` - Protocol error to use
  - RFC 3262 - Reliability of Provisional Responses in SIP
  - RFC 3261 §13.2.2.1 - 1xx responses (context)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_prack.py`
  - [ ] `pytest tests/test_rfc_prack.py` → PASS (12 tests, 0 failures)
  - [ ] `python -c "from sipx.rfc.prack import PrackHandler"` → exit 0
  - [ ] PRACK generation works (for 1xx with Require: 100rel)
  - [ ] RSeq tracking works (detect duplicates, track sequence)
  - [ ] RAck header generation works
  - [ ] Integration with ProvisionalStream works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import PrackHandler
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.prack import PrackHandler; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: PrackHandler importable
    Evidence: .omo/evidence/task-20-import-prack.txt

  Scenario: PRACK generation works for reliable 1xx
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.prack import PrackHandler; from sipx.models import Request, Response; handler = PrackHandler(); req = Request(method='INVITE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'CSeq': '1 INVITE'}, body=None); resp_180 = Response(180, 'Ringing', headers={'Call-ID': 'abc123', 'CSeq': '1 INVITE', 'Require': '100rel', 'RSeq': '1'}, body=None, request=req); prack_req = handler.generate_prack(resp_180); assert prack_req.method == 'PRACK'; assert 'RAck' in prack_req.headers; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: PRACK request generated correctly
    Evidence: .omo/evidence/task-20-prack-generation.txt

  Scenario: RSeq tracking detects duplicates
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.prack import PrackHandler; from sipx.models import Request, Response; handler = PrackHandler(); req = Request(method='INVITE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'CSeq': '1 INVITE'}, body=None); resp_180_1 = Response(180, 'Ringing', headers={'Call-ID': 'abc123', 'CSeq': '1 INVITE', 'Require': '100rel', 'RSeq': '1'}, body=None, request=req); resp_180_2 = Response(180, 'Ringing', headers={'Call-ID': 'abc123', 'CSeq': '1 INVITE', 'Require': '100rel', 'RSeq': '1'}, body=None, request=req); handler.track_rseq(resp_180_1); is_dup = handler.is_duplicate(resp_180_2); assert is_dup; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: RSeq tracking detects duplicate provisional responses
    Evidence: .omo/evidence/task-20-rseq-tracking.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 3262 PRACK for reliable provisional responses`
  - Files: `sipx/rfc/prack.py`, `tests/test_rfc_prack.py`
  - Pre-commit: `pytest tests/test_rfc_prack.py && ruff check sipx/rfc/prack.py`

- [x] 21. RFC 3263 DNS resolution (locating SIP servers)

  **What to do**:
  - Create `sipx/rfc/dns.py` implementing RFC 3263:
    - `SipDnsResolver` class with `async def resolve(uri: str) -> list[tuple[str, int, str]]` (returns list of (host, port, transport))
    - Implement NAPTR record lookup (for service resolution) using `dnspython` library
    - Implement SRV record lookup (for host/port resolution) using `dnspython` library
    - Implement A/AAAA record lookup (fallback) using stdlib `asyncio.getaddrinfo()`
    - Add transport selection logic (prefer TLS > TCP > UDP)
    - Add proper error handling with `TransportError`
  - Add `dnspython` to dependencies in `pyproject.toml`
  - Write tests in `tests/test_rfc_dns.py` covering NAPTR, SRV, A/AAAA lookups, and transport selection

  **Must NOT do**:
  - Do NOT add DNS caching (keep it simple for now)
  - Do NOT add DNSSEC validation (out of scope)
  - Do NOT add connection pooling (that's for transport layer)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (DNS implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Task 15)
  - **Blocks**: Task 28 (RFC compliance matrix needs DNS evidence)
  - **Blocked By**: Task 9 (needs TransportRegistry for transport selection)

  **References**:
  - `sipx/transport/registry.py:TransportRegistry` - Transport registry for transport selection
  - `sipx/exceptions.py:TransportError` - Transport error to use
  - Python `asyncio.getaddrinfo()` - DNS resolution API (for A/AAAA fallback)
  - `dnspython` library - DNS library (for NAPTR/SRV resolution)
  - RFC 3263 - Session Initiation Protocol (SIP): Locating SIP Servers
  - RFC 2782 - DNS SRV records
  - RFC 2915 - NAPTR records

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_dns.py`
  - [ ] `pytest tests/test_rfc_dns.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx.rfc.dns import SipDnsResolver"` → exit 0
  - [ ] NAPTR lookup works (with mocked DNS)
  - [ ] SRV lookup works (with mocked DNS)
  - [ ] A/AAAA lookup works (with mocked DNS)
  - [ ] Transport selection works (follows RFC 3263 URI scheme and NAPTR/SRV preferences)
  - [ ] Fallback logic works (NAPTR → SRV → A/AAAA)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import SipDnsResolver
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.dns import SipDnsResolver; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: SipDnsResolver importable
    Evidence: .omo/evidence/task-21-import-dns.txt

  Scenario: DNS resolution works with mocked DNS
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.rfc.dns import SipDnsResolver
import asyncio

async def test():
    # Create resolver with mocked DNS records
    resolver = SipDnsResolver()
    
    # Mock DNS records for testing (implementation should support injecting mock records)
    resolver._mock_records = {
        'example.com': [
            ('example.com', 5060, 'udp'),
            ('example.com', 5060, 'tcp'),
            ('example.com', 5061, 'tls')
        ]
    }
    
    results = await resolver.resolve('sip:bob@example.com')
    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) > 0, "Expected at least one result"
    
    host, port, transport = results[0]
    assert isinstance(host, str), f"Expected str for host, got {type(host)}"
    assert isinstance(port, int), f"Expected int for port, got {type(port)}"
    assert transport in ['udp', 'tcp', 'tls'], f"Expected transport in ['udp', 'tcp', 'tls'], got {transport}"
    
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: DNS resolution returns list of (host, port, transport)
    Evidence: .omo/evidence/task-21-dns-resolution.txt
    Note: Implementation must support injecting mock DNS records via `_mock_records` attribute for testing

  Scenario: Transport selection works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.rfc.dns import SipDnsResolver
import asyncio

async def test():
    resolver = SipDnsResolver()
    
    # Test transport selection with predefined results
    results = [
        ('example.com', 5060, 'udp'),
        ('example.com', 5060, 'tcp'),
        ('example.com', 5061, 'tls')
    ]
    
    selected = resolver.select_transport(results)
    assert selected in results, f"Selected transport {selected} not in results"
    
    print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Transport selection follows RFC 3263 rules
    Evidence: .omo/evidence/task-21-transport-selection.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 3263 DNS resolution for locating SIP servers`
  - Files: `sipx/rfc/dns.py`, `tests/test_rfc_dns.py`, `pyproject.toml`
  - Pre-commit: `pytest tests/test_rfc_dns.py && ruff check sipx/rfc/dns.py`

- [x] 22. RFC 3265/6665 Event notification (SUBSCRIBE/NOTIFY)

  **What to do**:
  - Create `sipx/rfc/events.py` implementing RFC 3265 (updated by RFC 6665):
    - `SubscriptionDialog` class extending `Dialog` for SUBSCRIBE/NOTIFY
    - `SubscriptionState` enum (pending, active, terminated)
    - `EventPackage` dataclass (name, parameters)
    - Handle SUBSCRIBE requests (UAS) and responses (UAC)
    - Handle NOTIFY requests (UAS) and responses (UAC)
    - Add subscription state management (creation, refresh, termination)
    - Add proper error handling with `DialogError`
  - Write tests in `tests/test_rfc_events.py` covering subscription lifecycle, state transitions, and NOTIFY handling

  **Must NOT do**:
  - Do NOT implement specific event packages (presence, message-summary, etc.) - those are separate tasks
  - Do NOT add subscription authorization policy (out of scope)
  - Do NOT add subscription forking (keep it simple)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (RFC implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 7 (with Tasks 24, 25)
  - **Blocks**: Task 23 (RFC 3856 + RFC 3858 Presence needs event notification), Task 28 (RFC compliance matrix needs event notification evidence)
  - **Blocked By**: Task 11 (needs Dialog), Task 17 (needs UAS handlers)

  **References**:
  - `sipx/protocol/dialog.py:Dialog` - Dialog to extend
  - `sipx/client.py:AsyncClient` - Client with UAS handlers
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/exceptions.py:DialogError` - Dialog error to use
  - RFC 6665 - An Event Notification Framework for SIP (updates RFC 3265)
  - RFC 3265 - Session Initiation Protocol (SIP)-Specific Event Notification (obsoleted by 6665)
  - RFC 3261 §12 - Dialogs (context)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_events.py`
  - [ ] `pytest tests/test_rfc_events.py` → PASS (20 tests, 0 failures)
  - [ ] `python -c "from sipx.rfc.events import SubscriptionDialog, SubscriptionState, EventPackage"` → exit 0
  - [ ] SubscriptionDialog creation works
  - [ ] Subscription state transitions work (pending → active → terminated)
  - [ ] SUBSCRIBE request/response handling works
  - [ ] NOTIFY request/response handling works
  - [ ] Event package parsing works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import event notification classes
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.events import SubscriptionDialog, SubscriptionState, EventPackage; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Event notification classes importable
    Evidence: .omo/evidence/task-22-import-events.txt

  Scenario: SubscriptionDialog creation works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.events import SubscriptionDialog, EventPackage; from sipx.models import Request, Response; req = Request(method='SUBSCRIBE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'Event': 'presence', 'Expires': '3600'}, body=None); resp = Response(200, 'OK', headers={'Call-ID': 'abc123', 'Expires': '3600'}, body=None, request=req); sub = SubscriptionDialog.from_subscribe(req, resp); assert sub.state == 'active'; assert sub.event.name == 'presence'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: SubscriptionDialog created from SUBSCRIBE/200 OK
    Evidence: .omo/evidence/task-22-subscription-creation.txt

  Scenario: Subscription state transitions work
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.events import SubscriptionDialog, SubscriptionState; from sipx.models import Request, Response; req = Request(method='SUBSCRIBE', uri='sip:bob@example.com', headers={'Call-ID': 'abc123', 'Event': 'presence', 'Expires': '3600'}, body=None); resp = Response(202, 'Accepted', headers={'Call-ID': 'abc123', 'Expires': '3600'}, body=None, request=req); sub = SubscriptionDialog.from_subscribe(req, resp); assert sub.state == 'pending'; notify = Request(method='NOTIFY', uri='sip:alice@example.com', headers={'Call-ID': 'abc123', 'Subscription-State': 'active'}, body=None); sub.update_from_notify(notify); assert sub.state == 'active'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Subscription state transitions work (pending → active)
    Evidence: .omo/evidence/task-22-subscription-states.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 3265/6665 event notification framework`
  - Files: `sipx/rfc/events.py`, `tests/test_rfc_events.py`
  - Pre-commit: `pytest tests/test_rfc_events.py && ruff check sipx/rfc/events.py`

- [x] 23. RFC 3856 + RFC 3858 Presence (event package for presence)

  **What to do**:
  - Create `sipx/rfc/presence.py` implementing RFC 3856 + 3858:
    - `PresenceEventPackage` class extending `EventPackage` for "presence" event
    - `PresenceDocument` dataclass for PIDF (Presence Information Data Format)
    - `PresenceTuple` dataclass (status, contact, note)
    - Parse and generate PIDF XML documents
    - Integrate with `SubscriptionDialog` from Task 22
    - Add proper error handling with `ProtocolError`
  - Write tests in `tests/test_rfc_presence.py` covering PIDF parsing, presence subscription, and NOTIFY handling

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (RFC implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 8 (with Tasks 27, 29)
  - **Blocks**: Task 28 (RFC compliance matrix needs presence evidence), Task 32 (old API deletion needs presence complete)
  - **Blocked By**: Task 22 (needs SubscriptionDialog)

  **References**:
  - `sipx/rfc/events.py:SubscriptionDialog`, `sipx/rfc/events.py:EventPackage` - Event framework to use
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/exceptions.py:ProtocolError` - Protocol error to use
  - Python `xml.etree.ElementTree` - XML parsing
  - RFC 3856 - A Presence Event Package for SIP
  - RFC 3858 - An Extensible Markup Language (XML) Based Format for Presence Information (PIDF)
  - RFC 3863 - Presence Information Data Format (PIDF)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_presence.py`
  - [ ] `pytest tests/test_rfc_presence.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx.rfc.presence import PresenceEventPackage, PresenceDocument, PresenceTuple"` → exit 0
  - [ ] PresenceEventPackage registration works
  - [ ] PIDF XML parsing works
  - [ ] PIDF XML generation works
  - [ ] Presence subscription integration works
  - [ ] NOTIFY with PIDF body handling works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import presence classes
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.presence import PresenceEventPackage, PresenceDocument, PresenceTuple; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Presence classes importable
    Evidence: .omo/evidence/task-23-import-presence.txt

  Scenario: PIDF XML parsing works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.presence import PresenceDocument; pidf_xml = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?><presence xmlns=\"urn:ietf:params:xml:ns:pidf\" entity=\"pres:bob@example.com\"><tuple id=\"t1\"><status><basic>open</basic></status><contact>sip:bob@example.com</contact></tuple></presence>'''; doc = PresenceDocument.from_xml(pidf_xml); assert doc.entity == 'pres:bob@example.com'; assert len(doc.tuples) == 1; assert doc.tuples[0].status == 'open'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: PIDF XML parsing works
    Evidence: .omo/evidence/task-23-pidf-parsing.txt

  Scenario: PIDF XML generation works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.presence import PresenceDocument, PresenceTuple; tuple1 = PresenceTuple(id='t1', status='open', contact='sip:bob@example.com', note=None); doc = PresenceDocument(entity='pres:bob@example.com', tuples=[tuple1]); xml = doc.to_xml(); assert 'urn:ietf:params:xml:ns:pidf' in xml; assert 'pres:bob@example.com' in xml; assert '<basic>open</basic>' in xml; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: PIDF XML generation works
    Evidence: .omo/evidence/task-23-pidf-generation.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 3856 + 3858 presence event package with PIDF`
  - Files: `sipx/rfc/presence.py`, `tests/test_rfc_presence.py`
  - Pre-commit: `pytest tests/test_rfc_presence.py && ruff check sipx/rfc/presence.py`

- [x] 24. RFC 3428 MESSAGE (instant messaging)

  **What to do**:
  - Enhance `AsyncClient` in `sipx/client.py` with MESSAGE method support:
    - `async def message(uri: str, body: str | bytes, content_type: str = "text/plain", **kwargs) -> Response`
    - Handle MESSAGE requests (UAC) and responses
    - Handle incoming MESSAGE requests (UAS) with `on_message` handler
    - Add proper error handling with `ProtocolError`
  - Write tests in `tests/test_rfc_message.py` covering MESSAGE sending, receiving, and error cases

  **Must NOT do**:
  - Do NOT add message session (MSRP) - out of scope
  - Do NOT add message storage/forwarding - out of scope
  - Do NOT add message encryption (S/MIME) - out of scope

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (simple RFC implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 7 (with Tasks 22, 25)
  - **Blocks**: Task 28 (RFC compliance matrix needs MESSAGE evidence)
  - **Blocked By**: Task 16 (needs UAC methods)

  **References**:
  - `sipx/client.py:AsyncClient` - Client to enhance
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/exceptions.py:ProtocolError` - Protocol error to use
  - RFC 3428 - Session Initiation Protocol (SIP) Extension for Instant Messaging

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_message.py`
  - [ ] `pytest tests/test_rfc_message.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'message')"` → exit 0
  - [ ] MESSAGE request sent with correct Content-Type header (text/plain by default)
  - [ ] MESSAGE request body is properly encoded (UTF-8 for text, binary for bytes)
  - [ ] MESSAGE response 200 OK received and parsed correctly
  - [ ] MESSAGE response 4xx/5xx errors raise appropriate exceptions
  - [ ] Incoming MESSAGE requests trigger `on_message` handler with correct Request object

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: AsyncClient has message method
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx import AsyncClient; assert hasattr(AsyncClient, 'message'); print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient has message method
    Evidence: .omo/evidence/task-24-message-method.txt

  Scenario: MESSAGE sending works (mocked)
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient
from sipx.models import Response
import asyncio

async def test():
    async with AsyncClient() as client:
        print('message method exists')
        assert callable(client.message), "message method should be callable"
        print('OK')

asyncio.run(test())
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: message method is callable
    Evidence: .omo/evidence/task-24-message-sending.txt

  Scenario: MESSAGE Content-Type handling works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.models import Request; req = Request(method='MESSAGE', uri='sip:bob@example.com', headers={'Content-Type': 'text/plain'}, body=b'Hello, Bob!'); assert req.headers['Content-Type'] == 'text/plain'; assert req.body == b'Hello, Bob!'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: MESSAGE with Content-Type and body works
    Evidence: .omo/evidence/task-24-message-content-type.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 3428 MESSAGE method for instant messaging`
  - Files: `sipx/client.py`, `tests/test_rfc_message.py`
  - Pre-commit: `pytest tests/test_rfc_message.py && ruff check sipx/client.py`

- [x] 25. RFC 5626 Outbound (client-initiated connections)

  **What to do**:
  - Create `sipx/rfc/outbound.py` implementing RFC 5626:
    - `OutboundConfig` dataclass (instance_id, reg_id, flow_token)
    - `OutboundHandler` class for managing outbound connections
    - Generate instance-id (URN:UUID) and reg-id
    - Add Path header support for outbound
    - Add keepalive mechanism (CRLF ping)
    - Add flow token handling
    - Integrate with `AsyncClient` for registration
    - Add proper error handling with `ProtocolError`
  - Write tests in `tests/test_rfc_outbound.py` covering instance-id generation, Path headers, and keepalives

  **Must NOT do**:
  - Do NOT add multiple flows/redundancy (keep it simple)
  - Do NOT add flow recovery/backoff (keep it simple)
  - Do NOT add STUN keepalives (use CRLF only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (RFC implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 7 (with Tasks 22, 24)
  - **Blocks**: Task 28 (RFC compliance matrix needs outbound evidence)
  - **Blocked By**: Task 16 (needs UAC methods), Task 17 (needs UAS handlers)

  **References**:
  - `sipx/client.py:AsyncClient` - Client to integrate with
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/exceptions.py:ProtocolError` - Protocol error to use
  - Python `uuid` module - UUID generation for instance-id
  - RFC 5626 - Managing Client-Initiated Connections in SIP
  - RFC 3327 - Session Initiation Protocol (SIP) Extension Header Field for Registering Non-Adjacent Contacts (Path)
  - RFC 3261 §10 - Registrations (context)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_outbound.py`
  - [ ] `pytest tests/test_rfc_outbound.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx.rfc.outbound import OutboundConfig, OutboundHandler"` → exit 0
  - [ ] instance-id generation works (URN:UUID format)
  - [ ] reg-id generation works
  - [ ] Path header generation works
  - [ ] Keepalive mechanism works (CRLF ping)
  - [ ] Flow token handling works
  - [ ] Integration with AsyncClient registration works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import outbound classes
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.outbound import OutboundConfig, OutboundHandler; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Outbound classes importable
    Evidence: .omo/evidence/task-25-import-outbound.txt

  Scenario: instance-id generation works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.outbound import OutboundConfig; config = OutboundConfig(); assert config.instance_id.startswith('urn:uuid:'); assert len(config.instance_id) > 20; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: instance-id generated in URN:UUID format
    Evidence: .omo/evidence/task-25-instance-id.txt

  Scenario: Path header generation works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.rfc.outbound import OutboundHandler; handler = OutboundHandler(); path = handler.generate_path('sip:proxy.example.com', flow_token='abc123'); assert 'Path:' in path; assert 'sip:proxy.example.com' in path; assert 'ob' in path; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Path header generated with outbound parameter
    Evidence: .omo/evidence/task-25-path-header.txt
  ```

  **Commit**: YES
  - Message: `feat(rfc): implement RFC 5626 Outbound for client-initiated connections`
  - Files: `sipx/rfc/outbound.py`, `tests/test_rfc_outbound.py`
  - Pre-commit: `pytest tests/test_rfc_outbound.py && ruff check sipx/rfc/outbound.py`

- [x] 26. API docstrings (all public objects)

  **What to do**:
  - Add comprehensive docstrings to all public API objects:
    - `AsyncClient` class and all methods (invite, register, message, options, subscribe, on_invite, on_message, etc.)
    - `Request` and `Response` models
    - `Transport` interface and concrete transports (UdpTransport, TcpTransport, TlsTransport)
    - Exception hierarchy (SipError, TransportError, TimeoutError, ProtocolError, AuthError, DialogError, TransactionError)
    - Config classes (ClientConfig, TransportConfig, TlsConfig)
    - RFC classes (PrackHandler, SipDnsResolver, SubscriptionDialog, PresenceEventPackage, OutboundHandler)
  - Use Google-style docstrings with Args, Returns, Raises, Examples sections
  - Add module-level docstrings to all public modules
  - Ensure all docstrings are type-hint aware

  **Must NOT do**:
  - Do NOT add docstrings to private/internal methods (focus on public API)
  - Do NOT add excessive detail (keep docstrings concise and useful)
  - Do NOT add implementation details in docstrings (focus on usage)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none (documentation task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 9 (with Task 28)
  - **Blocks**: Task 32 (old API deletion needs docstrings complete)
  - **Blocked By**: Tasks 15-19 (needs AsyncClient and all public objects), Task 23 (needs PresenceEventPackage and RFC classes)

  **References**:
  - `sipx/client.py:AsyncClient` - Main public API class
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Public models
  - `sipx/transport/*.py` - Public transport classes
  - `sipx/exceptions.py` - Public exception hierarchy
  - `sipx/config.py` - Public config classes
  - `sipx/rfc/*.py` - Public RFC classes
  - Google Python Style Guide - Docstring format

  **Acceptance Criteria**:
  - [ ] All public classes have module-level docstrings with at least 2 sentences describing purpose
  - [ ] All public classes have class-level docstrings with Args section listing constructor parameters
  - [ ] All public methods have method-level docstrings with Args, Returns, Raises, Examples sections
  - [ ] `python -c "from sipx import AsyncClient; help(AsyncClient)"` shows comprehensive help
  - [ ] `ruff check .` passes (no docstring linting errors)
  - [ ] All docstrings include type annotations in Args section matching function signature
  - [ ] All docstrings follow consistent format: summary line, blank line, detailed description, Args, Returns, Raises, Examples
  - [ ] At least 90% of public symbols have docstrings (measured by `pydocstyle --count`)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: AsyncClient has comprehensive docstring
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx import AsyncClient; assert AsyncClient.__doc__ is not None; assert 'async sip client' in AsyncClient.__doc__.lower(); assert 'Args:' in AsyncClient.__doc__; assert 'Examples:' in AsyncClient.__doc__; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: AsyncClient has comprehensive docstring with Args and Examples
    Evidence: .omo/evidence/task-26-asyncclient-docstring.txt

  Scenario: All public methods have docstrings
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx import AsyncClient

methods = ['invite', 'register', 'message', 'options', 'subscribe']
for m in methods:
    method = getattr(AsyncClient, m)
    assert method.__doc__ is not None, f'{m} missing docstring'
    print(f'{m} has docstring')

print('OK')
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: All public UAC methods have docstrings
    Evidence: .omo/evidence/task-26-uac-methods-docstrings.txt

  Scenario: Exception hierarchy has docstrings
    Tool: Bash (python REPL)
    Steps:
      1. Run: python - <<'PY'
from sipx.exceptions import SipError, TransportError, TimeoutError, ProtocolError, AuthError, DialogError, TransactionError

exceptions = [SipError, TransportError, TimeoutError, ProtocolError, AuthError, DialogError, TransactionError]
for e in exceptions:
    assert e.__doc__ is not None, f'{e.__name__} missing docstring'
    print(f'{e.__name__} has docstring')

print('OK')
PY
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: All public exceptions have docstrings
    Evidence: .omo/evidence/task-26-exceptions-docstrings.txt
  ```

  **Commit**: YES
  - Message: `docs(api): add comprehensive docstrings to all public API objects`
  - Files: `sipx/client.py`, `sipx/models.py`, `sipx/transport/*.py`, `sipx/exceptions.py`, `sipx/config.py`, `sipx/rfc/*.py`
  - Pre-commit: `ruff check .`

- [x] 27. Examples rewrite (register, invite, message, subscribe)

  **What to do**:
  - Rewrite all examples in `sipx/examples/` using new httpx-like API:
    - `register.py` - Simple REGISTER example with AsyncClient
    - `invite.py` - INVITE example with basic SDP (parsing/generation only, no offer/answer negotiation)
    - `message.py` - MESSAGE example for instant messaging
    - `subscribe.py` - SUBSCRIBE/NOTIFY example for presence
    - `options.py` - OPTIONS example for capability discovery
    - `handlers.py` - UAS handler example with on_invite, on_message
    - `auth.py` - Authentication example with AuthFlow
    - `tls.py` - TLS transport example
  - Each example should be self-contained and runnable with `python -m sipx.examples.<name>`
  - Add comprehensive comments explaining each step
  - Add error handling examples

  **Must NOT do**:
  - Do NOT use old API (SipUac, SipUas, SipUserAgent) in examples
  - Do NOT add complex scenarios (keep examples simple and focused)
  - Do NOT add external dependencies (use only sipx and stdlib)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (example writing)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 8 (with Tasks 23, 29)
  - **Blocks**: None (examples are final polish)
  - **Blocked By**: Tasks 15-19 (needs AsyncClient and all public objects)

  **References**:
  - `sipx/client.py:AsyncClient` - New API to use in examples
  - `sipx/models.py:Request`, `sipx/models.py:Response` - Models to use
  - `sipx/rfc/*.py` - RFC classes to use
  - Old examples in `sipx/examples/` - Reference for scenarios (but rewrite with new API)

  **Acceptance Criteria**:
  - [ ] All 8 examples created and runnable
  - [ ] `python -m sipx.examples.register --help` works
  - [ ] `python -m sipx.examples.invite --help` works
  - [ ] `python -m sipx.examples.message --help` works
  - [ ] `python -m sipx.examples.subscribe --help` works
  - [ ] `python -m sipx.examples.options --help` works
  - [ ] `python -m sipx.examples.handlers --help` works
  - [ ] `python -m sipx.examples.auth --help` works
  - [ ] `python -m sipx.examples.tls --help` works
  - [ ] All examples use new httpx-like API (AsyncClient)
  - [ ] All examples have at least 5 inline comments explaining key steps
  - [ ] All examples include try/except blocks demonstrating error handling
  - [ ] All examples can be run without external dependencies (use mocked transports where needed)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: register example runs
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -m sipx.examples.register --help
      2. Assert: exit code 0, stdout contains "usage:" or "REGISTER"
    Expected Result: register example runs and shows help
    Evidence: .omo/evidence/task-27-register-example.txt

  Scenario: invite example runs
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -m sipx.examples.invite --help
      2. Assert: exit code 0, stdout contains "usage:" or "INVITE"
    Expected Result: invite example runs and shows help
    Evidence: .omo/evidence/task-27-invite-example.txt

  Scenario: message example runs
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -m sipx.examples.message --help
      2. Assert: exit code 0, stdout contains "usage:" or "MESSAGE"
    Expected Result: message example runs and shows help
    Evidence: .omo/evidence/task-27-message-example.txt

  Scenario: subscribe example runs
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -m sipx.examples.subscribe --help
      2. Assert: exit code 0, stdout contains "usage:" or "SUBSCRIBE"
    Expected Result: subscribe example runs and shows help
    Evidence: .omo/evidence/task-27-subscribe-example.txt
  ```

  **Commit**: YES
  - Message: `docs(examples): rewrite all examples with new httpx-like API`
  - Files: `sipx/examples/*.py`
  - Pre-commit: `python -m sipx.examples.register --help && python -m sipx.examples.invite --help`

- [x] 28. RFC compliance matrix update (with test evidence)

  **What to do**:
  - Update `.spec/rfc-compliance.md` with test evidence for all implemented RFCs:
    - RFC 3261 (SIP core) - mark as Implemented with test references
    - RFC 3262 (PRACK) - mark as Implemented with test references
    - RFC 3263 (DNS) - mark as Implemented with test references
    - RFC 3264 (SDP offer/answer) - mark as Partial (basic SDP parsing/generation only, no full offer/answer negotiation logic)
    - RFC 3265/6665 (Event notification) - mark as Implemented with test references
    - RFC 3581 (rport) - mark as Implemented (verify existing implementation in `sipx/sip/transport.py` or add if missing)
    - RFC 3856 + RFC 3858 (Presence) - mark as Implemented with test references
    - RFC 3428 (MESSAGE) - mark as Implemented with test references
    - RFC 5626 (Outbound) - mark as Implemented with test references
  - Add test file references for each requirement (e.g., `tests/test_rfc_prack.py`)
  - Add coverage percentages per RFC (if measurable)
  - Add notes on partial implementations or known limitations

  **Must NOT do**:
  - Do NOT claim full compliance without test evidence
  - Do NOT skip any targeted RFC
  - Do NOT add implementation details (this is a compliance doc)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none (documentation task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 9 (with Task 26)
  - **Blocks**: None (compliance matrix is final polish)
  - **Blocked By**: Tasks 20-25, 30, 31, 23 (needs all RFC implementations including Presence)

  **References**:
  - `.spec/rfc-compliance.md` - Existing compliance matrix to update
  - `tests/test_rfc_*.py` - Test files for RFC implementations
  - `tests/test_protocol_*.py` - Test files for protocol layer
  - `tests/test_transport_*.py` - Test files for transport layer (NEW transport layer: `sipx/transport/udp.py`, `sipx/transport/tcp.py`)

  **Acceptance Criteria**:
  - [ ] `.spec/rfc-compliance.md` updated with test evidence for all 10 targeted RFCs
  - [ ] Each RFC has test file references (e.g., `tests/test_rfc_prack.py`)
  - [ ] Each RFC has status (Implemented/Partial/Planned)
  - [ ] Each RFC has notes on limitations or partial implementations
  - [ ] `ruff format --check .spec/rfc-compliance.md` passes (if markdown formatter configured)
  - [ ] All "Implemented" RFCs have at least one test file reference
  - [ ] All "Partial" RFCs have explicit list of implemented vs missing features
  - [ ] No RFC marked "Implemented" without corresponding test evidence

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: RFC compliance matrix file exists and is updated
    Tool: Bash (file check)
    Steps:
      1. Run: test -f .spec/rfc-compliance.md && echo "File exists"
      2. Assert: stdout contains "File exists"
      3. Run: grep -c "Implemented" .spec/rfc-compliance.md
      4. Assert: count >= 9 (at least 9 RFCs marked as Implemented, RFC 3264 is Partial)
      5. Run: grep -c "tests/test_rfc_" .spec/rfc-compliance.md
      6. Assert: count >= 10 (test references for each RFC)
    Expected Result: Compliance matrix updated with test evidence
    Evidence: .omo/evidence/task-28-rfc-matrix-updated.txt

  Scenario: RFC matrix has correct status for each RFC
    Tool: Bash (grep check)
    Steps:
      1. Run: grep "RFC 3261" .spec/rfc-compliance.md | grep -c "Implemented"
      2. Assert: count >= 1 (RFC 3261 marked as Implemented)
      3. Run: grep "RFC 3262" .spec/rfc-compliance.md | grep -c "Implemented"
      4. Assert: count >= 1 (RFC 3262 marked as Implemented)
      5. Run: grep "RFC 3264" .spec/rfc-compliance.md | grep -c "Partial"
      6. Assert: count >= 1 (RFC 3264 marked as Partial)
      7. Run: grep "RFC 5626" .spec/rfc-compliance.md | grep -c "Implemented"
      8. Assert: count >= 1 (RFC 5626 marked as Implemented)
    Expected Result: Each targeted RFC has correct status (9 Implemented, 1 Partial)
    Evidence: .omo/evidence/task-28-rfc-matrix-status.txt
  ```

  **Commit**: YES
  - Message: `docs(rfc): update RFC compliance matrix with test evidence`
  - Files: `.spec/rfc-compliance.md`
  - Pre-commit: none (documentation only)

- [x] 29. Migration guide (old API → new API)

  **What to do**:
  - Create `MIGRATION.md` with comprehensive migration guide:
    - Overview of API changes (SipUac/SipUas → AsyncClient)
    - Side-by-side code examples (old API vs new API)
    - Common patterns migration (registration, INVITE, MESSAGE, handlers)
    - Breaking changes list (what's removed, what's changed)
    - Deprecation timeline (if any - but user said no deprecated code)
    - FAQ section (common migration questions)
  - Add migration examples for:
    - Simple REGISTER
    - INVITE with SDP (basic parsing/generation only)
    - MESSAGE sending
    - UAS handlers
    - Event hooks
    - Authentication
  - Ensure guide is clear and actionable

  **Must NOT do**:
  - Do NOT add deprecated code examples (user said no deprecated code)
  - Do NOT add excessive detail (keep guide concise and focused)
  - Do NOT add implementation details (focus on usage migration)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none (documentation task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 8 (with Tasks 23, 27)
  - **Blocks**: Task 32 (old API deletion needs migration guide complete)
  - **Blocked By**: Tasks 15-19 (needs AsyncClient and all public objects)

  **References**:
  - `sipx/client.py:AsyncClient` - New API
  - `docs/old-api-snapshot/uac.py:SipUac` - Old API snapshot (for comparison)
  - `docs/old-api-snapshot/uas.py:SipUas` - Old API snapshot (for comparison)
  - `docs/old-api-snapshot/ua.py:SipUserAgent` - Old API snapshot (for comparison)
  - Old examples in `sipx/examples/` - Old usage patterns

  **Acceptance Criteria**:
  - [ ] File created: `MIGRATION.md`
  - [ ] Migration guide covers all 5 major API changes: SipUac→AsyncClient, SipUas→AsyncClient handlers, SipUserAgent→removed, event_hooks→event_hooks, SDP handling
  - [ ] Side-by-side code examples for at least 5 common patterns: registration, INVITE, MESSAGE, SUBSCRIBE, event hooks
  - [ ] Breaking changes list includes at least 10 items with before/after examples
  - [ ] FAQ section addresses at least 8 common questions
  - [ ] `ruff format --check MIGRATION.md` passes (if markdown formatter configured)
  - [ ] All old API classes (SipUac, SipUas, SipUserAgent) have migration examples
  - [ ] All new API patterns (AsyncClient, Request, Response) have usage examples
  - [ ] Guide includes "Before/After" comparison for at least 5 common scenarios
  - [ ] Guide is at least 500 lines long (comprehensive coverage)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Migration guide file exists
    Tool: Bash (file check)
    Steps:
      1. Run: test -f MIGRATION.md && echo "File exists"
      2. Assert: stdout contains "File exists"
      3. Run: wc -l MIGRATION.md
      4. Assert: line count >= 500 (guide is comprehensive)
    Expected Result: Migration guide exists and has content
    Evidence: .omo/evidence/task-29-migration-guide-exists.txt

  Scenario: Migration guide has side-by-side examples
    Tool: Bash (grep check)
    Steps:
      1. Run: grep -c "Old API" MIGRATION.md
      2. Assert: count >= 5 (at least 5 old API examples)
      3. Run: grep -c "New API" MIGRATION.md
      4. Assert: count >= 5 (at least 5 new API examples)
      5. Run: grep -c "AsyncClient" MIGRATION.md
      6. Assert: count >= 10 (AsyncClient mentioned frequently)
    Expected Result: Migration guide has side-by-side examples
    Evidence: .omo/evidence/task-29-migration-examples.txt

  Scenario: Migration guide has breaking changes list
    Tool: Bash (grep check)
    Steps:
      1. Run: grep -c "Breaking Changes" MIGRATION.md
      2. Assert: count >= 1 (breaking changes section exists)
      3. Run: grep -c "SipUac" MIGRATION.md
      4. Assert: count >= 1 (SipUac mentioned in breaking changes)
      5. Run: grep -c "SipUas" MIGRATION.md
      6. Assert: count >= 1 (SipUas mentioned in breaking changes)
    Expected Result: Migration guide has breaking changes list
    Evidence: .omo/evidence/task-29-migration-breaking-changes.txt
  ```

  **Commit**: YES
  - Message: `docs(migration): add comprehensive migration guide from old API to new httpx-like API`
  - Files: `MIGRATION.md`
  - Pre-commit: none (documentation only)

- [x] 30. SDP parsing/generation (RFC 3264 basic support)

  **What to do**:
  - Enhance `sipx/sdp/model.py` and `sipx/sdp/parser.py` to provide basic SDP parsing/generation:
    - `parse_sdp(sdp_text: str) -> SessionDescription` - parse SDP text into structured model
    - `SessionDescription.to_sdp() -> str` - generate SDP text from model
    - Support basic SDP fields: v=, o=, s=, c=, t=, m=, a=
    - Support basic media types: audio, video
    - Support basic attributes: rtpmap, fmtp, sendrecv, sendonly, recvonly, inactive
  - Write tests in `tests/test_sdp_parsing.py` covering parsing and generation

  **Must NOT do**:
  - Do NOT implement full SDP offer/answer negotiation logic (RFC 3264 §6-7)
  - Do NOT add ICE candidate parsing (that's for NAT traversal, out of scope)
  - Do NOT add SRTP crypto attribute parsing (that's for security, out of scope)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none (SDP implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 10, 11, 12, 13)
  - **Blocks**: Task 28 (RFC compliance matrix needs SDP evidence)
  - **Blocked By**: Task 5 (needs Request/Response models)

  **References**:
  - `sipx/sdp/model.py:SessionDescription` - Existing SDP model to enhance
  - `sipx/sdp/parser.py:parse_sdp` - Existing parser to enhance
  - RFC 4566 - SDP: Session Description Protocol
  - RFC 3264 - An Offer/Answer Model with SDP (basic parsing only)

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_sdp_parsing.py`
  - [ ] `pytest tests/test_sdp_parsing.py` → PASS (15 tests, 0 failures)
  - [ ] `python -c "from sipx.sdp.parser import parse_sdp; from sipx.sdp.model import SessionDescription"` → exit 0
  - [ ] `parse_sdp()` correctly parses basic SDP with v=, o=, s=, c=, t=, m=, a= lines
  - [ ] `SessionDescription.to_sdp()` generates valid SDP text
  - [ ] Parser handles audio and video media types
  - [ ] Parser handles rtpmap, fmtp, sendrecv, sendonly, recvonly, inactive attributes
  - [ ] Parser raises `SdpParseError` for malformed SDP

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import SDP parser and model
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.sdp.parser import parse_sdp; from sipx.sdp.model import SessionDescription; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: SDP parser and model importable
    Evidence: .omo/evidence/task-30-import-sdp.txt

  Scenario: parse_sdp works for basic SDP
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.sdp.parser import parse_sdp; sdp_text = 'v=0\no=- 123 456 IN IP4 127.0.0.1\ns=-\nc=IN IP4 127.0.0.1\nt=0 0\nm=audio 5004 RTP/AVP 0\na=rtpmap:0 PCMU/8000\na=sendrecv'; sdp = parse_sdp(sdp_text); assert sdp.version == 0; assert sdp.origin.session_id == '123'; assert len(sdp.media) == 1; assert sdp.media[0].media_type == 'audio'; assert sdp.media[0].port == 5004; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: parse_sdp correctly parses basic SDP
    Evidence: .omo/evidence/task-30-parse-sdp.txt

  Scenario: SessionDescription.to_sdp works
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.sdp.model import SessionDescription, Origin, MediaDescription; sdp = SessionDescription(version=0, origin=Origin(username='-', session_id='123', session_version='456', nettype='IN', addrtype='IP4', address='127.0.0.1'), session_name='-', connection=None, time=None, media=[MediaDescription(media_type='audio', port=5004, proto='RTP/AVP', fmt=['0'], attributes=[('rtpmap', '0 PCMU/8000'), ('sendrecv', None)])]); sdp_text = sdp.to_sdp(); assert 'v=0' in sdp_text; assert 'm=audio 5004 RTP/AVP 0' in sdp_text; assert 'a=rtpmap:0 PCMU/8000' in sdp_text; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: SessionDescription.to_sdp generates valid SDP
    Evidence: .omo/evidence/task-30-to-sdp.txt
  ```

  **Commit**: YES
  - Message: `feat(sdp): implement basic SDP parsing/generation (RFC 3264/4566)`
  - Files: `sipx/sdp/model.py`, `sipx/sdp/parser.py`, `tests/test_sdp_parsing.py`
  - Pre-commit: `pytest tests/test_sdp_parsing.py && ruff check sipx/sdp/`

- [x] 31. RFC 3581 rport verification/implementation

  **What to do**:
  - Verify rport implementation in NEW transport layer (`sipx/transport/udp.py` and `sipx/transport/tcp.py`) or add if missing:
    - Check if `rport` parameter is added to Via header in outbound requests
    - Check if `rport` parameter is parsed from Via header in inbound responses
    - Check if `received` parameter is added to Via header when rport is present
    - Check if responses are sent to the source address/port (not the Via address) when rport is present
  - Write tests in `tests/test_rfc_rport.py` covering rport behavior
  - If implementation is missing or incomplete, add it to NEW transport layer

  **Must NOT do**:
  - Do NOT add STUN/TURN support (that's for NAT traversal, out of scope)
  - Do NOT add symmetric response routing beyond rport (keep it simple)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (verification/minor implementation)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 14)
  - **Blocks**: Task 28 (RFC compliance matrix needs rport evidence)
  - **Blocked By**: Task 6 (needs UdpTransport), Task 7 (needs TcpTransport)

  **References**:
  - `sipx/transport/udp.py:UdpTransport` - NEW transport to verify/enhance
  - `sipx/transport/tcp.py:TcpTransport` - NEW transport to verify/enhance
  - RFC 3581 - An Extension to SIP for Symmetric Response Routing

  **Acceptance Criteria**:
  - [ ] Test file created: `tests/test_rfc_rport.py`
  - [ ] `pytest tests/test_rfc_rport.py` → PASS (10 tests, 0 failures)
  - [ ] `python -c "from sipx.transport.udp import UdpTransport"` → exit 0
  - [ ] Outbound requests include `rport` parameter in Via header
  - [ ] Inbound responses parse `rport` and `received` parameters from Via header
  - [ ] Responses are sent to source address/port when rport is present
  - [ ] Existing tests still pass (no regression)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Import UdpTransport
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; from sipx.transport.base import TransportConfig; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: UdpTransport importable
    Evidence: .omo/evidence/task-31-import-transport.txt

  Scenario: Outbound requests include rport in Via
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; from sipx.transport.base import TransportConfig; from sipx.models import Request; config = TransportConfig(local_host='127.0.0.1', local_port=5060); transport = UdpTransport(config); req = Request(method='OPTIONS', uri='sip:bob@example.com', headers={}, body=None); transport.add_via_header(req); via = req.headers['Via']; assert 'rport' in via; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Outbound requests include rport parameter
    Evidence: .omo/evidence/task-31-rport-outbound.txt

  Scenario: Inbound responses parse rport and received
    Tool: Bash (python REPL)
    Steps:
      1. Run: python -c "from sipx.transport.udp import UdpTransport; from sipx.transport.base import TransportConfig; from sipx.models import Response; config = TransportConfig(local_host='127.0.0.1', local_port=5060); transport = UdpTransport(config); resp = Response(200, 'OK', headers={'Via': 'SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bK123;rport=5060;received=192.168.1.1'}, body=None); rport, received = transport.parse_via_rport(resp); assert rport == 5060; assert received == '192.168.1.1'; print('OK')"
      2. Assert: exit code 0, stdout contains "OK"
    Expected Result: Inbound responses parse rport and received parameters
    Evidence: .omo/evidence/task-31-rport-inbound.txt
  ```

  **Commit**: YES
  - Message: `feat(transport): verify/implement RFC 3581 rport support in NEW transport layer`
  - Files: `sipx/transport/udp.py`, `sipx/transport/tcp.py`, `tests/test_rfc_rport.py`
  - Pre-commit: `pytest tests/test_rfc_rport.py && ruff check sipx/transport/`

- [x] 32. Delete old API files and migrate remaining imports

  **What to do**:
  - Delete `sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py`
  - Update `sipx/__init__.py` to remove old exports
  - Grep for any remaining imports of old API in entire repo and migrate to new API:
    - `apps/scenarios/examples/mizu/mizu_common.py`
    - `apps/scenarios/examples/sip/call_with_dtmf.py`
    - `apps/harness/tests/test_recorder_reports_profiles.py`
    - `apps/asterisk/tests/test_asterisk_integration.py`
    - Any other files found by grep
  - Delete or rewrite `tests/test_uac_uas.py` to use new API
  - Verify all tests still pass after migration

  **Must NOT do**:
  - Do NOT delete old API files before Tasks 16-19 are complete
  - Do NOT leave any imports of old API in the codebase
  - Do NOT break existing tests during migration

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none (cleanup task)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 10 (sequential after Wave 9)
  - **Blocks**: None (final cleanup)
  - **Blocked By**: Tasks 16, 17, 18, 19, 26, 27, 28, 29 (UAC/UAS methods, docstrings, examples, migration guide must be complete)

  **References**:
  - `docs/old-api-snapshot/` - Snapshot of old API files (created in Task 15)
  - `sipx/client.py:AsyncClient` - New API to migrate to
  - `MIGRATION.md` - Migration guide (created in Task 29)

  **Acceptance Criteria**:
  - [ ] Old API files deleted: `sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py`
  - [ ] `sipx/__init__.py` updated to remove old exports
  - [ ] No remaining imports of old API in repo (verified by grep)
  - [ ] All app imports migrated to new API
  - [ ] `tests/test_uac_uas.py` deleted or rewritten to use new API
  - [ ] `pytest --cov=sipx --cov-fail-under=90` → exit 0, 90%+ coverage
  - [ ] `ruff check .` → exit 0
  - [ ] `ruff format --check .` → exit 0
  - [ ] `uv run ty check` → exit 0

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Old API files deleted
    Tool: Bash (file check)
    Steps:
      1. Run: test ! -f sipx/uac.py && test ! -f sipx/uas.py && test ! -f sipx/ua.py && echo "Files deleted"
      2. Assert: stdout contains "Files deleted"
    Expected Result: Old API files no longer exist
    Evidence: .omo/evidence/task-32-files-deleted.txt

  Scenario: No remaining old API imports
    Tool: Bash (grep check)
    Steps:
      1. Run: grep -r "from sipx.uac import\|from sipx.uas import\|from sipx.ua import\|from sipx import SipUac\|from sipx import SipUas\|from sipx import SipUserAgent" --include="*.py" . || echo "No imports found"
      2. Assert: stdout contains "No imports found"
    Expected Result: No imports of old API in codebase
    Evidence: .omo/evidence/task-32-no-old-imports.txt

  Scenario: All tests pass after migration
    Tool: Bash (pytest)
    Steps:
      1. Run: pytest --cov=sipx --cov-fail-under=90
      2. Assert: exit code 0
      3. Run: ruff check .
      4. Assert: exit code 0
      5. Run: ruff format --check .
      6. Assert: exit code 0
      7. Run: uv run ty check
      8. Assert: exit code 0
    Expected Result: All tests pass with 90%+ coverage, no linting errors
    Evidence: .omo/evidence/task-32-tests-pass.txt
  ```

  **Commit**: YES
  - Message: `refactor!: delete old API files and migrate all imports to AsyncClient`
  - Files: `sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py`, `sipx/__init__.py`, `apps/scenarios/examples/mizu/mizu_common.py`, `apps/scenarios/examples/sip/call_with_dtmf.py`, `apps/harness/tests/test_recorder_reports_profiles.py`, `apps/asterisk/tests/test_asterisk_integration.py`, `tests/test_uac_uas.py`, `pyproject.toml`, `CHANGELOG.md`, `TODO.md`
  - Pre-commit: `pytest --cov=sipx --cov-fail-under=90 && ruff check . && ruff format --check . && uv run ty check`
  - **Note**: Per AGENTS.md, update version in pyproject.toml, add entry to CHANGELOG.md, update TODO.md with completed task

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  
  **Acceptance Criteria**:
  - [ ] All "Must Have" items verified (implementation exists and works)
  - [ ] All "Must NOT Have" items verified (forbidden patterns absent)
  - [ ] Evidence files exist for all tasks in `.omo/evidence/`
  - [ ] Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`
  - [ ] VERDICT must be APPROVE to proceed

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Plan compliance audit execution
    Tool: Oracle agent
    Steps:
      1. Oracle reads .omo/plans/sipx-overhaul.md end-to-end
      2. For each "Must Have" item: verify implementation exists (read file, run command)
      3. For each "Must NOT Have" item: search codebase for forbidden patterns
      4. Check evidence files exist in .omo/evidence/
      5. Compare deliverables against plan
      6. Output structured verdict
    Expected Result: VERDICT: APPROVE
    Evidence: .omo/evidence/final-qa/f1-plan-compliance.txt
  ```

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check .` + `ruff format --check .` + `uv run ty check` + `pytest --cov=sipx --cov-fail-under=90`. Review all changed files for: `# type: ignore`, empty catches, `print()` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  
  **Acceptance Criteria**:
  - [ ] `ruff check .` → exit 0
  - [ ] `ruff format --check .` → exit 0
  - [ ] `uv run ty check` → exit 0
  - [ ] `pytest --cov=sipx --cov-fail-under=90` → exit 0, coverage >= 90%
  - [ ] No `# type: ignore` comments (except justified)
  - [ ] No empty `except:` clauses
  - [ ] No `print()` statements in production code (only in examples/tests)
  - [ ] No commented-out code blocks
  - [ ] No unused imports
  - [ ] No new god modules (files >500 lines without justification)
  - [ ] No over-fragmentation (excessive files <50 lines without justification)
  - [ ] Output: `Lint [PASS/FAIL] | Format [PASS/FAIL] | TypeCheck [PASS/FAIL] | Tests [N pass/N fail] | Coverage [N%] | Files [N clean/N issues] | Modularity [PASS/FAIL] | VERDICT`
  - [ ] VERDICT must be APPROVE to proceed

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Code quality review execution
    Tool: Bash (shell commands)
    Steps:
      1. Run: ruff check .
      2. Assert: exit code 0
      3. Run: ruff format --check .
      4. Assert: exit code 0
      5. Run: uv run ty check
      6. Assert: exit code 0
      7. Run: pytest --cov=sipx --cov-fail-under=90
      8. Assert: exit code 0, coverage >= 90%
      9. Grep all changed files for forbidden patterns
      10. Assert: no forbidden patterns found
    Expected Result: All quality checks pass
    Evidence: .omo/evidence/final-qa/f2-code-quality.txt
  ```

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task (1-32) — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.omo/evidence/final-qa/`.
  
  **Acceptance Criteria**:
  - [ ] All QA scenarios from Tasks 1-32 executed successfully
  - [ ] Cross-task integration tested (e.g., AsyncClient + Transport + Protocol + RFC)
  - [ ] Edge cases tested: invalid URIs, malformed messages, timeouts, network errors
  - [ ] Evidence files saved to `.omo/evidence/final-qa/`
  - [ ] Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`
  - [ ] VERDICT must be APPROVE to proceed

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Real QA execution (agent-only)
    Tool: Bash (python REPL)
    Steps:
      1. Create fresh worktree: git worktree add ../sipx-qa-test
      2. Change to worktree: cd ../sipx-qa-test
      3. Execute QA scenarios from Tasks 1-32 (see each task's QA Scenarios section):
         - Task 1: Import core types, Type aliases are correct
         - Task 2: Import exception hierarchy, Exception attributes work correctly, Exception hierarchy is correct
         - Task 3: RFC compliance matrix file exists and is valid, RFC matrix has correct table structure
         - Task 4: Import transport interface, Transport is abstract, TransportConfig is dataclass
         - Task 5: Import Request/Response models, Request construction works, Response.from_request helper works
         - Task 6: Import UdpTransport, UdpTransport implements Transport interface, UdpTransport transport_type is correct
         - Task 7: Import TcpTransport, TcpTransport implements Transport interface, TcpTransport transport_type is correct
         - Task 8: Import TlsTransport and TlsConfig, TlsTransport implements Transport interface, TlsConfig is dataclass
         - Task 9: Import transport registry, Default transports are registered, create_transport factory works
         - Task 10: Import transaction state machines, Client transaction state transitions work, Invalid state transition raises TransactionError
         - Task 11: Import dialog state machine, Dialog creation from INVITE works, Dialog state transitions work
         - Task 12: Import auth flow, Auth flow generator works, Digest authentication works
         - Task 13: Import event hooks, Hook registration and execution works, Hook errors do not break flow
         - Task 14: Import provisional stream, Provisional streaming works, Provisional filtering works
         - Task 15: Import AsyncClient, AsyncClient lifecycle works, AsyncClient transport selection works
         - Task 16: Import AsyncClient with UAC methods, invite method works, register method works
         - Task 17: Import AsyncClient with UAS handlers, on_invite handler registration works, on_message handler registration works
         - Task 18: Import ClientConfig, ClientConfig is dataclass with defaults, Config merge works
         - Task 19: AsyncClient context manager works, aclose method works, is_closed property works
         - Task 20: Import PrackHandler, PRACK generation works for reliable 1xx, RSeq tracking detects duplicates
         - Task 21: Import SipDnsResolver, DNS resolution works with mocked DNS, Transport selection works
         - Task 22: Import event notification classes, SubscriptionDialog creation works, Subscription state transitions work
         - Task 23: Import presence classes, PIDF XML parsing works, PIDF XML generation works
         - Task 24: AsyncClient has message method, MESSAGE sending works (mocked), MESSAGE Content-Type handling works
         - Task 25: Import outbound classes, instance-id generation works, Path header generation works
         - Task 26: AsyncClient has comprehensive docstring, All public methods have docstrings, Exception hierarchy has docstrings
         - Task 27: register example runs, invite example runs, message example runs, subscribe example runs
         - Task 28: RFC compliance matrix file exists and is updated, RFC matrix has correct status for each RFC
         - Task 29: Migration guide file exists, Migration guide has side-by-side examples, Migration guide has breaking changes list
          - Task 30: Import SDP parser and model, parse_sdp works for basic SDP, SessionDescription.to_sdp works
          - Task 31: Import UdpTransport, Outbound requests include rport in Via, Inbound responses parse rport and received
          - Task 32: Old API files deleted, No remaining old API imports, All tests pass after migration
      4. Test cross-task integration (e.g., AsyncClient + Transport + Protocol + RFC)
      5. Test edge cases (invalid URIs, malformed messages, timeouts, network errors)
      6. Verify all evidence files exist in .omo/evidence/ (one per QA scenario)
      7. Save summary to .omo/evidence/final-qa/f3-qa-summary.txt
      8. Clean up worktree: cd ../sipx && git worktree remove ../sipx-qa-test
    Expected Result: All 32 tasks' QA scenarios pass, all evidence files exist
    Evidence: .omo/evidence/final-qa/f3-qa-summary.txt
  ```

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task (1-32): read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  
  **Acceptance Criteria**:
  - [ ] All 32 tasks verified: "What to do" matches actual implementation
  - [ ] No missing features (everything in spec was built)
  - [ ] No scope creep (nothing beyond spec was built)
  - [ ] "Must NOT do" compliance verified for all tasks
  - [ ] No cross-task contamination (Task N did not touch Task M's files)
  - [ ] No unaccounted changes (all changes trace to a task)
  - [ ] No new god modules (files >500 lines without justification)
  - [ ] No over-fragmentation (excessive files <50 lines without justification)
  - [ ] Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | Modularity [PASS/FAIL] | VERDICT`
  - [ ] VERDICT must be APPROVE to proceed

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Scope fidelity check execution
    Tool: Deep agent
    Steps:
      1. For each task (1-32): read "What to do" section
      2. Read actual diff (git log/diff) for that task
      3. Verify 1:1 match between spec and implementation
      4. Check "Must NOT do" compliance
      5. Detect cross-task contamination
      6. Flag unaccounted changes
      7. Output structured verdict
    Expected Result: VERDICT: APPROVE
    Evidence: .omo/evidence/final-qa/f4-scope-fidelity.txt
  ```

---

## Commit Strategy

**Each task has its own individual commit** (not grouped by wave). This provides:
- Granular history for easier debugging and reverting
- Clear traceability between tasks and commits
- Ability to cherry-pick specific features

Each commit MUST include:
- Implementation files (as specified in task)
- Test files (as specified in task)
- **State/version files** (per AGENTS.md): `pyproject.toml` (version bump), `CHANGELOG.md` (entry), `TODO.md` (update), `.spec/state.md`, `.spec/checks.md`, `.spec/handoff.md`

**Note**: Even if a task's file list doesn't explicitly mention state/version files, they MUST be included in every commit per AGENTS.md requirements. The task file lists show implementation-specific files; state/version files are always required.

See individual task specifications for exact commit messages and implementation file lists.

---

## Success Criteria

### Verification Commands
```bash
python -c "from sipx import AsyncClient, Request, Response"  # Expected: exit 0
pytest --cov=sipx --cov-fail-under=90  # Expected: exit 0, 90%+ coverage
ruff check .  # Expected: exit 0
ruff format --check .  # Expected: exit 0
uv run ty check  # Expected: exit 0
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (90%+ coverage)
- [ ] All examples run successfully
- [ ] RFC compliance matrix complete with test evidence
- [ ] All public API objects have docstrings
- [ ] Migration guide available

---

## High Accuracy Verification

**Status**: Momus OKAY (attempt 11, pre-final-edits)

**Note**: Final edits after Momus OKAY were minor consistency fixes:
- Aligned critical path wording (TL;DR vs detailed)
- Added Wave 10 / Task 32 to Agent Dispatch Summary
- Corrected Task 1 dependency metadata (blocks Task 5 only, not 6/7/8)
- These edits do not affect plan validity or execution readiness.

**Verdict**: Plan is ready for execution by `/start-work`.
