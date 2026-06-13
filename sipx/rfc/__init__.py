"""Optional SIP extension feature handlers, grouped by RFC.

Each module implements a discrete SIP extension: reliable provisional
responses (PRACK), event subscription/notification, presence, client-
initiated connections (outbound), and DNS server resolution. These are
standalone handlers exercised by the test suite; they are not yet wired into
the ``AsyncClient`` runtime.

References:
    RFC 3262 - Reliability of Provisional Responses (prack)
    RFC 6665 - SIP-Specific Event Notification (events)
    RFC 3856 - A Presence Event Package for SIP (presence)
    RFC 5626 - Managing Client-Initiated Connections (outbound)
    RFC 3263 - Locating SIP Servers (dns)
"""
