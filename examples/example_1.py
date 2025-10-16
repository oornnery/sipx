# -*- coding: utf-8 -*-
"""
Complete SIP system based on an httpx-style architecture.
Implements client, transport, headers, and utilities for the SIP protocol.

Author: HTTPX-inspired implementation for SIP
Version: 1.0
"""

import socket
import time
import uuid
from typing import Dict, List, Optional, Union


class SIPHeaders:
    """Manage SIP headers, similar to httpx.Headers."""

    def __init__(self, headers: Optional[Union[Dict[str, str], List[tuple]]] = None):
        self._headers = {}
        if headers:
            if isinstance(headers, dict):
                for key, value in headers.items():
                    self._headers[key.lower()] = str(value)
            elif isinstance(headers, list):
                for key, value in headers:
                    self._headers[key.lower()] = str(value)

    def __setitem__(self, key: str, value: str):
        self._headers[key.lower()] = str(value)

    def __getitem__(self, key: str) -> str:
        return self._headers[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._headers

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._headers.get(key.lower(), default)

    def items(self):
        return self._headers.items()

    def keys(self):
        return self._headers.keys()

    def values(self):
        return self._headers.values()

    def update(self, other: Union[Dict[str, str], "SIPHeaders"]):
        if isinstance(other, SIPHeaders):
            self._headers.update(other._headers)
        elif isinstance(other, dict):
            for key, value in other.items():
                self._headers[key.lower()] = str(value)

    def to_string(self) -> str:
        """Convert headers to SIP wire format."""
        lines = []
        for key, value in self._headers.items():
            # Capitalize headers to standard SIP format
            formatted_key = "-".join(word.capitalize() for word in key.split("-"))
            lines.append(f"{formatted_key}: {value}")
        return "\r\n".join(lines)


class SIPRequest:
    """Represents a SIP request, inspired by httpx's Request."""

    def __init__(
        self,
        method: str,
        uri: str,
        headers: Optional[Union[Dict[str, str], SIPHeaders]] = None,
        content: Optional[str] = None,
        version: str = "SIP/2.0",
    ):
        self.method = method.upper()
        self.uri = uri
        self.version = version
        self.headers = (
            SIPHeaders(headers) if not isinstance(headers, SIPHeaders) else headers
        )
        self.content = content or ""
        # Auto-generate required headers if not provided
        self._ensure_required_headers()

    def _ensure_required_headers(self):
        """Ensure required headers are present."""
        if "call-id" not in self.headers:
            self.headers["call-id"] = self._generate_call_id()

        if "cseq" not in self.headers:
            self.headers["cseq"] = f"1 {self.method}"

        if "via" not in self.headers:
            self.headers["via"] = self._generate_via()

        if "from" not in self.headers:
            self.headers["from"] = f"<{self.uri}>;tag={self._generate_tag()}"

        if "to" not in self.headers:
            self.headers["to"] = f"<{self.uri}>"

        if "max-forwards" not in self.headers:
            self.headers["max-forwards"] = "70"

        if self.content:
            self.headers["content-length"] = str(len(self.content))
            if "content-type" not in self.headers:
                self.headers["content-type"] = "application/sdp"
        else:
            self.headers["content-length"] = "0"

    def _generate_call_id(self) -> str:
        """Generate a unique Call-ID."""
        return f"{uuid.uuid4().hex}@localhost"

    def _generate_tag(self) -> str:
        """Generate a unique tag."""
        return uuid.uuid4().hex[:8]

    def _generate_via(self) -> str:
        """Generate a default Via header."""
        branch = f"z9hG4bK{uuid.uuid4().hex[:8]}"
        return f"SIP/2.0/UDP localhost:5060;branch={branch}"

    def to_string(self) -> str:
        """Convert the request to a SIP message string."""
        # Start line (request line)
        start_line = f"{self.method} {self.uri} {self.version}"

        # Headers
        headers_str = self.headers.to_string()

        # Blank line + body
        if self.content:
            return f"{start_line}\r\n{headers_str}\r\n\r\n{self.content}"
        else:
            return f"{start_line}\r\n{headers_str}\r\n\r\n"


class SIPResponse:
    """Represents a SIP response."""

    def __init__(
        self,
        status_code: int,
        reason_phrase: str,
        headers: Optional[Union[Dict[str, str], SIPHeaders]] = None,
        content: Optional[str] = None,
        version: str = "SIP/2.0",
    ):
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.version = version
        self.headers = (
            SIPHeaders(headers) if not isinstance(headers, SIPHeaders) else headers
        )
        self.content = content or ""

        if self.content:
            self.headers["content-length"] = str(len(self.content))
        else:
            self.headers["content-length"] = "0"

    def to_string(self) -> str:
        """Convert the response to a SIP message string."""
        # Status line
        status_line = f"{self.version} {self.status_code} {self.reason_phrase}"

        # Headers
        headers_str = self.headers.to_string()

        # Blank line + body
        if self.content:
            return f"{status_line}\r\n{headers_str}\r\n\r\n{self.content}"
        else:
            return f"{status_line}\r\n{headers_str}\r\n\r\n"


class BaseSIPTransport:
    """Base class for SIP transports, inspired by httpx.BaseTransport."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5060):
        self.host = host
        self.port = port
        self.socket = None

    def send_request(self, request: SIPRequest) -> SIPResponse:
        """Abstract method to send a request."""
        raise NotImplementedError

    def close(self):
        """Close the transport."""
        if self.socket:
            self.socket.close()


class UDPSIPTransport(BaseSIPTransport):
    """SIP transport over UDP."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5060, timeout: float = 5.0):
        super().__init__(host, port)
        self.timeout = timeout
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)

    def send_request(
        self, request: SIPRequest, target_host: str, target_port: int = 5060
    ) -> SIPResponse:
        """Send SIP request over UDP."""
        try:
            # Serialize the request
            message = request.to_string()

            # Send via UDP
            self.socket.sendto(message.encode("utf-8"), (target_host, target_port))

            # Wait for a response
            data, addr = self.socket.recvfrom(4096)
            response_text = data.decode("utf-8")

            # Parse the response
            return self._parse_response(response_text)

        except socket.timeout:
            return SIPResponse(408, "Request Timeout")
        except Exception as e:
            return SIPResponse(500, f"Transport Error: {str(e)}")

    def _parse_response(self, response_text: str) -> SIPResponse:
        """Parse a SIP response message."""
        lines = response_text.split("\r\n")

        # Parse status line
        status_line = lines[0]
        parts = status_line.split(" ", 2)
        version = parts[0]
        status_code = int(parts[1])
        reason_phrase = parts[2] if len(parts) > 2 else ""

        # Parse headers
        headers = SIPHeaders()
        content_start = 0

        for i, line in enumerate(lines[1:], 1):
            if line == "":  # Empty line marks the end of headers
                content_start = i + 1
                break

            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        # Body (if any)
        content = (
            "\r\n".join(lines[content_start:]) if content_start < len(lines) else ""
        )

        return SIPResponse(status_code, reason_phrase, headers, content, version)


class TCPSIPTransport(BaseSIPTransport):
    """SIP transport over TCP."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5060, timeout: float = 5.0):
        super().__init__(host, port)
        self.timeout = timeout

    def send_request(
        self, request: SIPRequest, target_host: str, target_port: int = 5060
    ) -> SIPResponse:
        """Send SIP request over TCP."""
        try:
            # Create TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((target_host, target_port))

            # Serialize and send request
            message = request.to_string()
            sock.send(message.encode("utf-8"))

            # Receive response
            data = sock.recv(4096)
            response_text = data.decode("utf-8")

            sock.close()

            # Parse the response (reuse UDP method)
            return UDPSIPTransport._parse_response(self, response_text)

        except socket.timeout:
            return SIPResponse(408, "Request Timeout")
        except Exception as e:
            return SIPResponse(500, f"Transport Error: {str(e)}")


class SIPClient:
    """Main SIP client, inspired by httpx.Client."""

    def __init__(
        self,
        transport: Optional[BaseSIPTransport] = None,
        default_headers: Optional[Dict[str, str]] = None,
        user_agent: str = "PythonSIP/1.0",
        local_host: str = "localhost",
        local_port: int = 5060,
    ):
        self.transport = transport or UDPSIPTransport()
        self.default_headers = SIPHeaders(default_headers or {})
        self.local_host = local_host
        self.local_port = local_port
        # Default headers
        self.default_headers["user-agent"] = user_agent
        # Session state
        self.call_sessions = {}  # Store active sessions by Call-ID

    def _merge_headers(
        self, headers: Optional[Union[Dict[str, str], SIPHeaders]]
    ) -> SIPHeaders:
        """Merge default headers with request-specific headers."""
        merged = SIPHeaders()
        merged.update(self.default_headers)
        if headers:
            merged.update(headers)
        return merged

    def request(
        self,
        method: str,
        uri: str,
        headers: Optional[Union[Dict[str, str], SIPHeaders]] = None,
        content: Optional[str] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Send a generic SIP request."""

        # Merge headers
        merged_headers = self._merge_headers(headers)

        # Auto-extract host from URI if not specified
        if not target_host:
            target_host = self._extract_host_from_uri(uri)

        # Build request
        request = SIPRequest(method, uri, merged_headers, content)

        # Send via transport
        response = self.transport.send_request(request, target_host, target_port)

        return response

    def _extract_host_from_uri(self, uri: str) -> str:
        """Extract the hostname from a SIP URI."""
        if uri.startswith("sip:"):
            # Remove sip: prefix
            uri = uri[4:]

        # Parse user@host:port
        if "@" in uri:
            uri = uri.split("@")[1]  # Keep only the host part

        if ":" in uri:
            uri = uri.split(":")[0]  # Remove port if specified

        return uri if uri else "localhost"

    # SIP specific methods

    def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        sdp_content: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Send a SIP INVITE to initiate a call."""

        if not from_uri:
            from_uri = f"sip:user@{self.local_host}:{self.local_port}"

        invite_headers = SIPHeaders(headers or {})
        invite_headers["from"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        invite_headers["to"] = f"<{to_uri}>"
        invite_headers["contact"] = f"<{from_uri}>"

        if sdp_content:
            invite_headers["content-type"] = "application/sdp"

        return self.request(
            "INVITE", to_uri, invite_headers, sdp_content, target_host, target_port
        )

    def register(
        self,
        register_uri: str,
        contact_uri: Optional[str] = None,
        expires: int = 3600,
        headers: Optional[Dict[str, str]] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Register the client with a SIP server."""

        if not contact_uri:
            contact_uri = f"sip:user@{self.local_host}:{self.local_port}"

        register_headers = SIPHeaders(headers or {})
        register_headers["contact"] = f"<{contact_uri}>"
        register_headers["expires"] = str(expires)
        register_headers["from"] = f"<{register_uri}>;tag={uuid.uuid4().hex[:8]}"
        register_headers["to"] = f"<{register_uri}>"

        return self.request(
            "REGISTER", register_uri, register_headers, None, target_host, target_port
        )

    def bye(
        self,
        to_uri: str,
        call_id: str,
        from_tag: str,
        to_tag: str,
        cseq: int = 1,
        headers: Optional[Dict[str, str]] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Terminate a SIP call."""

        bye_headers = SIPHeaders(headers or {})
        bye_headers["call-id"] = call_id
        bye_headers["from"] = f"<sip:user@{self.local_host}>;tag={from_tag}"
        bye_headers["to"] = f"<{to_uri}>;tag={to_tag}"
        bye_headers["cseq"] = f"{cseq} BYE"

        return self.request("BYE", to_uri, bye_headers, None, target_host, target_port)

    def ack(
        self,
        to_uri: str,
        call_id: str,
        from_tag: str,
        to_tag: str,
        cseq: int = 1,
        headers: Optional[Dict[str, str]] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Send ACK to confirm an INVITE."""

        ack_headers = SIPHeaders(headers or {})
        ack_headers["call-id"] = call_id
        ack_headers["from"] = f"<sip:user@{self.local_host}>;tag={from_tag}"
        ack_headers["to"] = f"<{to_uri}>;tag={to_tag}"
        ack_headers["cseq"] = f"{cseq} ACK"

        return self.request("ACK", to_uri, ack_headers, None, target_host, target_port)

    def options(
        self,
        uri: str,
        headers: Optional[Dict[str, str]] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> SIPResponse:
        """Query capabilities of a SIP endpoint."""
        return self.request("OPTIONS", uri, headers, None, target_host, target_port)

    def close(self):
        """Close the SIP client."""
        if self.transport:
            self.transport.close()


class SIPSession:
    """Manage an individual SIP session."""

    def __init__(self, call_id: str, from_tag: str, to_tag: Optional[str] = None):
        self.call_id = call_id
        self.from_tag = from_tag
        self.to_tag = to_tag
        self.cseq = 1
        self.state = "initial"  # initial, calling, ringing, connected, terminated
        self.created_at = time.time()

    def next_cseq(self) -> int:
        """Return the next CSeq number."""
        self.cseq += 1
        return self.cseq


class SIPUtils:
    """SIP utilities."""

    @staticmethod
    def generate_sdp(
        audio_port: int = 8000,
        audio_ip: str = "127.0.0.1",
        session_name: str = "Python SIP Session",
    ) -> str:
        """Generate basic SDP content for audio."""
        session_id = int(time.time())

        sdp = f"""v=0
o=pythonsip {session_id} {session_id} IN IP4 {audio_ip}
s={session_name}
c=IN IP4 {audio_ip}
t=0 0
m=audio {audio_port} RTP/AVP 0 8 101
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-16
a=sendrecv"""

        return sdp

    @staticmethod
    def parse_sip_uri(uri: str) -> dict:
        """Parse a SIP URI into components."""
        result = {"scheme": "", "user": "", "host": "", "port": 5060, "params": {}}

        if uri.startswith("sip:"):
            result["scheme"] = "sip"
            uri = uri[4:]
        elif uri.startswith("sips:"):
            result["scheme"] = "sips"
            uri = uri[5:]

        # Parse user@host:port;params
        if "@" in uri:
            user_part, host_part = uri.split("@", 1)
            result["user"] = user_part
        else:
            host_part = uri

        # Parse host:port;params
        if ";" in host_part:
            host_port, params_str = host_part.split(";", 1)
            # Parse params
            for param in params_str.split(";"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    result["params"][key] = value
                else:
                    result["params"][param] = True
        else:
            host_port = host_part

        # Parse host:port
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            result["host"] = host
            try:
                result["port"] = int(port)
            except ValueError:
                result["port"] = 5060
        else:
            result["host"] = host_port

        return result


class SimpleSIPServer:
    """Simple SIP server for testing."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5060):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False

    def start(self):
        """Start the server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.running = True
        print(f"SIP server started at {self.host}:{self.port}")

        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                request_text = data.decode("utf-8")

                # Basic request parsing
                lines = request_text.split("\r\n")
                request_line = lines[0]

                print(f"Request received from {addr}: {request_line}")

                # Simple automatic response
                response = self._generate_response(request_text, addr)
                if response:
                    self.socket.sendto(response.encode("utf-8"), addr)

            except Exception as e:
                print(f"Server error: {e}")
                break

    def _generate_response(self, request_text: str, addr: tuple) -> str:
        """Generate an automatic response for incoming requests."""
        lines = request_text.split("\r\n")
        request_line = lines[0]

        # Parse request headers
        headers = {}
        for line in lines[1:]:
            if line == "":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        # Method-based response
        if request_line.startswith("OPTIONS"):
            return f"""SIP/2.0 200 OK
Via: {headers.get("via", "")}
From: {headers.get("from", "")}
To: {headers.get("to", "")}
Call-ID: {headers.get("call-id", "")}
CSeq: {headers.get("cseq", "")}
Allow: INVITE, ACK, BYE, CANCEL, OPTIONS, REGISTER
Content-Length: 0

"""
        elif request_line.startswith("REGISTER"):
            return f"""SIP/2.0 200 OK
Via: {headers.get("via", "")}
From: {headers.get("from", "")}
To: {headers.get("to", "")};tag={uuid.uuid4().hex[:8]}
Call-ID: {headers.get("call-id", "")}
CSeq: {headers.get("cseq", "")}
Contact: {headers.get("contact", "")}
Expires: {headers.get("expires", "3600")}
Content-Length: 0

"""
        elif request_line.startswith("INVITE"):
            return f"""SIP/2.0 200 OK
Via: {headers.get("via", "")}
From: {headers.get("from", "")}
To: {headers.get("to", "")};tag={uuid.uuid4().hex[:8]}
Call-ID: {headers.get("call-id", "")}
CSeq: {headers.get("cseq", "")}
Contact: <sip:test@{addr[0]}:{addr[1]}>
Content-Type: application/sdp
Content-Length: 0

"""

        return ""

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.socket:
            self.socket.close()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================


def exemplo_uso_basico():
    """Demonstrate basic usage of the SIP client."""
    print("=== Basic Usage Example ===")

    # Create SIP client
    client = SIPClient(user_agent="MeuApp/1.0", local_host="192.168.1.100")

    # 1. Register with the server
    print("1. Registering with the server...")
    response = client.register(
        register_uri="sip:1111@demo.mizu-voip.com:37075",
        target_host="demo.mizu-voip.com",
        target_port=37075,
    )
    print(f"Response: {response.status_code} {response.reason_phrase}")

    # 2. Query capabilities
    print("\n2. Querying capabilities...")
    response = client.options(
        uri="sip:demo.mizu-voip.com:37075",
        target_host="demo.mizu-voip.com",
        target_port=37075,
    )
    print(f"Response: {response.status_code} {response.reason_phrase}")

    # 3. Make a call
    print("\n3. Starting call...")
    sdp_content = SIPUtils.generate_sdp(8000, "192.168.1.100")
    response = client.invite(
        to_uri="sip:1111@demo.mizu-voip.com:37075",
        from_uri="sip:1111@demo.mizu-voip.com:37075",
        sdp_content=sdp_content,
        target_host="demo.mizu-voip.com",
        target_port=37075,
    )
    print(f"Response: {response.status_code} {response.reason_phrase}")

    # Close client
    client.close()


def exemplo_mensagem_customizada():
    """Demonstrate crafting custom SIP messages."""
    print("\n=== Custom Message Example ===")

    # Create custom headers
    headers = SIPHeaders(
        {
            "from": "<sip:1111@demo.mizu-voip.com:37075>;tag=abc123",
            "to": "<sip:1111@demo.mizu-voip.com:37075>",
            "contact": "<sip:1111@192.168.1.100:37075>",
            "allow": "INVITE,ACK,BYE,CANCEL,OPTIONS",
            "supported": "replaces,timer",
        }
    )

    # Create SDP
    sdp = SIPUtils.generate_sdp(8000, "192.168.1.100", "My Session")

    # Create INVITE request
    invite = SIPRequest(
        method="INVITE",
        uri="sip:1111@demo.mizu-voip.com:37075",
        headers=headers,
        content=sdp,
    )

    print("Created INVITE message:")
    print(invite.to_string())


if __name__ == "__main__":
    # Run examples
    exemplo_uso_basico()
    exemplo_mensagem_customizada()

    print("\n=== Complete SIP System Implemented ===")
    print("Features:")
    print("- Based on httpx-style architecture")
    print("- UDP and TCP support")
    print("- Headers and automatic parsing")
    print("- SIP methods: INVITE, REGISTER, BYE, ACK, OPTIONS")
    print("- Automatic SDP generation")
    print("- SIP URI parsing")
    print("- Test server included")
