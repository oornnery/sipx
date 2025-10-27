FROM debian:bullseye-slim

# Instalar dependências
RUN apt-get update && apt-get install -y \
    asterisk \
    asterisk-modules \
    asterisk-core-sounds-en \
    asterisk-core-sounds-en-gsm \
    asterisk-moh-opsound-gsm \
    && rm -rf /var/lib/apt/lists/*

# Criar diretórios necessários
RUN mkdir -p /var/run/asterisk \
    && mkdir -p /var/log/asterisk \
    && mkdir -p /var/spool/asterisk \
    && mkdir -p /etc/asterisk

# Expor portas
# SIP: 5060 (UDP/TCP)
# RTP: 10000-10099 (UDP)
# AMI: 5038 (TCP) - opcional
EXPOSE 5060/udp 5060/tcp 10000-10099/udp 5038/tcp

# Copiar configurações customizadas
COPY config/*.conf /etc/asterisk/

# Iniciar Asterisk em foreground
CMD ["asterisk", "-f", "-vvvvv", "-g", "-c"]
