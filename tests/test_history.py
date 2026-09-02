import json
from pathlib import Path

from batch_rename.history import (
    OperationItem,
    OperationLog,
    OperationStatus,
    OperationStore,
    UndoStatus,
    default_operation_directory,
    filter_operations,
)
from batch_rename.models import ItemKind


def operation(
    identifier: str = "op-001",
    *,
    created_at: str = "2026-09-02T10:00:00+08:00",
    status: OperationStatus = OperationStatus.COMPLETED,
) -> OperationLog:
    return OperationLog(
        identifier=identifier,
        created_at=created_at,
        updated_at=created_at,
        root=Path("D:/资料/待整理"),
        search=r"项目-(\d+)",
        replacement=r"归档-\1",
        use_regex=True,
        max_depth=3,
        include_files=True,
        include_dirs=False,
        rename_extension=False,
        status=status,
        items=[
            OperationItem(
                source=Path("D:/资料/待整理/项目-01.txt"),
                target=Path("D:/资料/待整理/归档-01.txt"),
                kind=ItemKind.FILE,
                outcome="成功",
                detail="重命名完成",
                undo_status=UndoStatus.PENDING,
            )
        ],
    )


def test_operation_log_round_trips_all_rule_and_item_fields():
    original = operation()

    restored = OperationLog.from_dict(original.to_dict())

    assert restored == original
    assert restored.items[0].kind is ItemKind.FILE
    assert restored.items[0].undo_status is UndoStatus.PENDING
    assert restored.success_count == 1
    assert restored.pending_undo_count == 1


def test_operation_store_saves_one_atomic_json_file_per_operation(tmp_path):
    store = OperationStore(tmp_path)
    item = operation()

    target = store.create(item)

    assert target == tmp_path / "op-001.json"
    assert json.loads(target.read_text(encoding="utf-8"))["identifier"] == "op-001"
    assert list(tmp_path.glob("*.tmp")) == []
    assert store.load("op-001") == item


def test_operation_store_loads_newest_first_and_isolates_corrupt_files(tmp_path):
    store = OperationStore(tmp_path)
    store.create(operation("older", created_at="2026-09-01T09:00:00+08:00"))
    store.create(operation("newer", created_at="2026-09-02T09:00:00+08:00"))
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")

    records = store.load_all()

    assert [item.identifier for item in records[:2]] == ["newer", "older"]
    damaged = next(item for item in records if item.identifier == "broken")
    assert damaged.status is OperationStatus.CORRUPT
    assert damaged.error


def test_operation_store_marks_running_logs_as_interrupted_on_load(tmp_path):
    store = OperationStore(tmp_path)
    store.create(operation(status=OperationStatus.RUNNING))

    loaded = store.load("op-001")

    assert loaded.status is OperationStatus.INTERRUPTED
    persisted = json.loads((tmp_path / "op-001.json").read_text(encoding="utf-8"))
    assert persisted["status"] == OperationStatus.INTERRUPTED.value


def test_filter_operations_matches_root_rule_identifier_and_status():
    first = operation("alpha", status=OperationStatus.COMPLETED)
    second = operation("beta", status=OperationStatus.UNDONE)
    second.root = Path("D:/客户/众川")
    second.search = "旧名称"

    assert filter_operations([first, second], query="众川") == [second]
    assert filter_operations([first, second], query="项目") == [first]
    assert filter_operations([first, second], query="BETA") == [second]
    assert filter_operations(
        [first, second], status=OperationStatus.UNDONE
    ) == [second]


def test_default_operation_directory_uses_local_app_data():
    assert default_operation_directory(
        {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}
    ) == Path("C:/Users/test/AppData/Local/BatchRename/operations")
