# SIPX - Quick Start Guide

Guia rápido para começar a usar o SIPX em 5 minutos.

---

## 📦 Instalação

### Requisitos

- Python 3.12+
- Docker (opcional, para testar com Asterisk)

### Instalar SIPX

```bash
# Clonar repositório
git clone <repo-url>
cd sipx

# Instalar com uv (recomendado)
uv sync

# Ou com pip
pip install -e .
```

---

## 🚀 Hello World SIP

### 1. Registro Básico

```python
from sipx import Client, SipAuthCredentials

# Criar credenciais
credentials = SipAuthCredentials(
    username="seu_usuario",
    password="sua_senha"
)

# Criar cliente
with Client(credentials=credentials) as client:
    # Registrar no servidor
    response = client.register(
        aor="sip:seu_usuario@sip.example.com",
        registrar="sip.example.com"
    )
    
    if response.status_code == 200:
        print("✅ Registrado com sucesso!")
    else:
        print(f"❌ Falha: {response.status_code}")
```

### 2. Fazer uma Chamada (INVITE)

```python
from sipx import Client, SipAuthCredentials

credentials = SipAuthCredentials(username="1111", password="pass")

with Client(credentials=credentials) as client:
    # Registrar
    client.register(aor="sip:1111@example.com", registrar="example.com")
    
    # SDP para áudio
    sdp = """v=0
o=- 123456 123456 IN IP4 192.168.1.100
s=Call
c=IN IP4 192.168.1.100
t=0 0
m=audio 10000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
"""
    
    # Fazer chamada
    response = client.invite(
        uri="sip:2222@example.com",
        host="example.com",
        sdp=sdp
    )
    
    if response.status_code == 200:
        print("✅ Chamada atendida!")
        
        # Aguardar alguns segundos
        import time
        time.sleep(10)
        
        # Desligar
        client.bye()
```

### 3. Enviar Mensagem (MESSAGE)

```python
from sipx import Client, SipAuthCredentials

credentials = SipAuthCredentials(username="1111", password="pass")

with Client(credentials=credentials) as client:
    # Registrar
    client.register(aor="sip:1111@example.com", registrar="example.com")
    
    # Enviar mensagem
    response = client.message(
        uri="sip:2222@example.com",
        host="example.com",
        content="Olá do SIPX! 👋",
        content_type="text/plain"
    )
    
    if response.status_code == 200:
        print("✅ Mensagem enviada!")
```

---

## 🎯 Usando com Asterisk Local

### 1. Iniciar Asterisk

```bash
# Navegar até diretório do Docker
cd docker/asterisk

# Iniciar Asterisk
docker-compose up -d

# Verificar se está rodando
docker ps | grep sipx-asterisk
```

### 2. Testar Registro

```python
from sipx import Client, SipAuthCredentials

# Usuário configurado no Asterisk
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx"
)

with Client(credentials=credentials) as client:
    response = client.register(
        aor="sip:1111@127.0.0.1",
        registrar="127.0.0.1",
        port=5060
    )
    
    print(f"Status: {response.status_code}")
    # Deve retornar: Status: 200
```

### 3. Testar Chamada (Echo Test)

```python
from sipx import Client, SipAuthCredentials
import time

credentials = SipAuthCredentials(username="1111", password="1111xxx")

with Client(credentials=credentials) as client:
    # Registrar
    client.register(aor="sip:1111@127.0.0.1", registrar="127.0.0.1")
    
    # Chamar extensão de echo (100)
    response = client.invite(
        uri="sip:100@127.0.0.1",
        host="127.0.0.1"
    )
    
    if response.status_code == 200:
        print("✅ Echo test conectado!")
        time.sleep(5)
        client.bye()
```

---

## 🔧 Usando Handlers

Handlers permitem processar eventos SIP de forma modular.

### Handler Básico

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import InviteFlowHandler

# Callbacks
def on_ringing(response, context):
    print("📞 Tocando...")

def on_answered(response, context):
    print("✅ Atendeu!")

# Criar cliente
credentials = SipAuthCredentials(username="1111", password="1111xxx")
client = Client(credentials=credentials)

# Adicionar handler
invite_handler = InviteFlowHandler(
    on_ringing=on_ringing,
    on_answered=on_answered
)
client.add_handler(invite_handler)

# Usar normalmente - callbacks serão chamados automaticamente
client.register(aor="sip:1111@127.0.0.1", registrar="127.0.0.1")
response = client.invite("sip:100@127.0.0.1", "127.0.0.1")

client.close()
```

### Handler Completo (All-in-One)

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import SipFlowHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")
client = Client(credentials=credentials)

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
client.register(aor="sip:1111@127.0.0.1", registrar="127.0.0.1")
client.invite("sip:100@127.0.0.1", "127.0.0.1")
```

---

## 🖥️ Servidor SIP

Receber requests SIP de outros clientes.

```python
from sipx import SIPServer, Request, Response
import time

# Handler customizado
def handle_message(request: Request, source) -> Response:
    print(f"📨 Mensagem recebida de {source.host}:{source.port}")
    
    if request.content:
        print(f"Conteúdo: {request.content.decode()}")
    
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
server = SIPServer(local_host="0.0.0.0", local_port=5060)

# Registrar handler
server.register_handler("MESSAGE", handle_message)

# Iniciar
server.start()
print("Servidor rodando em 0.0.0.0:5060")

# Aguardar
time.sleep(60)

# Parar
server.stop()
```

---

## 🎓 Exemplos Completos

### Demo Completa

Execute a demo que mostra TODAS as funcionalidades:

```bash
# Navegar até examples
cd examples

# Executar demo completa
python asterisk_complete_demo.py

# Ou demo específica
python asterisk_complete_demo.py --demo 1
```

**Demos disponíveis**:
1. REGISTER - Registro com autenticação
2. OPTIONS - Verificação de capacidades
3. INVITE Flow - Chamada completa
4. MESSAGE - Mensagem instantânea
5. Multiple Transports - UDP vs TCP
6. State Management - Tracking de transações
7. SIP Server - Servidor escutando
8. Complete Workflow - Workflow completo

---

## 📚 Próximos Passos

1. **Leia a documentação completa**:
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitetura do sistema
   - [MODULES.md](MODULES.md) - Documentação de módulos
   - [examples/README.md](../examples/README.md) - Guia de exemplos

2. **Explore os handlers**:
   - [HANDLERS_REFACTORING.md](HANDLERS_REFACTORING.md) - Sistema de handlers
   - [HANDLERS_QUICK_REFERENCE.md](HANDLERS_QUICK_REFERENCE.md) - Referência rápida

3. **Execute os exemplos**:
   ```bash
   cd examples
   python asterisk_complete_demo.py
   ```

4. **Customize para seu caso de uso**:
   - Crie handlers personalizados
   - Implemente lógica de negócio
   - Integre com seu sistema

---

## 🆘 Ajuda

### Problemas Comuns

**Connection refused**:
```bash
# Verificar se Asterisk está rodando
docker ps | grep sipx-asterisk

# Iniciar se necessário
cd docker/asterisk
docker-compose up -d
```

**401 Unauthorized**:
- Verifique username/password
- Confirme que usuário está configurado no Asterisk
- Veja logs: `docker-compose logs asterisk`

**Timeout**:
- Aumente o timeout:
  ```python
  from sipx import TransportConfig
  config = TransportConfig(read_timeout=60.0)
  client = Client(config=config)
  ```

### Debug

Ative debug para ver mensagens SIP:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Mensagens SIP serão exibidas no console
```

### Ferramentas Úteis

- **sngrep**: Visualizador de tráfego SIP
  ```bash
  sudo sngrep port 5060
  ```

- **Wireshark**: Análise de pacotes
  ```bash
  sudo wireshark -k -i any -f "port 5060"
  ```

---

## 📖 Referências

- [RFC 3261 - SIP](https://datatracker.ietf.org/doc/html/rfc3261)
- [RFC 2617 - Digest Authentication](https://datatracker.ietf.org/doc/html/rfc2617)
- [RFC 4566 - SDP](https://datatracker.ietf.org/doc/html/rfc4566)

---

**Pronto para começar! 🚀**

Execute `python examples/asterisk_complete_demo.py` e veja tudo funcionando!