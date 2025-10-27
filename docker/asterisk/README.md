# Asterisk Docker para Testes SIPX

Container Docker com Asterisk configurado para testar a biblioteca SIPX com 3 políticas de autenticação diferentes.

**Versão**: 2.0.0  
**Asterisk**: 18+  
**Status**: ✅ Produção

## 🚀 Como Usar

### 1. Build e Start

```bash
cd docker/asterisk
docker-compose up -d --build
```

### 2. Verificar Logs

```bash
docker-compose logs -f
```

### 3. Conectar ao CLI do Asterisk

```bash
docker exec -it sipx-asterisk asterisk -rvvv
```

### 4. Verificar Registro

No CLI do Asterisk:
```
pjsip show endpoints
pjsip show registrations
pjsip show contacts
```

## 📞 Usuários Configurados

### Políticas de Autenticação

Este setup possui **3 usuários com políticas diferentes** para testar diversos cenários de autenticação:

| Username | Password | Política | Porta Cliente | Contexto |
|----------|----------|----------|---------------|----------|
| **1111** | 1111xxx  | 🔐 **Auth para TODOS os métodos** | 5061 | sipx-test |
| **2222** | 2222xxx  | 🔓 **OPTIONS sem auth, outros com auth** | 5062 | sipx-test |
| **3333** | 3333xxx  | 🚫 **OPTIONS rejeitado, strict security** | 5063 | sipx-test |

### Detalhes das Políticas

#### 🔐 Usuário 1111 - Autenticação Completa
- Requer autenticação para **todos** os métodos (OPTIONS, REGISTER, INVITE)
- Ideal para testar fluxo completo de autenticação
- Usado para testar `retry_with_auth()` em todos os cenários

#### 🔓 Usuário 2222 - OPTIONS Aberto (Relaxed)
- **OPTIONS**: Aceita sem autenticação (para health checks)
- **REGISTER/INVITE**: Requer autenticação
- Ideal para testar servidores que permitem OPTIONS sem credenciais
- Usado para testar:
  - INVITE com late offer (SDP answer)
  - Early media detection (183 Session Progress)
  - Codec negotiation

#### 🚫 Usuário 3333 - Segurança Restritiva (Paranoid)
- **OPTIONS**: Rejeitado (403 Forbidden)
- **REGISTER/INVITE**: Requer autenticação
- Ideal para testar:
  - Credenciais inválidas (403)
  - Políticas de segurança estritas
  - Auto re-registration com threading
  - Handling de rejeições

## 🔧 Configuração do Cliente SIPX

### Exemplo Básico

```python
from sipx import Client, Auth

# Credenciais
auth = Auth.Digest(username="1111", password="1111xxx")

# Cliente (use porta diferente de 5060!)
with Client(local_port=5061, auth=auth) as client:
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"Status: {response.status_code}")
```

**Importante**: 
- Cliente usa porta **5061+** (não 5060)
- Servidor Asterisk usa porta **5060**
- Evita conflito "Address already in use"

## 🧪 Testes Disponíveis

### Echo Test
Disque `100` para testar áudio (echo)

### Music on Hold
Disque `200` para ouvir música

### Voicemail Test
Disque `300` para ouvir mensagem de voicemail

### Time Announcement
Disque `400` para ouvir o horário

### Conference Room
Disque `500` para entrar em sala de conferência

### Chamadas Entre Extensões
Disque `1111`, `2222` ou `3333` para chamar outros usuários

## ⚠️ Notas Importantes

### Portas

- **Asterisk Docker**: Porta `5060` (UDP/TCP)
- **Cliente SIPX**: Use portas `5061`, `5062`, `5063` etc
- **Motivo**: Evitar conflito "Address already in use"

### Autenticação

A biblioteca SIPX v2.0 usa **autenticação manual explícita**:

```python
# Enviar request
response = client.register(aor="sip:1111@127.0.0.1")

# Verificar se precisa autenticação
if response.status_code == 401:
    # Retry com autenticação
    response = client.retry_with_auth(response)
```

**Não há retry automático** - você controla quando e como autenticar.

## 📊 Monitoramento

### Ver chamadas ativas
```bash
docker exec sipx-asterisk asterisk -rx "core show channels"
```

### Ver endpoints registrados
```bash
docker exec sipx-asterisk asterisk -rx "pjsip show endpoints"
```

### Debug SIP
```bash
docker exec sipx-asterisk asterisk -rx "pjsip set logger on"
```

### Ver logs em tempo real
```bash
docker exec sipx-asterisk tail -f /var/log/asterisk/messages
```

## 🛑 Parar e Remover

```bash
# Parar containers
docker-compose down

# Parar e remover volumes (limpa dados)
docker-compose down -v
```

## 🔍 Troubleshooting

### RTP não funciona
- Verifique se as portas 10000-10099/udp estão abertas
- Use `network_mode: host` no docker-compose.yml (já configurado)
- No Windows, pode ser necessário usar portas mapeadas em vez de host mode

### Autenticação falha
- Verifique username/password em `config/pjsip.conf`
- Veja logs: `docker-compose logs asterisk`
- Confirme que o cliente está usando as credenciais corretas

### Sem áudio em chamadas
- Configure `direct_media=no` em pjsip.conf (já configurado)
- Verifique NAT settings em rtp.conf
- Teste com `100` (echo test) para verificar fluxo RTP

### Container não inicia
- Verifique se a porta 5060 não está em uso: `netstat -an | findstr 5060` (Windows)
- Veja logs detalhados: `docker-compose logs asterisk`
- Rebuilde a imagem: `docker-compose build --no-cache`

### Chamadas caem imediatamente
- Verifique dialplan em `config/extensions.conf`
- Confirme que o contexto está correto (`sipx-test`)
- Veja logs do Asterisk no CLI: `asterisk -rvvv`

## 📝 Comandos Úteis do Asterisk CLI

```bash
# Conectar ao CLI
docker exec -it sipx-asterisk asterisk -rvvv

# Dentro do CLI:
pjsip show endpoints          # Lista endpoints
pjsip show registrations      # Lista registros ativos
pjsip show contacts           # Lista contatos
core show channels            # Mostra chamadas ativas
dialplan show sipx-test       # Mostra dialplan do contexto
pjsip set logger on           # Ativa debug SIP
pjsip set logger off          # Desativa debug SIP
core reload                   # Recarrega configurações
core restart now              # Reinicia Asterisk

# Sair do CLI: Ctrl+C ou 'exit'
```

## 🧪 Testando com SIPX

### Demo Completo (Recomendado) ⭐

Execute o demo completo com interface Rich que testa todos os 3 usuários:

```bash
uv run examples/asterisk_demo.py
```

**Este demo executa 16 testes**:

#### User 1111 (5 testes)
- ✅ OPTIONS com autenticação
- ✅ REGISTER (expires=3600)
- ✅ REGISTER update (expires=1800)
- ✅ INVITE com create_offer (early offer)
- ✅ UNREGISTER

#### User 2222 (5 testes)
- ✅ OPTIONS sem autenticação
- ✅ REGISTER
- ✅ INVITE com create_answer (late offer)
- ✅ Early media detection (183)
- ✅ UNREGISTER

#### User 3333 (6 testes)
- ❌ OPTIONS (deve ser rejeitado - esperado)
- ✅ REGISTER com credenciais inválidas (deve falhar)
- ✅ REGISTER com credenciais válidas
- ✅ INVITE
- ✅ Auto re-registration (5s interval)
- ✅ UNREGISTER

**Resultado esperado**: 15/16 testes passam (1 falha intencional)

### Exemplo 1: Registro Simples

```python
from sipx import Client, Auth

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Fazer registro
    response = client.register(aor="sip:1111@127.0.0.1")
    
    # Tratar autenticação
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    print(f"Registro: {response.status_code} {response.reason_phrase}")
```

### Exemplo 2: Chamada para Echo Test

```python
from sipx import Client, Auth, SDPBody
import time

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Criar SDP offer
    sdp_offer = SDPBody.create_offer(
        session_name="Echo Test",
        origin_username="1111",
        origin_address=client.local_address.host,
        connection_address=client.local_address.host,
        media_specs=[{
            "media": "audio",
            "port": 8000,
            "codecs": [
                {"payload": "0", "name": "PCMU", "rate": "8000"},
                {"payload": "8", "name": "PCMA", "rate": "8000"},
            ]
        }]
    )
    
    # Chamar extensão 100 (echo test)
    response = client.invite(
        to_uri="sip:100@127.0.0.1",
        from_uri=f"sip:1111@{client.local_address.host}",
        body=sdp_offer.to_string(),
        headers={"Contact": f"<sip:1111@{client.local_address.host}:5061>"}
    )
    
    # Autenticação
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    if response.status_code == 200:
        print(f"✅ INVITE: {response.status_code}")
        client.ack(response=response)
        time.sleep(5)
        client.bye(response=response)
```

### Exemplo 3: Auto Re-Registration

```python
from sipx import Client, Auth
import time

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Registrar inicialmente
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    # Ativar auto re-registration (threading.Timer)
    client.enable_auto_reregister(
        aor="sip:1111@127.0.0.1",
        interval=300  # Re-registrar a cada 5 minutos
    )
    
    print("✅ Auto re-registration habilitado")
    
    # Manter rodando (re-registro acontece automaticamente)
    time.sleep(600)  # 10 minutos
    
    # Desabilitar e remover registro
    client.disable_auto_reregister()
    response = client.unregister(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
```

### Exemplo 4: Early Media Detection (183)

```python
from sipx import Client, Auth, Events, event_handler, SDPBody
from sipx._types import Response, RequestContext

class EarlyMediaEvents(Events):
    def __init__(self):
        super().__init__()
        self.early_media_detected = False
    
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        if response.status_code == 183:
            print("🎵 Early Media (183 Session Progress)")
            self.early_media_detected = True
            
            if response.body:
                codecs = response.body.get_codecs_summary()
                print(f"   Codecs: {', '.join(codecs)}")
        
        return response

auth = Auth.Digest(username="2222", password="2222xxx")
events = EarlyMediaEvents()

with Client(local_port=5062, auth=auth, events=events) as client:
    # INVITE sem SDP (late offer)
    response = client.invite(
        to_uri="sip:100@127.0.0.1",
        from_uri=f"sip:2222@{client.local_address.host}",
        body=None,
        headers={"Contact": f"<sip:2222@{client.local_address.host}:5062>"}
    )
    
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    if events.early_media_detected:
        print("✅ Early media foi detectado!")
```

### Exemplo 5: Event Handlers Customizados

```python
from sipx import Client, Auth, Events, event_handler
from sipx._types import Request, Response, RequestContext

class CustomEvents(Events):
    """Event handlers com Rich console output"""
    
    @event_handler("request")
    def on_request(self, request: Request, context: RequestContext):
        print(f"📤 {request.method} → {request.uri}")
        return request
    
    @event_handler("response")
    def on_response(self, response: Response, context: RequestContext):
        if response.status_code >= 200 and response.status_code < 300:
            print(f"✅ {response.status_code} {response.reason_phrase}")
        elif response.status_code == 401:
            print(f"🔐 401 Unauthorized")
        else:
            print(f"❌ {response.status_code} {response.reason_phrase}")
        return response

auth = Auth.Digest(username="1111", password="1111xxx")
events = CustomEvents()

with Client(local_port=5061, auth=auth, events=events) as client:
    # Requests acionam os event handlers automaticamente
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    # Output:
    # 📤 REGISTER → sip:1111@127.0.0.1
    # 🔐 401 Unauthorized
    # 📤 REGISTER → sip:1111@127.0.0.1
    # ✅ 200 OK
```

## 🔧 Estrutura dos Arquivos

```
asterisk-docker/
├── Dockerfile              # Imagem Docker do Asterisk
├── docker-compose.yml      # Orquestração do container
├── config/
│   ├── pjsip.conf         # Configuração PJSIP (usuários, transports)
│   ├── extensions.conf    # Dialplan (rotas de chamadas)
│   ├── rtp.conf           # Configuração RTP (portas de áudio)
│   └── modules.conf       # Módulos carregados
└── README.md              # Este arquivo
```

## 🎯 Próximos Passos

1. **Testar Registro**: Execute o script de registro básico
2. **Testar Echo**: Chame a extensão 100 para validar RTP
3. **Testar Chamadas**: Faça chamadas entre 1111, 2222 e 3333
4. **Monitorar Logs**: Use `pjsip set logger on` para debug detalhado
5. **Validar ACK**: Verifique envio de ACK com sngrep ou logs

## 📚 Recursos Adicionais

- [Asterisk Official Docs](https://docs.asterisk.org/)
- [PJSIP Configuration](https://wiki.asterisk.org/wiki/display/AST/Configuring+res_pjsip)
- [Dialplan Basics](https://wiki.asterisk.org/wiki/display/AST/Dialplan)
- [RFC 3261 - SIP](https://datatracker.ietf.org/doc/html/rfc3261)

## 🐛 Debug Avançado

### Capturar tráfego SIP com tcpdump

```bash
# No host (não no container)
sudo tcpdump -i any -s 0 -A 'port 5060'
```

### Usar sngrep para visualizar fluxo SIP

```bash
# Instalar sngrep (Ubuntu/Debian)
sudo apt-get install sngrep

# Executar
sudo sngrep port 5060
```

### Logs detalhados do Asterisk

Edite `config/modules.conf` e adicione:
```ini
load => logger.so
```

Crie `config/logger.conf`:
```ini
[general]
dateformat=%F %T

[logfiles]
console => notice,warning,error,debug,verbose
messages => notice,warning,error,verbose
full => notice,warning,error,debug,verbose
```

## 📚 Recursos Adicionais

- **[examples/README.md](../../examples/README.md)** - Guia de exemplos
- **[docs/QUICK_START.md](../../docs/QUICK_START.md)** - Início rápido
- **[docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)** - Arquitetura
- **[docs/GUIA_WSL_ASTERISK.md](../../docs/GUIA_WSL_ASTERISK.md)** - Guia WSL

---

## 📄 Licença

MIT License - Este setup é fornecido como exemplo para testes.

---

**Versão**: 2.0.0  
**Última Atualização**: Outubro 2025  
**Status**: ✅ Produção