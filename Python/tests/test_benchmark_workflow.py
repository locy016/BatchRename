import json
import subprocess
import sys
from pathlib import Path

from batch_rename.models import MatchOptions
from tools.benchmark_workflow import benchmark_scenario


def test_benchmark_scenario_reports_scan_and_preview_measurements(tmp_path: Path):
    (tmp_path / "项目01.txt").write_text("", encoding="utf-8")
    (tmp_path / "项目02.txt").write_text("", encoding="utf-8")
    (tmp_path / "其他.txt").write_text("", encoding="utf-8")
    options = MatchOptions(root=tmp_path, search="项目")

    result = benchmark_scenario(tmp_path, options, replacement="客户")

    assert result["scenario"] == tmp_path.name
    assert result["entries"] == 3
    assert result["matched"] == 2
    assert result["scanMs"] >= 0
    assert result["previewMs"] >= 0


def test_benchmark_script_runs_directly_from_the_python_project():
    completed = subprocess.run(
        [sys.executable, "tools/benchmark_workflow.py", "--entries", "5"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["entries"] == 10
