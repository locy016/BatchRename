from pathlib import Path
import tkinter as tk
from tkinter import ttk

import main
from batch_rename.app import (
    AutoHideScrollbar,
    BatchRenameApp,
    _tree_cell_content,
    sorted_preview_items,
    summarize_candidates,
)
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


def test_main_window_uses_one_result_table_with_type_column():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)

        assert hasattr(app, "result_tree")
        assert not hasattr(app, "preview_notebook")
        assert app.result_tree["columns"][0] == "kind"
        assert hasattr(app, "scope_card")
        assert hasattr(app, "rule_card")
    finally:
        root.destroy()


def test_default_layout_fits_960_by_680_and_expands_the_result_area():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)
        root.update_idletasks()

        assert root.geometry().startswith("960x680")
        assert root.minsize() == (960, 680)
        assert root.winfo_reqwidth() <= 960
        assert root.winfo_reqheight() <= 680
        assert int(app.result_tree.cget("height")) >= 10
        assert app.main_content.grid_rowconfigure(3)["weight"] > 0
        assert app.result_card.grid_rowconfigure(1)["weight"] > 0
    finally:
        root.destroy()


def test_search_and_replacement_inputs_stay_on_one_row():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)

        assert app.search_entry.grid_info()["row"] == app.replacement_entry.grid_info()["row"]
        assert app.search_entry.grid_info()["column"] < app.replacement_entry.grid_info()["column"]
    finally:
        root.destroy()


def test_horizontal_scrollbar_hides_when_everything_is_visible():
    root = tk.Tk()
    root.withdraw()
    try:
        frame = tk.Frame(root)
        frame.grid()
        scrollbar = AutoHideScrollbar(frame, orient="horizontal")
        scrollbar.grid(row=1, column=0, sticky="ew")

        scrollbar.set("0.0", "1.0")
        assert scrollbar.winfo_manager() == ""

        scrollbar.set("0.0", "0.5")
        assert scrollbar.winfo_manager() == "grid"
    finally:
        root.destroy()


def test_tree_cell_content_returns_heading_and_full_value():
    root = tk.Tk()
    root.withdraw()
    try:
        tree = ttk.Treeview(root, columns=("kind", "parent"), show="headings")
        tree.heading("kind", text="类型")
        tree.heading("parent", text="所在目录")
        row = tree.insert("", "end", values=("文件", "C:/这是一个很长的完整目录/子目录"))

        assert _tree_cell_content(tree, row, "#2") == (
            "所在目录",
            "C:/这是一个很长的完整目录/子目录",
        )
        assert _tree_cell_content(tree, "", "#2") is None
        assert _tree_cell_content(tree, row, "#0") is None
    finally:
        root.destroy()


def test_main_window_loads_project_icon_for_window_and_header():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BatchRenameApp(root)

        assert app._app_icon is not None
        assert app.brand_icon_label.cget("image")
    finally:
        root.destroy()
