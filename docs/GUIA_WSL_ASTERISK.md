# sipx + Asterisk no WSL

Guia para configurar e testar sipx com Asterisk rodando em Docker no WSL.

**Versao**: 0.3.0
**Data**: Marco 2026

---

## Pre-requisitos

- WSL2 (Ubuntu)
- Docker Desktop com integracao WSL
- Python 3.13+ (via uv)
- sipx instalado (`uv sync`)

## Configuracao do ambiente

| Componente | Endereco |
|------------|----------|
| WSL | `172.19.x.x` (ou `127.0.0.1`) |
| Asterisk Docker | porta `5060` |
| sipx Client | porta `5061`+ |

### Credenciais do Asterisk

Configuradas em `docker/asterisk/config/pjsip.conf`:

| Usuario | Senha | Extensao |
|---------|-------|----------|
| 1111 | 1111xxx | 1111 |
| 2222 | 2222xxx | 2222 |
| 3333 | 3333xxx | 3333 |

---

## Setup

### 1. Iniciar Asterisk

```bash
cd docker/asterisk
docker-compose up -d
```

Verificar:

```bash
docker ps | grep asterisk
# sipx-asterisk   ... Up X minutes   0.0.0.0:5060->5060/tcp
```

### 2. Testar conectividade

```python
from sipx import Client

with Client(local_port=5061) as client:
    response = client.options('sip:127.0.0.1')
    print(f"Status: {response.status_code}")
    # Esperado: 200 ou 401
```

### 3. Teste completo

```bash
uv run python examples/asterisk_demo.py
```

---

## Porta 5060 em uso

O Docker expoe Asterisk na porta 5060. O cliente sipx precisa usar outra porta:

```python
# Errado - conflita com Docker
client = Client(local_port=5060)

# Correto
client = Client(local_port=5061)
```

Se receber `OSError: [Errno 98] Address already in use`:

```bash
# Ver o que usa a porta
ss -tulnp | grep 5060
# Solucao: use 5061, 5062, 5063...
```

---

## Exemplos

### Registro

```python
from sipx import Client, Auth

with Client(local_port=5061) as client:
    client.auth = Auth.Digest('1111', '1111xxx')

    response = client.register('sip:1111@127.0.0.1')
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    print(f"REGISTER: {response.status_code}")
```

### Chamada para echo test (ext 100)

```python
from sipx import Client, Auth, SDPBody

with Client(local_port=5061) as client:
    client.auth = Auth.Digest('1111', '1111xxx')

    sdp = SDPBody.create_offer(
        session_name="Test",
        origin_username="1111",
        origin_address=client.local_address.host,
        connection_address=client.local_address.host,
        media_specs=[{
            "media": "audio",
            "port": 8000,
            "codecs": [
                {"payload": "0", "name": "PCMU", "rate": "8000"},
                {"payload": "8", "name": "PCMA", "rate": "8000"},
            ],
        }],
    )

    response = client.invite(
        to_uri='sip:100@127.0.0.1',
        body=sdp.to_string(),
    )
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    if response.status_code == 200:
        client.ack(response=response)
        import time
        time.sleep(5)
        client.bye(response=response)
```

### Mensagem

```python
with Client(local_port=5061) as client:
    client.auth = Auth.Digest('1111', '1111xxx')

    response = client.message(
        to_uri='sip:2222@127.0.0.1',
        content='Hello from sipx!',
    )
    if response.status_code == 401:
        response = client.retry_with_auth(response)
```

---

## Extensoes de teste

| Extensao | Descricao |
|----------|-----------|
| 100 | Echo test (repete audio) |
| 200 | Music on Hold |
| 300 | Voicemail test |
| 400 | Time announcement |
| 1111 | Usuario 1 |
| 2222 | Usuario 2 |
| 3333 | Usuario 3 |

---

## Troubleshooting

### Container nao roda

```bash
cd docker/asterisk
docker-compose up -d
docker logs -f sipx-asterisk
```

### 401 persistente

Verificar credenciais:

```bash
docker exec -it sipx-asterisk asterisk -rvvv
# Dentro do CLI:
pjsip show endpoints
pjsip show auth auth1111
```

### Chamada cai

```bash
docker exec -it sipx-asterisk asterisk -rvvv
# Dentro do CLI:
pjsip set logger on
```

### Capturar trafico SIP

```bash
# sngrep (visual)
sudo apt-get install sngrep
sudo sngrep port 5060

# tcpdump
sudo tcpdump -i any -s 0 -A 'port 5060'
```

---

## Comandos uteis do Asterisk CLI

```bash
docker exec -it sipx-asterisk asterisk -rvvv
```

Dentro do CLI:

| Comando | Descricao |
|---------|-----------|
| `pjsip show endpoints` | Lista endpoints |
| `pjsip show registrations` | Registros ativos |
| `pjsip show contacts` | Contatos registrados |
| `core show channels` | Chamadas ativas |
| `dialplan show sipx-test` | Dialplan |
| `pjsip set logger on` | Ativar debug SIP |
| `pjsip set logger off` | Desativar debug |
| `core reload` | Recarregar config |

Sair: `Ctrl+C` ou `exit`

---

## Checklist

- [ ] Docker container rodando (`docker ps`)
- [ ] Porta 5060 usada pelo Asterisk (`ss -tulnp | grep 5060`)
- [ ] Client usando porta 5061+ (`Client(local_port=5061)`)
- [ ] Credenciais corretas (1111/1111xxx)
- [ ] OPTIONS retorna 200
- [ ] REGISTER com auth retorna 200

---

## Proximos passos

- [QUICK_START.md](QUICK_START.md) — mais exemplos
- [SDD.md](SDD.md) — spec completa e roadmap
- [../docker/asterisk/README.md](../docker/asterisk/README.md) — config Asterisk

---

**Versao**: 0.3.0
**Ultima atualizacao**: Marco 2026
**Ambiente**: WSL2 + Docker + Asterisk PJSIP
