"""
SIP-I / ISUP interworking support (ITU-T Q.1912.5).

Provides ISUP cause code <-> SIP status code mapping tables and
helper functions for common SIP-I headers (P-Asserted-Identity,
P-Charging-Vector).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .._models._message import Request, Response

# ---------------------------------------------------------------------------
# ISUP cause -> SIP status  (ITU-T Q.1912.5 / RFC 3398)
# ---------------------------------------------------------------------------

ISUP_CAUSE_TO_SIP: dict[int, int] = {
    1: 404,  # Unallocated number
    2: 404,  # No route to specified transit network
    3: 404,  # No route to destination
    16: 487,  # Normal clearing -> Request Terminated (BYE context)
    17: 486,  # User busy
    18: 408,  # No user responding
    19: 480,  # No answer from user
    21: 403,  # Call rejected
    27: 502,  # Destination out of order
    28: 484,  # Invalid number format (address incomplete)
    34: 503,  # No circuit/channel available
    38: 503,  # Network out of order
    41: 503,  # Temporary failure
    42: 503,  # Switching equipment congestion
    47: 503,  # Resource unavailable
    55: 403,  # Incoming calls barred within CUG
    57: 403,  # Bearer capability not authorized
    58: 503,  # Bearer capability not presently available
    63: 503,  # Service or option not available
    65: 488,  # Bearer capability not implemented
    79: 501,  # Service or option not implemented
    87: 502,  # User not member of CUG
    88: 488,  # Incompatible destination
    102: 504,  # Recovery on timer expiry
    111: 500,  # Protocol error, unspecified
    127: 500,  # Interworking, unspecified
}

# ---------------------------------------------------------------------------
# SIP status -> ISUP cause  (reverse mapping)
# ---------------------------------------------------------------------------

SIP_TO_ISUP_CAUSE: dict[int, int] = {
    400: 41,  # Bad Request -> Temporary failure
    401: 21,  # Unauthorized -> Call rejected
    403: 21,  # Forbidden -> Call rejected
    404: 1,  # Not Found -> Unallocated number
    405: 63,  # Method Not Allowed -> Service/option unavailable
    408: 18,  # Request Timeout -> No user responding
    410: 1,  # Gone -> Unallocated number
    480: 19,  # Temporarily Unavailable -> No answer from user
    484: 28,  # Address Incomplete -> Invalid number format
    486: 17,  # Busy Here -> User busy
    487: 16,  # Request Terminated -> Normal clearing
    488: 127,  # Not Acceptable Here -> Interworking
    500: 41,  # Server Internal Error -> Temporary failure
    501: 79,  # Not Implemented -> Service not implemented
    502: 38,  # Bad Gateway -> Network out of order
    503: 34,  # Service Unavailable -> No circuit/channel available
    504: 102,  # Server Timeout -> Recovery on timer expiry
    600: 17,  # Busy Everywhere -> User busy
    603: 21,  # Decline -> Call rejected
    604: 1,  # Does Not Exist Anywhere -> Unallocated number
}


# ---------------------------------------------------------------------------
# SIP-I Helper
# ---------------------------------------------------------------------------


class SipI:
    """SIP-I / ISUP interworking helper (ITU-T Q.1912.5)."""

    @staticmethod
    def isup_to_sip(cause: int) -> int:
        """Convert ISUP cause code to SIP status code (500 if unknown)."""
        return ISUP_CAUSE_TO_SIP.get(cause, 500)

    @staticmethod
    def sip_to_isup(status: int) -> int:
        """Convert SIP status code to ISUP cause code (127 if unknown)."""
        return SIP_TO_ISUP_CAUSE.get(status, 127)

    @staticmethod
    def add_pai(request: "Request", identity: str) -> None:
        """Add P-Asserted-Identity header."""
        request.headers["P-Asserted-Identity"] = identity

    @staticmethod
    def get_pai(message: Union["Request", "Response"]) -> str | None:
        """Extract P-Asserted-Identity header value."""
        return message.headers.get("P-Asserted-Identity")

    @staticmethod
    def add_charging_vector(
        request: "Request",
        icid: str,
        orig_ioi: str | None = None,
        term_ioi: str | None = None,
    ) -> None:
        """Add P-Charging-Vector header."""
        value = f"icid-value={icid}"
        if orig_ioi:
            value += f";orig-ioi={orig_ioi}"
        if term_ioi:
            value += f";term-ioi={term_ioi}"
        request.headers["P-Charging-Vector"] = value


__all__ = [
    "SipI",
    "ISUP_CAUSE_TO_SIP",
    "SIP_TO_ISUP_CAUSE",
]
