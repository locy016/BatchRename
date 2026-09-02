from pathlib import Path

import pytest

import batch_rename.core as core_module
from batch_rename.core import preflight_undo, undo_operation
from batch_rename.history import (
    OperationItem,
    OperationLog,
    OperationStatus,
    UndoStatus,
)
from batch_rename.models import ItemKind


def operation(tmp_path: Path, items: list[OperationItem]) -> OperationLog:
    return OperationLog(
        identifier="undo-001",
        created_at="2026-09-02T12:00:00+08:00",
        updated_at="2026-09-02T12:01:00+08:00",
        root=tmp_path,
        search="旧",
        replacement="新",
        status=OperationStatus.COMPLETED,
        items=items,
    )


def successful_item(
    source: Path,
    target: Path,
    kind: ItemKind,
    execution_index: int,
) -> OperationItem:
    return OperationItem(
        source=source,
        target=target,
        kind=kind,
        outcome="成功",
        detail="重命名完成",
        undo_status=UndoStatus.PENDING,
        execution_index=execution_index,
    )


def test_undo_restores_nested_directory_and_file_in_reverse_execution_order(tmp_path):
    final_directory = tmp_path / "新目录"
    final_directory.mkdir()
    (final_directory / "新文件.txt").write_text("content", encoding="utf-8")
    log = operation(
        tmp_path,
        [
            successful_item(
                tmp_path / "旧目录" / "旧文件.txt",
                tmp_path / "旧目录" / "新文件.txt",
                ItemKind.FILE,
                1,
            ),
            successful_item(
                tmp_path / "旧目录",
                tmp_path / "新目录",
                ItemKind.DIRECTORY,
                2,
            ),
        ],
    )

    check = preflight_undo(log)
    result = undo_operation(log)

    assert check.safe is True
    assert check.items[0].current_source == final_directory
    assert result.succeeded == 2
    assert log.status is OperationStatus.UNDONE
    assert (tmp_path / "旧目录" / "旧文件.txt").read_text(encoding="utf-8") == "content"
    assert not final_directory.exists()


def test_undo_preflight_blocks_entire_batch_when_current_item_is_missing(tmp_path):
    log = operation(
        tmp_path,
        [
            successful_item(
                tmp_path / "旧.txt",
                tmp_path / "新.txt",
                ItemKind.FILE,
                1,
            )
        ],
    )

    check = preflight_undo(log)
    result = undo_operation(log)

    assert check.safe is False
    assert "不存在" in check.items[0].detail
    assert result.succeeded == 0
    assert log.status is OperationStatus.UNDO_CHECK_FAILED
    assert not (tmp_path / "旧.txt").exists()


def test_undo_preflight_blocks_entire_batch_when_original_name_is_occupied(tmp_path):
    (tmp_path / "新.txt").write_text("renamed", encoding="utf-8")
    (tmp_path / "旧.txt").write_text("external", encoding="utf-8")
    log = operation(
        tmp_path,
        [
            successful_item(
                tmp_path / "旧.txt",
                tmp_path / "新.txt",
                ItemKind.FILE,
                1,
            )
        ],
    )

    result = undo_operation(log)

    assert result.check.safe is False
    assert "占用" in result.check.items[0].detail
    assert (tmp_path / "新.txt").read_text(encoding="utf-8") == "renamed"
    assert (tmp_path / "旧.txt").read_text(encoding="utf-8") == "external"


def test_undo_handles_case_only_rename(tmp_path):
    target = tmp_path / "NAME.txt"
    target.write_text("content", encoding="utf-8")
    log = operation(
        tmp_path,
        [successful_item(tmp_path / "name.txt", target, ItemKind.FILE, 1)],
    )

    result = undo_operation(log)

    assert result.succeeded == 1
    assert {path.name for path in tmp_path.iterdir()} == {"name.txt"}


def test_undo_stops_after_runtime_failure_and_can_retry_remaining_items(
    tmp_path, monkeypatch
):
    for name in ("新一.txt", "新二.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    log = operation(
        tmp_path,
        [
            successful_item(tmp_path / "旧一.txt", tmp_path / "新一.txt", ItemKind.FILE, 1),
            successful_item(tmp_path / "旧二.txt", tmp_path / "新二.txt", ItemKind.FILE, 2),
        ],
    )
    original_rename = Path.rename
    calls = 0

    def fail_second(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("文件被占用")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_second)
    first_result = undo_operation(log)

    assert first_result.succeeded == 1
    assert first_result.failed == 1
    assert log.status is OperationStatus.PARTIALLY_UNDONE
    assert log.items[1].undo_status is UndoStatus.UNDONE
    assert log.items[0].undo_status is UndoStatus.FAILED

    monkeypatch.setattr(Path, "rename", original_rename)
    retry_result = undo_operation(log)

    assert retry_result.succeeded == 1
    assert log.status is OperationStatus.UNDONE
    assert (tmp_path / "旧一.txt").exists()
    assert (tmp_path / "旧二.txt").exists()


def test_fully_undone_operation_cannot_run_again(tmp_path):
    item = successful_item(
        tmp_path / "旧.txt", tmp_path / "新.txt", ItemKind.FILE, 1
    )
    item.undo_status = UndoStatus.UNDONE
    log = operation(tmp_path, [item])
    log.status = OperationStatus.UNDONE

    check = preflight_undo(log)
    result = undo_operation(log)

    assert check.safe is False
    assert "已经撤回" in check.summary
    assert result.succeeded == 0
