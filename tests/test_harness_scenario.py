import json
import asyncio
from pathlib import Path

from sipx import Harness, expect, scenario


def test_harness_runs_scenario_and_writes_minimum_artifacts(tmp_path: Path) -> None:
    async def run() -> None:
        @scenario("mock_call")
        async def mock_call(h: Harness) -> None:
            caller = h.actor("caller").softphone()
            call = await caller.call("sip:ivr@example.com")
            await expect(call.timeline).event("sip", "final_response").within()
            await call.send_dtmf("1#")
            await call.hangup()

        harness = Harness(run_id="run-1", artifact_root=tmp_path)
        verdict = await harness.run(mock_call)

        assert verdict.status == "passed"
        assert (tmp_path / "run-1" / "timeline.jsonl").exists()
        verdict_json = json.loads((tmp_path / "run-1" / "verdict.json").read_text())
        assert verdict_json["status"] == "passed"
        assert {artifact["kind"] for artifact in verdict_json["artifacts"]} == {
            "timeline",
            "verdict",
        }

    asyncio.run(run())


def test_harness_converts_assertion_to_failed_verdict(tmp_path: Path) -> None:
    async def run() -> None:
        @scenario("broken")
        async def broken(_: Harness) -> None:
            raise AssertionError("expected signal")

        verdict = await Harness(run_id="run-2", artifact_root=tmp_path).run(broken)

        assert verdict.status == "failed"
        assert verdict.reason == "expected signal"

    asyncio.run(run())
