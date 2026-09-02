from pathlib import Path

from batch_rename.core import execute, scan
from batch_rename.models import ScanOptions


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("内容", encoding="utf-8")
    return path


def test_execute_renames_ready_file(tmp_path):
    source = touch(tmp_path / "旧版资料.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))

    execution = execute(result.candidates)

    assert not source.exists()
    assert (tmp_path / "新版资料.txt").read_text(encoding="utf-8") == "内容"
    assert execution.succeeded == 1
    assert execution.skipped == 0
    assert execution.failed == 0


def test_execute_includes_preflight_conflict_as_skipped(tmp_path):
    touch(tmp_path / "旧版.txt")
    touch(tmp_path / "新版.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))

    execution = execute(result.candidates)

    assert execution.succeeded == 0
    assert execution.skipped == 1
    assert "已存在" in execution.records[0].detail


def test_execute_processes_child_before_renaming_parent(tmp_path):
    folder = tmp_path / "旧版目录"
    child = touch(folder / "旧版文件.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))

    execution = execute(result.candidates)

    final_child = tmp_path / "新版目录" / "新版文件.txt"
    assert final_child.exists()
    assert not folder.exists()
    assert execution.succeeded == 2
    assert execution.records[0].source == child


def test_execute_skips_source_removed_after_scan(tmp_path):
    source = touch(tmp_path / "旧版.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))
    source.unlink()

    execution = execute(result.candidates)

    assert execution.skipped == 1
    assert "不存在" in execution.records[0].detail


def test_execute_skips_target_created_after_scan(tmp_path):
    touch(tmp_path / "旧版.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))
    touch(tmp_path / "新版.txt")

    execution = execute(result.candidates)

    assert execution.skipped == 1
    assert (tmp_path / "旧版.txt").exists()
    assert "目标" in execution.records[0].detail


def test_progress_callback_receives_every_processed_item(tmp_path):
    touch(tmp_path / "旧版1.txt")
    touch(tmp_path / "旧版2.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))
    updates = []

    execute(result.candidates, progress=lambda current, total, record: updates.append(
        (current, total, record.outcome)
    ))

    assert updates == [(1, 2, "成功"), (2, 2, "成功")]
