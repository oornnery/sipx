#!/usr/bin/env python3
"""
sipx — Quick Start Examples

The simplest possible examples for each common operation.

Usage:
    uv run python examples/quickstart.py
"""

import sipx


def example_register():
    """Register with a PBX — 1 line."""
    r = sipx.register("sip:alice@127.0.0.1", auth=("1111", "1111xxx"))
    print(f"REGISTER: {r.status_code}")


def example_options():
    """Check server capabilities — 1 line."""
    r = sipx.options("sip:127.0.0.1")
    print(f"OPTIONS: {r.status_code}")


def example_send_message():
    """Send instant message — 1 line."""
    r = sipx.send("sip:2222@127.0.0.1", "Hello from sipx!", auth=("1111", "1111xxx"))
    print(f"MESSAGE: {r.status_code}")


def example_call():
    """Make a call — 1 line."""
    from sipx import SDPBody

    sdp = SDPBody.audio(ip="127.0.0.1", port=8000)
    r = sipx.call("sip:100@127.0.0.1", auth=("1111", "1111xxx"), body=sdp.to_string())
    print(f"INVITE: {r.status_code}")


def example_client():
    """Use Client for multiple operations."""
    from sipx import Client

    with Client(local_port=5061) as client:
        client.auth = ("1111", "1111xxx")

        # Register
        r = client.register("sip:1111@127.0.0.1")
        print(f"REGISTER: {r.status_code}")

        # Options
        r = client.options("sip:127.0.0.1")
        print(f"OPTIONS: {r.status_code}")

        # Unregister
        r = client.unregister("sip:1111@127.0.0.1")
        print(f"UNREGISTER: {r.status_code}")


if __name__ == "__main__":
    print("sipx Quick Start Examples")
    print("Requires: cd docker/asterisk && docker-compose up -d\n")

    print("1. Register")
    example_register()

    print("\n2. Options")
    example_options()

    print("\n3. Send Message")
    example_send_message()

    print("\n4. Call")
    example_call()

    print("\n5. Client (multiple ops)")
    example_client()
