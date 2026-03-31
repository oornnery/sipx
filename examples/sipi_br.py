#!/usr/bin/env python3
"""sipx — SIP-I BR (Brazilian ANATEL extensions)."""

from sipx import Request
from sipx._utils import console
from sipx.contrib import SipIBR, normalize_br_number, is_valid_br_number, is_mobile

# Number normalization
console.print("[bold]BR Number Normalization[/bold]")
for n in ["+55 (11) 98765-4321", "011987654321", "2134567890", "85912345678"]:
    norm = normalize_br_number(n)
    console.print(
        f"  {n:25s} -> {norm:12s} valid={is_valid_br_number(n)} mobile={is_mobile(n)}"
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
