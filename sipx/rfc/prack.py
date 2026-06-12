"""RFC 3262 PRACK (Provisional Response Acknowledgment).

This module implements the PRACK mechanism for reliable provisional responses
in SIP. When a UAC receives a provisional response (1xx) with the
Require: 100rel header, it must acknowledge it with a PRACK request.

References:
    RFC 3262 - Reliability of Provisional Responses in the Session
               Initiation Protocol (SIP)
    RFC 3261 §17.1.1 - INVITE client transaction
"""

from __future__ import annotations

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response


class PrackHandler:
    """Handles PRACK generation and RSeq tracking for reliable provisional responses.

    Per RFC 3262, when a UAC receives a reliable provisional response (a 1xx
    response with Require: 100rel), it must send a PRACK request to acknowledge
    receipt. The PRACK contains a RAck header that identifies which provisional
    response is being acknowledged.

    The handler tracks RSeq numbers to detect duplicate provisional responses.
    If a duplicate RSeq is received, a ProtocolError is raised.
    """

    def __init__(self) -> None:
        """Initialize a new PRACK handler with empty RSeq tracking."""
        self._seen_rseq: set[int] = set()
        self._prack_cseq: int = 1

    def is_reliable(self, response: Response) -> bool:
        """Check if a response is a reliable provisional response.

        A reliable provisional response is a 1xx response that includes
        the Require: 100rel header.

        Args:
            response: The SIP response to check.

        Returns:
            True if the response is a reliable provisional response.
        """
        if response.status_code < 100 or response.status_code >= 200:
            return False
        require = response.headers.get("Require", "")
        if isinstance(require, list):
            return "100rel" in require
        return "100rel" in require

    def generate_prack(self, provisional: Response) -> Request:
        """Generate a PRACK request for a reliable provisional response.

        Args:
            provisional: The reliable provisional response to acknowledge.

        Returns:
            A PRACK Request with the appropriate RAck header.

        Raises:
            ProtocolError: If the response is not a reliable provisional,
                if the RSeq header is missing or invalid, or if a duplicate
                RSeq is detected.
        """
        # Validate it's a reliable provisional response
        if not self.is_reliable(provisional):
            raise ProtocolError(
                "Response is not a reliable provisional response "
                "(requires 1xx with Require: 100rel)",
                rfc_ref="RFC 3262 §3",
            )

        # Extract RSeq
        rseq_raw = provisional.headers.get("RSeq")
        if rseq_raw is None:
            raise ProtocolError(
                "Reliable provisional response missing RSeq header",
                rfc_ref="RFC 3262 §3",
            )

        try:
            rseq = int(rseq_raw) if not isinstance(rseq_raw, list) else int(rseq_raw[0])
        except ValueError, IndexError:
            raise ProtocolError(
                f"Invalid RSeq header value: {rseq_raw}",
                rfc_ref="RFC 3262 §3",
            )

        # Check for duplicate RSeq
        if rseq in self._seen_rseq:
            raise ProtocolError(
                f"Duplicate RSeq {rseq} already acknowledged",
                rfc_ref="RFC 3262 §3",
            )

        # Extract CSeq from the original request
        original_request = provisional.request
        if original_request is None:
            raise ProtocolError(
                "Provisional response not linked to an original request",
                rfc_ref="RFC 3262 §3",
            )

        cseq_num = self._extract_cseq_number(original_request)
        method = original_request.method

        # Build RAck header: RAck: <rseq> <cseq> <method>
        rack_value = f"{rseq} {cseq_num} {method}"

        # Mark RSeq as seen
        self._seen_rseq.add(rseq)

        # Build PRACK request
        prack_cseq = self._prack_cseq
        self._prack_cseq += 1

        prack_headers: dict[str, str | list[str]] = {
            "RAck": rack_value,
            "CSeq": f"{prack_cseq} PRACK",
        }

        # Copy essential headers from the original request
        for header in ("From", "To", "Call-ID", "Via"):
            if header in original_request.headers:
                prack_headers[header] = original_request.headers[header]

        return Request(
            method="PRACK",
            uri=original_request.uri,
            headers=prack_headers,
            body=None,
        )

    def _extract_cseq_number(self, request: Request) -> int:
        """Extract the CSeq number from a request's CSeq header.

        Args:
            request: The SIP request.

        Returns:
            The CSeq number, defaulting to 1 if not present.
        """
        cseq_raw = request.headers.get("CSeq")
        if cseq_raw is None:
            return 1
        if isinstance(cseq_raw, list):
            cseq_raw = cseq_raw[0]
        # CSeq format: "<number> <method>"
        parts = str(cseq_raw).split(None, 1)
        try:
            return int(parts[0])
        except ValueError, IndexError:
            return 1

    @property
    def seen_rseq_numbers(self) -> frozenset[int]:
        """Return the set of RSeq numbers that have been acknowledged."""
        return frozenset(self._seen_rseq)
