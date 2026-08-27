from pathlib import Path
import tkinter as tk
from tkinter import ttk

import main
import pytest
from batch_rename.app import (
    AutoHideScrollbar,
    BatchRenameApp,
    _tree_cell_content,
    sorted_preview_items,
    summarize_candidates,
)
from batch_rename.examples import REGEX_EXAMPLES
from batch_rename.models import CandidateStatus, ItemKind, RenameCandidate


@pytest.fixture(scope="session")
def tk_session_root():
    """每次测试运行只初始化一次 Tcl/Tk 资源。"""

    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def tk_window(tk_session_root):
    window = tk.Toplevel(tk_session_root)
    window.withdraw()
    yield window
    if window.winfo_exists():
        window.destroy()


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


def test_busy_state_locks_every_rule_and_scope_input(tk_window):
    app = BatchRenameApp(tk_window)

    app._set_busy(True)

    assert app.scan_button.instate(["disabled"])
    assert all(widget.instate(["disabled"]) for widget in app._input_widgets)
    assert app.search_scan_button.instate(["disabled"])


def test_search_scan_button_and_enter_share_the_preview_action(tk_window, monkeypatch):
    calls = []
    monkeypatch.setattr(BatchRenameApp, "_start_scan", lambda self: calls.append("scan"))
    app = BatchRenameApp(tk_window)

    assert app.search_scan_button.cget("text") == "扫描"
    assert app.scan_button.cget("text") == "结果预览"

    app.search_scan_button.invoke()
    assert calls == ["scan"]

    tk_window.deiconify()
    tk_window.update()
    app.search_entry.focus_force()
    tk_window.update()
    app.search_entry.event_generate("<Return>")
    tk_window.update()
    assert calls == ["scan", "scan"]


def test_applying_regex_example_fills_rule_and_enables_regex_mode(tk_window):
    app = BatchRenameApp(tk_window)
    example = REGEX_EXAMPLES[0]

    app._apply_regex_example(example)

    assert app.search_var.get() == example.search
    assert app.replacement_var.get() == example.replacement
    assert app.regex_var.get() is True


def test_applying_extension_regex_example_enables_full_filename_processing(tk_window):
    app = BatchRenameApp(tk_window)
    example = next(item for item in REGEX_EXAMPLES if item.rename_extension)

    app._apply_regex_example(example)

    assert app.rename_extension_var.get() is True


def test_regex_template_chooser_filters_by_category_and_exposes_one_click_apply(
    tk_window,
):
    app = BatchRenameApp(tk_window)
    original_templates = REGEX_EXAMPLES

    app._show_regex_examples()
    categories = tuple(app.regex_category_selector.cget("values"))

    assert len(categories) >= 4
    assert str(app.regex_category_selector.cget("state")) == "readonly"
    assert str(app.regex_search_entry.cget("state")) == "readonly"
    assert str(app.regex_replacement_entry.cget("state")) == "readonly"
    assert app.regex_apply_button.cget("text") == "一键应用此规则"

    selected_category = categories[-1]
    app.regex_category_var.set(selected_category)
    app.regex_category_selector.event_generate("<<ComboboxSelected>>")
    tk_window.update()

    visible_titles = app.regex_template_list.get(0, "end")
    expected_titles = tuple(
        item.title for item in REGEX_EXAMPLES if item.category == selected_category
    )
    assert visible_titles == expected_titles
    assert REGEX_EXAMPLES is original_templates

    app.regex_examples_window.destroy()


def test_main_window_uses_one_result_table_with_type_column(tk_window):
    app = BatchRenameApp(tk_window)

    assert hasattr(app, "result_tree")
    assert not hasattr(app, "preview_notebook")
    assert app.result_tree["columns"][0] == "kind"
    assert hasattr(app, "scope_card")
    assert hasattr(app, "rule_card")
    assert app.regex_templates_button.cget("text") == "正则模板"


def test_default_layout_fits_960_by_680_and_expands_the_result_area(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.update_idletasks()

    assert tk_window.geometry().startswith("960x680")
    assert tk_window.minsize() == (960, 680)
    assert tk_window.winfo_reqwidth() <= 960
    assert tk_window.winfo_reqheight() <= 680
    assert int(app.result_tree.cget("height")) >= 10
    assert app.main_content.grid_rowconfigure(3)["weight"] > 0
    assert app.result_card.grid_rowconfigure(1)["weight"] > 0


def test_settings_use_35_65_split_and_complete_single_line_statistics(tk_window):
    app = BatchRenameApp(tk_window)

    assert app.settings_frame.grid_columnconfigure(0)["weight"] == 35
    assert app.settings_frame.grid_columnconfigure(1)["weight"] == 65
    assert not app.settings_frame.grid_columnconfigure(0)["uniform"]
    assert app.preview_limit_var.get() == 100
    assert app.stats_var.get() == (
        "匹配：0 项 | 可修改：0 项 | 名称未变化：0 项 | 阻止执行：0 项"
    )
    assert not app.stats_label.cget("wraplength")


def test_search_and_replacement_inputs_stay_on_one_row(tk_window):
    app = BatchRenameApp(tk_window)

    assert app.search_entry.grid_info()["row"] == app.replacement_entry.grid_info()["row"]
    assert app.search_entry.grid_info()["column"] < app.replacement_entry.grid_info()["column"]


def test_horizontal_scrollbar_hides_when_everything_is_visible(tk_window):
    frame = tk.Frame(tk_window)
    frame.grid()
    scrollbar = AutoHideScrollbar(frame, orient="horizontal")
    scrollbar.grid(row=1, column=0, sticky="ew")

    scrollbar.set("0.0", "1.0")
    assert scrollbar.winfo_manager() == ""

    scrollbar.set("0.0", "0.5")
    assert scrollbar.winfo_manager() == "grid"


def test_tree_cell_content_returns_heading_and_full_value(tk_window):
    tree = ttk.Treeview(tk_window, columns=("kind", "parent"), show="headings")
    tree.heading("kind", text="类型")
    tree.heading("parent", text="所在目录")
    row = tree.insert("", "end", values=("文件", "C:/这是一个很长的完整目录/子目录"))

    assert _tree_cell_content(tree, row, "#2") == (
        "所在目录",
        "C:/这是一个很长的完整目录/子目录",
    )
    assert _tree_cell_content(tree, "", "#2") is None
    assert _tree_cell_content(tree, row, "#0") is None


def test_main_controls_use_the_polished_component_styles(tk_window):
    app = BatchRenameApp(tk_window)
    style = ttk.Style(tk_window)

    assert app.directory_entry.cget("style") == "Modern.TEntry"
    assert app.search_entry.cget("style") == "Modern.TEntry"
    assert app.replacement_entry.cget("style") == "Modern.TEntry"
    assert app.depth_spin.cget("style") == "Modern.TSpinbox"
    assert app.result_scrollbar.cget("style") == "Modern.Vertical.TScrollbar"
    assert (
        app.result_horizontal_scrollbar.cget("style")
        == "Modern.Horizontal.TScrollbar"
    )
    assert app.progress.cget("style") == "Modern.Horizontal.TProgressbar"
    assert style.lookup("Modern.TEntry", "fieldbackground")
    assert style.lookup("Modern.TSpinbox", "fieldbackground")
    assert style.lookup("Modern.Vertical.TScrollbar", "troughcolor")
    assert style.lookup("Modern.Horizontal.TProgressbar", "troughcolor")


def test_main_window_loads_project_icon_for_window_and_header(tk_window):
    app = BatchRenameApp(tk_window)

    assert app._app_icon is not None
    assert app.brand_icon_label.cget("image")
