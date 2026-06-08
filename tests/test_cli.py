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
