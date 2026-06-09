from __future__ import annotations

import argparse
import asyncio
import runpy
import sys
import time
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sipx.backends import NativeSipBackend
from sipx.core import (
    Harness,
    Profile,
    Scenario,
    ScenarioRecorder,
    Timeline,
    Verdict,
    load_profiles,
    render_text_report,
)
from sipx.security.redaction import default_redactor
from sipx.sip import (
    HeaderMap,
    SipRequest,
    SipResponse,
    SipUri,
    build_digest_authorization,
    parse_digest_challenge,
)
from sipx.sip.transport import SipWireEvent
from sipx_softphone import (
    NativeSoftphone,
    NativeSoftphoneAccount,
    NativeSoftphoneConfig,
)


@dataclass(frozen=True, slots=True)
class PhoneCommandConfig:
    config: NativeSoftphoneConfig
    target: str | None = None
    duration: float = 0.0
    keepalive: float = 0.0
    debug_sip: bool = False
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


class PhoneCommandError(RuntimeError):
    pass


def load_scenario(path: str | Path) -> Scenario:
    scenario_path = Path(path)
    namespace = runpy.run_path(str(scenario_path))

    explicit = namespace.get("scenario")
    if isinstance(explicit, Scenario):
        return explicit

    for value in namespace.values():
        if isinstance(value, Scenario):
            return value

    raise ValueError(f"No sipx Scenario found in {scenario_path}")


async def run_scenario_file(path: str | Path, *, artifacts_dir: str | Path) -> Verdict:
    harness = Harness(artifact_root=artifacts_dir)
    return await harness.run(load_scenario(path))


async def run_phone_register(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with _native_softphone(command) as phone:
        state = await phone.register()
        print(f"registered: {state.value}")
        print(f"contact: {phone.contact}")
        print(f"local: {_format_address(phone.local_address)}")
        if command.keepalive > 0:
            await asyncio.sleep(command.keepalive)
    return 0


async def run_phone_unregister(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with _native_softphone(command) as phone:
        state = await phone.unregister()
        print(f"unregistered: {state.value}")
        print(f"contact: {phone.contact}")
    return 0


async def run_phone_call(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    if command.target is None:
        raise ValueError("target is required")
    async with _native_softphone(command) as phone:
        call = await phone.call(command.target)
        print(f"call confirmed: {call.call_id}")
        print(f"remote: {_format_address(call.remote)}")
        for digits in command.dtmf:
            await phone.send_dtmf(call, digits, duration_ms=command.dtmf_duration_ms)
            print(f"dtmf sent: {digits}")
        if command.duration > 0:
            await asyncio.sleep(command.duration)
        await phone.hangup(call)
        print(f"call terminated: {call.call_id}")
    return 0


async def run_phone_listen(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with _native_softphone(command) as phone:
        print(f"listening: {_format_address(phone.local_address)}")
        call = await phone.answer_inbound()
        print(f"inbound answered: {call.call_id}")
        if command.duration > 0:
            await asyncio.sleep(command.duration)
            await phone.hangup(call)
            print(f"call terminated: {call.call_id}")
        else:
            await asyncio.Event().wait()
    return 0


async def run_sip_request(args: argparse.Namespace) -> int:
    command = _sip_request_command_config(args)
    async with NativeSipBackend(
        local_host=command.local_host,
        local_port=command.local_port,
        mode=command.mode,
        actor_id=command.actor_id,
        wire_event_handler=_debug_sip_event if command.debug_sip else None,
    ) as backend:
        contact = _contact_uri(
            command.aor,
            command.contact_user,
            backend.local_address,
        )
        call_id = _id("request")
        from_tag = _tag("from")
        request = _build_cli_request(
            command,
            contact=contact,
            call_id=call_id,
            from_tag=from_tag,
        )

        await backend.send_request(request, command.remote)
        print(f"> {request.method} {request.uri}")
        if command.no_wait:
            print("sent")
            return 0

        response = await _receive_cli_response(
            backend,
            call_id=call_id,
            method=request.method,
            timeout=command.timeout,
            cseq=1,
        )
        challenge = _response_digest_challenge(response)
        if challenge is not None and _has_request_credentials(command):
            auth_header_name, challenge_value = challenge
            request = _build_cli_request(
                command,
                contact=contact,
                call_id=call_id,
                from_tag=from_tag,
                cseq=2,
                auth_header=(
                    auth_header_name,
                    build_digest_authorization(
                        username=command.username or "",
                        password=command.password or "",
                        method=command.method,
                        uri=str(command.target),
                        challenge=parse_digest_challenge(challenge_value),
                    ),
                ),
            )
            await backend.send_request(request, command.remote)
            print(f"> {request.method} {request.uri}")
            response = await _receive_cli_response(
                backend,
                call_id=call_id,
                method=request.method,
                timeout=command.timeout,
                cseq=2,
            )
        _print_response(response, include_headers=command.include_headers)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipx",
        description="Programmable Voice/SIP harness and technical softphone.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    scenario_parser = subcommands.add_parser("scenario")
    scenario_subcommands = scenario_parser.add_subparsers(
        dest="scenario_command",
        required=True,
    )
    run_parser = scenario_subcommands.add_parser("run")
    run_parser.add_argument("file")
    run_parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Directory where run artifacts are written.",
    )

    export_parser = scenario_subcommands.add_parser("export")
    export_parser.add_argument("timeline")
    export_parser.add_argument("--name", default="recorded_scenario")
    export_parser.add_argument(
        "--format",
        choices=("python", "yaml"),
        default="python",
    )

    replay_parser = subcommands.add_parser("replay")
    replay_parser.add_argument("timeline")

    _add_options_parser(_sip_request_parser(subcommands, "options"))
    _add_message_parser(_sip_request_parser(subcommands, "message"))
    _add_generic_request_parser(_sip_request_parser(subcommands, "request"))

    profile_parser = subcommands.add_parser("profile")
    profile_subcommands = profile_parser.add_subparsers(
        dest="profile_command",
        required=True,
    )
    profile_list_parser = profile_subcommands.add_parser("list")
    profile_list_parser.add_argument("--config", default="harness.toml")
    profile_show_parser = profile_subcommands.add_parser("show")
    profile_show_parser.add_argument("name")
    profile_show_parser.add_argument("--config", default="harness.toml")

    phone_parser = subcommands.add_parser("phone")
    phone_subcommands = phone_parser.add_subparsers(dest="phone_command", required=True)
    _add_phone_register_parser(_phone_parser(phone_subcommands, "register"))
    _add_phone_unregister_parser(_phone_parser(phone_subcommands, "unregister"))
    _add_phone_call_parser(_phone_parser(phone_subcommands, "call"))
    _add_phone_listen_parser(_phone_parser(phone_subcommands, "listen"))

    _add_phone_register_parser(_phone_parser(subcommands, "register"))
    _add_phone_unregister_parser(_phone_parser(subcommands, "unregister"))
    _add_phone_call_parser(_phone_parser(subcommands, "call"))
    _add_phone_listen_parser(_phone_parser(subcommands, "listen"))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scenario" and args.scenario_command == "run":
        verdict = asyncio.run(
            run_scenario_file(args.file, artifacts_dir=args.artifacts_dir)
        )
        reason = f": {verdict.reason}" if verdict.reason else ""
        print(f"{verdict.status}{reason}")
        return 0 if verdict.status == "passed" else 1

    if args.command == "scenario" and args.scenario_command == "export":
        recorder = ScenarioRecorder.from_timeline(
            Timeline.read_jsonl(args.timeline),
            name=args.name,
        )
        output = (
            recorder.export_python()
            if args.format == "python"
            else recorder.export_yaml()
        )
        print(output, end="")
        return 0

    if args.command == "replay":
        timeline = Timeline.read_jsonl(args.timeline)
        print(render_text_report(timeline, Verdict.passed(reason="replay")), end="")
        return 0

    if args.command in {"options", "message", "request"}:
        return _run_cli_command(run_sip_request(args))

    if args.command == "profile" and args.profile_command == "list":
        profiles = load_profiles(args.config)
        for name, profile in sorted(profiles.items()):
            print(f"{name}\t{profile.mode}\t{profile.backend}")
        return 0

    if args.command == "profile" and args.profile_command == "show":
        profile = load_profiles(args.config)[args.name]
        print(f"name: {profile.name}")
        print(f"mode: {profile.mode}")
        print(f"backend: {profile.backend}")
        print(f"aor: {profile.account.aor}")
        print(f"registrar: {profile.account.registrar}")
        print(f"remote: {_format_address(profile.account.remote)}")
        print(f"codecs: {', '.join(profile.media.codecs)}")
        return 0

    phone_command = args.phone_command if args.command == "phone" else args.command
    if phone_command == "register":
        return _run_phone_command(run_phone_register(args))

    if phone_command == "unregister":
        return _run_phone_command(run_phone_unregister(args))

    if phone_command == "call":
        return _run_phone_command(run_phone_call(args))

    if phone_command == "listen":
        return _run_phone_command(run_phone_listen(args))

    parser.error("unsupported command")
    return 2


def _add_sip_request_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile", dest="profile_option", help="Profile name from --config."
    )
    parser.add_argument("--config", default="harness.toml", help="Profile config path.")
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
    parser.add_argument("--mode", choices=("strict", "lab"), help="Native SIP mode.")
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
        "--profile", dest="profile_option", help="Profile name from --config."
    )
    parser.add_argument("--config", default="harness.toml", help="Profile config path.")
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
    parser.add_argument("--mode", choices=("strict", "lab"), help="Native SIP mode.")
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="SIP transaction timeout in seconds."
    )
    parser.add_argument(
        "--expires", type=int, default=3600, help="REGISTER expiration in seconds."
    )
    parser.add_argument("--actor-id", default="softphone", help="Timeline actor id.")
    parser.add_argument(
        "--media-host",
        "--rtp-host",
        dest="media_host",
        help="Local RTP address advertised in SDP; defaults to the SIP bind address.",
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
        help="Audio codec to offer; repeatable. Defaults to profile codecs or PCMU,PCMA.",
    )
    parser.add_argument(
        "--debug-sip",
        action="store_true",
        help="Print redacted SIP datagrams to stderr as they are sent and received.",
    )


def _add_phone_register_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("profile_name", nargs="?")
    _add_phone_common(parser)
    parser.add_argument(
        "--keepalive",
        type=float,
        default=0.0,
        help="Keep the registered socket alive for N seconds before exit.",
    )


def _add_phone_unregister_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("profile_name", nargs="?")
    _add_phone_common(parser)


def _add_phone_call_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target")
    _add_phone_common(parser)
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
    parser.add_argument("profile_name", nargs="?")
    _add_phone_common(parser)
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=0.0,
        help="Seconds to keep an answered inbound call before BYE; 0 waits forever.",
    )


def _phone_command_config(args: argparse.Namespace) -> PhoneCommandConfig:
    profile = _load_selected_profile(args)
    account = _phone_account(args, profile)
    config = NativeSoftphoneConfig(
        account=account,
        remote=_phone_remote(args, profile, _sip_uri(account.registrar)),
        mode=str(args.mode or (profile.mode if profile else "strict")),
        local_host=args.local_host,
        local_port=args.local_port,
        actor_id=args.actor_id,
        timeout=args.timeout,
        media_host=args.media_host,
        media_port=args.media_port or 0,
        codecs=_phone_codecs(args, profile),
    )
    return PhoneCommandConfig(
        config=config,
        target=getattr(args, "target", None),
        duration=float(getattr(args, "duration", 0.0)),
        keepalive=float(getattr(args, "keepalive", 0.0)),
        debug_sip=args.debug_sip,
        dtmf=tuple(getattr(args, "dtmf", ()) or ()),
        dtmf_duration_ms=int(getattr(args, "dtmf_duration_ms", 160)),
    )


def _native_softphone(command: PhoneCommandConfig) -> NativeSoftphone:
    if not command.debug_sip:
        return NativeSoftphone(command.config)
    backend = NativeSipBackend(
        local_host=command.config.local_host,
        local_port=command.config.local_port,
        mode=command.config.mode,
        actor_id=command.config.actor_id,
        retransmission_policy=command.config.retransmission_policy,
        lab_hooks=command.config.lab_hooks,
        wire_event_handler=_debug_sip_event,
    )
    return NativeSoftphone(command.config, backend=backend)


def _load_selected_profile(args: argparse.Namespace) -> Profile | None:
    profile_name = _selected_profile_name(args)
    if profile_name is None:
        return None
    return load_profiles(args.config)[profile_name]


def _selected_profile_name(args: argparse.Namespace) -> str | None:
    positional = getattr(args, "profile_name", None)
    option = getattr(args, "profile_option", None)
    if positional and option and positional != option:
        raise ValueError("profile positional argument and --profile differ")
    return option or positional


def _phone_account(
    args: argparse.Namespace,
    profile: Profile | None,
) -> NativeSoftphoneAccount:
    aor = _arg_or_profile(args, profile, "aor")
    registrar = _arg_or_profile(args, profile, "registrar")
    if not aor or not registrar:
        raise PhoneCommandError(
            "phone command requires a profile or explicit --aor and --registrar; "
            "try `sipx register --help`"
        )
    return NativeSoftphoneAccount(
        aor=SipUri.parse(str(aor)),
        registrar=SipUri.parse(str(registrar)),
        username=_arg_or_profile(args, profile, "username"),
        password=_arg_or_profile(args, profile, "password"),
        contact_user=_arg_or_profile(args, profile, "contact_user"),
        expires=args.expires,
    )


def _phone_remote(
    args: argparse.Namespace,
    profile: Profile | None,
    registrar: SipUri,
) -> tuple[str, int]:
    if args.remote_host is not None:
        host = args.remote_host
    elif profile is not None:
        host = profile.account.remote_host
    else:
        host = registrar.host

    if args.remote_port is not None:
        port = args.remote_port
    elif profile is not None:
        port = profile.account.remote_port
    else:
        port = registrar.port or 5060

    return host, port


def _phone_codecs(args: argparse.Namespace, profile: Profile | None) -> tuple[str, ...]:
    if args.codec:
        return tuple(str(codec) for codec in args.codec)
    if profile is not None:
        return profile.media.codecs
    return ("PCMU", "PCMA")


def _sip_request_command_config(args: argparse.Namespace) -> SipRequestCommandConfig:
    profile = _load_selected_profile(args)
    target = SipUri.parse(args.target)
    aor = _request_aor(args, profile)
    registrar = _optional_sip_uri(_arg_or_profile(args, profile, "registrar"))
    method = _request_method(args).upper()
    body = _request_body(args)
    content_type = args.content_type or ("text/plain" if method == "MESSAGE" else None)
    return SipRequestCommandConfig(
        method=method,
        target=target,
        aor=aor,
        remote=_request_remote(args, profile, target, registrar),
        local_host=args.local_host,
        local_port=args.local_port,
        mode=str(args.mode or (profile.mode if profile else "strict")),
        timeout=args.timeout,
        actor_id=args.actor_id,
        contact_user=_arg_or_profile(args, profile, "contact_user"),
        username=_arg_or_profile(args, profile, "username"),
        password=_arg_or_profile(args, profile, "password"),
        headers=tuple(_parse_header(header) for header in args.header),
        body=body,
        content_type=content_type,
        include_headers=args.include,
        no_wait=args.no_wait,
        debug_sip=args.debug_sip,
    )


def _request_method(args: argparse.Namespace) -> str:
    if args.command == "options":
        return "OPTIONS"
    if args.command == "message":
        return "MESSAGE"
    return args.method


def _request_aor(args: argparse.Namespace, profile: Profile | None) -> SipUri:
    value = _arg_or_profile(args, profile, "aor")
    if not value:
        raise PhoneCommandError(
            "SIP request command requires --from/--aor or a profile with account.aor; "
            "try `sipx request --help`"
        )
    return SipUri.parse(str(value))


def _request_remote(
    args: argparse.Namespace,
    profile: Profile | None,
    target: SipUri,
    registrar: SipUri | None,
) -> tuple[str, int]:
    if args.remote_host is not None:
        host = args.remote_host
    elif profile is not None:
        host = profile.account.remote_host
    elif registrar is not None:
        host = registrar.host
    else:
        host = target.host

    if args.remote_port is not None:
        port = args.remote_port
    elif profile is not None:
        port = profile.account.remote_port
    elif registrar is not None and registrar.port is not None:
        port = registrar.port
    else:
        port = target.port or 5060

    return host, port


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
    branch = _branch(command.method.lower())
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP {contact.host}:{contact.port};branch={branch}")
    headers.add("From", f"<{command.aor}>;tag={from_tag}")
    headers.add("To", f"<{command.target}>")
    headers.add("Call-ID", call_id)
    headers.add("CSeq", f"{cseq} {command.method}")
    headers.add("Contact", f"<{contact}>")
    headers.add("Max-Forwards", "70")
    if auth_header is not None:
        headers.add(auth_header[0], auth_header[1])
    if command.body and command.content_type is not None:
        headers.add("Content-Type", command.content_type)
    for name, value in command.headers:
        headers.add(name, value)
    return SipRequest(
        method=command.method,
        uri=command.target,
        headers=headers,
        body=command.body,
    )


async def _receive_cli_response(
    backend: NativeSipBackend,
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
        event = await backend.receive_event(timeout=remaining)
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


def _debug_sip_event(event: SipWireEvent) -> None:
    direction = event.direction.value.upper()
    print(
        f"--- SIP {direction} {_format_address(event.remote)} {len(event.raw)} bytes ---",
        file=sys.stderr,
    )
    if event.error is not None:
        print(f"# parse-error: {event.error}", file=sys.stderr)
    text = event.raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    text = default_redactor.redact_text(text)
    print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
    print(f"--- END SIP {direction} ---", file=sys.stderr)


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
        port=local_address[1],
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


def _arg_or_profile(
    args: argparse.Namespace,
    profile: Profile | None,
    name: str,
    *,
    default: Any = None,
) -> Any:
    value = getattr(args, name, None)
    if value is not None:
        return value
    if profile is None:
        return default
    profile_value = getattr(profile.account, name)
    if profile_value in (None, "") and default is not None:
        return default
    return profile_value


def _format_address(address: tuple[str, int]) -> str:
    return f"{address[0]}:{address[1]}"


def _phone_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    examples = {
        "register": (
            "examples:\n"
            "  sipx register lab --config harness.toml\n"
            "  sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password secret"
        ),
        "unregister": (
            "examples:\n"
            "  sipx unregister lab --config harness.toml\n"
            "  sipx unregister --aor sip:1001@example.com --registrar sip:pbx.example.com"
        ),
        "call": (
            "examples:\n"
            "  sipx call sip:6000@pbx.example.com --profile lab --duration 5\n"
            "  sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com"
        ),
        "listen": (
            "examples:\n"
            "  sipx listen lab --config harness.toml --duration 30\n"
            "  sipx listen --aor sip:1001@example.com --registrar sip:pbx.example.com --local-port 5062"
        ),
    }
    return subcommands.add_parser(
        name,
        description=f"Native SIP softphone {name} command.",
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
            "  sipx options sip:pbx.example.com --from sip:1001@example.com\n"
            "  sipx options sip:pbx.example.com --profile lab -i"
        ),
        "message": (
            "examples:\n"
            "  sipx message sip:1002@example.com 'hello' --from sip:1001@example.com\n"
            "  sipx message sip:1002@example.com --profile lab -d 'hello'"
        ),
        "request": (
            "examples:\n"
            "  sipx request OPTIONS sip:pbx.example.com --from sip:1001@example.com\n"
            "  sipx request INFO sip:1002@example.com --profile lab -H 'Content-Type: application/dtmf-relay' -d 'Signal=1'"
        ),
    }
    return subcommands.add_parser(
        name,
        description=descriptions[name],
        epilog=examples[name],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _run_phone_command(coro: Coroutine[Any, Any, int]) -> int:
    return _run_cli_command(coro)


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
    "load_scenario",
    "main",
    "run_phone_call",
    "run_phone_listen",
    "run_phone_register",
    "run_phone_unregister",
    "run_sip_request",
    "run_scenario_file",
]
