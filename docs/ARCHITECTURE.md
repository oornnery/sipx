# SIPX - Arquitetura

Documentação completa da arquitetura da biblioteca SIPX - Um cliente e servidor SIP moderno para Python.

**Versão**: 2.0.0  
**Data**: Outubro 2025  
**Status**: ✅ Produção

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Princípios de Design](#princípios-de-design)
- [Camadas da Arquitetura](#camadas-da-arquitetura)
- [Componentes Principais](#componentes-principais)
- [Fluxo de Mensagens](#fluxo-de-mensagens)
- [Gerenciamento de Estado](#gerenciamento-de-estado)
- [Sistema de Eventos](#sistema-de-eventos)
- [Autenticação](#autenticação)
- [Transporte](#transporte)
- [Concorrência](#concorrência)
- [Extensibilidade](#extensibilidade)

---

## 🎯 Visão Geral

SIPX é uma biblioteca SIP (Session Initiation Protocol) moderna e completa para Python que fornece:

- **Cliente SIP** - Envio de requisições (REGISTER, INVITE, OPTIONS, etc)
- **Servidor SIP** - Recebimento de requisições
- **Autenticação Digest** - Suporte completo a RFC 2617
- **SDP** - Criação e análise de Session Description Protocol
- **Múltiplos Transports** - UDP, TCP (WebSocket planejado)
- **Event System** - Sistema de eventos baseado em decoradores
- **State Management** - Rastreamento de transações e diálogos
- **Auto Re-registration** - Re-registro automático com threading/asyncio

### Características Principais

```
┌─────────────────────────────────────────────────────────────┐
│                        SIPX Library                         │
├─────────────────────────────────────────────────────────────┤
│  📡 Transport Layer        │  🔐 Auth Layer                 │
│  • UDP/TCP                 │  • Digest Authentication       │
│  • Async/Sync              │  • Manual retry_with_auth()    │
│                            │  • Realm/nonce handling        │
├─────────────────────────────────────────────────────────────┤
│  📨 Message Layer          │  📊 SDP Layer                  │
│  • Request/Response        │  • Offer/Answer                │
│  • Header parsing          │  • Codec negotiation           │
│  • RFC 3261 ordering       │  • Media analysis              │
├─────────────────────────────────────────────────────────────┤
│  🎭 Event System           │  💾 State Management           │
│  • @event_handler          │  • Transactions                │
│  • Runtime hooks           │  • Dialogs                     │
│  • Custom handlers         │  • Call state                  │
├─────────────────────────────────────────────────────────────┤
│  🔄 Client/AsyncClient     │  🎯 High-level Methods         │
│  • Sync/Async APIs         │  • register()                  │
│  • Context managers        │  • invite() / ack() / bye()    │
│  • Auto cleanup            │  • options() / message()       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Princípios de Design

### 1. **Simplicidade**
```python
# API limpa e intuitiva
with Client(auth=auth) as client:
    response = client.register(aor="sip:user@domain.com")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
```

### 2. **Controle Explícito**
```python
# Autenticação manual - desenvolvedor controla o fluxo
response = client.invite(to_uri="sip:bob@example.com")
if response.status_code == 401:
    # Decide quando e como fazer retry
    response = client.retry_with_auth(response)
```

### 3. **RFC Compliance**
- **RFC 3261** - SIP (Session Initiation Protocol)
- **RFC 2617** - HTTP Digest Authentication
- **RFC 4566** - SDP (Session Description Protocol)
- **RFC 3264** - Offer/Answer Model

### 4. **Type Safety**
```python
def invite(
    self,
    to_uri: str,
    from_uri: Optional[str] = None,
    body: Optional[str] = None,
    **kwargs
) -> Response:
```

### 5. **Extensibilidade**
```python
# Event handlers customizados
class MyEvents(Events):
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        # Custom logic
        pass
```

---

## 📚 Camadas da Arquitetura

### Diagrama de Camadas

```
┌──────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│              (User Code, Examples, Tests)                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    High-Level API Layer                      │
│         Client / AsyncClient / SIPServer                     │
│    • register()  • invite()  • ack()  • bye()                │
│    • options()   • message() • subscribe()                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    Event System Layer                        │
│                Events + @event_handler                       │
│    • on_request   • on_response   • on_auth_challenge        │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                   Message Layer                              │
│        Request / Response / Headers / Body                   │
│    • Parsing   • Validation   • Serialization                │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                  State Management Layer                      │
│          StateManager / Transaction / Dialog                 │
│    • Transaction tracking   • Dialog tracking                │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                   Transport Layer                            │
│            UDPTransport / TCPTransport                       │
│    • send()   • receive()   • async variants                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    Network Layer                             │
│                  socket / asyncio                            │
└──────────────────────────────────────────────────────────────┘
```

### Responsabilidades por Camada

#### 1. **Network Layer**
- Sockets UDP/TCP
- I/O assíncrono (asyncio)
- Conexões de rede

#### 2. **Transport Layer**
```python
# sipx/_transport.py
class Transport(ABC):
    @abstractmethod
    def send(self, data: bytes, address: Address) -> None: ...
    
    @abstractmethod
    def receive(self, timeout: float) -> tuple[bytes, Address]: ...
```

#### 3. **State Management Layer**
```python
# sipx/_state.py
class StateManager:
    def create_transaction(self, request: Request) -> Transaction: ...
    def create_dialog(self, request: Request, response: Response) -> Dialog: ...
```

#### 4. **Message Layer**
```python
# sipx/_models/_message.py
class Request(SIPMessage):
    method: str
    uri: str
    headers: Headers
    body: Optional[MessageBody]
```

#### 5. **Event System Layer**
```python
# sipx/_events.py
class Events:
    @event_handler("request")
    def on_request(self, request: Request, context: RequestContext): ...
```

#### 6. **High-Level API Layer**
```python
# sipx/_client.py
class Client:
    def register(self, aor: str, **kwargs) -> Response: ...
    def invite(self, to_uri: str, **kwargs) -> Response: ...
```

#### 7. **Application Layer**
```python
# examples/asterisk_demo.py
with Client(auth=auth) as client:
    response = client.register(aor="sip:1111@127.0.0.1")
```

---

## 🔧 Componentes Principais

### 1. Client / AsyncClient

**Localização**: `sipx/_client.py`

Cliente SIP síncrono e assíncrono que gerencia todo o ciclo de vida de requisições SIP.

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
        self._transport = ...
        self._state_manager = StateManager()
        self._auth = auth
        self._events = events
        
    def request(self, method: str, uri: str, **kwargs) -> Response:
        """Generic SIP request"""
        
    def register(self, aor: str, **kwargs) -> Response:
        """REGISTER request"""
        
    def invite(self, to_uri: str, **kwargs) -> Response:
        """INVITE request"""
```

**Recursos**:
- Context manager (`with` statement)
- Retry com autenticação (`retry_with_auth()`)
- Auto re-registration (threading)
- Event system integrado
- State management automático

### 2. Transport

**Localização**: `sipx/_transport.py`

Camada de transporte abstrata com implementações UDP/TCP.

```python
class Transport(ABC):
    """Abstract transport layer"""
    
    @property
    @abstractmethod
    def local_address(self) -> Address: ...
    
    @abstractmethod
    def send(self, data: bytes, address: Address) -> None: ...
    
    @abstractmethod
    def receive(self, timeout: float) -> tuple[bytes, Address]: ...

class UDPTransport(Transport):
    """UDP transport implementation"""
    
class TCPTransport(Transport):
    """TCP transport implementation"""
```

### 3. Messages

**Localização**: `sipx/_models/_message.py`

Representação de mensagens SIP (Request/Response).

```python
class SIPMessage(ABC):
    """Base class for SIP messages"""
    headers: Headers
    body: Optional[MessageBody]
    
class Request(SIPMessage):
    method: str  # INVITE, REGISTER, etc
    uri: str
    version: str = "SIP/2.0"
    
    def to_bytes(self) -> bytes:
        """Serialize to wire format"""
        
class Response(SIPMessage):
    status_code: int
    reason_phrase: str
    request: Request  # Original request
```

### 4. Headers

**Localização**: `sipx/_models/_header.py`

Container case-insensitive com ordenação RFC 3261.

```python
class Headers(HeaderContainer):
    """Case-insensitive headers with RFC 3261 ordering"""
    
    def __getitem__(self, key: str) -> str: ...
    def __setitem__(self, key: str, value: str) -> None: ...
    
    def to_lines(self) -> list[str]:
        """Return headers in RFC 3261 order"""
        # Via, From, To, Call-ID, CSeq, Contact, ...
```

**Ordem RFC 3261**:
1. Via
2. From
3. To
4. Call-ID
5. CSeq
6. Contact
7. Max-Forwards
8. Route / Record-Route
9. Authorization / Proxy-Authorization
10. Other headers
11. Content-Type
12. Content-Length (sempre último)

### 5. SDP (Session Description Protocol)

**Localização**: `sipx/_models/_body.py`

Criação e análise de SDP.

```python
class SDPBody(MessageBody):
    """SDP message body"""
    
    @staticmethod
    def create_offer(
        session_name: str,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        media_specs: list[dict],
    ) -> SDPBody:
        """Create SDP offer"""
        
    @staticmethod
    def create_answer(
        offer: SDPBody,
        origin_username: str,
        origin_address: str,
        connection_address: str,
    ) -> SDPBody:
        """Create SDP answer from offer"""
        
    def get_codecs_summary(self) -> list[str]:
        """Get codec names: ['PCMU', 'PCMA']"""
        
    def has_early_media(self) -> bool:
        """Check for early media indicators"""
```

### 6. Authentication

**Localização**: `sipx/_auth.py`

Autenticação Digest HTTP (RFC 2617).

```python
class Auth:
    """Authentication credentials"""
    
    @staticmethod
    def Digest(
        username: str,
        password: str,
        realm: Optional[str] = None,
        **kwargs
    ) -> Auth:
        """Create Digest auth"""
        
    def calculate_response(
        self,
        method: str,
        uri: str,
        nonce: str,
        **kwargs
    ) -> str:
        """Calculate authentication response"""
```

**Fluxo de autenticação**:
```
1. Client → Request → Server
2. Client ← 401/407 (WWW-Authenticate) ← Server
3. Client → Request + Authorization → Server
4. Client ← 200 OK ← Server
```

### 7. Events

**Localização**: `sipx/_events.py`

Sistema de eventos baseado em decoradores.

```python
class Events:
    """Event system with decorator-based handlers"""
    
    @event_handler("request")
    def on_request(
        self,
        request: Request,
        context: RequestContext
    ) -> Optional[Request]:
        """Handle outgoing request"""
        
    @event_handler("response")
    def on_response(
        self,
        response: Response,
        context: RequestContext
    ) -> Optional[Response]:
        """Handle incoming response"""
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

### 8. State Manager

**Localização**: `sipx/_state.py`

Gerenciamento de transações e diálogos.

```python
class StateManager:
    """Manage SIP transactions and dialogs"""
    
    def create_transaction(
        self,
        request: Request
    ) -> Transaction:
        """Create new transaction"""
        
    def create_dialog(
        self,
        request: Request,
        response: Response
    ) -> Dialog:
        """Create dialog from INVITE/200"""
        
    def find_transaction(
        self,
        response: Response
    ) -> Optional[Transaction]:
        """Find transaction for response"""
```

**Transaction**:
- Associado a um request/response
- Rastreado por branch parameter
- Timeout configurable

**Dialog**:
- Criado por INVITE/200
- Identificado por Call-ID + tags
- Mantém estado de chamada

---

## 🔄 Fluxo de Mensagens

### REGISTER Flow

```
┌────────┐                                    ┌──────────┐
│ Client │                                    │ Server   │
└───┬────┘                                    └────┬─────┘
    │                                              │
    │ 1. REGISTER (sem auth)                       │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 2. 401 Unauthorized (WWW-Authenticate)       │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 3. REGISTER (com Authorization)              │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 4. 200 OK (Contact, Expires)                 │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ [Auto re-registration after ~expires-60]     │
    │                                              │
    │ 5. REGISTER (renewal)                        │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 6. 200 OK                                    │
    │◄─────────────────────────────────────────────┤
    │                                              │
```

### INVITE Flow (Early Offer)

```
┌────────┐                                    ┌──────────┐
│ Client │                                    │ Server   │
└───┬────┘                                    └────┬─────┘
    │                                              │
    │ 1. INVITE (com SDP offer)                    │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 2. 401 Unauthorized                          │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 3. INVITE (com SDP + auth)                   │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 4. 100 Trying                                │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 5. 180 Ringing (opcional)                    │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 6. 200 OK (com SDP answer)                   │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 7. ACK                                       │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ [RTP media session]                          │
    │◄────────────────────────────────────────────►│
    │                                              │
    │ 8. BYE                                       │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 9. 200 OK                                    │
    │◄─────────────────────────────────────────────┤
    │                                              │
```

### INVITE Flow (Late Offer com 183)

```
┌────────┐                                    ┌──────────┐
│ Client │                                    │ Server   │
└───┬────┘                                    └────┬─────┘
    │                                              │
    │ 1. INVITE (sem SDP)                          │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ 2. 100 Trying                                │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 3. 183 Session Progress (com SDP offer)      │
    │◄─────────────────────────────────────────────┤
    │    [Early Media - servidor envia RTP]        │
    │                                              │
    │ 4. 200 OK (com SDP)                          │
    │◄─────────────────────────────────────────────┤
    │                                              │
    │ 5. ACK (com SDP answer)                      │
    ├─────────────────────────────────────────────►│
    │                                              │
    │ [Full RTP media session]                     │
    │◄────────────────────────────────────────────►│
    │                                              │
```

---

## 💾 Gerenciamento de Estado

### Transaction State Machine

```
                    ┌─────────┐
                    │  NULL   │
                    └────┬────┘
                         │ send request
                         ▼
                    ┌─────────┐
            ┌──────►│ CALLING │
            │       └────┬────┘
            │            │ receive 1xx
            │            ▼
            │       ┌─────────┐
            │       │PROCEEDING│
            │       └────┬────┘
            │            │ receive 2xx/3xx/4xx/5xx
            │            ▼
            │       ┌─────────┐
            └───────┤COMPLETED│
                    └────┬────┘
                         │ timeout or ACK sent
                         ▼
                    ┌─────────┐
                    │TERMINATED│
                    └─────────┘
```

### Dialog State Machine

```
                    ┌─────────┐
                    │  NULL   │
                    └────┬────┘
                         │ INVITE sent
                         ▼
                    ┌─────────┐
                    │  EARLY  │
                    └────┬────┘
                         │ 200 OK received
                         ▼
                    ┌─────────┐
            ┌──────►│CONFIRMED│◄──────┐
            │       └────┬────┘       │
            │            │             │
            │    re-INVITE             │ UPDATE
            │            │             │
            │            ▼             │
            │       ┌─────────┐       │
            └───────┤ UPDATED │───────┘
                    └────┬────┘
                         │ BYE sent/received
                         ▼
                    ┌─────────┐
                    │TERMINATED│
                    └─────────┘
```

### State Storage

```python
class StateManager:
    def __init__(self):
        self._transactions: dict[str, Transaction] = {}
        self._dialogs: dict[str, Dialog] = {}
        
    def create_transaction(self, request: Request) -> Transaction:
        branch = self._extract_branch(request)
        transaction = Transaction(
            id=branch,
            request=request,
            state=TransactionState.CALLING,
            created_at=time.time(),
        )
        self._transactions[branch] = transaction
        return transaction
        
    def find_dialog(self, call_id: str, tags: tuple) -> Optional[Dialog]:
        dialog_id = f"{call_id}:{tags[0]}:{tags[1]}"
        return self._dialogs.get(dialog_id)
```

---

## 🎭 Sistema de Eventos

### Arquitetura

```
┌────────────────────────────────────────────────────────┐
│                   Application Code                     │
│                                                        │
│  class MyEvents(Events):                              │
│      @event_handler("response")                       │
│      def on_response(self, response, context):        │
│          # Custom logic                               │
│          return response  # Can modify or None        │
└──────────────────┬─────────────────────────────────────┘
                   │
                   │ inherits
                   ▼
┌────────────────────────────────────────────────────────┐
│                  Events Base Class                     │
│                                                        │
│  • _call_request_handlers()                           │
│  • _call_response_handlers()                          │
│  • _detect_auth_challenge()                           │
└──────────────────┬─────────────────────────────────────┘
                   │
                   │ calls
                   ▼
┌────────────────────────────────────────────────────────┐
│                Event Handler Registry                  │
│                                                        │
│  {                                                     │
│    "request": [on_request, ...],                      │
│    "response": [on_response, ...],                    │
│    "auth_challenge": [on_auth_challenge, ...],        │
│  }                                                     │
└────────────────────────────────────────────────────────┘
```

### Decorator Pattern

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

### Handler Execution

```python
class Events:
    def _call_response_handlers(
        self,
        response: Response,
        context: RequestContext
    ) -> Response:
        """Call all registered response handlers"""
        
        # Find all methods with @event_handler("response")
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_event_types"):
                if "response" in method._event_types:
                    # Call handler
                    result = method(response, context)
                    if result is not None:
                        response = result
                        
        return response
```

### Context Object

```python
@dataclass
class RequestContext:
    """Context passed to event handlers"""
    transaction: Optional[Transaction] = None
    dialog: Optional[Dialog] = None
    source: Optional[Address] = None
    destination: Optional[Address] = None
    response: Optional[Response] = None
```

---

## 🔐 Autenticação

### Digest Authentication Flow

```python
# 1. Initial request (no auth)
request = Request("REGISTER", "sip:user@domain.com")
response = client.send(request)

# 2. Receive challenge
# response.status_code == 401
# response.headers["WWW-Authenticate"] = 
#   'Digest realm="asterisk", nonce="abc123", qop="auth"'

# 3. Extract challenge parameters
auth_header = response.headers["WWW-Authenticate"]
params = parse_auth_header(auth_header)

# 4. Calculate response
auth = client._auth
response_hash = auth.calculate_response(
    method=request.method,
    uri=request.uri,
    nonce=params["nonce"],
    realm=params["realm"],
    qop=params.get("qop"),
)

# 5. Add Authorization header
request.headers["Authorization"] = (
    f'Digest username="{auth.username}", '
    f'realm="{params["realm"]}", '
    f'nonce="{params["nonce"]}", '
    f'uri="{request.uri}", '
    f'response="{response_hash}", '
    f'algorithm=MD5, '
    f'qop=auth, '
    f'nc=00000001, '
    f'cnonce="{generate_cnonce()}"'
)

# 6. Retry request
response = client.send(request)
# response.status_code == 200
```

### Manual vs Auto Retry

**Manual (Recomendado)**:
```python
response = client.register(aor="sip:user@domain.com")
if response.status_code == 401:
    response = client.retry_with_auth(response)
```

**Via Events (Automático)**:
```python
class AutoAuthEvents(Events):
    @event_handler("auth_challenge")
    def on_auth(self, response: Response, context: RequestContext):
        # Automatically retry with auth
        return self.client.retry_with_auth(response)
```

---

## 🚀 Transporte

### Transport Abstraction

```python
class Transport(ABC):
    """Abstract transport interface"""
    
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

### UDP Transport

```python
class UDPTransport(Transport):
    def __init__(self, local_host: str, local_port: int):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((local_host, local_port))
        
    def send(self, data: bytes, address: Address) -> None:
        self._socket.sendto(data, (address.host, address.port))
        
    def receive(self, timeout: float) -> tuple[bytes, Address]:
        self._socket.settimeout(timeout)
        data, addr = self._socket.recvfrom(65535)
        return data, Address(host=addr[0], port=addr[1])
```

### TCP Transport

```python
class TCPTransport(Transport):
    def __init__(self, local_host: str, local_port: int):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((local_host, local_port))
        self._connections: dict[Address, socket.socket] = {}
        
    def send(self, data: bytes, address: Address) -> None:
        # Get or create connection
        conn = self._get_connection(address)
        conn.sendall(data)
```

---

## ⚡ Concorrência

### Sync vs Async

**Synchronous Client**:
```python
class Client:
    def __init__(self, ...):
        self._transport = UDPTransport(...)
        self._rereg_timer: Optional[threading.Timer] = None
        
    def enable_auto_reregister(self, aor: str, interval: int):
        def _reregister():
            self.register(aor=aor)
            self._rereg_timer = threading.Timer(interval, _reregister)
            self._rereg_timer.start()
            
        _reregister()
```

**Asynchronous Client**:
```python
class AsyncClient:
    def __init__(self, ...):
        self._transport = AsyncUDPTransport(...)
        self._rereg_task: Optional[asyncio.Task] = None
        
    async def enable_auto_reregister(self, aor: str, interval: int):
        async def _reregister():
            while True:
                await asyncio.sleep(interval)
                await self.register(aor=aor)
                
        self._rereg_task = asyncio.create_task(_reregister())
```

### Thread Safety

- `Client` usa threading.Timer para auto-reregister
- `AsyncClient` usa asyncio.Task
- State manager é thread-safe (usa locks quando necessário)
- Transport layer é isolado por instância

---

## 🔌 Extensibilidade

### Custom Event Handlers

```python
class RichLogEvents(Events):
    """Event handler with Rich console output"""
    
    @event_handler("request")
    def on_request(self, request: Request, context: RequestContext):
        console.print(f"[cyan]📤 {request.method} → {request.uri}[/cyan]")
        return request
        
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        if response.status_code >= 200 and response.status_code < 300:
            console.print(f"[green]✅ {response.status_code} {response.reason_phrase}[/green]")
        elif response.status_code == 401:
            console.print(f"[yellow]🔐 401 Unauthorized[/yellow]")
        else:
            console.print(f"[red]❌ {response.status_code} {response.reason_phrase}[/red]")
        return response
```

### Custom Transports

```python
class WebSocketTransport(Transport):
    """WebSocket transport (future implementation)"""
    
    async def send(self, data: bytes, address: Address) -> None:
        # Send over WebSocket
        pass
        
    async def receive(self, timeout: float) -> tuple[bytes, Address]:
        # Receive over WebSocket
        pass
```

### Custom Body Parsers

```python
class XMLBody(MessageBody):
    """Custom XML body parser"""
    
    def __init__(self, content: bytes):
        super().__init__(content, "application/xml")
        self.tree = ET.fromstring(content)
        
    def to_string(self) -> str:
        return ET.tostring(self.tree, encoding="unicode")
```

---

## 📊 Diagrama Completo de Arquitetura

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Application Layer                            │
│  examples/asterisk_demo.py, User Code, Tests                        │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                    Client / AsyncClient                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  register()  │  │   invite()   │  │  options()   │              │
│  │  ack()       │  │   bye()      │  │  message()   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
│                           │                                         │
│                  ┌────────▼────────┐                                │
│                  │   request()     │                                │
│                  └────────┬────────┘                                │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                      Event System                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Events                                                      │    │
│  │  • @event_handler("request")                                │    │
│  │  • @event_handler("response")                               │    │
│  │  • @event_handler("auth_challenge")                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                    Message Layer                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Request    │  │   Response   │  │   Headers    │              │
│  │              │  │              │  │              │              │
│  │ • method     │  │ • status_code│  │ • RFC 3261   │              │
│  │ • uri        │  │ • reason     │  │   ordering   │              │
│  │ • headers    │  │ • headers    │  │ • case-      │              │
│  │ • body       │  │ • body       │  │   insensitive│              │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘              │
│         │                 │                                         │
│         └─────────────────┴───────────┬─────────────────────────────┤
│                                       │                             │
│  ┌────────────────────────────────────▼───────────────────────────┐ │
│  │                      Body / SDP                                 │ │
│  │  • create_offer()  • create_answer()                           │ │
│  │  • get_codecs()    • has_early_media()                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                   State Management                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  StateManager                                                 │   │
│  │  • create_transaction()  • find_transaction()                │   │
│  │  • create_dialog()       • find_dialog()                     │   │
│  │  • update_transaction()  • cleanup_old()                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────┐                     ┌──────────────┐             │
│  │ Transaction  │                     │   Dialog     │             │
│  │ • id         │                     │ • call_id    │             │
│  │ • request    │                     │ • local_tag  │             │
│  │ • state      │                     │ • remote_tag │             │
│  │ • timestamp  │                     │ • state      │             │
│  └──────────────┘                     └──────────────┘             │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                    Transport Layer                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ UDPTransport │  │ TCPTransport │  │AsyncTransport│              │
│  │              │  │              │  │              │              │
│  │ • send()     │  │ • send()     │  │ • send()     │              │
│  │ • receive()  │  │ • receive()  │  │ • receive()  │              │
│  │ • close()    │  │ • close()    │  │ • close()    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                      Network Layer                                   │
│  socket (UDP/TCP) | asyncio (async I/O)                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📚 Referências

### RFCs Implementadas

- **RFC 3261** - SIP: Session Initiation Protocol
- **RFC 2617** - HTTP Authentication: Basic and Digest Access Authentication
- **RFC 4566** - SDP: Session Description Protocol
- **RFC 3264** - An Offer/Answer Model with SDP
- **RFC 3581** - An Extension to SIP for Symmetric Response Routing (rport)
- **RFC 3665** - SIP Basic Call Flow Examples

### Documentos Relacionados

- `MODULES.md` - Documentação detalhada de cada módulo
- `API.md` - Referência completa da API pública
- `QUICK_START.md` - Guia de início rápido
- `examples/README.md` - Guia de exemplos

---

**Versão**: 2.0.0  
**Última Atualização**: Outubro 2025  
**Autor**: SIPX Development Team  
**Licença**: MIT