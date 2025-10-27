# SIPX - Exemplos

Este diretório contém exemplos práticos de uso da biblioteca SIPX.

## 📋 Índice

- [Pré-requisitos](#pré-requisitos)
- [Exemplos Disponíveis](#exemplos-disponíveis)
- [Setup do Asterisk](#setup-do-asterisk)
- [Executando os Exemplos](#executando-os-exemplos)
- [Troubleshooting](#troubleshooting)

---

## 🔧 Pré-requisitos

### Software Necessário

1. **Python 3.12+**
   ```bash
   python --version  # Deve ser >= 3.12
   ```

2. **Docker e Docker Compose** (para rodar Asterisk)
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Dependências Python**
   ```bash
   # No diretório raiz do projeto
   uv sync
   # ou
   pip install -e .
   ```

### Servidor Asterisk

Os exemplos foram projetados para funcionar com o servidor Asterisk configurado no diretório `docker/asterisk/`.

---

## 📚 Exemplos Disponíveis

### `asterisk_complete_demo.py`

**Descrição**: Demonstração completa de TODAS as funcionalidades do SIPX.

**Funcionalidades demonstradas**:
- ✅ Registro SIP com autenticação digest
- ✅ Verificação de capacidades (OPTIONS)
- ✅ Chamadas INVITE com SDP
- ✅ Envio de ACK
- ✅ Mensagens instantâneas (MESSAGE)
- ✅ Término de chamadas (BYE)
- ✅ Handlers customizados
- ✅ State management (Transactions e Dialogs)
- ✅ Múltiplos transports (UDP, TCP)
- ✅ Servidor SIP para receber chamadas

**Uso**:
```bash
# Executar todas as demos
python asterisk_complete_demo.py

# Executar demo específica
python asterisk_complete_demo.py --demo 1

# Usar servidor remoto
python asterisk_complete_demo.py --asterisk-host 192.168.1.100

# Usar TCP
python asterisk_complete_demo.py --transport TCP

# Pular demos interativas
python asterisk_complete_demo.py --skip-interactive

# Help
python asterisk_complete_demo.py --help
```

**Demos individuais**:
1. **REGISTER**: Registro com autenticação
2. **OPTIONS**: Verificação de capacidades
3. **INVITE Flow**: Chamada completa (INVITE → ACK → BYE)
4. **MESSAGE**: Mensagem instantânea
5. **Multiple Transports**: UDP vs TCP
6. **State Management**: Tracking de transactions/dialogs
7. **SIP Server**: Servidor escutando requests
8. **Complete Workflow**: Workflow completo (registro → chamada → mensagem)

---

## 🚀 Setup do Asterisk

### 1. Iniciar Asterisk com Docker

```bash
# Navegue até o diretório do Asterisk
cd ../docker/asterisk

# Build e start do container
docker-compose up -d --build

# Verificar logs
docker-compose logs -f
```

### 2. Verificar se está rodando

```bash
# Verificar container
docker ps | grep sipx-asterisk

# Conectar ao CLI do Asterisk
docker exec -it sipx-asterisk asterisk -rvvv

# No CLI, verificar endpoints
pjsip show endpoints
```

Você deve ver os 3 usuários configurados:
- **1111** (password: 1111xxx)
- **2222** (password: 2222xxx)
- **3333** (password: 3333xxx)

### 3. Extensões de Teste Disponíveis

| Extensão | Descrição |
|----------|-----------|
| **100** | Echo Test (repete áudio) |
| **200** | Music on Hold |
| **300** | Voicemail Test |
| **400** | Time Announcement |
| **1111, 2222, 3333** | Chamadas entre usuários |

---

## 🎯 Executando os Exemplos

### Exemplo Rápido: Registro

```bash
python asterisk_complete_demo.py --demo 1
```

**Output esperado**:
```
================================================================================
DEMO 1: REGISTER - Registro com Autenticação Digest
Demonstra autenticação automática e retry com credenciais
================================================================================

Registrando usuário 1111...

>>> SENDING REGISTER (0.0.0.0:5070 → 127.0.0.1:5060):
REGISTER sip:127.0.0.1 SIP/2.0
...

<<< RECEIVED 401 Unauthorized AUTH (...)
...

>>> SENDING REGISTER AUTH RETRY (...)
...

<<< RECEIVED 200 OK AUTH (...)

✅ REGISTERED!
   Expires: 3600 seconds
   Contact: <sip:1111@192.168.1.100:5070>
```

### Exemplo: Chamada Completa

```bash
python asterisk_complete_demo.py --demo 3
```

**Fluxo**:
1. REGISTER com autenticação
2. INVITE para extensão 100 (echo test)
3. Recebe 100 Trying, 180 Ringing, 200 OK
4. Envia ACK
5. Aguarda 5 segundos
6. Envia BYE
7. Recebe 200 OK

### Exemplo: Todas as Demos

```bash
python asterisk_complete_demo.py
```

Executa sequencialmente todas as 8 demos.

---

## 🔍 Estrutura do Código de Exemplo

### Anatomia de um Exemplo Básico

```python
from sipx import Client, SipAuthCredentials

# 1. Criar credenciais
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx"
)

# 2. Criar cliente
client = Client(
    local_host="0.0.0.0",
    local_port=5060,
    transport="UDP",
    credentials=credentials
)

# 3. Fazer operações SIP
response = client.register(
    uri="sip:1111@127.0.0.1",
    host="127.0.0.1",
    port=5060
)

# 4. Verificar resposta
if response.status_code == 200:
    print("Success!")

# 5. Limpar
client.close()
```

### Usando Context Manager (Recomendado)

```python
from sipx import Client, SipAuthCredentials

credentials = SipAuthCredentials(username="1111", password="1111xxx")

with Client(credentials=credentials) as client:
    # Operações SIP
    client.register(uri="sip:1111@127.0.0.1", host="127.0.0.1")
    client.invite("sip:2222@127.0.0.1", "127.0.0.1")
    # Client fechado automaticamente ao sair
```

### Adicionando Handlers

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import InviteFlowHandler

def on_ringing(response, context):
    print(f"Phone is ringing! Call-ID: {response.call_id}")

def on_answered(response, context):
    print("Call answered!")

client = Client(credentials=credentials)

# Adicionar handler com callbacks
invite_handler = InviteFlowHandler(
    on_ringing=on_ringing,
    on_answered=on_answered
)
client.add_handler(invite_handler)

# Agora os callbacks serão chamados automaticamente
response = client.invite("sip:100@127.0.0.1", "127.0.0.1")
```

---

## 🛠️ Troubleshooting

### Problema: "Connection refused"

**Sintomas**:
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solução**:
```bash
# Verificar se Asterisk está rodando
docker ps | grep sipx-asterisk

# Se não estiver, iniciar
cd ../docker/asterisk
docker-compose up -d

# Verificar logs
docker-compose logs -f
```

### Problema: "401 Unauthorized" persistente

**Sintomas**:
```
❌ REGISTRATION FAILED: 401
```

**Possíveis causas**:
1. Credenciais incorretas
2. Usuário não configurado no Asterisk
3. Realm incorreto

**Solução**:
```bash
# Verificar configuração do Asterisk
docker exec -it sipx-asterisk cat /etc/asterisk/pjsip.conf

# Deve conter:
# [auth1111]
# type=auth
# auth_type=userpass
# password=1111xxx
# username=1111
```

### Problema: "Address already in use"

**Sintomas**:
```
OSError: [Errno 48] Address already in use
```

**Solução**:
```bash
# Verificar portas em uso
# Linux/Mac
sudo lsof -i :5060

# Windows
netstat -an | findstr 5060

# Matar processo ou usar porta diferente
client = Client(local_port=5070)
```

### Problema: Asterisk não responde

**Diagnóstico**:
```bash
# Conectar ao CLI do Asterisk
docker exec -it sipx-asterisk asterisk -rvvv

# Ativar debug SIP
pjsip set logger on

# Enviar request e observar logs
```

### Problema: "No audio" em chamadas

**Possíveis causas**:
1. Portas RTP bloqueadas (10000-10099/udp)
2. Firewall bloqueando
3. NAT não configurado

**Solução**:
```bash
# Verificar configuração RTP no Asterisk
docker exec -it sipx-asterisk cat /etc/asterisk/rtp.conf

# Deve conter:
# rtpstart=10000
# rtpend=10099

# Verificar se portas estão abertas
# Linux
sudo iptables -L -n | grep 10000

# Testar com echo test (extensão 100)
# Echo test não precisa de RTP bidirecional
```

### Problema: Timeout em requests

**Sintomas**:
```
TimeoutError: Operation timed out
```

**Solução**:
```python
# Aumentar timeout
from sipx import TransportConfig

config = TransportConfig(
    read_timeout=60.0,  # 60 segundos
    connect_timeout=10.0
)

client = Client(config=config)
```

---

## 📖 Recursos Adicionais

### Documentação

- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - Arquitetura completa do SIPX
- [MODULES.md](../docs/MODULES.md) - Documentação de todos os módulos
- [HANDLERS_REFACTORING.md](../docs/HANDLERS_REFACTORING.md) - Sistema de handlers
- [HANDLERS_QUICK_REFERENCE.md](../docs/HANDLERS_QUICK_REFERENCE.md) - Referência rápida

### Ferramentas Úteis

#### sngrep - Visualizador de tráfego SIP

```bash
# Instalar (Ubuntu/Debian)
sudo apt-get install sngrep

# Executar
sudo sngrep port 5060
```

#### tcpdump - Captura de pacotes

```bash
# Capturar tráfego SIP
sudo tcpdump -i any -s 0 -A 'port 5060' -w sip_capture.pcap

# Ler arquivo
tcpdump -r sip_capture.pcap -A
```

#### Wireshark - Análise de pacotes

```bash
# Capturar com filtro SIP
sudo wireshark -k -i any -f "port 5060"
```

---

## 🎓 Próximos Passos

1. **Execute os exemplos**: Comece com `--demo 1` e vá progredindo
2. **Modifique o código**: Experimente com diferentes parâmetros
3. **Crie seus próprios handlers**: Estenda a funcionalidade
4. **Explore os docs**: Leia ARCHITECTURE.md e MODULES.md
5. **Teste cenários reais**: Integre com seu sistema

---

## 💬 Suporte

### Problemas?

1. Verifique os logs do Asterisk: `docker-compose logs -f`
2. Use sngrep para ver tráfego SIP: `sudo sngrep`
3. Ative debug no SIPX (veja exemplos)
4. Consulte a documentação completa em `docs/`

### Exemplos Adicionais Necessários?

Contribuições são bem-vindas! Veja o arquivo principal de README.md para diretrizes.

---

## 📄 Licença

MIT License - Veja LICENSE no diretório raiz do projeto.