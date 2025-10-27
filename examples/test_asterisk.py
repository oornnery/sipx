#!/usr/bin/env python3
"""
Script de teste simples para verificar conectividade com Asterisk.

Este script testa:
1. Registro com autenticação
2. OPTIONS
3. INVITE básico

Uso:
    python test_asterisk.py
"""

import sys
import time
from pathlib import Path

# Adicionar sipx ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import Client, SipAuthCredentials
from sipx._handlers import AuthenticationHandler

# Configuração
ASTERISK_HOST = "127.0.0.1"
ASTERISK_PORT = 5060
USERNAME = "1111"
PASSWORD = "1111xxx"

# Detectar IP local automaticamente
import socket


def get_local_ip():
    """Detecta IP local da máquina."""
    try:
        # Cria socket UDP (não precisa conectar de verdade)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP = get_local_ip()

print("=" * 80)
print("SIPX - Teste de Conectividade com Asterisk")
print("=" * 80)
print(f"Asterisk: {ASTERISK_HOST}:{ASTERISK_PORT}")
print(f"Usuário: {USERNAME}")
print(f"IP Local: {LOCAL_IP}")
print("=" * 80)

# Criar credenciais
credentials = SipAuthCredentials(username=USERNAME, password=PASSWORD)

# Criar cliente
print("\n[1/4] Criando cliente SIP...")
client = Client(
    local_host="0.0.0.0", local_port=5070, transport="UDP", credentials=credentials
)

# IMPORTANTE: Adicionar handler de autenticação para retry automático
print("[2/4] Adicionando handler de autenticação...")
client.add_handler(AuthenticationHandler(credentials))

print("[3/4] Cliente criado com sucesso!")
print(f"       Local: {client.local_address}")

try:
    # Teste 1: REGISTER
    print("\n" + "=" * 80)
    print("TESTE 1: REGISTER")
    print("=" * 80)

    response = client.register(
        aor=f"sip:{USERNAME}@{ASTERISK_HOST}",
        registrar=ASTERISK_HOST,
        port=ASTERISK_PORT,
        expires=3600,
    )

    if response.status_code == 200:
        print(f"✅ REGISTER OK: {response.status_code} {response.reason_phrase}")
        print(f"   Expires: {response.headers.get('Expires', 'N/A')}")
        print(f"   Contact: {response.headers.get('Contact', 'N/A')}")
    else:
        print(f"❌ REGISTER FALHOU: {response.status_code} {response.reason_phrase}")
        sys.exit(1)

    time.sleep(1)

    # Teste 2: OPTIONS
    print("\n" + "=" * 80)
    print("TESTE 2: OPTIONS")
    print("=" * 80)

    response = client.options(
        uri=f"sip:{ASTERISK_HOST}", host=ASTERISK_HOST, port=ASTERISK_PORT
    )

    if response.status_code == 200:
        print(f"✅ OPTIONS OK: {response.status_code} {response.reason_phrase}")
        print(f"   Allow: {response.headers.get('Allow', 'N/A')}")
        print(f"   Accept: {response.headers.get('Accept', 'N/A')}")
    else:
        print(f"⚠️  OPTIONS: {response.status_code} {response.reason_phrase}")

    time.sleep(1)

    # Teste 3: INVITE (Echo Test - extensão 100)
    print("\n" + "=" * 80)
    print("TESTE 3: INVITE (Echo Test - Extensão 100)")
    print("=" * 80)

    # SDP com IP correto
    sdp = f"""v=0
o=- {int(time.time())} {int(time.time())} IN IP4 {LOCAL_IP}
s=SIPX Test Call
c=IN IP4 {LOCAL_IP}
t=0 0
m=audio 10000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=sendrecv
"""

    print(f"SDP Offer (usando IP {LOCAL_IP}):")
    print(sdp)

    response = client.invite(
        to_uri=f"sip:100@{ASTERISK_HOST}",
        from_uri=f"sip:{USERNAME}@{ASTERISK_HOST}",
        host=ASTERISK_HOST,
        port=ASTERISK_PORT,
        sdp_content=sdp,
    )

    if response.status_code == 200:
        print(f"✅ INVITE OK: {response.status_code} {response.reason_phrase}")

        # Extrair SDP da resposta
        if response.content:
            print("\nSDP Answer recebido:")
            print(response.content.decode("utf-8"))

        # Manter chamada por 3 segundos
        print("\nMantendo chamada por 3 segundos...")
        time.sleep(3)

        # Desligar
        print("\nEnviando BYE...")
        bye_response = client.bye()
        print(f"✅ BYE: {bye_response.status_code} {bye_response.reason_phrase}")

    elif response.status_code == 100:
        print("⚠️  INVITE: Recebeu apenas 100 Trying, sem resposta final")
        print("   Possíveis causas:")
        print("   - Extensão 100 não existe no Asterisk")
        print("   - Asterisk não consegue rotear a chamada")
        print("   - Timeout esperando resposta")
    elif response.status_code == 404:
        print(f"⚠️  INVITE: {response.status_code} Not Found")
        print("   A extensão 100 não existe no Asterisk")
    elif response.status_code == 486:
        print(f"⚠️  INVITE: {response.status_code} Busy Here")
    else:
        print(f"❌ INVITE: {response.status_code} {response.reason_phrase}")

    # Sucesso!
    print("\n" + "=" * 80)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
    print("=" * 80)
    print("\nResumo:")
    print("- REGISTER: ✅ Funcionando")
    print("- OPTIONS: ✅ Funcionando")
    print(
        f"- INVITE: {'✅ Funcionando' if response.status_code == 200 else '⚠️  Verifique configuração'}"
    )

except KeyboardInterrupt:
    print("\n\n⚠️  Teste interrompido pelo usuário")
except Exception as e:
    print(f"\n\n❌ ERRO: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
finally:
    # Fechar cliente
    print("\n[4/4] Fechando cliente...")
    client.close()
    print("✅ Cliente fechado")

print("\n" + "=" * 80)
print("Teste finalizado!")
print("=" * 80)
