"""Utilities and constants for SIP protocol."""

import logging
from rich.console import Console
from rich.logging import RichHandler

# Rich Console for pretty printing
console = Console()

# Configure logging with RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)

# Get logger for the package
logger = logging.getLogger("sipx")

EOL = "\r\n"
SCHEME = "SIP"
VERSION = "2.0"
BRANCH = "z9hG4bK"

# Formas compactas de headers SIP (RFC 3261 Section 7.3.3)
# Mapeia forma compacta -> nome normalizado (minúsculo)
HEADERS_COMPACT = {
    "v": "via",
    "f": "from",
    "t": "to",
    "m": "contact",
    "i": "call-id",
    "e": "content-encoding",
    "l": "content-length",
    "c": "content-type",
    "s": "subject",
    "k": "supported",
    "a": "accept-contact",
    "u": "allow-events",
    "o": "event",
    "y": "identity",
    "b": "referred-by",
    "r": "refer-to",
    "d": "request-disposition",
    "x": "session-expires",
    "j": "reject-contact",
}

# Headers SIP essenciais e mais comuns com suas formas canônicas
# Mapeia nome normalizado (minúsculo) -> forma canônica correta
HEADERS = {
    # Headers obrigatórios RFC 3261
    # Headers com canonização especial (não seguem Title-Case simples)
    "call-id": "Call-ID",
    "cseq": "CSeq",
    "www-authenticate": "WWW-Authenticate",
    "proxy-authenticate": "Proxy-Authenticate",
    "rack": "RAck",
    "rseq": "RSeq",
    "sip-etag": "SIP-ETag",
    "sip-if-match": "SIP-If-Match",
    "mime-version": "MIME-Version",
    "min-se": "Min-SE",
    "content-id": "Content-ID",
    "session-id": "Session-ID",
    "policy-id": "Policy-ID",
    "via": "Via",
    "from": "From",
    "to": "To",
    "max-forwards": "Max-Forwards",
    # Headers mais comuns
    "contact": "Contact",
    "content-type": "Content-Type",
    "content-length": "Content-Length",
    "authorization": "Authorization",
    "proxy-authorization": "Proxy-Authorization",
    "authentication-info": "Authentication-Info",
    "expires": "Expires",
    "user-agent": "User-Agent",
    "server": "Server",
    "allow": "Allow",
    "supported": "Supported",
    "require": "Require",
    "proxy-require": "Proxy-Require",
    "route": "Route",
    "record-route": "Record-Route",
    "subject": "Subject",
    # Headers de conteúdo
    "content-encoding": "Content-Encoding",
    "content-disposition": "Content-Disposition",
    # Headers de extensões comuns
    "event": "Event",
    "allow-events": "Allow-Events",
    "subscription-state": "Subscription-State",
    "refer-to": "Refer-To",
    "referred-by": "Referred-By",
    "replaces": "Replaces",
    "session-expires": "Session-Expires",
    # Headers P- mais usados (IMS/3GPP)
    "p-asserted-identity": "P-Asserted-Identity",
    "p-preferred-identity": "P-Preferred-Identity",
    "p-charging-vector": "P-Charging-Vector",
    "p-access-network-info": "P-Access-Network-Info",
    "p-called-party-id": "P-Called-Party-ID",
    "p-visited-network-id": "P-Visited-Network-ID",
    "p-associated-uri": "P-Associated-URI",
    "p-served-user": "P-Served-User",
    "p-dcs-trace-party-id": "P-DCS-Trace-Party-ID",
    "p-dcs-osps": "P-DCS-OSPS",
    "p-dcs-billing-info": "P-DCS-Billing-Info",
    "p-dcs-laes": "P-DCS-LAES",
    "p-dcs-redirect": "P-DCS-Redirect",
    # Headers de qualidade/prioridade
    "priority": "Priority",
    "accept": "Accept",
    "accept-encoding": "Accept-Encoding",
    "accept-language": "Accept-Language",
    "accept-contact": "Accept-Contact",
    "reject-contact": "Reject-Contact",
    "request-disposition": "Request-Disposition",
    # Headers informativos
    "date": "Date",
    "timestamp": "Timestamp",
    "retry-after": "Retry-After",
    "warning": "Warning",
    "unsupported": "Unsupported",
    "identity": "Identity",
    "privacy": "Privacy",
    "origination-id": "Origination-ID",
}

# Standard SIP response reason phrases (RFC 3261)
REASON_PHRASES = {
    100: "Trying",
    180: "Ringing",
    181: "Call Is Being Forwarded",
    182: "Queued",
    183: "Session Progress",
    200: "OK",
    202: "Accepted",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    305: "Use Proxy",
    380: "Alternative Service",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    410: "Gone",
    413: "Request Entity Too Large",
    414: "Request-URI Too Long",
    415: "Unsupported Media Type",
    416: "Unsupported URI Scheme",
    420: "Bad Extension",
    421: "Extension Required",
    423: "Interval Too Brief",
    480: "Temporarily Unavailable",
    481: "Call/Transaction Does Not Exist",
    482: "Loop Detected",
    483: "Too Many Hops",
    484: "Address Incomplete",
    485: "Ambiguous",
    486: "Busy Here",
    487: "Request Terminated",
    488: "Not Acceptable Here",
    491: "Request Pending",
    493: "Undecipherable",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Server Time-out",
    505: "Version Not Supported",
    513: "Message Too Large",
    600: "Busy Everywhere",
    603: "Decline",
    604: "Does Not Exist Anywhere",
    606: "Not Acceptable",
}
