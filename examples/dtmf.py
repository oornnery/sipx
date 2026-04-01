#!/usr/bin/env python3
"""sipx — Send DTMF digits (all 3 methods)."""

import time
from sipx import Client
from sipx._utils import console
from sipx.media import CallSession, DTMFToneGenerator

with Client(local_port=5061) as client:
    client.auth = ("1111", "1111xxx")

    sdp = client.create_sdp(port=8000)
    r = client.invite(
        to_uri="sip:100@127.0.0.1",
        body=sdp.to_string(),
        headers={
            "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
        },
    )

    if r.status_code == 200:
        client.ack()

        # Method 1: RFC 4733 (RTP telephone-event)
        console.print("DTMF via RFC 4733:")
        with CallSession(client, r, rtp_port=8000) as call:
            call.send_dtmf("123")
            console.print("  Sent '123' as RTP telephone-event")
            time.sleep(1)

        # Method 2: SIP INFO
        console.print("DTMF via SIP INFO:")
        client.info(
            uri="sip:100@127.0.0.1",
            content="Signal=5\r\nDuration=160\r\n",
            content_type="application/dtmf-relay",
        )
        console.print("  Sent '5' as SIP INFO")

        # Method 3: Inband (dual-tone in audio)
        console.print("DTMF via Inband audio:")
        dtmf_gen = DTMFToneGenerator()
        with CallSession(client, r, rtp_port=8001) as call:
            call.play(dtmf_gen.generate_digit("9", 200))
            console.print("  Sent '9' as 697+1477Hz tone")

        client.bye()
