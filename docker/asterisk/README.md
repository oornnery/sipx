# Asterisk Docker para Testes SIPX

Container Docker com Asterisk configurado para testar sua biblioteca SIPX.

## 🚀 Como Usar

### 1. Build e Start

```bash
cd asterisk-docker
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

| Username | Password | Contexto |
|----------|----------|----------|
| 1111     | 1111xxx  | sipx-test |
| 2222     | 2222xxx  | sipx-test |
| 3333     | 3333xxx  | sipx-test |

## 🔧 Configuração do Cliente SIPX

Atualize seu `demo.py` para usar o Asterisk local:

```python
SIP_SERVER = "127.0.0.1"  # ou IP da máquina
SIP_PORT = 5060
SIP_USERNAME = "1111"
SIP_PASSWORD = "1111xxx"
SIP_DOMAIN = "127.0.0.1"
```

## 🧪 Testes Disponíveis

### Echo Test
Disque `100` para testar áudio (echo)

### Music on Hold
Disque `200` para ouvir música

### Voicemail Test
Disque `300` para ouvir mensagem de voicemail

### Time Announcement
Disque `400` para ouvir o horário

### Chamadas Entre Extensões
Disque `2222` ou `3333` para chamar outros usuários

## ⚠️ Notas Importantes

### Autenticação em OPTIONS
Por padrão, o Asterisk/PJSIP **requer autenticação para OPTIONS**. Isso é o comportamento correto segundo RFC 3261. Certifique-se de adicionar o `AuthenticationHandler` ao seu cliente:

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")
client = Client()
client.add_handler(AuthenticationHandler(credentials))

# OPTIONS agora funcionará com retry automático
response = client.options(uri="sip:127.0.0.1", host="127.0.0.1")
```

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

### Exemplo 1: Registro Simples

```python
from sipx import Client

client = Client(
    server="127.0.0.1",
    port=5060,
    username="1111",
    password="1111xxx",
    domain="127.0.0.1"
)

# Fazer registro
response = client.register()
print(f"Registro: {response.status_code} {response.reason}")
```

### Exemplo 2: Chamada para Echo Test

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")

client = Client()
client.add_handler(AuthenticationHandler(credentials))

# Registrar
client.register(aor="sip:1111@127.0.0.1", registrar="127.0.0.1")

# Chamar extensão de echo (100)
response = client.invite(
    to_uri="sip:100@127.0.0.1",
    from_uri="sip:1111@127.0.0.1",
    host="127.0.0.1"
)
print(f"INVITE: {response.status_code} {response.reason_phrase}")

# Aguardar um pouco e desligar
import time
time.sleep(5)
client.bye()
client.close()
```

### Exemplo 3: Chamada Entre Extensões

Terminal 1 (usuário 1111):
```python
from sipx import Client, SIPServer

# Iniciar servidor para receber chamadas
server = SIPServer(port=5070)
server.start()

# Cliente
client = Client(
    server="127.0.0.1",
    port=5060,
    username="1111",
    password="1111xxx",
    domain="127.0.0.1",
    local_port=5070
)
client.register()
print("Aguardando chamadas na extensão 1111...")
```

Terminal 2 (usuário 2222):
```python
from sipx import Client

client = Client(
    server="127.0.0.1",
    port=5060,
    username="2222",
    password="2222xxx",
    domain="127.0.0.1"
)
client.register()

# Chamar extensão 1111
response = client.invite("1111")
print(f"Chamando 1111: {response.status_code}")
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

## 📄 Licença

Este setup é fornecido como exemplo para testes. Consulte as licenças do Asterisk e suas dependências para uso em produção.