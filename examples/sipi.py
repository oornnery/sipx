#!/usr/bin/env python3
"""sipx — SIP-I / ISUP interworking examples."""

from sipx import Request
from sipx._utils import console
from sipx.contrib import (
    SipI,
    SipIBR,
    normalize_br_number,
    is_valid_br_number,
    is_mobile,
)

# --- ISUP <-> SIP cause code mapping ---
console.print("[bold]ISUP <-> SIP Cause Mapping[/bold]")
for cause in [1, 16, 17, 18, 19, 21, 34, 127]:
    sip = SipI.isup_to_sip(cause)
    console.print(f"  ISUP {cause:3d} -> SIP {sip}")

console.print()
for status in [400, 403, 404, 408, 480, 486, 500, 503]:
    isup = SipI.sip_to_isup(status)
    console.print(f"  SIP {status} -> ISUP {isup}")

# --- P-Asserted-Identity ---
console.print("\n[bold]P-Asserted-Identity[/bold]")
req = Request("INVITE", "sip:bob@carrier.com")
SipI.add_pai(req, "sip:+5511999999999@carrier.com.br")
console.print(f"  PAI: {SipI.get_pai(req)}")

# --- P-Charging-Vector ---
console.print("\n[bold]P-Charging-Vector[/bold]")
SipI.add_charging_vector(req, icid="abc123", orig_ioi="carrier.com.br")
console.print(f"  PCV: {req.headers['P-Charging-Vector']}")

# --- Brazilian extensions ---
console.print("\n[bold]Brazilian Extensions (SipIBR)[/bold]")

# Number normalization
for n in ["+55 (11) 98765-4321", "011987654321", "2134567890"]:
    norm = normalize_br_number(n)
    console.print(
        f"  {n:25s} -> {norm}  valid={is_valid_br_number(n)} mobile={is_mobile(n)}"
    )

# P-Preferred-Identity
req2 = Request("INVITE", "sip:bob@x")
SipIBR.add_preferred_identity(req2, "sip:+5511999999999@carrier.com.br")
console.print(f"\n  P-Preferred-Identity: {SipIBR.get_preferred_identity(req2)}")

# P-Charging-Function-Addresses
SipIBR.add_charging_function_addresses(
    req2, ccf=["ccf1.carrier.com"], ecf=["ecf1.carrier.com"]
)
addrs = SipIBR.get_charging_function_addresses(req2)
console.print(f"  P-Charging-Function-Addresses: {addrs}")

# Reason header
bye = Request("BYE", "sip:bob@x")
SipIBR.add_reason(bye, cause=16, text="Normal Clearing")
console.print(f"  Reason: {SipIBR.get_reason(bye)}")
