from __future__ import annotations

import argparse
import asyncio
import runpy
import sys
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from sipx.sip import SipUri
from sipx.softphone import (
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
    async with NativeSoftphone(command.config) as phone:
        state = await phone.register()
        print(f"registered: {state.value}")
        print(f"contact: {phone.contact}")
        print(f"local: {_format_address(phone.local_address)}")
        if command.keepalive > 0:
            await asyncio.sleep(command.keepalive)
    return 0


async def run_phone_unregister(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with NativeSoftphone(command.config) as phone:
        state = await phone.unregister()
        print(f"unregistered: {state.value}")
        print(f"contact: {phone.contact}")
    return 0


async def run_phone_call(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    if command.target is None:
        raise ValueError("target is required")
    async with NativeSoftphone(command.config) as phone:
        call = await phone.call(command.target)
        print(f"call confirmed: {call.call_id}")
        print(f"remote: {_format_address(call.remote)}")
        if command.duration > 0:
            await asyncio.sleep(command.duration)
        await phone.hangup(call)
        print(f"call terminated: {call.call_id}")
    return 0


async def run_phone_listen(args: argparse.Namespace) -> int:
    command = _phone_command_config(args)
    async with NativeSoftphone(command.config) as phone:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sipx")
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
    _add_phone_register_parser(phone_subcommands.add_parser("register"))
    _add_phone_unregister_parser(phone_subcommands.add_parser("unregister"))
    _add_phone_call_parser(phone_subcommands.add_parser("call"))
    _add_phone_listen_parser(phone_subcommands.add_parser("listen"))

    _add_phone_register_parser(subcommands.add_parser("register"))
    _add_phone_unregister_parser(subcommands.add_parser("unregister"))
    _add_phone_call_parser(subcommands.add_parser("call"))
    _add_phone_listen_parser(subcommands.add_parser("listen"))

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


def _add_phone_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", dest="profile_option")
    parser.add_argument("--config", default="harness.toml")
    parser.add_argument("--aor")
    parser.add_argument("--registrar")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--contact-user")
    parser.add_argument("--remote-host")
    parser.add_argument("--remote-port", type=int)
    parser.add_argument("--local-host", default="127.0.0.1")
    parser.add_argument("--local-port", type=int, default=0)
    parser.add_argument("--mode", choices=("strict", "lab"))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--expires", type=int, default=3600)
    parser.add_argument("--actor-id", default="softphone")


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
        remote=(
            str(_arg_or_profile(args, profile, "remote_host", default="127.0.0.1")),
            int(_arg_or_profile(args, profile, "remote_port", default=5060)),
        ),
        mode=str(args.mode or (profile.mode if profile else "strict")),
        local_host=args.local_host,
        local_port=args.local_port,
        actor_id=args.actor_id,
        timeout=args.timeout,
    )
    return PhoneCommandConfig(
        config=config,
        target=getattr(args, "target", None),
        duration=float(getattr(args, "duration", 0.0)),
        keepalive=float(getattr(args, "keepalive", 0.0)),
    )


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
    aor = _arg_or_profile(args, profile, "aor", default="sip:softphone@127.0.0.1")
    registrar = _arg_or_profile(args, profile, "registrar", default="sip:127.0.0.1")
    return NativeSoftphoneAccount(
        aor=SipUri.parse(str(aor)),
        registrar=SipUri.parse(str(registrar)),
        username=_arg_or_profile(args, profile, "username"),
        password=_arg_or_profile(args, profile, "password"),
        contact_user=_arg_or_profile(args, profile, "contact_user"),
        expires=args.expires,
    )


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


def _run_phone_command(coro: Coroutine[Any, Any, int]) -> int:
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130
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
    "run_scenario_file",
]
