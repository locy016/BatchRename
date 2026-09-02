from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "Python"))

from batch_rename.history import OperationLog  # noqa: E402


def test_rust_roundtrip_remains_readable_by_python(tmp_path: Path) -> None:
    source = REPOSITORY_ROOT / "tests" / "fixtures" / "logs" / "operation-completed-v1.json"
    output = tmp_path / "rust-output.json"
    subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(REPOSITORY_ROOT / "src-tauri" / "Cargo.toml"),
            "--example",
            "log_roundtrip",
            "--",
            str(source),
            str(output),
        ],
        check=True,
    )

    operation = OperationLog.from_dict(json.loads(output.read_text(encoding="utf-8")))
    assert operation.identifier == "demo-completed-v1"
    assert operation.items[0].outcome == "成功"
