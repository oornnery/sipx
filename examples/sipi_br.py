#!/usr/bin/env python3
"""sipx — SIP-I BR (Brazilian ANATEL extensions)."""

from sipx import Request
from rich.console import Console
from sipx.contrib import (
    SipI,
    SipIBR,
)

console = Console()

# Number normalization
console.print("[bold]BR Number Normalization[/bold]")
for n in ["+55 (11) 98765-4321", "011987654321", "2134567890", "85912345678"]:
    norm = SipIBR.normalize(n)
    console.print(
        f"  {n:25s} -> {norm:12s} valid={SipIBR.is_valid(n)} mobile={SipIBR.is_mobile(n)}"
    )

# P-Preferred-Identity
console.print("\n[bold]P-Preferred-Identity[/bold]")
req = Request("INVITE", "sip:bob@carrier.com.br")
SipIBR.add_preferred_identity(req, "sip:+5511999999999@carrier.com.br")
console.print(f"  PPI: {SipIBR.get_preferred_identity(req)}")

# P-Charging-Function-Addresses
console.print("\n[bold]P-Charging-Function-Addresses[/bold]")
SipIBR.add_charging_function_addresses(
    req, ccf=["ccf1.carrier.com"], ecf=["ecf1.carrier.com"]
)
console.print(f"  Addresses: {SipIBR.get_charging_function_addresses(req)}")

# Reason header (Q.850)
console.print("\n[bold]Reason Header (Q.850)[/bold]")
bye = Request("BYE", "sip:bob@carrier.com.br")
SipIBR.add_reason(bye, cause=16, text="Normal Clearing")
console.print(f"  Reason: {SipIBR.get_reason(bye)}")

SipIBR.add_reason(bye, cause=17, text="User Busy", location="user")
console.print(f"  Reason: {SipIBR.get_reason(bye)}")

# --- Full INVITE with BR SIP-I headers ---
console.print("\n[bold]INVITE with Brazilian SIP-I Headers[/bold]")
invite = Request(
    "INVITE",
    "sip:+5511987654321@gateway.carrier.com.br",
    headers={
        "Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bKbr01",
        "From": '"Caller" <sip:+5521999999999@carrier.com.br>;tag=br01',
        "To": "<sip:+5511987654321@gateway.carrier.com.br>",
        "Call-ID": "br-sipi-001@carrier.com.br",
        "CSeq": "1 INVITE",
        "Max-Forwards": "70",
        "Supported": "timer",
        "Session-Expires": "1800;refresher=uac",
        "Content-Type": "application/sdp",
        "Content-Length": "0",
    },
)

# Add all BR SIP-I headers
SipI.add_pai(invite, "sip:+5521999999999@carrier.com.br")
SipI.add_charging_vector(invite, icid="br-icid-001", orig_ioi="carrier-a.com.br")
SipIBR.add_preferred_identity(invite, "sip:+5521999999999@carrier.com.br")
SipIBR.add_charging_function_addresses(
    invite, ccf=["ccf.carrier.com.br"], ecf=["ecf.carrier.com.br"]
)

console.print(f"  To: {invite.headers['To']}")
console.print(f"  PAI: {SipI.get_pai(invite)}")
console.print(f"  PPI: {SipIBR.get_preferred_identity(invite)}")
console.print(f"  PCV: {invite.headers['P-Charging-Vector']}")
console.print(f"  PCFA: {invite.headers['P-Charging-Function-Addresses']}")
console.print(f"  Session-Expires: {invite.headers['Session-Expires']}")
console.print(f"\n  Full INVITE:\n{invite.to_string()}")
