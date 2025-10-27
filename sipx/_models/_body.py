"""
SIP Message Body Models and Parsers (Simplified).

Supports SDP (Session Description Protocol) as the primary body type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
        media_desc = {
            "media": media,
            "port": port,
            "port_count": port_count,
            "protocol": protocol,
            "formats": formats,
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


# ============================================================================
# Body Parser
# ============================================================================


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

        Example:
            >>> body = BodyParser.parse(b"v=0\\r\\no=...", "application/sdp")
            >>> isinstance(body, SDPBody)
            True
        """
        if not content:
            # Return empty SDP for empty content
            return SDPBody(
                session_name="-",
                origin_username="-",
                origin_session_id="0",
                origin_session_version="0",
            )

        # Extract MIME type (ignore parameters)
        mime_type = content_type.split(";")[0].strip().lower()

        # Parse based on MIME type
        if mime_type == "application/sdp":
            return BodyParser.parse_sdp(content)
        else:
            # For any other type, return as raw SDPBody with the content as session_name
            # This is a simplified approach - in production you might want a RawBody class
            return SDPBody(
                session_name=content.decode("utf-8", errors="ignore")[:100],
                origin_username="-",
                origin_session_id="0",
                origin_session_version="0",
            )

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
                if current_media is not None:
                    if "attributes" not in current_media:
                        current_media["attributes"] = {}
                    if ":" in value:
                        attr_name, attr_value = value.split(":", 1)
                        current_media["attributes"][attr_name] = attr_value
                    else:
                        current_media["attributes"][value] = None
                else:
                    if ":" in value:
                        attr_name, attr_value = value.split(":", 1)
                        attributes[attr_name] = attr_value
                    else:
                        attributes[value] = None

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

        return sdp
