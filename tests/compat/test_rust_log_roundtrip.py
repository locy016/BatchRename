from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[2]


def test_rust_roundtrip_preserves_the_stable_log_schema(tmp_path: Path) -> None:
    source = REPOSITORY_ROOT / "tests" / "fixtures" / "logs" / "operation-completed-v1.json"
    output = tmp_path / "rust-output.json"
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo.exe")
    subprocess.run(
        [
            cargo,
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

    operation = json.loads(output.read_text(encoding="utf-8"))
    assert operation["schema_version"] == 1
    assert operation["identifier"] == "demo-completed-v1"
    assert operation["status"] == "已完成"
    assert operation["items"][0]["kind"] == "文件"
    assert operation["items"][0]["outcome"] == "成功"
    assert operation["items"][0]["undo_status"] == "待撤回"
