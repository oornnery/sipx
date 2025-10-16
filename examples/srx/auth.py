"""
Módulo para autenticação HTTP Digest conforme RFC 2617.
"""

import hashlib


def make_digest_response(
    username: str, password: str, realm: str, method: str, uri: str, nonce: str
) -> str:
    """
    Gera resposta de autenticação digest para SIP.

    Args:
        username: Nome do usuário.
        password: Senha do usuário.
        realm: Realm do servidor.
        method: Método SIP (ex: INVITE).
        uri: URI requisitada.
        nonce: Nonce enviado pelo servidor.

    Returns:
        Hash MD5 string da resposta digest.
    """
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return response
