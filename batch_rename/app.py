"""Tkinter 图形界面。"""

from __future__ import annotations

import os
import queue
import re
import sys
import threading
import tkinter as tk
import ctypes
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Callable, Iterable

from . import __version__
from .core import (
    RenameRule,
    RuleError,
    ScanError,
    build_preview,
    execute,
    search_matches,
)
from .examples import REGEX_EXAMPLES, RegexExample
from .models import (
    CandidateStatus,
    ExecutionRecord,
    ExecutionResult,
    ItemKind,
    MatchedItem,
    MatchOptions,
    MatchResult,
    RenameCandidate,
    ScanResult,
)


MIN_WINDOW_WIDTH = 960
MIN_WINDOW_HEIGHT = 680


def layout_mode_for_width(width: int) -> str:
    """根据主窗口客户区宽度返回响应式布局档位。"""

    if width >= 1440:
        return "spacious"
    if width >= 1120:
        return "standard"
    return "compact"


@dataclass(frozen=True, slots=True)
class WindowLayout:
    """一次初始窗口布局计算的不可变结果。"""

    screen_kind: str
    width: int
    height: int
    x: int
    y: int
    layout_mode: str

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def geometry(self) -> str:
        return f"{self.width}x{self.height}+{self.x}+{self.y}"


def calculate_window_layout(work_area: tuple[int, int, int, int]) -> WindowLayout:
    """按显示器工作区分类并计算居中的初始窗口布局。"""

    left, top, right, bottom = work_area
    work_width = max(1, right - left)
    work_height = max(1, bottom - top)
    ratio = work_width / work_height

    if ratio < 1.15:
        screen_kind = "portrait"
        width = max(MIN_WINDOW_WIDTH, round(work_width * 0.90))
        height = max(
            MIN_WINDOW_HEIGHT,
            min(round(work_height * 0.68), round(width * 1.15)),
        )
    elif ratio > 2.0:
        screen_kind = "ultrawide"
        height = max(MIN_WINDOW_HEIGHT, round(work_height * 0.68))
        width = max(
            MIN_WINDOW_WIDTH,
            min(round(work_width * 0.46), round(height * 1.70)),
        )
    else:
        screen_kind = "standard"
        width = max(MIN_WINDOW_WIDTH, round(work_width * 0.50))
        height = max(MIN_WINDOW_HEIGHT, round(work_height * 0.50))

    if work_width >= MIN_WINDOW_WIDTH:
        width = min(width, work_width)
    if work_height >= MIN_WINDOW_HEIGHT:
        height = min(height, work_height)
    x = left if width > work_width else left + (work_width - width) // 2
    y = top if height > work_height else top + (work_height - height) // 2
    return WindowLayout(
        screen_kind=screen_kind,
        width=width,
        height=height,
        x=x,
        y=y,
        layout_mode=layout_mode_for_width(width),
    )


def _natural_name_key(value: str) -> tuple[tuple[int, str | int], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", value)
    )


def sorted_preview_items(
    candidates: Iterable[RenameCandidate], limit: int | None = None
) -> list[RenameCandidate]:
    """按文件夹、文件和自然名称顺序返回统一预览。"""

    items = sorted(
        candidates,
        key=lambda item: (
            0 if item.kind is ItemKind.DIRECTORY else 1,
            _natural_name_key(item.old_name),
            str(item.source.parent).casefold(),
        ),
    )
    return items if limit is None else items[: max(0, limit)]


def summarize_candidates(candidates: Iterable[RenameCandidate]) -> dict[str, int]:
    """返回界面统计所需的分类计数。"""

    items = list(candidates)
    ready_total = sum(item.status is CandidateStatus.READY for item in items)
    unchanged_total = sum(item.status is CandidateStatus.UNCHANGED for item in items)
    return {
        "matched_total": len(items),
        "ready_total": ready_total,
        "unchanged_total": unchanged_total,
        "blocked_total": len(items) - ready_total - unchanged_total,
    }


def centered_dialog_geometry(
    *,
    parent: tuple[int, int, int, int],
    dialog: tuple[int, int],
    work_area: tuple[int, int, int, int],
) -> str:
    """返回以父窗口为中心且限制在当前显示器工作区内的几何参数。"""

    parent_x, parent_y, parent_width, parent_height = parent
    dialog_width, dialog_height = dialog
    left, top, right, bottom = work_area
    width = min(dialog_width, max(1, right - left))
    height = min(dialog_height, max(1, bottom - top))
    x = parent_x + (parent_width - width) // 2
    y = parent_y + (parent_height - height) // 2
    x = min(max(x, left), right - width)
    y = min(max(y, top), bottom - height)
    return f"{width}x{height}+{x}+{y}"


def _monitor_work_area(root: tk.Misc) -> tuple[int, int, int, int]:
    """取得父窗口所在显示器的可用区域，失败时使用 Tk 虚拟桌面。"""

    if sys.platform == "win32":
        try:
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromWindow(root.winfo_id(), 2)
            info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return work.left, work.top, work.right, work.bottom
        except (AttributeError, OSError, tk.TclError):
            pass
    left = root.winfo_vrootx()
    top = root.winfo_vrooty()
    return left, top, left + root.winfo_vrootwidth(), top + root.winfo_vrootheight()


def _pointer_monitor_work_area(root: tk.Misc) -> tuple[int, int, int, int]:
    """取得鼠标指针所在显示器的工作区，失败时回退到 Tk 虚拟桌面。"""

    if sys.platform == "win32":
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            user32 = ctypes.windll.user32
            point = POINT()
            if user32.GetCursorPos(ctypes.byref(point)):
                monitor = user32.MonitorFromPoint(point, 2)
                info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
                if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    work = info.rcWork
                    return work.left, work.top, work.right, work.bottom
        except (AttributeError, OSError, tk.TclError):
            pass
    left = root.winfo_vrootx()
    top = root.winfo_vrooty()
    return left, top, left + root.winfo_vrootwidth(), top + root.winfo_vrootheight()


class ManagedDialogs:
    """统一管理子窗口的单实例、同屏定位、焦点和模态状态。"""

    def __init__(
        self,
        root: tk.Misc,
        *,
        work_area_provider: Callable[[tk.Misc], tuple[int, int, int, int]] = _monitor_work_area,
    ) -> None:
        self.root = root
        self.work_area_provider = work_area_provider
        self.windows: dict[str, tk.Toplevel] = {}

    def open(
        self,
        key: str,
        *,
        title: str,
        size: tuple[int, int],
        build: Callable[[tk.Toplevel], None],
        modal: bool = False,
    ) -> tk.Toplevel:
        existing = self.windows.get(key)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.after_idle(existing.focus_force)
            return existing

        window = tk.Toplevel(self.root)
        window.withdraw()
        window.title(title)
        window.transient(self.root)
        self.windows[key] = window
        window.protocol("WM_DELETE_WINDOW", lambda: self.close(key))
        build(window)
        window.update_idletasks()
        parent = (
            self.root.winfo_rootx(),
            self.root.winfo_rooty(),
            max(1, self.root.winfo_width()),
            max(1, self.root.winfo_height()),
        )
        window.geometry(
            centered_dialog_geometry(
                parent=parent,
                dialog=size,
                work_area=self.work_area_provider(self.root),
            )
        )
        window.deiconify()
        window.lift()
        if modal:
            window.grab_set()
        window.after_idle(window.focus_force)
        return window

    def close(self, key: str) -> None:
        window = self.windows.pop(key, None)
        if window is not None and window.winfo_exists():
            if window.grab_current() == window:
                window.grab_release()
            window.destroy()
        if self.root.winfo_exists():
            self.root.after_idle(self.root.focus_force)


class AutoHideScrollbar(ttk.Scrollbar):
    """内容完全可见时释放网格空间的滚动条。"""

    def set(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            if self.winfo_manager():
                self.grid_remove()
        elif not self.winfo_manager():
            self.grid()
        super().set(first, last)


def _tree_cell_content(
    tree: ttk.Treeview, row_id: str, column_id: str
) -> tuple[str, str] | None:
    """返回结果表单元格的标题与完整文本。"""

    if not row_id or not column_id.startswith("#"):
        return None
    try:
        index = int(column_id[1:]) - 1
    except ValueError:
        return None
    columns = tree["columns"]
    if index < 0 or index >= len(columns):
        return None
    values = tree.item(row_id, "values")
    if index >= len(values):
        return None
    text = str(values[index])
    if not text:
        return None
    heading = str(tree.heading(columns[index], "text"))
    return heading, text


class TreeCellToolTip:
    """在结果单元格被截短时显示完整内容。"""

    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self.window: tk.Toplevel | None = None
        self.after_id: str | None = None
        self.cell: tuple[str, str] | None = None
        self.pointer = (0, 0)
        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", self.hide, add="+")
        tree.bind("<ButtonPress>", self.hide, add="+")
        tree.bind("<MouseWheel>", self.hide, add="+")
        tree.bind("<Button-4>", self.hide, add="+")
        tree.bind("<Button-5>", self.hide, add="+")

    def _on_motion(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        cell = (row_id, column_id)
        if cell == self.cell:
            return
        self.hide()
        self.cell = cell
        self.pointer = (event.x_root, event.y_root)
        content = _tree_cell_content(self.tree, row_id, column_id)
        if content is None or not self._is_truncated(row_id, column_id, content[1]):
            return
        self.after_id = self.tree.after(350, lambda: self._show(content))

    def _is_truncated(self, row_id: str, column_id: str, text: str) -> bool:
        bounds = self.tree.bbox(row_id, column_id)
        visible_width = bounds[2] if bounds else int(self.tree.column(column_id, "width"))
        style_font = ttk.Style(self.tree).lookup("Treeview", "font")
        font = tkfont.Font(self.tree, font=style_font) if style_font else tkfont.nametofont("TkDefaultFont")
        return font.measure(text) + 18 > visible_width

    def _show(self, content: tuple[str, str]) -> None:
        self.after_id = None
        if self.window is not None or not self.tree.winfo_exists():
            return
        heading, value = content
        x, y = self.pointer
        self.window = tk.Toplevel(self.tree)
        self.window.wm_overrideredirect(True)
        label = tk.Label(
            self.window,
            text=f"{heading}\n{value}",
            justify="left",
            background="#F7FBFD",
            foreground="#1D2A35",
            relief="solid",
            borderwidth=1,
            highlightbackground="#9FB5C5",
            highlightthickness=1,
            padx=11,
            pady=8,
            font=("Microsoft YaHei UI", 9),
            wraplength=620,
        )
        label.pack()
        self.window.update_idletasks()
        target_x = min(
            x + 14,
            self.tree.winfo_screenwidth() - self.window.winfo_reqwidth() - 8,
        )
        target_y = min(
            y + 18,
            self.tree.winfo_screenheight() - self.window.winfo_reqheight() - 8,
        )
        self.window.wm_geometry(f"+{max(8, target_x)}+{max(8, target_y)}")

    def hide(self, _event=None) -> None:
        if self.after_id is not None:
            self.tree.after_cancel(self.after_id)
            self.after_id = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
        self.cell = None


class ToolTip:
    """为控件提供延迟显示的多行中文悬停说明。"""

    def __init__(self, widget: tk.Misc, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.after_id = self.widget.after(500, self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        if self.window is not None or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            justify="left",
            background="#F7FBFD",
            foreground="#1D2A35",
            relief="solid",
            borderwidth=1,
            highlightbackground="#9FB5C5",
            highlightthickness=1,
            padx=11,
            pady=8,
            font=("Microsoft YaHei UI", 9),
            wraplength=460,
        )
        label.pack()
        self.window.update_idletasks()
        target_x = min(x, self.widget.winfo_screenwidth() - self.window.winfo_reqwidth() - 8)
        target_y = min(y, self.widget.winfo_screenheight() - self.window.winfo_reqheight() - 8)
        self.window.wm_geometry(f"+{max(8, target_x)}+{max(8, target_y)}")

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


class TreeColumnTextOverlay:
    """仅覆盖 Treeview 的一个可见文本列，以支持单列强调色。"""

    def __init__(
        self,
        tree: ttk.Treeview,
        column: str,
        *,
        foreground: str,
        background: str,
        selected_background: str,
    ) -> None:
        self.tree = tree
        self.column = column
        self.foreground = foreground
        self.background = background
        self.selected_background = selected_background
        self._labels: list[tk.Label] = []
        self._tooltips: list[ToolTip] = []
        self._refresh_id: str | None = None
        self.tree.bind("<Configure>", self.schedule, add="+")
        self.tree.bind("<Expose>", self.schedule, add="+")
        self.tree.bind("<<TreeviewSelect>>", self.schedule, add="+")
        self.tree.bind("<MouseWheel>", self.schedule, add="+")
        self.tree.bind("<Button-4>", self.schedule, add="+")
        self.tree.bind("<Button-5>", self.schedule, add="+")

    @property
    def visible_labels(self) -> tuple[tk.Label, ...]:
        return tuple(label for label in self._labels if label.winfo_manager() == "place")

    def schedule(self, _event=None) -> None:
        if self._refresh_id is None and self.tree.winfo_exists():
            self._refresh_id = self.tree.after_idle(self.refresh)

    def refresh(self) -> None:
        self._refresh_id = None
        if not self.tree.winfo_exists() or not self.tree.winfo_ismapped():
            self._hide_from(0)
            return
        selection = set(self.tree.selection())
        visible_index = 0
        for item_id in self.tree.get_children(""):
            bounds = self.tree.bbox(item_id, self.column)
            if not bounds:
                continue
            x, y, width, height = bounds
            if width <= 2 or height <= 2:
                continue
            label, tooltip = self._label_at(visible_index)
            text = self.tree.set(item_id, self.column)
            label.configure(
                text=text,
                background=(
                    self.selected_background if item_id in selection else self.background
                ),
            )
            label._tree_item_id = item_id  # type: ignore[attr-defined]
            tooltip.text = f"新名称\n{text}"
            label.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)
            label.lift()
            visible_index += 1
        self._hide_from(visible_index)

    def _label_at(self, index: int) -> tuple[tk.Label, ToolTip]:
        if index == len(self._labels):
            style_font = ttk.Style(self.tree).lookup("Treeview", "font")
            label = tk.Label(
                self.tree,
                anchor="w",
                padx=6,
                borderwidth=0,
                background=self.background,
                foreground=self.foreground,
                font=style_font or ("Microsoft YaHei UI", 9),
            )
            label.bind("<Button-1>", lambda _event, item=label: self._select(item))
            label.bind("<MouseWheel>", self._scroll, add="+")
            label.bind("<Button-4>", lambda _event: self._scroll_lines(-1), add="+")
            label.bind("<Button-5>", lambda _event: self._scroll_lines(1), add="+")
            self._labels.append(label)
            self._tooltips.append(ToolTip(label, ""))
        return self._labels[index], self._tooltips[index]

    def _select(self, label: tk.Label) -> None:
        item_id = getattr(label, "_tree_item_id", "")
        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)

    def _scroll(self, event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            self._scroll_lines(-1 if delta > 0 else 1)
        return "break"

    def _scroll_lines(self, lines: int) -> str:
        self.tree.yview_scroll(lines, "units")
        self.schedule()
        return "break"

    def _hide_from(self, index: int) -> None:
        for label in self._labels[index:]:
            label.place_forget()


class BatchRenameApp:
    """批量重命名主窗口。"""

    POLL_INTERVAL_MS = 80
    RESPONSIVE_DELAY_MS = 120
    RAIL_WIDTHS = {"compact": 64, "standard": 270, "spacious": 300}
    RESULT_COLUMN_POLICIES = {
        "compact": {
            "kind": 52,
            "parent": 96,
            "old": 88,
            "new": 96,
            "status": 72,
            "detail": 88,
        },
        "standard": {
            "kind": 52,
            "parent": 135,
            "old": 100,
            "new": 110,
            "status": 72,
            "detail": 110,
        },
        "spacious": {
            "kind": 64,
            "parent": 250,
            "old": 180,
            "new": 190,
            "status": 96,
            "detail": 220,
        },
    }
    COLORS = {
        "background": "#F3F6FA",
        "card": "#FFFFFF",
        "navy": "#17324D",
        "navy_soft": "#284B6B",
        "accent": "#0F8B8D",
        "accent_hover": "#0B7476",
        "text": "#1D2A35",
        "muted": "#657482",
        "border": "#DCE4EB",
        "ready": "#177245",
        "warning": "#A76500",
        "blocked": "#A53A3A",
    }

    def __init__(
        self,
        root: tk.Tk,
        *,
        work_area_provider: Callable[[tk.Misc], tuple[int, int, int, int]] = _pointer_monitor_work_area,
    ) -> None:
        self.root = root
        self.root.title("批量重命名工具")
        self.initial_window_layout = calculate_window_layout(work_area_provider(root))
        self.root.geometry(self.initial_window_layout.geometry)
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(background=self.COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.directory_var = tk.StringVar(value=os.getcwd())
        self.depth_mode_var = tk.StringVar(value="all")
        self.depth_var = tk.IntVar(value=1)
        self.search_var = tk.StringVar()
        self.replacement_var = tk.StringVar()
        self.regex_var = tk.BooleanVar(value=False)
        self.rename_extension_var = tk.BooleanVar(value=False)
        self.include_dirs_var = tk.BooleanVar(value=True)
        self.include_files_var = tk.BooleanVar(value=True)
        self.preview_limit_var = tk.IntVar(value=100)
        self.rule_feedback_var = tk.StringVar(value="请输入查找内容；普通模式按原样匹配文本。")
        self.stats_var = tk.StringVar(
            value="匹配：0项 | 可修改：0项 | 名称未变化：0项 | 阻止执行：0项"
        )
        self.status_var = tk.StringVar(value="请设置目录和规则，然后点击“结果预览”。")
        self.progress_text_var = tk.StringVar(value="等待操作")

        self._messages: queue.Queue[tuple] = queue.Queue()
        self._busy = False
        self._input_widgets: list[ttk.Widget] = []
        self._last_matches: MatchResult | None = None
        self._last_scan: ScanResult | None = None
        self._last_execution: ExecutionResult | None = None
        self._responsive_after_id: str | None = None
        self._last_responsive_size: tuple[int, int] | None = None
        self.current_layout_mode = self.initial_window_layout.layout_mode
        self._app_icon: tk.PhotoImage | None = None
        self._header_icon: tk.PhotoImage | None = None
        self.dialogs = ManagedDialogs(self.root)

        self._configure_style()
        self._load_application_icon()
        self._build_ui()
        self._apply_responsive_layout(*self.initial_window_layout.size)
        self.root.bind("<Configure>", self._schedule_responsive_layout, add="+")
        self._bind_change_tracking()
        self._update_depth_state()
        self._sync_command_states()
        self.root.after(self.POLL_INTERVAL_MS, self._poll_messages)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        colors = self.COLORS
        style.configure("TFrame", background=colors["background"])
        style.configure("App.TFrame", background=colors["background"])
        style.configure("Workflow.TFrame", background="#EAF0F5")
        style.configure("WorkflowCard.TFrame", background="#EAF0F5")
        style.configure("CompactNav.TFrame", background="#17324D")
        style.configure(
            "CompactNav.TButton",
            background="#17324D",
            foreground="#FFFFFF",
            borderwidth=0,
            relief="flat",
            padding=(5, 9),
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        style.map(
            "CompactNav.TButton",
            background=[("active", "#284B6B"), ("pressed", "#0F8B8D")],
            foreground=[("disabled", "#8EA0B0")],
        )
        style.configure(
            "WorkflowTitle.TLabel",
            background="#EAF0F5",
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "WorkflowHint.TLabel",
            background="#EAF0F5",
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "Workflow.TRadiobutton",
            background="#EAF0F5",
            foreground=colors["text"],
            padding=(4, 3),
            font=("Microsoft YaHei UI", 9),
        )
        style.map(
            "Workflow.TRadiobutton",
            background=[("active", "#DCE7EF"), ("disabled", "#EAF0F5")],
            foreground=[("disabled", "#99A5AF")],
        )
        style.configure(
            "WorkflowAccent.TButton",
            background=colors["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(8, 2),
            font=("Microsoft YaHei UI", 9, "bold"),
            focuscolor=colors["accent_hover"],
        )
        style.map(
            "WorkflowAccent.TButton",
            background=[("active", colors["accent_hover"]), ("disabled", "#A9C7C8")],
            foreground=[("disabled", "#F3F6F6")],
        )
        style.configure(
            "WorkflowSecondary.TButton",
            background="#E1E9F0",
            foreground=colors["navy"],
            borderwidth=0,
            padding=(8, 2),
            font=("Microsoft YaHei UI", 8),
            focuscolor="#C7D8E5",
        )
        style.map("WorkflowSecondary.TButton", background=[("active", "#D2E0E9")])
        style.configure("Header.TFrame", background=colors["navy"])
        style.configure("Card.TFrame", background=colors["card"], relief="flat")
        style.configure(
            "HeaderTitle.TLabel",
            background=colors["navy"],
            foreground="#FFFFFF",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=colors["navy"],
            foreground="#D7E5F0",
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Title.TLabel",
            background=colors["background"],
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 17, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=colors["background"],
            foreground=colors["muted"],
        )
        style.configure(
            "Icon.TLabel",
            background=colors["navy_soft"],
            foreground="#FFFFFF",
            font=("Microsoft YaHei UI", 20, "bold"),
            anchor="center",
        )
        style.configure(
            "CardTitle.TLabel",
            background=colors["card"],
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        style.configure(
            "Card.TLabel",
            background=colors["card"],
            foreground=colors["text"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Field.TLabel",
            background=colors["card"],
            foreground=colors["navy_soft"],
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.configure(
            "Unit.TLabel",
            background=colors["card"],
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Hint.TLabel",
            background=colors["card"],
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "Stats.TLabel",
            background=colors["card"],
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "MatchStats.TLabel",
            background="#EAF7F7",
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(8, 5),
        )
        style.configure("Card.TCheckbutton", background=colors["card"], foreground=colors["text"])
        style.configure(
            "Card.TCheckbutton",
            padding=(4, 3),
            font=("Microsoft YaHei UI", 9),
            focuscolor=colors["accent"],
        )
        style.map(
            "Card.TCheckbutton",
            background=[("active", "#F0F7F8"), ("disabled", colors["card"])],
            foreground=[("disabled", "#99A5AF")],
        )
        style.configure(
            "Card.TRadiobutton",
            background=colors["card"],
            foreground=colors["text"],
            padding=(4, 3),
            font=("Microsoft YaHei UI", 9),
            focuscolor=colors["accent"],
        )
        style.map(
            "Card.TRadiobutton",
            background=[("active", "#F0F7F8"), ("disabled", colors["card"])],
            foreground=[("disabled", "#99A5AF")],
        )
        style.configure(
            "Modern.TEntry",
            fieldbackground="#F8FAFC",
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            insertcolor=colors["navy"],
            padding=(7, 3),
        )
        style.map(
            "Modern.TEntry",
            fieldbackground=[("disabled", "#EEF2F5")],
            foreground=[("disabled", "#8C99A4")],
            bordercolor=[("focus", colors["accent"]), ("invalid", colors["blocked"])],
            lightcolor=[("focus", colors["accent"])],
            darkcolor=[("focus", colors["accent"])],
        )
        style.configure(
            "Modern.TSpinbox",
            fieldbackground="#F8FAFC",
            foreground=colors["text"],
            arrowcolor=colors["navy_soft"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(5, 3),
            arrowsize=12,
        )
        style.map(
            "Modern.TSpinbox",
            fieldbackground=[("disabled", "#EEF2F5")],
            foreground=[("disabled", "#8C99A4")],
            bordercolor=[("focus", colors["accent"])],
            arrowcolor=[("active", colors["accent"]), ("disabled", "#AAB4BD")],
        )
        style.configure(
            "Modern.TCombobox",
            fieldbackground="#F8FAFC",
            background="#E8EEF4",
            foreground=colors["text"],
            arrowcolor=colors["navy_soft"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(6, 3),
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", "#F8FAFC")],
            bordercolor=[("focus", colors["accent"])],
            arrowcolor=[("active", colors["accent"])],
        )
        style.configure(
            "Accent.TButton",
            background=colors["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 7),
            font=("Microsoft YaHei UI", 10, "bold"),
            focuscolor=colors["accent_hover"],
        )
        style.map(
            "Accent.TButton",
            background=[("active", colors["accent_hover"]), ("disabled", "#A9C7C8")],
            foreground=[("disabled", "#F3F6F6")],
        )
        style.configure(
            "Secondary.TButton",
            background="#E8EEF4",
            foreground=colors["navy"],
            borderwidth=0,
            padding=(12, 6),
            font=("Microsoft YaHei UI", 9),
            focuscolor="#C7D8E5",
        )
        style.map("Secondary.TButton", background=[("active", "#D9E4ED")])
        style.configure(
            "Header.TButton",
            background=colors["navy_soft"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(13, 8),
            focuscolor="#356384",
        )
        style.map("Header.TButton", background=[("active", "#356384")])
        style.configure(
            "Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=colors["text"],
            bordercolor=colors["border"],
            rowheight=23,
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#EAF0F5",
            foreground=colors["navy"],
            relief="flat",
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(7, 4),
        )
        style.map("Treeview.Heading", background=[("active", "#DDE7EF")])
        for orientation in ("Horizontal", "Vertical"):
            style.configure(
                f"Modern.{orientation}.TScrollbar",
                troughcolor="#EDF2F6",
                background="#AFC2D0",
                bordercolor="#EDF2F6",
                lightcolor="#AFC2D0",
                darkcolor="#AFC2D0",
                arrowcolor=colors["navy_soft"],
                relief="flat",
                borderwidth=0,
                width=11,
            )
            style.map(
                f"Modern.{orientation}.TScrollbar",
                background=[("active", colors["accent"]), ("pressed", colors["accent_hover"])],
                arrowcolor=[("active", "#FFFFFF")],
            )
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor="#DDE7ED",
            background=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
            bordercolor="#DDE7ED",
            thickness=11,
        )
        style.configure(
            "Status.TLabel",
            background="#E8EEF4",
            foreground=colors["navy_soft"],
            bordercolor=colors["border"],
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )

    def _load_application_icon(self) -> None:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        icon_path = base / "assets" / "app-icon.png"
        try:
            self._app_icon = tk.PhotoImage(file=icon_path)
            factor = max(1, round(self._app_icon.width() / 46))
            self._header_icon = self._app_icon.subsample(factor, factor)
            self.root.iconphoto(True, self._app_icon)
        except (OSError, tk.TclError):
            self._app_icon = None
            self._header_icon = None

    def _build_ui(self) -> None:
        self._build_top_menu()
        outer = ttk.Frame(self.root, style="App.TFrame", padding=(8, 6, 8, 5))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        self.main_content = outer

        header = ttk.Frame(outer, style="Header.TFrame", padding=(11, 6))
        header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        header.columnconfigure(1, weight=1)
        if self._header_icon is not None:
            self.brand_icon_label = ttk.Label(
                header,
                image=self._header_icon,
                style="Icon.TLabel",
                padding=2,
            )
        else:
            self.brand_icon_label = ttk.Label(header, text="↻", style="Icon.TLabel", width=3)
        self.brand_icon_label.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 13))
        ttk.Label(header, text="批量重命名", style="HeaderTitle.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(
            header,
            text="在执行前看清每一个匹配结果，安全整理多层目录中的文件夹与文件。",
            style="HeaderSubtitle.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))
        body = ttk.Frame(outer, style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        self.body_frame = body
        self._build_compact_navigation(body)
        self._build_workflow_rail(body)
        self._build_result_workspace(body)
        self._build_tool_panels(body)

    def _build_compact_navigation(self, parent: ttk.Frame) -> None:
        navigation = ttk.Frame(
            parent,
            style="CompactNav.TFrame",
            width=self.RAIL_WIDTHS["compact"],
            padding=(6, 8),
        )
        navigation.grid(row=0, column=0, sticky="ns", padx=(0, 7))
        navigation.grid_propagate(False)
        navigation.columnconfigure(0, weight=1)
        navigation.rowconfigure(2, weight=1)
        self.compact_navigation = navigation
        self.workflow_drawer_open = False

        self.workflow_nav_button = ttk.Button(
            navigation,
            text="☰",
            style="CompactNav.TButton",
            command=self._toggle_workflow_drawer,
        )
        self.workflow_nav_button.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.compact_templates_button = ttk.Button(
            navigation,
            text=".*",
            style="CompactNav.TButton",
            command=self._show_regex_examples,
        )
        self.compact_templates_button.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.compact_settings_button = ttk.Button(
            navigation,
            text="⚙",
            style="CompactNav.TButton",
            command=self._show_settings,
        )
        self.compact_settings_button.grid(row=4, column=0, sticky="ew")
        self._input_widgets.extend(
            [self.compact_templates_button, self.compact_settings_button]
        )
        ToolTip(self.workflow_nav_button, "展开或收起完整重命名流程。")
        ToolTip(self.compact_templates_button, "打开常用正则模板。")
        ToolTip(self.compact_settings_button, "打开扫描与预览设置。")
        navigation.grid_remove()

    def _schedule_responsive_layout(self, event: tk.Event) -> None:
        """防抖处理主窗口缩放，避免拖动过程中连续重排。"""

        if event.widget is not self.root:
            return
        if self._responsive_after_id is not None:
            self.root.after_cancel(self._responsive_after_id)
        width = max(MIN_WINDOW_WIDTH, int(event.width))
        height = max(MIN_WINDOW_HEIGHT, int(event.height))
        self._responsive_after_id = self.root.after(
            self.RESPONSIVE_DELAY_MS,
            lambda: self._apply_responsive_layout(width, height),
        )

    def _apply_responsive_layout(self, width: int, height: int) -> None:
        """原地应用当前客户区的布局档位和结果列策略。"""

        self._responsive_after_id = None
        mode = layout_mode_for_width(width)
        previous_size = self._last_responsive_size
        if (
            mode == self.current_layout_mode
            and previous_size is not None
            and abs(previous_size[0] - width) < 8
            and abs(previous_size[1] - height) < 8
        ):
            return
        self.current_layout_mode = mode
        self._last_responsive_size = (width, height)
        self.workflow_rail.configure(width=self.RAIL_WIDTHS[mode])
        if mode == "compact":
            self.compact_navigation.grid()
            if self.workflow_drawer_open:
                self._position_workflow_drawer()
            else:
                self.workflow_rail.grid_remove()
        else:
            self._close_workflow_drawer()
            self.compact_navigation.grid_remove()
            self.workflow_rail.configure(width=self.RAIL_WIDTHS[mode])
            self.workflow_rail.grid(row=0, column=0, sticky="ns", padx=(0, 7))
        for column, column_width in self.RESULT_COLUMN_POLICIES[mode].items():
            min_width = 52 if column == "kind" else min(72, column_width)
            self.result_tree.column(column, width=column_width, minwidth=min_width)
        self.new_name_overlay.schedule()
        self._position_active_tool_panel()

    def _toggle_workflow_drawer(self) -> None:
        """在紧凑模式下展开或收起原有工作流控件。"""

        if self.current_layout_mode != "compact":
            return
        if self.workflow_drawer_open:
            self._close_workflow_drawer()
            return
        if self._busy:
            return
        self._close_tool_panel()
        self.workflow_drawer_open = True
        self._position_workflow_drawer()

    def _position_workflow_drawer(self) -> None:
        if not self.workflow_drawer_open or self.current_layout_mode != "compact":
            return
        self.root.update_idletasks()
        body_height = max(1, self.body_frame.winfo_height())
        body_width = max(1, self.body_frame.winfo_width())
        x = self.RAIL_WIDTHS["compact"] + 7
        width = min(300, max(1, body_width - x))
        self.workflow_rail.configure(width=width)
        self.workflow_rail.place(x=x, y=0, width=width, height=body_height)
        self.workflow_rail.lift()

    def _close_workflow_drawer(self) -> None:
        self.workflow_rail.place_forget()
        self.workflow_drawer_open = False

    def _close_overlays(self) -> None:
        self._close_workflow_drawer()
        self._close_tool_panel()

    def _build_top_menu(self) -> None:
        self.top_menu = tk.Menu(self.root, tearoff=False)
        self.file_menu = tk.Menu(self.top_menu, tearoff=False)
        self.file_menu.add_command(label="退出", command=self._on_close)
        self.top_menu.add_cascade(label="文件", menu=self.file_menu)

        self.feature_menu = tk.Menu(self.top_menu, tearoff=False)
        self.feature_menu.add_command(
            label="结果详情", command=self._show_execution_details, state="disabled"
        )
        self.result_details_menu_index = 0
        self.feature_menu.add_separator()
        self.feature_menu.add_command(label="撤回管理（开发中）", state="disabled")
        self.undo_menu_index = self.feature_menu.index("end")
        self.feature_menu.add_command(label="操作日志（开发中）", state="disabled")
        self.log_menu_index = self.feature_menu.index("end")
        self.top_menu.add_cascade(label="功能", menu=self.feature_menu)

        self.help_menu = tk.Menu(self.top_menu, tearoff=False)
        self.help_menu.add_command(label="使用说明", command=self._show_help)
        self.help_menu.add_command(label="关于", command=self._show_about)
        self.top_menu.add_cascade(label="帮助", menu=self.help_menu)
        self.root.configure(menu=self.top_menu)
        self.root.bind("<F1>", lambda _event: self._show_help())

    def _build_workflow_rail(self, parent: ttk.Frame) -> None:
        rail = ttk.Frame(parent, style="Workflow.TFrame", width=270, padding=(12, 6))
        rail.grid(row=0, column=0, sticky="ns", padx=(0, 7))
        rail.grid_propagate(False)
        rail.columnconfigure(0, weight=1)
        rail.columnconfigure(1, weight=1)
        rail.rowconfigure(14, weight=1)
        self.workflow_rail = rail

        ttk.Label(rail, text="重命名流程", style="WorkflowTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        self.root_directory_label = ttk.Label(
            rail, text="1  选择目录", style="WorkflowTitle.TLabel"
        )
        self.root_directory_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.directory_entry = ttk.Entry(
            rail, textvariable=self.directory_var, style="Modern.TEntry"
        )
        self.directory_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        self.directory_select_button = ttk.Button(
            rail, text="选择目录…", style="WorkflowSecondary.TButton", command=self._choose_directory
        )
        self.directory_select_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        ttk.Label(rail, text="2  查找规则", style="WorkflowTitle.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w"
        )
        self.plain_mode_radio = ttk.Radiobutton(
            rail,
            text="普通文本",
            variable=self.regex_var,
            value=False,
            style="Workflow.TRadiobutton",
        )
        self.plain_mode_radio.grid(row=5, column=0, sticky="w", pady=(1, 0))
        self.regex_mode_radio = ttk.Radiobutton(
            rail,
            text="正则表达式",
            variable=self.regex_var,
            value=True,
            style="Workflow.TRadiobutton",
        )
        self.regex_mode_radio.grid(row=5, column=1, sticky="w", pady=(1, 0))
        self.search_field_label = ttk.Label(
            rail, text="查找内容", style="WorkflowHint.TLabel"
        )
        self.search_field_label.grid(row=6, column=0, columnspan=2, sticky="w")
        self.search_entry = ttk.Entry(
            rail, textvariable=self.search_var, style="Modern.TEntry"
        )
        self.search_entry.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        self.search_button = ttk.Button(
            rail, text="扫描", style="WorkflowSecondary.TButton", command=self._start_search
        )
        self.search_button.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        self.replacement_field_label = ttk.Label(
            rail, text="3  替换为", style="WorkflowTitle.TLabel"
        )
        self.replacement_field_label.grid(row=9, column=0, columnspan=2, sticky="w")
        self.replacement_entry = ttk.Entry(
            rail, textvariable=self.replacement_var, style="Modern.TEntry"
        )
        self.replacement_entry.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        self.preview_button = ttk.Button(
            rail, text="结果预览", style="WorkflowAccent.TButton", command=self._start_preview
        )
        self.preview_button.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 3))
        self.execute_button = ttk.Button(
            rail,
            text="确认执行",
            style="WorkflowSecondary.TButton",
            command=self._confirm_execute,
            state="disabled",
        )
        self.execute_button.grid(row=12, column=0, columnspan=2, sticky="ew")
        self.rule_feedback_label = ttk.Label(
            rail,
            textvariable=self.rule_feedback_var,
            style="WorkflowHint.TLabel",
            wraplength=238,
            justify="left",
        )
        self.rule_feedback_label.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        self.regex_templates_button = ttk.Button(
            rail, text="⌘  正则模板", style="WorkflowSecondary.TButton", command=self._show_regex_examples
        )
        self.regex_templates_button.grid(row=15, column=0, sticky="ew", padx=(0, 3), pady=(8, 0))
        self.settings_tool_button = ttk.Button(
            rail, text="⚙  设置", style="WorkflowSecondary.TButton", command=self._show_settings
        )
        self.settings_tool_button.grid(row=15, column=1, sticky="ew", padx=(3, 0), pady=(8, 0))

        # 兼容旧的内部名称；界面中仍只有一组流程按钮。
        self.search_scan_button = self.search_button
        self.scan_button = self.preview_button
        self._input_widgets.extend(
            [
                self.directory_entry,
                self.directory_select_button,
                self.plain_mode_radio,
                self.regex_mode_radio,
                self.search_entry,
                self.search_button,
                self.replacement_entry,
                self.regex_templates_button,
                self.settings_tool_button,
            ]
        )
        ToolTip(self.directory_entry, "扫描起点；根目录本身不会改名。")
        ToolTip(self.search_button, "只查找名称匹配项，不计算新名称，也不会修改磁盘。")
        ToolTip(self.preview_button, "根据刚才的匹配快照计算新名称和安全状态，不会重新扫描目录。")
        ToolTip(self.execute_button, "只执行预览中状态为“可修改”的项目，并在执行前再次确认。")

    def _build_result_workspace(self, parent: ttk.Frame) -> None:
        workspace = ttk.Frame(parent, style="App.TFrame")
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.rowconfigure(1, weight=1)
        workspace.columnconfigure(0, weight=1)
        self.result_workspace = workspace
        self._build_actions_frame(workspace)
        self._build_preview_frame(workspace)
        self._build_progress_frame(workspace)

    def _build_tool_panels(self, parent: ttk.Frame) -> None:
        self.active_tool_panel: str | None = None
        self.settings_panel = ttk.Frame(parent, style="Card.TFrame", padding=14)
        self.settings_panel.columnconfigure(1, weight=1)
        ttk.Label(self.settings_panel, text="扫描与预览设置", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 9)
        )
        ttk.Label(self.settings_panel, text="扫描层级", style="Field.TLabel").grid(
            row=1, column=0, sticky="w", pady=4
        )
        all_depth = ttk.Radiobutton(
            self.settings_panel,
            text="全部层级",
            variable=self.depth_mode_var,
            value="all",
            style="Card.TRadiobutton",
            command=self._update_depth_state,
        )
        all_depth.grid(row=1, column=1, sticky="w")
        limited = ttk.Radiobutton(
            self.settings_panel,
            text="最多",
            variable=self.depth_mode_var,
            value="limited",
            style="Card.TRadiobutton",
            command=self._update_depth_state,
        )
        limited.grid(row=1, column=2, sticky="w")
        self.depth_spin = ttk.Spinbox(
            self.settings_panel,
            from_=1,
            to=999,
            width=6,
            textvariable=self.depth_var,
            style="Modern.TSpinbox",
            justify="center",
        )
        self.depth_spin.grid(row=1, column=3, sticky="w", padx=(4, 0))
        ttk.Label(self.settings_panel, text="处理对象", style="Field.TLabel").grid(
            row=2, column=0, sticky="w", pady=4
        )
        dirs = ttk.Checkbutton(
            self.settings_panel,
            text="文件夹",
            variable=self.include_dirs_var,
            style="Card.TCheckbutton",
        )
        dirs.grid(row=2, column=1, sticky="w")
        files = ttk.Checkbutton(
            self.settings_panel,
            text="文件",
            variable=self.include_files_var,
            style="Card.TCheckbutton",
        )
        files.grid(row=2, column=2, sticky="w")
        extension = ttk.Checkbutton(
            self.settings_panel,
            text="允许修改扩展名",
            variable=self.rename_extension_var,
            style="Card.TCheckbutton",
        )
        extension.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(
            self.settings_panel,
            text="层级和处理对象改变后需要重新扫描；扩展名选项只会使结果预览失效。",
            style="Hint.TLabel",
            wraplength=390,
        ).grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self._input_widgets.extend([all_depth, limited, self.depth_spin, dirs, files, extension])

        self.templates_panel = ttk.Frame(parent, style="Card.TFrame", padding=14)
        self.templates_panel.columnconfigure(1, weight=1)
        self.templates_panel.rowconfigure(2, weight=1)
        ttk.Label(self.templates_panel, text="常用正则模板", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        categories = tuple(dict.fromkeys(example.category for example in REGEX_EXAMPLES))
        self.regex_category_var = tk.StringVar(self.root, value=categories[0])
        self.regex_category_selector = ttk.Combobox(
            self.templates_panel,
            textvariable=self.regex_category_var,
            values=categories,
            state="readonly",
            width=17,
            style="Modern.TCombobox",
        )
        self.regex_category_selector.grid(row=1, column=0, sticky="ew", pady=(8, 7), padx=(0, 9))
        self.regex_purpose_var = tk.StringVar(self.root)
        ttk.Label(
            self.templates_panel,
            textvariable=self.regex_purpose_var,
            style="Hint.TLabel",
            wraplength=270,
            justify="left",
        ).grid(row=1, column=1, sticky="ew", pady=(8, 7))

        self.regex_template_list = tk.Listbox(
            self.templates_panel,
            exportselection=False,
            activestyle="none",
            height=8,
            width=20,
            font=("Microsoft YaHei UI", 9),
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            highlightcolor=self.COLORS["accent"],
            background="#F8FAFC",
            foreground=self.COLORS["text"],
            selectbackground=self.COLORS["accent"],
            selectforeground="#FFFFFF",
        )
        self.regex_template_list.grid(row=2, column=0, rowspan=5, sticky="nsew", padx=(0, 9))
        self.regex_example_search_var = tk.StringVar(self.root)
        self.regex_example_replacement_var = tk.StringVar(self.root)
        self.regex_before_var = tk.StringVar(self.root)
        self.regex_after_var = tk.StringVar(self.root)
        self.regex_option_note_var = tk.StringVar(self.root)
        ttk.Label(self.templates_panel, text="查找表达式", style="Field.TLabel").grid(
            row=2, column=1, sticky="w"
        )
        self.regex_search_entry = ttk.Entry(
            self.templates_panel,
            textvariable=self.regex_example_search_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 9),
        )
        self.regex_search_entry.grid(row=3, column=1, sticky="ew", pady=(2, 5))
        ttk.Label(self.templates_panel, text="替换内容", style="Field.TLabel").grid(
            row=4, column=1, sticky="w"
        )
        self.regex_replacement_entry = ttk.Entry(
            self.templates_panel,
            textvariable=self.regex_example_replacement_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 9),
        )
        self.regex_replacement_entry.grid(row=5, column=1, sticky="ew", pady=(2, 5))
        self.regex_example_text_var = tk.StringVar(self.root)
        ttk.Label(
            self.templates_panel,
            textvariable=self.regex_example_text_var,
            style="Card.TLabel",
            foreground=self.COLORS["ready"],
            wraplength=270,
        ).grid(row=6, column=1, sticky="ew")
        self.regex_apply_button = ttk.Button(
            self.templates_panel,
            text="一键应用此规则",
            style="Accent.TButton",
        )
        self.regex_apply_button.grid(row=7, column=1, sticky="e", pady=(8, 0))
        self.regex_category_selector.bind("<<ComboboxSelected>>", self._filter_regex_templates)
        self.regex_template_list.bind("<<ListboxSelect>>", self._show_selected_regex_template)
        self.regex_template_list.bind("<Double-Button-1>", lambda _event: self.regex_apply_button.invoke())
        self._filter_regex_templates()

        self.root.bind("<Escape>", lambda _event: self._close_overlays())
        for widget in (
            self.result_workspace,
            self.result_card,
            self.result_tree,
            self.stats_label,
            self.progress,
        ):
            widget.bind(
                "<Button-1>", lambda _event: self._close_overlays(), add="+"
            )

    def _toggle_tool_panel(self, name: str) -> None:
        if self.active_tool_panel == name:
            self._close_tool_panel()
            return
        if self._busy:
            return
        self._close_workflow_drawer()
        self._close_tool_panel()
        self.active_tool_panel = name
        self._position_active_tool_panel()

    def _position_active_tool_panel(self) -> None:
        """将当前浮动工具限制在主内容区域内并贴近侧栏。"""

        if self.active_tool_panel is None:
            return
        panel = (
            self.settings_panel
            if self.active_tool_panel == "settings"
            else self.templates_panel
        )
        self.root.update_idletasks()
        rail_width = self.RAIL_WIDTHS[self.current_layout_mode]
        x = rail_width + 8
        available_width = max(360, self.body_frame.winfo_width() - x)
        width = min(500, available_width - 16)
        body_height = max(1, self.body_frame.winfo_height())
        height = min(panel.winfo_reqheight(), max(1, body_height - 16))
        y = max(8, body_height - height - 8)
        panel.place(x=x, y=y, width=width, height=height)
        panel.lift()

    def _close_tool_panel(self) -> None:
        self.settings_panel.place_forget()
        self.templates_panel.place_forget()
        self.active_tool_panel = None

    def _show_settings(self) -> None:
        self._toggle_tool_panel("settings")

    def _filter_regex_templates(self, _event=None) -> None:
        category = self.regex_category_var.get()
        self._visible_regex_examples = [
            example for example in REGEX_EXAMPLES if example.category == category
        ]
        self.regex_template_list.delete(0, "end")
        for example in self._visible_regex_examples:
            self.regex_template_list.insert("end", example.title)
        if self._visible_regex_examples:
            self.regex_template_list.selection_set(0)
            self.regex_template_list.activate(0)
            self._show_selected_regex_template()

    def _show_selected_regex_template(self, _event=None) -> None:
        selection = self.regex_template_list.curselection()
        if not selection or not self._visible_regex_examples:
            return
        example = self._visible_regex_examples[selection[0]]
        self.regex_purpose_var.set(example.purpose)
        self.regex_example_search_var.set(example.search)
        self.regex_example_replacement_var.set(
            example.replacement or "（空文本：删除匹配内容）"
        )
        self.regex_before_var.set(example.before)
        self.regex_after_var.set(example.after)
        self.regex_example_text_var.set(f"示例：{example.before}  →  {example.after}")
        self.regex_option_note_var.set(
            "会同时开启扩展名处理" if example.rename_extension else "保留最后一个扩展名"
        )
        self.regex_apply_button.configure(command=lambda: self._apply_regex_example(example))

    def _build_scope_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.scope_card = frame
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="扫描范围", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        self.root_directory_label = ttk.Label(
            frame, text="根目录", style="Field.TLabel"
        )
        self.root_directory_label.grid(
            row=1, column=0, padx=(0, 8), pady=5, sticky="w"
        )
        self.directory_entry = ttk.Entry(
            frame,
            textvariable=self.directory_var,
            width=12,
            style="Modern.TEntry",
        )
        self.directory_entry.grid(row=1, column=1, padx=0, pady=5, sticky="ew", ipady=4)
        browse = ttk.Button(frame, text="选择…", style="Secondary.TButton", command=self._choose_directory)
        browse.grid(row=1, column=2, padx=(8, 0), pady=5)
        ToolTip(
            self.directory_entry,
            "要扫描的起始目录。根目录本身不会被重命名，只处理它内部的文件夹和文件。",
        )
        ToolTip(browse, "从系统目录选择器中选择扫描起点。")
        self._input_widgets.extend([self.directory_entry, browse])

        depth_row = ttk.Frame(frame, style="Card.TFrame")
        depth_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        ttk.Label(depth_row, text="层级", style="Field.TLabel").pack(
            side="left", padx=(0, 10)
        )
        all_depth = ttk.Radiobutton(
            depth_row,
            text="全部层级",
            variable=self.depth_mode_var,
            value="all",
            style="Card.TRadiobutton",
            command=self._update_depth_state,
        )
        all_depth.pack(side="left", padx=(0, 12))
        limited = ttk.Radiobutton(
            depth_row,
            text="限为",
            variable=self.depth_mode_var,
            value="limited",
            style="Card.TRadiobutton",
            command=self._update_depth_state,
        )
        limited.pack(side="left")
        self.depth_spin = ttk.Spinbox(
            depth_row,
            from_=1,
            to=999,
            width=6,
            textvariable=self.depth_var,
            style="Modern.TSpinbox",
            justify="center",
        )
        self.depth_spin.pack(side="left", padx=5)
        ttk.Label(depth_row, text="层", style="Unit.TLabel").pack(side="left")
        ToolTip(
            depth_row,
            "第 1 层是根目录中的直接子项；第 2 层是直接子文件夹中的项目，以此类推。符号链接不会被跟随。",
        )
        self._input_widgets.extend([all_depth, limited, self.depth_spin])

    def _build_rule_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=8)
        frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.rule_card = frame
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(4, weight=1)
        ttk.Label(frame, text="重命名规则", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self.regex_templates_button = ttk.Button(
            frame,
            text="正则模板",
            style="Secondary.TButton",
            command=self._show_regex_examples,
        )
        self.regex_templates_button.grid(row=0, column=4, sticky="e", pady=(0, 5))
        self.search_field_label = ttk.Label(
            frame, text="查找", style="Field.TLabel"
        )
        self.search_field_label.grid(
            row=1, column=0, padx=(0, 8), pady=4, sticky="w"
        )
        self.search_entry = ttk.Entry(
            frame, textvariable=self.search_var, width=14, style="Modern.TEntry"
        )
        self.search_entry.grid(row=1, column=1, padx=(0, 5), pady=3, sticky="ew", ipady=3)
        self.search_scan_button = ttk.Button(
            frame,
            text="扫描",
            style="Secondary.TButton",
            command=self._start_search,
        )
        self.search_scan_button.grid(row=1, column=2, padx=(0, 9), pady=3)
        self.replacement_field_label = ttk.Label(
            frame, text="替换", style="Field.TLabel"
        )
        self.replacement_field_label.grid(
            row=1, column=3, padx=(0, 8), pady=3, sticky="w"
        )
        self.replacement_entry = ttk.Entry(
            frame,
            textvariable=self.replacement_var,
            width=14,
            style="Modern.TEntry",
        )
        self.replacement_entry.grid(row=1, column=4, pady=3, sticky="ew", ipady=3)
        ToolTip(self.search_entry, "普通模式：输入要查找的原样文本。正则模式：输入 Python 正则表达式。不能为空。")
        ToolTip(self.replacement_entry, "可留空，表示删除匹配内容。正则模式可使用 \\1 或 \\g<名称> 引用捕获组。")

        options = ttk.Frame(frame, style="Card.TFrame")
        options.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(4, 1))
        regex = ttk.Checkbutton(options, text="正则表达式", variable=self.regex_var, style="Card.TCheckbutton")
        regex.pack(side="left", padx=(0, 12))
        dirs = ttk.Checkbutton(options, text="文件夹", variable=self.include_dirs_var, style="Card.TCheckbutton")
        dirs.pack(side="left", padx=(0, 12))
        files = ttk.Checkbutton(options, text="文件", variable=self.include_files_var, style="Card.TCheckbutton")
        files.pack(side="left", padx=(0, 12))
        extension = ttk.Checkbutton(
            options,
            text="包含扩展名",
            variable=self.rename_extension_var,
            style="Card.TCheckbutton",
        )
        extension.pack(side="left")
        self._input_widgets.extend(
            [
                self.search_entry,
                self.search_scan_button,
                self.replacement_entry,
                regex,
                dirs,
                files,
                extension,
                self.regex_templates_button,
            ]
        )
        ToolTip(regex, "关闭时按普通文本查找；开启后使用 Python 正则语法，例如 (\\d{4})-(\\d{2})。")
        ToolTip(dirs, "勾选后，名称匹配的子文件夹会进入预览。")
        ToolTip(files, "勾选后，名称匹配的文件会进入预览。")
        ToolTip(extension, "默认保护最后一个扩展名。例如查找 jpg 不会改变照片.jpg；开启后才会处理整个文件名。")
        ToolTip(
            self.regex_templates_button,
            "按用途选择经过验证的常用正则规则，查看处理前后效果并一键填入主窗口。",
        )
        ToolTip(
            self.search_scan_button,
            "使用当前全部规则生成结果预览；在查找框按 Enter 也可执行相同操作。",
        )

        self.rule_feedback_label = ttk.Label(
            frame,
            textvariable=self.rule_feedback_var,
            style="Hint.TLabel",
            wraplength=900,
        )
        self.rule_feedback_label.grid(row=3, column=0, columnspan=5, sticky="w", pady=(3, 0))

    def _build_actions_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(8, 5))
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        self.stats_label = ttk.Label(
            frame,
            textvariable=self.stats_var,
            style="MatchStats.TLabel",
        )
        self.stats_label.grid(row=0, column=0, sticky="w")

    def _build_preview_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(8, 5))
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        self.result_card = frame
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        heading = ttk.Frame(frame, style="Card.TFrame")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        heading.columnconfigure(1, weight=1)
        ttk.Label(heading, text="匹配结果", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(heading, text="显示", style="Field.TLabel").grid(
            row=0, column=2, padx=(8, 4)
        )
        self.preview_spin = ttk.Spinbox(
            heading,
            from_=1,
            to=100,
            width=5,
            textvariable=self.preview_limit_var,
            command=self._render_preview,
            style="Modern.TSpinbox",
            justify="center",
        )
        self.preview_spin.grid(row=0, column=3)
        ttk.Label(heading, text="条", style="Unit.TLabel").grid(
            row=0, column=4, padx=(4, 0)
        )
        ToolTip(
            self.preview_spin,
            "仅控制表格显示数量，不改变完整匹配统计和最终执行数量。文件夹优先，同类按名称自然排序。",
        )
        self._input_widgets.append(self.preview_spin)
        self.result_tree = self._create_tree(frame)

    def _create_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        columns = ("kind", "parent", "old", "new", "status", "detail")
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=10,
        )
        headings = {
            "kind": "类型",
            "old": "原名称",
            "new": "新名称",
            "parent": "所在目录",
            "status": "状态",
            "detail": "说明",
        }
        widths = {
            "kind": 52,
            "parent": 135,
            "old": 100,
            "new": 110,
            "status": 72,
            "detail": 110,
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(
                column,
                width=widths[column],
                minwidth=52 if column == "kind" else 72,
                stretch=column in {"old", "new", "parent", "detail"},
            )
        self.new_name_overlay = TreeColumnTextOverlay(
            tree,
            "new",
            foreground=self.COLORS["accent"],
            background=self.COLORS["card"],
            selected_background="#D9EAF2",
        )

        def scroll_vertical(*args: str) -> None:
            tree.yview(*args)
            self.new_name_overlay.schedule()

        def scroll_horizontal(*args: str) -> None:
            tree.xview(*args)
            self.new_name_overlay.schedule()

        ybar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=scroll_vertical,
            style="Modern.Vertical.TScrollbar",
        )
        xbar = AutoHideScrollbar(
            parent,
            orient="horizontal",
            command=scroll_horizontal,
            style="Modern.Horizontal.TScrollbar",
        )
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=1, column=0, sticky="nsew")
        ybar.grid(row=1, column=1, sticky="ns")
        xbar.grid(row=2, column=0, sticky="ew")
        tree.tag_configure("blocked", foreground="#9b2c2c")
        tree.tag_configure("ready", foreground="#176b34")
        tree.tag_configure("unchanged", foreground=self.COLORS["warning"])
        self.result_scrollbar = ybar
        self.result_horizontal_scrollbar = xbar
        self.result_cell_tooltip = TreeCellToolTip(tree)
        return tree

    def _build_progress_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(7, 4))
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100, style="Modern.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, textvariable=self.progress_text_var, width=42).grid(row=0, column=1, sticky="e")
        status = ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor="w",
            padding=(8, 2),
        )
        status.pack(fill="x", side="bottom")
        ToolTip(status, "状态栏会提示当前结果和建议的下一步操作。")

    def _bind_change_tracking(self) -> None:
        match_variables = [
            self.directory_var,
            self.depth_mode_var,
            self.depth_var,
            self.search_var,
            self.regex_var,
            self.include_dirs_var,
            self.include_files_var,
        ]
        for variable in match_variables:
            variable.trace_add("write", self._on_match_input_changed)
        for variable in (self.replacement_var, self.rename_extension_var):
            variable.trace_add("write", self._on_preview_input_changed)
        self.preview_limit_var.trace_add("write", lambda *_: self._render_preview())
        self.search_entry.bind("<Return>", self._search_from_entry)
        self.replacement_entry.bind("<Return>", self._preview_from_replacement)

    def _search_from_entry(self, _event=None) -> str:
        self._start_search()
        return "break"

    def _preview_from_replacement(self, _event=None) -> str:
        self._start_preview()
        return "break"

    def _on_match_input_changed(self, *_args) -> None:
        if not self._busy and (
            self._last_matches is not None or self._last_scan is not None
        ):
            self._last_matches = None
            self._last_scan = None
            self.status_var.set("扫描条件已改变，请重新执行“扫描”。")
            self._render_preview()
        self._update_rule_feedback(validate_replacement=False)
        self._sync_command_states()

    def _on_preview_input_changed(self, *_args) -> None:
        if not self._busy and self._last_scan is not None:
            self._last_scan = None
            self.status_var.set("替换设置已改变，请重新生成“结果预览”。")
            self._render_preview()
        self._update_rule_feedback(validate_replacement=True)
        self._sync_command_states()

    def _update_rule_feedback(self, *, validate_replacement: bool) -> None:
        search_text = self.search_var.get()
        if not search_text:
            self.rule_feedback_var.set("请输入查找内容；该字段不能为空。")
            return
        try:
            RenameRule(
                search_text,
                self.replacement_var.get() if validate_replacement else "",
                use_regex=self.regex_var.get(),
                rename_extension=self.rename_extension_var.get(),
            )
        except RuleError as exc:
            self.rule_feedback_var.set(f"规则需要修正：{exc}")
        else:
            if self.regex_var.get():
                self.rule_feedback_var.set("正则规则有效。示例：查找 (\\d{4})-(\\d{2})，替换为 \\1\\2。")
            else:
                self.rule_feedback_var.set("普通文本规则有效；所有匹配片段都会被替换。")

    def _update_depth_state(self) -> None:
        state = (
            "normal"
            if not self._busy and self.depth_mode_var.get() == "limited"
            else "disabled"
        )
        self.depth_spin.configure(state=state)

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title="选择要扫描的根目录",
            initialdir=self.directory_var.get() or os.getcwd(),
            mustexist=True,
        )
        if selected:
            self.directory_var.set(selected)

    def _collect_match_options(self) -> MatchOptions:
        directory_text = self.directory_var.get().strip()
        if not directory_text:
            raise ScanError("请先选择要扫描的根目录")
        if not self.include_dirs_var.get() and not self.include_files_var.get():
            raise ScanError("请至少勾选“处理文件夹”或“处理文件”")
        max_depth = None
        if self.depth_mode_var.get() == "limited":
            try:
                max_depth = int(self.depth_var.get())
            except (ValueError, tk.TclError) as exc:
                raise ScanError("限制层级必须是大于或等于 1 的整数") from exc
            if max_depth < 1:
                raise ScanError("限制层级必须是大于或等于 1 的整数")
        RenameRule(
            self.search_var.get(),
            "",
            use_regex=self.regex_var.get(),
        )
        return MatchOptions(
            root=Path(directory_text),
            search=self.search_var.get(),
            use_regex=self.regex_var.get(),
            max_depth=max_depth,
            include_files=self.include_files_var.get(),
            include_dirs=self.include_dirs_var.get(),
        )

    def _start_search(self) -> None:
        if self._busy:
            return
        try:
            options = self._collect_match_options()
        except (RuleError, ScanError) as exc:
            messagebox.showwarning("设置需要修正", str(exc), parent=self.root)
            self.status_var.set(f"无法扫描：{exc}")
            return
        self._last_matches = None
        self._last_scan = None
        self._last_execution = None
        self.feature_menu.entryconfigure(self.result_details_menu_index, state="disabled")
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_text_var.set("正在读取目录，请稍候…")
        self.status_var.set("正在扫描匹配名称；此阶段不计算新名称，也不会修改磁盘。")
        threading.Thread(
            target=self._search_worker,
            args=(options,),
            daemon=True,
        ).start()

    def _search_worker(self, options: MatchOptions) -> None:
        try:
            result = search_matches(options)
        except Exception as exc:
            self._messages.put(("error", "扫描失败", str(exc)))
        else:
            self._messages.put(("match_done", result))

    def _handle_search_done(self, result: MatchResult) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self._set_busy(False)
        self._last_matches = result
        self._last_scan = None
        matched_total = len(result.items)
        self.stats_var.set(
            f"匹配：{matched_total}项 | 可修改：— | 名称未变化：— | 阻止执行：—"
        )
        self.progress_text_var.set(f"扫描完成：找到 {matched_total} 个名称匹配")
        self._render_preview()
        if matched_total:
            self.status_var.set("扫描完成。请填写替换内容，然后生成“结果预览”。")
        else:
            self.status_var.set("没有找到符合搜索条件的名称，请检查目录、层级和查找内容。")
        self._sync_command_states()
        if result.errors:
            messagebox.showwarning(
                "扫描完成，但有提示",
                f"已完成其余目录扫描，但有 {len(result.errors)} 个位置无法读取。\n\n"
                + "\n".join(result.errors[:8]),
                parent=self.root,
            )

    def _start_preview(self) -> None:
        if self._busy:
            return
        if self._last_matches is None:
            self.status_var.set("请先执行“扫描”，再生成结果预览。")
            return
        try:
            RenameRule(
                self._last_matches.search,
                self.replacement_var.get(),
                use_regex=self._last_matches.use_regex,
                rename_extension=self.rename_extension_var.get(),
            )
        except RuleError as exc:
            messagebox.showwarning("替换规则需要修正", str(exc), parent=self.root)
            self.status_var.set(f"无法生成预览：{exc}")
            return
        self._last_scan = None
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_text_var.set("正在计算新名称与安全状态…")
        self.status_var.set("正在生成结果预览；不会修改磁盘。")
        threading.Thread(
            target=self._preview_worker,
            args=(
                self._last_matches,
                self.replacement_var.get(),
                self.rename_extension_var.get(),
            ),
            daemon=True,
        ).start()

    def _preview_worker(
        self,
        matches: MatchResult,
        replacement: str,
        rename_extension: bool,
    ) -> None:
        try:
            result = build_preview(
                matches,
                replacement,
                rename_extension=rename_extension,
            )
        except Exception as exc:
            self._messages.put(("error", "预览失败", str(exc)))
        else:
            self._messages.put(("preview_done", result))

    def _handle_preview_done(self, result: ScanResult) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self._set_busy(False)
        self._last_scan = result
        summary = summarize_candidates(result.candidates)
        self.stats_var.set(
            f"匹配：{summary['matched_total']}项 | 可修改：{summary['ready_total']}项 | "
            f"名称未变化：{summary['unchanged_total']}项 | 阻止执行：{summary['blocked_total']}项"
        )
        self.progress_text_var.set(f"预览完成：已检查 {summary['matched_total']} 个匹配名称")
        self._render_preview()
        if summary["ready_total"]:
            self.status_var.set("预览已生成。请检查新名称和状态，确认无误后点击“确认执行”。")
        else:
            if summary["matched_total"]:
                self.status_var.set(
                    f"已匹配 {summary['matched_total']} 项，但本次没有可执行动作；请查看状态说明或调整替换内容。"
                )
            else:
                self.status_var.set("没有找到符合搜索条件的名称，请检查目录、层级和查找内容。")
        self._sync_command_states()

    def _render_preview(self) -> None:
        if not hasattr(self, "result_tree"):
            return
        try:
            limit = max(1, int(self.preview_limit_var.get()))
        except (ValueError, tk.TclError):
            return
        if self._last_scan is not None:
            self._fill_tree(
                self.result_tree,
                sorted_preview_items(self._last_scan.candidates, limit),
            )
        elif self._last_matches is not None:
            self._fill_matches(self.result_tree, self._last_matches.items[:limit])
        else:
            self._fill_tree(self.result_tree, [])

    def _fill_matches(
        self, tree: ttk.Treeview, items: Iterable[MatchedItem]
    ) -> None:
        tree.delete(*tree.get_children())
        for item in items:
            tree.insert(
                "",
                "end",
                values=(
                    item.kind.value,
                    str(item.source.parent),
                    item.source.name,
                    "",
                    "等待结果预览",
                    "填写替换内容后生成结果预览",
                ),
            )
        if tree is self.result_tree:
            self.new_name_overlay.schedule()

    def _fill_tree(
        self, tree: ttk.Treeview, items: Iterable[RenameCandidate]
    ) -> None:
        tree.delete(*tree.get_children())
        for item in items:
            if item.status is CandidateStatus.READY:
                tag = "ready"
            elif item.status is CandidateStatus.UNCHANGED:
                tag = "unchanged"
            else:
                tag = "blocked"
            tree.insert(
                "",
                "end",
                values=(
                    item.kind.value,
                    str(item.source.parent),
                    item.old_name,
                    item.new_name,
                    item.status.value,
                    item.detail,
                ),
                tags=(tag,),
            )
        if tree is self.result_tree:
            self.new_name_overlay.schedule()

    def _sync_command_states(self) -> None:
        if not hasattr(self, "preview_button"):
            return
        self.preview_button.configure(
            state=(
                "normal"
                if not self._busy and self._last_matches is not None
                else "disabled"
            )
        )
        ready = (
            self._last_scan is not None
            and any(
                item.status is CandidateStatus.READY
                for item in self._last_scan.candidates
            )
        )
        self.execute_button.configure(
            state="normal" if not self._busy and ready else "disabled"
        )
        self.feature_menu.entryconfigure(
            self.result_details_menu_index,
            state="normal" if not self._busy and self._last_execution is not None else "disabled",
        )

    def _confirm_execute(self) -> None:
        if self._busy or self._last_scan is None:
            return
        summary = summarize_candidates(self._last_scan.candidates)
        if not summary["ready_total"]:
            messagebox.showinfo("没有可执行项目", "当前预览中没有状态为“可修改”的项目。", parent=self.root)
            return
        depth_text = "全部层级" if self.depth_mode_var.get() == "all" else f"最多 {self.depth_var.get()} 层"
        directory_ready = sum(
            item.status is CandidateStatus.READY and item.kind is ItemKind.DIRECTORY
            for item in self._last_scan.candidates
        )
        file_ready = summary["ready_total"] - directory_ready
        confirmed = messagebox.askyesno(
            "确认一次性执行重命名",
            "即将修改磁盘上的名称，请再次核对：\n\n"
            f"根目录：{self._last_scan.root}\n"
            f"扫描范围：{depth_text}（根目录本身不修改）\n"
            f"可执行：{summary['ready_total']} 项\n"
            f"其中：文件夹 {directory_ready} 项，文件 {file_ready} 项\n"
            f"名称未变化：{summary['unchanged_total']} 项\n"
            f"因冲突或规则问题阻止：{summary['blocked_total']} 项\n\n"
            "执行后不能在本工具中自动撤销。是否继续？",
            icon="warning",
            parent=self.root,
        )
        if not confirmed:
            self.status_var.set("已取消执行，磁盘上的名称没有变化。")
            return
        candidates = list(self._last_scan.candidates)
        self._set_busy(True)
        self.progress.configure(mode="determinate", maximum=max(len(candidates), 1), value=0)
        self.progress_text_var.set(f"准备处理 0/{len(candidates)}")
        self.status_var.set("正在执行重命名，请勿关闭程序或移动正在处理的项目。")
        threading.Thread(target=self._execute_worker, args=(candidates,), daemon=True).start()

    def _execute_worker(self, candidates: list[RenameCandidate]) -> None:
        try:
            result = execute(
                candidates,
                progress=lambda current, total, record: self._messages.put(
                    ("progress", current, total, record)
                ),
            )
        except Exception as exc:
            self._messages.put(("error", "执行失败", str(exc)))
        else:
            self._messages.put(("execute_done", result))

    def _handle_progress(self, current: int, total: int, record: ExecutionRecord) -> None:
        self.progress.configure(maximum=max(total, 1), value=current)
        self.progress_text_var.set(
            f"{current}/{total}  {record.outcome}：{record.source.name}"
        )

    def _handle_execute_done(self, result: ExecutionResult) -> None:
        self._set_busy(False)
        self._last_execution = result
        self._last_matches = None
        self._last_scan = None
        self._sync_command_states()
        self.progress.configure(value=max(len(result.records), 1))
        self.progress_text_var.set(
            f"完成：成功 {result.succeeded}，跳过 {result.skipped}，失败 {result.failed}"
        )
        self.status_var.set("批量处理已结束。可查看结果详情；如需继续修改，请重新扫描。")
        level = messagebox.showinfo if result.failed == 0 else messagebox.showwarning
        level(
            "处理完成",
            f"成功：{result.succeeded} 项\n跳过：{result.skipped} 项\n失败：{result.failed} 项\n\n"
            "可从顶部“功能 → 结果详情”查看每一项的处理记录。",
            parent=self.root,
        )

    def _poll_messages(self) -> None:
        try:
            while True:
                message = self._messages.get_nowait()
                kind = message[0]
                if kind == "match_done":
                    self._handle_search_done(message[1])
                elif kind == "preview_done":
                    self._handle_preview_done(message[1])
                elif kind == "progress":
                    self._handle_progress(message[1], message[2], message[3])
                elif kind == "execute_done":
                    self._handle_execute_done(message[1])
                elif kind == "error":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self._set_busy(False)
                    self.progress_text_var.set(message[1])
                    self.status_var.set(f"{message[1]}：{message[2]}")
                    messagebox.showerror(message[1], message[2], parent=self.root)
        except queue.Empty:
            pass
        finally:
            if self.root.winfo_exists():
                self.root.after(self.POLL_INTERVAL_MS, self._poll_messages)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.preview_button.configure(state=state)
        for widget in self._input_widgets:
            widget.configure(state=state)
        self.regex_category_selector.configure(
            state="disabled" if busy else "readonly"
        )
        self.regex_template_list.configure(state=state)
        self.regex_apply_button.configure(state=state)
        if busy:
            self.execute_button.configure(state="disabled")
        self._update_depth_state()
        self._sync_command_states()

    def _show_about(self) -> None:
        def build(window: tk.Toplevel) -> None:
            outer = ttk.Frame(window, style="App.TFrame", padding=18)
            outer.pack(fill="both", expand=True)
            header = ttk.Frame(outer, style="Header.TFrame", padding=14)
            header.pack(fill="x", pady=(0, 10))
            if self._header_icon is not None:
                ttk.Label(header, image=self._header_icon, style="Icon.TLabel").pack(
                    side="left", padx=(0, 12)
                )
            title = ttk.Frame(header, style="Header.TFrame")
            title.pack(side="left", fill="x", expand=True)
            ttk.Label(title, text="批量重命名", style="HeaderTitle.TLabel").pack(anchor="w")
            ttk.Label(
                title,
                text="面向 Windows 多层目录的安全名称整理工具",
                style="HeaderSubtitle.TLabel",
            ).pack(anchor="w", pady=(2, 0))
            ttk.Label(
                header,
                text=f"v{__version__}",
                style="HeaderSubtitle.TLabel",
                padding=(8, 4),
            ).pack(side="right")

            content = (
                f"版本：{__version__}\n\n"
                "当前已经实现\n"
                "• 扫描匹配与结果预览分离的两阶段工作流\n"
                "• 文件夹和文件统一分类排序、冲突拦截与执行确认\n"
                "• 普通文本、正则表达式、经典正则模板与一键应用\n"
                "• 多层目录、扩展名保护、处理进度和结果详情\n\n"
                "正在开发中\n"
                "• 撤回管理（开发中）\n"
                "• 操作日志（开发中）\n\n"
                "本软件处于快速开发期，预发行版本可能继续调整界面和数据格式。\n"
                "重要目录请先备份；名称规则、预览结果及最终执行由使用者自行确认。"
            )
            self.about_content_var = tk.StringVar(window, value=content)
            ttk.Label(
                outer,
                textvariable=self.about_content_var,
                style="Card.TLabel",
                justify="left",
                wraplength=600,
                padding=(14, 12),
            ).pack(fill="both", expand=True)
            contact = ttk.Frame(outer, style="Card.TFrame", padding=(14, 9))
            contact.pack(fill="x", pady=(10, 0))
            ttk.Label(contact, text="联系作者", style="Field.TLabel").pack(side="left")
            self.about_email_var = tk.StringVar(window, value="lo.c@live.cn")
            self.about_email_entry = ttk.Entry(
                contact,
                textvariable=self.about_email_var,
                state="readonly",
                style="Modern.TEntry",
                width=24,
            )
            self.about_email_entry.pack(side="right")

        self.dialogs.open(
            "about", title="关于批量重命名", size=(670, 570), build=build
        )

    def _show_execution_details(self) -> None:
        if self._last_execution is None:
            return
        execution = self._last_execution

        def build(window: tk.Toplevel) -> None:
            frame = ttk.Frame(window, padding=10)
            frame.pack(fill="both", expand=True)
            ttk.Label(
                frame,
                text=(
                    f"成功 {execution.succeeded} 项；"
                    f"跳过 {execution.skipped} 项；失败 {execution.failed} 项"
                ),
                style="Stats.TLabel",
            ).pack(anchor="w", pady=(0, 8))
            text = tk.Text(frame, wrap="none", font=("Consolas", 9))
            ybar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            xbar = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
            text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
            text.pack(side="left", fill="both", expand=True)
            ybar.pack(side="right", fill="y")
            for index, record in enumerate(execution.records, start=1):
                text.insert(
                    "end",
                    f"{index:>4}. [{record.outcome}] {record.kind.value}\n"
                    f"      原：{record.source}\n      新：{record.target}\n"
                    f"      说明：{record.detail}\n\n",
                )
            text.configure(state="disabled")
            xbar.pack(side="bottom", fill="x")

        self.dialogs.open(
            "execution-details",
            title="重命名结果详情",
            size=(900, 540),
            build=build,
        )

    def _apply_regex_example(
        self, example: RegexExample, window: tk.Toplevel | None = None
    ) -> None:
        if self._busy:
            return
        self.search_var.set(example.search)
        self.replacement_var.set(example.replacement)
        self.regex_var.set(True)
        self.rename_extension_var.set(example.rename_extension)
        self.status_var.set(f"已应用正则模板：{example.title}。请按实际名称调整后生成结果预览。")
        if window is not None:
            window.destroy()
        elif getattr(self, "active_tool_panel", None) == "templates":
            self._close_tool_panel()

    def _show_regex_examples_window_legacy(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("常用正则模板")
        window.geometry("920x580")
        window.minsize(820, 520)
        window.transient(self.root)
        window.grab_set()
        self.regex_examples_window = window

        outer = ttk.Frame(window, style="App.TFrame", padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="从常用场景选择规则", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            outer,
            text="先按用途分类，再查看真实处理前后效果；一键应用只填写规则，不会立即修改文件。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 12))

        navigation = ttk.Frame(outer, style="Card.TFrame", padding=12)
        navigation.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        navigation.columnconfigure(0, weight=1)
        navigation.rowconfigure(3, weight=1)
        ttk.Label(navigation, text="模板分类", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        categories = tuple(dict.fromkeys(example.category for example in REGEX_EXAMPLES))
        self.regex_category_var = tk.StringVar(window, value=categories[0])
        self.regex_category_selector = ttk.Combobox(
            navigation,
            textvariable=self.regex_category_var,
            values=categories,
            state="readonly",
            width=18,
            style="Modern.TCombobox",
        )
        self.regex_category_selector.grid(row=1, column=0, sticky="ew", pady=(0, 11))
        ttk.Label(navigation, text="可用规则", style="CardTitle.TLabel").grid(
            row=2, column=0, sticky="w", pady=(0, 7)
        )
        list_frame = ttk.Frame(navigation, style="Card.TFrame")
        list_frame.grid(row=3, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.regex_template_list = tk.Listbox(
            list_frame,
            exportselection=False,
            activestyle="none",
            font=("Microsoft YaHei UI", 10),
            width=21,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            highlightcolor=self.COLORS["accent"],
            background="#F8FAFC",
            foreground=self.COLORS["text"],
            selectbackground=self.COLORS["accent"],
            selectforeground="#FFFFFF",
        )
        self.regex_template_list.grid(row=0, column=0, sticky="nsew")
        list_scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.regex_template_list.yview,
            style="Modern.Vertical.TScrollbar",
        )
        list_scrollbar.grid(row=0, column=1, sticky="ns")
        self.regex_template_list.configure(yscrollcommand=list_scrollbar.set)

        details = ttk.Frame(outer, style="Card.TFrame", padding=16)
        details.grid(row=2, column=1, sticky="nsew")
        details.columnconfigure(1, weight=1)
        ttk.Label(details, text="规则说明", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        self.regex_purpose_var = tk.StringVar(window)
        ttk.Label(
            details,
            textvariable=self.regex_purpose_var,
            style="Card.TLabel",
            wraplength=590,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self.regex_example_search_var = tk.StringVar(window)
        self.regex_example_replacement_var = tk.StringVar(window)
        ttk.Label(details, text="查找表达式", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.regex_search_entry = ttk.Entry(
            details,
            textvariable=self.regex_example_search_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 10),
        )
        self.regex_search_entry.grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(details, text="替换内容", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.regex_replacement_entry = ttk.Entry(
            details,
            textvariable=self.regex_example_replacement_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 10),
        )
        self.regex_replacement_entry.grid(row=3, column=1, sticky="ew", pady=5)

        preview = ttk.Frame(details, style="Card.TFrame")
        preview.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        preview.columnconfigure(1, weight=1)
        self.regex_before_var = tk.StringVar(window)
        self.regex_after_var = tk.StringVar(window)
        ttk.Label(preview, text="处理前", style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            preview,
            textvariable=self.regex_before_var,
            style="Card.TLabel",
            font=("Microsoft YaHei UI", 10),
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(preview, text="处理后", style="Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(9, 0)
        )
        ttk.Label(
            preview,
            textvariable=self.regex_after_var,
            style="Card.TLabel",
            foreground=self.COLORS["ready"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(9, 0))

        self.regex_option_note_var = tk.StringVar(window)
        ttk.Label(
            details,
            textvariable=self.regex_option_note_var,
            style="Hint.TLabel",
            wraplength=620,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 8))
        self.regex_apply_button = ttk.Button(
            details,
            text="一键应用此规则",
            style="Accent.TButton",
        )
        self.regex_apply_button.grid(row=6, column=1, sticky="e", pady=(10, 0))

        def show_selected(_event=None) -> None:
            selection = self.regex_template_list.curselection()
            if not selection or not self._visible_regex_examples:
                return
            example = self._visible_regex_examples[selection[0]]
            self.regex_purpose_var.set(example.purpose)
            self.regex_example_search_var.set(example.search)
            self.regex_example_replacement_var.set(
                example.replacement or "（空文本：删除匹配内容）"
            )
            self.regex_before_var.set(example.before)
            self.regex_after_var.set(example.after)
            self.regex_option_note_var.set(
                "应用后会自动开启“包含扩展名”；请特别核对扩展名变化。"
                if example.rename_extension
                else "应用后保留文件扩展名；仍可在主窗口按实际需要调整选项。"
            )
            self.regex_apply_button.configure(
                command=lambda selected=example: self._apply_regex_example(selected, window)
            )

        def filter_category(_event=None) -> None:
            category = self.regex_category_var.get()
            self._visible_regex_examples = [
                example for example in REGEX_EXAMPLES if example.category == category
            ]
            self.regex_template_list.delete(0, "end")
            for example in self._visible_regex_examples:
                self.regex_template_list.insert("end", example.title)
            if self._visible_regex_examples:
                self.regex_template_list.selection_set(0)
                self.regex_template_list.activate(0)
                show_selected()

        self.regex_category_selector.bind("<<ComboboxSelected>>", filter_category)
        self.regex_template_list.bind("<<ListboxSelect>>", show_selected)
        self.regex_template_list.bind(
            "<Double-Button-1>",
            lambda _event: self.regex_apply_button.invoke(),
        )
        filter_category()

    def _show_regex_examples(self) -> None:
        self._toggle_tool_panel("templates")

    def _show_help(self) -> None:
        help_text = """使用流程

1. 在左侧选择根目录。根目录本身不会改名，只处理其内部项目。
2. 选择普通文本或正则表达式，填写查找内容，点击“扫描”或在查找框按 Enter。扫描只列出名称匹配项，不要求替换内容，也不会修改磁盘。
3. 填写“替换为”，点击“结果预览”或在替换框按 Enter。预览使用刚才的匹配快照计算新名称和安全状态，不会再次读取目录。
4. 在统一结果表中按“类型、所在目录、原名称、新名称、状态、说明”检查结果；文件夹排在文件之前，同类项目按名称排列。新名称使用青绿色便于对照，长内容被缩短时，把鼠标停在对应位置可查看完整文字。
5. 点击“确认执行”，核对汇总并二次确认。执行期间会显示逐项进度，完成后可从“功能 → 结果详情”查看记录。
6. 层级、文件夹/文件范围和扩展名保护位于左下角“设置”；正则模板与设置互斥显示，再次点击、按 Esc 或点击结果区会收起。

普通文本模式

查找内容按原样匹配，并替换名称中的每一处。例如查找“旧版”、替换为“新版”。替换内容可留空，表示删除匹配文本。

正则表达式模式

不熟悉语法时，点击左下角“正则模板”，按日期、编号、标签、文本清理、片段或扩展名选择常见场景。模板会先显示处理前后效果；点击“一键应用此规则”只会填写主窗口，不会立即修改文件。输入的表达式或捕获组引用无效时，规则说明区会立即提示。

文件扩展名

默认只修改文件主名称，保护最后一个扩展名。例如查找 jpg 不会改变“照片.jpg”的扩展名。只有在“设置”中明确勾选“允许修改扩展名”后，才会处理完整文件名。

安全与跳过策略

工具不会覆盖已有项目。目标已存在、多个项目生成同一目标、名称含 Windows 非法字符、名称为空或使用 CON 等保留名时，预览会用红色标出并跳过。执行前还会再次检查磁盘状态。子项目先于父文件夹处理；符号链接不会被跟随。

注意：执行完成后本工具不提供自动撤销。建议对重要目录先备份，并认真检查预览。"""
        def build(window: tk.Toplevel) -> None:
            frame = ttk.Frame(window, padding=12)
            frame.pack(fill="both", expand=True)
            text = tk.Text(
                frame,
                wrap="word",
                padx=10,
                pady=10,
                font=("Microsoft YaHei UI", 10),
                spacing2=3,
            )
            scrollbar = ttk.Scrollbar(
                frame,
                orient="vertical",
                command=text.yview,
                style="Modern.Vertical.TScrollbar",
            )
            text.configure(yscrollcommand=scrollbar.set)
            text.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            text.insert("1.0", help_text)
            text.configure(state="disabled")

        self.dialogs.open(
            "help", title="使用说明", size=(760, 640), build=build
        )

    def _on_close(self) -> None:
        if self._busy:
            messagebox.showwarning(
                "操作正在进行",
                "当前操作尚未结束。为避免部分处理，请等待进度完成后再关闭程序。",
                parent=self.root,
            )
            return
        self.root.destroy()


def run() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
    root = tk.Tk()
    BatchRenameApp(root)
    root.mainloop()
