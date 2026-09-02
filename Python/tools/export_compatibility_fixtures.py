"""导出 Python 1.x 与 Rust 2.x 共用的脱敏行为夹具。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from batch_rename.core import RenameRule, RuleError  # noqa: E402
from batch_rename.examples import REGEX_EXAMPLES  # noqa: E402
from batch_rename.history import (  # noqa: E402
    OperationItem,
    OperationLog,
    OperationStatus,
    UndoStatus,
)
from batch_rename.models import ItemKind  # noqa: E402


REPOSITORY_ROOT = PYTHON_ROOT.parent
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures"
FIXED_TIME = "2026-09-02T10:00:00+08:00"


def _rule_case(
    identifier: str,
    search: str,
    replacement: str,
    input_name: str,
    *,
    is_file: bool,
    rename_extension: bool,
    use_regex: bool,
) -> dict[str, object]:
    expected_name: str | None = None
    expected_error: str | None = None
    try:
        rule = RenameRule(
            search,
            replacement,
            use_regex=use_regex,
            rename_extension=rename_extension,
        )
        expected_name = rule.rename(input_name, is_file=is_file)
    except RuleError:
        expected_error = "invalidReplacementReference"
    return {
        "id": identifier,
        "search": search,
        "replacement": replacement,
        "input": input_name,
        "isFile": is_file,
        "renameExtension": rename_extension,
        "expectedName": expected_name,
        "expectedError": expected_error,
    }


def export_rules() -> None:
    cases = [
        _rule_case(
            "plain-text",
            "旧版",
            "正式",
            "项目旧版.txt",
            is_file=True,
            rename_extension=False,
            use_regex=False,
        ),
        _rule_case(
            "protected-extension",
            "txt",
            "md",
            "说明.txt",
            is_file=True,
            rename_extension=False,
            use_regex=False,
        ),
        _rule_case(
            "unchanged",
            "报告",
            "报告",
            "报告.docx",
            is_file=True,
            rename_extension=False,
            use_regex=False,
        ),
        _rule_case(
            "invalid-reference",
            r"(报告)",
            r"\9",
            "报告.docx",
            is_file=True,
            rename_extension=False,
            use_regex=True,
        ),
    ]
    for index, example in enumerate(REGEX_EXAMPLES, start=1):
        cases.append(
            _rule_case(
                f"template-{index:02d}",
                example.search,
                example.replacement,
                example.before,
                is_file=True,
                rename_extension=example.rename_extension,
                use_regex=True,
            )
        )

    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    (FIXTURE_ROOT / "rules-v1.json").write_text(
        json.dumps({"schemaVersion": 1, "cases": cases}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _item(
    source_name: str,
    target_name: str,
    *,
    kind: ItemKind = ItemKind.FILE,
    outcome: str = "成功",
    detail: str = "重命名完成",
    execution_index: int = 1,
    undo_status: UndoStatus = UndoStatus.PENDING,
    undo_detail: str = "",
) -> OperationItem:
    root = Path("示例资料") / "项目A"
    return OperationItem(
        source=root / source_name,
        target=root / target_name,
        kind=kind,
        outcome=outcome,
        detail=detail,
        execution_index=execution_index,
        undo_status=undo_status,
        undo_detail=undo_detail,
    )


def _operation(
    identifier: str,
    status: OperationStatus,
    items: list[OperationItem],
    *,
    error: str = "",
) -> OperationLog:
    return OperationLog(
        identifier=identifier,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        root=Path("示例资料") / "项目A",
        search="旧版",
        replacement="正式",
        include_files=True,
        include_dirs=True,
        status=status,
        items=items,
        error=error,
    )


def export_logs() -> None:
    log_root = FIXTURE_ROOT / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    operations = {
        "operation-completed-v1.json": _operation(
            "demo-completed-v1",
            OperationStatus.COMPLETED,
            [_item("项目旧版.txt", "项目正式.txt")],
        ),
        "operation-partial-v1.json": _operation(
            "demo-partial-v1",
            OperationStatus.PARTIAL,
            [
                _item("资料旧版", "资料正式", kind=ItemKind.DIRECTORY),
                _item(
                    "占用旧版.txt",
                    "占用正式.txt",
                    outcome="失败",
                    detail="目标在执行前已存在",
                    execution_index=2,
                    undo_status=UndoStatus.NOT_APPLICABLE,
                ),
            ],
            error="1 项未能完成",
        ),
        "operation-interrupted-v1.json": _operation(
            "demo-interrupted-v1",
            OperationStatus.INTERRUPTED,
            [_item("已处理旧版.txt", "已处理正式.txt")],
            error="程序在操作完成前退出",
        ),
        "operation-partially-undone-v1.json": _operation(
            "demo-partially-undone-v1",
            OperationStatus.PARTIALLY_UNDONE,
            [
                _item(
                    "文档旧版.txt",
                    "文档正式.txt",
                    undo_status=UndoStatus.UNDONE,
                    undo_detail="已恢复原名称",
                ),
                _item(
                    "图片旧版.jpg",
                    "图片正式.jpg",
                    execution_index=2,
                    undo_status=UndoStatus.FAILED,
                    undo_detail="原名称已被占用",
                ),
            ],
            error="撤回在第 2 项停止",
        ),
    }
    for filename, operation in operations.items():
        (log_root / filename).write_text(
            json.dumps(operation.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    export_rules()
    export_logs()


if __name__ == "__main__":
    main()
