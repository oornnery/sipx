# Guia Rápido: SIPX com Asterisk no WSL

Este guia mostra como configurar e testar a biblioteca SIPX com Asterisk rodando em Docker no WSL (Windows Subsystem for Linux).

## 🎯 Problema Resolvido

Você estava recebendo o erro:
```
OSError: [Errno 98] Address already in use
```

**Causa**: O Docker estava usando a porta 5060, impedindo o cliente SIP de usar a mesma porta.

**Solução**: Usar uma porta diferente para o cliente (5061) e corrigir as credenciais do Asterisk.

## ⚙️ Configuração do Ambiente

### Seu Setup Atual
- **Windows**: IP Wi-Fi `192.168.15.7`
- **WSL**: IP `172.19.112.1`
- **Asterisk Docker**: Rodando e expondo porta `5060`

### Credenciais do Asterisk
Conforme `docker/asterisk/README.md`:

| Usuário | Senha    | Extensão |
|---------|----------|----------|
| 1111    | 1111xxx  | 1111     |
| 2222    | 2222xxx  | 2222     |
| 3333    | 3333xxx  | 3333     |

## 🚀 Passos para Executar

### 1. Verificar se Asterisk está Rodando

```bash
docker ps | grep asterisk
```

Você deve ver:
```
sipx-asterisk   ... Up X minutes   0.0.0.0:5060->5060/tcp, ...
```

### 2. Verificar Configuração (Script de Diagnóstico)

```bash
uv run examples/check_asterisk.py
```

Saída esperada:
```
✅ Container 'sipx-asterisk' is running
✅ Port 5060 is in use (expected for Docker)
✅ Can connect to 127.0.0.1:5060
✅ Available client ports: 5061, 5062, 5063
✅ SIP OPTIONS successful: 200 OK
✅ ALL CHECKS PASSED - Ready to run demos!
```

### 3. Executar Demo Completo

```bash
uv run examples/asterisk_demo.py
```

Resultado esperado:
```
======================================================================
DEMO SUMMARY
======================================================================
  ✅ REGISTER: SUCCESS
  ✅ OPTIONS: SUCCESS
  ✅ INVITE: SUCCESS
  ✅ MESSAGE: SUCCESS

Total: 4/4 successful
======================================================================

🎉 All steps completed successfully!
```

## 🔧 Correções Aplicadas

### 1. Porta do Cliente
**Antes**: `LOCAL_PORT = 5060` ❌  
**Depois**: `LOCAL_PORT = 5061` ✅

### 2. Credenciais
**Antes**:
```python
ASTERISK_HOST = "192.168.1.100"
USERNAME = "alice"
PASSWORD = "secret"
```

**Depois**:
```python
ASTERISK_HOST = "127.0.0.1"  # localhost no WSL
USERNAME = "1111"
PASSWORD = "1111xxx"
```

### 3. FROM URI com Username Correto
Adicionado método que usa `auth.username` automaticamente em vez de "user" genérico.

### 4. Contact Header no INVITE
Asterisk/PJSIP requer header `Contact` em INVITE requests:
```python
invite_headers = {
    "Contact": f"<sip:{username}@{host}:{port}>"
}
```

## 🐛 Troubleshooting

### Porta 5060 em Uso
```bash
# Ver o que está usando a porta
ss -tulnp | grep 5060

# Solução: Use porta diferente no cliente (5061, 5062, etc)
```

### Container não está rodando
```bash
# Iniciar Asterisk
cd docker/asterisk
docker-compose up -d

# Ver logs
docker logs -f sipx-asterisk
```

### Autenticação falhando
```bash
# Conectar ao CLI do Asterisk
docker exec -it sipx-asterisk asterisk -rvvv

# Verificar endpoints
pjsip show endpoints

# Ver se usuário está configurado
pjsip show auth auth1111
```

### Chamada cai imediatamente
```bash
# Ver logs do Asterisk em tempo real
docker logs -f sipx-asterisk

# Ou conectar ao CLI
docker exec -it sipx-asterisk asterisk -rvvv
# Dentro do CLI:
pjsip set logger on
```

## 📊 O que o Demo Faz

### 1. REGISTER (Registro)
Registra o usuário 1111 no servidor Asterisk por 3600 segundos.

### 2. OPTIONS (Verificação)
Verifica as capacidades do servidor (métodos suportados, codecs, etc).

### 3. INVITE (Chamada)
Faz uma chamada para a extensão 100 (echo test):
- Envia SDP offer com codecs de áudio
- Recebe 401 Unauthorized
- Reenvia com autenticação Digest
- Recebe 200 OK
- Envia ACK
- Mantém a chamada por 5 segundos
- Envia BYE para encerrar

### 4. MESSAGE (Mensagem Instantânea)
Envia uma mensagem de texto para extensão 2222.

## 🎓 Comandos Úteis do Asterisk

```bash
# Conectar ao CLI
docker exec -it sipx-asterisk asterisk -rvvv

# Comandos dentro do CLI:
pjsip show endpoints          # Lista endpoints configurados
pjsip show registrations      # Registros ativos
pjsip show contacts           # Contatos registrados
core show channels            # Chamadas ativas
dialplan show sipx-test       # Dialplan (rotas)
pjsip set logger on           # Ativar debug SIP
pjsip set logger off          # Desativar debug SIP
core reload                   # Recarregar configurações

# Sair: Ctrl+C ou 'exit'
```

## 📝 Extensões de Teste Disponíveis

| Extensão | Descrição                    |
|----------|------------------------------|
| 100      | Echo test (repete seu áudio) |
| 200      | Music on Hold                |
| 300      | Voicemail test               |
| 400      | Time announcement            |
| 1111     | Usuário 1 (você)             |
| 2222     | Usuário 2 (outro ramal)      |
| 3333     | Usuário 3 (outro ramal)      |

## 🔍 Debug Avançado

### Capturar Tráfego SIP
```bash
# Com tcpdump
sudo tcpdump -i any -s 0 -A 'port 5060' -w sip.pcap

# Com sngrep (mais visual)
sudo apt-get install sngrep
sudo sngrep port 5060
```

### Ver Mensagens SIP no Asterisk
```bash
docker exec -it sipx-asterisk asterisk -rvvv
# Dentro do CLI:
pjsip set logger on
```

### Verificar Configuração PJSIP
```bash
docker exec sipx-asterisk cat /etc/asterisk/pjsip.conf | grep -A 10 "1111"
```

## 💡 Dicas

1. **Sempre use porta diferente de 5060** no cliente para evitar conflito com Docker
2. **Use 127.0.0.1** como host do Asterisk (localhost no WSL)
3. **Verifique credenciais** em `docker/asterisk/README.md`
4. **Execute check_asterisk.py** antes do demo para validar configuração
5. **Monitore logs** do Asterisk durante testes: `docker logs -f sipx-asterisk`

## 📚 Próximos Passos

- Testar chamadas entre extensões (1111 → 2222)
- Implementar recebimento de chamadas (servidor SIP)
- Adicionar suporte a áudio RTP real
- Testar com softphones (Linphone, X-Lite)
- Implementar transfer, hold, conference

## 🆘 Precisa de Ajuda?

1. Verifique os logs: `docker logs sipx-asterisk`
2. Execute diagnóstico: `uv run examples/check_asterisk.py`
3. Veja o arquivo: `ASTERISK_SETUP_FIXES.md` (detalhes técnicos)
4. Consulte: `docker/asterisk/README.md` (configuração Asterisk)

## ✅ Checklist de Validação

- [ ] Docker container rodando (`docker ps`)
- [ ] Porta 5060 em uso (`ss -tulnp | grep 5060`)
- [ ] Porta 5061 disponível para cliente
- [ ] Credenciais corretas (1111/1111xxx)
- [ ] `check_asterisk.py` passou todos os testes
- [ ] `asterisk_demo.py` completou 4/4 steps

---

**Status**: ✅ Tudo funcionando perfeitamente!

**Data**: 27 de Outubro de 2025

**Ambiente**: WSL (Ubuntu) + Docker + Asterisk PJSIP