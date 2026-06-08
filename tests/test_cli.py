from pathlib import Path

from sipx.cli.main import main


def test_cli_runs_python_scenario_file(tmp_path: Path, capsys) -> None:
    scenario_file = tmp_path / "sample_scenario.py"
    scenario_file.write_text(
        "from sipx import scenario\n"
        "@scenario('sample')\n"
        "async def scenario(h):\n"
        "    h.metrics.increment('calls', 1)\n",
        encoding="utf-8",
    )

    code = main(
        [
            "scenario",
            "run",
            str(scenario_file),
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "passed" in output


def test_cli_exports_recorded_scenario_from_timeline(tmp_path: Path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    timeline.write_text(
        '{"actor_id":"alice","call_id":null,"category":"sip","data":{"method":"INVITE"},'
        '"leg_id":null,"name":"request_sent","run_id":"run-1","ts_ns":1}\n',
        encoding="utf-8",
    )

    code = main(["scenario", "export", str(timeline), "--name", "recorded"])

    output = capsys.readouterr().out
    assert code == 0
    assert "@scenario('recorded')" in output
    assert "request_sent" in output


def test_cli_replays_timeline_as_text_report(tmp_path: Path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    timeline.write_text(
        '{"actor_id":"alice","call_id":null,"category":"sip","data":{"status":200},'
        '"leg_id":null,"name":"response_received","run_id":"run-2","ts_ns":1}\n',
        encoding="utf-8",
    )

    code = main(["replay", str(timeline)])

    output = capsys.readouterr().out
    assert code == 0
    assert "sipx report: run-2" in output
    assert "sip.response_received" in output
