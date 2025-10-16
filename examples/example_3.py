# sipx_mvp_ext.py
import asyncio
import re
import random
import time
import hashlib
import socket
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Callable, List

CRLF = b"\r\n"
CRLFCRLF = b"\r\n\r\n"

SIP_URI_RE = re.compile(r"^sip:(?:(?P<user>[^@]+)@)?(?P<hostport>[^;>]+)")

@dataclass
class SipMessage:
    is_request: bool
    method: Optional[str] = None
    request_uri: Optional[str] = None
    status_code: Optional[int] = None
    reason: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def to_bytes(self) -> bytes:
        if self.is_request:
            start = f"{self.method} {self.request_uri} SIP/2.0\r\n"
        else:
            start = f"SIP/2.0 {self.status_code} {self.reason}\r\n"
        # Preserve header order roughly; ensure Content-Length present
        hdrs = "".join([f"{k}: {v}\r\n" for k, v in self.headers.items()])
        if self.body and "Content-Length" not in {k.title() for k in self.headers}:
            hdrs += f"Content-Length: {len(self.body)}\r\n"
        if not self.body and "Content-Length" not in {k.title() for k in self.headers}:
            hdrs += "Content-Length: 0\r\n"
        return (start + hdrs + "\r\n").encode("utf-8") + self.body


def parse_sip_uri(uri: str) -> Tuple[Optional[str], str, Optional[int]]:
    cleaned = uri.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    match = SIP_URI_RE.match(cleaned)
    if not match:
        raise ValueError(f"Invalid SIP URI: {uri}")
    hostport = match.group("hostport")
    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = None
    else:
        host, port = hostport, None
    user = match.group("user")
    return user, host, port


def determine_outbound_ip(preferred: str, remote_host: str, remote_port: int) -> str:
    if preferred and preferred not in {"0.0.0.0", "::", ""}:
        return preferred
    target_host = remote_host
    try:
        addrinfo = socket.getaddrinfo(remote_host, remote_port, socket.AF_INET, socket.SOCK_DGRAM)
        if addrinfo:
            target_host = addrinfo[0][4][0]
    except socket.gaierror:
        target_host = remote_host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target_host, remote_port))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def format_sip_message(msg: "SipMessage") -> str:
    if msg.is_request:
        start = f"{msg.method} {msg.request_uri} SIP/2.0"
    else:
        reason = msg.reason or ""
        start = f"SIP/2.0 {msg.status_code} {reason}".rstrip()
    headers = "\n".join(f"{k}: {v}" for k, v in msg.headers.items())
    body = ""
    if msg.body:
        try:
            body_text = msg.body.decode("utf-8")
        except UnicodeDecodeError:
            body_text = msg.body.decode("utf-8", errors="replace")
        body = f"\n\n{body_text}"
    return f"{start}\n{headers}{body}" if headers else f"{start}{body}"


def log_sip(direction: str, msg: "SipMessage", addr: Tuple[str, int], proto: str) -> None:
    formatted = format_sip_message(msg)
    print(f"[{direction}] {proto} {addr[0]}:{addr[1]}\n{formatted}\n")

def parse_sip_message(data: bytes) -> SipMessage:
    try:
        header_part, body = data.split(CRLFCRLF, 1)
    except ValueError:
        header_part, body = data, b""
    lines = header_part.decode("utf-8", errors="replace").split("\r\n")
    start_line = lines[0]
    headers: Dict[str, str] = {}
    unfolded: List[str] = []
    for line in lines[1:]:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += " " + line.strip()
        else:
            unfolded.append(line)
    for line in unfolded:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    if start_line.startswith("SIP/2.0"):
        parts = start_line.split(" ", 2)
        code = int(parts[1])
        reason = parts[2] if len(parts) > 2 else ""
        return SipMessage(False, status_code=code, reason=reason, headers=headers, body=body)
    else:
        parts = start_line.split(" ", 2)
        method = parts[0]
        uri = parts[1] if len(parts) > 1 else ""
        return SipMessage(True, method=method, request_uri=uri, headers=headers, body=body)

def gen_branch() -> str:
    return f"z9hG4bK{random.randint(10**7, 10**8-1)}"

def gen_tag() -> str:
    return f"{random.randint(10**7, 10**8-1)}"

def next_cseq(h: str) -> str:
    num, meth = h.split()
    return f"{int(num)+1} {meth}"

def ensure_req_basics(
    msg: SipMessage,
    local_ip: str,
    sip_port: int,
    target_host: str,
    target_port: Optional[int],
):
    via_hostport = f"{local_ip}:{sip_port}" if sip_port else local_ip
    host_header = f"{target_host}:{target_port}" if target_port else target_host
    msg.headers["Host"] = host_header
    if "Via" not in msg.headers:
        msg.headers["Via"] = f"SIP/2.0/UDP {via_hostport};branch={gen_branch()}"
    else:
        msg.headers["Via"] = re.sub(
            r"SIP/2.0/UDP\s+[^;]+",
            f"SIP/2.0/UDP {via_hostport}",
            msg.headers["Via"],
            count=1,
        )
        if "branch=" not in msg.headers["Via"]:
            msg.headers["Via"] += f";branch={gen_branch()}"
    msg.headers.setdefault("Max-Forwards", "70")
    if "CSeq" not in msg.headers:
        msg.headers["CSeq"] = f"1 {msg.method}"
    msg.headers.setdefault(
        "Call-ID", f"{random.randint(1, 2**31-1)}@{local_ip}"
    )
    usr = msg.headers.get("Authorization-User") or "alice"
    from_header = msg.headers.get("From")
    if not from_header:
        msg.headers["From"] = f"<sip:{usr}@{target_host}>;tag={gen_tag()}"
    else:
        if "tag=" not in from_header:
            msg.headers["From"] = from_header.rstrip(">") + f">;tag={gen_tag()}"
        if "@local" in msg.headers["From"] or "@0.0.0.0" in msg.headers["From"]:
            msg.headers["From"] = re.sub(
                r"@[^;>]+",
                f"@{target_host}",
                msg.headers["From"],
                count=1,
            )
    msg.headers.setdefault("To", f"<{msg.request_uri}>")
    contact_user = usr
    contact_uri = f"<sip:{contact_user}@{local_ip}:{sip_port}>"
    if "Contact" not in msg.headers:
        msg.headers["Contact"] = contact_uri
    elif "0.0.0.0" in msg.headers["Contact"] or "@local" in msg.headers["Contact"]:
        msg.headers["Contact"] = contact_uri
    if msg.body and "Content-Type" not in msg.headers:
        msg.headers["Content-Type"] = "application/sdp"
    msg.headers["Content-Length"] = str(len(msg.body or b""))

def make_request(method: str, uri: str, headers: Dict[str, str], body: bytes = b"") -> SipMessage:
    msg = SipMessage(True, method=method, request_uri=uri, headers=dict(headers), body=body)
    return msg

def make_response(req: SipMessage, code: int, reason: str, headers: Optional[Dict[str,str]] = None, body: bytes = b"") -> SipMessage:
    h = dict(headers or {})
    h["Via"] = req.headers.get("Via","")
    h["From"] = req.headers.get("From","")
    to_val = req.headers.get("To","")
    if "tag=" not in to_val:
        to_val = to_val.rstrip(">") + f">;tag={gen_tag()}"
    h["To"] = to_val
    h["Call-ID"] = req.headers.get("Call-ID","")
    h["CSeq"] = req.headers.get("CSeq","")
    if body:
        h["Content-Type"] = "application/sdp"
    h["Content-Length"] = str(len(body))
    return SipMessage(False, status_code=code, reason=reason, headers=h, body=body)

def build_sdp(local_ip: str, rtp_port: int, payload=0, clock=8000) -> bytes:
    s = []
    s.append("v=0")
    s.append(f"o=- 0 0 IN IP4 {local_ip}")
    s.append("s=sipx-mvp")
    s.append(f"c=IN IP4 {local_ip}")
    s.append("t=0 0")
    s.append(f"m=audio {rtp_port} RTP/AVP {payload}")
    s.append(f"a=rtpmap:{payload} PCMU/{clock}")
    return ("\r\n".join(s) + "\r\n").encode()

class SipTransport:
    def __init__(self):
        self.on_message: Optional[Callable[[bytes, Tuple[str, int], str], None]] = None
        self._udp_transport: Optional[asyncio.transports.DatagramTransport] = None

    async def sendto(self, data: bytes, addr: Tuple[str, int], proto: str = "UDP", writer=None):
        if proto == "UDP":
            if self._udp_transport:
                self._udp_transport.sendto(data, addr)
                return
            loop = asyncio.get_running_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                remote_addr=addr
            )
            transport.sendto(data)
            transport.close()
        elif proto == "TCP" and writer:
            writer.write(data)
            await writer.drain()

class SipUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_message):
        self.on_message = on_message
    def datagram_received(self, data: bytes, addr):
        if self.on_message:
            self.on_message(data, addr, "UDP")

async def serve_udp(transport: SipTransport, host="0.0.0.0", port=5060):
    loop = asyncio.get_running_loop()
    udp_transport, _ = await loop.create_datagram_endpoint(
        lambda: SipUDPProtocol(transport.on_message), local_addr=(host, port)
    )
    transport._udp_transport = udp_transport
    return udp_transport

async def serve_tcp(transport: SipTransport, host="0.0.0.0", port=5060):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        buf = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf += chunk
            while True:
                header_end = buf.find(CRLFCRLF)
                if header_end < 0:
                    break
                headers_part = buf[:header_end].decode("utf-8", errors="replace")
                m = re.search(r"(?im)^Content-Length:\s*(\d+)\s*$", headers_part)
                length = int(m.group(1)) if m else 0
                total_len = header_end + 4 + length
                if len(buf) < total_len:
                    break
                msg = buf[:total_len]
                buf = buf[total_len:]
                if transport.on_message:
                    transport.on_message(msg, peer, "TCP")
    return await asyncio.start_server(handle, host, port)

def parse_auth_challenge(hval: str) -> Dict[str,str]:
    params: Dict[str,str] = {}
    # strip "Digest " prefix if present
    v = hval.strip()
    if v.lower().startswith("digest"):
        v = v[len("digest"):].strip()
    for part in re.split(r',\s*', v):
        if "=" in part:
            k, vv = part.split("=", 1)
            params[k.strip()] = vv.strip().strip('"')
    return params

def md5_hex(x: str) -> str:
    return hashlib.md5(x.encode()).hexdigest()

def build_digest_authorization(method: str, uri: str, username: str, password: str, chal: Dict[str,str], is_proxy=False, cseq_nc=1) -> Tuple[str,str]:
    realm = chal.get("realm","")
    nonce = chal.get("nonce","")
    qop = chal.get("qop","auth")
    algorithm = chal.get("algorithm","MD5")
    opaque = chal.get("opaque")
    cnonce = f"{random.randint(10**7, 10**8-1)}"
    nc = f"{cseq_nc:08x}"
    # Only MD5 for MVP
    ha1 = md5_hex(f"{username}:{realm}:{password}")
    ha2 = md5_hex(f"{method}:{uri}")
    if qop and qop.lower() == "auth":
        response = md5_hex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
    else:
        response = md5_hex(f"{ha1}:{nonce}:{ha2}")
    auth_params = [
        f'username="{username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
        f'algorithm={algorithm}',
    ]
    if opaque:
        auth_params.append(f'opaque="{opaque}"')
    if qop:
        auth_params.append(f"qop={qop}")
        auth_params.append(f'nc={nc}')
        auth_params.append(f'cnonce="{cnonce}"')
    header_name = "Proxy-Authorization" if is_proxy else "Authorization"
    return header_name, "Digest " + ", ".join(auth_params)

class ClientTransaction:
    def __init__(self, transport, key, request, addr, proto, writer):
        self.transport = transport
        self.key = key
        self.request: SipMessage = request
        self.addr = addr
        self.proto = proto
        self.writer = writer
        self.state = "init"
        self.response: Optional[SipMessage] = None
        self.provisional: Optional[SipMessage] = None
        self.auth_tried = False
        self.nc = 0  # nonce-count for digest
        self._response_event = asyncio.Event()

    def matches_response(self, resp: SipMessage) -> bool:
        if resp.is_request:
            return False
        via_req = self.request.headers.get("Via", "")
        branch_req = re.search(r"branch=([^;]+)", via_req or "")
        via_resp = resp.headers.get("Via", "")
        branch_resp = re.search(r"branch=([^;]+)", via_resp or "")
        cid_eq = self.request.headers.get("Call-ID") == resp.headers.get("Call-ID")
        cseq_req = self.request.headers.get("CSeq", "")
        method_req = cseq_req.split()[1] if len(cseq_req.split()) > 1 else ""
        cseq_resp = resp.headers.get("CSeq", "")
        method_resp = cseq_resp.split()[1] if len(cseq_resp.split()) > 1 else ""
        return cid_eq and method_req == method_resp and (branch_req and branch_resp and branch_req.group(1) == branch_resp.group(1))

    def is_terminated(self) -> bool:
        return self.state in ("terminated",)

    async def wait_for_response(self, timeout: Optional[float] = None) -> Optional[SipMessage]:
        if self.response is not None:
            return self.response
        if timeout is None:
            await self._response_event.wait()
        else:
            await asyncio.wait_for(self._response_event.wait(), timeout)
        return self.response

    def build_ack(self) -> SipMessage:
        # Minimal ACK mirrors route/To/From/Call-ID and increments CSeq method to ACK
        ack = SipMessage(True, method="ACK", request_uri=self.request.request_uri, headers={})
        # Copy dialog-identifying headers
        for k in ("From","To","Call-ID","Via","Contact"):
            if k in self.request.headers:
                ack.headers[k] = self.request.headers[k]
        # ACK CSeq must use same number as INVITE but method "ACK"
        if "CSeq" in self.request.headers:
            num = self.request.headers["CSeq"].split()[0]
            ack.headers["CSeq"] = f"{num} ACK"
        else:
            ack.headers["CSeq"] = "1 ACK"
        ack.headers["Max-Forwards"] = "70"
        ack.headers["Content-Length"] = "0"
        return ack

class NonInviteClientTransaction(ClientTransaction):
    async def start(self):
        self.state = "trying"
        await self._retransmit_until_response()

    async def _retransmit_until_response(self):
        t1 = 0.5
        interval = t1
        deadline = time.monotonic() + 32.0
        while time.monotonic() < deadline and self.state == "trying":
            await self.transport.sendto(self.request.to_bytes(), self.addr, self.proto, self.writer)
            await asyncio.sleep(interval)
            interval = min(interval * 2, 4.0)
        if self.response is None and self.state == "trying":
            self.state = "terminated"
            if not self._response_event.is_set():
                self._response_event.set()

    async def on_response(self, resp: SipMessage):
        self.response = resp
        self.state = "completed"
        if not self._response_event.is_set():
            self._response_event.set()

class InviteClientTransaction(ClientTransaction):
    async def start(self):
        self.state = "calling"
        await self._retransmit_until_provisional_or_final()

    async def _retransmit_until_provisional_or_final(self):
        t1 = 0.5
        interval = t1
        deadline = time.monotonic() + 64 * t1
        while time.monotonic() < deadline and self.state == "calling":
            await self.transport.sendto(self.request.to_bytes(), self.addr, self.proto, self.writer)
            await asyncio.sleep(interval)
            interval = min(interval * 2, 4.0)

    async def on_response(self, resp: SipMessage):
        self.response = resp
        code = resp.status_code or 0
        # Handle reliable provisional (100rel): send PRACK with RAck = RSeq CSeq Method
        if 100 < code < 200:
            self.provisional = resp
            rseq = resp.headers.get("RSeq")
            require = (resp.headers.get("Require","") + "," + resp.headers.get("Supported","")).lower()
            if rseq and "100rel" in require:
                await self._send_prack(resp)
            self.state = "proceeding"
            return
        # For final responses, send ACK (even on 401/407/4xx/5xx/6xx) per INVITE rules
        if code >= 200:
            ack = self.build_ack()
            await self.transport.sendto(ack.to_bytes(), self.addr, self.proto, self.writer)
        if code in (401, 407) and not self.auth_tried:
            # Build Authorization/Proxy-Authorization and resend INVITE with incremented CSeq
            chal_hdr = "WWW-Authenticate" if code == 401 else "Proxy-Authenticate"
            chal = resp.headers.get(chal_hdr)
            if chal:
                params = parse_auth_challenge(chal)
                self.nc += 1
                header_name, authv = build_digest_authorization(
                    method=self.request.method or "INVITE",
                    uri=self.request.request_uri or "",
                    username=self.request.headers.get("Authorization-User","alice"),
                    password=self.request.headers.get("Authorization-Pass","alice"),
                    chal=params,
                    is_proxy=(code == 407),
                    cseq_nc=self.nc
                )
                new_req = SipMessage(True, method=self.request.method, request_uri=self.request.request_uri, headers=dict(self.request.headers), body=self.request.body)
                # Increment CSeq number for re-INVITE
                if "CSeq" in new_req.headers:
                    n, m = new_req.headers["CSeq"].split()
                    new_req.headers["CSeq"] = f"{int(n)+1} {m}"
                new_req.headers[header_name] = authv
                # New branch for a new client transaction
                via = new_req.headers.get("Via","")
                new_req.headers["Via"] = re.sub(r"branch=[^;]+", f"branch={gen_branch()}", via) if "branch=" in via else (via + f";branch={gen_branch()}")
                # Mark tried
                self.auth_tried = True
                # Start a fresh transaction by delegating back to TM (handled outside)
                self.state = "authenticated-retry"
            return
        if 200 <= code < 300:
            self.state = "accepted"
        else:
            self.state = "completed"
        if not self._response_event.is_set():
            self._response_event.set()

    async def _send_prack(self, prov: SipMessage):
        # RAck: RSeq CSeq Method (of original INVITE)
        rseq = prov.headers.get("RSeq","")
        cseq = self.request.headers.get("CSeq","")
        method = cseq.split()[1] if len(cseq.split()) > 1 else "INVITE"
        rack = f"{rseq} {cseq.split()[0]} {method}"
        prack = SipMessage(True, method="PRACK", request_uri=self.request.request_uri, headers={})
        # Copy dialog-identifying headers
        for k in ("From","To","Call-ID","Contact"):
            if k in prov.headers:
                prack.headers[k] = prov.headers[k] if k != "To" else prov.headers["To"]
        # New Via/branch
        prack.headers["Via"] = f"SIP/2.0/UDP 127.0.0.1:5060;branch={gen_branch()}"
        prack.headers["Max-Forwards"] = "70"
        prack.headers["CSeq"] = f"{int(self.request.headers.get('CSeq','1 INVITE').split()[0])+1} PRACK"
        prack.headers["RAck"] = rack
        prack.headers["Content-Length"] = "0"
        await self.transport.sendto(prack.to_bytes(), self.addr, self.proto, self.writer)

class ServerTransaction:
    def __init__(self, transport, key, request, addr, proto):
        self.transport = transport
        self.key = key
        self.request: SipMessage = request
        self.addr = addr
        self.proto = proto
        self.state = "init"

    async def start(self):
        # Default handling for REGISTER/OPTIONS
        if self.request.method in ("REGISTER","OPTIONS","PRACK","CANCEL","BYE"):
            if self.request.method == "CANCEL":
                # 200 OK to CANCEL; INVITE will be answered 487 by UAS core
                resp = make_response(self.request, 200, "OK")
                await self.transport.sendto(resp.to_bytes(), self.addr, self.proto)
            elif self.request.method == "PRACK":
                resp = make_response(self.request, 200, "OK")
                await self.transport.sendto(resp.to_bytes(), self.addr, self.proto)
            elif self.request.method == "BYE":
                resp = make_response(self.request, 200, "OK")
                await self.transport.sendto(resp.to_bytes(), self.addr, self.proto)
            else:
                resp = make_response(self.request, 200, "OK")
                await self.transport.sendto(resp.to_bytes(), self.addr, self.proto)

class NonInviteServerTransaction(ServerTransaction):
    pass

class InviteServerTransaction(ServerTransaction):
    pass

class TransactionManager:
    def __init__(self, transport: SipTransport, local_addr: Tuple[str, int], host: str, sip_port: int, ua_ref=None):
        self.transport = transport
        self.local_addr = local_addr
        self.client_tx: Dict[str, ClientTransaction] = {}
        self.server_tx: Dict[str, ServerTransaction] = {}
        self.host = host
        self.sip_port = sip_port
        self.ua_ref = ua_ref  # to call back for retries (auth) and dialog mgmt

    def _key_from_msg(self, msg: SipMessage) -> str:
        via = msg.headers.get("Via", "")
        branch = re.search(r"branch=([^;]+)", via or "")
        call_id = msg.headers.get("Call-ID", "")
        cseq = msg.headers.get("CSeq", "")
        method = cseq.split()[1] if len(cseq.split()) > 1 else msg.method or ""
        return f"{branch.group(1) if branch else ''}:{call_id}:{method}"

    async def send_request(self, msg: SipMessage, addr: Tuple[str, int], proto="UDP", writer=None):
        uri_host = addr[0]
        uri_port = addr[1]
        if msg.request_uri:
            try:
                _, parsed_host, parsed_port = parse_sip_uri(msg.request_uri)
                if parsed_host:
                    uri_host = parsed_host
                if parsed_port:
                    uri_port = parsed_port
            except ValueError:
                pass
        local_ip = determine_outbound_ip(self.host, uri_host, uri_port)
        self.host = local_ip
        ensure_req_basics(msg, local_ip, self.sip_port, uri_host, uri_port)
        resolved_addr = (uri_host, uri_port)
        log_sip("SEND", msg, resolved_addr, proto)
        key = self._key_from_msg(msg)
        if msg.method == "INVITE":
            tx = InviteClientTransaction(self.transport, key, msg, resolved_addr, proto, writer)
        else:
            tx = NonInviteClientTransaction(self.transport, key, msg, resolved_addr, proto, writer)
        self.client_tx[key] = tx
        await tx.start()
        response: Optional[SipMessage] = None
        if isinstance(tx, NonInviteClientTransaction):
            try:
                response = await tx.wait_for_response()
            except asyncio.TimeoutError:
                response = None
        if response is not None:
            return response
        # If INVITE needed authenticated retry
        if isinstance(tx, InviteClientTransaction) and tx.state == "authenticated-retry":
            new_req = SipMessage(True, method=tx.request.method, request_uri=tx.request.request_uri, headers=dict(tx.request.headers), body=tx.request.body)
            # Apply Authorization from tx.request headers (they were set there)
            # The tx.request was already updated; send it as a fresh transaction
            await self.send_request(new_req, addr, proto, writer)
        return response

    async def handle_incoming(self, data: bytes, addr: Tuple[str, int], proto: str):
        msg = parse_sip_message(data)
        log_sip("RECV", msg, addr, proto)
        if msg.is_request:
            key = self._key_from_msg(msg)
            if msg.method == "INVITE":
                tx = InviteServerTransaction(self.transport, key, msg, addr, proto)
            else:
                tx = NonInviteServerTransaction(self.transport, key, msg, addr, proto)
            self.server_tx[key] = tx
            await tx.start()
            # Notify UA core for UAS behavior (200 OK, PRACK/ACK, CANCEL->487)
            if self.ua_ref:
                await self.ua_ref.on_request(msg, addr, proto)
        else:
            # Route to matching client transaction
            handled = False
            for k, tx in list(self.client_tx.items()):
                if tx.matches_response(msg):
                    await tx.on_response(msg)
                    if self.ua_ref:
                        await self.ua_ref.on_response(tx, msg)
                    if tx.is_terminated() or tx.state in ("accepted","completed"):
                        self.client_tx.pop(k, None)
                    handled = True
                    break
            if not handled and self.ua_ref:
                await self.ua_ref.on_response(None, msg)

class RtpSession:
    def __init__(self, local_ip: str, local_port: int, remote_ip: str, remote_port: int, payload_type=0, clock=8000):
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.payload_type = payload_type
        self.clock = clock
        self.ssrc = random.randint(1, 2**32-1)
        self.seq = random.randint(0, 65535)
        self.ts = random.randint(0, 2**32-1)
        self._transport = None
        self._task = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: asyncio.DatagramProtocol(),
            local_addr=(self.local_ip, self.local_port)
        )
        self._task = asyncio.create_task(self._send_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self._transport:
            self._transport.close()

    async def _send_loop(self):
        ptime = 0.02
        payload = b"\xFF" * 160
        while True:
            pkt = self._build_rtp(payload)
            self._transport.sendto(pkt, (self.remote_ip, self.remote_port))
            await asyncio.sleep(ptime)
            self.seq = (self.seq + 1) & 0xFFFF
            self.ts = (self.ts + int(self.clock * 0.02)) & 0xFFFFFFFF

    def _build_rtp(self, payload: bytes) -> bytes:
        v_p_x_cc = 0x80
        m_pt = 0x80 | (self.payload_type & 0x7F)
        header = bytes([
            v_p_x_cc, m_pt,
            (self.seq >> 8) & 0xFF, self.seq & 0xFF,
            (self.ts >> 24) & 0xFF, (self.ts >> 16) & 0xFF, (self.ts >> 8) & 0xFF, self.ts & 0xFF,
            (self.ssrc >> 24) & 0xFF, (self.ssrc >> 16) & 0xFF, (self.ssrc >> 8) & 0xFF, self.ssrc & 0xFF
        ])
        return header + payload

class Dialog:
    def __init__(self, call_id: str, local_tag: str, remote_tag: str = "", route_set: Optional[List[str]] = None, remote_target: Optional[str] = None):
        self.call_id = call_id
        self.local_tag = local_tag
        self.remote_tag = remote_tag
        self.route_set = route_set or []
        self.remote_target = remote_target
        self.local_cseq = 1
        self.early = True

class UserAgent:
    def __init__(self, transport: SipTransport, txm: TransactionManager, local_ip="127.0.0.1", sip_port=5060):
        self.transport = transport
        self.txm = txm
        self.local_ip = local_ip
        self.sip_port = sip_port
        self.dialogs: Dict[str, Dialog] = {}
        self.credentials = {"user":"alice","pass":"alice"}
        self.default_headers = {
            "Host": f"{local_ip}",
            "Contact": f"<sip:alice@{local_ip}:{sip_port}>",
            "From": f"<sip:alice@local>;tag={gen_tag()}",
        }
        self.active_rtp: Dict[str,RtpSession] = {}

    def _dialog_key(self, call_id: str, local_tag: str, remote_tag: str) -> str:
        return f"{call_id}|{local_tag}|{remote_tag}"

    def _update_uac_dialog_from_2xx(self, req: SipMessage, resp: SipMessage):
        call_id = resp.headers.get("Call-ID","")
        from_tag = req.headers.get("From","")
        from_tag = re.search(r"tag=([^;>]+)", from_tag).group(1) if "tag=" in from_tag else ""
        to_tag = resp.headers.get("To","")
        to_tag = re.search(r"tag=([^;>]+)", to_tag).group(1) if "tag=" in to_tag else ""
        # RFC3261: route-set from Record-Route in 2xx to INVITE (reverse order)
        rr = [v.strip() for k,v in resp.headers.items() if k.lower()=="record-route"]
        route_set = list(reversed(rr)) if rr else []
        # remote target from Contact
        remote_target = resp.headers.get("Contact","").strip("<>")
        dlg = Dialog(call_id, from_tag, to_tag, route_set, remote_target)
        dlg.early = False
        key = self._dialog_key(call_id, from_tag, to_tag)
        self.dialogs[key] = dlg

    async def _start_rtp_from_sdp(self, call_key: str, peer_ip: str, sdp: bytes):
        m = re.search(rb"m=audio\s+(\d+)\s+RTP/AVP\s+(\d+)", sdp or b"")
        if not m:
            return
        remote_port = int(m.group(1))
        rtp_port = 40000 + random.randint(0,1000)
        rtp = RtpSession(self.local_ip, rtp_port, peer_ip, remote_port)
        await rtp.start()
        self.active_rtp[call_key] = rtp

    async def register(self, registrar: Tuple[str,int], domain="local"):
        uri = f"sip:{domain}"
        req = make_request("REGISTER", uri, {**self.default_headers, "To": f"<sip:{self.credentials['user']}@{domain}>", "Authorization-User": self.credentials["user"], "Authorization-Pass": self.credentials["pass"]})
        await self.txm.send_request(req, registrar, "UDP")

    async def options(self, target_uri: str, dest: Tuple[str,int]):
        req = make_request("OPTIONS", target_uri, self.default_headers)
        return await self.txm.send_request(req, dest, "UDP")

    async def invite(self, target_uri: str, dest: Tuple[str,int], rtp_local_port=40000):
        sdp = build_sdp(self.local_ip, rtp_local_port)
        req = make_request("INVITE", target_uri, {**self.default_headers, "To": f"<{target_uri}>", "Authorization-User": self.credentials["user"], "Authorization-Pass": self.credentials["pass"], "Supported": "100rel"}, body=sdp)
        req.headers["Content-Type"] = "application/sdp"
        await self.txm.send_request(req, dest, "UDP")

    async def cancel(self, original_tx: InviteClientTransaction):
        # CANCEL must use same R-URI and route to same destination as INVITE
        cancel = SipMessage(True, method="CANCEL", request_uri=original_tx.request.request_uri, headers={})
        # Copy headers with same CSeq number but method CANCEL
        for k in ("From","To","Call-ID","Via"):
            cancel.headers[k] = original_tx.request.headers.get(k,"")
        num = original_tx.request.headers.get("CSeq","1 INVITE").split()[0]
        cancel.headers["CSeq"] = f"{num} CANCEL"
        cancel.headers["Max-Forwards"] = "70"
        cancel.headers["Content-Length"] = "0"
        await self.transport.sendto(cancel.to_bytes(), original_tx.addr, original_tx.proto, original_tx.writer)

    async def bye(self, dlg: Dialog, dest: Tuple[str,int], proto="UDP"):
        bye = SipMessage(True, method="BYE", request_uri=dlg.remote_target or "", headers={})
        bye.headers["From"] = f"<sip:alice@{self.local_ip}>;tag={dlg.local_tag}"
        bye.headers["To"] = f"<{dlg.remote_target or ''}>;tag={dlg.remote_tag}"
        bye.headers["Call-ID"] = dlg.call_id
        bye.headers["CSeq"] = f"{dlg.local_cseq+1} BYE"
        bye.headers["Max-Forwards"] = "70"
        bye.headers["Via"] = f"SIP/2.0/UDP {self.local_ip}:{self.sip_port};branch={gen_branch()}"
        bye.headers["Content-Length"] = "0"
        await self.transport.sendto(bye.to_bytes(), dest, proto)

    async def on_request(self, req: SipMessage, addr: Tuple[str,int], proto: str):
        # Minimal UAS for INVITE: send 180 with 100rel + RSeq, then 200 with SDP
        if req.method == "INVITE":
            # Send reliable provisional (180) if Supported/Require allows
            supported = (req.headers.get("Supported","") + "," + req.headers.get("Require","")).lower()
            if "100rel" in supported:
                prov = make_response(req, 180, "Ringing", headers={"Require": "100rel", "RSeq": "1"})
                await self.transport.sendto(prov.to_bytes(), addr, proto)
            # Answer with 200 OK + SDP
            local_rtp_port = 40100
            sdp = build_sdp(self.local_ip, local_rtp_port)
            resp = make_response(req, 200, "OK", body=sdp)
            await self.transport.sendto(resp.to_bytes(), addr, proto)
        elif req.method == "PRACK":
            # 200 OK to PRACK already handled in ServerTransaction
            pass
        elif req.method == "CANCEL":
            # Send 487 to the original INVITE as per UAS behavior
            inv_req = req  # In a real core, map CANCEL to original INVITE server tx
            resp487 = make_response(inv_req, 487, "Request Terminated")
            await self.transport.sendto(resp487.to_bytes(), addr, proto)
        elif req.method == "BYE":
            # 200 OK is sent in ServerTransaction; stop RTP
            # Find dialog by Call-ID and tags to stop RTP
            pass

    async def on_response(self, tx: Optional[ClientTransaction], resp: SipMessage):
        code = resp.status_code or 0
        if tx and isinstance(tx, InviteClientTransaction):
            # Handle 2xx to INVITE: establish dialog, start RTP, send ACK (already sent)
            if 200 <= code < 300:
                self._update_uac_dialog_from_2xx(tx.request, resp)
                key = self._dialog_key(resp.headers.get("Call-ID",""),
                                       re.search(r"tag=([^;>]+)", tx.request.headers.get("From","")).group(1),
                                       re.search(r"tag=([^;>]+)", resp.headers.get("To","")).group(1))
                await self._start_rtp_from_sdp(key, tx.addr[0], resp.body or b"")
        # Handle 401/407 for REGISTER/OPTIONS (non-INVITE): build auth and retry
        if tx and isinstance(tx, NonInviteClientTransaction) and code in (401,407) and not tx.auth_tried:
            chal_hdr = "WWW-Authenticate" if code == 401 else "Proxy-Authenticate"
            chal = resp.headers.get(chal_hdr)
            if chal:
                params = parse_auth_challenge(chal)
                tx.nc += 1
                header_name, authv = build_digest_authorization(
                    method=tx.request.method or "",
                    uri=tx.request.request_uri or "",
                    username=tx.request.headers.get("Authorization-User", self.credentials["user"]),
                    password=tx.request.headers.get("Authorization-Pass", self.credentials["pass"]),
                    chal=params,
                    is_proxy=(code == 407),
                    cseq_nc=tx.nc
                )
                new_req = SipMessage(True, method=tx.request.method, request_uri=tx.request.request_uri, headers=dict(tx.request.headers), body=tx.request.body)
                # increment CSeq
                if "CSeq" in new_req.headers:
                    n, m = new_req.headers["CSeq"].split()
                    new_req.headers["CSeq"] = f"{int(n)+1} {m}"
                new_req.headers[header_name] = authv
                await self.txm.send_request(new_req, tx.addr, tx.proto, tx.writer)

async def main():
    local_ip = "0.0.0.0"
    sip_port = 5060
    transport = SipTransport()
    txm = TransactionManager(transport, (local_ip, sip_port), local_ip, sip_port)
    ua = UserAgent(transport, txm, local_ip, sip_port)
    txm.ua_ref = ua

    def on_message(data: bytes, addr: Tuple[str,int], proto: str):
        asyncio.create_task(txm.handle_incoming(data, addr, proto))
    transport.on_message = on_message

    udp_transport = await serve_udp(transport, host=local_ip, port=sip_port)
    tcp_server = await serve_tcp(transport, host=local_ip, port=sip_port)

    # Exemplo: discar
    # await ua.invite("sip:bob@127.0.0.1", ("127.0.0.1", 5062))
    try:
        resp = await ua.options("sip:1111@demo.mizu-voip.com:37075", ("demo.mizu-voip.com", 37075))
        if resp:
            print("[FINAL] Received response:")
            print(format_sip_message(resp))
        else:
            print("[FINAL] No SIP response received before timeout")
    finally:
        transport._udp_transport = None
        udp_transport.close()
        tcp_server.close()
        await tcp_server.wait_closed()

    # await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
