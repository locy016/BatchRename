"""Tkinter 图形界面。"""

from __future__ import annotations

import os
import queue
import re
import sys
import threading
import tkinter as tk
import ctypes
from dataclasses import dataclass, replace
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
from .preferences import (
    AppPreferences,
    default_preferences_path,
    load_preferences,
    normalize_appearance,
    resolve_appearance,
    save_preferences,
    system_prefers_light,
)


MIN_WINDOW_WIDTH = 1120
MIN_WINDOW_HEIGHT = 720
THEME_PALETTES = {
    "light": {
        "background": "#F6F7F9",
        "card": "#FFFFFF",
        "surface_alt": "#F1F3F6",
        "sidebar": "#F0F2F5",
        "sidebar_active": "#E2E5FF",
        "navy": "#172033",
        "navy_soft": "#344054",
        "accent": "#5B5BD6",
        "accent_hover": "#4848B8",
        "text": "#182230",
        "muted": "#667085",
        "border": "#E4E7EC",
        "selection": "#E4E7FF",
        "input": "#FFFFFF",
        "disabled": "#D0D5DD",
        "ready": "#16875B",
        "warning": "#B4690E",
        "blocked": "#C43D4B",
        "tooltip": "#FFFFFF",
        "tooltip_border": "#C7CDD6",
    },
    "dark": {
        "background": "#0F1115",
        "card": "#171A21",
        "surface_alt": "#20242D",
        "sidebar": "#14171D",
        "sidebar_active": "#292D5C",
        "navy": "#F4F6F8",
        "navy_soft": "#D0D5DD",
        "accent": "#8B8CFF",
        "accent_hover": "#A5A6FF",
        "text": "#F3F4F6",
        "muted": "#98A2B3",
        "border": "#2D3440",
        "selection": "#2C3261",
        "input": "#11141A",
        "disabled": "#4B5563",
        "ready": "#45C18B",
        "warning": "#F0A44B",
        "blocked": "#F26B77",
        "tooltip": "#20242D",
        "tooltip_border": "#475467",
    },
}


def theme_palette(mode: str) -> dict[str, str]:
    """返回完整的现代浅色或深色语义色板副本。"""

    resolved = mode if mode in THEME_PALETTES else "light"
    return dict(THEME_PALETTES[resolved])


RESULT_FIXED_COLUMN_WIDTHS = {"kind": 44, "status": 48, "detail": 44}
RESULT_ELASTIC_MINIMUMS = {
    "compact": {"parent": 90, "old": 130, "new": 150},
    "standard": {"parent": 120, "old": 160, "new": 180},
    "spacious": {"parent": 160, "old": 220, "new": 250},
}
RESULT_ELASTIC_RATIOS = {"parent": 0.26, "old": 0.34, "new": 0.40}
RESULT_TABLE_BORDER_RESERVE = 4
RESULT_ICON_COLORS = {
    "neutral": "#284B6B",
    "ready": "#177245",
    "warning": "#A76500",
    "blocked": "#A53A3A",
    "pending": "#0F8B8D",
    "info": "#2F6F9F",
}


@dataclass(frozen=True, slots=True)
class ResultIconSpec:
    """结果表图标的绘制、颜色、悬浮文字与动作定义。"""

    shape: str
    color_name: str
    color: str
    tooltip: str
    actionable: bool


def result_icon_spec(column: str, value: str) -> ResultIconSpec:
    """把结果表完整文字转换为不丢失语义的图标规格。"""

    text = str(value)
    if column == "kind":
        shape = "folder" if text == ItemKind.DIRECTORY.value else "file"
        color_name = "neutral"
        heading = "类型"
        actionable = False
    elif column == "status":
        heading = "状态"
        actionable = True
        if text == CandidateStatus.READY.value:
            shape, color_name = "check", "ready"
        elif text == CandidateStatus.UNCHANGED.value:
            shape, color_name = "minus", "warning"
        elif text == "等待结果预览":
            shape, color_name = "clock", "pending"
        else:
            shape, color_name = "warning", "blocked"
    else:
        shape, color_name = "info", "info"
        heading = "说明"
        actionable = True
    return ResultIconSpec(
        shape=shape,
        color_name=color_name,
        color=RESULT_ICON_COLORS[color_name],
        tooltip=f"{heading}\n{text}",
        actionable=actionable,
    )


def calculate_result_column_widths(total_width: int, mode: str) -> dict[str, int]:
    """按可用宽度返回固定图标列和弹性文字列的精确宽度。"""

    fixed_total = sum(RESULT_FIXED_COLUMN_WIDTHS.values())
    elastic_total = max(3, int(total_width) - fixed_total)
    preferred = RESULT_ELASTIC_MINIMUMS.get(
        mode, RESULT_ELASTIC_MINIMUMS["standard"]
    )
    preferred_total = sum(preferred.values())
    elastic: dict[str, int] = {}
    if elastic_total >= preferred_total:
        extra = elastic_total - preferred_total
        elastic["parent"] = preferred["parent"] + round(
            extra * RESULT_ELASTIC_RATIOS["parent"]
        )
        elastic["old"] = preferred["old"] + round(
            extra * RESULT_ELASTIC_RATIOS["old"]
        )
        elastic["new"] = elastic_total - elastic["parent"] - elastic["old"]
    else:
        elastic["parent"] = max(
            1, elastic_total * preferred["parent"] // preferred_total
        )
        elastic["old"] = max(
            1, elastic_total * preferred["old"] // preferred_total
        )
        elastic["new"] = elastic_total - elastic["parent"] - elastic["old"]
    return {
        "kind": RESULT_FIXED_COLUMN_WIDTHS["kind"],
        "parent": elastic["parent"],
        "old": elastic["old"],
        "new": elastic["new"],
        "status": RESULT_FIXED_COLUMN_WIDTHS["status"],
        "detail": RESULT_FIXED_COLUMN_WIDTHS["detail"],
    }


def layout_mode_for_width(width: int) -> str:
    """根据主窗口客户区宽度返回响应式布局档位。"""

    if width >= 1440:
        return "spacious"
    if width >= 1120:
        return "standard"
    return "compact"


def layout_mode_for_size(width: int, height: int) -> str:
    """根据客户区尺寸选择布局，竖向窗口始终使用紧凑工作台。"""

    if width / max(1, height) < 1.15:
        return "compact"
    return layout_mode_for_width(width)


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


@dataclass(frozen=True, slots=True)
class DirectoryInventoryView:
    """目录概况栏使用的稳定显示值。"""

    folder_count: str
    file_count: str
    state: str
    warning: str


def directory_scope_text(mode: str, depth: int) -> str:
    """把扫描层级设置转换为目录概况中的简短说明。"""

    return "全部层级" if mode == "all" else f"最多 {max(1, int(depth))} 层"


def directory_inventory_view(
    snapshot: MatchResult | None,
    *,
    scanning: bool = False,
) -> DirectoryInventoryView:
    """返回扫描前、扫描中或扫描完成后的目录概况文字。"""

    if scanning:
        return DirectoryInventoryView("—", "—", "正在统计", "")
    if snapshot is None:
        return DirectoryInventoryView("—", "—", "尚未扫描", "")
    error_count = len(snapshot.errors)
    return DirectoryInventoryView(
        folder_count=str(snapshot.scanned_directory_count),
        file_count=str(snapshot.scanned_file_count),
        state="扫描完成",
        warning=f"{error_count} 处无法读取" if error_count else "",
    )


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
        layout_mode=layout_mode_for_size(width, height),
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


def result_parent_text(root: Path, source: Path) -> str:
    """返回项目父目录相对于当前扫描根目录的显示文字。"""

    try:
        relative_parent = source.parent.relative_to(root)
    except ValueError:
        return str(source.parent)
    return "（根目录）" if relative_parent == Path(".") else str(relative_parent)


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

    def __init__(self, tree: ttk.Treeview, colors: dict[str, str] | None = None) -> None:
        self.tree = tree
        self.colors = colors or theme_palette("light")
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
            background=self.colors["tooltip"],
            foreground=self.colors["text"],
            relief="solid",
            borderwidth=1,
            highlightbackground=self.colors["tooltip_border"],
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

    def set_colors(self, colors: dict[str, str]) -> None:
        """更新下一次显示使用的外观，并关闭仍显示的旧主题提示。"""

        self.hide()
        self.colors = colors

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

    def __init__(
        self,
        widget: tk.Misc,
        text: str,
        colors: dict[str, str] | None = None,
    ) -> None:
        self.widget = widget
        self.text = text
        self.colors = colors or theme_palette("light")
        self.window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.after_id = self.widget.after(500, self._show)

    def set_text(self, text: str) -> None:
        """更新说明文字；已显示的旧提示会先关闭，避免内容残留。"""

        if text != self.text:
            self._hide()
            self.text = text

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
            background=self.colors["tooltip"],
            foreground=self.colors["text"],
            relief="solid",
            borderwidth=1,
            highlightbackground=self.colors["tooltip_border"],
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

    def set_colors(self, colors: dict[str, str]) -> None:
        """更新提示配色，已展开的提示会在下次悬停时使用新主题。"""

        self._hide()
        self.colors = colors

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
        tooltip_colors: dict[str, str] | None = None,
    ) -> None:
        self.tree = tree
        self.column = column
        self.foreground = foreground
        self.background = background
        self.selected_background = selected_background
        self.tooltip_colors = tooltip_colors or theme_palette("light")
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
            tooltip.set_text(f"新名称\n{text}")
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
            self._tooltips.append(ToolTip(label, "", self.tooltip_colors))
        return self._labels[index], self._tooltips[index]

    def set_theme(
        self,
        *,
        foreground: str,
        background: str,
        selected_background: str,
        tooltip_colors: dict[str, str],
    ) -> None:
        self.foreground = foreground
        self.background = background
        self.selected_background = selected_background
        self.tooltip_colors = tooltip_colors
        for label, tooltip in zip(self._labels, self._tooltips):
            label.configure(foreground=foreground, background=background)
            tooltip.set_colors(tooltip_colors)
        self.schedule()

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
        for label, tooltip in zip(self._labels[index:], self._tooltips[index:]):
            tooltip._hide()
            label.place_forget()


class TreeCellIconOverlay:
    """把结果表的类型、状态和说明文字覆盖为紧凑语义图标。"""

    COLUMNS = ("kind", "status", "detail")

    def __init__(
        self,
        tree: ttk.Treeview,
        *,
        background: str,
        selected_background: str,
        tooltip_colors: dict[str, str] | None = None,
        icon_colors: dict[str, str] | None = None,
        on_activate: Callable[[str, str], None] | None = None,
    ) -> None:
        self.tree = tree
        self.background = background
        self.selected_background = selected_background
        self.tooltip_colors = tooltip_colors or theme_palette("light")
        self.icon_colors = icon_colors or RESULT_ICON_COLORS
        self.on_activate = on_activate
        self._canvases: list[tk.Canvas] = []
        self._tooltips: list[ToolTip] = []
        self._refresh_id: str | None = None
        self.tree.bind("<Configure>", self.schedule, add="+")
        self.tree.bind("<Expose>", self.schedule, add="+")
        self.tree.bind("<<TreeviewSelect>>", self.schedule, add="+")
        self.tree.bind("<MouseWheel>", self.schedule, add="+")
        self.tree.bind("<Button-4>", self.schedule, add="+")
        self.tree.bind("<Button-5>", self.schedule, add="+")

    @property
    def visible_icon_data(self) -> tuple[tuple[str, str, str, str], ...]:
        """返回当前可见图标的行、列、形状和完整悬浮文字。"""

        data: list[tuple[str, str, str, str]] = []
        for canvas, tooltip in zip(self._canvases, self._tooltips):
            if canvas.winfo_manager() != "place":
                continue
            data.append(
                (
                    getattr(canvas, "_tree_item_id", ""),
                    getattr(canvas, "_tree_column", ""),
                    getattr(canvas, "_icon_shape", ""),
                    tooltip.text,
                )
            )
        return tuple(data)

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
            for column in self.COLUMNS:
                bounds = self.tree.bbox(item_id, column)
                if not bounds:
                    continue
                x, y, width, height = bounds
                if width <= 2 or height <= 2:
                    continue
                canvas, tooltip = self._canvas_at(visible_index)
                spec = result_icon_spec(column, self.tree.set(item_id, column))
                spec = replace(
                    spec,
                    color=self.icon_colors.get(spec.color_name, spec.color),
                )
                background = (
                    self.selected_background if item_id in selection else self.background
                )
                canvas.configure(
                    background=background,
                    cursor="hand2" if spec.actionable else "arrow",
                )
                canvas.delete("all")
                self._draw_icon(canvas, spec, width - 2, height - 2)
                canvas._tree_item_id = item_id  # type: ignore[attr-defined]
                canvas._tree_column = column  # type: ignore[attr-defined]
                canvas._icon_shape = spec.shape  # type: ignore[attr-defined]
                canvas._icon_actionable = spec.actionable  # type: ignore[attr-defined]
                tooltip.set_text(spec.tooltip)
                canvas.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)
                canvas.tk.call("raise", canvas._w)
                visible_index += 1
        self._hide_from(visible_index)

    def _canvas_at(self, index: int) -> tuple[tk.Canvas, ToolTip]:
        if index == len(self._canvases):
            canvas = tk.Canvas(
                self.tree,
                borderwidth=0,
                highlightthickness=0,
                background=self.background,
                takefocus=False,
            )
            canvas.bind("<Button-1>", lambda _event, target=canvas: self._activate(target))
            canvas.bind("<MouseWheel>", self._scroll, add="+")
            canvas.bind("<Button-4>", lambda _event: self._scroll_lines(-1), add="+")
            canvas.bind("<Button-5>", lambda _event: self._scroll_lines(1), add="+")
            self._canvases.append(canvas)
            self._tooltips.append(ToolTip(canvas, "", self.tooltip_colors))
        return self._canvases[index], self._tooltips[index]

    def set_theme(
        self,
        *,
        background: str,
        selected_background: str,
        tooltip_colors: dict[str, str],
        icon_colors: dict[str, str],
    ) -> None:
        self.background = background
        self.selected_background = selected_background
        self.tooltip_colors = tooltip_colors
        self.icon_colors = icon_colors
        for canvas, tooltip in zip(self._canvases, self._tooltips):
            canvas.configure(background=background)
            tooltip.set_colors(tooltip_colors)
        self.schedule()

    @staticmethod
    def _draw_icon(
        canvas: tk.Canvas,
        spec: ResultIconSpec,
        width: int,
        height: int,
    ) -> None:
        cx = max(1, width) / 2
        cy = max(1, height) / 2
        color = spec.color
        shape = spec.shape
        if shape == "folder":
            canvas.create_polygon(
                cx - 9, cy - 6,
                cx - 2, cy - 6,
                cx + 1, cy - 3,
                cx + 9, cy - 3,
                cx + 9, cy + 7,
                cx - 9, cy + 7,
                fill=color,
                outline=color,
            )
        elif shape == "file":
            canvas.create_polygon(
                cx - 7, cy - 8,
                cx + 3, cy - 8,
                cx + 7, cy - 4,
                cx + 7, cy + 8,
                cx - 7, cy + 8,
                fill="",
                outline=color,
                width=2,
            )
            canvas.create_line(cx + 3, cy - 8, cx + 3, cy - 4, cx + 7, cy - 4, fill=color)
            canvas.create_line(cx - 4, cy, cx + 4, cy, fill=color)
            canvas.create_line(cx - 4, cy + 4, cx + 4, cy + 4, fill=color)
        elif shape in {"check", "minus", "clock", "info"}:
            radius = 8
            canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline=color,
            )
            if shape == "check":
                canvas.create_line(
                    cx - 4, cy,
                    cx - 1, cy + 3,
                    cx + 5, cy - 4,
                    fill="white",
                    width=2,
                    capstyle="round",
                    joinstyle="round",
                )
            elif shape == "minus":
                canvas.create_line(cx - 4, cy, cx + 4, cy, fill="white", width=2)
            elif shape == "clock":
                canvas.create_line(cx, cy, cx, cy - 4, fill="white", width=2)
                canvas.create_line(cx, cy, cx + 4, cy + 2, fill="white", width=2)
            else:
                canvas.create_text(
                    cx,
                    cy,
                    text="i",
                    fill="white",
                    font=("Segoe UI", 9, "bold"),
                )
        else:
            canvas.create_polygon(
                cx, cy - 9,
                cx + 9, cy + 7,
                cx - 9, cy + 7,
                fill=color,
                outline=color,
            )
            canvas.create_text(
                cx,
                cy + 2,
                text="!",
                fill="white",
                font=("Segoe UI", 9, "bold"),
            )

    def _activate(self, canvas: tk.Canvas) -> str:
        item_id = getattr(canvas, "_tree_item_id", "")
        column = getattr(canvas, "_tree_column", "")
        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
        if (
            item_id
            and column
            and getattr(canvas, "_icon_actionable", False)
            and self.on_activate is not None
        ):
            self.on_activate(item_id, column)
        return "break"

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
        for canvas, tooltip in zip(
            self._canvases[index:], self._tooltips[index:]
        ):
            tooltip._hide()
            canvas.place_forget()


class BatchRenameApp:
    """批量重命名主窗口。"""

    POLL_INTERVAL_MS = 80
    RESPONSIVE_DELAY_MS = 120
    RAIL_WIDTHS = {"compact": 64, "standard": 288, "spacious": 304}
    COLORS = theme_palette("light")

    def __init__(
        self,
        root: tk.Tk,
        *,
        work_area_provider: Callable[[tk.Misc], tuple[int, int, int, int]] = _pointer_monitor_work_area,
        preferences_path: Path | None = None,
        system_light_provider: Callable[[], bool] = system_prefers_light,
    ) -> None:
        self.root = root
        self.preferences_path = (
            default_preferences_path()
            if preferences_path is None
            else Path(preferences_path)
        )
        self.system_light_provider = system_light_provider
        preferences = load_preferences(self.preferences_path)
        self.requested_appearance = preferences.appearance
        self.resolved_appearance = resolve_appearance(
            self.requested_appearance,
            self.system_light_provider,
        )
        self.COLORS = theme_palette(self.resolved_appearance)
        self._app_tooltips: list[ToolTip] = []
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
        self.matched_count_var = tk.StringVar(value="0")
        self.ready_count_var = tk.StringVar(value="0")
        self.unchanged_count_var = tk.StringVar(value="0")
        self.blocked_count_var = tk.StringVar(value="0")
        self.match_stat_value_vars = (
            self.matched_count_var,
            self.ready_count_var,
            self.unchanged_count_var,
            self.blocked_count_var,
        )
        self.status_var = tk.StringVar(value="请设置目录和规则，然后点击“结果预览”。")
        self.progress_text_var = tk.StringVar(value="等待操作")
        self.appearance_var = tk.StringVar(value=self.requested_appearance)
        self.directory_context_path_var = tk.StringVar(value=self.directory_var.get())
        self.directory_context_scope_var = tk.StringVar(
            value=directory_scope_text(self.depth_mode_var.get(), self.depth_var.get())
        )
        self.directory_folder_count_var = tk.StringVar(value="—")
        self.directory_file_count_var = tk.StringVar(value="—")
        self.directory_inventory_state_var = tk.StringVar(value="尚未扫描")
        self.directory_inventory_warning_var = tk.StringVar()

        self._messages: queue.Queue[tuple] = queue.Queue()
        self._busy = False
        self._input_widgets: list[ttk.Widget] = []
        self._last_matches: MatchResult | None = None
        self._last_scan: ScanResult | None = None
        self._last_execution: ExecutionResult | None = None
        self._inventory_scanning = False
        self._result_row_details: dict[str, dict[str, str]] = {}
        self._responsive_after_id: str | None = None
        self._last_responsive_size: tuple[int, int] | None = None
        self._last_result_width: tuple[int, str] | None = None
        self.current_layout_mode = self.initial_window_layout.layout_mode
        self._app_icon: tk.PhotoImage | None = None
        self._header_icon: tk.PhotoImage | None = None
        self.dialogs = ManagedDialogs(self.root)

        self._configure_style()
        self._load_application_icon()
        self._build_ui()
        self._apply_responsive_layout(*self.initial_window_layout.size)
        self.root.bind("<Configure>", self._schedule_responsive_layout, add="+")
        self.root.bind("<FocusIn>", self._on_root_focus_for_theme, add="+")
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
            padding=(10, 7),
            font=("Microsoft YaHei UI", 9),
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
            padding=(10, 7),
            font=("Microsoft YaHei UI", 9),
            focuscolor="#C7D8E5",
        )
        style.map("WorkflowSecondary.TButton", background=[("active", "#D2E0E9")])
        style.configure(
            "WorkflowFinal.TButton",
            background=colors["navy"],
            foreground=colors["card"],
            borderwidth=0,
            padding=(10, 7),
            font=("Microsoft YaHei UI", 9),
            focuscolor=colors["selection"],
        )
        style.map(
            "WorkflowFinal.TButton",
            background=[("active", colors["navy_soft"]), ("disabled", colors["surface_alt"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.configure(
            "WorkflowTool.TButton",
            background=colors["sidebar"],
            foreground=colors["navy_soft"],
            borderwidth=1,
            relief="solid",
            padding=(10, 6),
            font=("Microsoft YaHei UI", 9),
            focuscolor=colors["selection"],
        )
        style.configure(
            "WorkflowFeedback.TLabel",
            background=colors["surface_alt"],
            foreground=colors["muted"],
            padding=(8, 4),
            font=("Microsoft YaHei UI", 8),
        )
        style.configure("Header.TFrame", background=colors["navy"])
        style.configure("Card.TFrame", background=colors["card"], relief="flat")
        style.configure("PanelSection.TFrame", background=colors["surface_alt"], relief="flat")
        style.configure(
            "PanelSectionTitle.TLabel",
            background=colors["surface_alt"],
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "PanelSectionHint.TLabel",
            background=colors["surface_alt"],
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "PanelExample.TLabel",
            background=colors["surface_alt"],
            foreground=colors["ready"],
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(9, 7),
        )
        for option_style in ("PanelSection.TRadiobutton", "PanelSection.TCheckbutton"):
            style.configure(
                option_style,
                background=colors["surface_alt"],
                foreground=colors["text"],
                padding=(4, 3),
                font=("Microsoft YaHei UI", 9),
                focuscolor=colors["accent"],
            )
            style.map(
                option_style,
                background=[("active", colors["selection"]), ("disabled", colors["surface_alt"])],
                foreground=[("disabled", colors["disabled"])],
            )
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
        style.configure(
            "DirectoryPath.TLabel",
            background=colors["card"],
            foreground=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "ContextTitle.TLabel",
            background=colors["card"],
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "ContextValue.TLabel",
            background=colors["card"],
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "ContextWarning.TLabel",
            background=colors["card"],
            foreground=colors["warning"],
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        style.configure(
            "MatchStatTitle.TLabel",
            background="#F5F7FA",
            foreground=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "MatchStatValue.TLabel",
            background="#F5F7FA",
            foreground=colors["navy"],
            font=("Microsoft YaHei UI", 11, "bold"),
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

        # 最后一层只使用语义色板覆盖控件状态，保证浅色与深色外观一致。
        style.configure("Workflow.TFrame", background=colors["sidebar"])
        style.configure("WorkflowCard.TFrame", background=colors["sidebar"])
        style.configure("CompactNav.TFrame", background=colors["sidebar"])
        for label_style in ("WorkflowTitle.TLabel", "WorkflowHint.TLabel"):
            style.configure(label_style, background=colors["sidebar"])
        style.configure(
            "WorkflowTitle.TLabel",
            foreground=colors["navy"],
        )
        style.configure(
            "WorkflowHint.TLabel",
            foreground=colors["muted"],
        )
        style.configure(
            "Workflow.TRadiobutton",
            background=colors["sidebar"],
            foreground=colors["text"],
        )
        style.map(
            "Workflow.TRadiobutton",
            background=[("active", colors["surface_alt"]), ("disabled", colors["sidebar"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.configure(
            "CompactNav.TButton",
            background=colors["sidebar"],
            foreground=colors["navy_soft"],
        )
        style.map(
            "CompactNav.TButton",
            background=[("active", colors["sidebar_active"]), ("pressed", colors["selection"])],
            foreground=[("active", colors["accent"]), ("disabled", colors["disabled"])],
        )
        style.configure(
            "WorkflowSecondary.TButton",
            background=colors["surface_alt"],
            foreground=colors["navy"],
            focuscolor=colors["selection"],
        )
        style.map(
            "WorkflowSecondary.TButton",
            background=[("active", colors["sidebar_active"]), ("disabled", colors["surface_alt"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.map(
            "WorkflowAccent.TButton",
            background=[("active", colors["accent_hover"]), ("disabled", colors["disabled"])],
        )
        style.configure(
            "WorkflowFinal.TButton",
            background=colors["navy"],
            foreground=colors["card"],
        )
        style.map(
            "WorkflowFinal.TButton",
            background=[("active", colors["navy_soft"]), ("disabled", colors["surface_alt"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.configure(
            "WorkflowTool.TButton",
            background=colors["sidebar"],
            foreground=colors["navy_soft"],
            bordercolor=colors["border"],
        )
        style.map(
            "WorkflowTool.TButton",
            background=[("active", colors["sidebar_active"]), ("disabled", colors["sidebar"])],
            foreground=[("active", colors["accent"]), ("disabled", colors["disabled"])],
        )
        style.configure(
            "WorkflowFeedback.TLabel",
            background=colors["surface_alt"],
            foreground=colors["muted"],
        )
        style.configure("Header.TFrame", background=colors["surface_alt"])
        style.configure("HeaderTitle.TLabel", background=colors["surface_alt"], foreground=colors["text"])
        style.configure("HeaderSubtitle.TLabel", background=colors["surface_alt"], foreground=colors["muted"])
        style.configure("Icon.TLabel", background=colors["sidebar_active"], foreground=colors["accent"])
        style.configure("MatchStats.TLabel", background=colors["surface_alt"])
        style.configure("MatchStatTitle.TLabel", background=colors["surface_alt"])
        style.configure("MatchStatValue.TLabel", background=colors["surface_alt"])
        for option_style in ("Card.TCheckbutton", "Card.TRadiobutton"):
            style.map(
                option_style,
                background=[("active", colors["surface_alt"]), ("disabled", colors["card"])],
                foreground=[("disabled", colors["disabled"])],
            )
        for input_style in ("Modern.TEntry", "Modern.TSpinbox", "Modern.TCombobox"):
            style.configure(input_style, fieldbackground=colors["input"], foreground=colors["text"])
        style.map(
            "Modern.TEntry",
            fieldbackground=[("disabled", colors["surface_alt"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.map(
            "Modern.TSpinbox",
            fieldbackground=[("disabled", colors["surface_alt"])],
            foreground=[("disabled", colors["disabled"])],
            arrowcolor=[("active", colors["accent"]), ("disabled", colors["disabled"])],
        )
        style.map("Modern.TCombobox", fieldbackground=[("readonly", colors["input"])])
        style.configure("Secondary.TButton", background=colors["surface_alt"], foreground=colors["navy"])
        style.map("Secondary.TButton", background=[("active", colors["sidebar_active"])])
        style.configure(
            "Treeview",
            background=colors["card"],
            fieldbackground=colors["card"],
            foreground=colors["text"],
        )
        style.map(
            "Treeview",
            background=[("selected", colors["selection"])],
            foreground=[("selected", colors["text"])],
        )
        style.configure("Treeview.Heading", background=colors["surface_alt"], foreground=colors["navy"])
        style.map("Treeview.Heading", background=[("active", colors["sidebar_active"])])
        for orientation in ("Horizontal", "Vertical"):
            style.configure(
                f"Modern.{orientation}.TScrollbar",
                troughcolor=colors["surface_alt"],
                background=colors["disabled"],
                bordercolor=colors["surface_alt"],
                lightcolor=colors["disabled"],
                darkcolor=colors["disabled"],
            )
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor=colors["surface_alt"],
            bordercolor=colors["surface_alt"],
        )
        style.configure("Status.TLabel", background=colors["surface_alt"], foreground=colors["navy_soft"])

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
        outer.rowconfigure(0, weight=1)
        self.main_content = outer

        body = ttk.Frame(outer, style="App.TFrame")
        body.grid(row=0, column=0, sticky="nsew")
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
        self._tooltip(self.workflow_nav_button, "展开或收起完整重命名流程。")
        self._tooltip(self.compact_templates_button, "打开常用正则模板。")
        self._tooltip(self.compact_settings_button, "打开扫描与预览设置。")
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
        mode = layout_mode_for_size(width, height)
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
        measured_tree_width = self.result_tree.winfo_width()
        estimated_tree_width = max(
            320,
            width - self.RAIL_WIDTHS[mode] - 64,
        )
        self._apply_result_column_widths(
            (
                max(1, measured_tree_width - RESULT_TABLE_BORDER_RESERVE)
                if measured_tree_width > 1
                else estimated_tree_width
            )
        )
        self._position_active_tool_panel()

    def _apply_result_column_widths(self, total_width: int) -> None:
        """按结果表当前可用宽度原地更新六列，不重建任何行。"""

        key = (max(1, int(total_width)), self.current_layout_mode)
        if self._last_result_width == key:
            return
        self._last_result_width = key
        widths = calculate_result_column_widths(key[0], key[1])
        for column, column_width in widths.items():
            self.result_tree.column(
                column,
                width=column_width,
                minwidth=column_width if column in RESULT_FIXED_COLUMN_WIDTHS else 1,
                stretch=False,
            )
        self.new_name_overlay.schedule()
        self.result_icon_overlay.schedule()

    def _on_result_tree_configure(self, event: tk.Event) -> None:
        width = max(1, int(event.width) - RESULT_TABLE_BORDER_RESERVE)
        previous = self._last_result_width
        if previous is not None and previous[1] == self.current_layout_mode:
            if abs(previous[0] - width) < 4:
                return
        self._apply_result_column_widths(width)

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
        width = min(320, max(1, body_width - x))
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

        self.view_menu = tk.Menu(self.top_menu, tearoff=False)
        self.appearance_menu = tk.Menu(self.view_menu, tearoff=False)
        for label, value in (
            ("跟随系统", "system"),
            ("浅色", "light"),
            ("深色", "dark"),
        ):
            self.appearance_menu.add_radiobutton(
                label=label,
                value=value,
                variable=self.appearance_var,
                command=lambda selected=value: self.set_appearance(selected),
            )
        self.view_menu.add_cascade(label="外观", menu=self.appearance_menu)
        self.top_menu.add_cascade(label="视图", menu=self.view_menu)

        self.help_menu = tk.Menu(self.top_menu, tearoff=False)
        self.help_menu.add_command(label="使用说明", command=self._show_help)
        self.help_menu.add_command(label="关于", command=self._show_about)
        self.top_menu.add_cascade(label="帮助", menu=self.help_menu)
        self.root.configure(menu=self.top_menu)
        self.root.bind("<F1>", lambda _event: self._show_help())

    def set_appearance(self, mode: str, *, persist: bool = True) -> None:
        """切换外观并原地重绘，不重建业务控件或清空状态。"""

        requested = normalize_appearance(mode)
        resolved = resolve_appearance(requested, self.system_light_provider)
        self.requested_appearance = requested
        self.appearance_var.set(requested)
        if persist:
            try:
                save_preferences(AppPreferences(appearance=requested), self.preferences_path)
            except OSError as exc:
                if hasattr(self, "status_var"):
                    self.status_var.set(f"外观已切换，但无法保存设置：{exc}")
        if resolved == self.resolved_appearance and hasattr(self, "result_tree"):
            return
        self.resolved_appearance = resolved
        self.COLORS = theme_palette(resolved)
        self.root.configure(background=self.COLORS["background"])
        self._configure_style()
        if hasattr(self, "result_tree"):
            self._apply_runtime_theme()

    def _refresh_system_appearance(self) -> None:
        if self.requested_appearance != "system":
            return
        self.set_appearance("system", persist=False)

    def _on_root_focus_for_theme(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self._refresh_system_appearance()

    def _result_icon_theme_colors(self) -> dict[str, str]:
        return {
            "neutral": self.COLORS["navy_soft"],
            "ready": self.COLORS["ready"],
            "warning": self.COLORS["warning"],
            "blocked": self.COLORS["blocked"],
            "pending": self.COLORS["accent"],
            "info": self.COLORS["accent"],
        }

    def _tooltip(self, widget: tk.Misc, text: str) -> ToolTip:
        tooltip = ToolTip(widget, text, self.COLORS)
        self._app_tooltips.append(tooltip)
        return tooltip

    def _apply_runtime_theme(self) -> None:
        """重绘无法只靠 ttk 样式自动更新的原生与覆盖层组件。"""

        colors = self.COLORS
        menu_options = {
            "background": colors["card"],
            "foreground": colors["text"],
            "activebackground": colors["selection"],
            "activeforeground": colors["text"],
            "selectcolor": colors["accent"],
        }
        for menu_name in (
            "top_menu",
            "file_menu",
            "feature_menu",
            "view_menu",
            "appearance_menu",
            "help_menu",
        ):
            menu = getattr(self, menu_name, None)
            if menu is not None:
                menu.configure(**menu_options)
        if hasattr(self, "regex_template_list"):
            self.regex_template_list.configure(
                background=colors["input"],
                foreground=colors["text"],
                highlightbackground=colors["border"],
                highlightcolor=colors["accent"],
                selectbackground=colors["accent"],
                selectforeground=colors["card"],
            )
        self.new_name_overlay.set_theme(
            foreground=colors["accent"],
            background=colors["card"],
            selected_background=colors["selection"],
            tooltip_colors=colors,
        )
        self.result_icon_overlay.set_theme(
            background=colors["card"],
            selected_background=colors["selection"],
            tooltip_colors=colors,
            icon_colors=self._result_icon_theme_colors(),
        )
        self.result_cell_tooltip.set_colors(colors)
        for tooltip in self._app_tooltips:
            tooltip.set_colors(colors)
        self.result_tree.tag_configure("blocked", foreground=colors["blocked"])
        self.result_tree.tag_configure("ready", foreground=colors["ready"])
        self.result_tree.tag_configure("unchanged", foreground=colors["warning"])

    def _build_workflow_rail(self, parent: ttk.Frame) -> None:
        rail = ttk.Frame(
            parent,
            style="Workflow.TFrame",
            width=self.RAIL_WIDTHS["standard"],
            padding=(12, 5),
        )
        rail.grid(row=0, column=0, sticky="ns", padx=(0, 7))
        rail.grid_propagate(False)
        rail.columnconfigure(0, weight=1)
        rail.columnconfigure(1, weight=1)
        rail.rowconfigure(14, weight=1)
        self.workflow_rail = rail

        ttk.Label(rail, text="重命名流程", style="WorkflowTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
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
        self.directory_select_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

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
        self.search_button.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 8))

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
        self.preview_button.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.execute_button = ttk.Button(
            rail,
            text="确认执行",
            style="WorkflowFinal.TButton",
            command=self._confirm_execute,
            state="disabled",
        )
        self.execute_button.grid(row=12, column=0, columnspan=2, sticky="ew")
        self.rule_feedback_label = ttk.Label(
            rail,
            textvariable=self.rule_feedback_var,
            style="WorkflowFeedback.TLabel",
            wraplength=252,
            justify="left",
        )
        self.rule_feedback_label.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.tools_footer_label = ttk.Label(
            rail,
            text="工具",
            style="WorkflowTitle.TLabel",
        )
        self.tools_footer_label.grid(
            row=15,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(5, 5),
        )

        self.regex_templates_button = ttk.Button(
            rail,
            text="⌘  正则模板",
            style="WorkflowTool.TButton",
            command=self._show_regex_examples,
        )
        self.regex_templates_button.grid(
            row=16,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        self.settings_tool_button = ttk.Button(
            rail,
            text="⚙  设置",
            style="WorkflowTool.TButton",
            command=self._show_settings,
        )
        self.settings_tool_button.grid(
            row=17,
            column=0,
            columnspan=2,
            sticky="ew",
        )

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
        self._tooltip(self.directory_entry, "扫描起点；根目录本身不会改名。")
        self._tooltip(self.search_button, "只查找名称匹配项，不计算新名称，也不会修改磁盘。")
        self._tooltip(self.preview_button, "根据刚才的匹配快照计算新名称和安全状态，不会重新扫描目录。")
        self._tooltip(self.execute_button, "只执行预览中状态为“可修改”的项目，并在执行前再次确认。")
        self._tooltip(self.regex_templates_button, "打开常用正则模板工作面板。")
        self._tooltip(self.settings_tool_button, "打开扫描范围和名称保护设置。")

    def _build_result_workspace(self, parent: ttk.Frame) -> None:
        workspace = ttk.Frame(parent, style="App.TFrame")
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.rowconfigure(1, weight=1)
        workspace.columnconfigure(0, weight=1)
        self.result_workspace = workspace
        self._build_directory_overview(workspace)
        self._build_preview_frame(workspace)
        self._build_progress_frame(workspace)

    def _build_tool_panels(self, parent: ttk.Frame) -> None:
        self.active_tool_panel: str | None = None
        self.settings_panel = ttk.Frame(parent, style="Card.TFrame", padding=18)
        self.settings_panel.columnconfigure(0, weight=1)
        self.settings_panel.rowconfigure(1, weight=1)
        (
            self.settings_panel_title,
            self.settings_panel_helper,
            self.settings_panel_close,
        ) = self._build_tool_panel_header(
            self.settings_panel,
            "扫描与预览设置",
            "集中调整当前规则的扫描范围、处理对象和名称保护选项。",
        )
        settings_content = ttk.Frame(self.settings_panel, style="Card.TFrame")
        settings_content.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        settings_content.columnconfigure(0, weight=1)

        scan_group, scan_title = self._build_settings_group(
            settings_content,
            row=0,
            title="扫描范围",
            helper="控制从根目录向下读取多少层；根目录本身不会改名。",
        )
        scan_group.columnconfigure(3, weight=1)
        all_depth = ttk.Radiobutton(
            scan_group,
            text="全部层级",
            variable=self.depth_mode_var,
            value="all",
            style="PanelSection.TRadiobutton",
            command=self._update_depth_state,
        )
        all_depth.grid(row=2, column=0, sticky="w", pady=(8, 0))
        limited = ttk.Radiobutton(
            scan_group,
            text="最多",
            variable=self.depth_mode_var,
            value="limited",
            style="PanelSection.TRadiobutton",
            command=self._update_depth_state,
        )
        limited.grid(row=2, column=1, sticky="w", padx=(14, 0), pady=(8, 0))
        self.depth_spin = ttk.Spinbox(
            scan_group,
            from_=1,
            to=999,
            width=6,
            textvariable=self.depth_var,
            style="Modern.TSpinbox",
            justify="center",
        )
        self.depth_spin.grid(row=2, column=2, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Label(scan_group, text="层", style="PanelSectionHint.TLabel").grid(
            row=2, column=3, sticky="w", padx=(5, 0), pady=(8, 0)
        )

        object_group, object_title = self._build_settings_group(
            settings_content,
            row=1,
            title="处理对象",
            helper="可以只查询文件夹、只查询文件，或同时处理两类名称。",
        )
        dirs = ttk.Checkbutton(
            object_group,
            text="文件夹",
            variable=self.include_dirs_var,
            style="PanelSection.TCheckbutton",
        )
        dirs.grid(row=2, column=0, sticky="w", pady=(8, 0))
        files = ttk.Checkbutton(
            object_group,
            text="文件",
            variable=self.include_files_var,
            style="PanelSection.TCheckbutton",
        )
        files.grid(row=2, column=1, sticky="w", padx=(18, 0), pady=(8, 0))

        protection_group, protection_title = self._build_settings_group(
            settings_content,
            row=2,
            title="名称保护",
            helper="默认保留文件最后一个扩展名，避免无意改变文件类型。",
        )
        extension = ttk.Checkbutton(
            protection_group,
            text="允许修改扩展名",
            variable=self.rename_extension_var,
            style="PanelSection.TCheckbutton",
        )
        extension.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            protection_group,
            text="层级和处理对象改变后需要重新扫描；扩展名选项只会使结果预览失效。",
            style="Hint.TLabel",
            wraplength=520,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.settings_groups = (scan_group, object_group, protection_group)
        self.settings_group_labels = (scan_title, object_title, protection_title)
        self._input_widgets.extend([all_depth, limited, self.depth_spin, dirs, files, extension])

        self.templates_panel = ttk.Frame(parent, style="Card.TFrame", padding=18)
        self.templates_panel.columnconfigure(0, weight=1)
        self.templates_panel.rowconfigure(1, weight=1)
        (
            self.templates_panel_title,
            self.templates_panel_helper,
            self.templates_panel_close,
        ) = self._build_tool_panel_header(
            self.templates_panel,
            "常用正则模板",
            "按用途选择示例，确认处理前后效果后可一键应用到当前规则。",
        )
        template_content = ttk.Frame(self.templates_panel, style="Card.TFrame")
        template_content.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        template_content.columnconfigure(0, weight=2, uniform="template-columns")
        template_content.columnconfigure(1, weight=3, uniform="template-columns")
        template_content.rowconfigure(0, weight=1)

        self.regex_template_browser = ttk.Frame(
            template_content, style="PanelSection.TFrame", padding=12
        )
        self.regex_template_browser.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.regex_template_browser.columnconfigure(0, weight=1)
        self.regex_template_browser.rowconfigure(2, weight=1)
        ttk.Label(
            self.regex_template_browser,
            text="模板库",
            style="PanelSectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        categories = tuple(dict.fromkeys(example.category for example in REGEX_EXAMPLES))
        self.regex_category_var = tk.StringVar(self.root, value=categories[0])
        self.regex_category_selector = ttk.Combobox(
            self.regex_template_browser,
            textvariable=self.regex_category_var,
            values=categories,
            state="readonly",
            width=17,
            style="Modern.TCombobox",
        )
        self.regex_category_selector.grid(row=1, column=0, sticky="ew", pady=(10, 9))
        self.regex_purpose_var = tk.StringVar(self.root)

        list_frame = ttk.Frame(self.regex_template_browser, style="PanelSection.TFrame")
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.regex_template_list = tk.Listbox(
            list_frame,
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
            background=self.COLORS["input"],
            foreground=self.COLORS["text"],
            selectbackground=self.COLORS["accent"],
            selectforeground="#FFFFFF",
        )
        self.regex_template_list.grid(row=0, column=0, sticky="nsew")
        regex_list_scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.regex_template_list.yview,
            style="Modern.Vertical.TScrollbar",
        )
        regex_list_scrollbar.grid(row=0, column=1, sticky="ns")
        self.regex_template_list.configure(yscrollcommand=regex_list_scrollbar.set)

        self.regex_template_details = ttk.Frame(
            template_content, style="PanelSection.TFrame", padding=14
        )
        self.regex_template_details.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.regex_template_details.columnconfigure(0, weight=1)
        self.regex_template_details.rowconfigure(8, weight=1)
        ttk.Label(
            self.regex_template_details,
            text="规则详情",
            style="PanelSectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.regex_template_details,
            textvariable=self.regex_purpose_var,
            style="PanelSectionHint.TLabel",
            wraplength=350,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(5, 12))
        self.regex_example_search_var = tk.StringVar(self.root)
        self.regex_example_replacement_var = tk.StringVar(self.root)
        self.regex_before_var = tk.StringVar(self.root)
        self.regex_after_var = tk.StringVar(self.root)
        self.regex_option_note_var = tk.StringVar(self.root)
        ttk.Label(self.regex_template_details, text="查找表达式", style="Field.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        self.regex_search_entry = ttk.Entry(
            self.regex_template_details,
            textvariable=self.regex_example_search_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 9),
        )
        self.regex_search_entry.grid(row=3, column=0, sticky="ew", pady=(3, 10), ipady=2)
        ttk.Label(self.regex_template_details, text="替换内容", style="Field.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        self.regex_replacement_entry = ttk.Entry(
            self.regex_template_details,
            textvariable=self.regex_example_replacement_var,
            state="readonly",
            style="Modern.TEntry",
            font=("Consolas", 9),
        )
        self.regex_replacement_entry.grid(row=5, column=0, sticky="ew", pady=(3, 10), ipady=2)
        self.regex_example_text_var = tk.StringVar(self.root)
        ttk.Label(
            self.regex_template_details,
            textvariable=self.regex_example_text_var,
            style="PanelExample.TLabel",
            wraplength=350,
        ).grid(row=6, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(
            self.regex_template_details,
            textvariable=self.regex_option_note_var,
            style="PanelSectionHint.TLabel",
        ).grid(row=7, column=0, sticky="w")
        self.regex_apply_button = ttk.Button(
            self.regex_template_details,
            text="一键应用此规则",
            style="Accent.TButton",
        )
        self.regex_apply_button.grid(row=9, column=0, sticky="e", pady=(14, 0))
        self.regex_category_selector.bind("<<ComboboxSelected>>", self._filter_regex_templates)
        self.regex_template_list.bind("<<ListboxSelect>>", self._show_selected_regex_template)
        self.regex_template_list.bind("<Double-Button-1>", lambda _event: self.regex_apply_button.invoke())
        self._filter_regex_templates()

        self.root.bind("<Escape>", lambda _event: self._close_overlays())
        for widget in (
            self.result_workspace,
            self.result_card,
            self.result_tree,
            self.stats_footer,
            self.progress,
        ):
            widget.bind(
                "<Button-1>", lambda _event: self._close_overlays(), add="+"
            )

    def _build_tool_panel_header(
        self,
        panel: ttk.Frame,
        title: str,
        helper: str,
    ) -> tuple[ttk.Label, ttk.Label, ttk.Button]:
        header = ttk.Frame(panel, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        title_label = ttk.Label(header, text=title, style="CardTitle.TLabel")
        title_label.grid(row=0, column=0, sticky="w")
        helper_label = ttk.Label(
            header,
            text=helper,
            style="Hint.TLabel",
            justify="left",
        )
        helper_label.grid(row=1, column=0, sticky="w", pady=(4, 0), padx=(0, 18))
        close_button = ttk.Button(
            header,
            text="关闭",
            style="Secondary.TButton",
            command=self._close_tool_panel,
        )
        close_button.grid(row=0, column=1, rowspan=2, sticky="ne")
        return title_label, helper_label, close_button

    def _build_settings_group(
        self,
        parent: ttk.Frame,
        *,
        row: int,
        title: str,
        helper: str,
    ) -> tuple[ttk.Frame, ttk.Label]:
        group = ttk.Frame(parent, style="PanelSection.TFrame", padding=(14, 11))
        group.grid(row=row, column=0, sticky="ew", pady=(0 if row == 0 else 9, 0))
        group.columnconfigure(0, weight=0)
        title_label = ttk.Label(group, text=title, style="PanelSectionTitle.TLabel")
        title_label.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(
            group,
            text=helper,
            style="PanelSectionHint.TLabel",
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 0))
        return group, title_label

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
        """将工作面板居中放入侧栏右侧，并限制在主内容区域内。"""

        if self.active_tool_panel is None:
            return
        panel = (
            self.settings_panel
            if self.active_tool_panel == "settings"
            else self.templates_panel
        )
        self.root.update_idletasks()
        rail_width = self.RAIL_WIDTHS[self.current_layout_mode]
        margin = 12
        x = rail_width + margin
        available_width = max(1, self.body_frame.winfo_width() - x - margin)
        target_width = 720 if self.current_layout_mode == "spacious" else 620
        width = min(target_width, available_width)
        body_height = max(1, self.body_frame.winfo_height())
        available_height = max(1, body_height - margin * 2)
        target_height = 460 if self.active_tool_panel == "templates" else 420
        height = min(
            available_height,
            max(target_height, panel.winfo_reqheight()),
        )
        y = max(margin, (body_height - height) // 2)
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
        self._tooltip(
            self.directory_entry,
            "要扫描的起始目录。根目录本身不会被重命名，只处理它内部的文件夹和文件。",
        )
        self._tooltip(browse, "从系统目录选择器中选择扫描起点。")
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
        self._tooltip(
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
        self._tooltip(self.search_entry, "普通模式：输入要查找的原样文本。正则模式：输入 Python 正则表达式。不能为空。")
        self._tooltip(self.replacement_entry, "可留空，表示删除匹配内容。正则模式可使用 \\1 或 \\g<名称> 引用捕获组。")

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
        self._tooltip(regex, "关闭时按普通文本查找；开启后使用 Python 正则语法，例如 (\\d{4})-(\\d{2})。")
        self._tooltip(dirs, "勾选后，名称匹配的子文件夹会进入预览。")
        self._tooltip(files, "勾选后，名称匹配的文件会进入预览。")
        self._tooltip(extension, "默认保护最后一个扩展名。例如查找 jpg 不会改变照片.jpg；开启后才会处理整个文件名。")
        self._tooltip(
            self.regex_templates_button,
            "按用途选择经过验证的常用正则规则，查看处理前后效果并一键填入主窗口。",
        )
        self._tooltip(
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

    def _build_directory_overview(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(11, 7))
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        self.directory_overview = frame
        ttk.Label(frame, text="当前目录", style="ContextTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.directory_context_path_label = ttk.Label(
            frame,
            textvariable=self.directory_context_path_var,
            style="DirectoryPath.TLabel",
            anchor="w",
        )
        self.directory_context_path_label.grid(
            row=1, column=0, sticky="ew", padx=(0, 16)
        )
        self.directory_path_tooltip = self._tooltip(
            self.directory_context_path_label,
            self.directory_context_path_var.get(),
        )

        context_items = (
            ("扫描范围", self.directory_context_scope_var),
            ("文件夹", self.directory_folder_count_var),
            ("文件", self.directory_file_count_var),
            ("状态", self.directory_inventory_state_var),
        )
        for column, (title, variable) in enumerate(context_items, start=1):
            ttk.Label(frame, text=title, style="ContextTitle.TLabel").grid(
                row=0, column=column, sticky="w", padx=(0 if column == 1 else 14, 0)
            )
            label = ttk.Label(
                frame,
                textvariable=variable,
                style="ContextValue.TLabel",
            )
            label.grid(
                row=1, column=column, sticky="w", padx=(0 if column == 1 else 14, 0)
            )
            if title == "扫描范围":
                self.directory_context_scope_label = label
        self.directory_warning_label = ttk.Label(
            frame,
            textvariable=self.directory_inventory_warning_var,
            style="ContextWarning.TLabel",
        )
        self.directory_warning_label.grid(
            row=2, column=0, columnspan=5, sticky="e", pady=(2, 0)
        )

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
        self._tooltip(
            self.preview_spin,
            "仅控制表格显示数量，不改变完整匹配统计和最终执行数量。文件夹优先，同类按名称自然排序。",
        )
        self._input_widgets.append(self.preview_spin)
        self.result_tree = self._create_tree(frame)
        self._build_match_stats_footer(frame)

    def _build_match_stats_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent, style="App.TFrame", padding=(8, 5))
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.stats_footer = footer
        titles = ("匹配", "可修改", "名称未变化", "阻止执行")
        self.match_stat_title_labels: list[ttk.Label] = []
        for column, (title, variable) in enumerate(
            zip(titles, self.match_stat_value_vars)
        ):
            footer.columnconfigure(column, weight=1, uniform="match-stats")
            item = ttk.Frame(footer, style="App.TFrame")
            item.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0),
            )
            item.columnconfigure(1, weight=1)
            title_label = ttk.Label(
                item,
                text=title,
                style="MatchStatTitle.TLabel",
            )
            title_label.grid(row=0, column=0, sticky="w")
            ttk.Label(
                item,
                textvariable=variable,
                style="MatchStatValue.TLabel",
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))
            self.match_stat_title_labels.append(title_label)

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
        widths = calculate_result_column_widths(700, "standard")
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(
                column,
                width=widths[column],
                minwidth=widths[column] if column in RESULT_FIXED_COLUMN_WIDTHS else 1,
                stretch=False,
            )
        self.new_name_overlay = TreeColumnTextOverlay(
            tree,
            "new",
            foreground=self.COLORS["accent"],
            background=self.COLORS["card"],
            selected_background=self.COLORS["selection"],
            tooltip_colors=self.COLORS,
        )
        self.result_icon_overlay = TreeCellIconOverlay(
            tree,
            background=self.COLORS["card"],
            selected_background=self.COLORS["selection"],
            tooltip_colors=self.COLORS,
            icon_colors=self._result_icon_theme_colors(),
            on_activate=self._show_result_item_details,
        )
        tree.bind("<Configure>", self._on_result_tree_configure, add="+")

        def scroll_vertical(*args: str) -> None:
            tree.yview(*args)
            self.new_name_overlay.schedule()
            self.result_icon_overlay.schedule()

        def scroll_horizontal(*args: str) -> None:
            tree.xview(*args)
            self.new_name_overlay.schedule()
            self.result_icon_overlay.schedule()

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
        tree.tag_configure("blocked", foreground=self.COLORS["blocked"])
        tree.tag_configure("ready", foreground=self.COLORS["ready"])
        tree.tag_configure("unchanged", foreground=self.COLORS["warning"])
        self.result_scrollbar = ybar
        self.result_horizontal_scrollbar = xbar
        self.result_cell_tooltip = TreeCellToolTip(tree, self.COLORS)
        return tree

    def _build_progress_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(7, 4))
        frame.grid(row=2, column=0, sticky="ew")
        self.progress_frame = frame
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
        self._tooltip(status, "状态栏会提示当前结果和建议的下一步操作。")

    def _bind_change_tracking(self) -> None:
        scope_variables = [
            self.directory_var,
            self.depth_mode_var,
            self.depth_var,
        ]
        match_variables = [
            self.search_var,
            self.regex_var,
            self.include_dirs_var,
            self.include_files_var,
        ]
        for variable in scope_variables:
            variable.trace_add("write", self._on_scope_input_changed)
        for variable in match_variables:
            variable.trace_add("write", self._on_match_input_changed)
        for variable in (self.replacement_var, self.rename_extension_var):
            variable.trace_add("write", self._on_preview_input_changed)
        self.preview_limit_var.trace_add("write", lambda *_: self._render_preview())
        self.search_entry.bind("<Return>", self._search_from_entry)
        self.replacement_entry.bind("<Return>", self._preview_from_replacement)

    def _set_directory_inventory(
        self,
        snapshot: MatchResult | None = None,
        *,
        scanning: bool = False,
    ) -> None:
        """原地更新目录上下文，不影响匹配或预览业务状态。"""

        view = directory_inventory_view(snapshot, scanning=scanning)
        self.directory_context_path_var.set(
            str(snapshot.root) if snapshot is not None else self.directory_var.get().strip()
        )
        self.directory_context_scope_var.set(
            directory_scope_text(self.depth_mode_var.get(), self.depth_var.get())
        )
        self.directory_folder_count_var.set(view.folder_count)
        self.directory_file_count_var.set(view.file_count)
        self.directory_inventory_state_var.set(view.state)
        self.directory_inventory_warning_var.set(view.warning)
        if hasattr(self, "directory_path_tooltip"):
            self.directory_path_tooltip.set_text(
                self.directory_context_path_var.get() or "尚未选择目录"
            )

    def _set_match_statistics(
        self,
        matched: int | str,
        ready: int | str,
        unchanged: int | str,
        blocked: int | str,
    ) -> None:
        """同步更新结果表下方四项统计和兼容汇总文字。"""

        values = (matched, ready, unchanged, blocked)
        for variable, value in zip(self.match_stat_value_vars, values):
            variable.set(str(value))

        def summary_value(value: int | str) -> str:
            return f"{value}项" if isinstance(value, int) else str(value)

        self.stats_var.set(
            f"匹配：{summary_value(matched)} | 可修改：{summary_value(ready)} | "
            f"名称未变化：{summary_value(unchanged)} | 阻止执行：{summary_value(blocked)}"
        )

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
            self._set_match_statistics(0, 0, 0, 0)
            self.status_var.set("扫描条件已改变，请重新执行“扫描”。")
            self._render_preview()
        self._update_rule_feedback(validate_replacement=False)
        self._sync_command_states()

    def _on_scope_input_changed(self, *_args) -> None:
        self._inventory_scanning = False
        self._set_directory_inventory(None)
        self._on_match_input_changed()

    def _on_preview_input_changed(self, *_args) -> None:
        if not self._busy and self._last_scan is not None:
            self._last_scan = None
            matched_total = (
                len(self._last_matches.items) if self._last_matches is not None else 0
            )
            self._set_match_statistics(matched_total, "—", "—", "—")
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
        self._inventory_scanning = True
        self._set_directory_inventory(None, scanning=True)
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
        self._inventory_scanning = False
        self._set_directory_inventory(result)
        matched_total = len(result.items)
        self._set_match_statistics(matched_total, "—", "—", "—")
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
        self._set_match_statistics(
            summary["matched_total"],
            summary["ready_total"],
            summary["unchanged_total"],
            summary["blocked_total"],
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
                root=self._last_scan.root,
            )
        elif self._last_matches is not None:
            self._fill_matches(
                self.result_tree,
                self._last_matches.items[:limit],
                root=self._last_matches.root,
            )
        else:
            self._fill_tree(
                self.result_tree,
                [],
                root=Path(self.directory_var.get()),
            )

    def _fill_matches(
        self,
        tree: ttk.Treeview,
        items: Iterable[MatchedItem],
        *,
        root: Path,
    ) -> None:
        self._reset_result_row_details()
        tree.delete(*tree.get_children())
        for item in items:
            parent_text = result_parent_text(root, item.source)
            row_id = tree.insert(
                "",
                "end",
                values=(
                    item.kind.value,
                    parent_text,
                    item.source.name,
                    "",
                    "等待结果预览",
                    "填写替换内容后生成结果预览",
                ),
            )
            self._result_row_details[row_id] = {
                "kind": item.kind.value,
                "parent": parent_text,
                "old": item.source.name,
                "new": "",
                "status": "等待结果预览",
                "detail": "填写替换内容后生成结果预览",
            }
        if tree is self.result_tree:
            self.new_name_overlay.schedule()
            self.result_icon_overlay.schedule()

    def _fill_tree(
        self,
        tree: ttk.Treeview,
        items: Iterable[RenameCandidate],
        *,
        root: Path,
    ) -> None:
        self._reset_result_row_details()
        tree.delete(*tree.get_children())
        for item in items:
            if item.status is CandidateStatus.READY:
                tag = "ready"
            elif item.status is CandidateStatus.UNCHANGED:
                tag = "unchanged"
            else:
                tag = "blocked"
            parent_text = result_parent_text(root, item.source)
            row_id = tree.insert(
                "",
                "end",
                values=(
                    item.kind.value,
                    parent_text,
                    item.old_name,
                    item.new_name,
                    item.status.value,
                    item.detail,
                ),
                tags=(tag,),
            )
            self._result_row_details[row_id] = {
                "kind": item.kind.value,
                "parent": parent_text,
                "old": item.old_name,
                "new": item.new_name,
                "status": item.status.value,
                "detail": item.detail,
            }
        if tree is self.result_tree:
            self.new_name_overlay.schedule()
            self.result_icon_overlay.schedule()

    def _reset_result_row_details(self) -> None:
        """清除旧行详情，并关闭已失去数据来源的详情窗口。"""

        self._result_row_details = {}
        if "result-item-details" in self.dialogs.windows:
            self.dialogs.close("result-item-details")

    def _show_result_item_details(self, item_id: str, focus_column: str) -> None:
        """显示图标所在行的完整只读信息，不触碰扫描或文件状态。"""

        details = self._result_row_details.get(item_id)
        if details is None:
            return
        explanation = details["detail"] or "暂无补充说明。"
        if focus_column == "status":
            focus_text = f"状态：{details['status']}\n{explanation}"
        else:
            focus_text = f"说明：{explanation}"
        values = {
            "focus": focus_text,
            "kind": details["kind"],
            "parent": details["parent"],
            "old": details["old"],
            "new": details["new"],
            "status": details["status"],
            "detail": explanation,
        }
        existing = self.dialogs.windows.get("result-item-details")
        if (
            existing is not None
            and existing.winfo_exists()
            and hasattr(self, "result_item_detail_vars")
        ):
            for key, value in values.items():
                self.result_item_detail_vars[key].set(value)
            self.dialogs.open(
                "result-item-details",
                title="匹配结果详情",
                size=(680, 500),
                build=lambda _window: None,
            )
            return

        def build(window: tk.Toplevel) -> None:
            self.result_item_detail_vars = {
                key: tk.StringVar(window, value=value) for key, value in values.items()
            }
            outer = ttk.Frame(window, style="App.TFrame", padding=18)
            outer.pack(fill="both", expand=True)
            ttk.Label(
                outer,
                text="匹配结果详情",
                style="SectionTitle.TLabel",
            ).pack(anchor="w")
            ttk.Label(
                outer,
                textvariable=self.result_item_detail_vars["focus"],
                style="Feedback.TLabel",
                justify="left",
                wraplength=620,
                padding=(12, 10),
            ).pack(fill="x", pady=(10, 12))

            fields = ttk.Frame(outer, style="Card.TFrame", padding=(14, 12))
            fields.pack(fill="both", expand=True)
            fields.columnconfigure(1, weight=1)
            labels = (
                ("类型", "kind"),
                ("所在目录", "parent"),
                ("原名称", "old"),
                ("新名称", "new"),
                ("状态", "status"),
            )
            for row, (label_text, key) in enumerate(labels):
                ttk.Label(fields, text=label_text, style="Field.TLabel").grid(
                    row=row, column=0, sticky="nw", padx=(0, 12), pady=5
                )
                entry = ttk.Entry(
                    fields,
                    textvariable=self.result_item_detail_vars[key],
                    state="readonly",
                    style="Modern.TEntry",
                )
                entry.grid(row=row, column=1, sticky="ew", pady=5)
            detail_row = len(labels)
            ttk.Label(fields, text="完整说明", style="Field.TLabel").grid(
                row=detail_row, column=0, sticky="nw", padx=(0, 12), pady=5
            )
            ttk.Label(
                fields,
                textvariable=self.result_item_detail_vars["detail"],
                style="Card.TLabel",
                justify="left",
                wraplength=500,
                padding=(1, 5),
            ).grid(row=detail_row, column=1, sticky="ew", pady=5)
            ttk.Button(
                outer,
                text="关闭",
                command=lambda: self.dialogs.close("result-item-details"),
                style="Secondary.TButton",
            ).pack(anchor="e", pady=(12, 0))

        self.dialogs.open(
            "result-item-details",
            title="匹配结果详情",
            size=(680, 500),
            build=build,
        )

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
        self._set_directory_inventory(None)
        self._set_match_statistics(0, 0, 0, 0)
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
                    if self._inventory_scanning:
                        self._inventory_scanning = False
                        self._set_directory_inventory(None)
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
                "• 相对目录、语义状态图标、悬浮提示与单项详情\n"
                "• 多层目录、扩展名保护、处理进度和执行结果详情\n\n"
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
4. 在统一结果表中按“类型、所在目录、原名称、新名称、状态、说明”检查结果；所在目录从当前根目录之后开始显示。类型、状态和说明使用紧凑图标，把鼠标停在图标上可查看完整文字；点击状态或说明图标会打开该项目的完整详情。新名称使用青绿色便于对照，原名称和新名称会随结果区宽度自动伸缩。
5. 点击“确认执行”，核对汇总并二次确认。执行期间会显示逐项进度，完成后可从“功能 → 结果详情”查看记录。
6. 层级、文件夹/文件范围和扩展名保护位于左下角“设置”；正则模板与设置互斥显示，再次点击、按 Esc 或点击结果区会收起。

窗口与紧凑导航

程序启动时会跟随鼠标所在显示器选择初始大小，窗口始终保留 1120×720 的完整工作台尺寸。标准屏、超宽屏和竖屏使用不同的内容比例；手动放大时，结果区会优先获得空间。

竖屏或窗口内容比例偏窄时，左侧流程会折叠为深色导航条。点击顶部流程图标展开工作流抽屉；底部“.*”和齿轮图标分别打开正则模板与设置。工作流、模板和设置互斥显示，可重复点击、按 Esc 或点击结果区收起。缩放不会清空已经填写的目录、规则、匹配或预览。

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
