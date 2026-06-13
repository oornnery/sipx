"""sipx command-line client built on the AsyncClient API."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Coroutine, Sequence
from pathlib import Path
from typing import Any

from sipx import AsyncClient, AuthFlow, ClientConfig, Request, Response


class CliError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipx",
        description="SIP command-line client.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    _add_request_flags(_subparser(subcommands, "options"), target=True)
    message_parser = _subparser(subcommands, "message")
    message_parser.add_argument("target")
    message_parser.add_argument("text", nargs="?", help="MESSAGE body text.")
    _add_request_flags(message_parser, target=False)
    generic_parser = _subparser(subcommands, "request")
    generic_parser.add_argument("method")
    _add_request_flags(generic_parser, target=True)

    register_parser = _subparser(subcommands, "register")
    _add_register_flags(register_parser)
    register_parser.add_argument(
        "--keepalive",
        type=float,
        default=0.0,
        help="Keep the client alive for N seconds after registering.",
    )
    unregister_parser = _subparser(subcommands, "unregister")
    _add_register_flags(unregister_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"options", "message", "request"}:
        return _run(run_sip_request(args))
    if args.command in {"register", "unregister"}:
        return _run(run_register(args))

    parser.error("unsupported command")
    return 2


async def run_sip_request(args: argparse.Namespace) -> int:
    method = _request_method(args)
    from_uri = _require_from(args)
    body = _request_body(args)
    headers = dict(_parse_header(header) for header in args.header)
    if args.content_type:
        headers["Content-Type"] = args.content_type

    client = _build_client(args, from_uri)
    async with client:
        print(f"> {method} {args.target}")
        if method == "MESSAGE":
            text = body if body else b""
            response = await client.message(args.target, text, **headers)
        elif method == "OPTIONS" and not body:
            response = await client.options(args.target, **headers)
        else:
            kwargs: dict[str, Any] = dict(headers)
            if body:
                kwargs["body"] = body
                kwargs.setdefault("Content-Length", str(len(body)))
            response = await client.request(method, args.target, **kwargs)
        _print_response(response, include_headers=args.include)
    return 0 if response.status_code < 300 else 1


async def run_register(args: argparse.Namespace) -> int:
    if not args.aor or not args.registrar:
        raise CliError(
            "register requires explicit --aor and --registrar; "
            "try `sipx register --help`"
        )

    expires = 0 if args.command == "unregister" else args.expires
    client = _build_client(args, args.aor)
    async with client:
        response = await client.register(
            args.registrar,
            **{"Expires": str(expires)},
        )
        action = "unregistered" if expires == 0 else "registered"
        if 200 <= response.status_code < 300:
            print(f"{action}: {response.status_code} {response.reason}")
        else:
            print(f"{action} failed: {response.status_code} {response.reason}")
            return 1
        if args.command == "register" and args.keepalive > 0:
            await asyncio.sleep(args.keepalive)
    return 0


def _add_request_flags(parser: argparse.ArgumentParser, *, target: bool) -> None:
    if target:
        parser.add_argument("target")
    parser.add_argument(
        "--aor",
        "--from",
        dest="aor",
        help="From account URI, for example sip:1001@example.com.",
    )
    parser.add_argument("--username", help="Digest auth username.")
    parser.add_argument("--password", help="Digest auth password.")
    parser.add_argument("--contact-user", help="User part for the Contact URI.")
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
    _add_common_flags(parser)


def _add_register_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--aor",
        "--from",
        dest="aor",
        help="Account address, for example sip:1001@example.com.",
    )
    parser.add_argument(
        "--registrar",
        help="Registrar URI, for example sip:pbx.example.com:5060.",
    )
    parser.add_argument("--username", help="Digest auth username.")
    parser.add_argument("--password", help="Digest auth password.")
    parser.add_argument("--contact-user", help="User part for the Contact URI.")
    parser.add_argument(
        "--expires", type=int, default=3600, help="REGISTER expiration in seconds."
    )
    _add_common_flags(parser)


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--transport",
        choices=("udp", "tcp", "tls"),
        default="udp",
        help="SIP transport.",
    )
    parser.add_argument("--local-host", default="0.0.0.0", help="Local bind host.")
    parser.add_argument(
        "--local-port",
        type=int,
        default=0,
        help="Local bind port; 0 picks a free port.",
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="SIP response timeout in seconds."
    )
    parser.add_argument(
        "--debug-sip",
        action="store_true",
        help="Print redacted SIP messages to stderr as they are sent and received.",
    )
    parser.add_argument(
        "--no-rport",
        action="store_true",
        help="Do not add the rport parameter (RFC 3581) to outgoing Via headers.",
    )
    parser.add_argument(
        "--no-retransmit",
        action="store_true",
        help="Disable RFC 3261 §17 request retransmission on unreliable transports.",
    )


def _build_client(args: argparse.Namespace, from_uri: str) -> AsyncClient:
    contact_uri = None
    if args.contact_user:
        contact_uri = f"sip:{args.contact_user}@{args.local_host}"

    config = ClientConfig(
        transport=args.transport,
        local_host=args.local_host,
        local_port=args.local_port,
        timeout=args.timeout,
        from_uri=str(from_uri),
        contact_uri=contact_uri,
        rport=not getattr(args, "no_rport", False),
        retransmit=not getattr(args, "no_retransmit", False),
    )
    auth = None
    if args.username and args.password:
        auth = AuthFlow(username=args.username, password=args.password)

    event_hooks = None
    if args.debug_sip:
        event_hooks = {
            "request": [_debug_request],
            "response": [_debug_response],
            "provisional": [_debug_response],
        }

    return AsyncClient(
        transport=args.transport,
        config=config,
        event_hooks=event_hooks,
        auth=auth,
    )


def _request_method(args: argparse.Namespace) -> str:
    if args.command == "options":
        return "OPTIONS"
    if args.command == "message":
        return "MESSAGE"
    return str(args.method).upper()


def _require_from(args: argparse.Namespace) -> str:
    if not args.aor:
        raise CliError(
            "SIP request command requires --from/--aor; try `sipx request --help`"
        )
    return str(args.aor)


def _request_body(args: argparse.Namespace) -> bytes:
    text = getattr(args, "text", None)
    sources = [value is not None for value in (text, args.body, args.body_file)]
    if sum(sources) > 1:
        raise CliError("use only one request body source")
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
        raise CliError("headers must be formatted as 'Name: value'")
    name = name.strip()
    if not name:
        raise CliError("header name is required")
    return name, header_value.strip()


def _print_response(response: Response, *, include_headers: bool) -> None:
    reason = f" {response.reason}" if response.reason else ""
    print(f"< {response.status_code}{reason}")
    if include_headers:
        for name, value in response.headers.items():
            if isinstance(value, list):
                for item in value:
                    print(f"{name}: {item}")
            else:
                print(f"{name}: {value}")
        if response.body:
            print()
    if response.body:
        print(response.body.decode("utf-8", errors="replace"), end="")


def _debug_request(request: Request) -> None:
    text = request.to_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    text = _redact_sip_text(text)
    print(f"--- SIP TX {request.uri} ---", file=sys.stderr)
    print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
    print("--- END SIP TX ---", file=sys.stderr)


def _debug_response(response: Response) -> None:
    text = response.to_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    text = _redact_sip_text(text)
    print(f"--- SIP RX {response.status_code} {response.reason} ---", file=sys.stderr)
    print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
    print("--- END SIP RX ---", file=sys.stderr)


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


def _subparser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    descriptions = {
        "options": "Send a SIP OPTIONS request.",
        "message": "Send a SIP MESSAGE request.",
        "request": "Send a generic SIP request.",
        "register": "Register an account with a SIP registrar.",
        "unregister": "Remove a registration (REGISTER with Expires: 0).",
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
            "  sipx request INFO sip:1002@example.com --from sip:1001@example.com"
            " -H 'Content-Type: application/dtmf-relay' -d 'Signal=1'"
        ),
        "register": (
            "examples:\n"
            "  sipx register --aor sip:1001@example.com"
            " --registrar sip:pbx.example.com:5060 --username 1001 --password secret"
        ),
        "unregister": (
            "examples:\n"
            "  sipx unregister --aor sip:1001@example.com"
            " --registrar sip:pbx.example.com"
        ),
    }
    return subcommands.add_parser(
        name,
        description=descriptions[name],
        epilog=examples[name],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _run(coro: Coroutine[Any, Any, int]) -> int:
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "build_parser",
    "main",
    "run_register",
    "run_sip_request",
]
