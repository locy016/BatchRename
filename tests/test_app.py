from pathlib import Path
import tkinter as tk

import main
from batch_rename.app import BatchRenameApp, partition_preview, summarize_candidates
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


def test_preview_is_limited_independently_for_each_category():
    items = [
        candidate("目录1", ItemKind.DIRECTORY),
        candidate("目录2", ItemKind.DIRECTORY),
        candidate("文件1.txt", ItemKind.FILE),
        candidate("文件2.txt", ItemKind.FILE),
    ]

    directories, files = partition_preview(items, limit=1)

    assert [item.old_name for item in directories] == ["目录1"]
    assert [item.old_name for item in files] == ["文件1.txt"]


def test_summary_counts_categories_and_ready_items():
    items = [
        candidate("目录", ItemKind.DIRECTORY),
        candidate("冲突目录", ItemKind.DIRECTORY, CandidateStatus.CONFLICT),
        candidate("文件.txt", ItemKind.FILE),
    ]

    assert summarize_candidates(items) == {
        "directory_total": 2,
        "directory_ready": 1,
        "file_total": 1,
        "file_ready": 1,
        "ready_total": 2,
        "skipped_total": 1,
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
