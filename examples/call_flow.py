#!/usr/bin/env python3
"""sipx — Complete call flow: REGISTER → INVITE → ACK → BYE."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import Client, SDPBody

with Client(local_port=5061) as client:
    client.auth = ("1111", "1111xxx")

    # Register
    r = client.register("sip:1111@127.0.0.1")
    print(f"REGISTER: {r.status_code}")

    # Call
    sdp = SDPBody.audio(ip=client.local_address.host, port=8000)
    r = client.invite(
        to_uri="sip:100@127.0.0.1",
        body=sdp.to_string(),
        headers={
            "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
        },
    )
    print(f"INVITE: {r.status_code}")

    if r.status_code == 200:
        client.ack(response=r)
        print("ACK sent, call active...")
        time.sleep(3)
        bye_r = client.bye(response=r)
        print(f"BYE: {bye_r.status_code}")

    # Unregister
    client.unregister("sip:1111@127.0.0.1")
