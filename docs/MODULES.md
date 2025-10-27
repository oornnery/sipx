# SIPX - Documentação de Módulos e Funcionalidades

## 📋 Índice

1. [Visão Geral dos Módulos](#visão-geral-dos-módulos)
2. [Módulo Client](#módulo-client)
3. [Módulo Server](#módulo-server)
4. [Módulo Handlers](#módulo-handlers)
5. [Módulo Models](#módulo-models)
6. [Módulo Transports](#módulo-transports)
7. [Módulo FSM](#módulo-fsm)
8. [Funcionalidades Implementadas](#funcionalidades-implementadas)
9. [Exemplos de Uso](#exemplos-de-uso)

---

## 🎯 Visão Geral dos Módulos

```
sipx/
├── __init__.py              # API pública
├── _client.py               # Cliente SIP
├── _server.py               # Servidor SIP
├── _fsm.py                  # Máquinas de Estado
├── _types.py                # Definições de tipos
├── _utils.py                # Utilitários
├── _handlers/               # Sistema de handlers
│   ├── _base.py            # Classes base
│   ├── _auth.py            # Autenticação
│   ├── _invite.py          # Fluxo INVITE
│   ├── _register.py        # Fluxo REGISTER
│   ├── _response.py        # Processamento de respostas
│   ├── _state.py           # Rastreamento de estado
│   ├── _utility.py         # Handlers utilitários
│   └── _composite.py       # Handler composto
├── _models/                 # Modelos de dados
│   ├── _message.py         # Request/Response
│   ├── _header.py          # Headers SIP
│   ├── _body.py            # Body content
│   └── _auth.py            # Autenticação
└── _transports/            # Camada de transporte
    ├── _base.py            # Interface base
    ├── _udp.py             # UDP transport
    ├── _tcp.py             # TCP transport
    └── _tls.py             # TLS transport
```

---

## 📱 Módulo Client

### Localização
`sipx/_client.py`

### Classes Principais

#### Client (Síncrono)

Cliente SIP síncrono para operações bloqueantes.

**Inicialização**:
```python
Client(
    local_host: str = "0.0.0.0",
    local_port: int = 5060,
    transport: str = "UDP",
    config: Optional[TransportConfig] = None,
    credentials: Optional[SipAuthCredentials] = None,
)
```

**Parâmetros**:
- `local_host`: IP local para bind (padrão: "0.0.0.0")
- `local_port`: Porta local (padrão: 5060)
- `transport`: Protocolo ("UDP", "TCP", ou "TLS")
- `config`: Configuração avançada de transport
- `credentials`: Credenciais padrão para autenticação

**Métodos Principais**:

##### 1. `register()`
Registra o cliente no servidor SIP.

```python
def register(
    self,
    uri: Optional[str] = None,
    host: Optional[str] = None,
    port: int = 5060,
    expires: int = 3600,
    auth: Optional[SipAuthCredentials] = None,
    **kwargs
) -> Response
```

**Exemplo**:
```python
client = Client(
    local_host="192.168.1.100",
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

response = client.register(
    aor="sip:1111@example.com",
    registrar="example.com",
    expires=3600
)

print(f"Status: {response.status_code}")
```

##### 2. `invite()`
Inicia uma chamada SIP (sessão).

```python
def invite(
    self,
    uri: str,
    host: Optional[str] = None,
    port: int = 5060,
    sdp: Optional[str] = None,
    auth: Optional[SipAuthCredentials] = None,
    **kwargs
) -> Response
```

**Exemplo**:
```python
sdp = """v=0
o=- 123456 123456 IN IP4 192.168.1.100
s=Call
c=IN IP4 192.168.1.100
t=0 0
m=audio 10000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
"""

response = client.invite(
    uri="sip:2222@example.com",
    host="example.com",
    sdp=sdp
)

if response.status_code == 200:
    print("Call answered!")
    # Enviar ACK
    client.ack(response)
```

##### 3. `bye()`
Termina uma chamada ativa.

```python
def bye(
    self,
    dialog: Optional[Dialog] = None,
    uri: Optional[str] = None,
    host: Optional[str] = None,
    port: int = 5060,
    **kwargs
) -> Response
```

**Exemplo**:
```python
# Após INVITE respondido com 200 OK
response = client.bye()
print(f"Call ended: {response.status_code}")
```

##### 4. `message()`
Envia mensagem SIP MESSAGE (IM).

```python
def message(
    self,
    uri: str,
    host: str,
    port: int = 5060,
    content: str = "",
    content_type: str = "text/plain",
    auth: Optional[SipAuthCredentials] = None,
    **kwargs
) -> Response
```

**Exemplo**:
```python
response = client.message(
    uri="sip:2222@example.com",
    host="example.com",
    content="Hello from SIPX!",
    content_type="text/plain"
)
```

##### 5. `options()`
Verifica capacidades do servidor.

```python
def options(
    self,
    uri: str,
    host: str,
    port: int = 5060,
    **kwargs
) -> Response
```

**Exemplo**:
```python
response = client.options(
    uri="sip:example.com",
    host="example.com"
)

# Verificar métodos suportados
if "Allow" in response.headers:
    methods = response.headers["Allow"]
    print(f"Supported methods: {methods}")
```

##### 6. Outros Métodos SIP

- `cancel()`: Cancela um INVITE em progresso
- `subscribe()`: Subscreve a eventos
- `notify()`: Notifica subscritores
- `refer()`: Transfere chamadas
- `info()`: Envia informações mid-dialog
- `update()`: Atualiza sessão
- `prack()`: Confirma resposta provisional
- `publish()`: Publica estado

**Gerenciamento de Handlers**:

```python
# Adicionar handler
client.add_handler(LoggingHandler())

# Remover handler
client.remove_handler(handler)
```

**Context Manager**:
```python
with Client() as client:
    response = client.register(...)
    # Transport fechado automaticamente ao sair
```

**Propriedades**:
```python
client.transport         # Acesso ao transport
client.local_address     # Endereço local
client.is_closed        # Status do cliente
client.state_manager    # Gerenciador de estado
```

#### AsyncClient (Assíncrono)

Cliente SIP assíncrono para operações não-bloqueantes.

**Uso**:
```python
async with AsyncClient() as client:
    response = await client.register(...)
    response = await client.invite(...)
```

**Métodos Async**:
- `async def register()`
- `async def invite()`
- `async def options()`
- `async def request()`

---

## 🖥️ Módulo Server

### Localização
`sipx/_server.py`

### Classes Principais

#### SIPServer (Síncrono)

Servidor SIP que escuta e responde a requests.

**Inicialização**:
```python
SIPServer(
    local_host: str = "0.0.0.0",
    local_port: int = 5060,
    config: Optional[TransportConfig] = None,
)
```

**Exemplo Básico**:
```python
from sipx import SIPServer

server = SIPServer(
    local_host="0.0.0.0",
    local_port=5060
)

# Iniciar servidor
server.start()

# Aguardar...
import time
time.sleep(60)

# Parar servidor
server.stop()
```

**Handlers Padrão**:

O servidor responde automaticamente a:
- **BYE**: 200 OK
- **CANCEL**: 200 OK
- **OPTIONS**: 200 OK com Allow header
- **ACK**: Sem resposta (conforme RFC)

**Handlers Customizados**:

```python
from sipx import SIPServer, Request, Response

def handle_invite(request: Request, source) -> Response:
    """Handler customizado para INVITE."""
    print(f"INVITE recebido de {source}")
    
    # Retornar 200 OK
    return Response(
        status_code=200,
        reason_phrase="OK",
        headers={
            "Via": request.via,
            "From": request.from_header,
            "To": request.to_header,
            "Call-ID": request.call_id,
            "CSeq": request.cseq,
            "Content-Length": "0",
        }
    )

server = SIPServer()
server.register_handler("INVITE", handle_invite)
server.start()
```

**Context Manager**:
```python
with SIPServer() as server:
    # Servidor roda automaticamente
    time.sleep(60)
# Servidor para automaticamente
```

#### AsyncSIPServer (Assíncrono)

Versão assíncrona do servidor.

```python
async with AsyncSIPServer() as server:
    await asyncio.sleep(60)
```

---

## 🔗 Módulo Handlers

### Localização
`sipx/_handlers/`

### Arquitetura

Sistema modular baseado em **Chain of Responsibility** que permite processar requests/responses através de uma cadeia de handlers especializados.

### Classes Base (`_base.py`)

#### EventHandler

Classe abstrata base para handlers síncronos.

```python
class EventHandler(ABC):
    def on_request(self, request: Request, context: EventContext) -> Request:
        """Chamado antes de enviar request."""
        return request
    
    def on_response(self, response: Response, context: EventContext) -> Response:
        """Chamado após receber response."""
        return response
    
    def on_error(self, error: Exception, context: EventContext) -> None:
        """Chamado quando ocorre erro."""
        pass
```

#### EventContext

Container de informações compartilhadas entre handlers.

```python
@dataclass
class EventContext:
    request: Optional[Request] = None
    response: Optional[Response] = None
    destination: Optional[TransportAddress] = None
    source: Optional[TransportAddress] = None
    transaction_id: Optional[str] = None
    dialog_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
```

**Uso do metadata**:
```python
# Handler 1: Armazena informação
def on_request(self, request, context):
    context.metadata["custom_data"] = "value"
    return request

# Handler 2: Lê informação
def on_response(self, response, context):
    data = context.metadata.get("custom_data")
    print(f"Data from previous handler: {data}")
    return response
```

#### HandlerChain

Gerencia cadeia de handlers.

```python
chain = HandlerChain()
chain.add_handler(LoggingHandler())
chain.add_handler(AuthenticationHandler(credentials))
chain.add_handler(InviteFlowHandler())

# Executar cadeia
request = chain.on_request(request, context)
response = chain.on_response(response, context)
```

### Utility Handlers (`_utility.py`)

#### LoggingHandler

Handler para logging de mensagens.

```python
class LoggingHandler(EventHandler):
    def __init__(self, level: str = "INFO"):
        self.level = level
```

**Exemplo**:
```python
client.add_handler(LoggingHandler(level="DEBUG"))
```

**Output**:
```
[INFO] >>> SENDING INVITE
[DEBUG] Via: SIP/2.0/UDP 192.168.1.100:5060...
[INFO] <<< RECEIVED 200 OK
```

#### RetryHandler

Handler para retry automático.

```python
class RetryHandler(EventHandler):
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        retry_on: Optional[List[int]] = None
    ):
        """
        Args:
            max_retries: Número máximo de tentativas
            backoff_factor: Fator de backoff exponencial
            retry_on: Lista de status codes para retry
        """
```

**Exemplo**:
```python
# Retry em timeouts e 503
retry_handler = RetryHandler(
    max_retries=3,
    backoff_factor=1.0,
    retry_on=[503, 408]
)
client.add_handler(retry_handler)
```

#### TimeoutHandler

Handler para controle de timeouts.

```python
class TimeoutHandler(EventHandler):
    def __init__(
        self,
        timeout: float = 32.0,
        on_timeout: Optional[Callable] = None
    ):
        """
        Args:
            timeout: Timeout em segundos
            on_timeout: Callback chamado no timeout
        """
```

**Exemplo**:
```python
def handle_timeout(context):
    print(f"Timeout na transação {context.transaction_id}")

timeout_handler = TimeoutHandler(
    timeout=10.0,
    on_timeout=handle_timeout
)
client.add_handler(timeout_handler)
```

#### HeaderInjectionHandler

Handler para injetar headers customizados.

```python
class HeaderInjectionHandler(EventHandler):
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers
```

**Exemplo**:
```python
# Adicionar headers customizados
custom_headers = HeaderInjectionHandler({
    "X-Custom-Header": "MyValue",
    "User-Agent": "SIPX/1.0"
})
client.add_handler(custom_headers)
```

### Authentication Handler (`_auth.py`)

#### AuthenticationHandler

Handler para autenticação digest automática.

```python
class AuthenticationHandler(EventHandler):
    def __init__(self, credentials: Optional[SipAuthCredentials] = None):
        """
        Args:
            credentials: Credenciais padrão (client-level)
        """
```

**Prioridade de Credenciais**:
1. **Method-level**: `client.invite(auth=credentials)`
2. **Client-level**: `Client(credentials=credentials)`
3. **Handler-level**: `AuthenticationHandler(credentials)` (legacy)

**Exemplo Completo**:
```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

# Opção 1: Client-level (mais simples)
client = Client(
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

# Opção 2: Handler-level (mais flexível)
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx"
)
client = Client()
client.add_handler(AuthenticationHandler(credentials))

# Opção 3: Method-level (prioridade máxima)
response = client.invite(
    to_uri="sip:2222@example.com",
    from_uri="sip:1111@example.com",
    host="example.com",
    auth=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)
```

**Fluxo de Autenticação**:
```
1. Request enviado (sem auth)
2. 401/407 recebido
3. Extração do challenge (WWW-Authenticate)
4. Seleção de credenciais (priority)
5. Cálculo de digest (MD5/SHA-256/SHA-512)
6. Build Authorization header
7. Increment CSeq
8. Retry request com auth
9. Response final processado
```

### Response Handlers (`_response.py`)

#### ResponseCategory

Enum para categorias de resposta.

```python
class ResponseCategory(Enum):
    PROVISIONAL = "1xx"    # 100-199
    SUCCESS = "2xx"        # 200-299
    REDIRECT = "3xx"       # 300-399
    CLIENT_ERROR = "4xx"   # 400-499
    SERVER_ERROR = "5xx"   # 500-599
    GLOBAL_ERROR = "6xx"   # 600-699
```

#### ProvisionalResponseHandler

Handler para respostas 1xx.

```python
class ProvisionalResponseHandler(EventHandler):
    def __init__(
        self,
        on_trying: Optional[Callable] = None,
        on_ringing: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
    ):
        """
        Args:
            on_trying: Callback para 100 Trying
            on_ringing: Callback para 180 Ringing
            on_progress: Callback para 183 Session Progress
        """
```

**Exemplo**:
```python
provisional = ProvisionalResponseHandler(
    on_trying=lambda r, c: print("Trying..."),
    on_ringing=lambda r, c: print("Ringing..."),
    on_progress=lambda r, c: print("Session Progress")
)
client.add_handler(provisional)
```

#### FinalResponseHandler

Handler para respostas finais (2xx-6xx).

```python
class FinalResponseHandler(EventHandler):
    def __init__(
        self,
        on_success: Optional[Callable] = None,
        on_redirect: Optional[Callable] = None,
        on_client_error: Optional[Callable] = None,
        on_server_error: Optional[Callable] = None,
    ):
        """Callbacks para cada categoria de resposta final."""
```

### Flow Handlers

#### InviteFlowHandler (`_invite.py`)

Gerencia fluxo completo de INVITE.

**Estados**:
```python
class InviteFlowState(Enum):
    IDLE = auto()
    CALLING = auto()
    RINGING = auto()
    EARLY_MEDIA = auto()
    ANSWERED = auto()
    CONFIRMED = auto()
    TERMINATED = auto()
```

**Exemplo**:
```python
from sipx._handlers import InviteFlowHandler

def on_ringing(response, context):
    print(f"Phone is ringing! Call-ID: {response.call_id}")

def on_answered(response, context):
    print(f"Call answered! Extracting SDP...")
    sdp = response.content.decode() if response.content else None
    print(f"Remote SDP: {sdp}")

invite_handler = InviteFlowHandler(
    on_ringing=on_ringing,
    on_answered=on_answered,
    on_confirmed=lambda r, c: print("ACK sent, call confirmed")
)

client.add_handler(invite_handler)
response = client.invite("sip:2222@example.com", "example.com")
```

#### RegisterFlowHandler (`_register.py`)

Gerencia fluxo de REGISTER.

**Estados**:
```python
class RegisterFlowState(Enum):
    IDLE = auto()
    REGISTERING = auto()
    REGISTERED = auto()
    UNREGISTERING = auto()
    UNREGISTERED = auto()
    FAILED = auto()
```

**Exemplo**:
```python
from sipx._handlers import RegisterFlowHandler

def on_registered(response, context):
    print("Successfully registered!")
    # Extrair expires
    if "Expires" in response.headers:
        expires = response.headers["Expires"]
        print(f"Registration valid for {expires} seconds")

register_handler = RegisterFlowHandler(
    on_registered=on_registered,
    on_failed=lambda r, c: print(f"Registration failed: {r.status_code}")
)

client.add_handler(register_handler)
```

### State Handlers (`_state.py`)

#### TransactionStateHandler

Rastreia estado de transações conforme RFC 3261.

```python
class TransactionStateHandler(EventHandler):
    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        on_state_change: Optional[Callable] = None
    ):
        """
        Args:
            state_manager: StateManager para usar
            on_state_change: Callback de mudança de estado
        """
```

**Exemplo**:
```python
def on_transaction_change(transaction):
    print(f"Transaction {transaction.id}: {transaction.state}")

tx_handler = TransactionStateHandler(
    state_manager=client.state_manager,
    on_state_change=on_transaction_change
)
client.add_handler(tx_handler)
```

#### DialogStateHandler

Rastreia estado de diálogos.

```python
class DialogStateHandler(EventHandler):
    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        on_state_change: Optional[Callable] = None
    ):
        """Handler para rastreamento de diálogos."""
```

**Exemplo**:
```python
def on_dialog_change(dialog):
    print(f"Dialog {dialog.id}: {dialog.state}")
    if dialog.state == DialogState.CONFIRMED:
        print(f"Dialog confirmed! Route set: {dialog.route_set}")

dialog_handler = DialogStateHandler(
    state_manager=client.state_manager,
    on_state_change=on_dialog_change
)
client.add_handler(dialog_handler)
```

### Composite Handler (`_composite.py`)

#### SipFlowHandler

Handler composto que combina todos os handlers especializados.

```python
class SipFlowHandler(EventHandler):
    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        # INVITE callbacks
        on_ringing: Optional[Callable] = None,
        on_answered: Optional[Callable] = None,
        on_confirmed: Optional[Callable] = None,
        # REGISTER callbacks
        on_registered: Optional[Callable] = None,
        on_unregistered: Optional[Callable] = None,
        # General callbacks
        on_provisional: Optional[Callable] = None,
        on_final: Optional[Callable] = None,
    ):
        """Handler completo que combina todos os sub-handlers."""
```

**Exemplo (All-in-One)**:
```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import SipFlowHandler

client = Client(
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

# Um único handler para tudo
# Adicionar handler de autenticação (necessário para auto-retry)
client.add_handler(AuthenticationHandler(credentials))

# Um handler para tudo
sip_handler = SipFlowHandler(
    state_manager=client.state_manager,
    # INVITE callbacks
    on_ringing=lambda r, c: print("📞 Ringing"),
    on_answered=lambda r, c: print("✅ Answered"),
    on_confirmed=lambda r, c: print("✅ Confirmed"),
    # REGISTER callbacks
    on_registered=lambda r, c: print("✅ Registered"),
)

client.add_handler(sip_handler)

# Usar normalmente
client.register(aor="sip:1111@example.com", registrar="example.com")
client.invite(to_uri="sip:2222@example.com", from_uri="sip:1111@example.com", host="example.com")
```

---

## 📦 Módulo Models

### Localização
`sipx/_models/`

### Message Models (`_message.py`)

#### SIPMessage (Base)

Classe base abstrata para Request e Response.

```python
class SIPMessage(ABC):
    version: str = "SIP/2.0"
    headers: Headers
    content: Optional[bytes]
    
    def to_bytes() -> bytes
    def to_string() -> str
```

#### Request

Representa um request SIP.

```python
class Request(SIPMessage):
    method: str           # INVITE, REGISTER, BYE, etc.
    uri: str             # sip:user@domain
    version: str = "SIP/2.0"
    headers: Headers
    content: Optional[bytes]
```

**Construção**:
```python
request = Request(
    method="INVITE",
    uri="sip:bob@example.com",
    headers={
        "From": "Alice <sip:alice@example.com>;tag=1234",
        "To": "Bob <sip:bob@example.com>",
        "Call-ID": "call123@host",
        "CSeq": "1 INVITE",
        "Via": "SIP/2.0/UDP host:5060;branch=z9hG4bK1234",
    },
    content=sdp_body.encode()
)
```

**Serialização**:
```python
# Para bytes
data = request.to_bytes()

# Para string
text = request.to_string()
```

**Propriedades úteis**:
```python
request.method          # "INVITE"
request.uri            # "sip:bob@example.com"
request.via            # Header Via
request.from_header    # Header From
request.to_header      # Header To
request.call_id        # Header Call-ID
request.cseq           # Header CSeq
request.contact        # Header Contact
```

#### Response

Representa uma response SIP.

```python
class Response(SIPMessage):
    status_code: int              # 100-699
    reason_phrase: str            # OK, Ringing, etc.
    version: str = "SIP/2.0"
    headers: Headers
    content: Optional[bytes]
    request: Optional[Request]    # Request original
    raw: Optional[bytes]          # Bytes originais
    transport_info: Optional[dict]  # Info de transporte
```

**Construção**:
```python
response = Response(
    status_code=200,
    reason_phrase="OK",
    headers={
        "Via": request.via,
        "From": request.from_header,
        "To": request.to_header + ";tag=5678",
        "Call-ID": request.call_id,
        "CSeq": request.cseq,
    }
)
```

**Propriedades úteis**:
```python
response.is_provisional  # True se 1xx
response.is_final       # True se 2xx-6xx
response.is_success     # True se 2xx
response.is_redirect    # True se 3xx
response.is_client_error  # True se 4xx
response.is_server_error  # True se 5xx
```

#### MessageParser

Parser para mensagens SIP.

```python
class MessageParser:
    def parse(self, data: bytes) -> Union[Request, Response]:
        """Parse bytes para Request ou Response."""
```

**Exemplo**:
```python
parser = MessageParser()

# Parse request
data = b"INVITE sip:bob@example.com SIP/2.0\r\n..."
message = parser.parse(data)

if isinstance(message, Request):
    print(f"Method: {message.method}")
elif isinstance(message, Response):
    print(f"Status: {message.status_code}")
```

### Header Models (`_header.py`)

#### Headers

Container de headers SIP com acesso case-insensitive.

```python
class Headers(HeaderContainer):
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        """Inicializa headers."""
    
    def __getitem__(self, key: str) -> str:
        """Acesso case-insensitive."""
    
    def __setitem__(self, key: str, value: str):
        """Define header."""
    
    def __contains__(self, key: str) -> bool:
        """Verifica se header existe."""
    
    def get(self, key: str, default=None) -> Optional[str]:
        """Get com default."""
```

**Exemplo**:
```python
headers = Headers({
    "From": "Alice <sip:alice@example.com>",
    "To": "Bob <sip:bob@example.com>",
    "Call-ID": "abc123",
})

# Case-insensitive
print(headers["from"])        # Alice <sip:alice@example.com>
print(headers["FROM"])        # Alice <sip:alice@example.com>
print(headers["From"])        # Alice <sip:alice@example.com>

# Compact form support
headers["v"] = "SIP/2.0/UDP host:5060"
print(headers["Via"])         # SIP/2.0/UDP host:5060

# Iterar
for name, value in headers.items():
    print(f"{name}: {value}")
```

**Compact Forms Suportados**:
- `v` → `Via`
- `f` → `From`
- `t` → `To`
- `i` → `Call-ID`
- `m` → `Contact`
- `c` → `Content-Type`
- `l` → `Content-Length`

### Body Models (`_body.py`)

#### SDPBody

Session Description Protocol body.

```python
class SDPBody(MessageBody):
    content_type = "application/sdp"
    
    def __init__(self, sdp: str):
        self.sdp = sdp
    
    @property
    def media_info(self) -> Dict[str, Any]:
        """Extrai informações de mídia."""
```

**Exemplo**:
```python
sdp = SDPBody("""v=0
o=- 123456 123456 IN IP4 192.168.1.100
s=Call
c=IN IP4 192.168.1.100
t=0 0
m=audio 10000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
""")

info = sdp.media_info
print(f"Media type: {info['media_type']}")
print(f"Port: {info['port']}")
print(f"Codecs: {info['codecs']}")
```

#### XMLBody

Body XML genérico.

```python
class XMLBody(MessageBody):
    content_type = "application/xml"
    
    def __init__(self, xml: str):
        self.xml = xml
    
    @property
    def root(self) -> ElementTree.Element:
        """Retorna root element."""
```

#### TextBody

Plain text body.

```python
class TextBody(MessageBody):
    content_type = "text/plain"
    
    def __init__(self, text: str, encoding: str = "utf-8"):
        self.text = text
        self.encoding = encoding
```

#### MultipartBody

Body com múltiplas partes MIME.

```python
class MultipartBody(MessageBody):
    content_type = "multipart/mixed"
    
    def __init__(self, parts: List[MessageBody], boundary: Optional[str] = None):
        self.parts = parts
        self.boundary = boundary or self._generate_boundary()
```

**Exemplo**:
```python
multipart = MultipartBody([
    TextBody("Message text"),
    SDPBody(sdp_content),
])

request = Request(
    method="MESSAGE",
    uri="sip:bob@example.com",
    content=multipart.to_bytes()
)
```

### Authentication Models (`_auth.py`)

#### SipAuthCredentials

Credenciais simplificadas para autenticação.

```python
@dataclass
class SipAuthCredentials:
    username: str
    password: str
    realm: Optional[str] = None
```

**Exemplo**:
```python
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx",
    realm="example.com"  # Opcional
)
```

#### DigestAuth

Implementação completa de digest authentication (RFC 2617).

```python
class DigestAuth:
    def __init__(
        self,
        credentials: DigestCredentials,
        challenge: DigestChallenge
    ):
        """
        Args:
            credentials: Username/password
            challenge: Challenge do servidor (401/407)
        """
    
    def build_authorization(
        self,
        method: str,
        uri: str,
        entity_body: Optional[bytes] = None
    ) -> str:
        """Gera Authorization header."""
```

**Algoritmos Suportados**:
- MD5
- MD5-sess
- SHA-256
- SHA-256-sess
- SHA-512
- SHA-512-sess

**QoP Suportados**:
- `auth`: Autenticação apenas
- `auth-int`: Autenticação + integridade do body

**Exemplo**:
```python
# Parse challenge
parser = AuthParser()
challenge = parser.parse_from_headers(response.headers)

# Create credentials
credentials = DigestCredentials(
    username="1111",
    password="1111xxx"
)

# Build auth
digest_auth = DigestAuth(credentials, challenge)
auth_header = digest_auth.build_authorization(
    method="INVITE",
    uri="sip:bob@example.com"
)

# Add to request
request.headers["Authorization"] = auth_header
```

---

## 🚀 Módulo Transports

### Localização
`sipx/_transports/`

### BaseTransport (`_base.py`)

Interface abstrata para todos os transports.

```python
class BaseTransport(ABC):
    config: TransportConfig
    
    @abstractmethod
    def send(self, data: bytes, destination: TransportAddress):
        """Envia dados."""
    
    @abstractmethod
    def receive(self, timeout: float) -> Tuple[bytes, TransportAddress]:
        """Recebe dados."""
    
    @abstractmethod
    def close(self):
        """Fecha transport."""
    
    @property
    @abstractmethod
    def local_address(self) -> TransportAddress:
        """Retorna endereço local."""
```

### UDPTransport (`_udp.py`)

Transport UDP (connectionless).

**Características**:
- Connectionless
- Não confiável
- Sem handshake
- Baixa latência
- Max message size: 65535 bytes

**Exemplo**:
```python
from sipx._transports import UDPTransport
from sipx import TransportConfig, TransportAddress

config = TransportConfig(
    local_host="0.0.0.0",
    local_port=5060,
    read_timeout=32.0
)

transport = UDPTransport(config)

# Enviar
destination = TransportAddress("example.com", 5060, "UDP")
transport.send(request_data, destination)

# Receber
data, source = transport.receive(timeout=10.0)

# Fechar
transport.close()
```

### TCPTransport (`_tcp.py`)

Transport TCP (connection-oriented).

**Características**:
- Connection-oriented
- Confiável
- Handshake (SYN/SYN-ACK/ACK)
- Reordenação de pacotes
- Keep-alive opcional

**Exemplo**:
```python
from sipx._transports import TCPTransport

config = TransportConfig(
    local_host="0.0.0.0",
    local_port=5060,
    connect_timeout=5.0,
    enable_keepalive=True,
    keepalive_interval=30.0
)

transport = TCPTransport(config)
```

### TLSTransport (`_tls.py`)

Transport TLS (secure).

**Características**:
- Baseado em TCP
- Criptografia SSL/TLS
- Verificação de certificados
- SNI support
- Client certificates

**Exemplo**:
```python
from sipx._transports import TLSTransport

config = TransportConfig(
    local_host="0.0.0.0",
    local_port=5061,
    verify_mode=True,
    ca_certs="/path/to/ca-bundle.crt",
    certfile="/path/to/client.crt",  # Opcional
    keyfile="/path/to/client.key",   # Opcional
)

transport = TLSTransport(config)
```

### TransportConfig

Configuração de transporte.

```python
@dataclass
class TransportConfig:
    # Network
    local_host: str = "0.0.0.0"
    local_port: int = 5060
    
    # Timeouts
    connect_timeout: float = 5.0
    read_timeout: float = 32.0    # Timer B (RFC 3261)
    write_timeout: float = 5.0
    
    # Buffer
    buffer_size: int = 65535
    
    # Retry
    max_retries: int = 0
    retry_backoff_factor: float = 0.5
    
    # TLS
    verify_mode: bool = True
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    ca_certs: Optional[str] = None
    
    # Keep-alive
    enable_keepalive: bool = False
    keepalive_interval: float = 30.0
    
    # Extra
    extra: dict = field(default_factory=dict)
```

---

## 🔄 Módulo FSM

### Localização
`sipx/_fsm.py`

### StateManager

Gerenciador de máquinas de estado para transações e diálogos.

```python
class StateManager:
    def __init__(self):
        self._transactions: Dict[str, Transaction] = {}
        self._dialogs: Dict[str, Dialog] = {}
        self._transaction_handlers: Dict[TransactionState, List[Callable]] = {}
        self._dialog_handlers: Dict[DialogState, List[Callable]] = {}
```

**Gerenciamento de Transações**:

```python
# Criar transação
transaction = state_manager.create_transaction(
    request=request,
    transaction_type=TransactionType.INVITE
)

# Buscar transação
tx = state_manager.get_transaction(transaction_id)

# Atualizar transação
state_manager.update_transaction(
    transaction_id,
    state=TransactionState.PROCEEDING,
    response=response
)

# Limpar transações terminadas
state_manager.cleanup_transactions()
```

**Gerenciamento de Diálogos**:

```python
# Criar diálogo
dialog = state_manager.create_dialog(
    call_id=call_id,
    local_tag=local_tag,
    remote_tag=remote_tag,
    local_uri=local_uri,
    remote_uri=remote_uri
)

# Buscar diálogo
dlg = state_manager.get_dialog(dialog_id)

# Atualizar diálogo
state_manager.update_dialog(
    dialog_id,
    state=DialogState.CONFIRMED
)
```

**Callbacks de Estado**:

```python
# Callback de transação
def on_transaction_completed(transaction):
    print(f"Transaction {transaction.id} completed")
    final_response = transaction.get_final_response()
    print(f"Final response: {final_response.status_code}")

state_manager.on_transaction_state(
    TransactionState.COMPLETED,
    on_transaction_completed
)

# Callback de diálogo
def on_dialog_confirmed(dialog):
    print(f"Dialog {dialog.id} confirmed")
    print(f"Route set: {dialog.route_set}")

state_manager.on_dialog_state(
    DialogState.CONFIRMED,
    on_dialog_confirmed
)
```

**Estatísticas**:

```python
stats = state_manager.get_statistics()
print(f"Active transactions: {stats['active_transactions']}")
print(f"Completed transactions: {stats['completed_transactions']}")
print(f"Active dialogs: {stats['active_dialogs']}")
print(f"Confirmed dialogs: {stats['confirmed_dialogs']}")
```

### Transaction

Representa uma transação SIP.

```python
class Transaction:
    id: str
    request: Request
    type: TransactionType
    state: TransactionState
    responses: List[Response]
    created_at: datetime
    updated_at: datetime
```

**Métodos**:
```python
# Transição de estado
transaction.transition_to(TransactionState.PROCEEDING)

# Adicionar response
transaction.add_response(response)

# Verificar se completa
if transaction.is_complete():
    final = transaction.get_final_response()

# Verificar se terminada
if transaction.is_terminated():
    cleanup(transaction)
```

### Dialog

Representa um diálogo SIP.

```python
class Dialog:
    id: str
    call_id: str
    local_tag: str
    remote_tag: str
    local_uri: str
    remote_uri: str
    local_seq: int
    remote_seq: int
    state: DialogState
    route_set: List[str]
    secure: bool
```

**Métodos**:
```python
# Transição de estado
dialog.transition_to(DialogState.CONFIRMED)

# Incrementar CSeq local
dialog.increment_local_seq()

# Atualizar CSeq remoto
dialog.update_remote_seq(remote_seq)

# Verificar estado
if dialog.is_confirmed():
    send_bye(dialog)
```

---

## ✨ Funcionalidades Implementadas

### ✅ Métodos SIP Completos

- ✅ **REGISTER**: Registro com autenticação digest
- ✅ **INVITE**: Chamadas com SDP
- ✅ **ACK**: Confirmação de INVITE
- ✅ **BYE**: Término de chamada
- ✅ **CANCEL**: Cancelamento de INVITE
- ✅ **OPTIONS**: Verificação de capacidades
- ✅ **MESSAGE**: Mensagens instantâneas
- ✅ **SUBSCRIBE**: Subscrição a eventos
- ✅ **NOTIFY**: Notificação de eventos
- ✅ **REFER**: Transferência de chamadas
- ✅ **INFO**: Informações mid-dialog
- ✅ **UPDATE**: Atualização de sessão
- ✅ **PRACK**: Confirmação de provisional
- ✅ **PUBLISH**: Publicação de estado

### ✅ Autenticação

- ✅ Digest Authentication (RFC 2617)
- ✅ Algoritmos: MD5, SHA-256, SHA-512
- ✅ QoP: auth, auth-int
- ✅ Auto-retry com auth
- ✅ Prioridade de credenciais (method > client > handler)

### ✅ Transporte

- ✅ UDP (connectionless)
- ✅ TCP (connection-oriented)
- ✅ TLS (secure)
- ✅ Keep-alive para TCP/TLS
- ✅ Retry automático
- ✅ Timeouts configuráveis

### ✅ Estado

- ✅ Transaction State Machine (RFC 3261)
- ✅ Dialog State Machine
- ✅ Transaction tracking
- ✅ Dialog tracking
- ✅ CSeq management
- ✅ Route set extraction

### ✅ Handlers

- ✅ Chain of Responsibility
- ✅ Authentication handler
- ✅ INVITE flow handler
- ✅ REGISTER flow handler
- ✅ Transaction state handler
- ✅ Dialog state handler
- ✅ Logging handler
- ✅ Retry handler
- ✅ Timeout handler
- ✅ Header injection handler

### ✅ Parsing

- ✅ Request parsing
- ✅ Response parsing
- ✅ Header parsing (case-insensitive)
- ✅ Compact form support
- ✅ SDP parsing
- ✅ XML parsing
- ✅ Multipart parsing
- ✅ Auth challenge parsing

### ⏳ Em Desenvolvimento

- ⏳ Auto re-registration
- ⏳ PRACK completo (RFC 3262)
- ⏳ Forking support completo
- ⏳ WebSocket transport
- ⏳ IPv6 support
- ⏳ Retransmission timers (Timer A/B/D/F)

---

## 💡 Exemplos de Uso

### Exemplo 1: Registro Básico

```python
from sipx import Client, SipAuthCredentials

# Criar cliente
client = Client(
    local_host="192.168.1.100",
    local_port=5060,
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

# Registrar
response = client.register(
    aor=f"sip:1111@example.com",
    registrar="example.com",
    port=5060,
    expires=3600
)

if response.status_code == 200:
    print("Registered successfully!")
    print(f"Expires: {response.headers.get('Expires', 'N/A')}")
else:
    print(f"Registration failed: {response.status_code}")

client.close()
```

### Exemplo 2: Chamada Completa (INVITE)

```python
from sipx import Client, SipAuthCredentials

# SDP offer
sdp = """v=0
o=- 123456 123456 IN IP4 192.168.1.100
s=Call
c=IN IP4 192.168.1.100
t=0 0
m=audio 10000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
"""

client = Client(
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

# Fazer chamada
response = client.invite(
    uri="sip:2222@example.com",
    host="example.com",
    sdp=sdp
)

if response.status_code == 200:
    print("Call answered!")
    
    # Extrair SDP answer
    remote_sdp = response.content.decode() if response.content else None
    print(f"Remote SDP: {remote_sdp}")
    
    # Aguardar 10 segundos
    import time
    time.sleep(10)
    
    # Desligar
    bye_response = client.bye()
    print(f"Call ended: {bye_response.status_code}")

client.close()
```

### Exemplo 3: Com Handlers

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import (
    AuthenticationHandler,
    InviteFlowHandler,
    RegisterFlowHandler
)

def on_ringing(response, context):
    print(f"📞 Phone is ringing! Call-ID: {response.call_id}")

def on_answered(response, context):
    print(f"✅ Call answered!")

def on_registered(response, context):
    print(f"✅ Registered! Expires: {response.headers.get('Expires')}")

# Criar credenciais
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx"
)

# Criar cliente
client = Client()

# Adicionar handlers
# 1. Autenticação (OBRIGATÓRIO para auto-retry)
client.add_handler(AuthenticationHandler(credentials))

# 2. Flow handlers
client.add_handler(InviteFlowHandler(
    on_ringing=on_ringing,
    on_answered=on_answered
))
client.add_handler(RegisterFlowHandler(
    on_registered=on_registered
))

# Usar normalmente
client.register(aor="sip:1111@example.com", registrar="example.com")
client.invite(
    to_uri="sip:2222@example.com",
    from_uri="sip:1111@example.com",
    host="example.com"
)
```

### Exemplo 4: Servidor Customizado

```python
from sipx import SIPServer, Request, Response

def handle_message(request: Request, source) -> Response:
    """Handler para MESSAGE."""
    print(f"📨 Message from {source.host}:{source.port}")
    
    # Extrair conteúdo
    content = request.content.decode() if request.content else ""
    print(f"Content: {content}")
    
    # Responder 200 OK
    return Response(
        status_code=200,
        reason_phrase="OK",
        headers={
            "Via": request.via,
            "From": request.from_header,
            "To": request.to_header,
            "Call-ID": request.call_id,
            "CSeq": request.cseq,
            "Content-Length": "0",
        }
    )

# Criar servidor
server = SIPServer(
    local_host="0.0.0.0",
    local_port=5060
)

# Registrar handler customizado
server.register_handler("MESSAGE", handle_message)

# Iniciar
server.start()

# Aguardar...
import time
time.sleep(60)

# Parar
server.stop()
```

---

## 📚 Referências

- [RFC 3261 - SIP](https://datatracker.ietf.org/doc/html/rfc3261)
- [RFC 2617 - Digest Authentication](https://datatracker.ietf.org/doc/html/rfc2617)
- [RFC 4566 - SDP](https://datatracker.ietf.org/doc/html/rfc4566)
- [RFC 3262 - PRACK](https://datatracker.ietf.org/doc/html/rfc3262)