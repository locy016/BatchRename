"""与图形界面无关的重命名规则、扫描和执行逻辑。"""

from __future__ import annotations

import os
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .models import (
    CandidateStatus,
    ExecutionRecord,
    ExecutionResult,
    ItemKind,
    MatchedItem,
    MatchOptions,
    MatchResult,
    ProgressCallback,
    RenameCandidate,
    ScanOptions,
    ScanResult,
)


class RuleError(ValueError):
    """重命名规则不可用。"""


class ScanError(ValueError):
    """扫描范围或参数不可用。"""


_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]|[\x00-\x1f]')
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _natural_name_key(value: str) -> tuple[tuple[int, str | int], ...]:
    """生成不区分大小写且支持数字片段的稳定名称排序键。"""

    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", value)
    )


def validate_windows_name(name: str) -> str | None:
    """返回 Windows 文件名无效的中文原因，有效时返回 ``None``。"""

    if not name:
        return "新名称不能为空"
    if name in {".", ".."}:
        return "新名称不能是 . 或 .."
    if len(name) > 255:
        return "新名称不能超过 255 个字符"
    if _INVALID_CHARS.search(name):
        return '新名称包含 Windows 不允许的字符 < > : " / \\ | ? *'
    if name.endswith((" ", ".")):
        return "新名称不能以空格或句点结尾"
    stem = name.split(".", 1)[0].upper()
    if stem in _RESERVED_NAMES:
        return f"{stem} 是 Windows 保留名称"
    return None


class RenameRule:
    """普通文本或正则表达式重命名规则。"""

    def __init__(
        self,
        search: str,
        replacement: str,
        *,
        use_regex: bool = False,
        rename_extension: bool = False,
    ) -> None:
        if not search:
            raise RuleError("查找内容不能为空")
        self.search = search
        self.replacement = replacement
        self.use_regex = use_regex
        self.rename_extension = rename_extension
        self._pattern: re.Pattern[str] | None = None
        if use_regex:
            try:
                self._pattern = re.compile(search)
            except re.error as exc:
                raise RuleError(f"正则表达式无效：{exc}") from exc
            try:
                self._pattern.sub(replacement, "")
            except re.error as exc:
                raise RuleError(f"正则替换内容无效：{exc}") from exc

    def rename(self, name: str, *, is_file: bool) -> str:
        """根据规则返回新名称；默认只处理文件的主文件名。"""

        target_text = name
        suffix = ""
        if is_file and not self.rename_extension:
            target_text, suffix = os.path.splitext(name)
        if self._pattern is not None:
            renamed = self._pattern.sub(self.replacement, target_text)
        else:
            renamed = target_text.replace(self.search, self.replacement)
        return renamed + suffix

    def matches(self, name: str) -> bool:
        """判断完整名称是否符合搜索条件，不受扩展名保护影响。"""

        if self._pattern is not None:
            return self._pattern.search(name) is not None
        return self.search in name


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def search_matches(options: MatchOptions) -> MatchResult:
    """只读取目录并返回名称符合查找规则的项目快照。"""

    root = Path(options.root).expanduser().resolve()
    if not root.is_dir():
        raise ScanError("所选目录不存在或不是文件夹")
    if options.max_depth is not None and options.max_depth < 1:
        raise ScanError("扫描层级必须是大于或等于 1 的整数")
    if not options.include_files and not options.include_dirs:
        raise ScanError("请至少选择文件夹或文件中的一类")

    rule = RenameRule(options.search, "", use_regex=options.use_regex)
    result = MatchResult(
        root=root,
        search=options.search,
        use_regex=options.use_regex,
    )
    pending: list[tuple[Path, int]] = [(root, 1)]

    while pending:
        parent, child_depth = pending.pop()
        try:
            with os.scandir(parent) as iterator:
                entries = sorted(
                    iterator,
                    key=lambda item: item.name.casefold(),
                    reverse=True,
                )
        except OSError as exc:
            result.errors.append(f"无法读取 {parent}：{exc}")
            continue

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError as exc:
                result.errors.append(f"无法检查 {entry.path}：{exc}")
                continue

            source = Path(entry.path)
            if is_dir and (
                options.max_depth is None or child_depth < options.max_depth
            ):
                pending.append((source, child_depth + 1))

            selected = (is_dir and options.include_dirs) or (
                is_file and options.include_files
            )
            if selected and rule.matches(entry.name):
                result.items.append(
                    MatchedItem(
                        source=source,
                        kind=ItemKind.DIRECTORY if is_dir else ItemKind.FILE,
                    )
                )

    result.items.sort(
        key=lambda item: (
            item.kind is ItemKind.FILE,
            _natural_name_key(item.source.name),
            str(item.source.parent).casefold(),
        )
    )
    return result


def build_preview(
    snapshot: MatchResult,
    replacement: str,
    *,
    rename_extension: bool = False,
) -> ScanResult:
    """从名称匹配快照计算目标名称与安全状态，不重新遍历目录。"""

    rule = RenameRule(
        snapshot.search,
        replacement,
        use_regex=snapshot.use_regex,
        rename_extension=rename_extension,
    )
    result = ScanResult(root=snapshot.root, errors=list(snapshot.errors))

    for item in snapshot.items:
        source = item.source
        is_file = item.kind is ItemKind.FILE
        new_name = rule.rename(source.name, is_file=is_file)
        if new_name == source.name:
            detail = "名称符合搜索条件，但替换后没有变化"
            if is_file and not rename_extension:
                stem, _suffix = os.path.splitext(source.name)
                if not rule.matches(stem):
                    detail = "搜索内容位于受保护的文件扩展名中，因此名称没有变化"
            result.candidates.append(
                RenameCandidate(
                    source=source,
                    target=source,
                    kind=item.kind,
                    status=CandidateStatus.UNCHANGED,
                    detail=detail,
                )
            )
            continue

        target = source.with_name(new_name)
        invalid_reason = validate_windows_name(new_name)
        if invalid_reason:
            status = CandidateStatus.INVALID
            detail = invalid_reason
        elif target.exists() and _path_key(target) != _path_key(source):
            status = CandidateStatus.CONFLICT
            detail = "同一目录中已存在该目标名称"
        else:
            status = CandidateStatus.READY
            detail = "可以安全修改"
        result.candidates.append(
            RenameCandidate(
                source=source,
                target=target,
                kind=item.kind,
                status=status,
                detail=detail,
            )
        )

    target_groups: dict[str, list[RenameCandidate]] = defaultdict(list)
    for candidate in result.candidates:
        if candidate.status is CandidateStatus.READY:
            target_groups[_path_key(candidate.target)].append(candidate)
    for group in target_groups.values():
        if len(group) > 1:
            for candidate in group:
                candidate.status = CandidateStatus.DUPLICATE
                candidate.detail = "多个来源会生成同一个目标名称"

    result.candidates.sort(
        key=lambda item: (
            item.kind is ItemKind.FILE,
            str(item.source.parent).casefold(),
            item.source.name.casefold(),
        )
    )
    return result


def scan(options: ScanOptions) -> ScanResult:
    """兼容入口：依次生成匹配快照和重命名预览。"""

    snapshot = search_matches(
        MatchOptions(
            root=options.root,
            search=options.search,
            use_regex=options.use_regex,
            max_depth=options.max_depth,
            include_files=options.include_files,
            include_dirs=options.include_dirs,
        )
    )
    return build_preview(
        snapshot,
        options.replacement,
        rename_extension=options.rename_extension,
    )


def _rename_case_only(source: Path, target: Path) -> None:
    """通过同目录临时名称可靠完成 Windows 仅大小写变化的改名。"""

    temporary = source.with_name(f".__batch_rename_{uuid.uuid4().hex}__")
    source.rename(temporary)
    try:
        temporary.rename(target)
    except OSError:
        try:
            temporary.rename(source)
        except OSError:
            pass
        raise


def execute(
    candidates: Iterable[RenameCandidate],
    *,
    progress: ProgressCallback | None = None,
) -> ExecutionResult:
    """安全执行候选项，逐项返回成功、跳过或失败记录。"""

    ordered = sorted(
        candidates,
        key=lambda item: (
            len(item.source.parts),
            item.kind is ItemKind.FILE,
        ),
        reverse=True,
    )
    result = ExecutionResult()
    total = len(ordered)

    for current, candidate in enumerate(ordered, start=1):
        if candidate.status is not CandidateStatus.READY:
            record = ExecutionRecord(
                source=candidate.source,
                target=candidate.target,
                kind=candidate.kind,
                outcome="跳过",
                detail=candidate.detail or candidate.status.value,
            )
        elif not candidate.source.exists():
            record = ExecutionRecord(
                source=candidate.source,
                target=candidate.target,
                kind=candidate.kind,
                outcome="跳过",
                detail="来源在扫描后已不存在",
            )
        elif (
            candidate.target.exists()
            and _path_key(candidate.target) != _path_key(candidate.source)
        ):
            record = ExecutionRecord(
                source=candidate.source,
                target=candidate.target,
                kind=candidate.kind,
                outcome="跳过",
                detail="目标在扫描后已存在",
            )
        else:
            try:
                if (
                    candidate.source != candidate.target
                    and _path_key(candidate.source) == _path_key(candidate.target)
                ):
                    _rename_case_only(candidate.source, candidate.target)
                else:
                    candidate.source.rename(candidate.target)
                record = ExecutionRecord(
                    source=candidate.source,
                    target=candidate.target,
                    kind=candidate.kind,
                    outcome="成功",
                    detail="重命名完成",
                )
            except OSError as exc:
                record = ExecutionRecord(
                    source=candidate.source,
                    target=candidate.target,
                    kind=candidate.kind,
                    outcome="失败",
                    detail=str(exc),
                )

        result.records.append(record)
        if progress is not None:
            progress(current, total, record)

    return result
