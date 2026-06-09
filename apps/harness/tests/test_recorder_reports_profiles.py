import json
from pathlib import Path

import pytest

from sipx import SipUserAgent
from sipx_harness import (
    ArtifactStore,
    Harness,
    MediaOverrides,
    MixedActorSpec,
    MixedScenario,
    Profile,
    ScenarioRecorder,
    SipOverrides,
    Timeline,
    Verdict,
    load_profiles,
    render_html_report,
    render_text_report,
)
from sipx_harness import MockRuntime


def test_scenario_recorder_exports_timeline_to_yaml_and_python() -> None:
    timeline = Timeline(run_id="record-run", clock_ns=lambda: 10)
    timeline.record("sip", "request_sent", actor_id="alice", data={"method": "INVITE"})
    recorder = ScenarioRecorder.from_timeline(timeline, name="ivr_recording")

    yaml_text = recorder.export_yaml()
    python_text = recorder.export_python()

    assert "name: ivr_recording" in yaml_text
    assert "request_sent" in yaml_text
    assert "@scenario('ivr_recording')" in python_text
    assert "ACTIONS" in python_text


def test_scenario_recorder_writes_export_artifacts(tmp_path: Path) -> None:
    timeline = Timeline(run_id="record-artifact")
    recorder = ScenarioRecorder(name="manual")
    recorder.record_action(
        timeline, "pressed_digit", actor_id="user", data={"digit": "1"}
    )
    store = ArtifactStore(tmp_path)

    yaml_artifact, python_artifact = recorder.write_exports(store)

    assert yaml_artifact.path.exists()
    assert python_artifact.path.exists()
    assert "pressed_digit" in yaml_artifact.path.read_text()


def test_reports_render_text_and_html_with_verdict_evidence() -> None:
    timeline = Timeline(run_id="report-run", clock_ns=lambda: 1)
    timeline.record("sip", "response_received", actor_id="alice", data={"status": 200})
    verdict = Verdict.passed(reason="ok")

    text = render_text_report(timeline, verdict)
    html = render_html_report(timeline, verdict)

    assert "status: passed" in text
    assert "sip.response_received" in text
    assert "<table>" in html
    assert "response_received" in html


def test_harness_writes_report_artifacts(tmp_path: Path) -> None:
    async def run_scenario(h: Harness) -> None:
        h.timeline.record("sip", "request_sent", actor_id="caller")

    from sipx_harness import scenario

    scenario_obj = scenario("reporting")(run_scenario)

    import asyncio

    verdict = asyncio.run(
        Harness(run_id="report-harness", artifact_root=tmp_path).run(scenario_obj)
    )

    names = {artifact.name for artifact in verdict.artifacts}
    assert {"timeline.jsonl", "verdict.json", "report.txt", "report.html"} <= names
    verdict_json = json.loads(
        (tmp_path / "report-harness" / "verdict.json").read_text()
    )
    assert "report.html" in {artifact["name"] for artifact in verdict_json["artifacts"]}


def test_profile_config_loads_strict_and_lab_profiles(tmp_path: Path) -> None:
    config = tmp_path / "harness.toml"
    config.write_text(
        "[profiles.normal]\n"
        "mode = 'strict'\n"
        "[profiles.normal.account]\n"
        "aor = 'sip:alice@example.com'\n"
        "registrar = 'sip:example.com'\n"
        "remote_host = '127.0.0.1'\n"
        "remote_port = 5060\n"
        "[profiles.lab]\n"
        "mode = 'lab'\n"
        "[profiles.lab.sip]\n"
        "headers = { X_Sipx = 'yes' }\n"
        "allow_malformed = true\n"
        "[profiles.lab.media]\n"
        "codecs = ['PCMU']\n",
        encoding="utf-8",
    )

    profiles = load_profiles(config)

    assert profiles["normal"].mode == "strict"
    assert profiles["normal"].account.remote == ("127.0.0.1", 5060)
    assert profiles["lab"].sip.allow_malformed
    assert profiles["lab"].media == MediaOverrides(codecs=("PCMU",))


def test_profile_rejects_lab_overrides_in_strict_mode() -> None:
    with pytest.raises(ValueError, match="strict profiles"):
        Profile(name="bad", sip=SipOverrides(allow_malformed=True))


def test_mixed_scenario_binds_sip_asterisk_and_mock_actors() -> None:
    timeline = Timeline(run_id="mixed-run")
    runtimes: dict[str, object] = {
        "mock": MockRuntime(),
        "sip": SipUserAgent(timeline=timeline, actor_id="sip"),
        "asterisk": MockRuntime(),
    }
    harness = Harness(run_id="mixed-run", runtimes=runtimes)
    harness.timeline = timeline
    mixed = MixedScenario(
        MixedActorSpec("caller", runtime="sip", kind="softphone"),
        MixedActorSpec("pbx", runtime="asterisk", kind="asterisk"),
        MixedActorSpec("agent", runtime="mock", kind="remote"),
    )

    actors = mixed.bind(harness)

    assert actors["caller"].runtime_name == "sip"
    assert actors["pbx"].kind == "asterisk"
    assert actors["agent"].runtime_name == "mock"
    assert [event.name for event in timeline.events] == ["actor_bound"] * 3
