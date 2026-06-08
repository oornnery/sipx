import pytest

from sipx import (
    HeaderMap,
    NonInviteClientTransaction,
    RegisterClientError,
    RegisterClientFlow,
    RegisterClientState,
    SipResponse,
    SipUri,
    build_digest_authorization,
    create_register_request,
    parse_digest_challenge,
)


def register_flow() -> RegisterClientFlow:
    return RegisterClientFlow(
        registrar=SipUri.parse("sip:example.com"),
        aor=SipUri.parse("sip:alice@example.com"),
        contact=SipUri.parse("sip:alice@192.0.2.10:5060"),
        call_id="register-1",
        from_tag="from-1",
        expires=3600,
    )


def register_response(
    status_code: int,
    reason: str,
    *,
    challenge_header: str | None = None,
    challenge: str | None = None,
) -> SipResponse:
    headers = HeaderMap()
    headers.add("Call-ID", "register-1")
    if challenge_header and challenge:
        headers.add(challenge_header, challenge)
    return SipResponse(status_code=status_code, reason=reason, headers=headers)


def test_create_register_request_sets_required_headers() -> None:
    request = create_register_request(
        registrar=SipUri.parse("sip:example.com"),
        aor=SipUri.parse("sip:alice@example.com"),
        contact=SipUri.parse("sip:alice@192.0.2.10:5060"),
        call_id="register-1",
        branch="z9hG4bK-register",
        from_tag="from-1",
        expires=3600,
    )

    assert request.method == "REGISTER"
    assert (
        request.headers.get("Via") == "SIP/2.0/UDP 192.0.2.10;branch=z9hG4bK-register"
    )
    assert request.headers.get("From") == "<sip:alice@example.com>;tag=from-1"
    assert request.headers.get("To") == "<sip:alice@example.com>"
    assert request.headers.get("Contact") == "<sip:alice@192.0.2.10:5060>"
    assert request.headers.get("Expires") == "3600"


def test_non_invite_client_transaction_tracks_final_response() -> None:
    request = create_register_request(
        registrar=SipUri.parse("sip:example.com"),
        aor=SipUri.parse("sip:alice@example.com"),
        contact=SipUri.parse("sip:alice@192.0.2.10"),
        call_id="register-1",
        branch="z9hG4bK-register",
        from_tag="from-1",
    )
    transaction = NonInviteClientTransaction(request)
    headers = HeaderMap()
    headers.add("Call-ID", "register-1")
    response = SipResponse(status_code=401, reason="Unauthorized", headers=headers)

    state = transaction.receive_response(response)

    assert state == "completed"
    assert transaction.final_response == response

    transaction.terminate()
    assert transaction.state == "terminated"


def test_register_client_flow_creates_initial_register() -> None:
    flow = register_flow()

    request = flow.create_register(branch="z9hG4bK-register")

    assert flow.state == RegisterClientState.READY
    assert flow.cseq == 1
    assert request.method == "REGISTER"
    assert request.headers.get("CSeq") == "1 REGISTER"
    assert request.headers.get("Expires") == "3600"


def test_register_client_flow_retries_digest_challenge_without_storing_secret() -> None:
    flow = register_flow()
    flow.create_register(branch="z9hG4bK-register")
    challenge = 'Digest realm="example.com", nonce="nonce-1", qop="auth"'

    state = flow.receive_response(
        register_response(
            401,
            "Unauthorized",
            challenge_header="WWW-Authenticate",
            challenge=challenge,
        )
    )
    retry = flow.create_authenticated_register(
        branch="z9hG4bK-register-auth",
        username="alice",
        password="secret-password",
        cnonce="cnonce-1",
    )

    authorization = retry.headers.get("Authorization") or ""
    assert state == RegisterClientState.CHALLENGED
    assert retry.headers.get("CSeq") == "2 REGISTER"
    assert 'username="alice"' in authorization
    assert 'nonce="nonce-1"' in authorization
    assert "qop=auth" in authorization
    assert "secret-password" not in authorization


def test_register_client_flow_marks_success_and_failure_states() -> None:
    flow = register_flow()
    flow.create_register(branch="z9hG4bK-register")

    assert flow.receive_response(register_response(200, "OK")) == "registered"

    failed = register_flow()
    failed.create_register(branch="z9hG4bK-register-failed")
    assert failed.receive_response(register_response(403, "Forbidden")) == "failed"


def test_register_client_flow_creates_unregister_and_marks_unregistered() -> None:
    flow = register_flow()

    request = flow.create_unregister(branch="z9hG4bK-unregister")

    assert request.headers.get("CSeq") == "1 REGISTER"
    assert request.headers.get("Expires") == "0"
    assert flow.receive_response(register_response(200, "OK")) == "unregistered"


def test_register_client_flow_requires_challenge_before_auth_retry() -> None:
    flow = register_flow()

    with pytest.raises(RegisterClientError):
        flow.create_authenticated_register(
            branch="z9hG4bK-register-auth",
            username="alice",
            password="secret-password",
            cnonce="cnonce-1",
        )


def test_digest_authorization_matches_rfc_example() -> None:
    challenge = parse_digest_challenge(
        'Digest realm="testrealm@host.com", '
        'qop="auth,auth-int", '
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", '
        'opaque="5ccc069c403ebaf9f0171e9517f40e41"'
    )

    authorization = build_digest_authorization(
        username="Mufasa",
        password="Circle Of Life",
        method="GET",
        uri="/dir/index.html",
        challenge=challenge,
        cnonce="0a4f113b",
        nonce_count="00000001",
    )

    assert 'response="6629fae49393a05397450978507c4ef1"' in authorization
    assert "qop=auth" in authorization
    assert 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in authorization
