#!/usr/bin/env python3
"""sipx — SDP creation and analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import SDPBody

# Simple audio SDP (1 line)
sdp = SDPBody.audio(ip="192.168.1.100", port=8000)
print("=== Simple Audio SDP ===")
print(sdp.to_string())

# Custom codecs
sdp2 = SDPBody.audio(
    ip="10.0.0.1", port=9000, codecs=["PCMU", "PCMA"], username="alice"
)
print("=== Custom Codecs ===")
print(f"Codecs: {sdp2.get_codecs_summary()}")
print(f"Ports: {sdp2.get_media_ports()}")
print(f"Connection: {sdp2.get_connection_address()}")
print(f"RTP params: {sdp2.get_rtp_params()}")

# Full offer with video
full = SDPBody.create_offer(
    session_name="Conference",
    origin_username="bob",
    origin_address="10.0.0.2",
    connection_address="10.0.0.2",
    media_specs=[
        {
            "media": "audio",
            "port": 49170,
            "codecs": [
                {"payload": "0", "name": "PCMU", "rate": "8000"},
                {
                    "payload": "101",
                    "name": "telephone-event",
                    "rate": "8000",
                    "fmtp": "0-16",
                },
            ],
        },
        {
            "media": "video",
            "port": 51372,
            "codecs": [
                {"payload": "31", "name": "H261", "rate": "90000"},
            ],
        },
    ],
)
print("\n=== Full Offer (audio + video) ===")
print(full.to_string())

# Create answer from offer
answer = SDPBody.create_answer(
    offer=full,
    origin_username="carol",
    origin_address="10.0.0.3",
    connection_address="10.0.0.3",
    accepted_media=[
        {"index": 0, "port": 49170, "codecs": ["0"]},  # accept PCMU only
        {"index": 1, "port": 0, "codecs": []},  # reject video
    ],
)
print("=== Answer (accept audio, reject video) ===")
print(f"Audio rejected: {answer.is_media_rejected(0)}")
print(f"Video rejected: {answer.is_media_rejected(1)}")
print(f"Accepted codecs: {answer.get_accepted_codecs(0)}")
