#!/usr/bin/env python3
"""
sipx — Response Builders + Dialog Tracking + create_sdp

Shows the new API patterns:
- request.ok(), request.trying(), request.ringing(), request.error()
- client.ack() / client.bye() without passing response (dialog tracking)
- client.create_sdp() instead of manual SDPBody.audio()

No network required — builds and inspects SIP messages offline.
"""

from sipx import Request
from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# 1. Response builders on Request
# ---------------------------------------------------------------------------

console.print("[bold]1. Response Builders[/bold]\n")

# Simulate an incoming INVITE
invite = Request(
    method="INVITE",
    uri="sip:bob@example.com",
    headers={
        "Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK776asdhds",
        "From": "<sip:alice@example.com>;tag=1928301774",
        "To": "<sip:bob@example.com>",
        "Call-ID": "a84b4c76e66710@pc33.example.com",
        "CSeq": "314159 INVITE",
        "Contact": "<sip:alice@10.0.0.1>",
        "Content-Type": "application/sdp",
    },
)

# 100 Trying (auto-sent by server on INVITE)
trying = invite.trying()
console.print(f"  trying()   -> {trying.status_code} {trying.reason_phrase}")

# 180 Ringing
ringing = invite.ringing()
console.print(f"  ringing()  -> {ringing.status_code} {ringing.reason_phrase}")

# 200 OK (with extra headers and body)
ok = invite.ok(
    headers={"Contact": "<sip:bob@10.0.0.2>", "Content-Type": "application/sdp"},
    content="v=0\r\no=bob 2890844527 2890844527 IN IP4 10.0.0.2\r\n",
)
console.print(f"  ok()       -> {ok.status_code} {ok.reason_phrase}")
via = ok.headers.get("Via", "") or ""
console.print(f"               Via: {via[:40]}...")

# Error responses
busy = invite.error(486)
console.print(f"  error(486) -> {busy.status_code} {busy.reason_phrase}")

not_found = invite.error(404)
console.print(f"  error(404) -> {not_found.status_code} {not_found.reason_phrase}")

# Redirect
redirect = invite.redirect("sip:bob@backup.example.com")
console.print(f"  redirect() -> {redirect.status_code} {redirect.reason_phrase}")
console.print(f"               Contact: {redirect.headers.get('Contact', '')}")

# ---------------------------------------------------------------------------
# 2. Server handler with request.ok()
# ---------------------------------------------------------------------------

console.print("\n[bold]2. Server Handler Pattern[/bold]\n")

console.print("  # Before (6 lines of boilerplate):")
console.print(
    "  return Response(status_code=200, headers={Via, From, To, Call-ID, CSeq, ...})"
)
console.print()
console.print("  # After (1 line):")
console.print("  return request.ok()")
console.print("  return request.ok(headers={'Allow': 'INVITE,BYE'}, content=sdp)")

# ---------------------------------------------------------------------------
# 3. Dialog tracking pattern
# ---------------------------------------------------------------------------

console.print("\n[bold]3. Dialog Tracking Pattern[/bold]\n")

console.print("  # Before:")
console.print("  r = client.invite('sip:bob@x', body=sdp)")
console.print("  client.ack(response=r)")
console.print("  client.bye(response=r)")
console.print()
console.print("  # After (dialog tracked automatically):")
console.print("  r = client.invite('sip:bob@x', body=sdp)")
console.print("  client.ack()    # uses tracked dialog")
console.print("  client.bye()    # uses tracked dialog, clears after BYE")

# ---------------------------------------------------------------------------
# 4. create_sdp() pattern
# ---------------------------------------------------------------------------

console.print("\n[bold]4. create_sdp() Pattern[/bold]\n")

console.print("  # Before:")
console.print("  sdp = SDPBody.audio(ip=client.local_address.host, port=8000)")
console.print()
console.print("  # After:")
console.print("  sdp = client.create_sdp(port=8000)  # uses client's local address")

console.print("\n[bold green]All patterns demonstrated.[/bold green]")
