from __future__ import annotations

from sipx.sip.dialog import Dialog, header_tag
from sipx.sip.headers import HeaderMap
from sipx.sip.message import SipRequest, SipResponse
from sipx.sip.uri import SipUri


def create_register_request(
    *,
    registrar: SipUri,
    aor: SipUri,
    contact: SipUri,
    call_id: str,
    branch: str,
    from_tag: str,
    cseq: int = 1,
    expires: int | None = None,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {contact.host};branch={branch}")
    headers.add("From", f"<{aor}>;tag={from_tag}")
    headers.add("To", f"<{aor}>")
    headers.add("Call-ID", call_id)
    headers.add("CSeq", f"{cseq} REGISTER")
    headers.add("Contact", f"<{contact}>")
    headers.add("Max-Forwards", "70")
    if expires is not None:
        headers.add("Expires", str(expires))
    return SipRequest(method="REGISTER", uri=registrar, headers=headers)


def create_bye_request(
    *,
    dialog: Dialog,
    request_uri: SipUri,
    via_host: str,
    branch: str,
    max_forwards: int = 70,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {via_host};branch={branch}")
    headers.add("From", dialog.local_uri)
    headers.add("To", dialog.remote_uri)
    headers.add("Call-ID", dialog.dialog_id.call_id)
    headers.add("CSeq", dialog.next_local_cseq("BYE"))
    headers.add("Max-Forwards", str(max_forwards))
    return SipRequest(method="BYE", uri=request_uri, headers=headers)


def create_info_request(
    *,
    dialog: Dialog,
    request_uri: SipUri,
    via_host: str,
    branch: str,
    body: bytes = b"",
    content_type: str | None = None,
    max_forwards: int = 70,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {via_host};branch={branch}")
    headers.add("From", dialog.local_uri)
    headers.add("To", dialog.remote_uri)
    headers.add("Call-ID", dialog.dialog_id.call_id)
    headers.add("CSeq", dialog.next_local_cseq("INFO"))
    headers.add("Max-Forwards", str(max_forwards))
    if content_type is not None:
        headers.add("Content-Type", content_type)
    return SipRequest(method="INFO", uri=request_uri, headers=headers, body=body)


def create_invite_request(
    *,
    target: SipUri,
    caller: SipUri,
    contact: SipUri,
    call_id: str,
    branch: str,
    from_tag: str,
    cseq: int = 1,
    body: bytes = b"",
    content_type: str | None = None,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {contact.host};branch={branch}")
    headers.add("From", f"<{caller}>;tag={from_tag}")
    headers.add("To", f"<{target}>")
    headers.add("Call-ID", call_id)
    headers.add("CSeq", f"{cseq} INVITE")
    headers.add("Contact", f"<{contact}>")
    headers.add("Max-Forwards", "70")
    if content_type is not None:
        headers.add("Content-Type", content_type)
    return SipRequest(method="INVITE", uri=target, headers=headers, body=body)


def create_ack_request(
    *,
    invite: SipRequest,
    response: SipResponse,
    via_host: str,
    branch: str,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {via_host};branch={branch}")
    headers.add("From", _required_header(invite, "From"))
    headers.add("To", _required_header(response, "To"))
    headers.add("Call-ID", _required_header(invite, "Call-ID"))
    headers.add("CSeq", f"{_cseq_number(_required_header(invite, 'CSeq'))} ACK")
    headers.add("Max-Forwards", invite.headers.get("Max-Forwards", "70") or "70")
    return SipRequest(method="ACK", uri=invite.uri, headers=headers)


def create_response_for_request(
    *,
    request: SipRequest,
    status_code: int,
    reason: str,
    to_tag: str | None = None,
    contact: SipUri | None = None,
    body: bytes = b"",
    content_type: str | None = None,
) -> SipResponse:
    headers = HeaderMap()
    for via in request.headers.get_all("Via"):
        headers.add("Via", via)
    headers.add("From", _required_header(request, "From"))
    headers.add("To", _tagged_to_header(_required_header(request, "To"), to_tag))
    headers.add("Call-ID", _required_header(request, "Call-ID"))
    headers.add("CSeq", _required_header(request, "CSeq"))
    if contact is not None:
        headers.add("Contact", f"<{contact}>")
    if content_type is not None:
        headers.add("Content-Type", content_type)
    return SipResponse(
        status_code=status_code,
        reason=reason,
        headers=headers,
        body=body,
    )


def _required_header(message: SipRequest | SipResponse, name: str) -> str:
    value = message.headers.get(name)
    if value is None:
        raise ValueError(f"missing required SIP header: {name}")
    return value


def _tagged_to_header(value: str, tag: str | None) -> str:
    if tag is None or header_tag(value):
        return value
    return f"{value};tag={tag}"


def _cseq_number(value: str) -> int:
    number, _, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError as exc:
        raise ValueError(f"invalid CSeq header: {value!r}") from exc
