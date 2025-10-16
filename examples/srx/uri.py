"""
Módulo para parsing e manipulação de SIP URI e endereços conforme RFC 2396 e RFC 3261.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class URI:
    scheme: str
    user: Optional[str]
    host: str
    port: Optional[int] = None
    params: Optional[str] = None
    headers: Optional[str] = None

    @classmethod
    def parse(cls, uri: str):
        """
        Constrói objeto URI a partir de string SIP URI.

        Args:
            uri (str): URI SIP completa, ex: sip:usuario@host:5060;param=1?header=val

        Returns:
            URI: Objeto URI preenchido.
        """
        regex = re.compile(
            r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+\-.]*):"
            r"(?:(?P<user>[^:@;]+)@)?"
            r"(?P<host>[^;?:]+)"
            r"(:(?P<port>\d+))?"
            r"(;(?P<params>[^?]+))?"
            r"(\?(?P<headers>.+))?"
        )
        m = regex.match(uri)
        if not m:
            raise ValueError(f"URI inválida: {uri}")
        gd = m.groupdict()
        return cls(
            scheme=gd["scheme"],
            user=gd["user"],
            host=gd["host"],
            port=int(gd["port"]) if gd["port"] else None,
            params=gd["params"],
            headers=gd["headers"],
        )


@dataclass
class Address:
    display_name: Optional[str]
    uri: URI

    @classmethod
    def parse(cls, raw: str):
        """
        Parseia um endereço SIP com display name opcional e URI.

        Args:
            raw (str): Exemplo: '"Fulano" <sip:fulano@dominio.com>' ou 'sip:fulano@dominio.com'

        Returns:
            Address: Objeto com display name e URI parsed.
        """
        if raw.startswith('"'):
            try:
                dn, uri = raw.split('" <', 1)
                display_name = dn.strip('" ')
                uri = uri.rstrip(">")
            except Exception:
                raise ValueError(f"Endereço SIP inválido: {raw}")
            return cls(display_name, URI.parse(uri))
        else:
            return cls(None, URI.parse(raw))
