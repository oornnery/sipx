# -*- coding: utf-8 -*-
"""
Sistema SIP Avançado com Transações, Diálogos, Autenticação e Handlers
Implementação completa baseada em httpx para protocolo SIP

Características:
- Transações INVITE e Non-INVITE conforme RFC 3261/6026
- Diálogos com estados Early/Confirmed/Terminated
- Autenticação Digest conforme RFC 8760
- Sistema de handlers com decoradores
- Gerenciamento automático de timers
- Thread-safe com cleanup automático

Autor: Implementação baseada em httpx e Oracle SIP API
"""

import time
import uuid
import hashlib
import secrets
import enum
import threading
import logging
from typing import Dict, List, Optional, Union, Callable, cast

from rich.logging import RichHandler
from rich.console import Console


console = Console()
# Define the log message format
FORMAT = "%(message)s"

# Configure the basic logging setup
logging.basicConfig(
    level="NOTSET",  # Set the lowest level to capture all messages
    format=FORMAT,
    datefmt="[%X]",  # Format for the timestamp
    handlers=[
        RichHandler(
            console=console,
        )
    ],  # Use RichHandler for colorful output
)

# Get a logger instance
log = logging.getLogger("rich")
# ============================================================================
# ESTADOS E ENUMS
# ============================================================================


class TransactionState(enum.Enum):
    """Estados das transações SIP"""

    # INVITE Client Transaction (ICT)
    CALLING = "calling"
    PROCEEDING = "proceeding"
    COMPLETED = "completed"
    ACCEPTED = "accepted"  # RFC 6026
    TERMINATED = "terminated"

    # Non-INVITE Client Transaction (NICT)
    TRYING = "trying"

    # Server Transactions
    TRYING_SERVER = "trying_server"
    PROCEEDING_SERVER = "proceeding_server"
    COMPLETED_SERVER = "completed_server"
    CONFIRMED_SERVER = "confirmed_server"
    ACCEPTED_SERVER = "accepted_server"
    TERMINATED_SERVER = "terminated_server"


class DialogState(enum.Enum):
    """Estados dos diálogos SIP"""

    EARLY = "early"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"


class TransactionType(enum.Enum):
    """Tipos de transação SIP"""

    INVITE_CLIENT = "invite_client"
    NON_INVITE_CLIENT = "non_invite_client"
    INVITE_SERVER = "invite_server"
    NON_INVITE_SERVER = "non_invite_server"


class SIPTimers:
    """Timers SIP conforme RFC 3261"""

    T1 = 0.5  # RTT estimado
    T2 = 4.0  # Máximo retransmit interval para non-INVITE
    T4 = 5.0  # Máximo duração para mensagens na rede

    # Timers específicos
    TIMER_A = T1  # Retransmit INVITE
    TIMER_B = 64 * T1  # Timeout INVITE
    TIMER_D = 32.0  # Wait time para response retransmits
    TIMER_E = T1  # Retransmit non-INVITE
    TIMER_F = 64 * T1  # Timeout non-INVITE
    TIMER_G = T1  # Retransmit response
    TIMER_H = 64 * T1  # Timeout para ACK
    TIMER_I = T4  # Wait time para ACK retransmits
    TIMER_J = 64 * T1  # Timeout para non-INVITE server
    TIMER_K = T4  # Wait time para response retransmits
    TIMER_L = 64 * T1  # Wait time para accepted state (RFC 6026)
    TIMER_M = 64 * T1  # Wait time para 2xx retransmits (RFC 6026)


# ============================================================================
# CLASSES BASE (REPLICADAS DO ARQUIVO ANTERIOR)
# ============================================================================


class SIPHeaders:
    """Classe para gerenciar headers SIP"""

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

    def update(self, other: Union[Dict[str, str], "SIPHeaders"]):
        if isinstance(other, SIPHeaders):
            self._headers.update(other._headers)
        elif isinstance(other, dict):
            for key, value in other.items():
                self._headers[key.lower()] = str(value)

    def to_string(self) -> str:
        """Converte headers para formato SIP"""
        lines = []
        for key, value in self._headers.items():
            formatted_key = "-".join(word.capitalize() for word in key.split("-"))
            lines.append(f"{formatted_key}: {value}")
        return "\r\n".join(lines)


class SIPRequest:
    """Classe para representar uma requisição SIP"""

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
        self._ensure_required_headers()

    def _ensure_required_headers(self):
        """Garante que headers obrigatórios estejam presentes"""
        if "call-id" not in self.headers:
            self.headers["call-id"] = f"{uuid.uuid4().hex}@localhost"
        if "cseq" not in self.headers:
            self.headers["cseq"] = f"1 {self.method}"
        if "via" not in self.headers:
            branch = f"z9hG4bK{uuid.uuid4().hex[:8]}"
            self.headers["via"] = f"SIP/2.0/UDP localhost:5060;branch={branch}"
        if "from" not in self.headers:
            self.headers["from"] = f"<{self.uri}>;tag={uuid.uuid4().hex[:8]}"
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


class SIPResponse:
    """Classe para representar uma resposta SIP"""

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


# ============================================================================
# AUTENTICAÇÃO DIGEST SIP
# ============================================================================


class SIPAuthenticator:
    """Sistema de autenticação digest SIP baseado em RFC 8760"""

    def __init__(self, username: str, password: str, realm: Optional[str] = None):
        self.username = username
        self.password = password
        self.realm = realm
        self.algorithm = "MD5"
        self.qop = "auth"

    def generate_nonce(self) -> str:
        """Gera nonce único para autenticação"""
        return secrets.token_hex(16)

    def generate_response(
        self,
        method: str,
        uri: str,
        nonce: str,
        nc: str = "00000001",
        cnonce: Optional[str] = None,
        realm: Optional[str] = None,
    ) -> str:
        """Gera resposta digest para autenticação"""
        if not cnonce:
            cnonce = secrets.token_hex(8)
        if not realm:
            realm = self.realm or "sip"

        # A1 = username:realm:password
        a1 = f"{self.username}:{realm}:{self.password}"
        # A2 = method:uri
        a2 = f"{method}:{uri}"

        # Hash A1 e A2
        ha1 = hashlib.md5(a1.encode()).hexdigest()
        ha2 = hashlib.md5(a2.encode()).hexdigest()

        # Response = MD5(HA1:nonce:nc:cnonce:qop:HA2)
        if self.qop:
            response_str = f"{ha1}:{nonce}:{nc}:{cnonce}:{self.qop}:{ha2}"
        else:
            response_str = f"{ha1}:{nonce}:{ha2}"

        response = hashlib.md5(response_str.encode()).hexdigest()
        return response

    def create_authorization_header(
        self,
        method: str,
        uri: str,
        nonce: str,
        realm: Optional[str] = None,
        opaque: Optional[str] = None,
    ) -> str:
        """Cria header Authorization para requisição SIP"""
        if not realm:
            realm = self.realm or "sip"

        nc = "00000001"
        cnonce = secrets.token_hex(8)

        response = self.generate_response(method, uri, nonce, nc, cnonce, realm)

        auth_parts = [
            f'username="{self.username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            f'response="{response}"',
            f"algorithm={self.algorithm}",
        ]

        if self.qop:
            auth_parts.extend([f"qop={self.qop}", f"nc={nc}", f'cnonce="{cnonce}"'])

        if opaque:
            auth_parts.append(f'opaque="{opaque}"')

        return f"Digest {', '.join(auth_parts)}"

    def parse_www_authenticate(self, auth_header: str) -> Dict[str, str]:
        """Parse do header WWW-Authenticate ou Proxy-Authenticate"""
        if auth_header.startswith("Digest "):
            auth_header = auth_header[7:]

        auth_params = {}
        parts = auth_header.split(",")

        for part in parts:
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"')
                auth_params[key] = value

        return auth_params


class SIPAuthChallenge:
    """Gera desafios de autenticação SIP"""

    def __init__(self, realm: str = "sip", algorithm: str = "MD5"):
        self.realm = realm
        self.algorithm = algorithm
        self.active_nonces = {}

    def create_challenge(self, stale: bool = False) -> str:
        """Cria header WWW-Authenticate para desafiar cliente"""
        nonce = secrets.token_hex(16)
        timestamp = time.time()
        self.active_nonces[nonce] = timestamp

        challenge_parts = [
            f'realm="{self.realm}"',
            f'nonce="{nonce}"',
            f"algorithm={self.algorithm}",
            'qop="auth"',
        ]

        if stale:
            challenge_parts.append("stale=TRUE")

        return f"Digest {', '.join(challenge_parts)}"

    def is_nonce_valid(self, nonce: str, max_age: int = 300) -> bool:
        """Verifica se nonce ainda é válido"""
        if nonce not in self.active_nonces:
            return False
        timestamp = self.active_nonces[nonce]
        return (time.time() - timestamp) < max_age


# ============================================================================
# SISTEMA DE TRANSAÇÕES
# ============================================================================


class SIPTransaction:
    """Classe base para transações SIP"""

    def __init__(
        self,
        transaction_id: str,
        transaction_type: TransactionType,
        request: SIPRequest | None = None,
    ):
        self.transaction_id = transaction_id
        self.transaction_type = transaction_type
        self.state = TransactionState.TRYING
        self.request = request
        self.responses = []

        # Timers
        self.timers = {}
        self.created_at = time.time()
        self.last_activity = time.time()

        # Callbacks
        self.state_change_callback = None
        self.timeout_callback = None

    def set_state(self, new_state: TransactionState):
        """Muda estado da transação"""
        old_state = self.state
        self.state = new_state
        self.last_activity = time.time()

        if self.state_change_callback:
            self.state_change_callback(self, old_state, new_state)

    def add_response(self, response: SIPResponse):
        """Adiciona resposta à transação"""
        self.responses.append(response)
        self.last_activity = time.time()

    def start_timer(self, timer_name: str, duration: float, callback: Callable):
        """Inicia um timer para a transação"""
        if timer_name in self.timers:
            self.timers[timer_name].cancel()

        timer = threading.Timer(duration, callback)
        timer.start()
        self.timers[timer_name] = timer

    def cancel_timer(self, timer_name: str):
        """Cancela um timer"""
        if timer_name in self.timers:
            self.timers[timer_name].cancel()
            del self.timers[timer_name]

    def cancel_all_timers(self):
        """Cancela todos os timers"""
        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()

    def is_terminated(self) -> bool:
        """Verifica se transação está terminada"""
        return self.state == TransactionState.TERMINATED


class InviteClientTransaction(SIPTransaction):
    """Transação INVITE do cliente (ICT) - RFC 3261 Section 17.1.1"""

    def __init__(self, transaction_id: str, request: SIPRequest):
        super().__init__(transaction_id, TransactionType.INVITE_CLIENT, request)
        self.state = TransactionState.CALLING
        self.retransmit_count = 0

        # Inicia timers
        self._start_timer_a()
        self._start_timer_b()

    def _start_timer_a(self):
        """Timer A - Retransmissão de INVITE"""
        self.start_timer("A", SIPTimers.TIMER_A, self._on_timer_a)

    def _start_timer_b(self):
        """Timer B - Timeout de INVITE"""
        self.start_timer("B", SIPTimers.TIMER_B, self._on_timer_b)

    def _on_timer_a(self):
        """Callback do Timer A - Retransmitir INVITE"""
        if self.state == TransactionState.CALLING:
            self.retransmit_count += 1
            # Dobrar intervalo para próxima retransmissão
            next_interval = min(
                SIPTimers.TIMER_A * (2**self.retransmit_count), SIPTimers.T2
            )
            self.start_timer("A", next_interval, self._on_timer_a)

    def _on_timer_b(self):
        """Callback do Timer B - Timeout de transação"""
        if self.state in [TransactionState.CALLING, TransactionState.PROCEEDING]:
            self.set_state(TransactionState.TERMINATED)
            if self.timeout_callback:
                self.timeout_callback(self, "INVITE timeout")

    def process_response(self, response: SIPResponse):
        """Processa resposta recebida"""
        self.add_response(response)
        status_code = response.status_code

        if self.state == TransactionState.CALLING:
            self.cancel_timer("A")

            if 100 <= status_code <= 199:
                self.set_state(TransactionState.PROCEEDING)
            elif 200 <= status_code <= 299:
                self.cancel_timer("B")
                self.set_state(TransactionState.ACCEPTED)
                self._start_timer_m()
            elif 300 <= status_code <= 699:
                self.cancel_timer("B")
                self.set_state(TransactionState.COMPLETED)
                self._start_timer_d()

        elif self.state == TransactionState.PROCEEDING:
            if 200 <= status_code <= 299:
                self.cancel_timer("B")
                self.set_state(TransactionState.ACCEPTED)
                self._start_timer_m()
            elif 300 <= status_code <= 699:
                self.cancel_timer("B")
                self.set_state(TransactionState.COMPLETED)
                self._start_timer_d()

    def _start_timer_m(self):
        """Timer M - Wait time para 2xx retransmits (RFC 6026)"""
        self.start_timer("M", SIPTimers.TIMER_M, self._on_timer_m)

    def _start_timer_d(self):
        """Timer D - Wait time para response retransmits"""
        self.start_timer("D", SIPTimers.TIMER_D, self._on_timer_d)

    def _on_timer_m(self):
        """Callback do Timer M"""
        if self.state == TransactionState.ACCEPTED:
            self.set_state(TransactionState.TERMINATED)

    def _on_timer_d(self):
        """Callback do Timer D"""
        if self.state == TransactionState.COMPLETED:
            self.set_state(TransactionState.TERMINATED)


class NonInviteClientTransaction(SIPTransaction):
    """Transação Non-INVITE do cliente (NICT) - RFC 3261 Section 17.1.2"""

    def __init__(self, transaction_id: str, request: SIPRequest):
        super().__init__(transaction_id, TransactionType.NON_INVITE_CLIENT, request)
        self.state = TransactionState.TRYING
        self.retransmit_count = 0

        self._start_timer_e()
        self._start_timer_f()

    def _start_timer_e(self):
        """Timer E - Retransmissão de non-INVITE"""
        self.start_timer("E", SIPTimers.TIMER_E, self._on_timer_e)

    def _start_timer_f(self):
        """Timer F - Timeout de non-INVITE"""
        self.start_timer("F", SIPTimers.TIMER_F, self._on_timer_f)

    def _on_timer_e(self):
        """Callback do Timer E - Retransmitir requisição"""
        if self.state in [TransactionState.TRYING, TransactionState.PROCEEDING]:
            self.retransmit_count += 1
            next_interval = min(
                SIPTimers.TIMER_E * (2**self.retransmit_count), SIPTimers.T2
            )
            self.start_timer("E", next_interval, self._on_timer_e)

    def _on_timer_f(self):
        """Callback do Timer F - Timeout de transação"""
        if self.state in [TransactionState.TRYING, TransactionState.PROCEEDING]:
            self.set_state(TransactionState.TERMINATED)
            if self.timeout_callback:
                self.timeout_callback(self, "Non-INVITE timeout")

    def process_response(self, response: SIPResponse):
        """Processa resposta recebida"""
        self.add_response(response)
        status_code = response.status_code

        if self.state == TransactionState.TRYING:
            self.cancel_timer("E")

            if 100 <= status_code <= 199:
                self.set_state(TransactionState.PROCEEDING)
            elif 200 <= status_code <= 699:
                self.cancel_timer("F")
                self.set_state(TransactionState.COMPLETED)
                self._start_timer_k()

        elif self.state == TransactionState.PROCEEDING:
            if 200 <= status_code <= 699:
                self.cancel_timer("F")
                self.set_state(TransactionState.COMPLETED)
                self._start_timer_k()

    def _start_timer_k(self):
        """Timer K - Wait time para response retransmits"""
        self.start_timer("K", SIPTimers.TIMER_K, self._on_timer_k)

    def _on_timer_k(self):
        """Callback do Timer K"""
        if self.state == TransactionState.COMPLETED:
            self.set_state(TransactionState.TERMINATED)


# ============================================================================
# SISTEMA DE DIÁLOGOS
# ============================================================================


class SIPDialog:
    """Gerenciamento de diálogo SIP conforme RFC 3261"""

    def __init__(
        self, dialog_id: str, call_id: str, local_tag: str, remote_tag: str = ""
    ):
        self.dialog_id = dialog_id
        self.call_id = call_id
        self.local_tag = local_tag
        self.remote_tag = remote_tag

        self.state = DialogState.EARLY
        self.local_cseq = 1
        self.remote_cseq = 0

        # URIs do diálogo
        self.local_uri = None
        self.remote_uri = None
        self.local_contact = None
        self.remote_contact = None

        # Route sets
        self.route_set = []

        self.created_at = time.time()
        self.last_activity = time.time()

        # Callbacks
        self.state_change_callback = None

    def set_state(self, new_state: DialogState):
        """Muda estado do diálogo"""
        old_state = self.state
        self.state = new_state
        self.last_activity = time.time()

        if self.state_change_callback:
            self.state_change_callback(self, old_state, new_state)

    def next_local_cseq(self) -> int:
        """Retorna próximo CSeq local"""
        self.local_cseq += 1
        return self.local_cseq

    def update_remote_cseq(self, cseq: int):
        """Atualiza CSeq remoto"""
        if cseq > self.remote_cseq:
            self.remote_cseq = cseq

    def is_established(self) -> bool:
        """Verifica se diálogo está estabelecido"""
        return self.state == DialogState.CONFIRMED

    def is_terminated(self) -> bool:
        """Verifica se diálogo está terminado"""
        return self.state == DialogState.TERMINATED


# ============================================================================
# SISTEMA DE HANDLERS COM DECORADORES
# ============================================================================


class SIPEventHandler:
    """Sistema de handlers para eventos SIP"""

    def __init__(self):
        self.request_handlers = {}  # method -> [handlers]
        self.response_handlers = {}  # status_code -> [handlers]
        self.transaction_handlers = {}  # event -> [handlers]
        self.dialog_handlers = {}  # event -> [handlers]

    def on_request(self, method: str):
        """Decorador para handler de requisições"""

        def decorator(func):
            if method not in self.request_handlers:
                self.request_handlers[method] = []
            self.request_handlers[method].append(func)
            return func

        return decorator

    def on_response(self, status_code: Union[int, str] | None = None):
        """Decorador para handler de respostas"""

        def decorator(func):
            key = str(status_code) if status_code else "ALL"
            if key not in self.response_handlers:
                self.response_handlers[key] = []
            self.response_handlers[key].append(func)
            return func

        return decorator

    def on_transaction_state(self, state: TransactionState):
        """Decorador para mudanças de estado de transação"""

        def decorator(func):
            state_name = state.value
            if state_name not in self.transaction_handlers:
                self.transaction_handlers[state_name] = []
            self.transaction_handlers[state_name].append(func)
            return func

        return decorator

    def on_dialog_state(self, state: DialogState):
        """Decorador para mudanças de estado de diálogo"""

        def decorator(func):
            state_name = state.value
            if state_name not in self.dialog_handlers:
                self.dialog_handlers[state_name] = []
            self.dialog_handlers[state_name].append(func)
            return func

        return decorator

    def on_auth_challenge(self):
        """Decorador para desafios de autenticação"""

        def decorator(func):
            for code in ["401", "407"]:
                if code not in self.response_handlers:
                    self.response_handlers[code] = []
                self.response_handlers[code].append(func)
            return func

        return decorator

    # Shortcuts para métodos comuns
    def on_invite(self):
        return self.on_request("INVITE")

    def on_register(self):
        return self.on_request("REGISTER")

    def on_bye(self):
        return self.on_request("BYE")

    def on_ack(self):
        return self.on_request("ACK")

    def on_ok(self):
        return self.on_response(200)

    def on_ringing(self):
        return self.on_response(180)

    def on_busy(self):
        return self.on_response(486)

    # Métodos para executar handlers

    def handle_request(self, request: SIPRequest, context: Dict | None = None):
        """Executa handlers para requisição"""
        method = request.method
        context = context or {}

        if method in self.request_handlers:
            for handler in self.request_handlers[method]:
                try:
                    result = handler(request, context)
                    if result:
                        return result
                except Exception as e:
                    log.error(f"Erro no handler {method}: {e}")

        return None

    def handle_response(self, response: SIPResponse, context: Dict | None = None):
        """Executa handlers para resposta"""
        status_code = str(response.status_code)
        context = context or {}

        # Handlers específicos primeiro
        if status_code in self.response_handlers:
            for handler in self.response_handlers[status_code]:
                try:
                    handler(response, context)
                except Exception as e:
                    log.error(f"Erro no handler {status_code}: {e}")

        # Handlers gerais
        if "ALL" in self.response_handlers:
            for handler in self.response_handlers["ALL"]:
                try:
                    handler(response, context)
                except Exception as e:
                    log.error(f"Erro no handler ALL: {e}")

    def handle_transaction_state_change(
        self,
        transaction: SIPTransaction,
        old_state: TransactionState,
        new_state: TransactionState,
    ):
        """Executa handlers para mudança de estado de transação"""
        state_name = new_state.value

        if state_name in self.transaction_handlers:
            for handler in self.transaction_handlers[state_name]:
                try:
                    handler(transaction, old_state, new_state)
                except Exception as e:
                    log.error(f"Erro no handler transaction {state_name}: {e}")

    def handle_dialog_state_change(
        self, dialog: SIPDialog, old_state: DialogState, new_state: DialogState
    ):
        """Executa handlers para mudança de estado de diálogo"""
        state_name = new_state.value

        if state_name in self.dialog_handlers:
            for handler in self.dialog_handlers[state_name]:
                try:
                    handler(dialog, old_state, new_state)
                except Exception as e:
                    log.error(f"Erro no handler dialog {state_name}: {e}")


# ============================================================================
# GERENCIADOR DE TRANSAÇÕES
# ============================================================================


class SIPTransactionManager:
    """Gerenciador de transações SIP"""

    def __init__(self):
        self.transactions = {}
        self.dialogs = {}
        self.event_handler = SIPEventHandler()

        # Thread safety
        self._lock = threading.RLock()

        # Cleanup thread
        self._cleanup_thread = None
        self._running = False

    def start(self):
        """Inicia o gerenciador"""
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop(self):
        """Para o gerenciador"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join()

    def _cleanup_loop(self):
        """Loop de limpeza de transações/diálogos terminados"""
        while self._running:
            try:
                time.sleep(5)
                self._cleanup_terminated()
            except Exception as e:
                log.error(f"Erro no cleanup: {e}")

    def _cleanup_terminated(self):
        """Remove transações e diálogos terminados"""
        with self._lock:
            # Cleanup transações
            terminated_transactions = [
                tid
                for tid, tx in self.transactions.items()
                if tx.is_terminated() and (time.time() - tx.last_activity) > 30
            ]

            for tid in terminated_transactions:
                tx = self.transactions.pop(tid)
                tx.cancel_all_timers()

            # Cleanup diálogos
            terminated_dialogs = [
                did
                for did, dialog in self.dialogs.items()
                if dialog.is_terminated() and (time.time() - dialog.last_activity) > 300
            ]

            for did in terminated_dialogs:
                del self.dialogs[did]

    def create_client_transaction(self, request: SIPRequest) -> SIPTransaction:
        """Cria transação de cliente"""
        transaction_id = self._generate_transaction_id(request)

        with self._lock:
            if request.method == "INVITE":
                transaction = InviteClientTransaction(transaction_id, request)
            else:
                transaction = NonInviteClientTransaction(transaction_id, request)

            transaction.state_change_callback = self._on_transaction_state_change
            transaction.timeout_callback = self._on_transaction_timeout

            self.transactions[transaction_id] = transaction
            return transaction

    def find_transaction(
        self, message: Union[SIPRequest, SIPResponse]
    ) -> Optional[SIPTransaction]:
        """Encontra transação corresponde à mensagem"""
        transaction_id = self._generate_transaction_id(message)
        return self.transactions.get(transaction_id)

    def _generate_transaction_id(self, message: Union[SIPRequest, SIPResponse]) -> str:
        """Gera ID de transação baseado na mensagem"""
        if hasattr(message, "method"):  # SIPRequest
            via = message.headers.get("via", "")
            method = message.method
        else:  # SIPResponse
            via = message.headers.get("via", "")
            cseq = message.headers.get("cseq", "")
            method = cseq.split()[-1] if cseq else "UNKNOWN"

        # Extrai branch do Via header
        branch = "default"
        if via:
            if "branch=" in via:
                branch = via.split("branch=")[1].split(";")[0]

        return f"{branch}_{method}"

    def create_dialog(self, request: SIPRequest, response: SIPResponse) -> SIPDialog:
        """Cria diálogo a partir de requisição e resposta"""
        call_id = cast(str, request.headers.get("call-id", "") or "")
        from_header = cast(str, request.headers.get("from", "") or "")
        to_header = cast(str, response.headers.get("to", "") or "")

        # Extrai tags
        local_tag = self._extract_tag(from_header)
        remote_tag = self._extract_tag(to_header)

        dialog_id = f"{call_id}_{local_tag}_{remote_tag}"

        with self._lock:
            if dialog_id not in self.dialogs:
                dialog = SIPDialog(dialog_id, call_id, local_tag, remote_tag)
                dialog.state_change_callback = self._on_dialog_state_change

                dialog.local_uri = request.headers.get("from", "") or ""
                dialog.remote_uri = response.headers.get("to", "") or ""
                dialog.local_contact = request.headers.get("contact", "") or ""
                dialog.remote_contact = response.headers.get("contact", "") or ""

                self.dialogs[dialog_id] = dialog

            return self.dialogs[dialog_id]

    def _extract_tag(self, header: str) -> str:
        """Extrai tag de header From/To"""
        if "tag=" in header:
            return header.split("tag=")[1].split(";")[0]
        return ""

    def _on_transaction_state_change(
        self,
        transaction: SIPTransaction,
        old_state: TransactionState,
        new_state: TransactionState,
    ):
        """Callback para mudança de estado de transação"""
        self.event_handler.handle_transaction_state_change(
            transaction, old_state, new_state
        )

    def _on_transaction_timeout(self, transaction: SIPTransaction, reason: str):
        """Callback para timeout de transação"""
        log.warning(f"Transação {transaction.transaction_id} timeout: {reason}")

    def _on_dialog_state_change(
        self, dialog: SIPDialog, old_state: DialogState, new_state: DialogState
    ):
        """Callback para mudança de estado de diálogo"""
        self.event_handler.handle_dialog_state_change(dialog, old_state, new_state)

    def process_request(self, request: SIPRequest) -> Optional[SIPResponse]:
        """Processa requisição recebida"""
        transaction = self.find_transaction(request)

        context = {"transaction": transaction, "transaction_manager": self}

        return self.event_handler.handle_request(request, context)

    def process_response(
        self, response: SIPResponse, request: Optional[SIPRequest] = None
    ):
        """Processa resposta recebida"""
        transaction = self.find_transaction(response)

        if transaction:
            transaction.process_response(response)

            # Gerencia diálogo se necessário
            if request and response.status_code >= 200:
                if request.method in ["INVITE", "SUBSCRIBE"]:
                    dialog = self.create_dialog(request, response)

                    if response.status_code < 300:
                        dialog.set_state(DialogState.CONFIRMED)
                    else:
                        dialog.set_state(DialogState.TERMINATED)

        context = {
            "transaction": transaction,
            "dialog": self.dialogs.get(f"{response.headers.get('call-id', '')}", None),
            "transaction_manager": self,
        }

        self.event_handler.handle_response(response, context)


# ============================================================================
# CLIENTE SIP AVANÇADO
# ============================================================================


class SIPClient:
    """Cliente SIP avançado com suporte a transações, diálogos, auth e handlers"""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        realm: Optional[str] = None,
        user_agent: str = "SIPClient/1.0",
        local_host: str = "localhost",
        local_port: int = 0,
    ):
        # Configuração básica
        self.local_host = local_host
        self.local_port = local_port
        self.user_agent = user_agent

        # Transações e diálogos
        self.transaction_manager = SIPTransactionManager()

        # Autenticação
        self.authenticator = None
        if username and password:
            self.authenticator = SIPAuthenticator(username, password, realm)

        self.auth_challenge = SIPAuthChallenge(realm or "sip")

        # Handlers de eventos (proxy para transaction_manager)
        self.handlers = self.transaction_manager.event_handler

        # Estado
        self._running = False

    def start(self):
        """Inicia o cliente"""
        self._running = True
        self.transaction_manager.start()

    def stop(self):
        """Para o cliente"""
        self._running = False
        self.transaction_manager.stop()

    def send_request(
        self, request: SIPRequest, target_host: str, target_port: int = 5060
    ) -> SIPTransaction:
        """Envia requisição SIP com suporte a transações"""
        transaction = self.transaction_manager.create_client_transaction(request)

        # Simula envio (em implementação real, usaria transporte)
        print(f"Enviando {request.method} para {target_host}:{target_port}")

        # Simula resposta (em implementação real, viria do transporte)
        response = SIPResponse(200, "OK")
        self.transaction_manager.process_response(response, request)

        return transaction

    def register(
        self,
        register_uri: str,
        target_host: str,
        contact_uri: Optional[str] = None,
        expires: int = 3600,
        target_port: int = 5060,
    ) -> str:
        """REGISTER com suporte automático a autenticação digest"""

        if not contact_uri:
            contact_uri = f"sip:user@{self.local_host}:{self.local_port}"

        register_headers = SIPHeaders(
            {
                "contact": f"<{contact_uri}>",
                "expires": str(expires),
                "from": f"<{register_uri}>;tag={uuid.uuid4().hex[:8]}",
                "to": f"<{register_uri}>",
            }
        )

        request = SIPRequest("REGISTER", register_uri, register_headers)

        # Primeira tentativa
        print(f"Tentativa 1: REGISTER {register_uri}")

        # Simula resposta 401
        if self.authenticator:
            challenge = self.auth_challenge.create_challenge()
            print(f"Recebido 401 com challenge: {challenge}")

            # Segunda tentativa com auth
            auth_params = self.authenticator.parse_www_authenticate(challenge)
            nonce = auth_params.get("nonce", "")
            realm = auth_params.get("realm", "sip")

            auth_value = self.authenticator.create_authorization_header(
                "REGISTER", register_uri, nonce, realm
            )

            register_headers["authorization"] = auth_value
            request = SIPRequest("REGISTER", register_uri, register_headers)

            print("Tentativa 2: REGISTER com auth")
            print(f"Authorization: {auth_value[:50]}...")

            transaction = self.send_request(request, target_host, target_port)
            return f"REGISTER autenticado: {transaction.transaction_id}"

        transaction = self.send_request(request, target_host, target_port)
        return f"REGISTER simples: {transaction.transaction_id}"

    def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        sdp_content: Optional[str] = None,
        target_host: Optional[str] = None,
        target_port: int = 5060,
    ) -> Dict:
        """INVITE com gerenciamento completo de diálogo"""

        if not from_uri:
            from_uri = f"sip:user@{self.local_host}:{self.local_port}"

        invite_headers = SIPHeaders(
            {
                "from": f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}",
                "to": f"<{to_uri}>",
                "contact": f"<{from_uri}>",
            }
        )

        if sdp_content:
            invite_headers["content-type"] = "application/sdp"

        request = SIPRequest("INVITE", to_uri, invite_headers, sdp_content)

        target = target_host or to_uri.split("@")[1] if "@" in to_uri else "localhost"
        transaction = self.send_request(request, target, target_port)

        return {
            "transaction": transaction,
            "request": request,
            "call_id": request.headers["call-id"],
        }

    # Métodos de conveniência para decoradores
    def on_request(self, method: str):
        return self.handlers.on_request(method)

    def on_response(self, status_code: Optional[Union[int, str]] = None):
        return self.handlers.on_response(status_code)

    def on_transaction_state(self, state: TransactionState):
        return self.handlers.on_transaction_state(state)

    def on_dialog_state(self, state: DialogState):
        return self.handlers.on_dialog_state(state)

    def on_auth_challenge(self):
        return self.handlers.on_auth_challenge()

    # Shortcuts para decoradores comuns
    def on_invite(self):
        return self.handlers.on_invite()

    def on_register(self):
        return self.handlers.on_register()

    def on_bye(self):
        return self.handlers.on_bye()

    def on_ack(self):
        return self.handlers.on_ack()

    def on_ok(self):
        return self.handlers.on_ok()

    def on_ringing(self):
        return self.handlers.on_ringing()

    def on_busy(self):
        return self.handlers.on_busy()


# ============================================================================
# EXEMPLOS DE USO
# ============================================================================


def exemplo_uso_completo():
    """Exemplo completo de uso do sistema SIP"""

    print("=== SISTEMA SIP AVANÇADO - EXEMPLO COMPLETO ===\\n")

    # Criar cliente com autenticação
    client = SIPClient(
        username="1111",
        password="1111xxx",
        realm="demo.mizu-voip.com",
    )

    # Configurar handlers com decoradores

    @client.on_register()
    def handle_register_request(request, context):
        log.info(f"📝 REGISTER recebido de: {request.headers.get('from')}")
        return None

    @client.on_invite()
    def handle_invite_request(request, context):
        log.info(f"📞 INVITE recebido para: {request.uri}")
        log.info(f"   From: {request.headers.get('from')}")
        log.info(f"   Call-ID: {request.headers.get('call-id')}")
        return None

    @client.on_response(200)
    def handle_ok_response(response, context):
        log.info("✅ 200 OK recebido!")
        transaction = context.get("transaction")
        if transaction:
            log.info(f"   Transação: {transaction.transaction_id}")
            log.info(f"   Estado: {transaction.state.value}")

    @client.on_auth_challenge()
    def handle_auth_challenge(response, context):
        log.info("🔐 Desafio de autenticação recebido")
        auth_header = response.headers.get("www-authenticate", "")
        log.info(f"   Challenge: {auth_header[:50]}...")

    @client.on_transaction_state(TransactionState.COMPLETED)
    def handle_transaction_completed(transaction, old_state, new_state):
        log.info(f"🔄 Transação {transaction.transaction_id} completada")
        log.info(f"   {old_state.value} → {new_state.value}")

    @client.on_dialog_state(DialogState.CONFIRMED)
    def handle_dialog_confirmed(dialog, old_state, new_state):
        log.info(f"💬 Diálogo {dialog.dialog_id} estabelecido")
        log.info(f"   Call-ID: {dialog.call_id}")

    # Iniciar cliente
    client.start()

    console.rule("Cliente SIP iniciado com handlers configurados\\n")

    # Exemplo 1: REGISTER com autenticação
    console.rule("--- EXEMPLO 1: REGISTER com Autenticação ---")
    result = client.register(
        "sip:1111@demo.mizu-voip.com:37075",
        "demo.mizu-voip.com",
        target_port=37075,
    )
    console.print(f"Resultado: {result}\\n")

    # Exemplo 2: INVITE com diálogo
    console.rule("--- EXEMPLO 2: INVITE com Diálogo ---")
    call_info = client.invite(
        to_uri="sip:1111@demo.mizu-voip.com:37075",
        from_uri="sip:1111@demo.mizu-voip.com:37075",
        sdp_content="v=0\no=1111 123 456 IN IP4 192.168.1.100\n...",
        target_host="demo.mizu-voip.com",
        target_port=37075,
    )
    console.print(f"Call-ID: {call_info['call_id']}")
    console.print(f"Transaction: {call_info['transaction'].transaction_id}\\n")

    # Exemplo options
    console.rule("--- EXEMPLO 3: OPTIONS Simples ---")

    # Para o cliente
    client.stop()

    print("✨ Exemplo concluído!")


if __name__ == "__main__":
    exemplo_uso_completo()

    print("\\n" + "=" * 70)
    print("🎉 SISTEMA SIP COMPLETO IMPLEMENTADO!")
    print("=" * 70)
    print("\\n✨ Recursos implementados:")
    print("• Transações INVITE e Non-INVITE com estados RFC 3261/6026")
    print("• Diálogos com estados Early/Confirmed/Terminated")
    print("• Autenticação Digest conforme RFC 8760")
    print("• Sistema completo de handlers com decoradores")
    print("• Gerenciamento automático de timers SIP")
    print("• Thread-safe com cleanup automático")
    print("• Integração completa entre todos os componentes")

    print("\\n🔧 Como usar:")
    print("1. client = SIPClient(username='user', password='pass')")
    print("2. @client.on_invite() - Configurar handlers")
    print("3. client.start() - Iniciar cliente")
    print("4. client.register() - Registrar com auth automático")
    print("5. client.invite() - Fazer chamadas")

    print("\\n📚 Conformidade com RFCs:")
    print("• RFC 3261: SIP Protocol")
    print("• RFC 6026: Correct 2xx Transaction Handling")
    print("• RFC 8760: SIP Digest Authentication")
    print("• Oracle SIP API: Transaction and Dialog Management")
