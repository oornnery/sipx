"""
Presence agent demo — PUBLISH + SUBSCRIBE/NOTIFY (RFC 3863, RFC 3903).

Illustrates:
  1. Building PIDF-XML presence documents
  2. Initial PUBLISH (creates presence state, receives SIP-ETag)
  3. Refresh PUBLISH (uses SIP-If-Match with stored ETag)
  4. SUBSCRIBE to presence event from another UA
  5. NOTIFY flow with PIDF-XML body

This example runs fully offline using PIFDBody — no real network needed.

Run:
    uv run python examples/presence.py
"""

from __future__ import annotations

from sipx.models import PIFDBody


def demo_pidf() -> None:
    print("=== PIFDBody demo ===\n")

    # --- Online presence ---
    alice_online = PIFDBody(
        entity="sip:alice@pbx.example.com",
        status="open",
        note="Available",
    )
    print("Alice online:")
    print(alice_online.to_string())
    print()

    # --- Away / DND ---
    alice_dnd = PIFDBody(
        entity="sip:alice@pbx.example.com",
        status="open",
        note="Do not disturb",
        tuple_id="t2",
    )
    print("Alice DND:")
    print(alice_dnd.to_string())
    print()

    # --- Offline ---
    alice_offline = PIFDBody(
        entity="sip:alice@pbx.example.com",
        status="closed",
    )
    print("Alice offline:")
    print(alice_offline.to_string())
    print()

    # --- Parse round-trip ---
    parsed = PIFDBody.parse(alice_online.to_string())
    print(f"Round-trip: entity={parsed.entity!r} status={parsed.status!r} note={parsed.note!r}")
    print()


def demo_publish_flow() -> None:
    print("=== PUBLISH flow (RFC 3903) ===\n")
    print(
        "1. Initial PUBLISH: no SIP-If-Match, server returns SIP-ETag\n"
        "   client.publish('sip:alice@pbx.com', content=pidf.to_string())\n"
        "   → 200 OK  SIP-ETag: abc123\n"
        "   client._presence_etag = 'abc123'\n"
    )
    print(
        "2. Refresh PUBLISH: include SIP-If-Match\n"
        "   client.publish('sip:alice@pbx.com', etag=client._presence_etag)\n"
        "   → 200 OK  SIP-ETag: abc456\n"
    )
    print(
        "3. Modify state (e.g. go offline):\n"
        "   pidf_off = PIFDBody('sip:alice@pbx.com', status='closed')\n"
        "   client.publish('sip:alice@pbx.com',\n"
        "                  content=pidf_off.to_string(),\n"
        "                  etag=client._presence_etag)\n"
    )
    print(
        "4. Withdraw (Expires: 0, no body):\n"
        "   client.publish('sip:alice@pbx.com', expires=0,\n"
        "                  etag=client._presence_etag)\n"
    )


def demo_subscribe_notify() -> None:
    print("=== SUBSCRIBE/NOTIFY presence (RFC 6665) ===\n")
    print(
        "Subscriber:\n"
        "  client.subscribe('sip:alice@pbx.com', event='presence', expires=3600)\n"
        "  → 200 OK\n"
        "\n"
        "Server sends NOTIFY:\n"
        "  Content-Type: application/pidf+xml\n"
        "  Body: PIFDBody(entity='sip:alice@pbx.com', status='open').to_string()\n"
        "\n"
        "Parse the NOTIFY body:\n"
        "  pidf = PIFDBody.parse(notify.content_text)\n"
        "  print(pidf.status)  # 'open'\n"
    )


if __name__ == "__main__":
    demo_pidf()
    demo_publish_flow()
    demo_subscribe_notify()
