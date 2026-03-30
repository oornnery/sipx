# Astrerisk Guide

Guide for configuring and testing sipx with Asterisk running in Docker on WSL.

**Version**: 0.3.0
**Date**: March 2026

---

## Prerequisites

- WSL2 (Ubuntu)
- Docker Desktop with WSL integration
- Python 3.13+ (via uv)
- sipx installed (`uv sync`)

## Environment Configuration

| Component | Address |
|-----------|---------|
| WSL | `172.19.x.x` (or `127.0.0.1`) |
| Asterisk Docker | port `5060` |
| sipx Client | port `5061`+ |

### Asterisk Credentials

Configured in `docker/asterisk/config/pjsip.conf`:

| User | Password | Extension |
|------|----------|-----------|
| 1111 | 1111xxx | 1111 |
| 2222 | 2222xxx | 2222 |
| 3333 | 3333xxx | 3333 |

---

## Setup

### 1. Start Asterisk

```bash
cd docker/asterisk
docker-compose up -d
```

Verify:

```bash
docker ps | grep asterisk
# sipx-asterisk   ... Up X minutes   0.0.0.0:5060->5060/tcp
```

### 2. Test connectivity

```python
from sipx import Client

with Client(local_port=5061) as client:
    response = client.options('sip:127.0.0.1')
    print(f"Status: {response.status_code}")
    # Expected: 200 or 401
```

### 3. Full test

```bash
uv run python examples/asterisk_demo.py
```

---

## Port 5060 in use

Docker exposes Asterisk on port 5060. The sipx client must use a different port:

```python
# Wrong - conflicts with Docker
client = Client(local_port=5060)

# Correct
client = Client(local_port=5061)
```

If you receive `OSError: [Errno 98] Address already in use`:

```bash
# See what is using the port
ss -tulnp | grep 5060
# Solution: use 5061, 5062, 5063...
```

---

## Examples

### Registration

```python
from sipx import Client, Auth

with Client(local_port=5061) as client:
    client.auth = Auth.Digest('1111', '1111xxx')

    response = client.register('sip:1111@127.0.0.1')
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    print(f"REGISTER: {response.status_code}")
```

### Call to echo test (ext 100)

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

### Message

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

## Test Extensions

| Extension | Description |
|-----------|-------------|
| 100 | Echo test (repeats audio) |
| 200 | Music on Hold |
| 300 | Voicemail test |
| 400 | Time announcement |
| 1111 | User 1 |
| 2222 | User 2 |
| 3333 | User 3 |

---

## Troubleshooting

### Container does not run

```bash
cd docker/asterisk
docker-compose up -d
docker logs -f sipx-asterisk
```

### Persistent 401

Check credentials:

```bash
docker exec -it sipx-asterisk asterisk -rvvv
# Inside the CLI:
pjsip show endpoints
pjsip show auth auth1111
```

### Call drops

```bash
docker exec -it sipx-asterisk asterisk -rvvv
# Inside the CLI:
pjsip set logger on
```

### Capture SIP traffic

```bash
# sngrep (visual)
sudo apt-get install sngrep
sudo sngrep port 5060

# tcpdump
sudo tcpdump -i any -s 0 -A 'port 5060'
```

---

## Useful Asterisk CLI Commands

```bash
docker exec -it sipx-asterisk asterisk -rvvv
```

Inside the CLI:

| Command | Description |
|---------|-------------|
| `pjsip show endpoints` | List endpoints |
| `pjsip show registrations` | Active registrations |
| `pjsip show contacts` | Registered contacts |
| `core show channels` | Active calls |
| `dialplan show sipx-test` | Dialplan |
| `pjsip set logger on` | Enable SIP debug |
| `pjsip set logger off` | Disable debug |
| `core reload` | Reload config |

Exit: `Ctrl+C` or `exit`

---

## Checklist

- [ ] Docker container running (`docker ps`)
- [ ] Port 5060 used by Asterisk (`ss -tulnp | grep 5060`)
- [ ] Client using port 5061+ (`Client(local_port=5061)`)
- [ ] Correct credentials (1111/1111xxx)
- [ ] OPTIONS returns 200
- [ ] REGISTER with auth returns 200

---

## Next Steps

- [SDD.md](SDD.md) -- full spec and roadmap
- [../docker/asterisk/README.md](../docker/asterisk/README.md) -- Asterisk config

---

**Version**: 0.3.0
**Last updated**: March 2026
**Environment**: WSL2 + Docker + Asterisk PJSIP
