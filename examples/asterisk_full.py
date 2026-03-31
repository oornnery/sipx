#!/usr/bin/env python3
"""
sipx — Asterisk Integration Demo (simplified API)

Exercises the full sipx API against Asterisk with 3 users.

Usage:
    uv run python examples/asterisk_full.py

Requires:
    cd docker/asterisk && docker-compose up -d
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import (
    Client,
    Events,
    EventContext,
    on,
    Auth,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    Request,
    Response,
    MessageParser,
    Headers,
    SDPBody,
    BodyParser,
    StateManager,
    DialogState,
    TransportAddress,
    console,
)
from sipx._server import SIPServer
from sipx._utils import (
    EOL,
    SCHEME,
    VERSION,
    BRANCH,
    HEADERS,
    HEADERS_COMPACT,
    REASON_PHRASES,
)

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
    def __init__(self):
        super().__init__()
        self.request_count = 0
        self.response_count = 0
        self.early_media = False
        self.auth_challenges = 0
        self.call_accepted = False
        self.codecs: dict[str, list[str]] = {}

    def on_request(self, request: Request, context: EventContext) -> Request:
        self.request_count += 1
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        self.response_count += 1
        return response

    @on("REGISTER", status=200)
    def on_registered(self, request, response, context):
        contact = response.headers.get("Contact", "")
        if "expires=" in contact:
            exp = contact.split("expires=")[1].split(";")[0]
            console.print(f"  [green]registered (expires={exp})[/green]")

    @on("OPTIONS", status=200)
    def on_options_ok(self, request, response, context):
        allow = response.headers.get("Allow", "")
        if allow:
            console.print(f"  [green]server allows: {allow}[/green]")

    @on("INVITE", status=183)
    def on_early_media(self, request, response, context):
        self.early_media = True

    @on("INVITE", status=200)
    def on_call_accepted(self, request, response, context):
        self.call_accepted = True
        if response.body:
            self.codecs = response.body.get_codecs_summary()

    @on(status=(401, 407))
    def on_auth(self, request, response, context):
        self.auth_challenges += 1

    @on("BYE", status=200)
    def on_bye(self, request, response, context):
        console.print("  [green]call terminated[/green]")

    @on("MESSAGE", status=(200, 202))
    def on_msg(self, request, response, context):
        console.print("  [green]message delivered[/green]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_sdp(client: Client, username: str, port: int = 8000) -> SDPBody:
    return SDPBody.audio(ip=client.local_address.host, port=port)


def contact(username: str, client: Client) -> dict:
    addr = client.local_address
    return {"Contact": f"<sip:{username}@{addr.host}:{addr.port}>"}


# ---------------------------------------------------------------------------
# Section 0: Offline tests (no network)
# ---------------------------------------------------------------------------


def demo_offline() -> dict:
    results = {}

    # Constants
    console.print("\n[bold]0.1 Constants[/bold]")
    console.print(f"  EOL={EOL!r}, {SCHEME}/{VERSION}, BRANCH={BRANCH}")
    console.print(
        f"  headers={len(HEADERS)}, compact={len(HEADERS_COMPACT)}, reasons={len(REASON_PHRASES)}"
    )
    results["constants"] = len(HEADERS) > 40

    # Headers
    console.print("\n[bold]0.2 Headers[/bold]")
    h = Headers({"Via": "SIP/2.0/UDP 10.0.0.1", "from": "alice@x", "call-id": "test"})
    assert h["FROM"] == h["from"] == h["f"]
    results["headers"] = True

    # MessageParser
    console.print("\n[bold]0.3 MessageParser[/bold]")
    msg = MessageParser.parse(
        "INVITE sip:bob@x SIP/2.0\r\nVia: SIP/2.0/UDP x;branch=z9hG4bKtest\r\n"
        "From: alice@x\r\nTo: bob@x\r\nCall-ID: test\r\nCSeq: 1 INVITE\r\n"
        "Content-Length: 0\r\n\r\n"
    )
    assert isinstance(msg, Request) and msg.is_invite
    results["parser"] = True

    # SDP
    console.print("\n[bold]0.4 SDPBody.audio()[/bold]")
    sdp = SDPBody.audio(ip="10.0.0.1", port=8000)
    console.print(f"  codecs={sdp.get_codecs_summary()}, ports={sdp.get_media_ports()}")
    answer = SDPBody.create_answer(
        offer=sdp,
        origin_username="bob",
        origin_address="10.0.0.2",
        connection_address="10.0.0.2",
    )
    console.print(f"  answer codecs={answer.get_accepted_codecs(0)}")
    parsed = BodyParser.parse_sdp(sdp.to_bytes())
    assert parsed.session_name == "sipx"
    results["sdp"] = True

    # Auth offline
    console.print("\n[bold]0.5 Auth[/bold]")
    ch = DigestChallenge(realm="test", nonce="abc", algorithm="MD5", qop="auth")
    auth = DigestAuth(credentials=DigestCredentials("alice", "secret"), challenge=ch)
    hdr = auth.build_authorization(method="REGISTER", uri="sip:test")
    assert "Digest " in hdr
    results["auth"] = True

    # TransportAddress
    console.print("\n[bold]0.6 TransportAddress[/bold]")
    addr = TransportAddress.from_uri("sips:alice@example.com:5061")
    assert addr.is_secure and addr.is_reliable
    results["transport"] = True

    # FSM
    console.print("\n[bold]0.7 FSM[/bold]")
    sm = StateManager()
    req = Request(
        "INVITE", "sip:bob@x", headers={"Via": "SIP/2.0/UDP x;branch=z9hG4bKtest"}
    )
    txn = sm.create_transaction(req)
    sm.update_transaction(txn.id, Response(200))
    dlg = sm.create_dialog("c", "l", "r", "sip:a", "sip:b", "sip:b")
    assert txn.is_complete() and dlg.state == DialogState.EARLY
    results["fsm"] = True

    return results


# ---------------------------------------------------------------------------
# Section S: SIPServer
# ---------------------------------------------------------------------------


def demo_server() -> dict:
    results = {}
    server = SIPServer(local_host="127.0.0.1", local_port=15060)

    @server.message
    def on_msg(request, source):
        return Response(
            status_code=200,
            headers={
                "Via": request.via or "",
                "From": request.from_header or "",
                "To": request.to_header or "",
                "Call-ID": request.call_id or "",
                "CSeq": request.cseq or "",
                "Content-Length": "0",
            },
        )

    server.start()
    time.sleep(0.5)

    try:
        with Client(local_host="127.0.0.1", local_port=15061) as c:
            r = c.options("sip:127.0.0.1:15060", host="127.0.0.1", port=15060)
            results["server_options"] = r.status_code == 200

            r = c.message(
                to_uri="sip:test@127.0.0.1:15060",
                content="hello",
                host="127.0.0.1",
                port=15060,
            )
            results["server_message"] = r.status_code == 200
    finally:
        server.stop()

    return results


# ---------------------------------------------------------------------------
# Section 1-3: Asterisk per-user tests
# ---------------------------------------------------------------------------


def test_user(user: User, test_id: int) -> dict:
    results = {}
    u = user.username

    with Client(local_port=user.client_port) as client:
        events = FullEvents()
        client.events = events
        client.auth = (u, user.password)  # tuple auth

        # OPTIONS
        console.print(f"\n[bold]{test_id}.1 OPTIONS[/bold]")
        r = client.options(f"sip:{HOST}")
        results["options"] = r and r.status_code == 200
        console.print(f"  -> {r.status_code}" if r else "  -> None")

        time.sleep(0.3)

        # REGISTER
        console.print(f"\n[bold]{test_id}.2 REGISTER[/bold]")
        r = client.register(f"sip:{u}@{HOST}", expires=3600)
        results["register"] = r and r.status_code == 200
        console.print(f"  -> {r.status_code}" if r else "  -> None")

        time.sleep(0.3)

        # INVITE + ACK + BYE
        console.print(f"\n[bold]{test_id}.3 INVITE[/bold]")
        sdp = make_sdp(client, u, port=8000 + test_id * 100)
        r = client.invite(
            to_uri=f"sip:100@{HOST}",
            body=sdp.to_string(),
            headers=contact(u, client),
        )
        if r and r.status_code == 200:
            results["invite"] = True
            client.ack(response=r)
            time.sleep(2)
            bye_r = client.bye(response=r)
            results["bye"] = bye_r and bye_r.status_code == 200
        else:
            results["invite"] = False
            results["bye"] = False

        time.sleep(0.3)

        # MESSAGE
        console.print(f"\n[bold]{test_id}.4 MESSAGE[/bold]")
        r = client.message(to_uri=f"sip:100@{HOST}", content=f"test {u}")
        results["message"] = r and r.status_code in (200, 202)

        time.sleep(0.3)

        # INFO
        console.print(f"\n[bold]{test_id}.5 INFO[/bold]")
        try:
            r = client.info(
                uri=f"sip:100@{HOST}", content="Signal=5\r\nDuration=160\r\n"
            )
            results["info"] = r is not None
        except Exception:
            results["info"] = False

        # Stats
        stats = client._state_manager.get_statistics()
        results["fsm_stats"] = stats["transactions"]["total"] > 0
        results["events_fired"] = events.request_count > 0

        # UNREGISTER
        console.print(f"\n[bold]{test_id}.6 UNREGISTER[/bold]")
        r = client.unregister(f"sip:{u}@{HOST}")
        results["unregister"] = r and r.status_code == 200

    return results


# ---------------------------------------------------------------------------
# Section A: Advanced
# ---------------------------------------------------------------------------


def test_advanced(user: User) -> dict:
    results = {}
    u = user.username

    # Invalid credentials
    console.print("\n[bold]A.1 Invalid creds[/bold]")
    with Client(local_port=user.client_port, auto_auth=True) as c:
        c.auth = (u, "WRONG")
        r = c.register(f"sip:{u}@{HOST}", expires=60)
        results["invalid_creds"] = r and r.status_code in (401, 403)
        console.print(f"  -> {r.status_code}")

    time.sleep(0.3)

    # Per-request auth
    console.print("\n[bold]A.2 Per-request auth[/bold]")
    with Client(local_port=user.client_port, auto_auth=False) as c:
        r = c.register(f"sip:{u}@{HOST}", expires=60)
        if r.status_code == 401:
            override = Auth.Digest(u, user.password)
            r = c.retry_with_auth(r, auth=override)
        results["per_request"] = r and r.status_code == 200
        console.print(f"  -> {r.status_code}")

    time.sleep(0.3)

    # Auto re-registration
    console.print("\n[bold]A.3 Auto re-reg[/bold]")
    with Client(local_port=user.client_port) as c:
        c.auth = (u, user.password)
        r = c.register(f"sip:{u}@{HOST}", expires=120)
        if not (r and r.status_code == 200):
            results["auto_rereg"] = False
            return results

        count = [0]

        def on_rereg(resp):
            count[0] += 1

        c.enable_auto_reregister(aor=f"sip:{u}@{HOST}", interval=4, callback=on_rereg)
        console.print("  [dim]waiting 10s...[/dim]")
        time.sleep(10)
        results["auto_rereg"] = count[0] >= 2
        console.print(f"  re-registrations: {count[0]}")
        c.disable_auto_reregister()
        c.unregister(f"sip:{u}@{HOST}")

    return results


# ---------------------------------------------------------------------------
# Section L: Late offer
# ---------------------------------------------------------------------------


def test_late_offer(user: User) -> dict:
    results = {}
    u = user.username

    with Client(local_port=user.client_port) as client:
        events = FullEvents()
        client.events = events
        client.auth = (u, user.password)

        client.register(f"sip:{u}@{HOST}")
        time.sleep(0.3)

        console.print("\n[bold]L.1 INVITE (late offer)[/bold]")
        r = client.invite(
            to_uri=f"sip:100@{HOST}",
            body=None,
            headers=contact(u, client),
        )

        if r and r.status_code == 200 and r.body and isinstance(r.body, SDPBody):
            results["late_offer"] = True
            console.print(f"  codecs={r.body.get_codecs_summary()}")
            client.ack(response=r)
            time.sleep(1)
            client.bye(response=r)
        else:
            results["late_offer"] = False

        results["early_media"] = events.early_media
        client.unregister(f"sip:{u}@{HOST}")

    return results


# ---------------------------------------------------------------------------
# Summary + Main
# ---------------------------------------------------------------------------


def print_summary(all_results: dict[str, dict]):
    table = Table(title="sipx Demo Results", box=box.SIMPLE_HEAVY)
    table.add_column("Section", style="bold", width=18)
    table.add_column("Test", width=20)
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


def main():
    console.print("\n[bold]sipx — Asterisk Demo[/bold]")
    console.print(f"Target: {HOST}:{PORT}\n")
    console.print("[dim]Press Enter to start (Ctrl+C to cancel)...[/dim]")
    try:
        input()
    except KeyboardInterrupt:
        return

    results: dict[str, dict] = {}

    try:
        console.rule("Section 0: Offline")
        results["0-offline"] = demo_offline()

        console.rule("Section S: SIPServer")
        results["S-server"] = demo_server()
        time.sleep(1)

        for i, user in enumerate(USERS, start=1):
            console.rule(f"Section {i}: User {user.username}")
            results[f"{i}-{user.username}"] = test_user(user, i)
            time.sleep(1)

        console.rule("Section A: Advanced (3333)")
        results["A-advanced"] = test_advanced(USERS[2])
        time.sleep(1)

        console.rule("Section L: Late Offer (2222)")
        results["L-late"] = test_late_offer(USERS[1])

        print_summary(results)

    except KeyboardInterrupt:
        console.print("\n[yellow]interrupted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]{e}[/red]")
        raise


if __name__ == "__main__":
    main()
