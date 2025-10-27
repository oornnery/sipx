#!/usr/bin/env python3
"""
SIPX - Demonstração Completa de Funcionalidades com Asterisk

Este script demonstra TODAS as funcionalidades implementadas no SIPX
usando o servidor Asterisk configurado no Docker.

Funcionalidades demonstradas:
1. Registro com autenticação digest
2. Verificação de capacidades (OPTIONS)
3. Chamada INVITE com SDP
4. Envio de ACK
5. Mensagens instantâneas (MESSAGE)
6. Término de chamada (BYE)
7. Handlers customizados
8. State management (Transactions e Dialogs)
9. Múltiplos transports (UDP, TCP)
10. Servidor SIP para receber chamadas

Pré-requisitos:
- Docker com Asterisk rodando (docker-compose up -d)
- Porta 5060 UDP/TCP disponível no host
- Python 3.12+

Uso:
    # Do diretório raiz do projeto:
    uv run python examples/asterisk_complete_demo.py

    # Ou se você instalou o pacote:
    python examples/asterisk_complete_demo.py

Ou com opções:
    uv run python examples/asterisk_complete_demo.py --asterisk-host 192.168.1.100 --transport TCP
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

# Adicionar o diretório pai ao path para importar sipx
sys.path.insert(0, str(Path(__file__).parent.parent))

# Rich para output bonito
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

# SIPX imports
from sipx import (
    Client,
    SIPServer,
    SipAuthCredentials,
    Request,
    Response,
)

# Handlers
from sipx._handlers import (
    SipFlowHandler,
    AuthenticationHandler,
)

# FSM
from sipx import TransactionState, DialogState

# Console para output
console = Console()


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================


class Config:
    """Configurações do demo."""

    # Asterisk
    ASTERISK_HOST = "127.0.0.1"
    ASTERISK_PORT = 5060

    # Credenciais dos usuários configurados no Asterisk
    USER_1111 = SipAuthCredentials(username="1111", password="1111xxx")
    USER_2222 = SipAuthCredentials(username="2222", password="2222xxx")
    USER_3333 = SipAuthCredentials(username="3333", password="3333xxx")

    # Transport
    TRANSPORT = "UDP"  # UDP, TCP, ou TLS

    # Timing
    WAIT_TIME = 2  # Segundos entre operações
    CALL_DURATION = 5  # Duração da chamada em segundos


# =============================================================================
# SDP TEMPLATES
# =============================================================================


def create_sdp_offer(local_ip: str = "192.168.1.100", local_port: int = 10000) -> str:
    """Cria SDP offer para INVITE."""
    return f"""v=0
o=- {int(time.time())} {int(time.time())} IN IP4 {local_ip}
s=SIPX Demo Call
c=IN IP4 {local_ip}
t=0 0
m=audio {local_port} RTP/AVP 0 8 101
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-16
a=ptime:20
a=sendrecv
"""


# =============================================================================
# CALLBACKS PARA HANDLERS
# =============================================================================


class DemoCallbacks:
    """Callbacks para demonstrar handlers."""

    @staticmethod
    def on_ringing(response: Response, context) -> None:
        """Callback quando recebe 180 Ringing."""
        console.print("\n[bold yellow]📞 RINGING![/bold yellow]")
        console.print(f"   Call-ID: {response.call_id}")
        console.print(f"   From: {response.headers.get('From', 'N/A')}")
        console.print(f"   To: {response.headers.get('To', 'N/A')}")

    @staticmethod
    def on_session_progress(response: Response, context) -> None:
        """Callback quando recebe 183 Session Progress."""
        console.print("\n[bold cyan]🔊 SESSION PROGRESS (Early Media)[/bold cyan]")
        if response.content:
            console.print(f"   SDP Answer length: {len(response.content)} bytes")

    @staticmethod
    def on_answered(response: Response, context) -> None:
        """Callback quando recebe 200 OK (call answered)."""
        console.print("\n[bold green]✅ CALL ANSWERED![/bold green]")

        # Extrair SDP answer
        if response.content:
            sdp = response.content.decode("utf-8")
            console.print("\n[bold]Remote SDP:[/bold]")
            console.print(Panel(sdp, title="SDP Answer", border_style="green"))

    @staticmethod
    def on_confirmed(response: Response, context) -> None:
        """Callback quando ACK é enviado."""
        console.print("\n[bold green]✅ ACK SENT - Call Confirmed![/bold green]")

    @staticmethod
    def on_registered(response: Response, context) -> None:
        """Callback quando registro é bem-sucedido."""
        console.print("\n[bold green]✅ REGISTERED![/bold green]")

        # Extrair informações úteis
        expires = response.headers.get("Expires", "N/A")
        contact = response.headers.get("Contact", "N/A")

        console.print(f"   Expires: {expires} seconds")
        console.print(f"   Contact: {contact}")

    @staticmethod
    def on_unregistered(response: Response, context) -> None:
        """Callback quando unregister é confirmado."""
        console.print("\n[bold yellow]📤 UNREGISTERED[/bold yellow]")

    @staticmethod
    def on_registration_failed(response: Response, context) -> None:
        """Callback quando registro falha."""
        console.print(
            f"\n[bold red]❌ REGISTRATION FAILED: {response.status_code}[/bold red]"
        )

    @staticmethod
    def on_transaction_state_change(transaction) -> None:
        """Callback para mudança de estado de transação."""
        console.print(
            f"[dim]   Transaction {transaction.id[:8]}... → {transaction.state.name}[/dim]"
        )

    @staticmethod
    def on_dialog_state_change(dialog) -> None:
        """Callback para mudança de estado de diálogo."""
        console.print(f"[dim]   Dialog {dialog.id[:8]}... → {dialog.state.name}[/dim]")


# =============================================================================
# DEMONSTRAÇÕES
# =============================================================================


class SIPXDemo:
    """Classe principal para demonstrações."""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[Client] = None
        self.server: Optional[SIPServer] = None

    def print_header(self, title: str, subtitle: str = "") -> None:
        """Imprime cabeçalho de seção."""
        console.print("\n" + "=" * 80)
        console.print(f"[bold cyan]{title}[/bold cyan]")
        if subtitle:
            console.print(f"[dim]{subtitle}[/dim]")
        console.print("=" * 80 + "\n")

    def create_client(
        self, credentials: SipAuthCredentials, local_port: int = 5070
    ) -> Client:
        """Cria cliente SIP com handlers configurados."""

        # Criar cliente
        client = Client(
            local_host="0.0.0.0",
            local_port=local_port,
            transport=self.config.TRANSPORT,
            credentials=credentials,
        )

        # Adicionar handlers
        # 1. Authentication handler (necessário para auto-retry)
        client.add_handler(AuthenticationHandler(credentials))

        # 2. Flow handlers com callbacks
        client.add_handler(
            SipFlowHandler(
                state_manager=client.state_manager,
                on_ringing=DemoCallbacks.on_ringing,
                on_answered=DemoCallbacks.on_answered,
                on_confirmed=DemoCallbacks.on_confirmed,
                on_registered=DemoCallbacks.on_registered,
                on_unregistered=DemoCallbacks.on_unregistered,
            )
        )

        # 3. State tracking
        client.state_manager.on_transaction_state(
            TransactionState.PROCEEDING, DemoCallbacks.on_transaction_state_change
        )
        client.state_manager.on_transaction_state(
            TransactionState.COMPLETED, DemoCallbacks.on_transaction_state_change
        )
        client.state_manager.on_dialog_state(
            DialogState.CONFIRMED, DemoCallbacks.on_dialog_state_change
        )

        return client

    def demo_1_register(self) -> None:
        """Demo 1: Registro básico com autenticação."""
        self.print_header(
            "DEMO 1: REGISTER - Registro com Autenticação Digest",
            "Demonstra autenticação automática e retry com credenciais",
        )

        # Criar cliente
        client = self.create_client(self.config.USER_1111)

        try:
            # Registrar
            console.print("[bold]Registrando usuário 1111...[/bold]")
            response = client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
                port=self.config.ASTERISK_PORT,
                expires=3600,
            )

            # Verificar resultado
            if response.status_code == 200:
                console.print("\n[bold green]✅ Registro bem-sucedido![/bold green]")

                # Mostrar estatísticas
                stats = client.state_manager.get_statistics()

                table = Table(title="Estatísticas da Transação", box=box.ROUNDED)
                table.add_column("Métrica", style="cyan")
                table.add_column("Valor", style="green")

                table.add_row(
                    "Total de transações", str(stats["transactions"]["total"])
                )
                table.add_row("Total de diálogos", str(stats["dialogs"]["total"]))

                # Estados das transações
                for state, count in stats["transactions"]["by_state"].items():
                    table.add_row(f"  {state}", str(count))

                console.print("\n", table)
            else:
                console.print(
                    f"\n[bold red]❌ Registro falhou: {response.status_code}[/bold red]"
                )

        finally:
            client.close()
            time.sleep(self.config.WAIT_TIME)

    def demo_2_options(self) -> None:
        """Demo 2: Verificação de capacidades do servidor."""
        self.print_header(
            "DEMO 2: OPTIONS - Verificação de Capacidades",
            "Consulta métodos e codecs suportados pelo servidor",
        )

        client = self.create_client(self.config.USER_1111)

        try:
            console.print("[bold]Enviando OPTIONS...[/bold]")
            response = client.options(
                uri=f"sip:{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                port=self.config.ASTERISK_PORT,
            )

            if response.status_code == 200:
                console.print("\n[bold green]✅ OPTIONS bem-sucedido![/bold green]")

                # Mostrar capacidades
                table = Table(title="Capacidades do Servidor", box=box.ROUNDED)
                table.add_column("Header", style="cyan")
                table.add_column("Valor", style="green")

                if "Allow" in response.headers:
                    table.add_row("Allow (Métodos)", response.headers["Allow"])

                if "Accept" in response.headers:
                    table.add_row("Accept (Content-Types)", response.headers["Accept"])

                if "Supported" in response.headers:
                    table.add_row(
                        "Supported (Extensions)", response.headers["Supported"]
                    )

                console.print("\n", table)

        finally:
            client.close()
            time.sleep(self.config.WAIT_TIME)

    def demo_3_invite_full_flow(self) -> None:
        """Demo 3: Fluxo completo de INVITE (call)."""
        self.print_header(
            "DEMO 3: INVITE - Chamada Completa com SDP",
            "INVITE → 180 Ringing → 200 OK → ACK → BYE → 200 OK",
        )

        client = self.create_client(self.config.USER_1111, local_port=5070)

        try:
            # 1. Registrar primeiro
            console.print("[bold]Passo 1: Registrando usuário 1111...[/bold]")
            reg_response = client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
                port=self.config.ASTERISK_PORT,
            )

            if reg_response.status_code != 200:
                console.print("[bold red]❌ Registro falhou, abortando...[/bold red]")
                return

            time.sleep(1)

            # 2. Fazer chamada para echo test (extensão 100)
            console.print(
                "\n[bold]Passo 2: Chamando extensão 100 (Echo Test)...[/bold]"
            )

            # Criar SDP
            sdp = create_sdp_offer(local_ip=client.local_address.host, local_port=10000)

            console.print("\n[bold]SDP Offer:[/bold]")
            console.print(Panel(sdp, title="Local SDP", border_style="cyan"))

            # INVITE
            invite_response = client.invite(
                to_uri=f"sip:100@{self.config.ASTERISK_HOST}",
                from_uri=f"sip:1111@{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                port=self.config.ASTERISK_PORT,
                sdp_content=sdp,
            )

            if invite_response.status_code == 200:
                console.print("\n[bold green]✅ Chamada estabelecida![/bold green]")

                # Aguardar alguns segundos (simular conversação)
                console.print(
                    f"\n[bold yellow]⏱️  Mantendo chamada por {self.config.CALL_DURATION} segundos...[/bold yellow]"
                )

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Chamada ativa...", total=None)
                    time.sleep(self.config.CALL_DURATION)

                # 3. Desligar
                console.print("\n[bold]Passo 3: Encerrando chamada (BYE)...[/bold]")
                bye_response = client.bye()

                if bye_response.status_code == 200:
                    console.print(
                        "\n[bold green]✅ Chamada encerrada com sucesso![/bold green]"
                    )
                else:
                    console.print(
                        f"\n[bold red]❌ BYE falhou: {bye_response.status_code}[/bold red]"
                    )

            elif invite_response.status_code == 486:
                console.print(
                    "\n[bold yellow]⚠️  Busy Here - Extensão ocupada[/bold yellow]"
                )
            elif invite_response.status_code == 487:
                console.print(
                    "\n[bold yellow]⚠️  Request Terminated - Chamada cancelada[/bold yellow]"
                )
            else:
                console.print(
                    f"\n[bold red]❌ INVITE falhou: {invite_response.status_code}[/bold red]"
                )

        finally:
            client.close()
            time.sleep(self.config.WAIT_TIME)

    def demo_4_message(self) -> None:
        """Demo 4: Envio de mensagem instantânea (MESSAGE)."""
        self.print_header(
            "DEMO 4: MESSAGE - Mensagem Instantânea",
            "Envia mensagem de texto para outro usuário",
        )

        client = self.create_client(self.config.USER_1111)

        try:
            # Registrar
            console.print("[bold]Registrando usuário 1111...[/bold]")
            client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
            )

            time.sleep(1)

            # Enviar mensagem
            console.print("\n[bold]Enviando MESSAGE para usuário 2222...[/bold]")

            message_text = "Olá do SIPX! Esta é uma mensagem de teste. 👋"

            response = client.message(
                to_uri=f"sip:2222@{self.config.ASTERISK_HOST}",
                from_uri=f"sip:1111@{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                port=self.config.ASTERISK_PORT,
                content=message_text,
                content_type="text/plain; charset=utf-8",
            )

            if response.status_code == 200:
                console.print(
                    "\n[bold green]✅ Mensagem enviada com sucesso![/bold green]"
                )
                console.print(f"   Conteúdo: {message_text}")
            else:
                console.print(
                    f"\n[bold red]❌ MESSAGE falhou: {response.status_code}[/bold red]"
                )

        finally:
            client.close()
            time.sleep(self.config.WAIT_TIME)

    def demo_5_multiple_transports(self) -> None:
        """Demo 5: Demonstração de múltiplos transports."""
        self.print_header("DEMO 5: Múltiplos Transports", "Demonstra uso de UDP e TCP")

        for transport in ["UDP", "TCP"]:
            console.print(f"\n[bold cyan]Testando com {transport}...[/bold cyan]")

            # Criar config customizado
            old_transport = self.config.TRANSPORT
            self.config.TRANSPORT = transport

            client = self.create_client(
                self.config.USER_1111, local_port=5070 if transport == "UDP" else 5071
            )

            try:
                response = client.options(
                    uri=f"sip:{self.config.ASTERISK_HOST}",
                    host=self.config.ASTERISK_HOST,
                    port=self.config.ASTERISK_PORT,
                )

                if response.status_code == 200:
                    console.print(
                        f"[bold green]✅ {transport} funcionando![/bold green]"
                    )
                    console.print(f"   Transport info: {response.transport_info}")
                else:
                    console.print(
                        f"[bold red]❌ {transport} falhou: {response.status_code}[/bold red]"
                    )

            finally:
                client.close()
                self.config.TRANSPORT = old_transport
                time.sleep(1)

    def demo_6_state_management(self) -> None:
        """Demo 6: Demonstração de state management."""
        self.print_header(
            "DEMO 6: State Management", "Rastreamento de Transactions e Dialogs"
        )

        client = self.create_client(self.config.USER_1111)

        try:
            console.print("[bold]Criando múltiplas transações...[/bold]\n")

            # 1. REGISTER
            console.print("1. REGISTER...")
            client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
            )

            time.sleep(1)

            # 2. OPTIONS
            console.print("2. OPTIONS...")
            client.options(
                uri=f"sip:{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
            )

            time.sleep(1)

            # 3. MESSAGE
            console.print("3. MESSAGE...")
            client.message(
                to_uri=f"sip:2222@{self.config.ASTERISK_HOST}",
                from_uri=f"sip:1111@{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                content="Test message",
            )

            # Mostrar estatísticas finais
            console.print("\n[bold]Estatísticas Finais:[/bold]")
            stats = client.state_manager.get_statistics()

            table = Table(title="State Manager Statistics", box=box.DOUBLE)
            table.add_column("Categoria", style="cyan", no_wrap=True)
            table.add_column("Métrica", style="yellow")
            table.add_column("Valor", justify="right", style="green")

            table.add_row("Transactions", "Total", str(stats["transactions"]["total"]))
            for state, count in stats["transactions"]["by_state"].items():
                table.add_row("", state, str(count))

            table.add_row("Dialogs", "Total", str(stats["dialogs"]["total"]))
            for state, count in stats["dialogs"]["by_state"].items():
                table.add_row("", state, str(count))

            console.print("\n", table)

        finally:
            client.close()
            time.sleep(self.config.WAIT_TIME)

    def demo_7_server(self) -> None:
        """Demo 7: Servidor SIP recebendo requests."""
        self.print_header(
            "DEMO 7: SIP Server", "Servidor escutando e respondendo a requests"
        )

        console.print("[bold yellow]⚠️  Esta demo requer interação manual[/bold yellow]")
        console.print("O servidor ficará escutando por 30 segundos.")
        console.print("Use outro cliente SIP para enviar requests.\n")

        # Handler customizado para MESSAGE
        def handle_message(request: Request, source) -> Response:
            console.print(
                f"\n[bold green]📨 MESSAGE recebido de {source.host}:{source.port}[/bold green]"
            )

            if request.content:
                content = request.content.decode("utf-8", errors="ignore")
                console.print(
                    Panel(content, title="Conteúdo da Mensagem", border_style="green")
                )

            return Response(
                status_code=200,
                reason_phrase="OK",
                headers={
                    "Via": request.via or "",
                    "From": request.from_header or "",
                    "To": request.to_header or "",
                    "Call-ID": request.call_id or "",
                    "CSeq": request.cseq or "",
                    "Content-Length": "0",
                },
            )

        # Criar servidor
        server = SIPServer(
            local_host="0.0.0.0",
            local_port=5080,  # Porta diferente para não conflitar
        )

        # Registrar handler customizado
        server.register_handler("MESSAGE", handle_message)

        # Iniciar servidor
        console.print("[bold]Iniciando servidor na porta 5080...[/bold]")
        server.start()

        console.print("[bold green]✅ Servidor rodando![/bold green]")
        console.print("\nAguardando requests por 30 segundos...")
        console.print("Exemplo de comando para testar:")
        console.print("  [dim]# De outro terminal/máquina:[/dim]")
        console.print(
            f"  [cyan]# Enviar MESSAGE para sip:test@{self.config.ASTERISK_HOST}:5080[/cyan]\n"
        )

        # Aguardar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Servidor escutando...", total=None)
            time.sleep(30)

        # Parar servidor
        console.print("\n[bold]Parando servidor...[/bold]")
        server.stop()
        console.print("[bold green]✅ Servidor parado[/bold green]")

        time.sleep(self.config.WAIT_TIME)

    def demo_8_complete_workflow(self) -> None:
        """Demo 8: Workflow completo com múltiplos usuários."""
        self.print_header(
            "DEMO 8: Workflow Completo",
            "Simula cenário real: registro, chamada, mensagem, unregister",
        )

        client = self.create_client(self.config.USER_1111)

        try:
            # 1. Register
            console.print("[bold cyan]Etapa 1/5: Registro[/bold cyan]")
            reg = client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
                expires=1800,
            )
            console.print(f"Status: {reg.status_code}")
            time.sleep(2)

            # 2. Verificar server
            console.print("\n[bold cyan]Etapa 2/5: Verificação do Servidor[/bold cyan]")
            opts = client.options(
                uri=f"sip:{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
            )
            console.print(f"Status: {opts.status_code}")
            time.sleep(2)

            # 3. Enviar mensagem
            console.print("\n[bold cyan]Etapa 3/5: Enviar Mensagem[/bold cyan]")
            msg = client.message(
                to_uri=f"sip:2222@{self.config.ASTERISK_HOST}",
                from_uri=f"sip:1111@{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                content="Olá do workflow completo!",
            )
            console.print(f"Status: {msg.status_code}")
            time.sleep(2)

            # 4. Fazer chamada
            console.print("\n[bold cyan]Etapa 4/5: Chamada (Echo Test)[/bold cyan]")
            sdp = create_sdp_offer()
            inv = client.invite(
                to_uri=f"sip:100@{self.config.ASTERISK_HOST}",
                from_uri=f"sip:1111@{self.config.ASTERISK_HOST}",
                host=self.config.ASTERISK_HOST,
                sdp_content=sdp,
            )
            console.print(f"Status: {inv.status_code}")

            if inv.status_code == 200:
                time.sleep(3)
                bye = client.bye()
                console.print(f"BYE Status: {bye.status_code}")

            time.sleep(2)

            # 5. Unregister
            console.print("\n[bold cyan]Etapa 5/5: Unregister[/bold cyan]")
            unreg = client.register(
                aor=f"sip:1111@{self.config.ASTERISK_HOST}",
                registrar=self.config.ASTERISK_HOST,
                expires=0,  # Expires=0 para unregister
            )
            console.print(f"Status: {unreg.status_code}")

            # Summary
            console.print("\n[bold green]✅ Workflow Completo Finalizado![/bold green]")

            summary = Table(title="Resumo do Workflow", box=box.ROUNDED)
            summary.add_column("Operação", style="cyan")
            summary.add_column("Status", justify="center")

            summary.add_row("REGISTER", "✅" if reg.status_code == 200 else "❌")
            summary.add_row("OPTIONS", "✅" if opts.status_code == 200 else "❌")
            summary.add_row("MESSAGE", "✅" if msg.status_code == 200 else "❌")
            summary.add_row("INVITE", "✅" if inv.status_code == 200 else "❌")
            summary.add_row("UNREGISTER", "✅" if unreg.status_code == 200 else "❌")

            console.print("\n", summary)

        finally:
            client.close()

    def run_all_demos(self, skip_interactive: bool = False) -> None:
        """Executa todas as demos em sequência."""
        console.print(
            Panel.fit(
                "[bold cyan]SIPX - Demonstração Completa de Funcionalidades[/bold cyan]\n"
                f"Asterisk: {self.config.ASTERISK_HOST}:{self.config.ASTERISK_PORT}\n"
                f"Transport: {self.config.TRANSPORT}",
                border_style="cyan",
            )
        )

        demos = [
            ("REGISTER", self.demo_1_register),
            ("OPTIONS", self.demo_2_options),
            ("INVITE Flow", self.demo_3_invite_full_flow),
            ("MESSAGE", self.demo_4_message),
            ("Multiple Transports", self.demo_5_multiple_transports),
            ("State Management", self.demo_6_state_management),
            ("Complete Workflow", self.demo_8_complete_workflow),
        ]

        # Adicionar demo do servidor se não for skip interactive
        if not skip_interactive:
            demos.append(("SIP Server", self.demo_7_server))

        for i, (name, demo_func) in enumerate(demos, 1):
            try:
                console.print(
                    f"\n[bold yellow]>>> Executando Demo {i}/{len(demos)}: {name}[/bold yellow]"
                )
                demo_func()
                console.print(f"[bold green]✅ Demo {i} completa[/bold green]")
            except KeyboardInterrupt:
                console.print(
                    "\n[bold red]❌ Demo interrompida pelo usuário[/bold red]"
                )
                break
            except Exception as e:
                console.print(f"\n[bold red]❌ Erro na demo {i}: {e}[/bold red]")
                import traceback

                traceback.print_exc()

        console.print("\n" + "=" * 80)
        console.print("[bold green]🎉 Todas as demos finalizadas![/bold green]")
        console.print("=" * 80)


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="SIPX - Demonstração completa de funcionalidades com Asterisk"
    )

    parser.add_argument(
        "--asterisk-host",
        default="127.0.0.1",
        help="Endereço do servidor Asterisk (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--asterisk-port",
        type=int,
        default=5060,
        help="Porta do servidor Asterisk (default: 5060)",
    )

    parser.add_argument(
        "--transport",
        choices=["UDP", "TCP", "TLS"],
        default="UDP",
        help="Protocolo de transporte (default: UDP)",
    )

    parser.add_argument(
        "--demo", type=int, choices=range(1, 9), help="Executar demo específica (1-8)"
    )

    parser.add_argument(
        "--skip-interactive",
        action="store_true",
        help="Pular demos que requerem interação manual",
    )

    args = parser.parse_args()

    # Configurar
    config = Config()
    config.ASTERISK_HOST = args.asterisk_host
    config.ASTERISK_PORT = args.asterisk_port
    config.TRANSPORT = args.transport

    # Criar demo
    demo = SIPXDemo(config)

    try:
        if args.demo:
            # Executar demo específica
            demo_methods = [
                demo.demo_1_register,
                demo.demo_2_options,
                demo.demo_3_invite_full_flow,
                demo.demo_4_message,
                demo.demo_5_multiple_transports,
                demo.demo_6_state_management,
                demo.demo_7_server,
                demo.demo_8_complete_workflow,
            ]
            demo_methods[args.demo - 1]()
        else:
            # Executar todas as demos
            demo.run_all_demos(skip_interactive=args.skip_interactive)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Demo interrompida pelo usuário[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Erro fatal: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
