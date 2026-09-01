from pathlib import Path
import tkinter as tk
from tkinter import ttk

import main
import pytest
from batch_rename.app import (
    AutoHideScrollbar,
    BatchRenameApp,
    ManagedDialogs,
    _tree_cell_content,
    centered_dialog_geometry,
    sorted_preview_items,
    summarize_candidates,
)
from batch_rename.examples import REGEX_EXAMPLES
from batch_rename.models import (
    CandidateStatus,
    ItemKind,
    MatchedItem,
    MatchResult,
    RenameCandidate,
    ScanResult,
)


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


def menu_labels(menu):
    end = menu.index("end")
    if end is None:
        return ()
    return tuple(
        menu.entrycget(index, "label")
        for index in range(end + 1)
        if menu.type(index) != "separator"
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

    assert app.preview_button.instate(["disabled"])
    assert all(widget.instate(["disabled"]) for widget in app._input_widgets)
    assert app.search_button.instate(["disabled"])


def match_result(search="项目"):
    source = Path("C:/root/项目合同.docx")
    return MatchResult(
        root=Path("C:/root"),
        search=search,
        use_regex=False,
        items=[MatchedItem(source=source, kind=ItemKind.FILE)],
    )


def scan_result():
    item = candidate("项目合同.docx", ItemKind.FILE)
    return ScanResult(root=Path("C:/root"), candidates=[item])


def test_search_and_preview_commands_are_separate(tk_window, monkeypatch):
    calls = []
    monkeypatch.setattr(BatchRenameApp, "_start_search", lambda self: calls.append("search"))
    monkeypatch.setattr(BatchRenameApp, "_start_preview", lambda self: calls.append("preview"))
    app = BatchRenameApp(tk_window)

    assert app.search_button.cget("text") == "扫描"
    assert app.preview_button.cget("text") == "结果预览"

    app.search_button.invoke()
    assert calls == ["search"]

    app._last_matches = match_result()
    app._sync_command_states()
    app.preview_button.invoke()
    assert calls == ["search", "preview"]

    tk_window.deiconify()
    tk_window.update()
    app.search_entry.focus_force()
    tk_window.update()
    app.search_entry.event_generate("<Return>")
    tk_window.update()
    assert calls == ["search", "preview", "search"]

    app.replacement_entry.focus_force()
    tk_window.update()
    app.replacement_entry.event_generate("<Return>")
    tk_window.update()
    assert calls == ["search", "preview", "search", "preview"]


def test_replacement_change_keeps_match_snapshot_but_invalidates_preview(tk_window):
    app = BatchRenameApp(tk_window)
    app._last_matches = match_result()
    app._last_scan = scan_result()

    app.replacement_var.set("新名称")

    assert app._last_matches is not None
    assert app._last_scan is None


def test_search_change_invalidates_match_snapshot_and_preview(tk_window):
    app = BatchRenameApp(tk_window)
    app._last_matches = match_result()
    app._last_scan = scan_result()

    app.search_var.set("另一规则")

    assert app._last_matches is None
    assert app._last_scan is None


def test_matched_snapshot_renders_waiting_preview_rows(tk_window):
    app = BatchRenameApp(tk_window)
    app._last_matches = match_result()

    app._render_preview()

    row = app.result_tree.get_children()[0]
    values = app.result_tree.item(row, "values")
    assert values[2:] == (
        "项目合同.docx",
        "",
        "等待结果预览",
        "填写替换内容后生成结果预览",
    )


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
    assert app.active_tool_panel == "templates"
    assert app.templates_panel.winfo_manager() == "place"
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

    app._close_tool_panel()


def test_bottom_tool_panels_are_mutually_exclusive_and_collapsible(tk_window):
    app = BatchRenameApp(tk_window)

    app._toggle_tool_panel("settings")
    assert app.active_tool_panel == "settings"
    assert app.settings_panel.winfo_manager() == "place"

    app._toggle_tool_panel("templates")
    assert app.active_tool_panel == "templates"
    assert app.settings_panel.winfo_manager() == ""
    assert app.templates_panel.winfo_manager() == "place"

    app._toggle_tool_panel("templates")
    assert app.active_tool_panel is None
    assert app.templates_panel.winfo_manager() == ""


def test_escape_and_workspace_click_close_floating_tools(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()
    tk_window.focus_force()
    tk_window.update()

    app._toggle_tool_panel("settings")
    tk_window.event_generate("<Escape>")
    tk_window.update()
    assert app.active_tool_panel is None

    app._toggle_tool_panel("templates")
    app.result_workspace.event_generate("<Button-1>")
    tk_window.update()
    assert app.active_tool_panel is None


def test_main_window_uses_one_result_table_with_type_column(tk_window):
    app = BatchRenameApp(tk_window)

    assert hasattr(app, "result_tree")
    assert not hasattr(app, "preview_notebook")
    assert app.result_tree["columns"] == (
        "kind",
        "parent",
        "old",
        "new",
        "status",
        "detail",
    )
    assert hasattr(app, "workflow_rail")
    assert hasattr(app, "result_workspace")
    assert not hasattr(app, "scope_card")
    assert not hasattr(app, "rule_card")
    assert not hasattr(app, "help_button")


def test_top_menu_contains_only_global_commands(tk_window):
    app = BatchRenameApp(tk_window)

    assert menu_labels(app.top_menu) == ("文件", "功能", "帮助")
    assert menu_labels(app.file_menu) == ("退出",)
    assert menu_labels(app.feature_menu) == (
        "结果详情",
        "撤回管理（开发中）",
        "操作日志（开发中）",
    )
    assert menu_labels(app.help_menu) == ("使用说明", "关于")
    assert app.feature_menu.entrycget(app.undo_menu_index, "state") == "disabled"
    assert app.feature_menu.entrycget(app.log_menu_index, "state") == "disabled"

    workflow_labels = {
        app.directory_select_button.cget("text"),
        app.search_button.cget("text"),
        app.preview_button.cget("text"),
        app.execute_button.cget("text"),
    }
    top_commands = set(
        menu_labels(app.file_menu)
        + menu_labels(app.feature_menu)
        + menu_labels(app.help_menu)
    )
    assert workflow_labels.isdisjoint(top_commands)


def test_about_describes_current_beta_roadmap_safety_and_contact(tk_window):
    app = BatchRenameApp(tk_window)

    app._show_about()

    window = app.dialogs.windows["about"]
    content = app.about_content_var.get()
    assert "1.1.0-beta.1" in content
    assert "两阶段" in content
    assert "正则模板" in content
    assert "撤回管理" in content and "开发中" in content
    assert "操作日志" in content and "开发中" in content
    assert "快速开发期" in content
    assert "备份" in content and "自行确认" in content
    assert app.about_email_var.get() == "lo.c@live.cn"
    assert str(app.about_email_entry.cget("state")) == "readonly"
    assert not app.about_email_entry.bind("<Button-1>")
    assert window.winfo_exists()


def test_result_table_values_follow_the_visible_column_order(tk_window):
    app = BatchRenameApp(tk_window)
    item = candidate("文件2.txt", ItemKind.FILE)

    app._fill_tree(app.result_tree, [item])

    row = app.result_tree.get_children()[0]
    assert app.result_tree.item(row, "values") == (
        "文件",
        str(item.source.parent),
        "文件2.txt",
        "新-文件2.txt",
        "可修改",
        "",
    )


def test_new_name_column_uses_a_dedicated_accent_text_overlay(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()

    app._fill_tree(app.result_tree, [candidate("文件2.txt", ItemKind.FILE)])
    tk_window.update()

    visible_labels = app.new_name_overlay.visible_labels
    assert len(visible_labels) == 1
    assert visible_labels[0].cget("text") == "新-文件2.txt"
    assert visible_labels[0].cget("foreground") == app.COLORS["accent"]

    app._fill_tree(app.result_tree, [])
    tk_window.update()
    assert app.new_name_overlay.visible_labels == ()


def test_default_layout_fits_960_by_680_and_expands_the_result_area(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.update_idletasks()

    assert tk_window.geometry().startswith("960x680")
    assert tk_window.minsize() == (960, 680)
    assert tk_window.winfo_reqwidth() <= 960
    assert tk_window.winfo_reqheight() <= 680
    assert int(app.result_tree.cget("height")) >= 10
    assert app.main_content.grid_rowconfigure(1)["weight"] > 0
    assert app.result_workspace.grid_rowconfigure(1)["weight"] > 0
    assert app.result_card.grid_rowconfigure(1)["weight"] > 0


def test_left_workflow_is_ordered_and_statistics_stay_on_one_line(tk_window):
    app = BatchRenameApp(tk_window)

    assert app.preview_limit_var.get() == 100
    assert app.stats_var.get() == (
        "匹配：0项 | 可修改：0项 | 名称未变化：0项 | 阻止执行：0项"
    )
    assert not app.stats_label.cget("wraplength")

    rows = [
        app.directory_select_button.grid_info()["row"],
        app.plain_mode_radio.grid_info()["row"],
        app.search_entry.grid_info()["row"],
        app.search_button.grid_info()["row"],
        app.replacement_entry.grid_info()["row"],
        app.preview_button.grid_info()["row"],
        app.execute_button.grid_info()["row"],
    ]
    assert rows == sorted(rows)
    assert len(set(rows)) == len(rows)
    assert int(app.workflow_rail.cget("width")) <= 280


def test_horizontal_scrollbar_hides_when_everything_is_visible(tk_window):
    frame = tk.Frame(tk_window)
    frame.grid()
    scrollbar = AutoHideScrollbar(frame, orient="horizontal")
    scrollbar.grid(row=1, column=0, sticky="ew")

    scrollbar.set("0.0", "1.0")
    assert scrollbar.winfo_manager() == ""

    scrollbar.set("0.0", "0.5")
    assert scrollbar.winfo_manager() == "grid"


def test_centered_dialog_geometry_is_clamped_to_parent_monitor():
    geometry = centered_dialog_geometry(
        parent=(2100, 100, 960, 680),
        dialog=(760, 640),
        work_area=(1920, 0, 3840, 1040),
    )

    assert geometry == "760x640+2200+120"


def test_managed_dialog_reuses_instance_and_unregisters_on_close(tk_window):
    dialogs = ManagedDialogs(tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080))
    built = []

    first = dialogs.open(
        "help",
        title="使用说明",
        size=(500, 400),
        build=lambda window: built.append(window),
        modal=True,
    )
    second = dialogs.open(
        "help",
        title="不会重复创建",
        size=(300, 200),
        build=lambda window: built.append(window),
        modal=True,
    )

    assert first is second
    assert built == [first]
    assert str(first.transient()) == str(tk_window)
    assert first.grab_current() == first

    dialogs.close("help")
    assert "help" not in dialogs.windows


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
    assert app.preview_spin.cget("style") == "Modern.TSpinbox"
    assert app.depth_spin.cget("justify") == "center"
    assert app.preview_spin.cget("justify") == "center"
    assert app.root_directory_label.cget("style") == "WorkflowTitle.TLabel"
    assert app.search_field_label.cget("style") == "WorkflowHint.TLabel"
    assert app.replacement_field_label.cget("style") == "WorkflowTitle.TLabel"
    assert app.stats_label.cget("style") == "MatchStats.TLabel"
    assert app.workflow_rail.cget("style") == "Workflow.TFrame"
    assert app.result_scrollbar.cget("style") == "Modern.Vertical.TScrollbar"
    assert (
        app.result_horizontal_scrollbar.cget("style")
        == "Modern.Horizontal.TScrollbar"
    )
    assert app.progress.cget("style") == "Modern.Horizontal.TProgressbar"
    assert style.lookup("Modern.TEntry", "fieldbackground")
    assert style.lookup("Modern.TSpinbox", "fieldbackground")
    assert ("active", app.COLORS["accent"]) in style.map(
        "Modern.TSpinbox", "arrowcolor"
    )
    assert style.lookup("Field.TLabel", "font")
    assert style.lookup("MatchStats.TLabel", "padding")
    assert style.lookup("Modern.Vertical.TScrollbar", "troughcolor")
    assert style.lookup("Modern.Horizontal.TProgressbar", "troughcolor")


def test_main_window_loads_project_icon_for_window_and_header(tk_window):
    app = BatchRenameApp(tk_window)

    assert app._app_icon is not None
    assert app.brand_icon_label.cget("image")
