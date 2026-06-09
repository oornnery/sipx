from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Coroutine, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sipx.sip import (
    SipCapabilities,
    SipRequest,
    SipResponse,
    SipUri,
    create_invite_request,
    create_request,
)
from sipx.sdp import create_audio_offer
from sipx.sip.transport import SipWireEvent
from sipx.ua import SipHooks, SipRetransmissionPolicy, SipUserAgent
from sipx.uac import SipUac
from sipx.uas import SipUas


CallAudioMode = Literal["none", "silence", "noise", "pyaudio"]


@dataclass(frozen=True, slots=True)
class PhoneAccountConfig:
    aor: SipUri
    registrar: SipUri
    username: str | None = None
    password: str | None = None
    contact_user: str | None = None
    expires: int = 3600

    @property
    def user(self) -> str:
        return self.contact_user or self.aor.user or "sipx"


@dataclass(frozen=True, slots=True)
class PhoneCommandConfig:
    account: PhoneAccountConfig
    remote: tuple[str, int]
    mode: str = "strict"
    local_host: str = "127.0.0.1"
    local_port: int = 0
    actor_id: str = "sip-client"
    timeout: float = 1.0
    retransmission_policy: SipRetransmissionPolicy | None = None
    lab_hooks: SipHooks | None = None
    media_host: str | None = None
    rtp_bind_host: str | None = None
    rtp_advertise_host: str | None = None
    media_port: int = 0
    jitter_buffer_ms: int = 60
    codecs: tuple[str, ...] = ("PCMU", "PCMA")
    telephone_event: bool = True
    target: str | None = None
    duration: float = 0.0
    keepalive: float = 0.0
    debug_sip: bool = False
    audio: CallAudioMode = "none"
    rtp_stats: bool = False
    metrics_json: Path | None = None
    print_message: bool = False
    compact_headers: bool = False
    dtmf: tuple[str, ...] = ()
    dtmf_duration_ms: int = 160


@dataclass(frozen=True, slots=True)
class SipRequestCommandConfig:
    method: str
    target: SipUri
    aor: SipUri
    remote: tuple[str, int]
    local_host: str
    local_port: int
    mode: str
    timeout: float
    actor_id: str
    contact_user: str | None = None
    username: str | None = None
    password: str | None = None
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""
    content_type: str | None = None
    include_headers: bool = False
    no_wait: bool = False
    debug_sip: bool = False
    print_message: bool = False
    compact_headers: bool = False
    capabilities: SipCapabilities | None = None


class PhoneCommandError(RuntimeError):
    pass


async def run_phone_register(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with _sip_uac(command) as uac:
        state = await uac.register()
        print(f"registered: {state.value}")
        print(f"contact: {uac.contact}")
        print(f"local: {_format_address(uac.local_address)}")
        if command.keepalive > 0:
            await asyncio.sleep(command.keepalive)
    return 0


async def run_phone_unregister(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with _sip_uac(command) as uac:
        state = await uac.unregister()
        print(f"unregistered: {state.value}")
        print(f"contact: {uac.contact}")
    return 0


async def run_phone_call(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    if command.target is None:
        raise ValueError("target is required")
    if command.print_message:
        _print_message(_build_call_invite_request(command), command.compact_headers)
        return 0
    started = time.monotonic()
    metrics: dict[str, Any] | None = None
    async with _sip_uac(command) as uac:
        call = await uac.call(command.target, audio=command.audio)
        print(f"call confirmed: {call.call_id}")
        print(f"remote: {_format_address(call.remote)}")
        for digits in command.dtmf:
            await uac.send_dtmf(call, digits, duration_ms=command.dtmf_duration_ms)
            print(f"dtmf sent: {digits}")
        if command.duration > 0:
            await asyncio.sleep(command.duration)
        rtp_session = uac.rtp_session(call)
        metrics = _call_metrics(
            call=call,
            started=started,
            rtp_snapshot=rtp_session.snapshot() if rtp_session is not None else None,
        )
        await uac.hangup(call)
        print(f"call terminated: {call.call_id}")
    _emit_metrics(command, metrics)
    return 0


async def run_phone_listen(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    started = time.monotonic()
    metrics: dict[str, Any] | None = None
    async with _sip_uas(command) as uas:
        print(f"listening: {_format_address(uas.local_address)}")
        call = await uas.answer(audio=command.audio)
        print(f"inbound answered: {call.call_id}")
        if command.duration > 0:
            await asyncio.sleep(command.duration)
            rtp_session = uas.rtp_session(call)
            metrics = _call_metrics(
                call=call,
                started=started,
                rtp_snapshot=rtp_session.snapshot()
                if rtp_session is not None
                else None,
            )
            await uas.hangup(call)
            print(f"call terminated: {call.call_id}")
        else:
            await asyncio.Event().wait()
    _emit_metrics(command, metrics)
    return 0


async def run_sip_request(args: argparse.Namespace) -> int:
    command = _sip_request_command_config(args)
    if command.print_message:
        contact = _contact_uri(
            command.aor,
            command.contact_user,
            (command.local_host, command.local_port),
        )
        request = _build_cli_request(
            command,
            contact=contact,
            call_id=_id("request"),
            from_tag=_tag("from"),
        )
        _print_message(request, command.compact_headers)
        return 0
    async with SipUserAgent(
        local_host=command.local_host,
        local_port=command.local_port,
        mode=command.mode,
        actor_id=command.actor_id,
        wire_event_handler=_debug_sip_event if command.debug_sip else None,
        compact_headers=command.compact_headers,
    ) as user_agent:
        contact = _contact_uri(
            command.aor, command.contact_user, user_agent.local_address
        )
        request = _build_cli_request(
            command,
            contact=contact,
            call_id=_id("request"),
            from_tag=_tag("from"),
        )
        print(f"> {request.method} {request.uri}")
        if command.no_wait:
            await user_agent.send_request(request, command.remote)
            print("sent")
            return 0
        response = await user_agent.request(
            command.method,
            command.target,
            remote=command.remote,
            caller=command.aor,
            contact=_contact_uri(
                command.aor, command.contact_user, user_agent.local_address
            ),
            timeout=command.timeout,
            body=command.body,
            content_type=command.content_type,
            headers=command.headers,
            capabilities=command.capabilities,
            username=command.username,
            password=command.password,
        )
        _print_response(response, include_headers=command.include_headers)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipx",
        description="SIP/RTP command-line client.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    _add_options_parser(_sip_request_parser(subcommands, "options"))
    _add_message_parser(_sip_request_parser(subcommands, "message"))
    _add_generic_request_parser(_sip_request_parser(subcommands, "request"))

    _add_phone_register_parser(_phone_parser(subcommands, "register"))
    _add_phone_unregister_parser(_phone_parser(subcommands, "unregister"))
    _add_phone_call_parser(_phone_parser(subcommands, "call"))
    _add_phone_listen_parser(_phone_parser(subcommands, "listen"))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"options", "message", "request"}:
        return _run_cli_command(run_sip_request(args))

    if args.command == "register":
        return _run_cli_command(run_phone_register(args))

    if args.command == "unregister":
        return _run_cli_command(run_phone_unregister(args))

    if args.command == "call":
        return _run_cli_command(run_phone_call(args))

    if args.command == "listen":
        return _run_cli_command(run_phone_listen(args))

    parser.error("unsupported command")
    return 2


def _add_sip_request_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--aor",
        "--from",
        dest="aor",
        help="From account URI, for example sip:1001@example.com.",
    )
    parser.add_argument(
        "--registrar",
        help="Registrar/proxy URI; used for default remote host/port.",
    )
    parser.add_argument("--username", help="Digest auth username.")
    parser.add_argument("--password", help="Digest auth password.")
    parser.add_argument(
        "--contact-user", help="User part for the generated Contact URI."
    )
    parser.add_argument("--remote-host", help="SIP peer host; defaults to target host.")
    parser.add_argument(
        "--remote-port",
        type=int,
        help="SIP peer UDP port; defaults to target port, registrar port, or 5060.",
    )
    parser.add_argument(
        "--local-host", default="127.0.0.1", help="Local UDP bind host."
    )
    parser.add_argument(
        "--local-port",
        type=int,
        default=0,
        help="Local UDP bind port; 0 picks a free port.",
    )
    parser.add_argument("--mode", choices=("strict", "lab"), help="SIP mode.")
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="SIP response timeout in seconds."
    )
    parser.add_argument("--actor-id", default="sip-client", help="Timeline actor id.")
    parser.add_argument(
        "-H",
        "--header",
        action="append",
        default=[],
        help='Extra SIP header, for example -H "X-Test: yes".',
    )
    parser.add_argument(
        "-d",
        "--data",
        "--body",
        dest="body",
        help="Request body text.",
    )
    parser.add_argument("--body-file", help="Read request body from a file.")
    parser.add_argument("--content-type", help="Content-Type for request body.")
    parser.add_argument(
        "-i",
        "--include",
        action="store_true",
        help="Print response headers before the response body.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Send the request and exit without waiting for a response.",
    )
    parser.add_argument(
        "--debug-sip",
        action="store_true",
        help="Print redacted SIP datagrams to stderr as they are sent and received.",
    )
    parser.add_argument(
        "--print-message",
        action="store_true",
        help="Print the generated SIP request and exit without opening a socket.",
    )
    parser.add_argument(
        "--compact-headers",
        action="store_true",
        help="Serialize compact SIP header names where RFC 3261 defines them.",
    )
    parser.add_argument(
        "--accept",
        action="append",
        default=[],
        help="Add an Accept media type; repeatable.",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Add an Allow method; repeatable.",
    )
    parser.add_argument(
        "--allow-event",
        action="append",
        default=[],
        help="Add an Allow-Events token; repeatable.",
    )
    parser.add_argument(
        "--supported",
        action="append",
        default=[],
        help="Add a Supported option tag; repeatable.",
    )


def _add_options_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target")
    _add_sip_request_common(parser)


def _add_message_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target")
    parser.add_argument("text", nargs="?", help="MESSAGE body text.")
    _add_sip_request_common(parser)


def _add_generic_request_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("method")
    parser.add_argument("target")
    _add_sip_request_common(parser)


def _add_phone_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--aor",
        "--from",
        dest="aor",
        help="Account address, for example sip:1001@example.com.",
    )
    parser.add_argument(
        "--registrar", help="Registrar URI, for example sip:pbx.example.com:5060."
    )
    parser.add_argument("--username", help="Digest auth username.")
    parser.add_argument("--password", help="Digest auth password.")
    parser.add_argument(
        "--contact-user", help="User part for the generated Contact URI."
    )
    parser.add_argument(
        "--remote-host", help="SIP peer host; defaults to registrar host."
    )
    parser.add_argument(
        "--remote-port",
        type=int,
        help="SIP peer UDP port; defaults to registrar port or 5060.",
    )
    parser.add_argument(
        "--local-host", default="127.0.0.1", help="Local UDP bind host."
    )
    parser.add_argument(
        "--local-port",
        type=int,
        default=0,
        help="Local UDP bind port; 0 picks a free port.",
    )
    parser.add_argument("--mode", choices=("strict", "lab"), help="SIP mode.")
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="SIP transaction timeout in seconds."
    )
    parser.add_argument(
        "--expires", type=int, default=3600, help="REGISTER expiration in seconds."
    )
    parser.add_argument("--actor-id", default="sip-client", help="Timeline actor id.")
    parser.add_argument(
        "--media-host",
        "--rtp-host",
        dest="media_host",
        help="Legacy alias for setting both RTP bind and advertised SDP address.",
    )
    parser.add_argument(
        "--rtp-bind",
        dest="rtp_bind_host",
        help="Local RTP UDP bind address; defaults to SIP local address.",
    )
    parser.add_argument(
        "--rtp-advertise",
        dest="rtp_advertise_host",
        help="RTP address advertised in SDP; defaults to RTP bind address.",
    )
    parser.add_argument(
        "--media-port",
        "--rtp-port",
        dest="media_port",
        type=int,
        help="Local RTP UDP port advertised in SDP; defaults to an ephemeral port.",
    )
    parser.add_argument(
        "--codec",
        action="append",
        help="Audio codec to offer; repeatable. Defaults to PCMU,PCMA.",
    )
    parser.add_argument(
        "--debug-sip",
        action="store_true",
        help="Print redacted SIP datagrams to stderr as they are sent and received.",
    )
    parser.add_argument(
        "--compact-headers",
        action="store_true",
        help="Serialize compact SIP header names where RFC 3261 defines them.",
    )


def _add_call_media_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--audio",
        choices=("none", "silence", "noise", "pyaudio"),
        default="none",
        help="RTP audio source for SDP calls; pyaudio lazy-imports optional PyAudio.",
    )
    parser.add_argument(
        "--jitter-buffer-ms",
        type=int,
        default=60,
        help="Target RTP jitter buffer depth in milliseconds.",
    )
    parser.add_argument(
        "--rtp-stats",
        action="store_true",
        help="Print RTP/call metrics after the call ends.",
    )
    parser.add_argument(
        "--metrics-json",
        type=Path,
        help="Write call/RTP metrics JSON to this path.",
    )
    parser.add_argument(
        "--print-message",
        action="store_true",
        help="Print the generated INVITE and exit without opening a SIP/RTP socket.",
    )


def _add_phone_register_parser(parser: argparse.ArgumentParser) -> None:
    _add_phone_common(parser)
    parser.add_argument(
        "--keepalive",
        type=float,
        default=0.0,
        help="Keep the registered socket alive for N seconds before exit.",
    )


def _add_phone_unregister_parser(parser: argparse.ArgumentParser) -> None:
    _add_phone_common(parser)


def _add_phone_call_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target")
    _add_phone_common(parser)
    _add_call_media_parser(parser)
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=5.0,
        help="Seconds to hold the call before sending BYE.",
    )
    parser.add_argument(
        "--dtmf",
        action="append",
        default=[],
        help="Send DTMF digits over SIP INFO after the call is confirmed; repeatable.",
    )
    parser.add_argument(
        "--dtmf-duration-ms",
        type=int,
        default=160,
        help="Duration advertised for each SIP INFO DTMF digit.",
    )


def _add_phone_listen_parser(parser: argparse.ArgumentParser) -> None:
    _add_phone_common(parser)
    _add_call_media_parser(parser)
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=0.0,
        help="Seconds to keep an answered inbound call before BYE; 0 waits forever.",
    )


def _phone_command_config(args: argparse.Namespace) -> PhoneCommandConfig:
    account = _phone_account(args)
    return PhoneCommandConfig(
        account=account,
        remote=_phone_remote(args, _sip_uri(account.registrar)),
        mode=str(args.mode or "strict"),
        local_host=args.local_host,
        local_port=args.local_port,
        actor_id=args.actor_id,
        timeout=args.timeout,
        media_host=args.media_host,
        rtp_bind_host=getattr(args, "rtp_bind_host", None),
        rtp_advertise_host=getattr(args, "rtp_advertise_host", None),
        media_port=args.media_port or 0,
        jitter_buffer_ms=int(getattr(args, "jitter_buffer_ms", 60)),
        codecs=_phone_codecs(args),
        target=getattr(args, "target", None),
        duration=float(getattr(args, "duration", 0.0)),
        keepalive=float(getattr(args, "keepalive", 0.0)),
        debug_sip=args.debug_sip,
        print_message=bool(getattr(args, "print_message", False)),
        compact_headers=bool(getattr(args, "compact_headers", False)),
        audio=_call_audio_mode(getattr(args, "audio", "none")),
        rtp_stats=bool(getattr(args, "rtp_stats", False)),
        metrics_json=getattr(args, "metrics_json", None),
        dtmf=tuple(getattr(args, "dtmf", ()) or ()),
        dtmf_duration_ms=int(getattr(args, "dtmf_duration_ms", 160)),
    )


def _sip_uac(command: PhoneCommandConfig) -> SipUac:
    return SipUac(
        aor=command.account.aor,
        registrar=command.account.registrar,
        remote=command.remote,
        username=command.account.username,
        password=command.account.password,
        contact_user=command.account.contact_user,
        expires=command.account.expires,
        timeout=command.timeout,
        media_host=command.media_host,
        rtp_bind_host=command.rtp_bind_host,
        rtp_advertise_host=command.rtp_advertise_host,
        media_port=command.media_port,
        jitter_buffer_ms=command.jitter_buffer_ms,
        codecs=command.codecs,
        telephone_event=command.telephone_event,
        local_host=command.local_host,
        local_port=command.local_port,
        mode=command.mode,
        actor_id=command.actor_id,
        retransmission_policy=command.retransmission_policy,
        lab_hooks=command.lab_hooks,
        wire_event_handler=_debug_sip_event if command.debug_sip else None,
    )


def _sip_uas(command: PhoneCommandConfig) -> SipUas:
    return SipUas(
        aor=command.account.aor,
        username=command.account.username,
        password=command.account.password,
        contact_user=command.account.contact_user,
        timeout=command.timeout,
        media_host=command.media_host,
        rtp_bind_host=command.rtp_bind_host,
        rtp_advertise_host=command.rtp_advertise_host,
        media_port=command.media_port,
        jitter_buffer_ms=command.jitter_buffer_ms,
        codecs=command.codecs,
        telephone_event=command.telephone_event,
        local_host=command.local_host,
        local_port=command.local_port,
        mode=command.mode,
        actor_id=command.actor_id,
        retransmission_policy=command.retransmission_policy,
        lab_hooks=command.lab_hooks,
        wire_event_handler=_debug_sip_event if command.debug_sip else None,
    )


def _phone_account(args: argparse.Namespace) -> PhoneAccountConfig:
    aor = args.aor
    registrar = args.registrar
    if not aor or not registrar:
        raise PhoneCommandError(
            "SIP command requires explicit --aor and --registrar; "
            "try `sipx register --help`"
        )
    return PhoneAccountConfig(
        aor=SipUri.parse(str(aor)),
        registrar=SipUri.parse(str(registrar)),
        username=args.username,
        password=args.password,
        contact_user=args.contact_user,
        expires=args.expires,
    )


def _phone_remote(
    args: argparse.Namespace,
    registrar: SipUri,
) -> tuple[str, int]:
    if args.remote_host is not None:
        host = args.remote_host
    else:
        host = registrar.host

    if args.remote_port is not None:
        port = args.remote_port
    else:
        port = registrar.port or 5060

    return host, port


def _phone_codecs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.codec:
        return tuple(str(codec) for codec in args.codec)
    return ("PCMU", "PCMA")


def _sip_request_command_config(args: argparse.Namespace) -> SipRequestCommandConfig:
    target = SipUri.parse(args.target)
    aor = _request_aor(args)
    registrar = _optional_sip_uri(args.registrar)
    method = _request_method(args).upper()
    body = _request_body(args)
    content_type = args.content_type or ("text/plain" if method == "MESSAGE" else None)
    return SipRequestCommandConfig(
        method=method,
        target=target,
        aor=aor,
        remote=_request_remote(args, target, registrar),
        local_host=args.local_host,
        local_port=args.local_port,
        mode=str(args.mode or "strict"),
        timeout=args.timeout,
        actor_id=args.actor_id,
        contact_user=args.contact_user,
        username=args.username,
        password=args.password,
        headers=tuple(_parse_header(header) for header in args.header),
        body=body,
        content_type=content_type,
        include_headers=args.include,
        no_wait=args.no_wait,
        debug_sip=args.debug_sip,
        print_message=args.print_message,
        compact_headers=args.compact_headers,
        capabilities=_request_capabilities(args),
    )


def _request_method(args: argparse.Namespace) -> str:
    if args.command == "options":
        return "OPTIONS"
    if args.command == "message":
        return "MESSAGE"
    return args.method


def _request_aor(args: argparse.Namespace) -> SipUri:
    value = args.aor
    if not value:
        raise PhoneCommandError(
            "SIP request command requires --from/--aor; try `sipx request --help`"
        )
    return SipUri.parse(str(value))


def _request_remote(
    args: argparse.Namespace,
    target: SipUri,
    registrar: SipUri | None,
) -> tuple[str, int]:
    if args.remote_host is not None:
        host = args.remote_host
    elif registrar is not None:
        host = registrar.host
    else:
        host = target.host

    if args.remote_port is not None:
        port = args.remote_port
    elif registrar is not None and registrar.port is not None:
        port = registrar.port
    else:
        port = target.port or 5060

    return host, port


def _request_capabilities(args: argparse.Namespace) -> SipCapabilities | None:
    capabilities = SipCapabilities(
        accept=tuple(args.accept),
        allow=tuple(args.allow),
        allow_events=tuple(args.allow_event),
        supported=tuple(args.supported),
    )
    if not any(
        (
            capabilities.accept,
            capabilities.allow,
            capabilities.allow_events,
            capabilities.supported,
        )
    ):
        return None
    return capabilities


def _call_audio_mode(value: object) -> CallAudioMode:
    if value == "none":
        return "none"
    if value == "silence":
        return "silence"
    if value == "noise":
        return "noise"
    if value == "pyaudio":
        return "pyaudio"
    raise PhoneCommandError("audio must be none, silence, noise, or pyaudio")


def _request_body(args: argparse.Namespace) -> bytes:
    text = getattr(args, "text", None)
    sources = [value is not None for value in (text, args.body, args.body_file)]
    if sum(sources) > 1:
        raise PhoneCommandError("use only one request body source")
    if text is not None:
        return text.encode("utf-8")
    if args.body is not None:
        return args.body.encode("utf-8")
    if args.body_file is not None:
        return Path(args.body_file).read_bytes()
    return b""


def _parse_header(value: str) -> tuple[str, str]:
    if ":" in value:
        name, header_value = value.split(":", 1)
    elif "=" in value:
        name, header_value = value.split("=", 1)
    else:
        raise PhoneCommandError("headers must be formatted as 'Name: value'")
    name = name.strip()
    if not name:
        raise PhoneCommandError("header name is required")
    return name, header_value.strip()


def _build_cli_request(
    command: SipRequestCommandConfig,
    *,
    contact: SipUri,
    call_id: str,
    from_tag: str,
    cseq: int = 1,
    auth_header: tuple[str, str] | None = None,
) -> SipRequest:
    return create_request(
        method=command.method,
        target=command.target,
        caller=command.aor,
        contact=contact,
        call_id=call_id,
        branch=_branch(command.method.lower()),
        from_tag=from_tag,
        cseq=cseq,
        body=command.body,
        content_type=command.content_type,
        headers=command.headers,
        capabilities=command.capabilities,
        auth_header=auth_header,
    )


def _build_call_invite_request(command: PhoneCommandConfig) -> SipRequest:
    target = _sip_uri(command.target or "")
    contact = _contact_uri(
        command.account.aor,
        command.account.contact_user,
        (command.local_host, command.local_port),
    )
    body = b""
    content_type = None
    media_port = command.media_port
    media_host = (
        command.rtp_advertise_host or command.rtp_bind_host or command.local_host
    )
    offer = create_audio_offer(
        connection_address=media_host,
        port=media_port,
        codecs=command.codecs,
        telephone_event=command.telephone_event,
    )
    body = offer.to_sdp().encode("utf-8")
    content_type = "application/sdp"
    return create_invite_request(
        target=target,
        caller=command.account.aor,
        contact=contact,
        call_id=_id("call"),
        branch=_branch("invite"),
        from_tag=_tag("from"),
        body=body,
        content_type=content_type,
    )


def _print_message(message: SipRequest, compact_headers: bool) -> None:
    sys.stdout.buffer.write(message.to_bytes(compact_headers=compact_headers))


async def _receive_cli_response(
    user_agent: SipUserAgent,
    *,
    call_id: str,
    method: str,
    timeout: float,
    cseq: int,
) -> SipResponse:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PhoneCommandError("timed out waiting for SIP response")
        event = await user_agent.receive_event(timeout=remaining)
        message = event.message
        if not isinstance(message, SipResponse):
            continue
        if message.headers.get("Call-ID") != call_id:
            continue
        if _cseq_method(message.headers.get("CSeq")) != method:
            continue
        if _cseq_number(message.headers.get("CSeq")) != cseq:
            continue
        return message


def _cseq_method(value: str | None) -> str | None:
    if value is None:
        return None
    _number, _separator, method = value.partition(" ")
    return method or None


def _cseq_number(value: str | None) -> int | None:
    if value is None:
        return None
    number, _separator, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError:
        return None


def _print_response(response: SipResponse, *, include_headers: bool) -> None:
    reason = f" {response.reason}" if response.reason else ""
    print(f"< {response.status_code}{reason}")
    if include_headers:
        for name, value in response.headers.items():
            print(f"{name}: {value}")
        if response.body:
            print()
    if response.body:
        print(response.body.decode("utf-8", errors="replace"), end="")


def _call_metrics(
    *,
    call: Any,
    started: float,
    rtp_snapshot: Any | None,
) -> dict[str, Any]:
    ended = time.monotonic()
    return {
        "call_id": call.call_id,
        "duration_seconds": ended - started,
        "remote": {"host": call.remote[0], "port": call.remote[1]},
        "state": call.state.value,
        "sdp": {
            "local": _sdp_metrics(call.local_sdp),
            "remote": _sdp_metrics(call.remote_sdp),
        },
        "rtp": asdict(rtp_snapshot) if rtp_snapshot is not None else None,
    }


def _sdp_metrics(sdp: Any | None) -> dict[str, Any] | None:
    if sdp is None or sdp.audio is None:
        return None
    return {
        "connection_address": sdp.connection_address,
        "audio_port": sdp.audio.port,
        "direction": sdp.audio.direction,
        "codecs": [
            sdp.audio.codecs[payload].name
            for payload in sdp.audio.payload_types
            if payload in sdp.audio.codecs
        ],
    }


def _emit_metrics(command: PhoneCommandConfig, metrics: dict[str, Any] | None) -> None:
    if metrics is None:
        return
    if command.rtp_stats:
        _print_metrics(metrics)
    if command.metrics_json is not None:
        command.metrics_json.write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _print_metrics(metrics: dict[str, Any]) -> None:
    print(f"duration: {metrics['duration_seconds']:.3f}s")
    rtp = metrics.get("rtp")
    if rtp is None:
        print("rtp: none")
        return
    rx = rtp["metrics"]["rx"]
    print(f"rtp.local: {_format_address(tuple(rtp['local_address']))}")
    print(f"rtp.codec: {rtp['codec']}/{rtp['payload_type']}")
    print(
        f"rtp.tx: {rtp['metrics']['tx_packets']} packets, {rtp['metrics']['tx_bytes']} bytes"
    )
    print(f"rtp.rx: {rx['received']} packets, {rx['bytes']} bytes")
    print(f"rtp.loss: {rx['lost']} packets, {rx['loss_percent']:.2f}%")
    print(f"rtp.jitter: {rx['jitter_ms']:.3f} ms")
    print(f"rtp.duplicates: {rx['duplicates']}")
    print(f"rtp.late_drops: {rx['late_drops']}")
    print(f"rtp.buffer.depth: {rtp['jitter_buffer']['depth_ms']} ms")


def _debug_sip_event(event: SipWireEvent) -> None:
    direction = event.direction.value.upper()
    print(
        f"--- SIP {direction} {_format_address(event.remote)} {len(event.raw)} bytes ---",
        file=sys.stderr,
    )
    if event.error is not None:
        print(f"# parse-error: {event.error}", file=sys.stderr)
    text = event.raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    text = _redact_sip_text(text)
    print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
    print(f"--- END SIP {direction} ---", file=sys.stderr)


def _redact_sip_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        name, separator, _value = line.partition(":")
        lowered = name.strip().lower()
        if separator and lowered in {"authorization", "proxy-authorization"}:
            lines.append(f"{name}: [REDACTED]")
        elif line.strip().lower().startswith("a=crypto:"):
            lines.append("a=crypto: [REDACTED]")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _response_digest_challenge(response: SipResponse) -> tuple[str, str] | None:
    if response.status_code == 401:
        value = response.headers.get("WWW-Authenticate")
        return ("Authorization", value) if value is not None else None
    if response.status_code == 407:
        value = response.headers.get("Proxy-Authenticate")
        return ("Proxy-Authorization", value) if value is not None else None
    return None


def _has_request_credentials(command: SipRequestCommandConfig) -> bool:
    return bool(command.username and command.password)


def _contact_uri(
    aor: SipUri,
    contact_user: str | None,
    local_address: tuple[str, int],
) -> SipUri:
    return SipUri(
        scheme="sip",
        user=contact_user or aor.user or "sipx",
        host=local_address[0],
        port=local_address[1] or None,
    )


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _branch(prefix: str) -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def _tag(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _sip_uri(value: SipUri | str) -> SipUri:
    return value if isinstance(value, SipUri) else SipUri.parse(value)


def _optional_sip_uri(value: object) -> SipUri | None:
    return None if value in (None, "") else SipUri.parse(str(value))


def _format_address(address: tuple[str, int]) -> str:
    return f"{address[0]}:{address[1]}"


def _phone_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    examples = {
        "register": (
            "examples:\n"
            "  sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password secret"
        ),
        "unregister": (
            "examples:\n"
            "  sipx unregister --aor sip:1001@example.com --registrar sip:pbx.example.com"
        ),
        "call": (
            "examples:\n"
            "  sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --audio noise --rtp-stats\n"
            "  sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --metrics-json metrics.json"
        ),
        "listen": (
            "examples:\n"
            "  sipx listen --aor sip:1001@example.com --registrar sip:pbx.example.com --local-port 5062 --audio silence --duration 30"
        ),
    }
    return subcommands.add_parser(
        name,
        description=f"SIP {name} command.",
        epilog=examples[name],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _sip_request_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    descriptions = {
        "options": "Send a SIP OPTIONS request over UDP.",
        "message": "Send a SIP MESSAGE request over UDP.",
        "request": "Send a generic SIP request over UDP.",
    }
    examples = {
        "options": (
            "examples:\n"
            "  sipx options sip:pbx.example.com --from sip:1001@example.com -i"
        ),
        "message": (
            "examples:\n"
            "  sipx message sip:1002@example.com 'hello' --from sip:1001@example.com"
        ),
        "request": (
            "examples:\n"
            "  sipx request OPTIONS sip:pbx.example.com --from sip:1001@example.com\n"
            "  sipx request INFO sip:1002@example.com --from sip:1001@example.com -H 'Content-Type: application/dtmf-relay' -d 'Signal=1'"
        ),
    }
    return subcommands.add_parser(
        name,
        description=descriptions[name],
        epilog=examples[name],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _run_cli_command(coro: Coroutine[Any, Any, int]) -> int:
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130
    except PhoneCommandError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "build_parser",
    "main",
    "run_phone_call",
    "run_phone_listen",
    "run_phone_register",
    "run_phone_unregister",
    "run_sip_request",
]
