#!/usr/bin/env python3
"""sipx — Parse raw SIP messages and headers."""

from sipx import MessageParser, Headers
from sipx._models._message import Request, Response
from sipx._utils import console

# --- Parse a raw SIP request ---
raw = (
    "INVITE sip:bob@biloxi.com SIP/2.0\r\n"
    "Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds\r\n"
    "From: Alice <sip:alice@atlanta.com>;tag=1928301774\r\n"
    "To: Bob <sip:bob@biloxi.com>\r\n"
    "Call-ID: a84b4c76e66710@pc33.atlanta.com\r\n"
    "CSeq: 314159 INVITE\r\n"
    "Max-Forwards: 70\r\n"
    "Content-Type: application/sdp\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

msg = MessageParser.parse(raw)
assert isinstance(msg, Request)
console.print(f"Type: {type(msg).__name__}")
console.print(f"Method: {msg.method}, URI: {msg.uri}")
console.print(f"Via: {msg.via}")
console.print(f"From: {msg.from_header}")
console.print(f"Call-ID: {msg.call_id}")
console.print(f"is_invite={msg.is_invite}, valid_branch={msg.has_valid_via_branch()}")

# --- Parse a raw SIP response ---
raw_resp = (
    "SIP/2.0 486 Busy Here\r\n"
    "Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds\r\n"
    "From: Alice <sip:alice@atlanta.com>;tag=1928301774\r\n"
    "To: Bob <sip:bob@biloxi.com>;tag=a6c85cf\r\n"
    "Call-ID: a84b4c76e66710@pc33.atlanta.com\r\n"
    "CSeq: 314159 INVITE\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

resp = MessageParser.parse(raw_resp)
assert isinstance(resp, Response)
console.print(f"\nResponse: {resp.status_code} {resp.reason_phrase}")
console.print(f"is_error={resp.is_error}, is_client_error={resp.is_client_error}")

# --- Headers (case-insensitive + compact forms) ---
h = Headers({"via": "SIP/2.0/UDP x", "f": "alice@x", "i": "call-123"})
console.print(
    f"\nHeaders: h['Via']={h['Via']}, h['From']={h['From']}, h['Call-ID']={h['Call-ID']}"
)
console.print(f"Compact: h['f']=={h['f']}, h['i']=={h['i']}")

# --- URI parsing ---
uri = MessageParser.parse_uri("sip:alice@atlanta.com:5060;transport=tcp")
console.print(f"\nURI: {uri}")
