"""
Call transfer via REFER + NOTIFY (RFC 3515) — local loopback demo.

Flow:
  1. Alice (client) has an established call with Bob (server)
  2. Alice sends REFER to Bob with Refer-To: Carol
  3. Bob accepts (202 Accepted), then sends NOTIFY with sipfrag progress
  4. Alice auto-200s each NOTIFY and waits for final result

The server simulates the transfer by sending three NOTIFYs:
  - 100 Trying
  - 180 Ringing
  - 200 OK (transfer succeeded)

Run:
    uv run python examples/call_transfer.py
"""

from __future__ import annotations

import asyncio

from sipx import AsyncSIPServer, AsyncSIPClient, Request


SERVER_PORT = 15063


async def main() -> None:
    server = AsyncSIPServer(local_host="127.0.0.1", local_port=SERVER_PORT)
    client_addr: dict = {}

    @server.invite()
    def on_invite(request: Request):
        return request.ok()

    @server.refer()
    def on_refer(request: Request):
        """Accept transfer and schedule NOTIFY sequence."""
        refer_to = request.headers.get("Refer-To", "")
        print(f"  Server: REFER received, Refer-To={refer_to}")
        # Schedule async NOTIFY sequence after accepting
        asyncio.get_event_loop().create_task(
            send_notify_sequence(request, client_addr.get("addr"))
        )
        return request.ok({"Contact": f"<sip:bob@127.0.0.1:{SERVER_PORT}>"})

    async def send_notify_sequence(invite_req: Request, client_destination) -> None:
        if not client_destination or not server._transport:
            return

        call_id = invite_req.headers.get("Call-ID", "")
        from_hdr = invite_req.headers.get("To", "")
        to_hdr = invite_req.headers.get("From", "")

        def _notify(sipfrag: str, sub_state: str) -> Request:
            body = sipfrag.encode()
            return Request(
                method="NOTIFY",
                uri="sip:alice@127.0.0.1",
                headers={
                    "Via": f"SIP/2.0/UDP 127.0.0.1:{SERVER_PORT};branch=z9hG4bKnotify",
                    "From": from_hdr,
                    "To": to_hdr,
                    "Call-ID": call_id,
                    "CSeq": "1 NOTIFY",
                    "Event": "refer",
                    "Subscription-State": sub_state,
                    "Content-Type": "message/sipfrag",
                    "Content-Length": str(len(body)),
                },
                content=sipfrag,
            )

        await asyncio.sleep(0.05)
        server._transport.sendto(
            _notify("SIP/2.0 100 Trying\r\n", "active").to_bytes(),
            client_destination,
        )
        await asyncio.sleep(0.05)
        server._transport.sendto(
            _notify("SIP/2.0 180 Ringing\r\n", "active").to_bytes(),
            client_destination,
        )
        await asyncio.sleep(0.05)
        server._transport.sendto(
            _notify("SIP/2.0 200 OK\r\n", "terminated;reason=noresource").to_bytes(),
            client_destination,
        )

    async with server:
        print(f"Server on 127.0.0.1:{SERVER_PORT}")

        async with AsyncSIPClient(local_host="127.0.0.1", local_port=0) as client:
            local_port = client.local_address.port
            client_addr["addr"] = ("127.0.0.1", local_port)

            print("Client: establishing call…")
            invite_resp = await client.invite(f"sip:bob@127.0.0.1:{SERVER_PORT}")
            print(f"  INVITE → {invite_resp.status_code if invite_resp else 'timeout'}")

            print("Client: transferring call to Carol…")
            notify = await client.refer_and_wait(
                f"sip:bob@127.0.0.1:{SERVER_PORT}",
                refer_to="sip:carol@pbx.example.com",
                timeout=5.0,
            )

        if notify:
            print(f"Transfer result: {notify.content_text.strip()}")
        else:
            print("Transfer timed out (no NOTIFY received)")


if __name__ == "__main__":
    asyncio.run(main())
