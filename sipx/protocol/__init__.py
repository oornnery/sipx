"""Runtime SIP protocol layer used by the AsyncClient.

Contains the pieces the client drives at runtime: the Digest authentication
flow, dialog tracking, transaction state machines, event hooks, and
provisional-response handling. Built on ``sipx.models`` and consumed by
``sipx.client``.

References:
    RFC 3261 §12 - Dialogs
    RFC 3261 §17 - Transactions
    RFC 3261 §22 - Usage of HTTP Authentication
"""
