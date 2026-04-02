"""Smoke tests against the local Asterisk container."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pytest

from sipx import SIPClient, SDPBody

if os.getenv("ASTERISK_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(
        reason="Set ASTERISK_INTEGRATION=1 to run Asterisk integration tests."
    )

ASTERISK_HOST = os.getenv("ASTERISK_HOST", "127.0.0.1")
CLIENT_HOST = os.getenv("ASTERISK_CLIENT_HOST", "127.0.0.1")
ECHO_EXTENSION = "100"


@dataclass(frozen=True)
class User:
    username: str
    password: str
    client_port: int


USER_1111 = User("1111", "1111xxx", 5161)
USER_2222 = User("2222", "2222xxx", 5162)
USER_3333 = User("3333", "3333xxx", 5163)
ALL_USERS = (USER_1111, USER_2222, USER_3333)


def _aor(user: User) -> str:
    return f"sip:{user.username}@{ASTERISK_HOST}"


def _contact(user: User, client: SIPClient) -> dict[str, str]:
    return {
        "Contact": (
            f"<sip:{user.username}@{client.local_address.host}:{client.local_address.port}>"
        )
    }


def _register(client: SIPClient, user: User, expires: int = 60):
    response = client.register(_aor(user), expires=expires)
    assert response is not None
    return response


def _unregister(client: SIPClient, user: User):
    response = client.unregister(_aor(user))
    assert response is not None
    return response


def test_register_and_unregister_users():
    for user in ALL_USERS:
        with SIPClient(
            local_host=CLIENT_HOST,
            local_port=user.client_port,
            auth=(user.username, user.password),
        ) as client:
            response = _register(client, user)
            assert response.status_code == 200

            response = _unregister(client, user)
            assert response.status_code == 200


def test_user_2222_accepts_options():
    with SIPClient(
        local_host=CLIENT_HOST,
        local_port=5262,
        auth=(USER_2222.username, USER_2222.password),
    ) as client:
        response = client.options(f"sip:{ASTERISK_HOST}")
        assert response is not None
        assert response.status_code == 200


def test_user_3333_rejects_invalid_credentials():
    with SIPClient(
        local_host=CLIENT_HOST,
        local_port=5263,
        auth=(USER_3333.username, "WRONG"),
    ) as client:
        response = _register(client, USER_3333)
        assert response.status_code in (401, 403)


def test_user_1111_can_complete_echo_call():
    with SIPClient(
        local_host=CLIENT_HOST,
        local_port=5261,
        auth=(USER_1111.username, USER_1111.password),
    ) as client:
        register_response = _register(client, USER_1111)
        assert register_response.status_code == 200

        offer = SDPBody.audio(ip=CLIENT_HOST, port=8100)
        invite_response = client.invite(
            to_uri=f"sip:{ECHO_EXTENSION}@{ASTERISK_HOST}",
            body=offer.to_string(),
            headers=_contact(USER_1111, client),
        )
        assert invite_response is not None
        assert invite_response.status_code == 200

        client.ack()
        time.sleep(1)

        bye_response = client.bye()
        assert bye_response is not None
        assert bye_response.status_code == 200

        unregister_response = _unregister(client, USER_1111)
        assert unregister_response.status_code == 200
