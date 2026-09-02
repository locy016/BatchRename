from pathlib import Path
from types import SimpleNamespace
import time
import tkinter as tk
from tkinter import ttk

import main
import pytest
from batch_rename.app import (
    AutoHideScrollbar,
    BatchRenameApp,
    ManagedDialogs,
    _tree_cell_content,
    calculate_result_column_widths,
    calculate_window_layout,
    centered_dialog_geometry,
    layout_mode_for_size,
    layout_mode_for_width,
    result_icon_spec,
    result_parent_text,
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


@pytest.mark.parametrize(
    ("work_area", "screen_kind", "size", "geometry", "layout_mode"),
    [
        ((0, 0, 1920, 1080), "standard", (960, 680), "960x680+480+200", "compact"),
        ((0, 0, 2560, 1440), "standard", (1280, 720), "1280x720+640+360", "standard"),
        ((0, 0, 3840, 2160), "standard", (1920, 1080), "1920x1080+960+540", "spacious"),
        ((0, 0, 3440, 1440), "ultrawide", (1582, 979), "1582x979+929+230", "spacious"),
        ((0, 0, 5120, 1440), "ultrawide", (1664, 979), "1664x979+1728+230", "spacious"),
        ((0, 0, 1080, 1920), "portrait", (972, 1118), "972x1118+54+401", "compact"),
        ((0, 0, 1440, 2560), "portrait", (1296, 1490), "1296x1490+72+535", "compact"),
        ((0, 0, 2160, 3840), "portrait", (1944, 2236), "1944x2236+108+802", "compact"),
        ((-2560, 0, 0, 1440), "standard", (1280, 720), "1280x720+-1920+360", "standard"),
        ((100, 50, 900, 650), "standard", (960, 680), "960x680+100+50", "compact"),
    ],
)
def test_window_layout_classifies_and_centers_on_the_selected_work_area(
    work_area, screen_kind, size, geometry, layout_mode
):
    layout = calculate_window_layout(work_area)

    assert layout.screen_kind == screen_kind
    assert layout.size == size
    assert layout.geometry == geometry
    assert layout.layout_mode == layout_mode


@pytest.mark.parametrize(
    ("width", "expected"),
    [(960, "compact"), (1119, "compact"), (1120, "standard"), (1439, "standard"), (1440, "spacious")],
)
def test_layout_mode_uses_confirmed_client_width_breakpoints(width, expected):
    assert layout_mode_for_width(width) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [((1600, 800), "spacious"), ((1280, 800), "standard"), ((1600, 1800), "compact")],
)
def test_layout_mode_keeps_portrait_windows_compact_even_when_they_are_wide(
    size, expected
):
    assert layout_mode_for_size(*size) == expected


@pytest.mark.parametrize(
    ("total_width", "mode"),
    [(720, "compact"), (980, "standard"), (1440, "spacious")],
)
def test_result_column_widths_keep_icon_columns_narrow_and_names_flexible(
    total_width, mode
):
    widths = calculate_result_column_widths(total_width, mode)

    assert widths["kind"] == 44
    assert widths["status"] == 48
    assert widths["detail"] == 44
    assert widths["new"] > widths["old"] > widths["parent"]
    assert sum(widths.values()) == total_width
    assert all(width > 0 for width in widths.values())


def test_result_column_widths_scale_elastic_columns_below_preferred_minimums():
    widths = calculate_result_column_widths(420, "compact")

    assert sum(widths.values()) == 420
    assert widths["new"] > widths["old"] > widths["parent"] > 0


def test_result_icon_specs_distinguish_file_and_directory_without_status_color():
    directory = result_icon_spec("kind", ItemKind.DIRECTORY.value)
    file = result_icon_spec("kind", ItemKind.FILE.value)

    assert directory.shape == "folder"
    assert file.shape == "file"
    assert directory.color == file.color
    assert directory.tooltip == "类型\n文件夹"
    assert directory.actionable is False


@pytest.mark.parametrize(
    ("status", "shape", "color_name"),
    [
        (CandidateStatus.READY.value, "check", "ready"),
        (CandidateStatus.UNCHANGED.value, "minus", "warning"),
        ("等待结果预览", "clock", "pending"),
        (CandidateStatus.CONFLICT.value, "warning", "blocked"),
        ("未知状态", "warning", "blocked"),
    ],
)
def test_result_status_icon_specs_use_semantic_shape_and_color(
    status, shape, color_name
):
    spec = result_icon_spec("status", status)

    assert spec.shape == shape
    assert spec.color_name == color_name
    assert spec.tooltip == f"状态\n{status}"
    assert spec.actionable is True


def test_result_detail_icon_keeps_complete_explanation_for_hover_and_click():
    detail = "目标名称已经存在，程序不会覆盖。"

    spec = result_icon_spec("detail", detail)

    assert spec.shape == "info"
    assert spec.tooltip == f"说明\n{detail}"
    assert spec.actionable is True


def test_app_applies_calculated_result_widths_without_rebuilding_the_tree(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    result_tree = app.result_tree

    app._apply_result_column_widths(980)

    assert app.result_tree is result_tree
    assert {
        column: int(app.result_tree.column(column, "width"))
        for column in app.result_tree["columns"]
    } == calculate_result_column_widths(980, app.current_layout_mode)


@pytest.mark.parametrize(
    ("work_area", "geometry"),
    [
        ((0, 0, 1920, 1080), "960x680+480+200"),
        ((1920, 0, 5360, 1440), "1582x979+2849+230"),
        ((-1080, 0, 0, 1920), "972x1118+-1026+401"),
    ],
)
def test_app_uses_injected_pointer_monitor_work_area_for_initial_geometry(
    tk_window, work_area, geometry
):
    provider_calls = []

    app = BatchRenameApp(
        tk_window,
        work_area_provider=lambda root: provider_calls.append(root) or work_area,
    )
    tk_window.update_idletasks()

    assert provider_calls == [tk_window]
    assert app.initial_window_layout.geometry == geometry
    assert tk_window.geometry() == geometry
    assert tk_window.minsize() == (960, 680)


def test_preview_combines_categories_and_uses_natural_name_order():
    items = [
        candidate("文件10.txt", ItemKind.FILE),
        candidate("目录10", ItemKind.DIRECTORY),
        candidate("文件2.txt", ItemKind.FILE),
        candidate("目录2", ItemKind.DIRECTORY),
    ]

    preview = sorted_preview_items(items, limit=3)

    assert [item.old_name for item in preview] == ["目录2", "目录10", "文件2.txt"]


@pytest.mark.parametrize(
    ("root", "source", "expected"),
    [
        (Path("C:/资料"), Path("C:/资料/合同.docx"), "（根目录）"),
        (Path("C:/资料"), Path("C:/资料/合同/2026/清单.xlsx"), r"合同\2026"),
        (Path("C:/资料"), Path("D:/外部/清单.xlsx"), str(Path("D:/外部"))),
    ],
)
def test_result_parent_text_is_relative_to_the_selected_root(
    root, source, expected
):
    assert result_parent_text(root, source) == expected


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
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

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
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

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


def test_open_template_panel_is_locked_during_background_work(tk_window):
    app = BatchRenameApp(tk_window)
    app._toggle_tool_panel("templates")

    app._set_busy(True)

    assert str(app.regex_category_selector.cget("state")) == "disabled"
    assert str(app.regex_template_list.cget("state")) == "disabled"
    assert app.regex_apply_button.instate(["disabled"])


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
    app.result_tree.event_generate("<Button-1>", x=10, y=10)
    tk_window.update()
    assert app.active_tool_panel is None

    app._toggle_tool_panel("settings")
    app.progress.event_generate("<Button-1>", x=10, y=5)
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

    app._fill_tree(app.result_tree, [item], root=Path("C:/root"))

    row = app.result_tree.get_children()[0]
    assert app.result_tree.item(row, "values") == (
        "文件",
        "（根目录）",
        "文件2.txt",
        "新-文件2.txt",
        "可修改",
        "",
    )


def test_new_name_column_uses_a_dedicated_accent_text_overlay(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()

    app._fill_tree(
        app.result_tree,
        [candidate("文件2.txt", ItemKind.FILE)],
        root=Path("C:/root"),
    )
    tk_window.update()

    visible_labels = app.new_name_overlay.visible_labels
    assert len(visible_labels) == 1
    assert visible_labels[0].cget("text") == "新-文件2.txt"
    assert visible_labels[0].cget("foreground") == app.COLORS["accent"]

    app._fill_tree(app.result_tree, [], root=Path("C:/root"))
    tk_window.update()
    assert app.new_name_overlay.visible_labels == ()


def test_result_icon_overlay_covers_visible_type_status_and_detail_cells(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    items = [
        candidate("目录", ItemKind.DIRECTORY, CandidateStatus.READY),
        candidate("无变化.txt", ItemKind.FILE, CandidateStatus.UNCHANGED),
        candidate("冲突.txt", ItemKind.FILE, CandidateStatus.CONFLICT),
    ]
    app._fill_tree(app.result_tree, items, root=Path("C:/root"))
    tk_window.deiconify()
    tk_window.update()

    app.result_icon_overlay.refresh()

    icon_data = app.result_icon_overlay.visible_icon_data
    assert len(icon_data) == 9
    assert {column for _item_id, column, _shape, _tooltip in icon_data} == {
        "kind",
        "status",
        "detail",
    }
    assert {shape for _item_id, _column, shape, _tooltip in icon_data} >= {
        "folder",
        "file",
        "check",
        "minus",
        "warning",
        "info",
    }
    assert any(tooltip == "状态\n名称未变化" for *_rest, tooltip in icon_data)

    app._fill_tree(app.result_tree, [], root=Path("C:/root"))
    tk_window.update()
    app.result_icon_overlay.refresh()
    assert app.result_icon_overlay.visible_icon_data == ()


def test_default_layout_fits_960_by_680_and_expands_the_result_area(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    tk_window.update_idletasks()

    assert tk_window.geometry().startswith("960x680")
    assert tk_window.minsize() == (960, 680)
    assert tk_window.winfo_reqwidth() <= 960
    assert tk_window.winfo_reqheight() <= 680
    assert int(app.result_tree.cget("height")) >= 10
    assert app.main_content.grid_rowconfigure(1)["weight"] > 0
    assert app.result_workspace.grid_rowconfigure(1)["weight"] > 0
    assert app.result_card.grid_rowconfigure(1)["weight"] > 0


@pytest.mark.parametrize(
    ("width", "mode", "rail_width"),
    [(960, "compact", 64), (1280, "standard", 270), (1600, "spacious", 300)],
)
def test_responsive_modes_resize_the_rail_and_apply_result_column_policies(
    tk_window, width, mode, rail_width
):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

    app._apply_responsive_layout(width, 800)

    assert app.current_layout_mode == mode
    assert int(app.workflow_rail.cget("width")) == rail_width
    assert {
        column: int(app.result_tree.column(column, "width"))
        for column in app.result_tree["columns"]
    } == calculate_result_column_widths(width - rail_width - 64, mode)
    for essential_column in ("kind", "old", "new", "status"):
        assert int(app.result_tree.column(essential_column, "width")) > 0


def test_type_column_keeps_a_fixed_compact_icon_width_at_high_dpi(tk_window):
    previous_scaling = float(tk_window.tk.call("tk", "scaling"))
    try:
        tk_window.tk.call("tk", "scaling", 2.0)
        app = BatchRenameApp(
            tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
        )
        assert int(app.result_tree.column("kind", "width")) == 44
    finally:
        tk_window.tk.call("tk", "scaling", previous_scaling)


def test_responsive_mode_transitions_keep_rule_widgets_and_state_instances(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    search_entry = app.search_entry
    replacement_entry = app.replacement_entry
    search_var = app.search_var
    replacement_var = app.replacement_var
    app.search_var.set("项目")
    app.replacement_var.set("归档")

    for width in (960, 1280, 1600, 960):
        app._apply_responsive_layout(width, 800)

    assert app.search_entry is search_entry
    assert app.replacement_entry is replacement_entry
    assert app.search_var is search_var
    assert app.replacement_var is replacement_var
    assert (app.search_var.get(), app.replacement_var.get()) == ("项目", "归档")


def test_configure_debounce_applies_only_the_latest_window_size(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    applied_sizes = []
    app._apply_responsive_layout = lambda width, height: applied_sizes.append(
        (width, height)
    )

    for width in (1000, 1200, 1500):
        app._schedule_responsive_layout(
            SimpleNamespace(widget=tk_window, width=width, height=800)
        )
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline and not applied_sizes:
        tk_window.update()

    assert applied_sizes == [(1500, 800)]


def test_destroying_window_removes_pending_responsive_callback(
    tk_window, tk_session_root
):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    applied_sizes = []
    app._apply_responsive_layout = lambda width, height: applied_sizes.append(
        (width, height)
    )
    app._schedule_responsive_layout(
        SimpleNamespace(widget=tk_window, width=1500, height=800)
    )
    callback_id = app._responsive_after_id

    tk_window.destroy()
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        tk_session_root.update()

    assert callback_id not in tk_session_root.tk.call("after", "info")
    assert applied_sizes == []


def test_compact_navigation_reuses_the_workflow_rail_as_a_drawer(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    search_entry = app.search_entry
    tk_window.deiconify()
    tk_window.update()

    assert app.compact_navigation.winfo_manager() == "grid"
    assert app.workflow_rail.winfo_manager() == ""

    app.workflow_nav_button.invoke()
    tk_window.update()
    assert app.workflow_drawer_open is True
    assert app.workflow_rail.winfo_manager() == "place"
    assert app.search_entry is search_entry

    app.workflow_nav_button.invoke()
    assert app.workflow_drawer_open is False
    assert app.workflow_rail.winfo_manager() == ""


def test_compact_drawer_closes_from_escape_result_click_and_other_tools(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    tk_window.deiconify()
    tk_window.update()

    app.workflow_nav_button.invoke()
    tk_window.focus_force()
    tk_window.update()
    tk_window.event_generate("<Escape>")
    tk_window.update()
    assert app.workflow_drawer_open is False

    app.workflow_nav_button.invoke()
    app.result_tree.event_generate("<Button-1>", x=10, y=10)
    tk_window.update()
    assert app.workflow_drawer_open is False

    app.workflow_nav_button.invoke()
    app.compact_templates_button.invoke()
    tk_window.update()
    assert app.workflow_drawer_open is False
    assert app.active_tool_panel == "templates"

    app.workflow_nav_button.invoke()
    app.compact_settings_button.invoke()
    tk_window.update()
    assert app.workflow_drawer_open is False
    assert app.active_tool_panel == "settings"


def test_leaving_compact_mode_restores_full_rail_and_keeps_preview_state(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    app.search_var.set("项目")
    app.replacement_var.set("归档")
    app._last_matches = match_result()
    app._last_scan = scan_result()
    app.workflow_nav_button.invoke()

    app._apply_responsive_layout(1280, 800)

    assert app.current_layout_mode == "standard"
    assert app.workflow_drawer_open is False
    assert app.compact_navigation.winfo_manager() == ""
    assert app.workflow_rail.winfo_manager() == "grid"
    assert app.search_var.get() == "项目"
    assert app.replacement_var.get() == "归档"
    assert app._last_matches is not None
    assert app._last_scan is not None


def test_tall_high_resolution_window_uses_compact_navigation(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

    app._apply_responsive_layout(1600, 1800)

    assert app.current_layout_mode == "compact"
    assert app.compact_navigation.winfo_manager() == "grid"
    assert app.workflow_rail.winfo_manager() == ""


def test_left_workflow_is_ordered_and_statistics_stay_on_one_line(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

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


@pytest.mark.parametrize("scaling", [1.0, 1.5, 2.0])
def test_bottom_tool_buttons_fit_inside_960_by_680_workflow_rail(tk_window, scaling):
    previous_scaling = float(tk_window.tk.call("tk", "scaling"))
    try:
        tk_window.tk.call("tk", "scaling", scaling)
        app = BatchRenameApp(
            tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
        )
        tk_window.deiconify()
        tk_window.update()
        app.workflow_nav_button.invoke()
        tk_window.update()

        for button in (app.regex_templates_button, app.settings_tool_button):
            assert button.winfo_ismapped()
            assert button.winfo_y() + button.winfo_height() <= app.workflow_rail.winfo_height()
        assert app.workflow_rail.winfo_x() + app.workflow_rail.winfo_width() <= app.body_frame.winfo_width()
        assert app.workflow_rail.winfo_y() + app.workflow_rail.winfo_height() <= app.body_frame.winfo_height()
        assert app.stats_label.winfo_width() >= app.stats_label.winfo_reqwidth()
        app._toggle_tool_panel("templates")
        tk_window.update()
        assert (
            app.templates_panel.winfo_y() + app.templates_panel.winfo_height()
            <= app.body_frame.winfo_height()
        )
        assert (
            app.regex_apply_button.winfo_rooty() + app.regex_apply_button.winfo_height()
            <= app.templates_panel.winfo_rooty() + app.templates_panel.winfo_height()
        )
        assert app.templates_panel.winfo_x() + app.templates_panel.winfo_width() <= app.body_frame.winfo_width()
        app._toggle_tool_panel("settings")
        tk_window.update()
        assert app.settings_panel.winfo_x() + app.settings_panel.winfo_width() <= app.body_frame.winfo_width()
        assert app.settings_panel.winfo_y() + app.settings_panel.winfo_height() <= app.body_frame.winfo_height()
    finally:
        tk_window.tk.call("tk", "scaling", previous_scaling)


def test_busy_compact_workflow_can_close_but_cannot_be_reopened(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    app.workflow_nav_button.invoke()
    assert app.workflow_drawer_open is True

    app._set_busy(True)
    app.workflow_nav_button.invoke()
    assert app.workflow_drawer_open is False

    app.workflow_nav_button.invoke()
    assert app.workflow_drawer_open is False


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
