from pathlib import Path
import tkinter as tk

import main
from batch_rename.app import BatchRenameApp, sorted_preview_items, summarize_candidates
from batch_rename.examples import REGEX_EXAMPLES
from batch_rename.models import CandidateStatus, ItemKind, RenameCandidate


def candidate(name, kind, status=CandidateStatus.READY):
    source = Path("C:/root") / name
    return RenameCandidate(
        source=source,
        target=source.with_name("新-" + name),
        kind=kind,
        status=status,
    )


def test_main_exposes_callable_entrypoint():
    assert callable(main.main)
    assert BatchRenameApp.__name__ == "BatchRenameApp"


def test_preview_combines_categories_and_uses_natural_name_order():
    items = [
        candidate("文件10.txt", ItemKind.FILE),
        candidate("目录10", ItemKind.DIRECTORY),
        candidate("文件2.txt", ItemKind.FILE),
        candidate("目录2", ItemKind.DIRECTORY),
    ]

    preview = sorted_preview_items(items, limit=3)

    assert [item.old_name for item in preview] == ["目录2", "目录10", "文件2.txt"]


def test_summary_counts_categories_and_ready_items():
    items = [
        candidate("目录", ItemKind.DIRECTORY),
        candidate("无变化目录", ItemKind.DIRECTORY, CandidateStatus.UNCHANGED),
        candidate("冲突目录", ItemKind.DIRECTORY, CandidateStatus.CONFLICT),
        candidate("文件.txt", ItemKind.FILE),
    ]

    assert summarize_candidates(items) == {
        "matched_total": 4,
        "ready_total": 2,
        "unchanged_total": 1,
        "blocked_total": 1,
    }


def test_busy_state_locks_every_rule_and_scope_input():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)

        app._set_busy(True)

        assert app.scan_button.instate(["disabled"])
        assert all(widget.instate(["disabled"]) for widget in app._input_widgets)
    finally:
        root.destroy()


def test_applying_regex_example_fills_rule_and_enables_regex_mode():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)
        example = REGEX_EXAMPLES[0]

        app._apply_regex_example(example)

        assert app.search_var.get() == example.search
        assert app.replacement_var.get() == example.replacement
        assert app.regex_var.get() is True
    finally:
        root.destroy()
