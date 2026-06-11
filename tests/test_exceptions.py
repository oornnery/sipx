from sipx.exceptions import (
    AuthError,
    DialogError,
    ProtocolError,
    SipError,
    TimeoutError,
    TransactionError,
    TransportError,
)


def test_sip_error_base():
    e = SipError(
        "something went wrong",
        details={"host": "example.com"},
        rfc_ref="RFC 3261 §1",
    )
    assert e.message == "something went wrong"
    assert e.details == {"host": "example.com"}
    assert e.rfc_ref == "RFC 3261 §1"
    assert str(e) == "something went wrong"

    e_default = SipError("minimal")
    assert e_default.details == {}
    assert e_default.rfc_ref is None


def test_transport_error():
    assert issubclass(TransportError, SipError)
    e = TransportError(
        "connection refused",
        details={"host": "example.com", "port": 5060},
        rfc_ref="RFC 3261 §18.1",
    )
    assert e.message == "connection refused"
    assert e.details == {"host": "example.com", "port": 5060}
    assert e.rfc_ref == "RFC 3261 §18.1"


def test_timeout_error():
    assert issubclass(TimeoutError, SipError)
    e = TimeoutError(
        "transaction timed out",
        details={"timer": "Timer H"},
        rfc_ref="RFC 3261 §17.1.1",
    )
    assert e.message == "transaction timed out"
    assert e.details == {"timer": "Timer H"}
    assert e.rfc_ref == "RFC 3261 §17.1.1"


def test_protocol_error():
    assert issubclass(ProtocolError, SipError)
    e = ProtocolError(
        "malformed Via header",
        details={"header": "Via"},
        rfc_ref="RFC 3261 §20.42",
    )
    assert e.message == "malformed Via header"
    assert e.details == {"header": "Via"}
    assert e.rfc_ref == "RFC 3261 §20.42"


def test_auth_error():
    assert issubclass(AuthError, SipError)
    e = AuthError(
        "digest challenge failed",
        details={"realm": "example.com"},
        rfc_ref="RFC 3261 §22",
    )
    assert e.message == "digest challenge failed"
    assert e.details == {"realm": "example.com"}
    assert e.rfc_ref == "RFC 3261 §22"


def test_dialog_error():
    assert issubclass(DialogError, SipError)
    e = DialogError(
        "dialog not found",
        details={"call_id": "abc123"},
        rfc_ref="RFC 3261 §12",
    )
    assert e.message == "dialog not found"
    assert e.details == {"call_id": "abc123"}
    assert e.rfc_ref == "RFC 3261 §12"


def test_transaction_error():
    assert issubclass(TransactionError, SipError)
    e = TransactionError(
        "unexpected state transition",
        details={"from": "calling", "to": "terminated"},
        rfc_ref="RFC 3261 §17.1",
    )
    assert e.message == "unexpected state transition"
    assert e.details == {"from": "calling", "to": "terminated"}
    assert e.rfc_ref == "RFC 3261 §17.1"
