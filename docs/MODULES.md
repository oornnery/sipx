# SIPX - Módulos e Componentes

Documentação detalhada de todos os módulos da biblioteca SIPX.

**Versão**: 2.0.0  
**Data**: Outubro 2025

---

## 📋 Índice

- [Estrutura de Pacotes](#estrutura-de-pacotes)
- [Módulo Principal](#módulo-principal)
- [Modelos de Dados](#modelos-de-dados)
- [Transporte](#transporte)
- [Autenticação](#autenticação)
- [Sistema de Eventos](#sistema-de-eventos)
- [Gerenciamento de Estado](#gerenciamento-de-estado)
- [Utilitários](#utilitários)

---

## 📦 Estrutura de Pacotes

```
sipx/
├── __init__.py              # Public API exports
├── _client.py               # Client & AsyncClient
├── _transport.py            # Transport layer
├── _auth.py                 # Authentication
├── _events.py               # Event system
├── _state.py                # State management
├── _utils.py                # Utilities
├── _types.py                # Type definitions
├── _models/                 # Data models
│   ├── __init__.py
│   ├── _message.py         # Request/Response
│   ├── _header.py          # Headers
│   ├── _body.py            # Message bodies (SDP, etc)
│   └── _address.py         # Address/URI
└── _parsers/                # Parsers
    ├── __init__.py
    ├── _message.py         # Message parser
    ├── _header.py          # Header parser
    └── _sdp.py             # SDP parser
```

---

## 🎯 Módulo Principal

### `sipx/__init__.py`

**Exports públicos**:

```python
# Main classes
from ._client import Client, AsyncClient
from ._auth import Auth, SipAuthCredentials
from ._events import Events, event_handler

# Models
from ._models import (
    Request,
    Response,
    Headers,
    SDPBody,
    MessageBody,
    Address,
)

# State
from ._state import StateManager, Transaction, Dialog

# Types
from ._types import (
    RequestContext,
    TransactionState,
    DialogState,
)
```

### `sipx/_client.py`

**Classes**:
- `Client` - Cliente SIP síncrono
- `AsyncClient` - Cliente SIP assíncrono

**Client**:

```python
class Client:
    """Synchronous SIP client"""
    
    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        transport: str = "UDP",
        auth: Optional[Auth] = None,
        events: Optional[Events] = None,
    ):
        """Initialize SIP client"""
        
    # Generic request
    def request(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: int = 5060,
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        timeout: float = 32.0,
    ) -> Response:
        """Send generic SIP request"""
        
    # Specific methods
    def register(
        self,
        aor: str,
        registrar: Optional[str] = None,
        expires: int = 3600,
        **kwargs
    ) -> Response:
        """Send REGISTER"""
        
    def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        body: Optional[str] = None,
        **kwargs
    ) -> Response:
        """Send INVITE"""
        
    def ack(
        self,
        response: Response,
        **kwargs
    ) -> None:
        """Send ACK"""
        
    def bye(
        self,
        response: Optional[Response] = None,
        dialog_id: Optional[str] = None,
        **kwargs
    ) -> Response:
        """Send BYE"""
        
    def options(
        self,
        uri: str,
        **kwargs
    ) -> Response:
        """Send OPTIONS"""
        
    def message(
        self,
        to_uri: str,
        text: str,
        **kwargs
    ) -> Response:
        """Send MESSAGE"""
        
    # Authentication
    def retry_with_auth(
        self,
        response: Response,
        auth: Optional[Auth] = None,
    ) -> Response:
        """Retry request with authentication"""
        
    # Auto re-registration
    def enable_auto_reregister(
        self,
        aor: str,
        interval: Optional[int] = None,
    ) -> None:
        """Enable automatic re-registration"""
        
    def disable_auto_reregister(self) -> None:
        """Disable automatic re-registration"""
        
    # Unregister
    def unregister(
        self,
        aor: str,
        **kwargs
    ) -> Response:
        """Unregister (REGISTER with expires=0)"""
        
    # Context manager
    def __enter__(self) -> "Client":
        return self
        
    def __exit__(self, *args) -> None:
        self.close()
        
    def close(self) -> None:
        """Close transport and cleanup"""
```

**AsyncClient**:

```python
class AsyncClient:
    """Asynchronous SIP client (same API as Client)"""
    
    async def request(...) -> Response: ...
    async def register(...) -> Response: ...
    async def invite(...) -> Response: ...
    # ... (async versions of all methods)
    
    async def __aenter__(self) -> "AsyncClient": ...
    async def __aexit__(self, *args) -> None: ...
```

---

## 📨 Modelos de Dados

### `sipx/_models/_message.py`

**Classes**:
- `SIPMessage` - Classe base abstrata
- `Request` - Requisição SIP
- `Response` - Resposta SIP

**SIPMessage**:

```python
@dataclass
class SIPMessage(ABC):
    """Base class for SIP messages"""
    headers: Headers
    body: Optional[MessageBody] = None
    
    @abstractmethod
    def to_bytes(self) -> bytes:
        """Serialize to wire format"""
        
    @abstractmethod
    def to_string(self) -> str:
        """Serialize to string"""
        
    @property
    def content_type(self) -> Optional[str]:
        """Get Content-Type header"""
        
    @property
    def content_length(self) -> int:
        """Get Content-Length"""
```

**Request**:

```python
@dataclass
class Request(SIPMessage):
    """SIP Request"""
    method: str
    uri: str
    version: str = "SIP/2.0"
    headers: Headers = field(default_factory=Headers)
    body: Optional[MessageBody] = None
    auth: Optional[Auth] = None
    
    # Convenience properties
    @property
    def call_id(self) -> str:
        """Get Call-ID header"""
        
    @property
    def cseq(self) -> str:
        """Get CSeq header"""
        
    @property
    def via(self) -> str:
        """Get Via header"""
        
    @property
    def from_header(self) -> str:
        """Get From header"""
        
    @property
    def to_header(self) -> str:
        """Get To header"""
        
    # Serialization
    def to_bytes(self) -> bytes:
        """Convert to wire format"""
        
    def to_string(self) -> str:
        """Convert to string"""
        
    # Validation
    def has_valid_via_branch(self) -> bool:
        """Check if Via has valid branch"""
        
    def is_options(self) -> bool:
        """Check if method is OPTIONS"""
```

**Response**:

```python
@dataclass
class Response(SIPMessage):
    """SIP Response"""
    status_code: int
    reason_phrase: str
    version: str = "SIP/2.0"
    headers: Headers = field(default_factory=Headers)
    body: Optional[MessageBody] = None
    request: Optional[Request] = None
    
    # Status code checks
    def is_provisional(self) -> bool:
        """Check if 1xx"""
        
    def is_successful(self) -> bool:
        """Check if 2xx"""
        
    def is_redirect(self) -> bool:
        """Check if 3xx"""
        
    def is_client_error(self) -> bool:
        """Check if 4xx"""
        
    def is_server_error(self) -> bool:
        """Check if 5xx"""
        
    def is_auth_challenge(self) -> bool:
        """Check if 401 or 407"""
```

### `sipx/_models/_header.py`

**Classes**:
- `HeaderContainer` - Interface abstrata
- `Headers` - Implementação de headers

**Headers**:

```python
class Headers(HeaderContainer):
    """Case-insensitive headers with RFC 3261 ordering"""
    
    def __init__(
        self,
        headers: Optional[dict[str, str]] = None,
        encoding: str = "utf-8"
    ):
        """Initialize headers"""
        
    # Dict-like interface
    def __getitem__(self, key: str) -> str: ...
    def __setitem__(self, key: str, value: str) -> None: ...
    def __delitem__(self, key: str) -> None: ...
    def __contains__(self, key: str) -> bool: ...
    def __iter__(self) -> Iterator[str]: ...
    def __len__(self) -> int: ...
    
    # Methods
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get header with default"""
        
    def items(self) -> Iterator[tuple[str, str]]:
        """Iterate over (name, value) pairs"""
        
    def keys(self) -> Iterator[str]:
        """Iterate over header names"""
        
    def values(self) -> Iterator[str]:
        """Iterate over header values"""
        
    def update(self, other: dict[str, str]) -> None:
        """Update headers"""
        
    def copy(self) -> Headers:
        """Create a copy"""
        
    # Serialization
    def to_lines(self) -> list[str]:
        """Convert to list of 'Name: Value' strings in RFC 3261 order"""
        
    def raw(self, encoding: Optional[str] = None) -> bytes:
        """Serialize to bytes"""
```

**RFC 3261 Header Order**:
1. Via
2. From
3. To
4. Call-ID
5. CSeq
6. Contact
7. Max-Forwards
8. Route / Record-Route
9. Proxy-Authorization / Authorization
10. WWW-Authenticate / Proxy-Authenticate
11. Expires
12. User-Agent / Server
13. Allow / Supported
14. Other headers
15. Content-Type
16. Content-Length (always last)

### `sipx/_models/_body.py`

**Classes**:
- `MessageBody` - Classe base
- `SDPBody` - Session Description Protocol
- `TextBody` - Plain text
- `XMLBody` - XML content

**MessageBody**:

```python
@dataclass
class MessageBody:
    """Base class for message bodies"""
    content: bytes
    content_type: str
    
    def to_bytes(self) -> bytes:
        """Convert to bytes"""
        
    def to_string(self) -> str:
        """Convert to string"""
        
    def __len__(self) -> int:
        """Get content length"""
```

**SDPBody**:

```python
class SDPBody(MessageBody):
    """SDP message body"""
    
    def __init__(self, content: str | bytes):
        """Initialize SDP body"""
        
    # Factory methods
    @staticmethod
    def create_offer(
        session_name: str,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        media_specs: list[dict],
        session_id: Optional[int] = None,
    ) -> SDPBody:
        """Create SDP offer"""
        
    @staticmethod
    def create_answer(
        offer: SDPBody,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        session_id: Optional[int] = None,
    ) -> SDPBody:
        """Create SDP answer from offer"""
        
    # Analysis methods
    def get_media_info(self) -> list[dict]:
        """Get media information"""
        
    def get_codecs_summary(self) -> list[str]:
        """Get codec names: ['PCMU', 'PCMA']"""
        
    def has_early_media(self) -> bool:
        """Check for early media indicators"""
        
    def get_connection_address(self) -> Optional[str]:
        """Get connection address"""
        
    def get_media_ports(self) -> list[int]:
        """Get all media ports"""
        
    def is_media_rejected(self) -> bool:
        """Check if media is rejected (port=0)"""
```

**Exemplo de media_specs**:

```python
media_specs = [
    {
        "media": "audio",
        "port": 8000,
        "codecs": [
            {"payload": "0", "name": "PCMU", "rate": "8000"},
            {"payload": "8", "name": "PCMA", "rate": "8000"},
            {"payload": "101", "name": "telephone-event", "rate": "8000"},
        ],
    }
]
```

### `sipx/_models/_address.py`

**Classes**:
- `Address` - Endereço de transporte (IP:port)
- `URI` - SIP URI parser

**Address**:

```python
@dataclass
class Address:
    """Transport address (IP:port)"""
    host: str
    port: int
    
    def __str__(self) -> str:
        return f"{self.host}:{self.port}"
```

---

## 🚀 Transporte

### `sipx/_transport.py`

**Classes**:
- `Transport` - Interface abstrata
- `UDPTransport` - Transport UDP
- `TCPTransport` - Transport TCP
- `AsyncUDPTransport` - Transport UDP assíncrono
- `AsyncTCPTransport` - Transport TCP assíncrono

**Transport**:

```python
class Transport(ABC):
    """Abstract transport interface"""
    
    @property
    @abstractmethod
    def local_address(self) -> Address:
        """Get local address"""
        
    @abstractmethod
    def send(self, data: bytes, address: Address) -> None:
        """Send data to address"""
        
    @abstractmethod
    def receive(self, timeout: float) -> tuple[bytes, Address]:
        """Receive data with timeout"""
        
    @abstractmethod
    def close(self) -> None:
        """Close transport"""
```

**UDPTransport**:

```python
class UDPTransport(Transport):
    """UDP transport implementation"""
    
    def __init__(self, local_host: str, local_port: int):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((local_host, local_port))
        
    @property
    def local_address(self) -> Address:
        host, port = self._socket.getsockname()
        return Address(host=host, port=port)
```

**TCPTransport**:

```python
class TCPTransport(Transport):
    """TCP transport implementation"""
    
    def __init__(self, local_host: str, local_port: int):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((local_host, local_port))
        self._connections: dict[Address, socket.socket] = {}
```

---

## 🔐 Autenticação

### `sipx/_auth.py`

**Classes**:
- `Auth` - Credenciais de autenticação
- `SipAuthCredentials` - Alias para backward compatibility

**Auth**:

```python
@dataclass
class Auth:
    """SIP authentication credentials"""
    username: str
    password: str
    realm: Optional[str] = None
    algorithm: str = "MD5"
    
    @staticmethod
    def Digest(
        username: str,
        password: str,
        realm: Optional[str] = None,
        **kwargs
    ) -> Auth:
        """Create Digest authentication"""
        return Auth(username=username, password=password, realm=realm, **kwargs)
        
    def calculate_response(
        self,
        method: str,
        uri: str,
        nonce: str,
        realm: Optional[str] = None,
        qop: Optional[str] = None,
        nc: str = "00000001",
        cnonce: Optional[str] = None,
        body: Optional[bytes] = None,
    ) -> str:
        """Calculate authentication response hash"""
```

**Algoritmos suportados**:
- MD5 (padrão)
- MD5-sess
- SHA-256
- SHA-512

**QoP (Quality of Protection)**:
- `auth` - Autenticação apenas
- `auth-int` - Autenticação com integridade

---

## 🎭 Sistema de Eventos

### `sipx/_events.py`

**Classes**:
- `Events` - Classe base para event handlers

**Decorator**:

```python
def event_handler(event_type: str):
    """Decorator to register event handlers"""
    def decorator(func):
        if not hasattr(func, "_event_types"):
            func._event_types = []
        func._event_types.append(event_type)
        return func
    return decorator
```

**Events**:

```python
class Events:
    """Base class for event handlers"""
    
    @event_handler("request")
    def on_request(
        self,
        request: Request,
        context: RequestContext
    ) -> Optional[Request]:
        """Handle outgoing request (can modify or return None)"""
        return request
        
    @event_handler("response")
    def on_response(
        self,
        response: Response,
        context: RequestContext
    ) -> Optional[Response]:
        """Handle incoming response (can modify or return None)"""
        return response
        
    @event_handler("auth_challenge")
    def on_auth_challenge(
        self,
        response: Response,
        context: RequestContext
    ) -> Optional[Response]:
        """Handle 401/407 auth challenge"""
        return response
```

**Eventos disponíveis**:
- `request` - Antes de enviar request
- `response` - Ao receber response
- `auth_challenge` - Ao receber 401/407
- `provisional` - Ao receber 1xx
- `success` - Ao receber 2xx
- `redirect` - Ao receber 3xx
- `client_error` - Ao receber 4xx
- `server_error` - Ao receber 5xx

**Exemplo de uso**:

```python
class MyEvents(Events):
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        if response.status_code == 183:
            print("Early media detected!")
        return response
        
    @event_handler("auth_challenge")
    def on_auth(self, response: Response, context: RequestContext):
        # Automatically retry with auth
        return self.client.retry_with_auth(response)
```

---

## 💾 Gerenciamento de Estado

### `sipx/_state.py`

**Classes**:
- `StateManager` - Gerenciador de estado
- `Transaction` - Transação SIP
- `Dialog` - Diálogo SIP

**StateManager**:

```python
class StateManager:
    """Manage SIP transactions and dialogs"""
    
    def __init__(self):
        self._transactions: dict[str, Transaction] = {}
        self._dialogs: dict[str, Dialog] = {}
        
    def create_transaction(
        self,
        request: Request
    ) -> Transaction:
        """Create new transaction"""
        
    def find_transaction(
        self,
        response: Response
    ) -> Optional[Transaction]:
        """Find transaction for response"""
        
    def update_transaction(
        self,
        transaction_id: str,
        response: Response
    ) -> None:
        """Update transaction with response"""
        
    def create_dialog(
        self,
        request: Request,
        response: Response
    ) -> Dialog:
        """Create dialog from INVITE/200"""
        
    def find_dialog(
        self,
        call_id: str,
        local_tag: str,
        remote_tag: str
    ) -> Optional[Dialog]:
        """Find dialog by identifiers"""
        
    def cleanup_old_transactions(
        self,
        max_age: float = 32.0
    ) -> int:
        """Remove old transactions"""
```

**Transaction**:

```python
@dataclass
class Transaction:
    """SIP transaction"""
    id: str  # Via branch parameter
    request: Request
    state: TransactionState
    created_at: float
    responses: list[Response] = field(default_factory=list)
    
    def add_response(self, response: Response) -> None:
        """Add response to transaction"""
        
    def get_final_response(self) -> Optional[Response]:
        """Get final response (2xx-6xx)"""
```

**TransactionState**:

```python
class TransactionState(Enum):
    """Transaction states (RFC 3261)"""
    CALLING = "calling"          # INVITE sent
    TRYING = "trying"            # non-INVITE sent
    PROCEEDING = "proceeding"    # 1xx received
    COMPLETED = "completed"      # final response received
    CONFIRMED = "confirmed"      # ACK sent (INVITE only)
    TERMINATED = "terminated"    # transaction done
```

**Dialog**:

```python
@dataclass
class Dialog:
    """SIP dialog"""
    id: str
    call_id: str
    local_tag: str
    remote_tag: str
    local_uri: str
    remote_uri: str
    local_seq: int
    remote_seq: int
    state: DialogState
    route_set: list[str] = field(default_factory=list)
    
    def increment_local_seq(self) -> int:
        """Increment and return local CSeq"""
```

**DialogState**:

```python
class DialogState(Enum):
    """Dialog states"""
    EARLY = "early"              # 1xx with To tag
    CONFIRMED = "confirmed"      # 2xx received
    TERMINATED = "terminated"    # BYE sent/received
```

---

## 🛠️ Utilitários

### `sipx/_utils.py`

**Funções e constantes**:

```python
# Constants
EOL = "\r\n"
SIP_VERSION = "SIP/2.0"
BRANCH = "z9hG4bK"  # RFC 3261 magic cookie

# Headers mapping
HEADERS = {
    "via": "Via",
    "from": "From",
    "to": "To",
    # ...
}

HEADERS_COMPACT = {
    "v": "Via",
    "f": "From",
    "t": "To",
    # ...
}

# Rich console and logger
from rich.console import Console
from rich.logging import RichHandler

console = Console()
logger = logging.getLogger("sipx")
logger.addHandler(RichHandler(console=console))

# Utility functions
def generate_call_id(host: str) -> str:
    """Generate unique Call-ID"""
    
def generate_tag() -> str:
    """Generate random tag (8 hex chars)"""
    
def generate_branch() -> str:
    """Generate RFC 3261 compliant branch"""
    
def generate_cnonce() -> str:
    """Generate cnonce for Digest auth"""
    
def parse_uri(uri: str) -> dict:
    """Parse SIP URI"""
```

### `sipx/_types.py`

**Type definitions**:

```python
from typing import TypedDict, Optional

class RequestContext(TypedDict, total=False):
    """Context passed to event handlers"""
    transaction: Optional[Transaction]
    dialog: Optional[Dialog]
    source: Optional[Address]
    destination: Optional[Address]
    response: Optional[Response]
    
# Header types
HeaderTypes = dict[str, str]
```

---

## 📊 Resumo de Módulos

| Módulo | Arquivo | Responsabilidade |
|--------|---------|------------------|
| **Client** | `_client.py` | API de alto nível |
| **Transport** | `_transport.py` | Envio/recebimento de dados |
| **Message** | `_models/_message.py` | Request/Response |
| **Headers** | `_models/_header.py` | Container de headers |
| **Body** | `_models/_body.py` | SDP e outros bodies |
| **Auth** | `_auth.py` | Autenticação Digest |
| **Events** | `_events.py` | Sistema de eventos |
| **State** | `_state.py` | Transações e diálogos |
| **Utils** | `_utils.py` | Funções utilitárias |
| **Types** | `_types.py` | Definições de tipos |

---

## 🔗 Dependências Entre Módulos

```
Client
  ├── Transport (send/receive)
  ├── Auth (credentials)
  ├── Events (handlers)
  ├── State (transactions/dialogs)
  └── Models
      ├── Message (Request/Response)
      ├── Headers
      └── Body (SDP)
```

---

## 📚 Referências

- `ARCHITECTURE.md` - Arquitetura geral
- `API.md` - Referência completa da API
- `QUICK_START.md` - Guia de início rápido
- `examples/README.md` - Exemplos práticos

---

**Versão**: 2.0.0  
**Última Atualização**: Outubro 2025  
**Licença**: MIT