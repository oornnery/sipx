# Guia de Migração - Remoção do LegacyAuthHandler

**Data**: 27 de Outubro de 2024  
**Versão**: SIPX 0.2.0+  
**Status**: ✅ Migração Obrigatória

---

## 📋 Sumário

O `LegacyAuthHandler` foi **completamente removido** do SIPX. Agora existe apenas um único handler de autenticação: `AuthenticationHandler`, que é moderno, completo e mais fácil de usar.

---

## ❌ O Que Foi Removido

### Classes Removidas
- ❌ `LegacyAuthHandler` (sipx._handlers._auth.LegacyAuthHandler)
- ❌ `AuthHandler` (alias para LegacyAuthHandler)

### Imports Que Não Funcionam Mais
```python
# ❌ NÃO FUNCIONA MAIS
from sipx import AuthHandler
from sipx._handlers import LegacyAuthHandler
```

---

## ✅ Como Migrar

### Antes (com LegacyAuthHandler)

```python
from sipx import Client
from sipx._handlers import LegacyAuthHandler

# Criar cliente
client = Client(
    local_host="0.0.0.0",
    local_port=5060
)

# Adicionar handler de autenticação legado
auth_handler = LegacyAuthHandler(
    username="1111",
    password="1111xxx"
)
client.add_handler(auth_handler)

# Fazer requests
client.register(aor="sip:1111@example.com", registrar="example.com")
```

### Depois (com AuthenticationHandler)

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

# Criar credenciais
credentials = SipAuthCredentials(
    username="1111",
    password="1111xxx"
)

# Criar cliente
client = Client()

# Adicionar handler de autenticação moderno
auth_handler = AuthenticationHandler(credentials)
client.add_handler(auth_handler)

# Fazer requests (funciona igual)
client.register(aor="sip:1111@example.com", registrar="example.com")
```

---

## 🎯 Opções de Uso do AuthenticationHandler

### Opção 1: Via Handler (Mais Flexível)

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")
client = Client()
client.add_handler(AuthenticationHandler(credentials))

# Auto-retry funcionará automaticamente
response = client.register(aor="sip:1111@example.com", registrar="example.com")
```

**Vantagens**:
- Controle total sobre quando/como o handler é adicionado
- Pode trocar credenciais dinamicamente
- Mais explícito

### Opção 2: Via Client (Mais Simples)

```python
from sipx import Client, SipAuthCredentials

client = Client(
    credentials=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)

# O Client usa _auth_handler interno automaticamente
response = client.register(aor="sip:1111@example.com", registrar="example.com")
```

**Vantagens**:
- Menos código
- Configuração em um só lugar
- Recomendado para casos simples

**⚠️ IMPORTANTE**: Na Opção 2, você ainda precisa adicionar um `AuthenticationHandler` aos handlers para o auto-retry funcionar:

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")

client = Client(credentials=credentials)  # Credenciais no client
client.add_handler(AuthenticationHandler(credentials))  # Handler para auto-retry

# Agora sim funciona com retry automático
response = client.register(aor="sip:1111@example.com", registrar="example.com")
```

### Opção 3: Por Método (Prioridade Máxima)

```python
from sipx import Client, SipAuthCredentials

client = Client()

# Credenciais específicas para este método
response = client.register(
    aor="sip:1111@example.com",
    registrar="example.com",
    auth=SipAuthCredentials(
        username="1111",
        password="1111xxx"
    )
)
```

**Vantagens**:
- Credenciais diferentes para requests diferentes
- Prioridade máxima (sobrescreve client e handler)

---

## 🔄 Prioridade de Credenciais

O `AuthenticationHandler` suporta 3 níveis de credenciais com prioridade clara:

```
1. Method-level (maior prioridade)
   ↓
2. Handler-level (prioridade média)
   ↓
3. Client-level (menor prioridade - interno)
```

**Exemplo**:
```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

# Nível 2: Handler (prioridade média)
handler_creds = SipAuthCredentials(username="handler_user", password="handler_pass")
client = Client()
client.add_handler(AuthenticationHandler(handler_creds))

# Nível 1: Method (prioridade máxima - sobrescreve handler)
method_creds = SipAuthCredentials(username="method_user", password="method_pass")
response = client.register(
    aor="sip:method_user@example.com",
    registrar="example.com",
    auth=method_creds  # Este será usado
)
```

---

## 🆚 Comparação de Funcionalidades

| Funcionalidade | LegacyAuthHandler | AuthenticationHandler |
|----------------|-------------------|----------------------|
| **Auto-retry em 401/407** | ✅ | ✅ |
| **Digest Authentication** | ✅ | ✅ |
| **Múltiplos algoritmos** | ✅ MD5 | ✅ MD5, SHA-256, SHA-512 |
| **QoP support** | ✅ auth | ✅ auth, auth-int |
| **Prioridade de credenciais** | ❌ | ✅ 3 níveis |
| **SipAuthCredentials** | ❌ | ✅ |
| **Type hints completos** | ❌ | ✅ |
| **Documentação** | ❌ | ✅ |
| **Testes** | ❌ | ✅ |

---

## 📝 Checklist de Migração

- [ ] Remover imports de `LegacyAuthHandler` ou `AuthHandler`
- [ ] Criar `SipAuthCredentials` em vez de passar username/password separados
- [ ] Trocar `LegacyAuthHandler(username, password)` por `AuthenticationHandler(credentials)`
- [ ] Testar auto-retry de autenticação
- [ ] Verificar que 401/407 recebe retry automático
- [ ] (Opcional) Simplificar código usando Client(credentials=...)

---

## 🧪 Como Testar

### Teste Básico

```python
from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

credentials = SipAuthCredentials(username="1111", password="1111xxx")
client = Client()
client.add_handler(AuthenticationHandler(credentials))

# Deve funcionar com retry automático
response = client.register(aor="sip:1111@127.0.0.1", registrar="127.0.0.1")

assert response.status_code == 200, f"Expected 200, got {response.status_code}"
print("✅ Migração bem-sucedida!")
```

### Teste Completo

Execute o script de teste fornecido:

```bash
cd examples
uv run python test_asterisk.py
```

**Saída esperada**:
```
✅ REGISTER OK: 200 OK
✅ OPTIONS OK: 200 OK
✅ INVITE OK: 200 OK
```

---

## ❓ FAQ

### P: Por que o LegacyAuthHandler foi removido?

**R**: Para simplificar a biblioteca. Manter dois handlers de autenticação criava confusão e duplicação de código. O `AuthenticationHandler` moderno é mais completo e fácil de usar.

### P: Meu código vai quebrar?

**R**: Sim, se você usa `LegacyAuthHandler` ou `AuthHandler`. A migração é simples (veja exemplos acima).

### P: Qual é a vantagem do novo handler?

**R**: 
- ✅ Suporta múltiplos algoritmos (MD5, SHA-256, SHA-512)
- ✅ Prioridade clara de credenciais (3 níveis)
- ✅ Type hints completos
- ✅ Melhor documentação
- ✅ Código mais limpo e testável

### P: Posso continuar usando username/password direto?

**R**: Não. Você deve usar `SipAuthCredentials`:

```python
# Antes
handler = LegacyAuthHandler(username="user", password="pass")

# Depois
from sipx import SipAuthCredentials
credentials = SipAuthCredentials(username="user", password="pass")
handler = AuthenticationHandler(credentials)
```

### P: Como uso credenciais diferentes para cada request?

**R**: Use o parâmetro `auth` no método:

```python
response = client.register(
    aor="sip:user@example.com",
    registrar="example.com",
    auth=SipAuthCredentials(username="user", password="pass")
)
```

### P: O auto-retry ainda funciona?

**R**: Sim! Funciona melhor que antes:

1. `AuthenticationHandler.on_response()` detecta 401/407
2. Sinaliza `needs_auth` no metadata
3. Client executa retry automático
4. `AuthenticationHandler.handle_auth_response()` constrói Authorization header
5. Request é reenviado com autenticação
6. Response final é retornado

---

## 🚀 Próximos Passos

Após migrar:

1. **Teste seu código** com o novo handler
2. **Remova** qualquer código relacionado a LegacyAuthHandler
3. **Aproveite** as novas funcionalidades:
   - Prioridade de credenciais
   - Múltiplos algoritmos
   - Type hints

---

## 📚 Recursos Adicionais

- [MODULES.md](MODULES.md#authentication-handler) - Documentação completa do AuthenticationHandler
- [QUICK_START.md](QUICK_START.md) - Exemplos de uso básico
- [examples/test_asterisk.py](../examples/test_asterisk.py) - Script de teste completo
- [examples/asterisk_complete_demo.py](../examples/asterisk_complete_demo.py) - Demos avançadas

---

## ✅ Status da Migração

- ✅ `LegacyAuthHandler` removido do código
- ✅ `AuthHandler` alias removido
- ✅ `AuthenticationHandler.on_response()` implementado
- ✅ Documentação atualizada
- ✅ Exemplos atualizados
- ✅ Testes funcionando

**Versão afetada**: SIPX 0.2.0+  
**Breaking change**: ✅ Sim  
**Migration path**: ✅ Documentado acima

---

*Última atualização: 27 de Outubro de 2024*