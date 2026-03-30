# sipx - Exemplos

Demo completo exercitando todos os componentes da lib sipx.

## Executar

```bash
# Iniciar Asterisk
cd docker/asterisk && docker-compose up -d

# Rodar demo
uv run python examples/asterisk_demo.py
```

## O que e testado

- Constants, Headers, MessageParser, SDPBody, Auth, FSM (offline)
- SIPServer com handlers customizados
- 3 usuarios Asterisk (OPTIONS, REGISTER, INVITE, ACK, BYE, MESSAGE, INFO)
- Auth: invalid creds, per-request override, auto re-registration
- SDP: early offer, late offer, create_answer, codec analysis
- Events: on_request, on_response, @event_handler com method/status/tuple

Veja [docs/SDD.md](../docs/SDD.md) para a spec completa.
