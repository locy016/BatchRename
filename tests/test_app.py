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
    clamp_floating_panel_position,
    centered_dialog_geometry,
    directory_inventory_view,
    directory_scope_text,
    layout_mode_for_size,
    layout_mode_for_width,
    floating_panel_position,
    result_icon_spec,
    result_parent_text,
    sorted_preview_items,
    summarize_candidates,
    theme_palette,
)
from batch_rename.examples import REGEX_EXAMPLES
from batch_rename.models import (
    CandidateStatus,
    ExecutionResult,
    ItemKind,
    MatchedItem,
    MatchResult,
    RenameCandidate,
    ScanResult,
)
from batch_rename.preferences import AppPreferences, load_preferences, save_preferences


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


def test_app_loads_requested_appearance_without_touching_real_user_settings(
    tk_window, tmp_path
):
    preferences_path = tmp_path / "settings.json"
    save_preferences(AppPreferences(appearance="dark"), preferences_path)

    app = BatchRenameApp(
        tk_window,
        preferences_path=preferences_path,
        system_light_provider=lambda: True,
    )
    assert app.requested_appearance == "dark"
    assert app.resolved_appearance == "dark"
    assert app.preferences_path == preferences_path
    assert str(app.file_menu.cget("background")) == theme_palette("dark")["card"]
    assert app.regex_template_list.cget("background") == theme_palette("dark")["input"]


def test_floating_panel_position_aligns_with_trigger_and_stays_in_workspace():
    assert floating_panel_position(
        workspace_size=(1100, 700),
        panel_size=(620, 460),
        trigger_bounds=(12, 640, 280, 36),
        margin=12,
    ) == (304, 228)


def test_floating_panel_position_clamps_dragged_coordinates():
    assert clamp_floating_panel_position(
        requested=(-40, 900),
        workspace_size=(1100, 700),
        panel_size=(620, 460),
        margin=12,
    ) == (12, 228)


def test_modern_theme_palettes_define_complete_light_and_dark_tokens():
    required = {
        "background",
        "card",
        "surface_alt",
        "sidebar",
        "text",
        "muted",
        "border",
        "accent",
        "accent_hover",
        "selection",
        "input",
        "disabled",
        "ready",
        "warning",
        "blocked",
        "tooltip",
        "final_action",
        "on_accent",
    }

    light = theme_palette("light")
    dark = theme_palette("dark")

    assert required <= light.keys()
    assert required <= dark.keys()
    assert light["background"] != dark["background"]
    assert light["text"] != dark["text"]
    assert light["accent"] != dark["accent"]


def test_switching_appearance_repaints_in_place_and_preserves_workflow_state(
    tk_window, tmp_path
):
    preferences_path = tmp_path / "settings.json"
    app = BatchRenameApp(
        tk_window,
        preferences_path=preferences_path,
        system_light_provider=lambda: True,
    )
    search_var = app.search_var
    replacement_var = app.replacement_var
    matches = match_result()
    preview = scan_result()
    app.search_var.set("项目")
    app.replacement_var.set("客户")
    app._last_matches = matches
    app._last_scan = preview

    app.set_appearance("dark")

    assert app.requested_appearance == "dark"
    assert app.resolved_appearance == "dark"
    assert app.appearance_var.get() == "dark"
    assert load_preferences(preferences_path).appearance == "dark"
    assert app.search_var is search_var and app.search_var.get() == "项目"
    assert app.replacement_var is replacement_var and app.replacement_var.get() == "客户"
    assert app._last_matches is matches
    assert app._last_scan is preview
    assert tk_window.cget("background") == theme_palette("dark")["background"]
    assert ttk.Style(tk_window).lookup("Treeview", "background") == theme_palette("dark")["card"]
    assert ttk.Style(tk_window).lookup("TLabel", "background") == theme_palette("dark")["background"]
    assert (
        ttk.Style(tk_window).lookup("WorkflowFinal.TButton", "background")
        == theme_palette("dark")["final_action"]
    )
    assert (
        ttk.Style(tk_window).lookup("WorkflowFinal.TButton", "foreground")
        == theme_palette("dark")["on_accent"]
    )
    assert (
        ttk.Style(tk_window).lookup("Modern.TCombobox", "background")
        == theme_palette("dark")["surface_alt"]
    )
    assert (
        ttk.Style(tk_window).lookup("Modern.TSpinbox", "background")
        == theme_palette("dark")["surface_alt"]
    )
    assert (
        ttk.Style(tk_window).lookup(
            "Accent.TButton", "background", ("disabled",)
        )
        == theme_palette("dark")["disabled"]
    )
    assert app.new_name_overlay.background == theme_palette("dark")["card"]
    assert app.result_icon_overlay.background == theme_palette("dark")["card"]


def test_follow_system_rechecks_resolved_theme_without_changing_requested_mode(
    tk_window, tmp_path
):
    system = {"light": True}
    app = BatchRenameApp(
        tk_window,
        preferences_path=tmp_path / "settings.json",
        system_light_provider=lambda: system["light"],
    )
    app.set_appearance("system")
    assert app.resolved_appearance == "light"

    system["light"] = False
    app._refresh_system_appearance()

    assert app.requested_appearance == "system"
    assert app.appearance_var.get() == "system"
    assert app.resolved_appearance == "dark"


@pytest.mark.parametrize(
    ("mode", "depth", "expected"),
    [("all", 1, "全部层级"), ("limited", 3, "最多 3 层")],
)
def test_directory_scope_text_explains_the_current_traversal_depth(
    mode, depth, expected
):
    assert directory_scope_text(mode, depth) == expected


def test_directory_inventory_view_has_idle_scanning_and_completed_states():
    idle = directory_inventory_view(None)
    scanning = directory_inventory_view(None, scanning=True)
    completed = directory_inventory_view(
        MatchResult(
            root=Path("C:/root"),
            search="项目",
            use_regex=False,
            scanned_directory_count=12,
            scanned_file_count=34,
            errors=["无法读取一", "无法读取二"],
        )
    )

    assert (idle.folder_count, idle.file_count, idle.state, idle.warning) == (
        "—",
        "—",
        "尚未扫描",
        "",
    )
    assert scanning.state == "正在统计"
    assert (completed.folder_count, completed.file_count) == ("12", "34")
    assert completed.state == "扫描完成"
    assert completed.warning == "2 处无法读取"


def test_app_keeps_directory_context_in_separate_display_variables(tk_window):
    app = BatchRenameApp(tk_window)
    snapshot = MatchResult(
        root=Path("C:/资料"),
        search="项目",
        use_regex=False,
        scanned_directory_count=7,
        scanned_file_count=19,
    )

    app._set_directory_inventory(snapshot)

    assert app.directory_context_path_var.get() == str(snapshot.root)
    assert app.directory_context_scope_var.get() == "全部层级"
    assert app.directory_folder_count_var.get() == "7"
    assert app.directory_file_count_var.get() == "19"
    assert app.directory_inventory_state_var.get() == "扫描完成"


def test_directory_inventory_survives_rule_changes_but_resets_for_scope_changes(
    tk_window,
):
    app = BatchRenameApp(tk_window)
    snapshot = MatchResult(
        root=Path(app.directory_var.get()),
        search="项目",
        use_regex=False,
        scanned_directory_count=4,
        scanned_file_count=9,
    )
    app._set_directory_inventory(snapshot)

    app.search_var.set("合同")
    assert app.directory_folder_count_var.get() == "4"
    assert app.directory_file_count_var.get() == "9"

    app.depth_mode_var.set("limited")
    assert app.directory_folder_count_var.get() == "—"
    assert app.directory_file_count_var.get() == "—"
    assert app.directory_inventory_state_var.get() == "尚未扫描"


@pytest.mark.parametrize(
    ("work_area", "screen_kind", "size", "geometry", "layout_mode"),
    [
        ((0, 0, 1920, 1080), "standard", (1120, 720), "1120x720+400+180", "standard"),
        ((0, 0, 2560, 1440), "standard", (1280, 720), "1280x720+640+360", "standard"),
        ((0, 0, 3840, 2160), "standard", (1920, 1080), "1920x1080+960+540", "spacious"),
        ((0, 0, 3440, 1440), "ultrawide", (1582, 979), "1582x979+929+230", "spacious"),
        ((0, 0, 5120, 1440), "ultrawide", (1664, 979), "1664x979+1728+230", "spacious"),
        ((0, 0, 1080, 1920), "portrait", (1120, 1288), "1120x1288+0+316", "compact"),
        ((0, 0, 1440, 2560), "portrait", (1296, 1490), "1296x1490+72+535", "compact"),
        ((0, 0, 2160, 3840), "portrait", (1944, 2236), "1944x2236+108+802", "compact"),
        ((-2560, 0, 0, 1440), "standard", (1280, 720), "1280x720+-1920+360", "standard"),
        ((100, 50, 900, 650), "standard", (1120, 720), "1120x720+100+50", "standard"),
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
        ((0, 0, 1920, 1080), "1120x720+400+180"),
        ((1920, 0, 5360, 1440), "1582x979+2849+230"),
        ((-1080, 0, 0, 1920), "1120x1288+-1080+316"),
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
    assert tk_window.minsize() == (1120, 720)


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


def test_floating_tool_panel_has_border_and_offset_shadow(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()

    app._toggle_tool_panel("templates")
    tk_window.update()

    assert app.templates_panel.cget("style") == "FloatingPanel.TFrame"
    assert app.templates_panel_shadow.winfo_manager() == "place"
    assert app.templates_panel_shadow.winfo_x() == app.templates_panel.winfo_x() + 6
    assert app.templates_panel_shadow.winfo_y() == app.templates_panel.winfo_y() + 6
    assert app.templates_panel_shadow.winfo_width() == app.templates_panel.winfo_width()
    assert app.templates_panel_shadow.winfo_height() == app.templates_panel.winfo_height()

    app._close_tool_panel()

    assert app.templates_panel_shadow.winfo_manager() == ""


def test_tool_panel_opens_next_to_the_button_that_triggered_it(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()

    app.regex_templates_button.invoke()
    tk_window.update()

    assert app._active_tool_trigger is app.regex_templates_button
    assert (
        app.templates_panel.winfo_rootx()
        >= app.regex_templates_button.winfo_rootx()
        + app.regex_templates_button.winfo_width()
    )


def test_dragging_tool_panel_header_moves_shadow_and_clamps_to_workspace(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()
    app._toggle_tool_panel("settings", trigger=app.settings_tool_button)
    tk_window.update()

    app._start_tool_panel_drag(SimpleNamespace(x_root=400, y_root=500))
    app._drag_tool_panel(SimpleNamespace(x_root=-1000, y_root=-1000))
    app._finish_tool_panel_drag()
    tk_window.update()

    assert app._tool_panel_position == (12, 12)
    assert app.settings_panel.winfo_x() == 12
    assert app.settings_panel.winfo_y() == 12
    assert app.settings_panel_shadow.winfo_x() == 18
    assert app.settings_panel_shadow.winfo_y() == 18


def test_only_tool_panel_header_owns_drag_bindings(tk_window):
    app = BatchRenameApp(tk_window)

    assert app.templates_panel_header.bind("<ButtonPress-1>")
    assert app.templates_panel_title.bind("<ButtonPress-1>")
    assert app.templates_panel_helper.bind("<ButtonPress-1>")
    assert not app.regex_template_list.bind("<ButtonPress-1>")
    assert not app.regex_search_entry.bind("<ButtonPress-1>")


@pytest.mark.parametrize(
    ("size", "mode"),
    [((1120, 720), "standard"), ((1600, 900), "spacious"), ((1120, 1000), "compact")],
)
def test_tool_work_panels_have_roomy_headers_and_stay_inside_workspace(
    tk_window, size, mode
):
    app = BatchRenameApp(tk_window)
    width, height = size
    tk_window.geometry(f"{width}x{height}+0+0")
    tk_window.deiconify()
    tk_window.update()
    app._apply_responsive_layout(width, height)

    app._toggle_tool_panel("templates")
    tk_window.update()

    assert app.current_layout_mode == mode
    assert app.templates_panel_title.cget("text") == "常用正则模板"
    assert "一键应用" in app.templates_panel_helper.cget("text")
    assert app.templates_panel_close.cget("text") == "关闭"
    assert app.templates_panel.winfo_width() >= min(600, app.body_frame.winfo_width() - 96)
    assert app.templates_panel.winfo_height() >= min(420, app.body_frame.winfo_height() - 24)
    assert app.templates_panel.winfo_x() >= 0
    assert app.templates_panel.winfo_y() >= 0
    assert app.templates_panel.winfo_x() + app.templates_panel.winfo_width() <= app.body_frame.winfo_width()
    assert app.templates_panel.winfo_y() + app.templates_panel.winfo_height() <= app.body_frame.winfo_height()
    assert app.regex_template_browser.winfo_width() >= app.templates_panel.winfo_width() * 0.35
    assert app.regex_template_details.winfo_width() >= app.templates_panel.winfo_width() * 0.50

    app.templates_panel_close.invoke()
    assert app.active_tool_panel is None


def test_settings_panel_uses_three_clear_semantic_groups(tk_window):
    app = BatchRenameApp(tk_window)
    tk_window.deiconify()
    tk_window.update()

    app._toggle_tool_panel("settings")
    tk_window.update()

    assert app.settings_panel_title.cget("text") == "扫描与预览设置"
    assert "当前规则" in app.settings_panel_helper.cget("text")
    assert tuple(label.cget("text") for label in app.settings_group_labels) == (
        "扫描范围",
        "处理对象",
        "名称保护",
    )
    group_rectangles = [
        (
            group.winfo_x(),
            group.winfo_y(),
            group.winfo_x() + group.winfo_width(),
            group.winfo_y() + group.winfo_height(),
        )
        for group in app.settings_groups
    ]
    assert all(
        first[3] <= second[1]
        for first, second in zip(group_rectangles, group_rectangles[1:])
    )


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


def test_directory_overview_replaces_the_decorative_brand_header(tk_window):
    app = BatchRenameApp(tk_window)

    assert not hasattr(app, "brand_icon_label")
    assert app.main_content.grid_rowconfigure(0)["weight"] > 0
    assert app.directory_overview.grid_info()["row"] == 0
    assert app.result_card.grid_info()["row"] == 1
    assert app.progress_frame.grid_info()["row"] == 2
    assert app.directory_context_path_label.cget("textvariable") == str(
        app.directory_context_path_var
    )
    assert app.directory_context_scope_label.cget("textvariable") == str(
        app.directory_context_scope_var
    )


def test_match_statistics_are_presented_below_the_result_table(tk_window):
    app = BatchRenameApp(tk_window)

    assert app.stats_footer.master is app.result_card
    assert app.stats_footer.grid_info()["row"] > app.result_tree.grid_info()["row"]
    assert tuple(label.cget("text") for label in app.match_stat_title_labels) == (
        "匹配",
        "可修改",
        "名称未变化",
        "阻止执行",
    )
    assert tuple(variable.get() for variable in app.match_stat_value_vars) == (
        "0",
        "0",
        "0",
        "0",
    )


def test_directory_overview_uses_snapshot_counts_and_keeps_full_path_tooltip(
    tk_window,
):
    app = BatchRenameApp(tk_window)
    snapshot = MatchResult(
        root=Path("C:/非常长的目录/客户资料/2026/待处理"),
        search="项目",
        use_regex=False,
        scanned_directory_count=18,
        scanned_file_count=205,
        errors=["无法读取"],
    )

    app._set_directory_inventory(snapshot)

    assert app.directory_folder_count_var.get() == "18"
    assert app.directory_file_count_var.get() == "205"
    assert app.directory_inventory_warning_var.get() == "1 处无法读取"
    assert app.directory_path_tooltip.text.endswith(r"客户资料\2026\待处理")


def test_top_menu_contains_only_global_commands(tk_window):
    app = BatchRenameApp(tk_window)

    assert menu_labels(app.top_menu) == ("文件", "功能", "视图", "帮助")
    assert menu_labels(app.file_menu) == ("退出",)
    assert menu_labels(app.feature_menu) == (
        "结果详情",
        "撤回管理（开发中）",
        "操作日志（开发中）",
    )
    assert menu_labels(app.help_menu) == ("使用说明", "关于")
    assert menu_labels(app.view_menu) == ("外观",)
    assert menu_labels(app.appearance_menu) == ("跟随系统", "浅色", "深色")
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
        + menu_labels(app.view_menu)
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
    assert "目录概况" in content and "匹配统计" in content
    assert "跟随系统" in content and "深色" in content
    assert "快速开发期" in content
    assert "备份" in content and "自行确认" in content
    assert app.about_email_var.get() == "lo.c@live.cn"
    assert str(app.about_email_entry.cget("state")) == "readonly"
    assert not app.about_email_entry.bind("<Button-1>")
    assert window.winfo_exists()


def test_help_explains_inventory_statistics_work_panels_and_appearance(tk_window):
    app = BatchRenameApp(tk_window)

    app._show_help()

    content = app.help_text
    assert "目录概况" in content
    assert "文件夹总数" in content and "文件总数" in content
    assert "结果表下方" in content and "名称未变化" in content
    assert "40%" in content and "60%" in content
    assert "视图 → 外观" in content
    assert "跟随系统" in content and "浅色" in content and "深色" in content


def test_open_native_text_dialogs_follow_runtime_appearance_switch(tk_window):
    app = BatchRenameApp(tk_window, system_light_provider=lambda: True)
    app._show_help()
    app._last_execution = ExecutionResult()
    app._show_execution_details()

    app.set_appearance("dark", persist=False)

    dark = theme_palette("dark")
    assert app.help_text_widget.cget("background") == dark["card"]
    assert app.execution_details_text.cget("background") == dark["card"]
    assert app.help_text_widget.cget("foreground") == dark["text"]
    assert app.execution_details_text.cget("foreground") == dark["text"]


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


def test_visible_icon_tooltip_closes_before_canvas_is_reused_for_new_row(tk_window):
    app = BatchRenameApp(tk_window)
    source = Path("C:/root/旧项目.txt")
    old_item = RenameCandidate(
        source=source,
        target=source.with_name("新项目.txt"),
        kind=ItemKind.FILE,
        status=CandidateStatus.CONFLICT,
        detail="旧说明",
    )
    app._fill_tree(app.result_tree, [old_item], root=Path("C:/root"))
    tk_window.deiconify()
    tk_window.update()
    app.result_icon_overlay.refresh()
    detail_index = next(
        index
        for index, canvas in enumerate(app.result_icon_overlay._canvases)
        if getattr(canvas, "_tree_column", "") == "detail"
    )
    tooltip = app.result_icon_overlay._tooltips[detail_index]
    tooltip._show()
    assert tooltip.window is not None
    assert tooltip.window.winfo_children()[0].cget("text") == "说明\n旧说明"

    new_source = Path("C:/root/新项目.txt")
    new_item = RenameCandidate(
        source=new_source,
        target=new_source.with_name("归档项目.txt"),
        kind=ItemKind.FILE,
        status=CandidateStatus.READY,
        detail="新说明",
    )
    app._fill_tree(app.result_tree, [new_item], root=Path("C:/root"))
    tk_window.update()
    app.result_icon_overlay.refresh()

    assert tooltip.window is None
    assert tooltip.text == "说明\n新说明"


def test_status_and_detail_icons_select_rows_and_refresh_one_details_dialog(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )
    first_source = Path("C:/root/合同/2026/清单.xlsx")
    first = RenameCandidate(
        source=first_source,
        target=first_source.with_name("归档-清单.xlsx"),
        kind=ItemKind.FILE,
        status=CandidateStatus.READY,
        detail="规则匹配有效，可以执行重命名。",
    )
    second_source = Path("C:/root/合同/重复.xlsx")
    second = RenameCandidate(
        source=second_source,
        target=second_source.with_name("清单.xlsx"),
        kind=ItemKind.FILE,
        status=CandidateStatus.CONFLICT,
        detail="目标名称已经存在，程序不会覆盖。",
    )
    app._fill_tree(app.result_tree, [first, second], root=Path("C:/root"))
    tk_window.deiconify()
    tk_window.update()
    app.result_icon_overlay.refresh()

    rows = app.result_tree.get_children()
    assert app._result_row_details[rows[0]] == {
        "kind": "文件",
        "parent": r"合同\2026",
        "old": "清单.xlsx",
        "new": "归档-清单.xlsx",
        "status": "可修改",
        "detail": "规则匹配有效，可以执行重命名。",
    }

    first_status = next(
        canvas
        for canvas in app.result_icon_overlay._canvases
        if getattr(canvas, "_tree_item_id", "") == rows[0]
        and getattr(canvas, "_tree_column", "") == "status"
    )
    app.result_icon_overlay._activate(first_status)
    tk_window.update()

    details_window = app.dialogs.windows["result-item-details"]
    assert app.result_tree.selection() == (rows[0],)
    assert app.result_item_detail_vars["focus"].get().startswith("状态：可修改")
    assert tuple(
        variable.get() for key, variable in app.result_item_detail_vars.items() if key != "focus"
    ) == (
        "文件",
        r"合同\2026",
        "清单.xlsx",
        "归档-清单.xlsx",
        "可修改",
        "规则匹配有效，可以执行重命名。",
    )

    second_detail = next(
        canvas
        for canvas in app.result_icon_overlay._canvases
        if getattr(canvas, "_tree_item_id", "") == rows[1]
        and getattr(canvas, "_tree_column", "") == "detail"
    )
    app.result_icon_overlay._activate(second_detail)
    tk_window.update()

    assert app.dialogs.windows["result-item-details"] is details_window
    assert app.result_tree.selection() == (rows[1],)
    assert app.result_item_detail_vars["focus"].get().startswith("说明：")
    assert app.result_item_detail_vars["status"].get() == CandidateStatus.CONFLICT.value
    assert app.result_item_detail_vars["detail"].get() == "目标名称已经存在，程序不会覆盖。"


def test_type_icon_selects_the_row_without_opening_details(tk_window):
    app = BatchRenameApp(tk_window)
    app._fill_tree(
        app.result_tree,
        [candidate("资料", ItemKind.DIRECTORY)],
        root=Path("C:/root"),
    )
    tk_window.deiconify()
    tk_window.update()
    app.result_icon_overlay.refresh()
    type_icon = next(
        canvas
        for canvas in app.result_icon_overlay._canvases
        if getattr(canvas, "_tree_column", "") == "kind"
    )

    app.result_icon_overlay._activate(type_icon)

    assert app.result_tree.selection() == (app.result_tree.get_children()[0],)
    assert "result-item-details" not in app.dialogs.windows


def test_default_layout_uses_content_sized_minimum_and_expands_the_result_area(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    tk_window.update_idletasks()

    assert tk_window.geometry().startswith("1120x720")
    assert tk_window.minsize() == (1120, 720)
    assert tk_window.winfo_reqwidth() <= 1120
    assert tk_window.winfo_reqheight() <= 720
    assert int(app.result_tree.cget("height")) >= 10
    assert app.main_content.grid_rowconfigure(0)["weight"] > 0
    assert app.result_workspace.grid_rowconfigure(1)["weight"] > 0
    assert app.result_card.grid_rowconfigure(1)["weight"] > 0


@pytest.mark.parametrize(
    ("width", "mode", "rail_width"),
    [(960, "compact", 64), (1280, "standard", 288), (1600, "spacious", 304)],
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
        tk_window, work_area_provider=lambda _root: (0, 0, 1080, 1920)
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


def test_left_workflow_is_ordered_and_statistics_keep_complete_values(tk_window):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 2560, 1440)
    )

    assert app.preview_limit_var.get() == 100
    assert app.stats_var.get() == (
        "匹配：0项 | 可修改：0项 | 名称未变化：0项 | 阻止执行：0项"
    )
    assert tuple(variable.get() for variable in app.match_stat_value_vars) == (
        "0",
        "0",
        "0",
        "0",
    )

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
    assert app.RAIL_WIDTHS == {"compact": 64, "standard": 288, "spacious": 304}
    assert int(app.workflow_rail.cget("width")) == 288


@pytest.mark.parametrize("scaling", [1.0, 1.5, 2.0])
def test_workflow_actions_and_tools_use_full_width_comfortable_layout(
    tk_window, scaling
):
    previous_scaling = float(tk_window.tk.call("tk", "scaling"))
    try:
        tk_window.tk.call("tk", "scaling", scaling)
        app = BatchRenameApp(
            tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
        )
        tk_window.deiconify()
        tk_window.update()

        assert int(app.workflow_rail.cget("width")) == 288
        action_heights = {
            button.winfo_reqheight()
            for button in (
                app.directory_select_button,
                app.search_button,
                app.preview_button,
                app.execute_button,
            )
        }
        assert len(action_heights) == 1
        assert action_heights.pop() >= 30
        assert not hasattr(app, "tools_footer_label")
        assert app.regex_templates_button.grid_info()["column"] == 0
        assert app.settings_tool_button.grid_info()["column"] == 0
        assert app.regex_templates_button.grid_info()["columnspan"] == 2
        assert app.settings_tool_button.grid_info()["columnspan"] == 2
        assert (
            app.regex_templates_button.grid_info()["row"]
            < app.settings_tool_button.grid_info()["row"]
        )
        expected_width = app.workflow_rail.winfo_width() - 24
        assert app.regex_templates_button.winfo_width() >= expected_width
        assert app.settings_tool_button.winfo_width() >= expected_width
    finally:
        tk_window.tk.call("tk", "scaling", previous_scaling)


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
        assert app.stats_footer.winfo_width() >= app.stats_footer.winfo_reqwidth()
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
    app._apply_responsive_layout(1000, 800)
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


def test_result_table_reserves_border_space_so_horizontal_scrollbar_stays_hidden(
    tk_window,
):
    app = BatchRenameApp(
        tk_window, work_area_provider=lambda _root: (0, 0, 1920, 1080)
    )
    app._fill_tree(
        app.result_tree,
        [candidate("项目说明.txt", ItemKind.FILE)],
        root=Path("C:/root"),
    )
    tk_window.deiconify()
    tk_window.update()

    assert app.result_horizontal_scrollbar.winfo_manager() == ""


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
    assert all(
        label.cget("style") == "MatchStatTitle.TLabel"
        for label in app.match_stat_title_labels
    )
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


def test_main_window_loads_project_icon_without_a_decorative_header(tk_window):
    app = BatchRenameApp(tk_window)

    assert app._app_icon is not None
    assert app._header_icon is not None
    assert not hasattr(app, "brand_icon_label")
