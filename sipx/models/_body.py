"""
SIP Message Body Models and Parsers (Simplified).

Supports SDP (Session Description Protocol) as the primary body type.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .._utils import logger

_log = logger.getChild("sdp")


# ============================================================================
# Base Classes
# ============================================================================


class MessageBody(ABC):
    """Base class for SIP message bodies."""

    @abstractmethod
    def to_bytes(self) -> bytes:
        """Serialize body to bytes."""
        pass

    @abstractmethod
    def to_string(self) -> str:
        """Serialize body to string."""
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        """Return the Content-Type header value for this body."""
        pass


# ============================================================================
# SDP (Session Description Protocol) - RFC 4566
# ============================================================================


@dataclass
class SDPBody(MessageBody):
    """
    Session Description Protocol (RFC 4566).

    Simplified structure with all fields directly in the body.

    Example:
        sdp = SDPBody(
            session_name="SIP Call",
            origin_username="-",
            origin_session_id="123",
            origin_session_version="0",
            connection="IN IP4 192.168.1.100"
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0", "8"])
    """

    # Session fields (required - must come first)
    session_name: str
    origin_username: str
    origin_session_id: str
    origin_session_version: str

    # Origin fields (optional with defaults)
    origin_network_type: str = "IN"
    origin_address_type: str = "IP4"
    origin_address: str = "127.0.0.1"

    # Session-level fields (optional)
    version: int = 0
    connection: Optional[str] = None  # c= line
    session_info: Optional[str] = None  # i= line
    uri: Optional[str] = None  # u= line
    email: Optional[str] = None  # e= line
    phone: Optional[str] = None  # p= line
    bandwidth: Dict[str, int] = field(default_factory=dict)  # b= lines
    timing: List[str] = field(
        default_factory=lambda: ["0 0"]
    )  # t= lines (required, default to "0 0")
    repeat_times: List[str] = field(default_factory=list)  # r= lines
    time_zones: Optional[str] = None  # z= line
    encryption_key: Optional[str] = None  # k= line
    attributes: Dict[str, Optional[str]] = field(default_factory=dict)  # a= lines

    # Media descriptions (list of dicts)
    media_descriptions: List[Dict[str, Any]] = field(default_factory=list)

    def add_media(
        self,
        media: str,
        port: int,
        protocol: str,
        formats: List[str],
        *,
        port_count: int = 1,
        connection: Optional[str] = None,
        title: Optional[str] = None,
        bandwidth: Optional[Dict[str, int]] = None,
        attributes: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        """
        Add a media description to the SDP.

        Args:
            media: Media type ("audio", "video", "text", "application", "message")
            port: Port number (0 to reject media)
            protocol: Transport protocol (e.g., "RTP/AVP", "RTP/SAVP", "UDP")
            formats: List of format identifiers (codec payload types)
            port_count: Number of ports (default 1)
            connection: Optional media-level connection info
            title: Optional media title (i= line)
            bandwidth: Optional bandwidth limits
            attributes: Optional media attributes

        Example:
            >>> sdp.add_media("audio", 49170, "RTP/AVP", ["0", "8", "101"])
            >>> sdp.add_media("video", 51372, "RTP/AVP", ["31", "34"])
        """
        media_desc: Dict[str, Any] = {
            "media": media,
            "port": port,
            "port_count": port_count,
            "protocol": protocol,
            "formats": formats,
            "candidates": [],
            "crypto": [],
            "rtcp_fb": [],
        }

        if connection:
            media_desc["connection"] = connection
        if title:
            media_desc["title"] = title
        if bandwidth:
            media_desc["bandwidth"] = bandwidth
        if attributes:
            media_desc["attributes"] = attributes

        self.media_descriptions.append(media_desc)

    def to_lines(self) -> List[str]:
        """
        Serialize SDP to list of lines (without CRLF).

        Returns:
            List of SDP lines
        """
        lines = []

        # v= (version)
        lines.append(f"v={self.version}")

        # o= (origin)
        lines.append(
            f"o={self.origin_username} {self.origin_session_id} "
            f"{self.origin_session_version} {self.origin_network_type} "
            f"{self.origin_address_type} {self.origin_address}"
        )

        # s= (session name)
        lines.append(f"s={self.session_name}")

        # i= (session information)
        if self.session_info:
            lines.append(f"i={self.session_info}")

        # u= (URI)
        if self.uri:
            lines.append(f"u={self.uri}")

        # e= (email)
        if self.email:
            lines.append(f"e={self.email}")

        # p= (phone)
        if self.phone:
            lines.append(f"p={self.phone}")

        # c= (connection - session level)
        if self.connection:
            lines.append(f"c={self.connection}")

        # b= (bandwidth - session level)
        for bw_type, value in self.bandwidth.items():
            lines.append(f"b={bw_type}:{value}")

        # t= (timing)
        for timing in self.timing:
            lines.append(f"t={timing}")

        # r= (repeat times)
        for repeat in self.repeat_times:
            lines.append(f"r={repeat}")

        # z= (time zones)
        if self.time_zones:
            lines.append(f"z={self.time_zones}")

        # k= (encryption key)
        if self.encryption_key:
            lines.append(f"k={self.encryption_key}")

        # a= (attributes - session level)
        for attr, value in self.attributes.items():
            if value is None:
                lines.append(f"a={attr}")
            else:
                lines.append(f"a={attr}:{value}")

        # Media descriptions
        for media in self.media_descriptions:
            # m= line
            port_str = (
                f"{media['port']}/{media['port_count']}"
                if media["port_count"] > 1
                else str(media["port"])
            )
            formats_str = " ".join(media["formats"])
            lines.append(
                f"m={media['media']} {port_str} {media['protocol']} {formats_str}"
            )

            # i= line (title)
            if media.get("title"):
                lines.append(f"i={media['title']}")

            # c= line (media-level connection)
            if media.get("connection"):
                lines.append(f"c={media['connection']}")

            # b= lines (media-level bandwidth)
            for bw_type, value in media.get("bandwidth", {}).items():
                lines.append(f"b={bw_type}:{value}")

            # a= lines (media attributes)
            for attr, value in media.get("attributes", {}).items():
                if value is None:
                    lines.append(f"a={attr}")
                else:
                    lines.append(f"a={attr}:{value}")

            # Multi-value attribute lists
            for candidate in media.get("candidates", []):
                lines.append(f"a=candidate:{candidate}")
            for crypto in media.get("crypto", []):
                lines.append(f"a=crypto:{crypto}")
            for rtcp_fb in media.get("rtcp_fb", []):
                lines.append(f"a=rtcp-fb:{rtcp_fb}")

        return lines

    def to_string(self) -> str:
        """Serialize SDP to string with CRLF line endings."""
        return "\r\n".join(self.to_lines()) + "\r\n"

    def to_bytes(self) -> bytes:
        """Serialize SDP to bytes."""
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized SDP)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        """Return Content-Type for SDP."""
        return "application/sdp"

    # ========================================================================
    # Offer/Answer Negotiation (RFC 3264)
    # ========================================================================

    @classmethod
    def create_offer(
        cls,
        session_name: str,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        media_specs: List[Dict[str, Any]],
        *,
        session_id: Optional[str] = None,
        session_version: str = "0",
        attributes: Optional[Dict[str, Optional[str]]] = None,
    ) -> "SDPBody":
        """
        Create an SDP offer for media negotiation.

        Args:
            session_name: Session name
            origin_username: Originator username (use "-" for anonymous)
            origin_address: Originator IP address
            connection_address: Connection IP address
            media_specs: List of media specifications, each dict with:
                - media: Media type ("audio", "video", etc.)
                - port: Port number
                - protocol: Protocol (default "RTP/AVP")
                - codecs: List of codec dicts with 'payload', 'name', 'rate', optional 'params'
                - attributes: Optional dict of media attributes
            session_id: Session ID (auto-generated if not provided)
            session_version: Session version (default "0")
            attributes: Session-level attributes

        Returns:
            SDPBody offer instance

        Example:
            >>> offer = SDPBody.create_offer(
            ...     session_name="VoIP Call",
            ...     origin_username="alice",
            ...     origin_address="192.168.1.100",
            ...     connection_address="192.168.1.100",
            ...     media_specs=[
            ...         {
            ...             "media": "audio",
            ...             "port": 49170,
            ...             "codecs": [
            ...                 {"payload": "0", "name": "PCMU", "rate": "8000"},
            ...                 {"payload": "8", "name": "PCMA", "rate": "8000"},
            ...                 {"payload": "101", "name": "telephone-event", "rate": "8000"}
            ...             ]
            ...         }
            ...     ]
            ... )
        """
        # Generate session ID if not provided
        if session_id is None:
            from time import time

            session_id = str(int(time()))

        # Create SDP body
        sdp = cls(
            session_name=session_name,
            origin_username=origin_username,
            origin_session_id=session_id,
            origin_session_version=session_version,
            origin_address=origin_address,
            connection=f"IN IP4 {connection_address}",
            attributes=attributes or {},
        )

        # Add media descriptions
        for spec in media_specs:
            media_type = spec["media"]
            port = spec["port"]
            protocol = spec.get("protocol", "RTP/AVP")
            codecs = spec["codecs"]

            # Extract payload types
            formats = [codec["payload"] for codec in codecs]

            # Build media attributes
            media_attrs = {}

            # Add rtpmap for each codec
            for codec in codecs:
                payload = codec["payload"]
                name = codec["name"]
                rate = codec["rate"]
                params = codec.get("params")

                if params:
                    media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}/{params}"
                else:
                    media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}"

                # Add fmtp if provided
                if "fmtp" in codec:
                    media_attrs[f"fmtp:{payload}"] = codec["fmtp"]

            # Add custom attributes
            if "attributes" in spec:
                media_attrs.update(spec["attributes"])

            # Add media description
            sdp.add_media(
                media=media_type,
                port=port,
                protocol=protocol,
                formats=formats,
                connection=spec.get("connection"),
                attributes=media_attrs,
            )

        return sdp

    @classmethod
    def audio(
        cls,
        ip: str,
        port: int,
        codecs: list[str] | None = None,
        username: str = "-",
        session_name: str = "sipx",
        ice_ufrag: str | None = None,
        ice_pwd: str | None = None,
        crypto_key: str | None = None,
        fingerprint: tuple[str, str] | None = None,
        setup: str | None = None,
        direction: str = "sendrecv",
    ) -> "SDPBody":
        """Create a simple audio SDP offer with sensible defaults.

        Args:
            ip: Local IP address.
            port: RTP port.
            codecs: Codec names (default: ["PCMU", "PCMA", "telephone-event"]).
            username: Origin username.
            session_name: Session name.
            ice_ufrag: ICE username fragment.
            ice_pwd: ICE password.
            crypto_key: Base64 SDES key (uses AES_CM_128_HMAC_SHA1_80).
            fingerprint: Tuple of (hash_func, fingerprint_hex) for DTLS.
            setup: DTLS setup role ("actpass", "active", "passive").
            direction: Media direction (default "sendrecv").
        """
        codec_map = {
            "PCMU": {"payload": "0", "name": "PCMU", "rate": "8000"},
            "PCMA": {"payload": "8", "name": "PCMA", "rate": "8000"},
            "telephone-event": {
                "payload": "101",
                "name": "telephone-event",
                "rate": "8000",
                "fmtp": "0-16",
            },
            "G722": {"payload": "9", "name": "G722", "rate": "8000"},
        }

        if codecs is None:
            codecs = ["PCMU", "PCMA", "telephone-event"]

        codec_specs = [codec_map[c] for c in codecs if c in codec_map]

        sdp = cls.create_offer(
            session_name=session_name,
            origin_username=username,
            origin_address=ip,
            connection_address=ip,
            media_specs=[
                {
                    "media": "audio",
                    "port": port,
                    "codecs": codec_specs,
                }
            ],
        )

        # Apply optional advanced attributes to the first media
        if ice_ufrag is not None and ice_pwd is not None:
            sdp.add_ice_credentials(0, ice_ufrag, ice_pwd)
        if crypto_key is not None:
            sdp.add_crypto(0, 1, "AES_CM_128_HMAC_SHA1_80", crypto_key)
        if fingerprint is not None:
            sdp.add_fingerprint(0, fingerprint[0], fingerprint[1])
        if setup is not None:
            sdp.add_setup(0, setup)
        if direction != "sendrecv":
            sdp.set_direction(0, direction)

        return sdp

    @classmethod
    def create_answer(
        cls,
        offer: "SDPBody",
        origin_username: str,
        origin_address: str,
        connection_address: str,
        accepted_media: Optional[List[Dict[str, Any]]] = None,
        *,
        session_version: Optional[str] = None,
    ) -> "SDPBody":
        """
        Create an SDP answer in response to an offer.

        Args:
            offer: The SDP offer to answer
            origin_username: Answerer username
            origin_address: Answerer IP address
            connection_address: Answerer connection address
            accepted_media: List of accepted media specs (if None, accepts all offered media)
                Each dict should contain:
                - index: Index of offered media (0-based)
                - port: Port to use (0 to reject)
                - codecs: List of accepted codec payloads (subset of offered)
                - attributes: Optional additional attributes
            session_version: Session version (auto-incremented if not provided)

        Returns:
            SDPBody answer instance

        Example:
            >>> answer = SDPBody.create_answer(
            ...     offer=received_offer,
            ...     origin_username="bob",
            ...     origin_address="192.168.1.101",
            ...     connection_address="192.168.1.101",
            ...     accepted_media=[
            ...         {
            ...             "index": 0,  # First media from offer (audio)
            ...             "port": 49170,
            ...             "codecs": ["0", "8"]  # Accept PCMU and PCMA only
            ...         }
            ...     ]
            ... )
        """
        # Increment session version
        if session_version is None:
            session_version = str(int(offer.origin_session_version) + 1)

        # Create answer SDP
        answer = cls(
            session_name=offer.session_name,
            origin_username=origin_username,
            origin_session_id=offer.origin_session_id,  # Keep same session ID
            origin_session_version=session_version,
            origin_address=origin_address,
            connection=f"IN IP4 {connection_address}",
            attributes=offer.attributes.copy(),
        )

        # If no accepted_media specified, accept all offered media
        if accepted_media is None:
            accepted_media = [
                {"index": i, "port": media["port"], "codecs": media["formats"]}
                for i, media in enumerate(offer.media_descriptions)
            ]

        # Add accepted media descriptions
        for acceptance in accepted_media:
            idx = acceptance["index"]
            if idx >= len(offer.media_descriptions):
                continue

            offered_media = offer.media_descriptions[idx]
            port = acceptance.get("port", offered_media["port"])
            accepted_codecs = acceptance.get("codecs", offered_media["formats"])

            # Filter attributes for accepted codecs
            offered_attrs = offered_media.get("attributes", {})
            answer_attrs = {}

            for codec in accepted_codecs:
                # Copy rtpmap
                rtpmap_key = f"rtpmap:{codec}"
                if rtpmap_key in offered_attrs:
                    answer_attrs[rtpmap_key] = offered_attrs[rtpmap_key]

                # Copy fmtp
                fmtp_key = f"fmtp:{codec}"
                if fmtp_key in offered_attrs:
                    answer_attrs[fmtp_key] = offered_attrs[fmtp_key]

            # Add custom attributes from acceptance
            if "attributes" in acceptance:
                answer_attrs.update(acceptance["attributes"])

            # Add media description
            answer.add_media(
                media=offered_media["media"],
                port=port,
                protocol=offered_media["protocol"],
                formats=accepted_codecs,
                connection=acceptance.get("connection"),
                attributes=answer_attrs,
            )

        return answer

    def get_accepted_codecs(self, media_index: int = 0) -> List[Dict[str, str]]:
        """
        Extract accepted codec information from a media description.

        Args:
            media_index: Index of media description (default: 0 for first media)

        Returns:
            List of codec dicts with 'payload', 'name', 'rate', 'params' (if any)

        Example:
            >>> codecs = answer.get_accepted_codecs(0)
            >>> for codec in codecs:
            ...     print(f"{codec['name']} (payload {codec['payload']})")
        """
        if media_index >= len(self.media_descriptions):
            return []

        media = self.media_descriptions[media_index]
        formats = media["formats"]
        attributes = media.get("attributes", {})

        codecs = []
        for payload in formats:
            codec_info = {"payload": payload}

            # Look for rtpmap
            rtpmap_key = f"rtpmap:{payload}"
            if rtpmap_key in attributes:
                rtpmap = attributes[rtpmap_key]
                # Parse "name/rate" or "name/rate/params"
                parts = rtpmap.split("/")
                codec_info["name"] = parts[0]
                if len(parts) > 1:
                    codec_info["rate"] = parts[1]
                if len(parts) > 2:
                    codec_info["params"] = parts[2]

            # Look for fmtp
            fmtp_key = f"fmtp:{payload}"
            if fmtp_key in attributes:
                codec_info["fmtp"] = attributes[fmtp_key]

            codecs.append(codec_info)

        return codecs

    def is_media_rejected(self, media_index: int = 0) -> bool:
        """
        Check if a media stream has been rejected (port = 0).

        Args:
            media_index: Index of media description

        Returns:
            True if media is rejected, False otherwise
        """
        if media_index >= len(self.media_descriptions):
            return True

        return self.media_descriptions[media_index]["port"] == 0

    def get_media_info(self, media_index: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a media stream.

        Args:
            media_index: Index of media description

        Returns:
            Dict with media info (type, port, protocol, codecs, connection, etc.)
            or None if index is out of range

        Example:
            >>> info = sdp.get_media_info(0)
            >>> print(f"Media: {info['type']}, Port: {info['port']}")
            >>> print(f"Codecs: {', '.join([c['name'] for c in info['codecs']])}")
        """
        if media_index >= len(self.media_descriptions):
            return None

        media = self.media_descriptions[media_index]

        return {
            "type": media["media"],
            "port": media["port"],
            "protocol": media["protocol"],
            "formats": media["formats"],
            "codecs": self.get_accepted_codecs(media_index),
            "connection": media.get("connection") or self.connection,
            "attributes": media.get("attributes", {}),
            "rejected": media["port"] == 0,
        }

    def get_codecs_summary(self) -> Dict[str, List[str]]:
        """
        Get a summary of all codecs across all media streams.

        Returns:
            Dict mapping media type to list of codec names

        Example:
            >>> summary = sdp.get_codecs_summary()
            >>> # {'audio': ['PCMU', 'PCMA', 'telephone-event'],
            >>> #  'video': ['H264', 'VP8']}
        """
        summary = {}

        for i, media in enumerate(self.media_descriptions):
            media_type = media["media"]
            if media_type not in summary:
                summary[media_type] = []

            codecs = self.get_accepted_codecs(i)
            for codec in codecs:
                if "name" in codec:
                    codec_name = codec["name"]
                    if codec_name not in summary[media_type]:
                        summary[media_type].append(codec_name)

        return summary

    def has_early_media(self) -> bool:
        """
        Check if SDP indicates early media support.

        Early media is indicated by specific attributes like:
        - a=sendrecv, a=sendonly, a=recvonly (directional attributes)
        - Presence of media with valid ports

        Returns:
            True if early media is supported/indicated
        """
        # Check for directional attributes at session or media level
        directional_attrs = ["sendrecv", "sendonly", "recvonly"]

        # Check session-level attributes
        for attr in directional_attrs:
            if attr in self.attributes:
                return True

        # Check media-level attributes and valid ports
        for media in self.media_descriptions:
            if media["port"] > 0:  # Valid port (not rejected)
                media_attrs = media.get("attributes", {})
                for attr in directional_attrs:
                    if attr in media_attrs:
                        return True

        return False

    def get_connection_address(self) -> Optional[str]:
        """
        Get the connection address from SDP.

        Returns:
            IP address string or None if not found

        Example:
            >>> addr = sdp.get_connection_address()
            >>> # "192.168.1.100"
        """
        if self.connection:
            # Parse "IN IP4 192.168.1.100" or "IN IP6 ::1"
            parts = self.connection.split()
            if len(parts) >= 3:
                return parts[2]
        return None

    def get_media_ports(self) -> Dict[str, int]:
        """
        Get all media ports.

        Returns:
            Dict mapping media type to port number

        Example:
            >>> ports = sdp.get_media_ports()
            >>> # {'audio': 8000, 'video': 9000}
        """
        ports = {}
        for media in self.media_descriptions:
            media_type = media["media"]
            ports[media_type] = media["port"]
        return ports

    def get_rtp_params(self, media_index: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get RTP session parameters from SDP for creating an RTPSession.

        Returns:
            Dict with keys: ip, port, codec_name, payload_type, clock_rate
            or None if media index is out of range.
        """
        info = self.get_media_info(media_index)
        if info is None or info["rejected"]:
            return None

        # Get connection address (media-level or session-level)
        ip = self.get_connection_address()
        port = info["port"]

        # Get first codec
        codecs = info["codecs"]
        if codecs:
            first = codecs[0]
            return {
                "ip": ip,
                "port": port,
                "codec_name": first.get("name", "PCMU"),
                "payload_type": int(first.get("payload", "0")),
                "clock_rate": int(first.get("rate", "8000")),
            }

        return {
            "ip": ip,
            "port": port,
            "codec_name": "PCMU",
            "payload_type": 0,
            "clock_rate": 8000,
        }

    # ========================================================================
    # ICE Attributes (RFC 8445)
    # ========================================================================

    def _ensure_media_lists(self, media_index: int) -> Dict[str, Any]:
        """Get media description and ensure list fields exist.

        Raises:
            IndexError: If media_index is out of range.
        """
        if media_index >= len(self.media_descriptions):
            msg = f"media_index {media_index} out of range (have {len(self.media_descriptions)} media)"
            raise IndexError(msg)
        media = self.media_descriptions[media_index]
        for key in ("candidates", "crypto", "rtcp_fb"):
            if key not in media:
                media[key] = []
        if "attributes" not in media:
            media["attributes"] = {}
        return media

    def add_ice_candidate(
        self,
        media_index: int,
        foundation: str,
        component: int,
        transport: str,
        priority: int,
        address: str,
        port: int,
        typ: str,
        raddr: str = "",
        rport: int = 0,
    ) -> None:
        """Add a=candidate line to media description.

        Args:
            media_index: Index of media description.
            foundation: Candidate foundation string.
            component: Component ID (1=RTP, 2=RTCP).
            transport: Transport protocol (e.g. "UDP").
            priority: Candidate priority.
            address: Candidate IP address.
            port: Candidate port.
            typ: Candidate type (host, srflx, prflx, relay).
            raddr: Related address (for srflx/prflx/relay).
            rport: Related port (for srflx/prflx/relay).
        """
        media = self._ensure_media_lists(media_index)
        line = f"{foundation} {component} {transport} {priority} {address} {port} typ {typ}"
        if raddr and rport:
            line += f" raddr {raddr} rport {rport}"
        media["candidates"].append(line)

    def add_ice_credentials(self, media_index: int, ufrag: str, pwd: str) -> None:
        """Add a=ice-ufrag and a=ice-pwd to media description.

        Args:
            media_index: Index of media description.
            ufrag: ICE username fragment.
            pwd: ICE password.
        """
        media = self._ensure_media_lists(media_index)
        media["attributes"]["ice-ufrag"] = ufrag
        media["attributes"]["ice-pwd"] = pwd

    def get_ice_candidates(self, media_index: int = 0) -> list[dict]:
        """Parse a=candidate lines from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            List of dicts with keys: foundation, component, transport,
            priority, address, port, typ, raddr, rport.
        """
        if media_index >= len(self.media_descriptions):
            return []

        media = self.media_descriptions[media_index]
        results: list[dict] = []

        # Check list-based candidates first
        raw_candidates = list(media.get("candidates", []))

        # Also check attributes dict for parsed candidates
        for key, val in media.get("attributes", {}).items():
            if key == "candidate" and val is not None:
                raw_candidates.append(val)

        pattern = re.compile(
            r"(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+typ\s+(\S+)"
            r"(?:\s+raddr\s+(\S+)\s+rport\s+(\d+))?"
        )

        for raw in raw_candidates:
            m = pattern.match(raw)
            if m:
                candidate = {
                    "foundation": m.group(1),
                    "component": int(m.group(2)),
                    "transport": m.group(3),
                    "priority": int(m.group(4)),
                    "address": m.group(5),
                    "port": int(m.group(6)),
                    "typ": m.group(7),
                }
                if m.group(8):
                    candidate["raddr"] = m.group(8)
                    candidate["rport"] = int(m.group(9))
                results.append(candidate)

        return results

    def get_ice_credentials(self, media_index: int = 0) -> tuple[str, str] | None:
        """Get (ufrag, pwd) from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            Tuple of (ufrag, pwd) or None if not found.
        """
        if media_index >= len(self.media_descriptions):
            return None

        attrs = self.media_descriptions[media_index].get("attributes", {})
        ufrag = attrs.get("ice-ufrag")
        pwd = attrs.get("ice-pwd")
        if ufrag is not None and pwd is not None:
            return (ufrag, pwd)
        return None

    # ========================================================================
    # SRTP Crypto (RFC 4568 - SDES)
    # ========================================================================

    def add_crypto(self, media_index: int, tag: int, suite: str, key: str) -> None:
        """Add a=crypto line for SDES-SRTP.

        Args:
            media_index: Index of media description.
            tag: Crypto tag (1, 2, ...).
            suite: Crypto suite (e.g. "AES_CM_128_HMAC_SHA1_80").
            key: Base64 encoded key material.
        """
        media = self._ensure_media_lists(media_index)
        media["crypto"].append(f"{tag} {suite} inline:{key}")

    def get_crypto(self, media_index: int = 0) -> list[dict]:
        """Parse a=crypto lines from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            List of dicts with keys: tag, suite, key.
        """
        if media_index >= len(self.media_descriptions):
            return []

        media = self.media_descriptions[media_index]
        results: list[dict] = []

        raw_lines = list(media.get("crypto", []))

        # Also check attributes dict for single parsed crypto
        for key, val in media.get("attributes", {}).items():
            if key == "crypto" and val is not None:
                raw_lines.append(val)

        pattern = re.compile(r"(\d+)\s+(\S+)\s+inline:(\S+)")
        for raw in raw_lines:
            m = pattern.match(raw)
            if m:
                results.append(
                    {
                        "tag": int(m.group(1)),
                        "suite": m.group(2),
                        "key": m.group(3),
                    }
                )

        return results

    # ========================================================================
    # RTCP Feedback (RFC 4585)
    # ========================================================================

    def add_rtcp_fb(
        self,
        media_index: int,
        payload_type: str,
        fb_type: str,
        fb_param: str = "",
    ) -> None:
        """Add a=rtcp-fb line.

        Args:
            media_index: Index of media description.
            payload_type: Payload type number or "*".
            fb_type: Feedback type (e.g. "nack", "ccm").
            fb_param: Feedback parameter (e.g. "pli", "fir").
        """
        media = self._ensure_media_lists(media_index)
        line = f"{payload_type} {fb_type}"
        if fb_param:
            line += f" {fb_param}"
        media["rtcp_fb"].append(line)

    def get_rtcp_fb(self, media_index: int = 0) -> list[dict]:
        """Parse a=rtcp-fb lines from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            List of dicts with keys: pt, type, param.
        """
        if media_index >= len(self.media_descriptions):
            return []

        media = self.media_descriptions[media_index]
        results: list[dict] = []

        raw_lines = list(media.get("rtcp_fb", []))

        # Also check attributes for single parsed rtcp-fb
        for key, val in media.get("attributes", {}).items():
            if key == "rtcp-fb" and val is not None:
                raw_lines.append(val)

        for raw in raw_lines:
            parts = raw.split(None, 2)
            if len(parts) >= 2:
                entry: dict[str, str] = {"pt": parts[0], "type": parts[1]}
                if len(parts) > 2:
                    entry["param"] = parts[2]
                else:
                    entry["param"] = ""
                results.append(entry)

        return results

    # ========================================================================
    # DTLS-SRTP (RFC 5763/5764)
    # ========================================================================

    def add_fingerprint(
        self, media_index: int, hash_func: str, fingerprint: str
    ) -> None:
        """Add a=fingerprint for DTLS-SRTP.

        Args:
            media_index: Index of media description.
            hash_func: Hash function (e.g. "sha-256").
            fingerprint: Colon-separated hex fingerprint.
        """
        media = self._ensure_media_lists(media_index)
        media["attributes"]["fingerprint"] = f"{hash_func} {fingerprint}"

    def add_setup(self, media_index: int, role: str) -> None:
        """Add a=setup for DTLS role negotiation.

        Args:
            media_index: Index of media description.
            role: DTLS role ("actpass", "active", "passive").
        """
        media = self._ensure_media_lists(media_index)
        media["attributes"]["setup"] = role

    def get_fingerprint(self, media_index: int = 0) -> tuple[str, str] | None:
        """Get (hash_func, fingerprint) from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            Tuple of (hash_func, fingerprint) or None if not found.
        """
        if media_index >= len(self.media_descriptions):
            return None

        attrs = self.media_descriptions[media_index].get("attributes", {})
        fp = attrs.get("fingerprint")
        if fp is not None:
            parts = fp.split(None, 1)
            if len(parts) == 2:
                return (parts[0], parts[1])
        return None

    def get_setup(self, media_index: int = 0) -> str | None:
        """Get DTLS setup role from media description.

        Args:
            media_index: Index of media description (default 0).

        Returns:
            Setup role string or None if not found.
        """
        if media_index >= len(self.media_descriptions):
            return None

        return self.media_descriptions[media_index].get("attributes", {}).get("setup")

    # ========================================================================
    # Direction Attributes
    # ========================================================================

    _DIRECTION_ATTRS = frozenset({"sendrecv", "sendonly", "recvonly", "inactive"})

    def set_direction(self, media_index: int, direction: str) -> None:
        """Set media stream direction.

        Args:
            media_index: Index of media description.
            direction: One of "sendrecv", "sendonly", "recvonly", "inactive".
        """
        if direction not in self._DIRECTION_ATTRS:
            msg = f"Invalid direction: {direction!r}"
            raise ValueError(msg)
        media = self._ensure_media_lists(media_index)
        # Remove any existing direction attributes
        for d in self._DIRECTION_ATTRS:
            media["attributes"].pop(d, None)
        media["attributes"][direction] = None

    def get_direction(self, media_index: int = 0) -> str:
        """Get media stream direction (default "sendrecv").

        Args:
            media_index: Index of media description (default 0).

        Returns:
            Direction string.
        """
        if media_index >= len(self.media_descriptions):
            return "sendrecv"

        attrs = self.media_descriptions[media_index].get("attributes", {})
        for d in self._DIRECTION_ATTRS:
            if d in attrs:
                return d
        return "sendrecv"


# ============================================================================
# PIDF — Presence Information Data Format (RFC 3863)
# ============================================================================


class PIFDBody(MessageBody):
    """Minimal PIDF presence document (RFC 3863).

    Generates and parses ``application/pidf+xml`` bodies used with the
    SIP PUBLISH and NOTIFY methods for presence information.

    Args:
        entity: Presentity URI (e.g. ``sip:alice@example.com``).
        status: Basic status — ``"open"`` (available) or ``"closed"``
            (unavailable).  Defaults to ``"open"``.
        note: Optional human-readable note appended to the tuple.
        tuple_id: XML tuple element id.  Defaults to ``"t1"``.

    Example::

        pidf = PIFDBody(entity="sip:alice@pbx.com", status="open", note="At desk")
        print(pidf.to_string())
    """

    CONTENT_TYPE = "application/pidf+xml"

    def __init__(
        self,
        entity: str,
        status: str = "open",
        note: str = "",
        tuple_id: str = "t1",
    ) -> None:
        self.entity = entity
        self.status = status
        self.note = note
        self.tuple_id = tuple_id

    def to_string(self) -> str:
        note_xml = f"\n    <note>{self.note}</note>" if self.note else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<presence xmlns="urn:ietf:params:xml:ns:pidf"'
            f' entity="{self.entity}">\n'
            f'  <tuple id="{self.tuple_id}">\n'
            f"    <status><basic>{self.status}</basic></status>"
            f"{note_xml}\n"
            f"  </tuple>\n"
            f"</presence>"
        )

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    @property
    def content_type(self) -> str:
        return self.CONTENT_TYPE

    @classmethod
    def parse(cls, xml: str | bytes) -> PIFDBody:
        """Parse a PIDF-XML document.

        Extracts ``entity``, ``<basic>`` status, and optional ``<note>``.
        Falls back gracefully when elements are absent.

        Args:
            xml: Raw PIDF-XML string or bytes.

        Returns:
            :class:`PIFDBody` instance.
        """
        if isinstance(xml, bytes):
            xml = xml.decode("utf-8", errors="replace")

        entity_m = re.search(r'entity=["\']([^"\']+)["\']', xml)
        entity = entity_m.group(1) if entity_m else ""

        status_m = re.search(r"<basic>\s*(\w+)\s*</basic>", xml, re.IGNORECASE)
        status = status_m.group(1).lower() if status_m else "closed"

        note_m = re.search(r"<note>\s*(.*?)\s*</note>", xml, re.IGNORECASE | re.DOTALL)
        note = note_m.group(1) if note_m else ""

        tuple_m = re.search(r'<tuple[^>]+id=["\']([^"\']+)["\']', xml)
        tuple_id = tuple_m.group(1) if tuple_m else "t1"

        return cls(entity=entity, status=status, note=note, tuple_id=tuple_id)

    def __repr__(self) -> str:
        return f"<PIFDBody(entity={self.entity!r}, status={self.status!r})>"


# ============================================================================
# Body Parser
# ============================================================================


class RawBody(MessageBody):
    """Raw message body for non-SDP content types."""

    def __init__(self, content: bytes, content_type_value: str) -> None:
        self._content = content
        self._content_type = content_type_value

    def to_bytes(self) -> bytes:
        return self._content

    def to_string(self) -> str:
        return self._content.decode("utf-8", errors="replace")

    @property
    def content_type(self) -> str:
        return self._content_type

    def __repr__(self) -> str:
        return f"<RawBody({self._content_type}, {len(self._content)} bytes)>"


class BodyParser:
    """Parser for SIP message bodies based on Content-Type."""

    @staticmethod
    def parse(content: bytes, content_type: str) -> MessageBody:
        """
        Parse message body based on Content-Type.

        Args:
            content: Raw body content as bytes
            content_type: Content-Type header value

        Returns:
            Parsed MessageBody subclass instance
        """
        if not content:
            return RawBody(b"", content_type)

        mime_type = content_type.split(";")[0].strip().lower()

        if mime_type == "application/sdp":
            try:
                return BodyParser.parse_sdp(content)
            except Exception:
                _log.error(
                    "Failed to parse SDP body (%d bytes)", len(content), exc_info=True
                )
                return RawBody(content, content_type)
        elif mime_type == "application/pidf+xml":
            try:
                return PIFDBody.parse(content)
            except Exception:
                _log.error("Failed to parse PIDF body", exc_info=True)
                return RawBody(content, content_type)
        else:
            return RawBody(content, content_type)

    @staticmethod
    def parse_sdp(content: bytes) -> SDPBody:
        """
        Parse SDP body from bytes.

        Args:
            content: Raw SDP content

        Returns:
            Parsed SDPBody instance
        """
        text = content.decode("utf-8")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Required fields
        origin_username = "-"
        origin_session_id = "0"
        origin_session_version = "0"
        origin_network_type = "IN"
        origin_address_type = "IP4"
        origin_address = "127.0.0.1"
        session_name = "-"
        version = 0

        # Optional fields
        connection = None
        session_info = None
        uri = None
        email = None
        phone = None
        bandwidth = {}
        timing = []
        repeat_times = []
        time_zones = None
        encryption_key = None
        attributes = {}
        media_descriptions = []

        current_media = None

        for line in lines:
            if not line or "=" not in line:
                continue

            key, _, value = line.partition("=")

            if key == "v":
                version = int(value)

            elif key == "o":
                # o=<username> <sess-id> <sess-version> <nettype> <addrtype> <addr>
                parts = value.split()
                if len(parts) >= 6:
                    origin_username = parts[0]
                    origin_session_id = parts[1]
                    origin_session_version = parts[2]
                    origin_network_type = parts[3]
                    origin_address_type = parts[4]
                    origin_address = parts[5]

            elif key == "s":
                session_name = value

            elif key == "i":
                if current_media is not None:
                    current_media["title"] = value
                else:
                    session_info = value

            elif key == "u":
                uri = value

            elif key == "e":
                email = value

            elif key == "p":
                phone = value

            elif key == "c":
                if current_media is not None:
                    current_media["connection"] = value
                else:
                    connection = value

            elif key == "b":
                # b=<bwtype>:<bandwidth>
                if ":" in value:
                    bw_type, bw_value = value.split(":", 1)
                    if current_media is not None:
                        if "bandwidth" not in current_media:
                            current_media["bandwidth"] = {}
                        current_media["bandwidth"][bw_type] = int(bw_value)
                    else:
                        bandwidth[bw_type] = int(bw_value)

            elif key == "t":
                timing.append(value)

            elif key == "r":
                repeat_times.append(value)

            elif key == "z":
                time_zones = value

            elif key == "k":
                encryption_key = value

            elif key == "a":
                # a=<attribute> or a=<attribute>:<value>
                # Multi-value attributes go into dedicated lists
                if ":" in value:
                    attr_name, attr_value = value.split(":", 1)
                else:
                    attr_name = value
                    attr_value = None

                if current_media is not None:
                    if "attributes" not in current_media:
                        current_media["attributes"] = {}
                    for list_key in ("candidates", "crypto", "rtcp_fb"):
                        if list_key not in current_media:
                            current_media[list_key] = []

                    if attr_name == "candidate" and attr_value is not None:
                        current_media["candidates"].append(attr_value)
                    elif attr_name == "crypto" and attr_value is not None:
                        current_media["crypto"].append(attr_value)
                    elif attr_name == "rtcp-fb" and attr_value is not None:
                        current_media["rtcp_fb"].append(attr_value)
                    elif attr_value is not None:
                        current_media["attributes"][attr_name] = attr_value
                    else:
                        current_media["attributes"][attr_name] = None
                else:
                    if attr_value is not None:
                        attributes[attr_name] = attr_value
                    else:
                        attributes[attr_name] = None

            elif key == "m":
                # Save previous media if any
                if current_media is not None:
                    media_descriptions.append(current_media)

                # m=<media> <port>[/<num>] <proto> <fmt> ...
                parts = value.split()
                if len(parts) >= 4:
                    media_type = parts[0]
                    port_spec = parts[1]
                    protocol = parts[2]
                    formats = parts[3:]

                    # Parse port/count
                    if "/" in port_spec:
                        port, port_count = port_spec.split("/", 1)
                        port = int(port)
                        port_count = int(port_count)
                    else:
                        port = int(port_spec)
                        port_count = 1

                    current_media = {
                        "media": media_type,
                        "port": port,
                        "port_count": port_count,
                        "protocol": protocol,
                        "formats": formats,
                    }

        # Save last media if any
        if current_media is not None:
            media_descriptions.append(current_media)

        # Create SDP body
        sdp = SDPBody(
            version=version,
            session_name=session_name,
            origin_username=origin_username,
            origin_session_id=origin_session_id,
            origin_session_version=origin_session_version,
            origin_network_type=origin_network_type,
            origin_address_type=origin_address_type,
            origin_address=origin_address,
            connection=connection,
            session_info=session_info,
            uri=uri,
            email=email,
            phone=phone,
            bandwidth=bandwidth,
            timing=timing if timing else ["0 0"],
            repeat_times=repeat_times,
            time_zones=time_zones,
            encryption_key=encryption_key,
            attributes=attributes,
        )

        # Add media descriptions
        for media_desc in media_descriptions:
            sdp.add_media(
                media=media_desc["media"],
                port=media_desc["port"],
                protocol=media_desc["protocol"],
                formats=media_desc["formats"],
                port_count=media_desc.get("port_count", 1),
                connection=media_desc.get("connection"),
                title=media_desc.get("title"),
                bandwidth=media_desc.get("bandwidth"),
                attributes=media_desc.get("attributes"),
            )
            # Carry over multi-value list fields from parsing
            last = sdp.media_descriptions[-1]
            for list_key in ("candidates", "crypto", "rtcp_fb"):
                if list_key in media_desc and media_desc[list_key]:
                    last[list_key] = media_desc[list_key]

        return sdp
