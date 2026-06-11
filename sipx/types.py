"""Core SIP type aliases.

These aliases provide named types for SIP primitives without adding
runtime overhead. They document expected value shapes and can be
replaced with stricter types later without changing call sites.
"""

from typing import Union

#: SIP method string. Expected values per RFC 3261 and extensions:
#: INVITE, ACK, BYE, CANCEL, REGISTER, OPTIONS, INFO, PRACK,
#: SUBSCRIBE, NOTIFY, PUBLISH, REFER, MESSAGE, UPDATE.
SipMethod = str

#: SIP response status code (e.g. 200, 404, 487).
StatusCode = int

#: SIP header field name (case-insensitive at the protocol level).
HeaderName = str

#: SIP header field value. Single values are strings; repeated headers
#: may be represented as a list of strings.
HeaderValue = Union[str, list[str]]

#: SIP URI as a string (e.g. ``sip:alice@example.com``).
Uri = str
