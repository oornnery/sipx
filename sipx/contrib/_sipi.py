"""
SIP-I / ISUP interworking support (ITU-T Q.1912.5).

Provides ISUP cause code <-> SIP status code mapping tables,
helper functions for common SIP-I headers (P-Asserted-Identity,
P-Charging-Vector), and multipart/mixed body encoding for SDP + ISUP.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Union

from sipx.contrib._isup import ISUPMessage

if TYPE_CHECKING:
    from ..models._message import Request, Response

logger = logging.getLogger(__name__)

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

    # ------------------------------------------------------------------
    # Multipart SIP-I body (SDP + ISUP)
    # ------------------------------------------------------------------

    @staticmethod
    def create_sipi_body(
        sdp: str,
        isup_msg: ISUPMessage,
        boundary: str | None = None,
    ) -> tuple[str, bytes]:
        """Create multipart/mixed body with SDP + ISUP binary.

        Produces a MIME multipart/mixed body suitable for SIP-I messages,
        containing an application/sdp part and an application/isup part.

        Args:
            sdp: SDP body text.
            isup_msg: ISUP message to encode as binary.
            boundary: MIME boundary string (auto-generated if not provided).

        Returns:
            Tuple of (content_type_header, body_bytes).
            content_type_header includes the boundary parameter.
        """
        if boundary is None:
            boundary = f"sipx-{uuid.uuid4().hex[:16]}"

        isup_bytes = isup_msg.to_bytes()

        parts: list[bytes] = []

        # SDP part
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b"Content-Type: application/sdp\r\n")
        parts.append(b"Content-Disposition: session\r\n")
        parts.append(b"\r\n")
        # Normalize SDP line endings to CRLF
        sdp_normalized = sdp.replace("\r\n", "\n").replace("\n", "\r\n")
        if not sdp_normalized.endswith("\r\n"):
            sdp_normalized += "\r\n"
        parts.append(sdp_normalized.encode())

        # ISUP part
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b"Content-Type: application/isup; version=itu-t92+\r\n")
        parts.append(b"Content-Disposition: signal;handling=optional\r\n")
        parts.append(b"\r\n")
        parts.append(isup_bytes)
        parts.append(b"\r\n")

        # Closing boundary
        parts.append(f"--{boundary}--\r\n".encode())

        body = b"".join(parts)
        content_type = f"multipart/mixed; boundary={boundary}"

        return (content_type, body)

    @staticmethod
    def parse_sipi_body(
        content_type: str,
        body: bytes,
    ) -> tuple[str | None, ISUPMessage | None]:
        """Parse multipart/mixed body, extract SDP and ISUP.

        Args:
            content_type: Content-Type header value (must contain boundary).
            body: Raw multipart body bytes.

        Returns:
            Tuple of (sdp_text, isup_message). Either may be None if the
            corresponding part is not found.
        """
        # Extract boundary from Content-Type
        match = re.search(r"boundary=([^\s;]+)", content_type)
        if not match:
            logger.warning("No boundary found in Content-Type: %s", content_type)
            return (None, None)

        boundary = match.group(1).strip('"')
        delimiter = f"--{boundary}".encode()

        # Split body into parts
        raw_parts = body.split(delimiter)

        sdp_text: str | None = None
        isup_msg: ISUPMessage | None = None

        for part in raw_parts:
            # Skip preamble and closing delimiter
            if not part or part.startswith(b"--"):
                continue

            # Strip leading CRLF
            if part.startswith(b"\r\n"):
                part = part[2:]

            # Split headers from body at first double CRLF
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            header_section = part[:header_end].decode("utf-8", errors="replace")
            part_body = part[header_end + 4 :]

            # Strip trailing CRLF from part body
            if part_body.endswith(b"\r\n"):
                part_body = part_body[:-2]

            # Detect content type
            ct_lower = header_section.lower()
            if "application/sdp" in ct_lower:
                sdp_text = part_body.decode("utf-8", errors="replace")
            elif "application/isup" in ct_lower:
                try:
                    isup_msg = ISUPMessage.from_bytes(part_body)
                except (ValueError, IndexError) as exc:
                    logger.warning("Failed to decode ISUP part: %s", exc)

        return (sdp_text, isup_msg)


__all__ = [
    "SipI",
    "ISUP_CAUSE_TO_SIP",
    "SIP_TO_ISUP_CAUSE",
]
