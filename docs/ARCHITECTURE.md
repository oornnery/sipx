# SIPX - Arquitetura do Sistema

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura em Camadas](#arquitetura-em-camadas)
3. [Componentes Principais](#componentes-principais)
4. [Fluxo de Dados](#fluxo-de-dados)
5. [Padrões de Design](#padrões-de-design)
6. [Diagramas](#diagramas)

---

## 🎯 Visão Geral

SIPX é uma biblioteca Python moderna e assíncrona para o protocolo SIP (Session Initiation Protocol - RFC 3261). A arquitetura foi projetada seguindo princípios SOLID, com separação clara de responsabilidades e alta modularidade.

### Características Principais

- **Modular**: Sistema de handlers baseado em Chain of Responsibility
- **Extensível**: Fácil adição de novos handlers e transports
- **Type-Safe**: Tipagem completa com suporte a type hints
- **Async-First**: Suporte nativo a async/await
- **Testável**: Componentes desacoplados e injetáveis

### Tecnologias Core

- **Python 3.12+**: Recursos modernos da linguagem
- **asyncio**: Para operações assíncronas
- **Rich**: Interface de console elegante
- **dataclasses**: Modelagem de dados imutáveis

---

## 🏗️ Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                      │
│              (Client API / Server API)                   │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    HANDLER LAYER                         │
│   (Authentication, Flow Control, State Management)       │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    MESSAGE LAYER                         │
│         (Parsing, Serialization, Validation)             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                   TRANSPORT LAYER                        │
│              (UDP, TCP, TLS, WebSocket)                  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    NETWORK LAYER                         │
│                  (Socket, asyncio)                       │
└─────────────────────────────────────────────────────────┘
```

### 1. Application Layer

**Responsabilidade**: Interface pública da biblioteca

**Componentes**:
- `Client`: Cliente SIP síncrono
- `AsyncClient`: Cliente SIP assíncrono
- `SIPServer`: Servidor SIP síncrono
- `AsyncSIPServer`: Servidor SIP assíncrono

**Funcionalidades**:
- API de alto nível para métodos SIP (INVITE, REGISTER, BYE, etc.)
- Gerenciamento de sessão
- Configuração de transporte

### 2. Handler Layer

**Responsabilidade**: Processamento de eventos e lógica de negócio

**Componentes**:
- **Base Handlers**: `EventHandler`, `HandlerChain`
- **Utility Handlers**: `LoggingHandler`, `RetryHandler`, `TimeoutHandler`
- **Auth Handlers**: `AuthenticationHandler`
- **Flow Handlers**: `InviteFlowHandler`, `RegisterFlowHandler`
- **State Handlers**: `TransactionStateHandler`, `DialogStateHandler`

**Funcionalidades**:
- Chain of Responsibility pattern
- Autenticação digest automática
- Rastreamento de transações e diálogos
- Retry automático com backoff
- Logging estruturado

### 3. Message Layer

**Responsabilidade**: Representação e manipulação de mensagens SIP

**Componentes**:
- **Message Models**: `Request`, `Response`, `SIPMessage`
- **Header Models**: `Headers`, `HeaderContainer`
- **Body Models**: `SDPBody`, `XMLBody`, `MultipartBody`
- **Auth Models**: `DigestAuth`, `Challenge`, `Credentials`
- **Parsers**: `MessageParser`, `HeaderParser`, `BodyParser`, `AuthParser`

**Funcionalidades**:
- Parsing completo de mensagens SIP
- Serialização para bytes
- Validação de campos obrigatórios
- Suporte a múltiplos tipos de body (SDP, XML, texto, etc.)

### 4. Transport Layer

**Responsabilidade**: Transmissão de dados pela rede

**Componentes**:
- `BaseTransport`: Classe base abstrata
- `UDPTransport`: Transport connectionless
- `TCPTransport`: Transport orientado a conexão
- `TLSTransport`: Transport seguro

**Funcionalidades**:
- Abstração de protocolo de transporte
- Timeouts configuráveis
- Keep-alive para conexões TCP/TLS
- Retry automático
- Buffer de recebimento

### 5. Network Layer

**Responsabilidade**: Operações de rede de baixo nível

**Componentes**:
- `socket`: Sockets Python padrão
- `asyncio`: Event loop e operações assíncronas

---

## 🔧 Componentes Principais

### Client (_client.py)

Cliente SIP principal que orquestra todas as operações.

```python
class Client:
    """Cliente SIP síncrono."""
    
    # Gerenciamento de estado
    state_manager: StateManager
    
    # Handlers
    handlers: HandlerChain
    _auth_handler: AuthenticationHandler
    
    # Transport
    _transport: BaseTransport
    
    # Métodos SIP
    def register() -> Response
    def invite() -> Response
    def bye() -> Response
    def message() -> Response
    def options() -> Response
```

**Responsabilidades**:
- Construir requests SIP
- Gerenciar transporte
- Coordenar handlers
- Processar responses
- Manter estado de transações/diálogos

### StateManager (_fsm.py)

Gerencia máquinas de estado para transações e diálogos SIP.

```python
class StateManager:
    """Gerenciador de estado FSM (Finite State Machine)."""
    
    # Armazena transações ativas
    _transactions: Dict[str, Transaction]
    
    # Armazena diálogos ativos
    _dialogs: Dict[str, Dialog]
    
    # Callbacks de estado
    _transaction_handlers: List[Callable]
    _dialog_handlers: List[Callable]
```

**Estados de Transação** (RFC 3261):
- `CALLING`: Request enviado (INVITE)
- `TRYING`: Request enviado (não-INVITE)
- `PROCEEDING`: Response 1xx recebido
- `COMPLETED`: Response final recebido
- `CONFIRMED`: ACK enviado (apenas INVITE)
- `TERMINATED`: Transação finalizada

**Estados de Diálogo**:
- `EARLY`: Diálogo criado por 1xx com To tag
- `CONFIRMED`: Diálogo confirmado por 2xx
- `TERMINATED`: Diálogo terminado

### Handler System (_handlers/)

Sistema modular de processamento de eventos baseado em Chain of Responsibility.

#### Hierarquia de Handlers

```
EventHandler (base abstrata)
├── LoggingHandler (utility)
├── RetryHandler (utility)
├── TimeoutHandler (utility)
├── HeaderInjectionHandler (utility)
├── AuthenticationHandler (auth)
├── ProvisionalResponseHandler (response)
├── FinalResponseHandler (response)
├── InviteFlowHandler (flow)
├── RegisterFlowHandler (flow)
├── TransactionStateHandler (state)
├── DialogStateHandler (state)
└── SipFlowHandler (composite - combina todos)
```

#### Base Classes

**EventHandler**:
```python
class EventHandler(ABC):
    def on_request(request, context) -> Request
    def on_response(response, context) -> Response
    def on_error(error, context) -> None
```

**EventContext**:
```python
@dataclass
class EventContext:
    request: Optional[Request]
    response: Optional[Response]
    destination: Optional[TransportAddress]
    transaction_id: Optional[str]
    dialog_id: Optional[str]
    metadata: dict  # Comunicação entre handlers
```

#### Utility Handlers

**LoggingHandler**: Logging estruturado de mensagens
- Logs detalhados de requests/responses
- Formatação colorida com Rich
- Níveis de log configuráveis

**RetryHandler**: Retry automático com backoff
- Retry exponencial configurável
- Filtro por tipo de erro
- Max attempts configurável

**TimeoutHandler**: Controle de timeouts
- Timeout por transação
- Timeout global
- Callbacks de timeout

**HeaderInjectionHandler**: Injeção de headers customizados
- Headers dinâmicos
- Sobrescrita de headers existentes

#### Authentication Handler

**AuthenticationHandler**: Autenticação digest automática

**Prioridade de Credenciais**:
1. **Method-level**: Passadas no método (`invite(auth=...)`)
2. **Client-level**: Passadas no construtor (`Client(credentials=...)`)
3. **Handler-level**: Handler legado (backwards compatibility)

**Fluxo de Autenticação**:
```
1. Request enviado → 401/407 recebido
2. Parse do challenge (WWW-Authenticate)
3. Seleção de credenciais (priority)
4. Build do Authorization header (digest)
5. Increment CSeq
6. Retry do request com auth
7. Response final retornado
```

#### Flow Handlers

**InviteFlowHandler**: Gerencia fluxo de INVITE

**Estados**:
- `IDLE`: Estado inicial
- `CALLING`: INVITE enviado
- `RINGING`: 180 Ringing recebido
- `EARLY_MEDIA`: 183 Session Progress recebido
- `ANSWERED`: 200 OK recebido
- `CONFIRMED`: ACK enviado
- `TERMINATED`: Chamada finalizada

**Callbacks**:
- `on_ringing`: Chamado ao receber 180
- `on_early_media`: Chamado ao receber 183
- `on_answered`: Chamado ao receber 200 OK
- `on_confirmed`: Chamado após enviar ACK

**RegisterFlowHandler**: Gerencia fluxo de REGISTER

**Estados**:
- `IDLE`: Estado inicial
- `REGISTERING`: REGISTER enviado
- `REGISTERED`: 200 OK recebido
- `UNREGISTERING`: REGISTER com Expires=0 enviado
- `UNREGISTERED`: Unregister confirmado
- `FAILED`: Falha no registro

**Callbacks**:
- `on_registered`: Chamado ao receber 200 OK
- `on_unregistered`: Chamado ao confirmar unregister
- `on_failed`: Chamado em caso de falha

#### State Handlers

**TransactionStateHandler**: Rastreia estado de transações
- Cria transações automaticamente
- Atualiza estados conforme RFC 3261
- Limpa transações finalizadas
- Callbacks de mudança de estado

**DialogStateHandler**: Rastreia estado de diálogos
- Cria diálogos em 1xx com To tag
- Confirma diálogos em 2xx
- Gerencia CSeq local e remoto
- Extrai Route Set
- Callbacks de mudança de estado

#### Composite Handler

**SipFlowHandler**: Handler completo que combina:
- Transaction tracking
- Dialog tracking
- Provisional response handling
- Final response handling
- INVITE flow management
- REGISTER flow management

### Message Models (_models/)

#### Request & Response

**Request**:
```python
class Request(SIPMessage):
    method: str          # INVITE, REGISTER, etc.
    uri: str            # sip:user@domain
    version: str        # SIP/2.0
    headers: Headers
    content: Optional[bytes]
```

**Response**:
```python
class Response(SIPMessage):
    status_code: int           # 100-699
    reason_phrase: str         # OK, Ringing, etc.
    version: str              # SIP/2.0
    headers: Headers
    content: Optional[bytes]
    request: Optional[Request] # Request original
```

#### Headers

**Headers**: Container inteligente de headers SIP
- Case-insensitive access
- Compact form support (v = Via, f = From, etc.)
- Header parsing e serialização
- Validação de headers obrigatórios

#### Body Types

- **SDPBody**: Session Description Protocol
- **XMLBody**: Conteúdo XML genérico
- **PIDFBody**: Presence Information Data Format
- **DialogInfoBody**: Dialog state information
- **ConferenceInfoBody**: Conference state
- **MultipartBody**: Múltiplas partes MIME
- **TextBody**: Plain text
- **HTMLBody**: HTML content

#### Authentication

**DigestAuth**: Implementa RFC 2617
- Algoritmos: MD5, MD5-sess, SHA-256, SHA-512
- QoP: auth, auth-int
- Nonce, opaque, realm
- HA1/HA2 calculation
- Response hash generation

**Challenge**:
```python
class Challenge:
    realm: str
    nonce: str
    algorithm: str = "MD5"
    qop: Optional[str] = None
    opaque: Optional[str] = None
```

**Credentials**:
```python
class SipAuthCredentials:
    username: str
    password: str
    realm: Optional[str] = None
```

### Transport Layer (_transports/)

#### BaseTransport

Interface abstrata para todos os transports:

```python
class BaseTransport(ABC):
    config: TransportConfig
    
    @abstractmethod
    def send(data: bytes, destination: TransportAddress)
    
    @abstractmethod
    def receive(timeout: float) -> Tuple[bytes, TransportAddress]
    
    @abstractmethod
    def close()
    
    @property
    def local_address() -> TransportAddress
```

#### UDPTransport

- Connectionless
- Não confiável
- Baixa latência
- MTU: 65535 bytes
- Sem handshake

#### TCPTransport

- Connection-oriented
- Confiável
- Reordenação de pacotes
- Keep-alive opcional
- Handshake (SYN, SYN-ACK, ACK)

#### TLSTransport

- Baseado em TCP
- Criptografia SSL/TLS
- Verificação de certificados
- SNI (Server Name Indication)
- Suporta client certificates

---

## 🔄 Fluxo de Dados

### Fluxo de REGISTER

```
┌──────────┐                                    ┌──────────┐
│  Client  │                                    │  Server  │
└────┬─────┘                                    └────┬─────┘
     │                                               │
     │  1. REGISTER                                  │
     │──────────────────────────────────────────────>│
     │                                               │
     │  2. 401 Unauthorized (Challenge)              │
     │<──────────────────────────────────────────────│
     │                                               │
     │  3. REGISTER (com Authorization)              │
     │──────────────────────────────────────────────>│
     │                                               │
     │  4. 200 OK                                    │
     │<──────────────────────────────────────────────│
     │                                               │
```

**Processamento Interno (com Handlers)**:

```
Client.register()
    ↓
1. Build Request
    ↓
2. Create Transaction (StateManager)
    ↓
3. Create EventContext
    ↓
4. HandlerChain.on_request()
    ├── LoggingHandler.on_request()
    ├── HeaderInjectionHandler.on_request()
    └── RegisterFlowHandler.on_request()
    ↓
5. Transport.send()
    ↓
6. Transport.receive()
    ↓
7. Parse Response (401)
    ↓
8. HandlerChain.on_response()
    ├── AuthenticationHandler.on_response()
    │   ├── Detect 401
    │   ├── Extract challenge
    │   ├── Select credentials
    │   ├── Build Authorization header
    │   ├── Increment CSeq
    │   └── Retry request → 200 OK
    ├── RegisterFlowHandler.on_response()
    │   └── Trigger on_registered callback
    └── TransactionStateHandler.on_response()
        └── Update state to COMPLETED
    ↓
9. Return final Response (200 OK)
```

### Fluxo de INVITE

```
┌──────────┐                                    ┌──────────┐
│  Client  │                                    │  Server  │
└────┬─────┘                                    └────┬─────┘
     │                                               │
     │  1. INVITE (com SDP)                          │
     │──────────────────────────────────────────────>│
     │                                               │
     │  2. 100 Trying                                │
     │<──────────────────────────────────────────────│
     │                                               │
     │  3. 180 Ringing                               │
     │<──────────────────────────────────────────────│
     │                                               │
     │  4. 200 OK (com SDP)                          │
     │<──────────────────────────────────────────────│
     │                                               │
     │  5. ACK                                       │
     │──────────────────────────────────────────────>│
     │                                               │
     │  [RTP Media Session]                          │
     │<═════════════════════════════════════════════>│
     │                                               │
     │  6. BYE                                       │
     │──────────────────────────────────────────────>│
     │                                               │
     │  7. 200 OK                                    │
     │<──────────────────────────────────────────────│
     │                                               │
```

**Processamento com Handlers**:

```
Client.invite()
    ↓
1. Build INVITE with SDP
    ↓
2. Create INVITE Transaction
    ↓
3. HandlerChain.on_request()
    ├── LoggingHandler (log INVITE)
    └── InviteFlowHandler (state → CALLING)
    ↓
4. Send INVITE
    ↓
5. Receive 100 Trying
    ↓
6. HandlerChain.on_response()
    ├── ProvisionalResponseHandler
    ├── InviteFlowHandler (state → PROCEEDING)
    └── TransactionStateHandler (state → PROCEEDING)
    ↓
7. Receive 180 Ringing
    ↓
8. HandlerChain.on_response()
    ├── InviteFlowHandler (state → RINGING)
    │   └── Trigger on_ringing callback
    └── DialogStateHandler (create early dialog)
    ↓
9. Receive 200 OK
    ↓
10. HandlerChain.on_response()
    ├── FinalResponseHandler
    ├── InviteFlowHandler (state → ANSWERED)
    │   └── Trigger on_answered callback
    ├── DialogStateHandler (confirm dialog)
    └── TransactionStateHandler (state → COMPLETED)
    ↓
11. Send ACK
    ↓
12. InviteFlowHandler (state → CONFIRMED)
    └── Trigger on_confirmed callback
    ↓
13. Return 200 OK Response
```

---

## 🎨 Padrões de Design

### 1. Chain of Responsibility

**Uso**: Sistema de handlers

**Vantagens**:
- Handlers desacoplados
- Fácil adição/remoção de handlers
- Ordem de execução clara
- Handlers reutilizáveis

**Exemplo**:
```python
client = Client()
client.add_handler(LoggingHandler())
client.add_handler(AuthenticationHandler(credentials))
client.add_handler(InviteFlowHandler(on_ringing=lambda r, c: print("Ring!")))
```

### 2. Strategy Pattern

**Uso**: Transports intercambiáveis

**Vantagens**:
- Seleção de transporte em runtime
- Implementações específicas encapsuladas
- Fácil adicionar novos transports

**Exemplo**:
```python
# UDP
client = Client(transport="UDP")

# TCP
client = Client(transport="TCP")

# TLS
client = Client(transport="TLS")
```

### 3. State Pattern

**Uso**: Máquinas de estado (FSM)

**Vantagens**:
- Estados explícitos
- Transições controladas
- Validação de transições
- Callbacks de mudança de estado

**Exemplo**:
```python
transaction = state_manager.create_transaction(request)
# Estado inicial: CALLING

response_1xx = receive_response()
transaction.transition_to(TransactionState.PROCEEDING)

response_2xx = receive_response()
transaction.transition_to(TransactionState.COMPLETED)
```

### 4. Factory Pattern

**Uso**: Criação de transports

**Vantagens**:
- Lógica de criação centralizada
- Facilita testes (mock factories)
- Configuração simplificada

**Exemplo**:
```python
def _create_transport(self):
    if self.transport_protocol == "UDP":
        return UDPTransport(self.config)
    elif self.transport_protocol == "TCP":
        return TCPTransport(self.config)
    elif self.transport_protocol == "TLS":
        return TLSTransport(self.config)
```

### 5. Builder Pattern

**Uso**: Construção de mensagens SIP

**Vantagens**:
- Construção passo a passo
- Validação incremental
- Headers ordenados corretamente

**Exemplo**:
```python
request = Request(
    method="INVITE",
    uri="sip:bob@example.com",
)
request = self._ensure_required_headers(request, host, port)
request.add_header("Contact", contact_uri)
request.add_authorization(credentials, challenge)
```

### 6. Observer Pattern

**Uso**: Callbacks de estado

**Vantagens**:
- Desacoplamento de eventos
- Múltiplos observers
- Notificações automáticas

**Exemplo**:
```python
state_manager.on_transaction_state(
    TransactionState.COMPLETED,
    lambda t: print(f"Transaction {t.id} completed")
)

state_manager.on_dialog_state(
    DialogState.CONFIRMED,
    lambda d: print(f"Dialog {d.id} confirmed")
)
```

### 7. Singleton Pattern (implícito)

**Uso**: Logger, Console (Rich)

**Vantagens**:
- Instância única compartilhada
- Configuração centralizada
- Reduz overhead

**Exemplo**:
```python
# _utils.py
from rich.console import Console
console = Console()  # Singleton implícito
```

---

## 📊 Diagramas

### Diagrama de Classes Simplificado

```
┌─────────────────┐
│     Client      │
├─────────────────┤
│ + register()    │
│ + invite()      │
│ + bye()         │
│ + message()     │
└────────┬────────┘
         │ owns
         ├──────────────┬───────────────┬──────────────┐
         │              │               │              │
┌────────▼────────┐ ┌──▼───────┐ ┌────▼──────┐ ┌─────▼─────────┐
│  HandlerChain   │ │Transport │ │StateManager│ │ AuthHandler   │
├─────────────────┤ ├──────────┤ ├───────────┤ ├───────────────┤
│+ on_request()   │ │+ send()  │ │+ create() │ │+ credentials  │
│+ on_response()  │ │+ receive()│ │+ get()    │ │+ challenge    │
│+ on_error()     │ │+ close() │ │+ update() │ └───────────────┘
└────────┬────────┘ └──────────┘ └───────────┘
         │ contains
    ┌────▼────────────────────────────┐
    │        EventHandler             │
    │  (abstract base class)          │
    ├─────────────────────────────────┤
    │+ on_request(req, ctx) -> req    │
    │+ on_response(res, ctx) -> res   │
    │+ on_error(err, ctx)             │
    └─────────────────────────────────┘
                     △
                     │ extends
        ┌────────────┼────────────┬──────────────┐
        │            │            │              │
┌───────▼──────┐ ┌──▼─────────┐ ┌▼──────────┐ ┌─▼────────────┐
│LoggingHandler│ │InviteFlow  │ │Transaction│ │DialogState   │
│              │ │Handler     │ │StateHandler│ │Handler       │
└──────────────┘ └────────────┘ └───────────┘ └──────────────┘
```

### Diagrama de Sequência - INVITE com Auth

```
Client          HandlerChain    AuthHandler     Transport       Server
  │                  │              │               │              │
  │──invite()────────>│              │               │              │
  │                  │──on_request()─>│               │              │
  │                  │<──request─────│               │              │
  │                  │──────────────────send()──────>│──INVITE────>│
  │                  │                               │<─401────────│
  │                  │<──────────────receive()──────│              │
  │                  │──on_response()─>│             │              │
  │                  │                 │──detect_401()              │
  │                  │                 │──select_creds()            │
  │                  │                 │──build_auth()              │
  │                  │                 │───send()───────>│──INVITE─>│
  │                  │                 │                 │  +Auth   │
  │                  │                 │<──receive()────│<─200 OK──│
  │                  │<──response─────│                 │          │
  │<─200 OK─────────│                                   │          │
  │                                                      │          │
```

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      SIPX Library                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              sipx (package root)                   │     │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────────┐ │     │
│  │  │ __init__ │  │  Client   │  │  AsyncClient   │ │     │
│  │  └──────────┘  └───────────┘  └────────────────┘ │     │
│  │  ┌──────────┐  ┌───────────┐                      │     │
│  │  │ SIPServer│  │StateManager                      │     │
│  │  └──────────┘  └───────────┘                      │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              _handlers (package)                   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │ _base.py     │  │ EventHandler             │   │     │
│  │  │              │  │ EventContext             │   │     │
│  │  │              │  │ HandlerChain             │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │ _auth.py     │  │ AuthenticationHandler    │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │ _invite.py   │  │ InviteFlowHandler        │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │ _register.py │  │ RegisterFlowHandler      │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │ _state.py    │  │ TransactionStateHandler  │   │     │
│  │  │              │  │ DialogStateHandler       │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │     │
│  │  │_composite.py │  │ SipFlowHandler           │   │     │
│  │  └──────────────┘  └──────────────────────────┘   │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              _models (package)                     │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_message.py  │  │ Request, Response          │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_header.py   │  │ Headers, HeaderContainer   │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_body.py     │  │ SDPBody, XMLBody, etc.     │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_auth.py     │  │ DigestAuth, Credentials    │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │            _transports (package)                   │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_base.py     │  │ BaseTransport (ABC)        │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_udp.py      │  │ UDPTransport               │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_tcp.py      │  │ TCPTransport               │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  │  ┌─────────────┐  ┌────────────────────────────┐  │     │
│  │  │_tls.py      │  │ TLSTransport               │  │     │
│  │  └─────────────┘  └────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Segurança

### Autenticação

- **Digest Authentication** (RFC 2617)
- Suporte a MD5, SHA-256, SHA-512
- QoP auth e auth-int
- Proteção contra replay attacks (nonce)

### Transport Seguro

- **TLS 1.2+**
- Verificação de certificados
- Suporte a client certificates
- SNI (Server Name Indication)

### Validação

- Validação de headers obrigatórios
- Sanitização de inputs
- Validação de URIs
- Verificação de Content-Length

---

## 🚀 Performance

### Otimizações

1. **Lazy Loading**: Transports carregados sob demanda
2. **Connection Pooling**: Reutilização de conexões TCP/TLS
3. **Buffer Management**: Buffers ajustáveis por transport
4. **Async I/O**: Non-blocking operations com asyncio
5. **Parser Caching**: Cache de headers parsed

### Limites

- **Max SIP Message Size**: 65535 bytes (UDP MTU)
- **Max Transactions**: Ilimitado (limitado por memória)
- **Max Dialogs**: Ilimitado (limitado por memória)
- **Connection Timeout**: 5s (configurável)
- **Read Timeout**: 32s (Timer B - RFC 3261)

---

## 📚 Referências

- [RFC 3261 - SIP: Session Initiation Protocol](https://datatracker.ietf.org/doc/html/rfc3261)
- [RFC 2617 - HTTP Digest Authentication](https://datatracker.ietf.org/doc/html/rfc2617)
- [RFC 4566 - SDP: Session Description Protocol](https://datatracker.ietf.org/doc/html/rfc4566)
- [RFC 3262 - PRACK: Reliability of Provisional Responses](https://datatracker.ietf.org/doc/html/rfc3262)
- [RFC 3264 - Offer/Answer Model with SDP](https://datatracker.ietf.org/doc/html/rfc3264)

---

## 📝 Notas de Implementação

### Compatibilidade

- **Python**: 3.12+
- **Plataformas**: Windows, Linux, macOS
- **Asterisk**: 16+, 18+, 20+
- **FreeSWITCH**: 1.10+

### Limitações Atuais

- Não suporta IPv6 nativamente
- WebSocket transport não implementado
- PRACK não implementado completamente
- Auto-reregister não implementado
- Forking (múltiplas respostas 2xx) suporte limitado

### Próximos Passos

1. Implementar auto-reregister
2. Adicionar suporte a CANCEL completo
3. Implementar PRACK (RFC 3262)
4. Adicionar WebSocket transport
5. Melhorar suporte a forking
6. Implementar timers de retransmissão (Timer A/B/D)
7. Adicionar suporte a IPv6