"""批量重命名核心使用的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class ItemKind(str, Enum):
    DIRECTORY = "文件夹"
    FILE = "文件"


class CandidateStatus(str, Enum):
    READY = "可修改"
    UNCHANGED = "名称未变化"
    CONFLICT = "目标已存在"
    DUPLICATE = "批内目标重复"
    INVALID = "名称不合法"
    ERROR = "无法处理"


@dataclass(frozen=True, slots=True)
class ScanOptions:
    root: Path
    search: str
    replacement: str
    use_regex: bool = False
    max_depth: int | None = None
    include_files: bool = True
    include_dirs: bool = True
    rename_extension: bool = False


@dataclass(frozen=True, slots=True)
class MatchOptions:
    root: Path
    search: str
    use_regex: bool = False
    max_depth: int | None = None
    include_files: bool = True
    include_dirs: bool = True


@dataclass(frozen=True, slots=True)
class MatchedItem:
    source: Path
    kind: ItemKind


@dataclass(slots=True)
class MatchResult:
    root: Path
    search: str
    use_regex: bool
    items: list[MatchedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RenameCandidate:
    source: Path
    target: Path
    kind: ItemKind
    status: CandidateStatus
    detail: str = ""

    @property
    def old_name(self) -> str:
        return self.source.name

    @property
    def new_name(self) -> str:
        return self.target.name


@dataclass(slots=True)
class ScanResult:
    root: Path
    candidates: list[RenameCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ready(self) -> list[RenameCandidate]:
        return [item for item in self.candidates if item.status is CandidateStatus.READY]


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    source: Path
    target: Path
    kind: ItemKind
    outcome: str
    detail: str = ""


@dataclass(slots=True)
class ExecutionResult:
    records: list[ExecutionRecord] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(record.outcome == "成功" for record in self.records)

    @property
    def skipped(self) -> int:
        return sum(record.outcome == "跳过" for record in self.records)

    @property
    def failed(self) -> int:
        return sum(record.outcome == "失败" for record in self.records)


ProgressCallback = Callable[[int, int, ExecutionRecord], None]
