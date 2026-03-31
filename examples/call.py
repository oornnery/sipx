#!/usr/bin/env python3
"""sipx — Complete call flow: REGISTER → INVITE → ACK → BYE."""

import time
from sipx import Client
from sipx._utils import console

with Client(local_port=5061) as client:
    client.auth = ("1111", "1111xxx")

    # Register
    r = client.register("sip:1111@127.0.0.1")
    console.print(f"REGISTER: {r.status_code}")

    # Call
    sdp = client.create_sdp(port=8000)
    r = client.invite(
        to_uri="sip:100@127.0.0.1",
        body=sdp.to_string(),
        headers={
            "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
        },
    )
    console.print(f"INVITE: {r.status_code}")

    if r.status_code == 200:
        client.ack()
        console.print("ACK sent, call active...")
        time.sleep(3)
        bye_r = client.bye()
        console.print(f"BYE: {bye_r.status_code}")

    # Unregister
    client.unregister("sip:1111@127.0.0.1")
