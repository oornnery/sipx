"""
SIP-I BR — Brazilian SIP-I extensions for STFC/SMP interconnection.

Covers:
  - ATI numeric portability (DDD+NUMBER, RN1 codes, 302 redirect)
  - P-Charging-Function-Addresses (RFC 7315, 3GPP IMS)
  - P-Preferred-Identity (RFC 3325)
  - Reason header with Q.850 cause codes (RFC 3326 / RFC 6432)
  - Brazilian DDD normalization

References:
  - ANATEL interconnection regulations
  - ITU-T Q.850, Q.1912.5
  - RFC 3325, RFC 3326, RFC 6432, RFC 7315, RFC 8606
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .._models._message import Request, Response


# ---------------------------------------------------------------------------
# Brazilian DDD codes (area codes)
# ---------------------------------------------------------------------------

# All valid 2-digit DDD codes in Brazil
VALID_DDD = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,  # SP
    21, 22, 24,                             # RJ
    27, 28,                                 # ES
    31, 32, 33, 34, 35, 37, 38,            # MG
    41, 42, 43, 44, 45, 46,                # PR
    47, 48, 49,                             # SC
    51, 53, 54, 55,                         # RS
    61,                                     # DF
    62, 64,                                 # GO
    63,                                     # TO
    65, 66,                                 # MT
    67,                                     # MS
    68,                                     # AC
    69,                                     # RO
    71, 73, 74, 75, 77,                    # BA
    79,                                     # SE
    81, 82,                                 # PE, AL
    83, 84, 85, 86, 87, 88, 89,           # PB, RN, CE, PI
    91, 92, 93, 94, 95, 96, 97, 98, 99,   # PA, AM, AP, RR, MA
}


# ---------------------------------------------------------------------------
# ATI — Automatic Telco Identification (Numeric Portability)
# ---------------------------------------------------------------------------


@dataclass
class ATIResult:
    """Result of an ATI numeric portability query."""

    number: str = ""
    rn1: str = ""
    operator: str = ""
    ported: bool = False
    not_found: bool = False

    @classmethod
    def from_redirect(cls, redirect_uri: str) -> ATIResult:
        """Parse ATI result from a 302 Redirect URI.

        Format: sip:DDD+NUMBER-RN1@ati.server
        RN1 55999 = number not found.
        """
        result = cls()

        # Extract user part from URI
        match = re.match(r"sips?:([^@]+)@", redirect_uri)
        if not match:
            return result

        user = match.group(1)

        # Parse RN1 from suffix
        if "-" in user:
            number_part, rn1 = user.rsplit("-", 1)
            result.number = number_part
            result.rn1 = rn1
            result.ported = rn1 != "" and rn1 != "55999"
            result.not_found = rn1 == "55999"
        else:
            result.number = user

        return result


class ATI:
    """ATI (Automatic Telco Identification) for Brazilian number portability.

    Usage::

        ati = ATI(client, ati_server="sip:ati.carrier.com.br")
        result = ati.query("11987654321")
        if result.ported:
            print(f"Number ported to operator RN1={result.rn1}")
    """

    def __init__(self, client, ati_server: str):
        self.client = client
        self.ati_server = ati_server

    def query(self, number: str) -> ATIResult:
        """Query ATI for number portability.

        Args:
            number: Brazilian phone number (DDD+NUMBER, e.g. "11987654321").

        Returns:
            ATIResult with RN1 code and ported status.
        """
        # Normalize number
        number = normalize_br_number(number)

        # Send INVITE to ATI server
        r = self.client.invite(
            to_uri=f"sip:{number}@{self.ati_server}",
        )

        if r and r.status_code == 302:
            # Parse redirect
            contact = r.headers.get("Contact", "")
            contact = contact.strip("<>").strip()
            return ATIResult.from_redirect(contact)

        # No redirect — number is in original operator
        return ATIResult(number=number, ported=False)


# ---------------------------------------------------------------------------
# SipIBR — Brazilian SIP-I helper class
# ---------------------------------------------------------------------------


class SipIBR:
    """Brazilian SIP-I extensions for STFC/SMP interconnection."""

    # --- P-Preferred-Identity (RFC 3325) ---

    @staticmethod
    def add_preferred_identity(request: "Request", identity: str) -> None:
        """Add P-Preferred-Identity header."""
        request.headers["P-Preferred-Identity"] = identity

    @staticmethod
    def get_preferred_identity(message: Union["Request", "Response"]) -> str | None:
        """Extract P-Preferred-Identity header."""
        return message.headers.get("P-Preferred-Identity")

    # --- P-Charging-Function-Addresses (RFC 7315) ---

    @staticmethod
    def add_charging_function_addresses(
        request: "Request",
        ccf: list[str],
        ecf: list[str] | None = None,
    ) -> None:
        """Add P-Charging-Function-Addresses header.

        Args:
            request: SIP request to modify.
            ccf: Charging Collection Function addresses.
            ecf: Event Charging Function addresses (optional).
        """
        parts = [f"ccf={addr}" for addr in ccf]
        if ecf:
            parts.extend(f"ecf={addr}" for addr in ecf)
        request.headers["P-Charging-Function-Addresses"] = "; ".join(parts)

    @staticmethod
    def get_charging_function_addresses(
        message: Union["Request", "Response"],
    ) -> dict[str, list[str]]:
        """Extract P-Charging-Function-Addresses into {ccf: [...], ecf: [...]}."""
        value = message.headers.get("P-Charging-Function-Addresses", "")
        result: dict[str, list[str]] = {"ccf": [], "ecf": []}
        for part in value.split(";"):
            part = part.strip()
            if part.startswith("ccf="):
                result["ccf"].append(part[4:].strip())
            elif part.startswith("ecf="):
                result["ecf"].append(part[4:].strip())
        return result

    # --- Reason header (RFC 3326 / RFC 6432) ---

    @staticmethod
    def add_reason(
        message: Union["Request", "Response"],
        cause: int,
        protocol: str = "Q.850",
        text: str | None = None,
        location: str | None = None,
    ) -> None:
        """Add Reason header with Q.850 cause code.

        Args:
            message: SIP request or response.
            cause: Q.850 cause code.
            protocol: Protocol name (default "Q.850").
            text: Human-readable reason text (optional).
            location: Cause location per RFC 8606 (optional).
        """
        value = f"{protocol};cause={cause}"
        if text:
            value += f';text="{text}"'
        if location:
            value += f";location={location}"
        message.headers["Reason"] = value

    @staticmethod
    def get_reason(message: Union["Request", "Response"]) -> dict | None:
        """Parse Reason header into {protocol, cause, text, location}."""
        value = message.headers.get("Reason")
        if not value:
            return None

        result: dict[str, str | int | None] = {
            "protocol": "",
            "cause": 0,
            "text": None,
            "location": None,
        }

        parts = value.split(";")
        result["protocol"] = parts[0].strip()

        for part in parts[1:]:
            part = part.strip()
            if part.startswith("cause="):
                try:
                    result["cause"] = int(part[6:])
                except ValueError:
                    pass
            elif part.startswith("text="):
                result["text"] = part[5:].strip('"')
            elif part.startswith("location="):
                result["location"] = part[9:]

        return result


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def normalize_br_number(number: str) -> str:
    """Normalize a Brazilian phone number to DDD+NUMBER format.

    Strips +55, spaces, dashes, parentheses.

    Examples:
        "+55 (11) 98765-4321" -> "11987654321"
        "011987654321" -> "11987654321"
        "11987654321" -> "11987654321"
    """
    # Remove non-digits
    digits = re.sub(r"\D", "", number)

    # Remove country code 55
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]

    # Remove trunk prefix 0
    if digits.startswith("0") and len(digits) > 10:
        digits = digits[1:]

    return digits


def is_valid_br_number(number: str) -> bool:
    """Check if a number is a valid Brazilian phone number.

    Valid formats: 10 digits (landline) or 11 digits (mobile).
    """
    digits = normalize_br_number(number)
    if len(digits) not in (10, 11):
        return False
    try:
        ddd = int(digits[:2])
    except ValueError:
        return False
    return ddd in VALID_DDD


def is_mobile(number: str) -> bool:
    """Check if a Brazilian number is mobile (starts with 9 after DDD)."""
    digits = normalize_br_number(number)
    return len(digits) == 11 and digits[2] == "9"


__all__ = [
    "ATI",
    "ATIResult",
    "SipIBR",
    "VALID_DDD",
    "normalize_br_number",
    "is_valid_br_number",
    "is_mobile",
]
