"""可持久化操作档案、原子存储与历史筛选。"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .models import ExecutionRecord, ItemKind, ScanOptions, ScanResult


SCHEMA_VERSION = 1
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


class OperationStatus(str, Enum):
    PREPARING = "准备中"
    RUNNING = "执行中"
    COMPLETED = "已完成"
    PARTIAL = "部分失败"
    INTERRUPTED = "已中断"
    UNDO_CHECK_FAILED = "撤回检查失败"
    UNDOING = "撤回中"
    UNDONE = "已撤回"
    PARTIALLY_UNDONE = "部分撤回"
    CORRUPT = "记录损坏"


class UndoStatus(str, Enum):
    PENDING = "待撤回"
    UNDONE = "已撤回"
    FAILED = "撤回失败"
    NOT_APPLICABLE = "无需撤回"


@dataclass(slots=True)
class OperationItem:
    source: Path
    target: Path
    kind: ItemKind
    outcome: str = "待执行"
    detail: str = ""
    execution_index: int | None = None
    undo_status: UndoStatus = UndoStatus.NOT_APPLICABLE
    undo_detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "target": str(self.target),
            "kind": self.kind.value,
            "outcome": self.outcome,
            "detail": self.detail,
            "execution_index": self.execution_index,
            "undo_status": self.undo_status.value,
            "undo_detail": self.undo_detail,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OperationItem:
        return cls(
            source=Path(str(payload["source"])),
            target=Path(str(payload["target"])),
            kind=ItemKind(str(payload["kind"])),
            outcome=str(payload.get("outcome", "待执行")),
            detail=str(payload.get("detail", "")),
            execution_index=(
                None
                if payload.get("execution_index") is None
                else int(payload["execution_index"])
            ),
            undo_status=UndoStatus(
                str(payload.get("undo_status", UndoStatus.NOT_APPLICABLE.value))
            ),
            undo_detail=str(payload.get("undo_detail", "")),
        )


@dataclass(slots=True)
class OperationLog:
    identifier: str
    created_at: str
    updated_at: str
    root: Path
    search: str
    replacement: str
    use_regex: bool = False
    max_depth: int | None = None
    include_files: bool = True
    include_dirs: bool = True
    rename_extension: bool = False
    status: OperationStatus = OperationStatus.PREPARING
    items: list[OperationItem] = field(default_factory=list)
    error: str = ""
    schema_version: int = SCHEMA_VERSION

    @property
    def success_count(self) -> int:
        return sum(item.outcome == "成功" for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.outcome == "跳过" for item in self.items)

    @property
    def failed_count(self) -> int:
        return sum(item.outcome == "失败" for item in self.items)

    @property
    def undone_count(self) -> int:
        return sum(item.undo_status is UndoStatus.UNDONE for item in self.items)

    @property
    def pending_undo_count(self) -> int:
        return sum(
            item.outcome == "成功" and item.undo_status is not UndoStatus.UNDONE
            for item in self.items
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "identifier": self.identifier,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "root": str(self.root),
            "search": self.search,
            "replacement": self.replacement,
            "use_regex": self.use_regex,
            "max_depth": self.max_depth,
            "include_files": self.include_files,
            "include_dirs": self.include_dirs,
            "rename_extension": self.rename_extension,
            "status": self.status.value,
            "items": [item.to_dict() for item in self.items],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OperationLog:
        schema_version = int(payload.get("schema_version", 0))
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"不支持的操作档案版本：{schema_version}")
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("操作项目列表格式不正确")
        return cls(
            schema_version=schema_version,
            identifier=str(payload["identifier"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            root=Path(str(payload["root"])),
            search=str(payload.get("search", "")),
            replacement=str(payload.get("replacement", "")),
            use_regex=bool(payload.get("use_regex", False)),
            max_depth=(
                None
                if payload.get("max_depth") is None
                else int(payload["max_depth"])
            ),
            include_files=bool(payload.get("include_files", True)),
            include_dirs=bool(payload.get("include_dirs", True)),
            rename_extension=bool(payload.get("rename_extension", False)),
            status=OperationStatus(str(payload["status"])),
            items=[OperationItem.from_dict(item) for item in raw_items],
            error=str(payload.get("error", "")),
        )


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_operation_directory(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """返回当前用户的操作档案目录。"""

    values = os.environ if environ is None else environ
    local_app_data = values.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "BatchRename" / "operations"


def create_operation_log(
    scan: ScanResult,
    options: ScanOptions,
    *,
    identifier: str | None = None,
    created_at: str | None = None,
) -> OperationLog:
    """根据最终预览建立尚未执行的完整操作档案。"""

    timestamp = created_at or _now_iso()
    return OperationLog(
        identifier=identifier or f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}",
        created_at=timestamp,
        updated_at=timestamp,
        root=scan.root,
        search=options.search,
        replacement=options.replacement,
        use_regex=options.use_regex,
        max_depth=options.max_depth,
        include_files=options.include_files,
        include_dirs=options.include_dirs,
        rename_extension=options.rename_extension,
        status=OperationStatus.PREPARING,
        items=[
            OperationItem(
                source=candidate.source,
                target=candidate.target,
                kind=candidate.kind,
            )
            for candidate in scan.candidates
        ],
    )


def append_execution_record(
    operation: OperationLog, record: ExecutionRecord
) -> OperationItem:
    """把执行器返回的一项结果写回对应档案项目。"""

    item = next(
        (
            candidate
            for candidate in operation.items
            if candidate.source == record.source
            and candidate.target == record.target
            and candidate.kind is record.kind
        ),
        None,
    )
    if item is None:
        item = OperationItem(
            source=record.source,
            target=record.target,
            kind=record.kind,
        )
        operation.items.append(item)
    item.outcome = record.outcome
    item.detail = record.detail
    if item.execution_index is None:
        item.execution_index = (
            max(
                (
                    candidate.execution_index or 0
                    for candidate in operation.items
                ),
                default=0,
            )
            + 1
        )
    item.undo_status = (
        UndoStatus.PENDING
        if record.outcome == "成功"
        else UndoStatus.NOT_APPLICABLE
    )
    item.undo_detail = ""
    operation.status = OperationStatus.RUNNING
    return item


def finalize_operation(operation: OperationLog) -> None:
    """根据完整执行结果确定操作档案的最终状态。"""

    operation.status = (
        OperationStatus.PARTIAL
        if operation.failed_count
        else OperationStatus.COMPLETED
    )


class OperationStore:
    """以独立 JSON 文件安全保存和加载操作档案。"""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        clock: Callable[[], str] = _now_iso,
    ) -> None:
        self.directory = (
            default_operation_directory() if directory is None else Path(directory)
        )
        self.clock = clock

    def new_identifier(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{uuid.uuid4().hex[:8]}"

    def path_for(self, identifier: str) -> Path:
        if not _SAFE_IDENTIFIER.fullmatch(identifier):
            raise ValueError("操作标识包含不安全字符")
        return self.directory / f"{identifier}.json"

    def create(self, operation: OperationLog) -> Path:
        target = self.path_for(operation.identifier)
        if target.exists():
            raise FileExistsError(f"操作档案已经存在：{operation.identifier}")
        return self.save(operation)

    def save(self, operation: OperationLog) -> Path:
        target = self.path_for(operation.identifier)
        self.directory.mkdir(parents=True, exist_ok=True)
        operation.updated_at = self.clock()
        temporary = target.with_name(f".{target.stem}-{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(operation.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(target)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return target

    def load(self, identifier: str) -> OperationLog:
        target = self.path_for(identifier)
        payload = json.loads(target.read_text(encoding="utf-8"))
        operation = OperationLog.from_dict(payload)
        if operation.status in {
            OperationStatus.PREPARING,
            OperationStatus.RUNNING,
        }:
            operation.status = OperationStatus.INTERRUPTED
            operation.error = operation.error or "程序在操作完成前退出"
            self.save(operation)
        elif operation.status is OperationStatus.UNDOING:
            operation.status = OperationStatus.PARTIALLY_UNDONE
            operation.error = operation.error or "程序在撤回完成前退出"
            self.save(operation)
        return operation

    def load_all(self) -> list[OperationLog]:
        if not self.directory.exists():
            return []
        operations: list[OperationLog] = []
        for path in self.directory.glob("*.json"):
            try:
                operations.append(self.load(path.stem))
            except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                try:
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
                    created_at = timestamp.isoformat(timespec="seconds")
                except OSError:
                    created_at = ""
                operations.append(
                    OperationLog(
                        identifier=path.stem,
                        created_at=created_at,
                        updated_at=created_at,
                        root=path.parent,
                        search="",
                        replacement="",
                        status=OperationStatus.CORRUPT,
                        error=str(exc),
                    )
                )
        valid = [
            operation
            for operation in operations
            if operation.status is not OperationStatus.CORRUPT
        ]
        damaged = [
            operation
            for operation in operations
            if operation.status is OperationStatus.CORRUPT
        ]
        ordering = lambda operation: (operation.created_at, operation.identifier)
        return sorted(valid, key=ordering, reverse=True) + sorted(
            damaged, key=ordering, reverse=True
        )


def filter_operations(
    operations: Iterable[OperationLog],
    *,
    query: str = "",
    status: OperationStatus | str | None = None,
) -> list[OperationLog]:
    """按关键词和状态筛选操作档案，同时保持传入顺序。"""

    keyword = query.strip().casefold()
    expected_status = (
        None
        if status in (None, "", "全部状态")
        else status.value
        if isinstance(status, OperationStatus)
        else str(status)
    )
    result: list[OperationLog] = []
    for operation in operations:
        if expected_status is not None and operation.status.value != expected_status:
            continue
        haystack = "\n".join(
            (
                operation.identifier,
                str(operation.root),
                operation.search,
                operation.replacement,
            )
        ).casefold()
        if keyword and keyword not in haystack:
            continue
        result.append(operation)
    return result
