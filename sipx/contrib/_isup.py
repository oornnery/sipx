"""
ISUP binary message encoding/decoding (ITU-T Q.763).

Supports encoding and decoding of core ISUP message types used in SIP-I
interworking: IAM, ACM, ANM, REL, RLC, CPG.

References:
  - ITU-T Q.763 (ISUP formats and codes)
  - ITU-T Q.761 (ISUP functional description)
  - ITU-T Q.1912.5 (SIP-I interworking)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ISUP Message Types (ITU-T Q.763 Table 1)
# ---------------------------------------------------------------------------


class ISUPMessageType(IntEnum):
    """ISUP message type codes."""

    IAM = 0x01  # Initial Address Message
    ACM = 0x06  # Address Complete Message
    ANM = 0x09  # Answer Message
    REL = 0x0C  # Release Message
    RLC = 0x10  # Release Complete Message
    CPG = 0x2C  # Call Progress Message


# ---------------------------------------------------------------------------
# ISUP Parameter Codes (ITU-T Q.763 Table 2)
# ---------------------------------------------------------------------------


class ISUPParam(IntEnum):
    """ISUP parameter codes (ITU-T Q.763)."""

    END_OF_OPTIONAL = 0x00
    CALLED_PARTY_NUMBER = 0x04
    NATURE_OF_CONNECTION = 0x06
    FORWARD_CALL_INDICATORS = 0x07
    CALLING_PARTY_CATEGORY = 0x09
    CALLING_PARTY_NUMBER = 0x0A
    CAUSE_INDICATORS = 0x12
    REDIRECTION_INFO = 0x13
    TRANSMISSION_MEDIUM_REQ = 0x02
    USER_SERVICE_INFO = 0x1D
    EVENT_INFO = 0x24
    BACKWARD_CALL_INDICATORS = 0x11
    OPT_BACKWARD_CALL_INDICATORS = 0x29
    ACCESS_TRANSPORT = 0x03


# ---------------------------------------------------------------------------
# Calling Party Category (ITU-T Q.763 3.11)
# ---------------------------------------------------------------------------


class CallingPartyCategory(IntEnum):
    """Common calling party categories."""

    UNKNOWN = 0x00
    OPERATOR_FR = 0x01  # Operator, language French
    OPERATOR_EN = 0x02  # Operator, language English
    OPERATOR_DE = 0x03  # Operator, language German
    ORDINARY = 0x0A  # Ordinary calling subscriber
    PRIORITY = 0x0B  # Calling subscriber with priority
    DATA_CALL = 0x0C  # Data call (voice band data)
    TEST_CALL = 0x0D  # Test call
    PAYPHONE = 0x0F  # Payphone


# ---------------------------------------------------------------------------
# Nature of Address Indicator
# ---------------------------------------------------------------------------


class NatureOfAddress(IntEnum):
    """Nature of Address Indicator values."""

    SUBSCRIBER = 0x01
    UNKNOWN = 0x02
    NATIONAL = 0x03
    INTERNATIONAL = 0x04


# ---------------------------------------------------------------------------
# BCD Phone Number Encoding/Decoding
# ---------------------------------------------------------------------------


def encode_called_party(
    number: str,
    nai: int = NatureOfAddress.NATIONAL,
    numbering_plan: int = 0x01,  # ISDN/telephony (E.164)
    inn: int = 0x00,  # routing to internal network number allowed
) -> bytes:
    """Encode phone number in ISUP Called Party Number format (Q.763 3.9).

    Format:
      byte 0: odd/even indicator (bit 8) + nature of address indicator (bits 1-7)
      byte 1: INN indicator (bit 8) + numbering plan (bits 5-7) + address signals
      bytes 2+: BCD encoded digits (2 per byte, low nibble first)

    Args:
        number: Phone number digits (e.g. "5511987654321").
        nai: Nature of address indicator.
        numbering_plan: Numbering plan indicator (1 = E.164).
        inn: Internal Network Number indicator.

    Returns:
        Encoded Called Party Number parameter bytes.
    """
    digits = [int(d) for d in number if d.isdigit()]
    odd = len(digits) % 2 == 1

    # Byte 0: odd/even (bit 8) + NAI (bits 1-7)
    byte0 = (nai & 0x7F) | (0x80 if odd else 0x00)

    # Byte 1: INN (bit 8) + numbering plan (bits 5-7) + spare (bits 1-4)
    byte1 = ((inn & 0x01) << 7) | ((numbering_plan & 0x07) << 4)

    # BCD encode digits: two per byte, low nibble = first digit
    bcd = bytearray()
    for i in range(0, len(digits), 2):
        low = digits[i]
        high = digits[i + 1] if (i + 1) < len(digits) else 0x00
        bcd.append((high << 4) | low)

    return bytes([byte0, byte1]) + bytes(bcd)


def decode_called_party(data: bytes) -> tuple[str, int]:
    """Decode ISUP Called Party Number (Q.763 3.9).

    Args:
        data: Raw Called Party Number parameter bytes.

    Returns:
        Tuple of (number_string, nature_of_address_indicator).
    """
    if len(data) < 2:
        return ("", 0)

    byte0 = data[0]
    odd = bool(byte0 & 0x80)
    nai = byte0 & 0x7F

    # Decode BCD digits from byte 2 onwards
    digits: list[str] = []
    for b in data[2:]:
        low = b & 0x0F
        high = (b >> 4) & 0x0F
        digits.append(str(low))
        digits.append(str(high))

    # If odd number of digits, drop the trailing filler
    if odd and digits:
        digits = digits[:-1]

    return ("".join(digits), nai)


def encode_calling_party(
    number: str,
    nai: int = NatureOfAddress.NATIONAL,
    numbering_plan: int = 0x01,
    ni: int = 0x00,  # number incomplete
    screening: int = 0x01,  # user provided, verified and passed
    presentation: int = 0x00,  # presentation allowed
) -> bytes:
    """Encode phone number in ISUP Calling Party Number format (Q.763 3.10).

    Format:
      byte 0: odd/even indicator (bit 8) + nature of address indicator (bits 1-7)
      byte 1: NI (bit 8) + numbering plan (bits 5-7) + presentation (bits 3-4)
              + screening (bits 1-2)
      bytes 2+: BCD encoded digits

    Args:
        number: Phone number digits.
        nai: Nature of address indicator.
        numbering_plan: Numbering plan indicator.
        ni: Number Incomplete indicator.
        screening: Screening indicator.
        presentation: Address presentation restricted indicator.

    Returns:
        Encoded Calling Party Number parameter bytes.
    """
    digits = [int(d) for d in number if d.isdigit()]
    odd = len(digits) % 2 == 1

    byte0 = (nai & 0x7F) | (0x80 if odd else 0x00)
    byte1 = (
        ((ni & 0x01) << 7)
        | ((numbering_plan & 0x07) << 4)
        | ((presentation & 0x03) << 2)
        | (screening & 0x03)
    )

    bcd = bytearray()
    for i in range(0, len(digits), 2):
        low = digits[i]
        high = digits[i + 1] if (i + 1) < len(digits) else 0x00
        bcd.append((high << 4) | low)

    return bytes([byte0, byte1]) + bytes(bcd)


def decode_calling_party(data: bytes) -> tuple[str, int, int, int]:
    """Decode ISUP Calling Party Number (Q.763 3.10).

    Args:
        data: Raw Calling Party Number parameter bytes.

    Returns:
        Tuple of (number, nai, presentation, screening).
    """
    if len(data) < 2:
        return ("", 0, 0, 0)

    byte0 = data[0]
    odd = bool(byte0 & 0x80)
    nai = byte0 & 0x7F

    byte1 = data[1]
    presentation = (byte1 >> 2) & 0x03
    screening = byte1 & 0x03

    digits: list[str] = []
    for b in data[2:]:
        low = b & 0x0F
        high = (b >> 4) & 0x0F
        digits.append(str(low))
        digits.append(str(high))

    if odd and digits:
        digits = digits[:-1]

    return ("".join(digits), nai, presentation, screening)


def encode_cause_indicators(
    cause: int,
    coding_standard: int = 0x00,  # ITU-T standard
    location: int = 0x01,  # user, local private network
) -> bytes:
    """Encode ISUP Cause Indicators (Q.763 3.12).

    Format:
      byte 0: ext(1) + coding standard(2) + spare(1) + location(4)
      byte 1: ext(1) + cause value(7)

    Args:
        cause: Q.850 cause code (0-127).
        coding_standard: Coding standard (0 = ITU-T).
        location: Location indicator.

    Returns:
        Encoded Cause Indicators parameter bytes.
    """
    # Byte 0: ext=1 (no extension) + coding standard + spare(0) + location
    byte0 = 0x80 | ((coding_standard & 0x03) << 5) | (location & 0x0F)
    # Byte 1: ext=1 + cause value
    byte1 = 0x80 | (cause & 0x7F)
    return bytes([byte0, byte1])


def decode_cause_indicators(data: bytes) -> tuple[int, int, int]:
    """Decode ISUP Cause Indicators (Q.763 3.12).

    Args:
        data: Raw Cause Indicators parameter bytes.

    Returns:
        Tuple of (cause_code, coding_standard, location).
    """
    if len(data) < 2:
        return (0, 0, 0)

    byte0 = data[0]
    location = byte0 & 0x0F
    coding_standard = (byte0 >> 5) & 0x03

    byte1 = data[1]
    cause = byte1 & 0x7F

    return (cause, coding_standard, location)


# ---------------------------------------------------------------------------
# ISUPMessage — encode/decode full ISUP messages
# ---------------------------------------------------------------------------

# Fixed mandatory parameters per message type (in order).
# Each entry: (param_code, length_in_bytes)
_IAM_FIXED: list[tuple[int, int]] = [
    (ISUPParam.NATURE_OF_CONNECTION, 1),
    (ISUPParam.FORWARD_CALL_INDICATORS, 2),
    (ISUPParam.CALLING_PARTY_CATEGORY, 1),
    (ISUPParam.TRANSMISSION_MEDIUM_REQ, 1),
]

_ACM_FIXED: list[tuple[int, int]] = [
    (ISUPParam.BACKWARD_CALL_INDICATORS, 2),
]

_CPG_FIXED: list[tuple[int, int]] = [
    (ISUPParam.EVENT_INFO, 1),
]

# Variable mandatory parameters per message type
# Each entry: param_code (length is encoded in the message)
_IAM_VARIABLE: list[int] = [
    ISUPParam.CALLED_PARTY_NUMBER,
]

_REL_VARIABLE: list[int] = [
    ISUPParam.CAUSE_INDICATORS,
]

# Maps message type -> (fixed_params, variable_mandatory_params)
_MSG_STRUCTURE: dict[int, tuple[list[tuple[int, int]], list[int]]] = {
    ISUPMessageType.IAM: (_IAM_FIXED, _IAM_VARIABLE),
    ISUPMessageType.ACM: (_ACM_FIXED, []),
    ISUPMessageType.ANM: ([], []),
    ISUPMessageType.REL: ([], _REL_VARIABLE),
    ISUPMessageType.RLC: ([], []),
    ISUPMessageType.CPG: (_CPG_FIXED, []),
}


@dataclass
class ISUPMessage:
    """ISUP message with binary encoding/decoding (ITU-T Q.763).

    The message carries a type, circuit identification code, and a dict of
    parameters keyed by parameter code (int) with raw bytes values.
    """

    message_type: ISUPMessageType
    circuit_id: int = 0
    params: dict[int, bytes] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """Encode to ISUP binary format.

        Layout:
          [CIC: 2 bytes LE] [Message Type: 1 byte]
          [Fixed mandatory params]
          [Pointer(s) to variable mandatory params]
          [Pointer to optional part (0 if none)]
          [Variable mandatory params: length(1) + value(N)]
          [Optional params: code(1) + length(1) + value(N) ...]
          [End of optional: 0x00]
        """
        buf = bytearray()

        # CIC (2 bytes, little-endian)
        buf.append(self.circuit_id & 0xFF)
        buf.append((self.circuit_id >> 8) & 0x0F)

        # Message type (1 byte)
        buf.append(int(self.message_type) & 0xFF)

        fixed_defs, var_defs = _MSG_STRUCTURE.get(self.message_type, ([], []))

        # Track which param codes are structurally placed
        structural_codes = {code for code, _ in fixed_defs}
        structural_codes.update(var_defs)

        # --- Fixed mandatory parameters ---
        for param_code, length in fixed_defs:
            value = self.params.get(param_code, bytes(length))
            # Pad or truncate to expected length
            value = (value + bytes(length))[:length]
            buf.extend(value)

        # --- Collect variable mandatory and optional parts ---
        var_parts: list[bytes] = []
        for param_code in var_defs:
            value = self.params.get(param_code, b"")
            var_parts.append(value)

        optional_codes = [
            code
            for code in self.params
            if code not in structural_codes and code != ISUPParam.END_OF_OPTIONAL
        ]

        # --- Pointers ---
        # Number of pointers = len(var_defs) + 1 (optional pointer)
        num_pointers = len(var_defs) + 1
        # Calculate pointer values
        # Each pointer is relative to its own position
        # Variable parts follow after all pointers
        offset = num_pointers  # start offset from first pointer position
        for i, value in enumerate(var_parts):
            ptr = offset - i
            buf.append(ptr & 0xFF)
            offset += 1 + len(value)  # 1 for length byte + value

        # Optional part pointer
        if optional_codes:
            opt_ptr = offset - len(var_defs)
            buf.append(opt_ptr & 0xFF)
        else:
            buf.append(0x00)  # no optional part

        # --- Variable mandatory parameters ---
        for value in var_parts:
            buf.append(len(value) & 0xFF)
            buf.extend(value)

        # --- Optional parameters ---
        for param_code in optional_codes:
            value = self.params[param_code]
            buf.append(param_code & 0xFF)
            buf.append(len(value) & 0xFF)
            buf.extend(value)

        if optional_codes:
            buf.append(0x00)  # end of optional parameters

        return bytes(buf)

    @classmethod
    def from_bytes(cls, data: bytes) -> ISUPMessage:
        """Decode from ISUP binary format.

        Args:
            data: Raw ISUP message bytes (including CIC).

        Returns:
            Decoded ISUPMessage.

        Raises:
            ValueError: If data is too short or message type unknown.
        """
        if len(data) < 3:
            msg = f"ISUP message too short: {len(data)} bytes"
            raise ValueError(msg)

        circuit_id = data[0] | ((data[1] & 0x0F) << 8)

        try:
            message_type = ISUPMessageType(data[2])
        except ValueError:
            msg = f"Unknown ISUP message type: 0x{data[2]:02X}"
            raise ValueError(msg) from None

        params: dict[int, bytes] = {}
        pos = 3

        fixed_defs, var_defs = _MSG_STRUCTURE.get(message_type, ([], []))

        # --- Fixed mandatory parameters ---
        for param_code, length in fixed_defs:
            if pos + length > len(data):
                msg = f"Truncated fixed param 0x{param_code:02X}"
                raise ValueError(msg)
            params[param_code] = data[pos : pos + length]
            pos += length

        # --- Pointers ---
        pointer_base = pos
        num_pointers = len(var_defs) + 1
        if pos + num_pointers > len(data):
            msg = "Truncated pointer area"
            raise ValueError(msg)

        pointers = list(data[pos : pos + num_pointers])
        pos += num_pointers

        # --- Variable mandatory parameters ---
        for i, param_code in enumerate(var_defs):
            ptr = pointers[i]
            # Pointer is relative to its own position
            abs_pos = pointer_base + i + ptr
            if abs_pos >= len(data):
                msg = f"Variable param pointer out of bounds: 0x{param_code:02X}"
                raise ValueError(msg)
            length = data[abs_pos]
            value_start = abs_pos + 1
            if value_start + length > len(data):
                msg = f"Truncated variable param 0x{param_code:02X}"
                raise ValueError(msg)
            params[param_code] = data[value_start : value_start + length]

        # --- Optional parameters ---
        opt_ptr = pointers[-1] if pointers else 0
        if opt_ptr != 0:
            # Optional pointer is relative to its own position
            opt_pos = pointer_base + len(var_defs) + opt_ptr
            while opt_pos < len(data):
                param_code = data[opt_pos]
                if param_code == 0x00:
                    break  # end of optional
                opt_pos += 1
                if opt_pos >= len(data):
                    break
                length = data[opt_pos]
                opt_pos += 1
                if opt_pos + length > len(data):
                    logger.warning("Truncated optional param 0x%02X", param_code)
                    break
                params[param_code] = data[opt_pos : opt_pos + length]
                opt_pos += length

        return cls(
            message_type=message_type,
            circuit_id=circuit_id,
            params=params,
        )

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create_iam(
        cls,
        called: str,
        calling: str = "",
        circuit_id: int = 0,
        called_nai: int = NatureOfAddress.NATIONAL,
        calling_nai: int = NatureOfAddress.NATIONAL,
        calling_category: int = CallingPartyCategory.ORDINARY,
        nature_of_connection: int = 0x00,
        forward_call_indicators: bytes = b"\x20\x01",
        transmission_medium: int = 0x00,  # speech
    ) -> ISUPMessage:
        """Create an Initial Address Message (IAM).

        Args:
            called: Called party number digits.
            calling: Calling party number digits (optional).
            circuit_id: Circuit Identification Code.
            called_nai: Called party Nature of Address.
            calling_nai: Calling party Nature of Address.
            calling_category: Calling party category code.
            nature_of_connection: Nature of connection indicators byte.
            forward_call_indicators: Forward call indicators (2 bytes).
            transmission_medium: Transmission medium requirement.

        Returns:
            Configured IAM ISUPMessage.
        """
        params: dict[int, bytes] = {
            ISUPParam.NATURE_OF_CONNECTION: bytes([nature_of_connection]),
            ISUPParam.FORWARD_CALL_INDICATORS: forward_call_indicators,
            ISUPParam.CALLING_PARTY_CATEGORY: bytes([calling_category]),
            ISUPParam.TRANSMISSION_MEDIUM_REQ: bytes([transmission_medium]),
            ISUPParam.CALLED_PARTY_NUMBER: encode_called_party(called, nai=called_nai),
        }

        if calling:
            params[ISUPParam.CALLING_PARTY_NUMBER] = encode_calling_party(
                calling, nai=calling_nai
            )

        return cls(
            message_type=ISUPMessageType.IAM,
            circuit_id=circuit_id,
            params=params,
        )

    @classmethod
    def create_acm(
        cls,
        circuit_id: int = 0,
        backward_call_indicators: bytes = b"\x16\x04",
    ) -> ISUPMessage:
        """Create an Address Complete Message (ACM).

        Args:
            circuit_id: Circuit Identification Code.
            backward_call_indicators: Backward call indicators (2 bytes).

        Returns:
            Configured ACM ISUPMessage.
        """
        return cls(
            message_type=ISUPMessageType.ACM,
            circuit_id=circuit_id,
            params={
                ISUPParam.BACKWARD_CALL_INDICATORS: backward_call_indicators,
            },
        )

    @classmethod
    def create_anm(cls, circuit_id: int = 0) -> ISUPMessage:
        """Create an Answer Message (ANM).

        Args:
            circuit_id: Circuit Identification Code.

        Returns:
            Configured ANM ISUPMessage.
        """
        return cls(
            message_type=ISUPMessageType.ANM,
            circuit_id=circuit_id,
        )

    @classmethod
    def create_rel(
        cls,
        cause: int = 16,
        circuit_id: int = 0,
        location: int = 0x01,
    ) -> ISUPMessage:
        """Create a Release Message (REL).

        Args:
            cause: Q.850 cause code (default 16 = normal clearing).
            circuit_id: Circuit Identification Code.
            location: Cause location indicator.

        Returns:
            Configured REL ISUPMessage.
        """
        return cls(
            message_type=ISUPMessageType.REL,
            circuit_id=circuit_id,
            params={
                ISUPParam.CAUSE_INDICATORS: encode_cause_indicators(
                    cause, location=location
                ),
            },
        )

    @classmethod
    def create_rlc(cls, circuit_id: int = 0) -> ISUPMessage:
        """Create a Release Complete Message (RLC).

        Args:
            circuit_id: Circuit Identification Code.

        Returns:
            Configured RLC ISUPMessage.
        """
        return cls(
            message_type=ISUPMessageType.RLC,
            circuit_id=circuit_id,
        )

    @classmethod
    def create_cpg(
        cls,
        event_info: int = 0x01,
        circuit_id: int = 0,
    ) -> ISUPMessage:
        """Create a Call Progress Message (CPG).

        Args:
            event_info: Event information indicator.
            circuit_id: Circuit Identification Code.

        Returns:
            Configured CPG ISUPMessage.
        """
        return cls(
            message_type=ISUPMessageType.CPG,
            circuit_id=circuit_id,
            params={
                ISUPParam.EVENT_INFO: bytes([event_info]),
            },
        )

    # ------------------------------------------------------------------
    # Parameter access helpers
    # ------------------------------------------------------------------

    def get_called_party(self) -> tuple[str, int] | None:
        """Extract called party number from params.

        Returns:
            Tuple of (number, nai) or None if not present.
        """
        data = self.params.get(ISUPParam.CALLED_PARTY_NUMBER)
        if data is None:
            return None
        return decode_called_party(data)

    def get_calling_party(self) -> tuple[str, int, int, int] | None:
        """Extract calling party number from params.

        Returns:
            Tuple of (number, nai, presentation, screening) or None.
        """
        data = self.params.get(ISUPParam.CALLING_PARTY_NUMBER)
        if data is None:
            return None
        return decode_calling_party(data)

    def get_cause(self) -> tuple[int, int, int] | None:
        """Extract cause indicators from params.

        Returns:
            Tuple of (cause_code, coding_standard, location) or None.
        """
        data = self.params.get(ISUPParam.CAUSE_INDICATORS)
        if data is None:
            return None
        return decode_cause_indicators(data)


__all__ = [
    "CallingPartyCategory",
    "ISUPMessage",
    "ISUPMessageType",
    "ISUPParam",
    "NatureOfAddress",
    "decode_called_party",
    "decode_calling_party",
    "decode_cause_indicators",
    "encode_called_party",
    "encode_calling_party",
    "encode_cause_indicators",
]
