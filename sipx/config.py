from dataclasses import dataclass


@dataclass
class ClientConfig:
    """Configuration for SIP client behavior.

    Defaults match existing sipx behavior where applicable.
    New httpx-like fields (user_agent) are added for the evolving API.
    """

    transport: str = "udp"
    local_host: str = "0.0.0.0"
    local_port: int = 0
    timeout: float = 30.0
    max_message_size: int = 65535
    user_agent: str = "sipx/2.0"
    from_uri: str | None = None
    contact_uri: str | None = None
