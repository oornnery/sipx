from __future__ import annotations

import argparse
import asyncio
import runpy
from collections.abc import Sequence
from pathlib import Path

from sipx.core import (
    Harness,
    Scenario,
    ScenarioRecorder,
    Timeline,
    Verdict,
    render_text_report,
)


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

    parser.error("unsupported command")
    return 2


__all__ = ["build_parser", "load_scenario", "main", "run_scenario_file"]
