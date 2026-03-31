#!/usr/bin/env python3
"""sipx — SIP-I / ISUP interworking (international)."""

from sipx import Request
from sipx._utils import console
from sipx.contrib import SipI

# ISUP -> SIP
console.print("[bold]ISUP -> SIP[/bold]")
for cause in [1, 16, 17, 18, 19, 21, 34, 127]:
    console.print(f"  ISUP {cause:3d} -> SIP {SipI.isup_to_sip(cause)}")

# SIP -> ISUP
console.print("\n[bold]SIP -> ISUP[/bold]")
for status in [400, 403, 404, 408, 480, 486, 500, 503]:
    console.print(f"  SIP {status} -> ISUP {SipI.sip_to_isup(status)}")

# P-Asserted-Identity
console.print("\n[bold]P-Asserted-Identity[/bold]")
req = Request("INVITE", "sip:bob@carrier.com")
SipI.add_pai(req, "sip:+15551234567@carrier.com")
console.print(f"  PAI: {SipI.get_pai(req)}")

# P-Charging-Vector
console.print("\n[bold]P-Charging-Vector[/bold]")
SipI.add_charging_vector(req, icid="abc123", orig_ioi="carrier.com")
console.print(f"  PCV: {req.headers['P-Charging-Vector']}")
