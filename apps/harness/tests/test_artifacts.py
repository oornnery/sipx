import json
from pathlib import Path

from sipx_harness import ArtifactKind, ArtifactStore


def test_artifact_store_redacts_json_before_write(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    artifact = store.write_json(
        "verdict.json",
        {"token": "secret", "safe": "visible"},
        kind=ArtifactKind.VERDICT,
    )

    data = json.loads(artifact.path.read_text())
    assert data == {"safe": "visible", "token": "[REDACTED]"}
