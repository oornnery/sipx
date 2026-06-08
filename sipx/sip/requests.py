from __future__ import annotations

from sipx.sip.dialog import Dialog
from sipx.sip.headers import HeaderMap
from sipx.sip.message import SipRequest
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
