from __future__ import annotations

import argparse
import shlex


def register_command(profile: str, config: str = "harness.toml") -> list[str]:
    return ["sipx", "register", profile, "--config", config, "--debug-sip"]


def options_command(target: str, from_uri: str) -> list[str]:
    return ["sipx", "options", target, "--from", from_uri, "--include", "--debug-sip"]


def message_command(target: str, from_uri: str, text: str) -> list[str]:
    return ["sipx", "message", target, text, "--from", from_uri, "--debug-sip"]


def info_dtmf_command(target: str, from_uri: str, digit: str) -> list[str]:
    return [
        "sipx",
        "request",
        "INFO",
        target,
        "--from",
        from_uri,
        "-H",
        "Content-Type: application/dtmf-relay",
        "-d",
        f"Signal={digit}\r\nDuration=160\r\n",
        "--include",
        "--debug-sip",
    ]


def call_with_dtmf_command(
    target: str, profile: str, config: str = "harness.toml"
) -> list[str]:
    return [
        "sipx",
        "call",
        target,
        "--profile",
        profile,
        "--config",
        config,
        "--codec",
        "PCMU",
        "--dtmf",
        "123#",
        "--duration",
        "3",
        "--debug-sip",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print runnable sipx CLI examples.")
    parser.add_argument("--profile", default="lab")
    parser.add_argument("--config", default="harness.toml")
    parser.add_argument("--from-uri", default="sip:1001@example.com")
    parser.add_argument("--target", default="sip:ivr@example.com")
    parser.add_argument("--message-target", default="sip:1002@example.com")
    args = parser.parse_args(argv)

    commands = [
        register_command(args.profile, args.config),
        options_command(args.target, args.from_uri),
        message_command(args.message_target, args.from_uri, "hello from sipx"),
        info_dtmf_command(args.target, args.from_uri, "1"),
        call_with_dtmf_command(args.target, args.profile, args.config),
    ]
    for command in commands:
        print(_shell_join(command))
    return 0


def _shell_join(command: list[str]) -> str:
    parts = []
    for value in command:
        if "\r" in value or "\n" in value:
            escaped = (
                value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
            )
            parts.append(f"$'{escaped}'")
        else:
            parts.append(shlex.quote(value))
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
