# sipx — Test Coverage + TUI Dashboard

## Context

v0.0.5 shipped with PRACK, forking, REFER, presence, B2BUA, and Timer G.
682 tests, ~60% coverage. Two goals now:

1. Close test coverage gaps across 7 modules (~190 new tests, target >80%)
2. Build a TUI dashboard (`sipx dashboard`) using Textual for live SIP monitoring

---

## Phase 1: Test Coverage (independent tasks, can parallelize)

### Task 1: ISUP encode/decode roundtrips (0% → ~95%)

**Create:** `tests/test_isup.py` (~35 tests)

Target: `sipx/contrib/_isup.py` — pure functions, zero deps.

- `TestEncodeDecodeCalledParty` — even/odd digits, all NAI values, empty string, single digit
- `TestEncodeDecodeCallingParty` — screening/presentation roundtrip, all indicator combos
- `TestEncodDecodeCauseIndicators` — normal clearing (16), different locations/standards, short data
- `TestISUPMessageRoundtrip` — IAM, ACM, ANM, REL, RLC, CPG to_bytes/from_bytes
- `TestISUPMessageFactories` — create_iam with/without calling, get_called_party/get_cause helpers
- `TestISUPEnums` — value spot-checks against Q.763

### Task 2: Transport tests with socket mocking (0% → ~70%)

**Create:** `tests/transports/test_tcp.py` (~18 tests)
**Create:** `tests/transports/test_tls.py` (~12 tests)

Target: `sipx/transports/_tcp.py`, `_tls.py`

Use `unittest.mock.patch("socket.socket")` — TCPTransport calls `_initialize_socket()` in `__init__`, so patch before instantiation.

- TCP: creation+bind, send with partial sends, receive with Content-Length framing, connect/reconnect, close/context manager
- TLS: same patterns + SSL context creation, cert/key/ca_file from TransportConfig
- Async variants: mock `asyncio.open_connection`, writer.write+drain, reader.read

### Task 3: FSM timer edge cases

**Modify:** `tests/test_fsm.py` (add ~20 tests)

Already has 53 tests. Add edge cases:

- Timer G fires `_retransmit_fn` callback in PROCEEDING state
- Timer G doubles interval up to T2=4s
- Timer H → TERMINATED on IST
- Timer I/J/K expiry → TERMINATED
- AsyncTimerManager: start/cancel/cancel_all/active_timers, async callback support
- StateManager.cleanup_transactions/cleanup_dialogs with mixed ages

### Task 4: RTP session lifecycle (57% → ~85%)

**Modify:** `tests/media/test_rtp.py` (add ~15 tests)

Mock `socket.socket` for UDP to avoid real binding.

- RTPSession start/stop/context manager
- send_packet calls socket.sendto
- send_audio encodes and increments seq/timestamp
- recv_packet/recv_audio from buffer
- from_sdp factory extracts remote IP/port/codec
- DTMFHelper lazy creation

### Task 5: sipi_br remaining coverage

**Modify:** `tests/test_sipi_br.py` (add ~12 tests)

Already has 43 tests. Add:

- ATI.query() with 480/404/301 responses
- AsyncATI.query() with mock async client (ported/not-ported/None)
- SipIBR static methods called directly: add_preferred_identity, add_charging_function_addresses, add_reason/get_reason

---

## Phase 2: Client/Server async tests (after Phase 1 conftest setup)

### Task 6: AsyncMockTransport fixture

**Modify:** `tests/conftest.py` — add `AsyncMockTransport(AsyncBaseTransport)` with:
- `queue_response(data: bytes)`
- `async send(data, destination)` → appends to `self.sent`
- `async receive(timeout)` → pops from queue or raises TimeoutError
- `async close()` → sets `_closed`
- `@pytest.fixture async_mock_transport`

### Task 7: Client async + advanced sync tests (33% → ~65%)

**Create:** `tests/test_async_client.py` (~20 tests)
**Modify:** `tests/test_client.py` (add ~15 tests)

- AsyncClient: creation, context manager, invite/register/bye with AsyncMockTransport
- AsyncClient: auth retry (queue 401 then 200), publish with SIP-ETag
- Sync Client additions: invite with SDP body, register with auth, refer, publish

### Task 8: Server async + loopback tests (58% → ~80%)

**Create:** `tests/test_async_server.py` (~15 tests)
**Modify:** `tests/test_server.py` (add ~10 tests)

- AsyncSIPServer: handler registration, datagram processing (feed raw bytes, check response)
- AsyncSIPServer: async handler support, RSeq generation, auto 100 Trying
- Sync loopback: server + client exchanging OPTIONS via mocked transport
- DI resolution with Annotated parameters

---

## Phase 3: TUI SIP Client (inspired by Posting for HTTP)

Goal: A full interactive SIP client TUI — like Posting (posting.sh)
is for HTTP, but for SIP. Compose requests, send, see responses,
manage saved profiles.

### Task 9: Add textual optional dependency

**Modify:** `pyproject.toml`

```toml
[project.optional-dependencies]
tui = ["textual>=8.2.1"]
```

### Task 10: TUI app module

**Create:** `sipx/tui/__init__.py` — lazy import guard + `SipxApp` export
**Create:** `sipx/tui/_app.py` — main `SipxApp(textual.app.App)`
**Create:** `sipx/tui/_widgets.py` — custom widgets
**Create:** `sipx/tui/_styles.py` — SCSS/CSS theming
**Create:** `sipx/tui/_collection.py` — saved profiles/roles (YAML)
**Create:** `sipx/tui/_flows.py` — flow YAML parser + FlowRunner engine

Architecture (Posting-style):

```
┌──────────────────────────────────────────────────────────┐
│ sipx — SIP Workbench                            v0.0.5   │
├──────────────┬───────────────────────────────────────────┤
│ Collection   │  ┌─ Request ────────────────────────────┐ │
│              │  │ [INVITE ▾] [sip:bob@192.168.1.1    ] │ │
│ ▾ UAC       │  ├─ Headers ─┬─ Body ─┬─ Auth ─────────┤ │
│   basic-call │  │ From: ... │        │                │ │
│   softphone  │  │ To:   ... │  SDP   │ user: alice    │ │
│ ▾ UAS       │  │ Contact:  │  body  │ pass: ****     │ │
│   echo       │  │ Call-ID:  │        │                │ │
│   ivr-menu   │  └───────────┴────────┴────────────────┘ │
│ ▾ B2BUA     │  ┌─ Response ───────────────────────────┐ │
│   bridge     │  │ 200 OK                       1.2s   │ │
│ ▾ Flows     │  ├─ Headers ─┬─ Body ─┬─ Log ──────────┤ │
│   dtmf-test  │  │ Via: ...  │        │ >>> INVITE     │ │
│   load-test  │  │ To: ...   │  SDP   │ <<< 100 Trying │ │
│   audio-play │  │ Contact:  │  resp  │ <<< 200 OK     │ │
│ ▾ Profiles  │  │           │        │ >>> ACK         │ │
│   asterisk   │  └───────────┴────────┴────────────────┘ │
├──────────────────────────────────────────────────────────┤
│ ^J Send  ^T Method  ^H Sidebar  ^S Save  ^R Run Flow   │
└──────────────────────────────────────────────────────────┘
```

**Key components:**

`_app.py` — `SipxApp(App)`:
- Main screen with docked sidebar + tabbed workspace
- Key bindings: `ctrl+j` execute/send, `ctrl+t` new tab, `ctrl+h` toggle sidebar, `ctrl+s` save, `q` quit
- Creates `AsyncClient` + `AsyncSIPServer` internally (workers)
- Reactive state: active role, current flow, response log

`_widgets.py`:
- `MethodSelector(Select)` — INVITE, REGISTER, OPTIONS, BYE, MESSAGE, etc.
- `UriBar(Input)` — SIP URI input with validation
- `HeadersTable(DataTable)` — editable key-value header pairs
- `BodyEditor(TextArea)` — SDP/text body editor
- `AuthPanel(Container)` — username/password/realm
- `ResponseStatus(Static)` — status code + reason + elapsed
- `ResponseHeaders(DataTable)` — read-only response headers
- `ResponseBody(TextArea)` — read-only SDP/body viewer
- `MessageLog(RichLog)` — SIP transaction trace (>>> sent, <<< recv)
- `CollectionTree(Tree)` — roles/profiles/flows sidebar
- `FlowEditor(TextArea)` — YAML/Python flow script editor
- `FlowRunner(Container)` — flow execution status + step progress

`_collection.py` — Collection organized by role:
```yaml
# ~/.config/sipx/collection/
collection/
├── uac/                    # Client roles
│   ├── basic-call.yaml     # Simple INVITE → ACK → BYE
│   └── softphone.yaml      # Full softphone profile
├── uas/                    # Server roles
│   ├── echo-server.yaml    # Answer all, echo audio
│   └── ivr-menu.yaml       # IVR with DTMF menus
├── b2bua/                  # Bridge roles
│   └── proxy-bridge.yaml   # Forward A→B
├── flows/                  # Programmable test flows
│   ├── load-test.yaml      # N concurrent calls
│   ├── dtmf-test.yaml      # Call + send DTMF + hangup
│   └── audio-play.yaml     # Call + play WAV + hangup
└── profiles/               # Reusable connection profiles
    ├── asterisk-local.yaml
    └── freeswitch.yaml
```

Each YAML file is a `SipProfile`:
```yaml
name: softphone-test
role: uac
uri: sip:bob@192.168.1.1:5060
auth:
  username: alice
  password: secret123
headers:
  User-Agent: sipx-tui/0.0.5
transport: UDP
```

`_flows.py` — Programmable interaction flows:

Flows are step-by-step SIP interaction scripts. Users define
them in YAML and run them from the TUI.

```yaml
name: dtmf-test
description: Call, wait for answer, send DTMF, hangup
steps:
  - action: invite
    uri: sip:ivr@192.168.1.1
    body: auto-sdp         # auto-generate SDP offer
    timeout: 10

  - action: wait
    for: answer             # wait for 200 OK
    timeout: 30

  - action: ack

  - action: sleep
    duration: 1.0

  - action: dtmf
    digits: "1234#"
    method: rfc4733         # or sip-info, or inband
    interval: 0.2

  - action: sleep
    duration: 2.0

  - action: audio
    file: prompts/greeting.wav
    # or: tts: "Hello world"

  - action: bye
```

```yaml
name: uas-ivr
description: Answer calls with IVR menu
role: uas
listen:
  host: 0.0.0.0
  port: 5060
on_invite:
  - action: answer
    body: auto-sdp
  - action: audio
    file: prompts/welcome.wav
  - action: dtmf_collect
    max_digits: 4
    timeout: 10
    store_as: pin
  - action: condition
    if: "pin == '1234'"
    then:
      - action: audio
        file: prompts/success.wav
      - action: bye
    else:
      - action: audio
        file: prompts/invalid.wav
      - action: bye
```

Flow engine: `FlowRunner` interprets YAML steps, maps actions
to `AsyncClient`/`AsyncSIPServer` method calls:
- `invite` → `client.invite()`
- `ack` → `client.ack()`
- `bye` → `client.bye()`
- `dtmf` → `DTMFSender.send_rfc4733()` / `client.info()`
- `audio` → `AudioPlayer.play()` via RTP
- `wait` → poll for response with condition
- `sleep` → `asyncio.sleep()`
- `answer` → server handler returns `request.ok()`
- `dtmf_collect` → `DTMFCollector` with timeout
- `condition` → evaluate expression against flow variables

`_styles.py`:
- Textual SCSS for layout, dark theme default
- Clean aesthetic inspired by Posting

**SIP-specific features:**
- Auto-generate headers (Via, Call-ID, CSeq, Max-Forwards)
- SDP helper: `SDPBody.create_offer()` template button
- Dialog tracking: INVITE 200 OK → auto-enable ACK/BYE
- Auth auto-retry on 401/407
- Live RTP stats during active call (packets, jitter)
- Flow execution with step-by-step progress indicator

**Data flow for interactive mode:**
1. User selects role (UAC/UAS/B2BUA) from sidebar
2. Composes request or configures server behavior
3. `ctrl+j` → execute via AsyncClient/AsyncSIPServer
4. Response panel + message log update in real-time
5. Save profile via `ctrl+s` → YAML in collection dir

**Data flow for flow mode:**
1. User selects flow from sidebar
2. Opens in FlowEditor tab (editable YAML)
3. `ctrl+j` → FlowRunner executes step by step
4. Progress bar + step status updates in real-time
5. Message log shows all SIP traffic during flow

### Task 11: Wire CLI command

**Modify:** `sipx/main.py`

```python
@app.command()
def tui():
    """Launch interactive SIP client (TUI)."""
    try:
        from .tui import SipxApp
    except ImportError:
        console.print("[red]pip install sipx[tui][/red]")
        raise typer.Exit(1)
    SipxApp().run()
```

### Task 12: TUI tests (~15 tests)

**Create:** `tests/test_tui.py`
**Create:** `tests/test_flows.py`

Use `textual.testing` + `pytest.importorskip("textual")`.

TUI tests:
- App mounts without error
- MethodSelector contains all 12 SIP methods
- UriBar accepts valid SIP URIs
- HeadersTable add/remove rows
- Send triggers AsyncClient (mocked)
- Response panel populates on mock response
- MessageLog captures send/recv entries
- CollectionTree loads roles (UAC/UAS/B2BUA/Flows)
- Key bindings work (ctrl+j, ctrl+t, ctrl+h, ctrl+r)
- Quit exits cleanly

Flow engine tests (no textual dependency):
- Parse simple UAC flow YAML (invite → wait → bye)
- Parse UAS flow YAML (on_invite → answer → bye)
- Parse flow with DTMF steps
- Parse flow with audio steps
- Parse flow with conditions
- FlowRunner executes steps against mock client
- FlowRunner handles timeout in wait step
- Invalid YAML raises clear error

---

## Execution Order

```
Phase 1 (parallel): Tasks 1, 2, 3, 4, 5
Phase 2 (sequential): Task 6 → Tasks 7, 8
Phase 3 (sequential): Task 9 → 10 → 11 → 12
```

Total new tests: ~190 (Phase 1+2) + ~10 (Phase 3) = ~200
Projected total: 682 + 200 = ~882 tests

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -v --tb=short
uv run pytest --cov=sipx --cov-report=term-missing  # verify >80%
uv run sipx tui  # manual TUI test (interactive SIP client)
```
