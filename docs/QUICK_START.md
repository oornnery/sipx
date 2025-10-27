# SIPX - Guia de Início Rápido

Comece a usar o SIPX em minutos!

**Versão**: 2.0.0  
**Data**: Outubro 2025

---

## 📋 Índice

- [Instalação](#instalação)
- [Primeiro Exemplo](#primeiro-exemplo)
- [Registro SIP](#registro-sip)
- [Fazendo uma Chamada](#fazendo-uma-chamada)
- [Autenticação](#autenticação)
- [Event Handlers](#event-handlers)
- [Próximos Passos](#próximos-passos)

---

## 🚀 Instalação

### Requisitos

- Python 3.12+
- pip ou uv

### Instalar SIPX

```bash
# Com pip
pip install sipx

# Com uv (recomendado)
uv add sipx

# Ou clone do repositório
git clone https://github.com/seu-usuario/sipx.git
cd sipx
uv sync
```

### Verificar Instalação

```bash
python -c "import sipx; print(sipx.__version__)"
```

---

## 🎯 Primeiro Exemplo

### Hello SIP - OPTIONS Request

```python
from sipx import Client

# Criar cliente
with Client(local_port=5061) as client:
    # Enviar OPTIONS
    response = client.options(
        uri="sip:example.com",
        host="example.com"
    )
    
    print(f"Status: {response.status_code} {response.reason_phrase}")
    
    # Ver métodos suportados
    if "Allow" in response.headers:
        methods = response.headers["Allow"]
        print(f"Métodos: {methods}")
```

**Saída esperada**:
```
Status: 200 OK
Métodos: INVITE, ACK, BYE, CANCEL, OPTIONS, MESSAGE, SUBSCRIBE, NOTIFY, REFER
```

---

## 📞 Registro SIP

### Exemplo Básico

```python
from sipx import Client, Auth

# Credenciais
auth = Auth.Digest(
    username="1111",
    password="1111xxx",
    realm="asterisk"
)

# Cliente
with Client(local_port=5061, auth=auth) as client:
    # Registrar
    response = client.register(aor="sip:1111@127.0.0.1")
    
    # Verificar resposta
    if response.status_code == 401:
        # Retry com autenticação
        response = client.retry_with_auth(response)
    
    if response.status_code == 200:
        print("✅ Registrado com sucesso!")
        expires = response.headers.get("Expires", "unknown")
        print(f"Expira em: {expires} segundos")
    else:
        print(f"❌ Falha: {response.status_code}")
```

### Com Auto Re-registration

```python
from sipx import Client, Auth
import time

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Registro inicial
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    # Habilitar auto re-registro (a cada 5 minutos)
    client.enable_auto_reregister(
        aor="sip:1111@127.0.0.1",
        interval=300
    )
    
    print("✅ Registrado com auto-renewal")
    
    # Fazer outras coisas...
    time.sleep(600)  # 10 minutos
    
    # Auto re-registro acontece automaticamente
```

---

## 📱 Fazendo uma Chamada

### INVITE Básico

```python
from sipx import Client, Auth, SDPBody

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Criar SDP offer
    sdp_offer = SDPBody.create_offer(
        session_name="My Call",
        origin_username="1111",
        origin_address=client.local_address.host,
        connection_address=client.local_address.host,
        media_specs=[
            {
                "media": "audio",
                "port": 8000,
                "codecs": [
                    {"payload": "0", "name": "PCMU", "rate": "8000"},
                    {"payload": "8", "name": "PCMA", "rate": "8000"},
                ],
            }
        ],
    )
    
    # Enviar INVITE
    response = client.invite(
        to_uri="sip:100@127.0.0.1",
        from_uri=f"sip:1111@{client.local_address.host}",
        body=sdp_offer.to_string(),
        headers={
            "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
        }
    )
    
    # Tratar autenticação
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    # Verificar sucesso
    if response.status_code == 200:
        print("✅ Chamada aceita!")
        
        # Enviar ACK
        client.ack(response=response)
        
        # Chamada ativa...
        import time
        time.sleep(5)
        
        # Encerrar chamada
        client.bye(response=response)
        print("✅ Chamada encerrada")
```

### INVITE com Late Offer (SDP Answer)

```python
from sipx import Client, Auth, SDPBody

auth = Auth.Digest(username="2222", password="2222xxx")

with Client(local_port=5062, auth=auth) as client:
    # INVITE sem SDP (late offer)
    response = client.invite(
        to_uri="sip:100@127.0.0.1",
        from_uri=f"sip:2222@{client.local_address.host}",
        body=None,  # Sem SDP
        headers={
            "Contact": f"<sip:2222@{client.local_address.host}:{client.local_address.port}>"
        }
    )
    
    # Autenticação
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    # Processar resposta
    if response.status_code == 200 and response.body:
        # Criar SDP answer
        sdp_answer = SDPBody.create_answer(
            offer=response.body,
            origin_username="2222",
            origin_address=client.local_address.host,
            connection_address=client.local_address.host,
        )
        
        # ACK com SDP answer
        client.ack(response=response)
        
        print("✅ Chamada aceita com SDP answer")
```

---

## 🔐 Autenticação

### Digest Authentication

```python
from sipx import Client, Auth

# Método 1: Auth no construtor do Client
auth = Auth.Digest(username="1111", password="1111xxx")
client = Client(local_port=5061, auth=auth)

# Método 2: Auth por request
response = client.register(aor="sip:1111@127.0.0.1")
if response.status_code == 401:
    custom_auth = Auth.Digest(username="1111", password="1111xxx")
    response = client.retry_with_auth(response, auth=custom_auth)
```

### Retry Manual

```python
from sipx import Client, Auth

auth = Auth.Digest(username="1111", password="1111xxx")
client = Client(local_port=5061, auth=auth)

# Enviar request
response = client.options(uri="sip:127.0.0.1", host="127.0.0.1")

# Verificar se precisa autenticação
if response.status_code == 401 or response.status_code == 407:
    # Retry com autenticação
    response = client.retry_with_auth(response)
    
if response.status_code == 200:
    print("✅ Autenticado e aceito")
```

### Credenciais Diferentes por Request

```python
from sipx import Client, Auth

client = Client(local_port=5061)

# Auth para REGISTER
register_auth = Auth.Digest(username="1111", password="1111xxx")
response = client.register(aor="sip:1111@127.0.0.1")
if response.status_code == 401:
    response = client.retry_with_auth(response, auth=register_auth)

# Auth diferente para INVITE
invite_auth = Auth.Digest(username="2222", password="2222xxx")
response = client.invite(to_uri="sip:100@127.0.0.1")
if response.status_code == 401:
    response = client.retry_with_auth(response, auth=invite_auth)
```

---

## 🎭 Event Handlers

### Criar Custom Event Handler

```python
from sipx import Client, Auth, Events, event_handler
from sipx._types import RequestContext, Request, Response

class MyEvents(Events):
    """Custom event handlers"""
    
    @event_handler("request")
    def on_request(self, request: Request, context: RequestContext):
        """Chamado antes de enviar request"""
        print(f"📤 Enviando {request.method} → {request.uri}")
        return request
    
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        """Chamado ao receber response"""
        if response.status_code >= 200 and response.status_code < 300:
            print(f"✅ {response.status_code} {response.reason_phrase}")
        elif response.status_code == 401:
            print(f"🔐 Autenticação necessária")
        else:
            print(f"❌ {response.status_code} {response.reason_phrase}")
        return response
    
    @event_handler("auth_challenge")
    def on_auth(self, response: Response, context: RequestContext):
        """Chamado ao receber 401/407"""
        print(f"🔐 Challenge recebido: realm={response.headers.get('WWW-Authenticate')}")
        return response
```

### Usar Event Handler

```python
from sipx import Client, Auth

auth = Auth.Digest(username="1111", password="1111xxx")
events = MyEvents()

with Client(local_port=5061, auth=auth, events=events) as client:
    # Requests irão acionar os event handlers
    response = client.options(uri="sip:127.0.0.1", host="127.0.0.1")
    
    # Output:
    # 📤 Enviando OPTIONS → sip:127.0.0.1
    # 🔐 Autenticação necessária
    # 🔐 Challenge recebido: realm=Digest realm="asterisk",...
    # 📤 Enviando OPTIONS → sip:127.0.0.1
    # ✅ 200 OK
```

### Event Handler com Early Media

```python
from sipx import Events, event_handler, Response
from sipx._types import RequestContext

class CallEvents(Events):
    def __init__(self):
        super().__init__()
        self.early_media_detected = False
    
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        """Detectar early media (183)"""
        if response.status_code == 183:
            print("🎵 Early Media (183 Session Progress)")
            self.early_media_detected = True
            
            # Analisar SDP
            if response.body:
                codecs = response.body.get_codecs_summary()
                print(f"   Codecs: {', '.join(codecs)}")
        
        return response
```

---

## 🔄 Cliente Assíncrono

### AsyncClient Básico

```python
import asyncio
from sipx import AsyncClient, Auth

async def main():
    auth = Auth.Digest(username="1111", password="1111xxx")
    
    async with AsyncClient(local_port=5061, auth=auth) as client:
        # Registro
        response = await client.register(aor="sip:1111@127.0.0.1")
        if response.status_code == 401:
            response = await client.retry_with_auth(response)
        
        print(f"Status: {response.status_code}")
        
        # OPTIONS
        response = await client.options(uri="sip:127.0.0.1", host="127.0.0.1")
        print(f"OPTIONS: {response.status_code}")

# Executar
asyncio.run(main())
```

### Auto Re-registration Assíncrono

```python
import asyncio
from sipx import AsyncClient, Auth

async def main():
    auth = Auth.Digest(username="1111", password="1111xxx")
    
    async with AsyncClient(local_port=5061, auth=auth) as client:
        # Registro inicial
        response = await client.register(aor="sip:1111@127.0.0.1")
        if response.status_code == 401:
            response = await client.retry_with_auth(response)
        
        # Habilitar auto re-registro (usa asyncio.Task)
        await client.enable_auto_reregister(
            aor="sip:1111@127.0.0.1",
            interval=300
        )
        
        print("✅ Auto re-registro habilitado")
        
        # Aguardar (re-registro acontece em background)
        await asyncio.sleep(600)

asyncio.run(main())
```

---

## 📨 Enviando Mensagens

### MESSAGE (Instant Messaging)

```python
from sipx import Client, Auth

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Enviar mensagem
    response = client.message(
        to_uri="sip:2222@127.0.0.1",
        text="Hello from SIPX!",
    )
    
    # Autenticação se necessário
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    if response.status_code == 200:
        print("✅ Mensagem enviada")
    else:
        print(f"❌ Falha: {response.status_code}")
```

---

## 🛠️ Configuração Avançada

### Transport Personalizado

```python
from sipx import Client

# TCP transport
client = Client(
    local_host="192.168.1.100",
    local_port=5060,
    transport="TCP"
)

# UDP transport (padrão)
client = Client(
    local_host="0.0.0.0",
    local_port=5060,
    transport="UDP"
)
```

### Timeouts Personalizados

```python
from sipx import Client

client = Client(local_port=5061)

# Timeout específico por request
response = client.options(
    uri="sip:example.com",
    host="example.com",
    timeout=10.0  # 10 segundos
)
```

---

## 🧪 Testando com Asterisk Local

### Setup Rápido

```bash
# 1. Iniciar Asterisk Docker
cd docker/asterisk
docker-compose up -d

# 2. Verificar se está rodando
docker ps | grep asterisk

# 3. Ver logs
docker logs -f sipx-asterisk
```

### Teste Completo

```python
from sipx import Client, Auth

# Usuário configurado no Asterisk
auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # 1. REGISTER
    print("1. Registrando...")
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"   ✅ {response.status_code}")
    
    # 2. OPTIONS
    print("2. Verificando servidor...")
    response = client.options(uri="sip:127.0.0.1", host="127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"   ✅ {response.status_code}")
    
    # 3. MESSAGE
    print("3. Enviando mensagem...")
    response = client.message(
        to_uri="sip:2222@127.0.0.1",
        text="Hello from SIPX!"
    )
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"   ✅ {response.status_code}")
    
    print("\n✅ Todos os testes passaram!")
```

---

## 🎓 Próximos Passos

### Documentação Completa

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Entenda a arquitetura do SIPX
2. **[MODULES.md](MODULES.md)** - Documentação detalhada de cada módulo
3. **[API.md](API.md)** - Referência completa da API
4. **[examples/README.md](../examples/README.md)** - Mais exemplos práticos

### Exemplos Avançados

```bash
# Demo completo com 3 usuários
uv run examples/asterisk_demo.py

# Ver código dos exemplos
ls examples/
```

### Tutoriais

- **Registro e autenticação**: `examples/simple_example.py`
- **Chamadas INVITE**: Ver ARCHITECTURE.md seção "Fluxo de Mensagens"
- **Event handlers**: Ver seção acima
- **SDP parsing**: `docs/MODULES.md` seção "SDPBody"

### Ferramentas Úteis

- **sngrep**: Visualizador de tráfego SIP
  ```bash
  sudo apt-get install sngrep
  sudo sngrep port 5060
  ```

- **tcpdump**: Captura de pacotes
  ```bash
  sudo tcpdump -i any -s 0 -A 'port 5060'
  ```

### Comunidade

- GitHub Issues: Reporte bugs
- Pull Requests: Contribua com código
- Documentação: Ajude a melhorar

---

## 💡 Dicas

### ✅ Boas Práticas

1. **Sempre use context manager**:
   ```python
   with Client(...) as client:
       # código
   # Transport fechado automaticamente
   ```

2. **Trate autenticação explicitamente**:
   ```python
   if response.status_code == 401:
       response = client.retry_with_auth(response)
   ```

3. **Use portas diferentes do servidor**:
   ```python
   # Servidor usa 5060, cliente usa 5061+
   client = Client(local_port=5061)
   ```

4. **Sempre envie ACK após 200 OK do INVITE**:
   ```python
   response = client.invite(...)
   if response.status_code == 200:
       client.ack(response=response)
   ```

5. **Passe response para BYE**:
   ```python
   # Correto
   client.bye(response=invite_response)
   
   # Incorreto
   client.bye(to_uri="...", from_uri="...")  # Falta informação do diálogo
   ```

### ❌ Erros Comuns

1. **Porta em uso**:
   ```
   Error: Address already in use
   Solução: Use porta diferente (5061, 5062, etc)
   ```

2. **401 persistente**:
   ```
   Error: Always receiving 401
   Solução: Verifique username/password, chame retry_with_auth()
   ```

3. **BYE falhando**:
   ```
   Error: Either response or dialog_id must be provided
   Solução: Passe response do INVITE: client.bye(response=response)
   ```

4. **Headers fora de ordem**:
   ```
   Já corrigido! SIPX agora usa ordenação RFC 3261 automática.
   ```

---

## 📄 Licença

MIT License - Veja LICENSE no diretório raiz do projeto.

---

**Versão**: 2.0.0  
**Última Atualização**: Outubro 2025  
**Pronto para usar**: ✅ Sim!