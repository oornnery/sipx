#!/usr/bin/env python3
"""
sipx — Comprehensive Library Demo

Exercises every component of the sipx library:
  - Client (sync) with all SIP methods
  - SIPServer with custom handlers
  - Events + @event_handler decorator
  - Auth.Digest + retry_with_auth + per-request auth
  - SDPBody: create_offer, create_answer, codec analysis
  - Headers: case-insensitive, compact forms, RFC ordering
  - MessageParser: parse raw bytes, URI parsing
  - FSM: StateManager statistics, Transaction/Dialog tracking
  - TransportConfig + TransportAddress
  - Constants: HEADERS, HEADERS_COMPACT, REASON_PHRASES
  - Logging: console + logger

Usage:
    uv run python examples/asterisk_demo.py

Requires:
    cd docker/asterisk && docker-compose up -d
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# sipx imports — every public component
# ---------------------------------------------------------------------------

from sipx import (
    # Client / Server
    Client,
    # Events
    Events,
    EventContext,
    event_handler,
    # Auth
    Auth,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    # Models
    Request,
    Response,
    MessageParser,
    Headers,
    HeaderParser,
    SDPBody,
    BodyParser,
    # FSM
    StateManager,
    DialogState,
    # Transport
    TransportAddress,
    # Utils / Constants
    console,
    EOL,
    SCHEME,
    VERSION,
    BRANCH,
    HEADERS,
    HEADERS_COMPACT,
    REASON_PHRASES,
)
from sipx._server import SIPServer

from rich.table import Table
from rich import box


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 5060


@dataclass
class User:
    username: str
    password: str
    client_port: int


USERS = [
    User("1111", "1111xxx", 5061),
    User("2222", "2222xxx", 5062),
    User("3333", "3333xxx", 5063),
]


# ---------------------------------------------------------------------------
# Events — full showcase
# ---------------------------------------------------------------------------


class FullEvents(Events):
    """Demonstrates every event pattern."""

    def __init__(self):
        super().__init__()
        self.request_count = 0
        self.response_count = 0
        self.early_media = False
        self.auth_challenges = 0
        self.call_accepted = False
        self.codecs: dict[str, list[str]] = {}

    # --- Global hooks ---

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Intercept every outgoing request."""
        self.request_count += 1
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Intercept every incoming response."""
        self.response_count += 1
        return response

    # --- Method + status handlers ---

    @event_handler("REGISTER", status=200)
    def on_registered(self, request, response, context):
        contact = response.headers.get("Contact", "")
        if "expires=" in contact:
            exp = contact.split("expires=")[1].split(";")[0]
            console.print(f"  [green]registered (expires={exp})[/green]")

    @event_handler("OPTIONS", status=200)
    def on_options_ok(self, request, response, context):
        allow = response.headers.get("Allow", "")
        if allow:
            console.print(f"  [green]server allows: {allow}[/green]")

    @event_handler("INVITE", status=183)
    def on_early_media(self, request, response, context):
        self.early_media = True
        if response.body and response.body.has_early_media():
            console.print("  [magenta]early media detected (183)[/magenta]")

    @event_handler("INVITE", status=200)
    def on_call_accepted(self, request, response, context):
        self.call_accepted = True
        if response.body:
            self.codecs = response.body.get_codecs_summary()
            for media, codecs in self.codecs.items():
                console.print(f"  [cyan]{media}: {', '.join(codecs)}[/cyan]")

    @event_handler(status=(401, 407))
    def on_auth_challenge(self, request, response, context):
        self.auth_challenges += 1

    @event_handler("BYE", status=200)
    def on_bye_ok(self, request, response, context):
        console.print("  [green]call terminated[/green]")

    @event_handler("MESSAGE", status=(200, 202))
    def on_message_ok(self, request, response, context):
        console.print("  [green]message delivered[/green]")

    @event_handler(("SUBSCRIBE", "NOTIFY", "REFER", "INFO", "UPDATE", "PUBLISH"))
    def on_extension_method(self, request, response, context):
        if response and response.is_success:
            console.print(f"  [green]{request.method} ok[/green]")

    # --- Multi-method filter ---

    @event_handler(("INVITE", "REGISTER"), status=200)
    def on_critical_success(self, request, response, context):
        """Fires on both INVITE 200 and REGISTER 200."""
        context.metadata["critical_success"] = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def auth_request(client: Client, response: Response) -> Response:
    """Retry with auth if challenged."""
    if response and response.status_code in (401, 407):
        return client.retry_with_auth(response) or response
    return response


def make_sdp(client: Client, username: str, port: int = 8000) -> SDPBody:
    """Build a standard audio SDP offer with codecs and telephone-event."""
    return SDPBody.create_offer(
        session_name=f"sipx-{username}",
        origin_username=username,
        origin_address=client.local_address.host,
        connection_address=client.local_address.host,
        media_specs=[
            {
                "media": "audio",
                "port": port,
                "codecs": [
                    {"payload": "0", "name": "PCMU", "rate": "8000"},
                    {"payload": "8", "name": "PCMA", "rate": "8000"},
                    {
                        "payload": "101",
                        "name": "telephone-event",
                        "rate": "8000",
                        "fmtp": "0-16",
                    },
                ],
            }
        ],
    )


def contact_header(username: str, client: Client) -> dict:
    addr = client.local_address
    return {"Contact": f"<sip:{username}@{addr.host}:{addr.port}>"}


# ---------------------------------------------------------------------------
# Section 0: Constants, Types, Parsing (no network)
# ---------------------------------------------------------------------------


def demo_constants_and_parsing() -> dict:
    """Demonstrate Headers, MessageParser, constants — no Asterisk needed."""
    results = {}

    # --- Constants ---
    console.print("\n[bold]0.1 Constants[/bold]")
    console.print(f"  EOL repr: {EOL!r}")
    console.print(f"  SCHEME/VERSION: {SCHEME}/{VERSION}")
    console.print(f"  BRANCH prefix: {BRANCH}")
    console.print(f"  Known headers: {len(HEADERS)}")
    console.print(f"  Compact forms: {len(HEADERS_COMPACT)}")
    console.print(f"  Reason phrases: {len(REASON_PHRASES)}")
    console.print(f"  200 = {REASON_PHRASES[200]}, 486 = {REASON_PHRASES[486]}")
    results["constants"] = len(HEADERS) > 40 and len(REASON_PHRASES) > 50

    # --- Headers ---
    console.print("\n[bold]0.2 Headers[/bold]")
    h = Headers(
        {
            "Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bKtest",
            "from": '"Alice" <sip:alice@example.com>;tag=abc123',
            "To": "<sip:bob@example.com>",
            "call-id": "unique-id@10.0.0.1",
            "CSeq": "1 INVITE",
            "content-type": "application/sdp",
            "Content-Length": "0",
        }
    )
    # Case-insensitive access
    assert h["FROM"] == h["from"] == h["From"]
    # Compact form access
    assert h["f"] == h["From"]  # f -> From
    assert h["i"] == h["Call-ID"]  # i -> Call-ID
    assert h["c"] == h["Content-Type"]  # c -> Content-Type
    console.print("  case-insensitive: h['FROM'] == h['from'] == h['f']")
    console.print(f"  RFC ordering: {[k for k in h.keys()]}")
    console.print(f"  raw bytes: {len(h.raw())} bytes")
    results["headers"] = True

    # --- HeaderParser ---
    console.print("\n[bold]0.3 HeaderParser[/bold]")
    raw = b"Via: SIP/2.0/UDP pc33.com\r\nFrom: alice@ex.com\r\nTo: bob@ex.com\r\n"
    parsed = HeaderParser.parse(raw)
    assert "Via" in parsed
    console.print(f"  parsed {len(parsed)} headers from raw bytes")

    value_parts = HeaderParser.parse_header_value("application/sdp; charset=utf-8")
    console.print(f"  parse_header_value: {value_parts}")
    formatted = HeaderParser.format_header_value(
        "application/sdp", {"charset": "utf-8"}
    )
    console.print(f"  format_header_value: {formatted}")
    results["header_parser"] = True

    # --- MessageParser ---
    console.print("\n[bold]0.4 MessageParser[/bold]")

    # Parse a request
    raw_req = (
        "INVITE sip:bob@biloxi.com SIP/2.0\r\n"
        "Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bKxyz\r\n"
        "From: <sip:alice@atlanta.com>;tag=1928301774\r\n"
        "To: <sip:bob@biloxi.com>\r\n"
        "Call-ID: a84b4c76e66710@pc33.atlanta.com\r\n"
        "CSeq: 314159 INVITE\r\n"
        "Max-Forwards: 70\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    )
    msg = MessageParser.parse(raw_req)
    assert isinstance(msg, Request)
    assert msg.method == "INVITE"
    assert msg.is_invite
    assert msg.has_valid_via_branch()
    console.print(f"  parsed Request: {msg!r}")
    console.print(f"  via: {msg.via}")
    console.print(f"  call_id: {msg.call_id}")
    console.print(f"  is_invite={msg.is_invite}, is_register={msg.is_register}")

    # Parse a response
    raw_resp = (
        "SIP/2.0 200 OK\r\n"
        "Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bKxyz\r\n"
        "From: <sip:alice@atlanta.com>;tag=1928301774\r\n"
        "To: <sip:bob@biloxi.com>;tag=a6c85cf\r\n"
        "Call-ID: a84b4c76e66710@pc33.atlanta.com\r\n"
        "CSeq: 314159 INVITE\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    )
    resp = MessageParser.parse(raw_resp)
    assert isinstance(resp, Response)
    assert resp.status_code == 200
    assert resp.is_success
    assert resp.is_final
    assert not resp.is_provisional
    assert not resp.is_error
    assert not resp.requires_auth
    console.print(f"  parsed Response: {resp!r}")
    console.print(f"  is_success={resp.is_success}, is_final={resp.is_final}")
    results["message_parser"] = True

    # --- URI parsing ---
    console.print("\n[bold]0.5 URI Parsing[/bold]")
    uri = MessageParser.parse_uri("sip:alice@atlanta.com:5060;transport=tcp")
    console.print(f"  {uri}")
    assert uri["scheme"] == "sip"
    assert uri["user"] == "alice"
    assert uri["host"] == "atlanta.com"
    assert uri["port"] == "5060"
    results["uri_parser"] = True

    # --- SDP ---
    console.print("\n[bold]0.6 SDPBody[/bold]")
    offer = SDPBody.create_offer(
        session_name="Test",
        origin_username="alice",
        origin_address="10.0.0.1",
        connection_address="10.0.0.1",
        media_specs=[
            {
                "media": "audio",
                "port": 49170,
                "codecs": [
                    {"payload": "0", "name": "PCMU", "rate": "8000"},
                    {"payload": "8", "name": "PCMA", "rate": "8000"},
                    {
                        "payload": "101",
                        "name": "telephone-event",
                        "rate": "8000",
                        "fmtp": "0-16",
                    },
                ],
            }
        ],
    )
    console.print(
        f"  offer: {len(offer.to_string())} bytes, content_type={offer.content_type}"
    )
    console.print(f"  connection: {offer.get_connection_address()}")
    console.print(f"  ports: {offer.get_media_ports()}")
    console.print(f"  codecs: {offer.get_codecs_summary()}")
    console.print(f"  early_media: {offer.has_early_media()}")

    # Create answer
    answer = SDPBody.create_answer(
        offer=offer,
        origin_username="bob",
        origin_address="10.0.0.2",
        connection_address="10.0.0.2",
        accepted_media=[
            {
                "index": 0,
                "port": 49170,
                "codecs": ["0", "8"],  # accept PCMU + PCMA, reject telephone-event
            }
        ],
    )
    console.print(f"  answer: {len(answer.to_string())} bytes")
    console.print(f"  accepted codecs: {answer.get_accepted_codecs(0)}")
    console.print(f"  media_rejected: {answer.is_media_rejected(0)}")

    # Parse raw SDP
    parsed_sdp = BodyParser.parse_sdp(offer.to_bytes())
    console.print(f"  round-trip parse: {parsed_sdp.session_name}")
    results["sdp"] = True

    # --- Auth (offline) ---
    console.print("\n[bold]0.7 Auth (offline)[/bold]")
    challenge = DigestChallenge(
        realm="asterisk",
        nonce="abc123def456",
        algorithm="MD5",
        qop="auth",
    )
    creds = DigestCredentials(username="alice", password="secret", realm="asterisk")
    auth = DigestAuth(credentials=creds, challenge=challenge)
    auth_header = auth.build_authorization(method="REGISTER", uri="sip:asterisk")
    console.print(f"  challenge: realm={challenge.realm}, algo={challenge.algorithm}")
    console.print(f"  authorization: {auth_header[:60]}...")
    assert "Digest " in auth_header
    assert 'username="alice"' in auth_header
    results["auth_offline"] = True

    # --- TransportAddress ---
    console.print("\n[bold]0.8 TransportAddress[/bold]")
    addr = TransportAddress.from_uri("sips:alice@example.com:5061")
    console.print(
        f"  from_uri: {addr} (secure={addr.is_secure}, reliable={addr.is_reliable})"
    )
    addr2 = TransportAddress.from_uri("sip:bob@example.com;transport=tcp")
    console.print(
        f"  from_uri: {addr2} (secure={addr2.is_secure}, reliable={addr2.is_reliable})"
    )
    results["transport_address"] = True

    # --- FSM (offline) ---
    console.print("\n[bold]0.9 StateManager[/bold]")
    sm = StateManager()
    req = Request(
        "INVITE",
        "sip:bob@example.com",
        headers={"Via": "SIP/2.0/UDP x;branch=z9hG4bKtest"},
    )
    txn = sm.create_transaction(req)
    console.print(f"  created: {txn!r}")
    console.print(f"  type: {txn.transaction_type.name}, state: {txn.state.name}")

    fake_resp = Response(180, headers={"Via": "SIP/2.0/UDP x"})
    sm.update_transaction(txn.id, fake_resp)
    console.print(f"  after 180: state={txn.state.name}")

    fake_resp2 = Response(200, headers={"Via": "SIP/2.0/UDP x"})
    sm.update_transaction(txn.id, fake_resp2)
    console.print(
        f"  after 200: state={txn.state.name}, is_complete={txn.is_complete()}"
    )

    dlg = sm.create_dialog(
        call_id="test-call",
        local_tag="abc",
        remote_tag="def",
        local_uri="sip:alice@x",
        remote_uri="sip:bob@x",
        remote_target="sip:bob@x",
    )
    console.print(f"  dialog: {dlg!r}")
    console.print(f"  dialog_id: {dlg.get_dialog_id()}")

    stats = sm.get_statistics()
    console.print(f"  stats: {stats}")
    results["fsm"] = txn.is_complete() and dlg.state == DialogState.EARLY

    return results


# ---------------------------------------------------------------------------
# Section S: SIPServer
# ---------------------------------------------------------------------------


def demo_server() -> dict:
    """Start a SIPServer, send it an OPTIONS, verify custom handler."""
    results = {}
    server_port = 15060  # avoid conflict with Asterisk on 5060

    console.print("\n[bold]S.1 SIPServer with custom handler[/bold]")

    server = SIPServer(local_host="127.0.0.1", local_port=server_port)

    # Custom handler for MESSAGE
    def handle_message(request, source):
        console.print(f"  [dim]server received MESSAGE from {source}[/dim]")
        return Response(
            status_code=200,
            reason_phrase="OK",
            headers={
                "Via": request.via or "",
                "From": request.from_header or "",
                "To": request.to_header or "",
                "Call-ID": request.call_id or "",
                "CSeq": request.cseq or "",
                "Content-Length": "0",
            },
        )

    server.register_handler("MESSAGE", handle_message)
    server.start()
    time.sleep(0.5)

    try:
        with Client(local_host="127.0.0.1", local_port=15061) as client:
            # OPTIONS -> server default handler (200 OK with Allow)
            r = client.options(
                f"sip:127.0.0.1:{server_port}",
                host="127.0.0.1",
                port=server_port,
            )
            console.print(f"  OPTIONS -> {r.status_code}")
            results["server_options"] = r.status_code == 200

            time.sleep(0.3)

            # MESSAGE -> custom handler
            r = client.message(
                to_uri=f"sip:test@127.0.0.1:{server_port}",
                content="hello from sipx client",
                host="127.0.0.1",
                port=server_port,
            )
            console.print(f"  MESSAGE -> {r.status_code}")
            results["server_message"] = r.status_code == 200
    finally:
        server.stop()

    return results


# ---------------------------------------------------------------------------
# Section 1-3: Asterisk integration (per user)
# ---------------------------------------------------------------------------


def test_user(user: User, test_id: int) -> dict:
    """Run integration tests for a single user against Asterisk."""
    results = {}
    u = user.username

    with Client(local_port=user.client_port) as client:
        events = FullEvents()
        client.events = events
        client.auth = Auth.Digest(u, user.password, realm="asterisk")

        # --- OPTIONS ---
        console.print(f"\n[bold]{test_id}.1 OPTIONS[/bold]")
        r = auth_request(client, client.options(f"sip:{HOST}"))
        results["options"] = r and r.status_code == 200
        if r:
            console.print(f"  -> {r.status_code} {r.reason_phrase}")

        time.sleep(0.3)

        # --- REGISTER ---
        console.print(f"\n[bold]{test_id}.2 REGISTER[/bold]")
        r = auth_request(client, client.register(f"sip:{u}@{HOST}", expires=3600))
        results["register"] = r and r.status_code == 200
        if r:
            console.print(f"  -> {r.status_code} {r.reason_phrase}")

        time.sleep(0.3)

        # --- INVITE + ACK + BYE (early offer) ---
        console.print(f"\n[bold]{test_id}.3 INVITE (early offer)[/bold]")
        sdp = make_sdp(client, u, port=8000 + test_id * 100)
        console.print(
            f"  [dim]SDP: {len(sdp.to_string())}B, "
            f"codecs={list(sdp.get_codecs_summary().get('audio', []))}[/dim]"
        )

        r = client.invite(
            to_uri=f"sip:100@{HOST}",
            body=sdp.to_string(),
            headers=contact_header(u, client),
        )
        r = auth_request(client, r)

        if r and r.status_code == 200:
            results["invite"] = True

            # Inspect response SDP
            if r.body and isinstance(r.body, SDPBody):
                info = r.body.get_media_info(0)
                if info:
                    console.print(
                        f"  [dim]remote media: {info['type']} "
                        f"port={info['port']} "
                        f"codecs={[c.get('name', '?') for c in info['codecs']]}[/dim]"
                    )

            client.ack(response=r)
            console.print("  [dim]ACK sent, call active...[/dim]")
            time.sleep(2)
            bye_r = client.bye(response=r)
            results["bye"] = bye_r and bye_r.status_code == 200
        else:
            results["invite"] = False
            results["bye"] = False
            if r:
                console.print(f"  -> {r.status_code} {r.reason_phrase}")

        time.sleep(0.3)

        # --- MESSAGE ---
        console.print(f"\n[bold]{test_id}.4 MESSAGE[/bold]")
        r = client.message(
            to_uri=f"sip:100@{HOST}",
            content=f"test from user {u}",
        )
        r = auth_request(client, r)
        results["message"] = r and r.status_code in (200, 202)
        if r:
            console.print(f"  -> {r.status_code} {r.reason_phrase}")

        time.sleep(0.3)

        # --- INFO (DTMF relay) ---
        console.print(f"\n[bold]{test_id}.5 INFO[/bold]")
        try:
            r = client.info(
                uri=f"sip:100@{HOST}",
                content="Signal=5\r\nDuration=160\r\n",
                content_type="application/dtmf-relay",
            )
            r = auth_request(client, r)
            results["info"] = r is not None
            if r:
                console.print(f"  -> {r.status_code} {r.reason_phrase}")
        except Exception as e:
            console.print(f"  [dim]info skipped: {e}[/dim]")
            results["info"] = False

        time.sleep(0.3)

        # --- StateManager stats ---
        console.print(f"\n[bold]{test_id}.6 FSM Stats[/bold]")
        stats = client._state_manager.get_statistics()
        console.print(f"  transactions: {stats['transactions']['total']}")
        console.print(f"  dialogs: {stats['dialogs']['total']}")
        results["fsm_stats"] = stats["transactions"]["total"] > 0

        # --- Events stats ---
        console.print(f"\n[bold]{test_id}.7 Events Stats[/bold]")
        console.print(f"  requests sent: {events.request_count}")
        console.print(f"  responses received: {events.response_count}")
        console.print(f"  auth challenges: {events.auth_challenges}")
        console.print(f"  early media: {events.early_media}")
        console.print(f"  call accepted: {events.call_accepted}")
        if events.codecs:
            console.print(f"  negotiated codecs: {events.codecs}")
        results["events_fired"] = events.request_count > 0 and events.response_count > 0

        # --- UNREGISTER ---
        console.print(f"\n[bold]{test_id}.8 UNREGISTER[/bold]")
        r = auth_request(client, client.unregister(f"sip:{u}@{HOST}"))
        results["unregister"] = r and r.status_code == 200
        if r:
            console.print(f"  -> {r.status_code} {r.reason_phrase}")

    return results


# ---------------------------------------------------------------------------
# Section A: Advanced — per-request auth, auto re-reg, invalid creds
# ---------------------------------------------------------------------------


def test_advanced(user: User) -> dict:
    """Advanced tests: invalid creds, per-request auth, auto re-register."""
    results = {}
    u = user.username

    # --- Invalid credentials ---
    console.print("\n[bold]A.1 Invalid credentials[/bold]")
    with Client(local_port=user.client_port) as client:
        client.auth = Auth.Digest(u, "WRONG_PASSWORD", realm="asterisk")
        r = client.register(f"sip:{u}@{HOST}", expires=60)
        if r.status_code == 401:
            r = client.retry_with_auth(r)
        results["invalid_creds"] = r and r.status_code in (401, 403)
        console.print(f"  -> {r.status_code} (expected 401 or 403)")

    time.sleep(0.3)

    # --- Per-request auth override ---
    console.print("\n[bold]A.2 Per-request auth override[/bold]")
    with Client(local_port=user.client_port) as client:
        # No default auth on client
        r = client.register(f"sip:{u}@{HOST}", expires=60)
        if r.status_code == 401:
            # Provide auth only for this retry
            override = Auth.Digest(u, user.password, realm="asterisk")
            r = client.retry_with_auth(r, auth=override)
        results["per_request_auth"] = r and r.status_code == 200
        console.print(f"  -> {r.status_code}")

    time.sleep(0.3)

    # --- Auto re-registration ---
    console.print("\n[bold]A.3 Auto re-registration[/bold]")
    with Client(local_port=user.client_port) as client:
        client.auth = Auth.Digest(u, user.password, realm="asterisk")

        r = auth_request(client, client.register(f"sip:{u}@{HOST}", expires=120))
        if not (r and r.status_code == 200):
            results["auto_rereg"] = False
            console.print(
                f"  initial register failed: {r.status_code if r else 'None'}"
            )
            return results

        count = [0]

        def on_rereg(resp):
            count[0] += 1
            console.print(f"  [dim]re-register #{count[0]}: {resp.status_code}[/dim]")

        client.enable_auto_reregister(
            aor=f"sip:{u}@{HOST}",
            interval=4,
            callback=on_rereg,
        )
        console.print("  [dim]waiting 10s...[/dim]")
        time.sleep(10)

        results["auto_rereg"] = count[0] >= 2
        console.print(f"  re-registrations: {count[0]} (need >= 2)")
        client.disable_auto_reregister()

        # Cleanup
        auth_request(client, client.unregister(f"sip:{u}@{HOST}"))

    return results


# ---------------------------------------------------------------------------
# Section L: INVITE late offer + SDP answer
# ---------------------------------------------------------------------------


def test_late_offer(user: User) -> dict:
    """INVITE without SDP, receive offer from server, create answer."""
    results = {}
    u = user.username

    console.print("\n[bold]L.1 INVITE (late offer)[/bold]")
    with Client(local_port=user.client_port) as client:
        events = FullEvents()
        client.events = events
        client.auth = Auth.Digest(u, user.password, realm="asterisk")

        # Register first
        auth_request(client, client.register(f"sip:{u}@{HOST}"))

        time.sleep(0.3)

        # INVITE without SDP
        r = client.invite(
            to_uri=f"sip:100@{HOST}",
            body=None,
            headers=contact_header(u, client),
        )
        r = auth_request(client, r)

        if r and r.status_code == 200 and r.body and isinstance(r.body, SDPBody):
            results["late_offer"] = True

            # Full SDP analysis
            console.print("  [dim]received SDP from server[/dim]")
            console.print(f"  connection: {r.body.get_connection_address()}")
            console.print(f"  ports: {r.body.get_media_ports()}")
            console.print(f"  codecs: {r.body.get_codecs_summary()}")
            console.print(f"  early_media: {r.body.has_early_media()}")

            # Create answer
            answer = SDPBody.create_answer(
                offer=r.body,
                origin_username=u,
                origin_address=client.local_address.host,
                connection_address=client.local_address.host,
            )
            console.print(
                f"  answer: {len(answer.to_string())}B, "
                f"codecs={answer.get_codecs_summary()}"
            )

            client.ack(response=r)
            time.sleep(1)
            client.bye(response=r)
        else:
            results["late_offer"] = False
            if r:
                console.print(f"  -> {r.status_code}")

        results["early_media"] = events.early_media

        # Cleanup
        auth_request(client, client.unregister(f"sip:{u}@{HOST}"))

    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(all_results: dict[str, dict]):
    table = Table(title="sipx Demo Results", box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Section", style="bold", width=18)
    table.add_column("Test", width=22)
    table.add_column("Result", width=6)

    total, passed = 0, 0
    for section, results in all_results.items():
        first = True
        for name, ok in results.items():
            total += 1
            if ok:
                passed += 1
            table.add_row(
                section if first else "",
                name,
                "[green]PASS[/green]" if ok else "[red]FAIL[/red]",
            )
            first = False

    console.print()
    console.print(table)
    color = "green" if passed == total else "yellow"
    console.print(f"\n[bold {color}]{passed}/{total} passed[/bold {color}]\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    console.print("\n[bold]sipx — Comprehensive Library Demo[/bold]")
    console.print(f"Asterisk: {HOST}:{PORT}")
    console.print(f"Users: {', '.join(u.username for u in USERS)}\n")
    console.print("[dim]Press Enter to start (Ctrl+C to cancel)...[/dim]")

    try:
        input()
    except KeyboardInterrupt:
        return

    all_results: dict[str, dict] = {}

    try:
        # Section 0: Offline — constants, parsing, SDP, auth, FSM
        console.rule("Section 0: Constants, Parsing, SDP, Auth, FSM (offline)")
        all_results["0-offline"] = demo_constants_and_parsing()

        # Section S: SIPServer
        console.rule("Section S: SIPServer")
        all_results["S-server"] = demo_server()

        time.sleep(1)

        # Section 1-3: Per-user Asterisk integration
        for i, user in enumerate(USERS, start=1):
            console.rule(f"Section {i}: User {user.username}")
            all_results[f"{i}-user-{user.username}"] = test_user(user, i)
            time.sleep(1)

        # Section A: Advanced — invalid creds, per-request auth, auto re-reg
        console.rule("Section A: Advanced (user 3333)")
        all_results["A-advanced"] = test_advanced(USERS[2])

        time.sleep(1)

        # Section L: Late offer + SDP answer
        console.rule("Section L: Late Offer (user 2222)")
        all_results["L-late-offer"] = test_late_offer(USERS[1])

        # Summary
        print_summary(all_results)

    except KeyboardInterrupt:
        console.print("\n[yellow]interrupted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
