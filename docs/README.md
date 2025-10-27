# SIPX - Documentação

Bem-vindo à documentação completa do SIPX - Uma biblioteca SIP moderna para Python.

**Versão**: 2.0.0  
**Data**: Outubro 2025  
**Status**: ✅ Produção

---

## 📚 Índice da Documentação

### 🚀 Começando

- **[QUICK_START.md](QUICK_START.md)** - Guia de início rápido
  - Instalação
  - Primeiro exemplo
  - Registro SIP
  - Fazer chamadas
  - Autenticação
  - Event handlers
  - Cliente assíncrono

### 🏗️ Arquitetura

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Arquitetura completa do SIPX
  - Visão geral
  - Princípios de design
  - Camadas da arquitetura
  - Componentes principais
  - Fluxo de mensagens
  - Gerenciamento de estado
  - Sistema de eventos
  - Diagramas

### 📦 Módulos

- **[MODULES.md](MODULES.md)** - Documentação de módulos e componentes
  - Estrutura de pacotes
  - Módulo principal (Client/AsyncClient)
  - Modelos de dados (Request/Response/Headers/SDP)
  - Transporte (UDP/TCP)
  - Autenticação (Digest)
  - Sistema de eventos
  - Gerenciamento de estado
  - Utilitários

### 📖 Exemplos

- **[../examples/README.md](../examples/README.md)** - Guia de exemplos práticos
  - Demo principal (asterisk_demo.py)
  - Outros exemplos
  - Setup do Asterisk
  - Testes realizados
  - Troubleshooting

### 🐳 Docker

- **[../docker/asterisk/README.md](../docker/asterisk/README.md)** - Asterisk Docker
  - Como usar
  - Usuários configurados
  - Políticas de autenticação
  - Extensões de teste
  - Comandos úteis

### 🌍 Guias Regionais

- **[GUIA_WSL_ASTERISK.md](GUIA_WSL_ASTERISK.md)** - Guia WSL/Docker (Português)
  - Setup no Windows/WSL
  - Configuração do ambiente
  - Troubleshooting específico

---

## 🎯 Onde Começar?

### Se você é novo no SIPX:

1. **[QUICK_START.md](QUICK_START.md)** - Comece aqui!
2. **[../examples/README.md](../examples/README.md)** - Veja exemplos práticos
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Entenda a arquitetura

### Se você quer entender a fundo:

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Arquitetura completa
2. **[MODULES.md](MODULES.md)** - Cada módulo em detalhe
3. Código fonte em `sipx/`

### Se você quer testar rapidamente:

1. **[../docker/asterisk/README.md](../docker/asterisk/README.md)** - Setup Asterisk
2. **[QUICK_START.md](QUICK_START.md#testando-com-asterisk-local)** - Teste local
3. `uv run examples/asterisk_demo.py` - Demo completo

---

## 📋 O que é SIPX?

SIPX é uma biblioteca SIP (Session Initiation Protocol) completa e moderna para Python que fornece:

### ✨ Recursos Principais

- 🎯 **API Simples e Intuitiva** - Fácil de usar, difícil de errar
- 🔐 **Autenticação Digest** - RFC 2617 completo (MD5, SHA-256, SHA-512)
- 📞 **Métodos SIP Completos** - REGISTER, INVITE, ACK, BYE, OPTIONS, MESSAGE
- 🎵 **SDP** - Offer/Answer, parsing, análise de codecs
- 🔄 **Sync/Async** - Client e AsyncClient com mesma API
- 🎭 **Event System** - Decoradores @event_handler
- 💾 **State Management** - Transações e diálogos RFC 3261
- 🚀 **Auto Re-registration** - Threading/asyncio automático
- 📊 **RFC Compliant** - Headers ordenados, branch mágico, etc

### 🎨 Princípios de Design

1. **Simplicidade** - API limpa e pythônica
2. **Controle Explícito** - Desenvolvedor controla autenticação
3. **RFC Compliance** - Segue RFC 3261, 2617, 4566, 3264
4. **Type Safety** - Type hints completos
5. **Extensibilidade** - Event handlers customizados

---

## 🚀 Instalação Rápida

```bash
# Com pip
pip install sipx

# Com uv (recomendado)
uv add sipx
```

---

## 💡 Exemplo Rápido

```python
from sipx import Client, Auth

# Autenticação
auth = Auth.Digest(username="1111", password="1111xxx")

# Cliente
with Client(local_port=5061, auth=auth) as client:
    # Registrar
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    
    print(f"Status: {response.status_code}")
    # Output: Status: 200
```

**Veja mais exemplos em [QUICK_START.md](QUICK_START.md)**

---

## 📊 Estrutura da Documentação

```
docs/
├── README.md                    # Este arquivo (índice)
├── QUICK_START.md              # ⭐ Comece aqui
├── ARCHITECTURE.md             # Arquitetura completa
├── MODULES.md                  # Módulos detalhados
├── GUIA_WSL_ASTERISK.md       # Guia WSL/Docker
│
../examples/
├── README.md                   # Guia de exemplos
├── asterisk_demo.py           # ⭐ Demo principal
├── simple_example.py          # Exemplo básico
└── simplified_demo.py         # Demo simplificado
│
../docker/asterisk/
├── README.md                  # Setup Asterisk
├── docker-compose.yml         # Docker compose
└── config/                    # Configurações
    ├── pjsip.conf            # Usuários SIP
    └── extensions.conf       # Dialplan
```

---

## 🎓 Tutoriais por Tópico

### Registro e Autenticação

- [QUICK_START.md#registro-sip](QUICK_START.md#registro-sip)
- [QUICK_START.md#autenticação](QUICK_START.md#autenticação)
- [MODULES.md#autenticação](MODULES.md#autenticação)

### Chamadas (INVITE/ACK/BYE)

- [QUICK_START.md#fazendo-uma-chamada](QUICK_START.md#fazendo-uma-chamada)
- [ARCHITECTURE.md#invite-flow](ARCHITECTURE.md#fluxo-de-mensagens)
- [examples/README.md](../examples/README.md)

### SDP (Session Description Protocol)

- [MODULES.md#sdpbody](MODULES.md#sipx_models_bodypy)
- [ARCHITECTURE.md#sdp-layer](ARCHITECTURE.md#componentes-principais)

### Event Handlers

- [QUICK_START.md#event-handlers](QUICK_START.md#event-handlers)
- [ARCHITECTURE.md#sistema-de-eventos](ARCHITECTURE.md#sistema-de-eventos)

### Cliente Assíncrono

- [QUICK_START.md#cliente-assíncrono](QUICK_START.md#cliente-assíncrono)
- [ARCHITECTURE.md#concorrência](ARCHITECTURE.md#concorrência)

### Auto Re-registration

- [QUICK_START.md#com-auto-re-registration](QUICK_START.md#com-auto-re-registration)
- [ARCHITECTURE.md#auto-re-registration-flow](ARCHITECTURE.md#gerenciamento-de-estado)

---

## 🔧 Configuração

### Asterisk Local (Docker)

```bash
cd docker/asterisk
docker-compose up -d
```

**Veja**: [docker/asterisk/README.md](../docker/asterisk/README.md)

### WSL/Windows

**Veja**: [GUIA_WSL_ASTERISK.md](GUIA_WSL_ASTERISK.md)

---

## 🧪 Testes

### Demo Completo

```bash
# Demo principal (3 usuários, 16 testes)
uv run examples/asterisk_demo.py
```

**Resultado esperado**: 15/16 testes passam (1 falha esperada)

**Veja**: [examples/README.md](../examples/README.md)

---

## 📖 Referências RFC

- **RFC 3261** - SIP: Session Initiation Protocol
- **RFC 2617** - HTTP Authentication: Basic and Digest Access
- **RFC 4566** - SDP: Session Description Protocol
- **RFC 3264** - An Offer/Answer Model with SDP
- **RFC 3581** - Symmetric Response Routing (rport)

---

## 🆘 Suporte

### Problemas Comuns

**Porta em uso**:
```
Solução: Use porta diferente (5061, 5062, 5063)
```

**401 Unauthorized persistente**:
```
Solução: Verifique credenciais, use retry_with_auth()
```

**BYE falhando**:
```
Solução: Passe response do INVITE: client.bye(response=response)
```

### Debug

```python
# Ativar logs detalhados
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Ferramentas

- **sngrep**: `sudo sngrep port 5060`
- **tcpdump**: `sudo tcpdump -i any -s 0 -A 'port 5060'`

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature
3. Faça commit das mudanças
4. Abra um Pull Request

### Áreas de Contribuição

- 📝 Documentação
- 🧪 Testes
- 🐛 Correção de bugs
- ✨ Novas features
- 🌍 Traduções

---

## 📄 Licença

MIT License - Veja LICENSE no diretório raiz do projeto.

---

## 🗺️ Roadmap

### Versão Atual (2.0.0)

- ✅ Client/AsyncClient
- ✅ Digest Authentication
- ✅ Event System
- ✅ SDP Offer/Answer
- ✅ Auto Re-registration
- ✅ UDP/TCP Transport
- ✅ State Management

### Futuro (3.0.0)

- ⏳ WebSocket Transport
- ⏳ IPv6 Support
- ⏳ PRACK (RFC 3262)
- ⏳ SUBSCRIBE/NOTIFY completo
- ⏳ Video codecs
- ⏳ TLS Transport

---

## 📞 Contato

- **GitHub Issues**: Reporte bugs e sugira features
- **Pull Requests**: Contribua com código
- **Documentação**: Ajude a melhorar

---

**Versão**: 2.0.0  
**Última Atualização**: Outubro 2025  
**Autor**: SIPX Development Team  
**Status**: ✅ Produção

**Pronto para começar? → [QUICK_START.md](QUICK_START.md)**