"""Tkinter 图形界面。"""

from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

from .core import RenameRule, RuleError, ScanError, execute, scan
from .models import (
    CandidateStatus,
    ExecutionRecord,
    ExecutionResult,
    ItemKind,
    RenameCandidate,
    ScanOptions,
    ScanResult,
)


def partition_preview(
    candidates: Iterable[RenameCandidate], limit: int
) -> tuple[list[RenameCandidate], list[RenameCandidate]]:
    """分别截取文件夹和文件预览，互不占用对方限额。"""

    items = list(candidates)
    directories = [item for item in items if item.kind is ItemKind.DIRECTORY][:limit]
    files = [item for item in items if item.kind is ItemKind.FILE][:limit]
    return directories, files


def _natural_name_key(value: str) -> tuple[str | int, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
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
            background="#fffbe6",
            foreground="#202020",
            relief="solid",
            borderwidth=1,
            padx=9,
            pady=6,
            wraplength=460,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


class BatchRenameApp:
    """批量重命名主窗口。"""

    POLL_INTERVAL_MS = 80

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("批量重命名工具")
        self.root.geometry("1180x800")
        self.root.minsize(940, 680)
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
        self.preview_limit_var = tk.IntVar(value=10)
        self.rule_feedback_var = tk.StringVar(value="请输入查找内容；普通模式按原样匹配文本。")
        self.stats_var = tk.StringVar(value="尚未扫描")
        self.status_var = tk.StringVar(value="请设置目录和规则，然后点击“扫描预览”。")
        self.progress_text_var = tk.StringVar(value="等待操作")

        self._messages: queue.Queue[tuple] = queue.Queue()
        self._busy = False
        self._input_widgets: list[ttk.Widget] = []
        self._last_scan: ScanResult | None = None
        self._last_execution: ExecutionResult | None = None

        self._configure_style()
        self._build_ui()
        self._bind_change_tracking()
        self._update_depth_state()
        self.root.after(self.POLL_INTERVAL_MS, self._poll_messages)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 17, "bold"))
        style.configure("Subtitle.TLabel", foreground="#555555")
        style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Stats.TLabel", font=("Microsoft YaHei UI", 10, "bold"), foreground="#174a7e")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Treeview", rowheight=25)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(14, 12, 14, 8))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="批量重命名工具", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="先扫描预览，再确认执行；不会覆盖已有文件或文件夹。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        help_button = ttk.Button(header, text="使用说明", command=self._show_help)
        help_button.grid(row=0, column=1, rowspan=2, padx=(10, 0))
        ToolTip(help_button, "打开完整说明，包括层级定义、正则示例、冲突策略和安全注意事项。")

        self._build_scope_frame(outer)
        self._build_rule_frame(outer)
        self._build_actions_frame(outer)
        self._build_preview_frame(outer)
        self._build_progress_frame(outer)

    def _build_scope_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="1. 扫描范围", style="Section.TLabelframe")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="根目录：").grid(row=0, column=0, padx=(10, 6), pady=(9, 5), sticky="w")
        self.directory_entry = ttk.Entry(frame, textvariable=self.directory_var)
        self.directory_entry.grid(row=0, column=1, padx=0, pady=(9, 5), sticky="ew")
        browse = ttk.Button(frame, text="选择目录…", command=self._choose_directory)
        browse.grid(row=0, column=2, padx=8, pady=(9, 5))
        ToolTip(
            self.directory_entry,
            "要扫描的起始目录。根目录本身不会被重命名，只处理它内部的文件夹和文件。",
        )
        ToolTip(browse, "从系统目录选择器中选择扫描起点。")
        self._input_widgets.extend([self.directory_entry, browse])

        depth_row = ttk.Frame(frame)
        depth_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(2, 5))
        ttk.Label(depth_row, text="扫描层级：").pack(side="left")
        all_depth = ttk.Radiobutton(
            depth_row,
            text="全部层级（默认，扫描到最深处）",
            variable=self.depth_mode_var,
            value="all",
            command=self._update_depth_state,
        )
        all_depth.pack(side="left", padx=(0, 14))
        limited = ttk.Radiobutton(
            depth_row,
            text="限制为",
            variable=self.depth_mode_var,
            value="limited",
            command=self._update_depth_state,
        )
        limited.pack(side="left")
        self.depth_spin = ttk.Spinbox(depth_row, from_=1, to=999, width=6, textvariable=self.depth_var)
        self.depth_spin.pack(side="left", padx=5)
        ttk.Label(depth_row, text="层").pack(side="left")
        ToolTip(
            depth_row,
            "第 1 层是根目录中的直接子项；第 2 层是直接子文件夹中的项目，以此类推。符号链接不会被跟随。",
        )
        self._input_widgets.extend([all_depth, limited, self.depth_spin])
        ttk.Label(
            frame,
            text="说明：根目录自身不改名；无法访问的子目录会记录为扫描提示，不影响其他项目。",
            style="Hint.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 8))

    def _build_rule_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="2. 重命名规则", style="Section.TLabelframe")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="查找内容：").grid(row=0, column=0, padx=(10, 6), pady=(9, 5), sticky="w")
        search_entry = ttk.Entry(frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, padx=(0, 14), pady=(9, 5), sticky="ew")
        ttk.Label(frame, text="替换为：").grid(row=0, column=2, padx=(0, 6), pady=(9, 5), sticky="w")
        replace_entry = ttk.Entry(frame, textvariable=self.replacement_var)
        replace_entry.grid(row=0, column=3, padx=(0, 10), pady=(9, 5), sticky="ew")
        ToolTip(search_entry, "普通模式：输入要查找的原样文本。正则模式：输入 Python 正则表达式。不能为空。")
        ToolTip(replace_entry, "可留空，表示删除匹配内容。正则模式可使用 \\1 或 \\g<名称> 引用捕获组。")

        options = ttk.Frame(frame)
        options.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(3, 4))
        regex = ttk.Checkbutton(options, text="使用正则表达式（高级）", variable=self.regex_var)
        regex.pack(side="left", padx=(0, 18))
        dirs = ttk.Checkbutton(options, text="处理文件夹", variable=self.include_dirs_var)
        dirs.pack(side="left", padx=(0, 18))
        files = ttk.Checkbutton(options, text="处理文件", variable=self.include_files_var)
        files.pack(side="left", padx=(0, 18))
        extension = ttk.Checkbutton(
            options,
            text="允许修改文件扩展名",
            variable=self.rename_extension_var,
        )
        extension.pack(side="left")
        self._input_widgets.extend([search_entry, replace_entry, regex, dirs, files, extension])
        ToolTip(regex, "关闭时按普通文本查找；开启后使用 Python 正则语法，例如 (\\d{4})-(\\d{2})。")
        ToolTip(dirs, "勾选后，名称匹配的子文件夹会进入预览。")
        ToolTip(files, "勾选后，名称匹配的文件会进入预览。")
        ToolTip(extension, "默认保护最后一个扩展名。例如查找 jpg 不会改变照片.jpg；开启后才会处理整个文件名。")

        self.rule_feedback_label = ttk.Label(frame, textvariable=self.rule_feedback_var, style="Hint.TLabel")
        self.rule_feedback_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 8))

    def _build_actions_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(2, weight=1)
        self.scan_button = ttk.Button(frame, text="扫描预览", style="Accent.TButton", command=self._start_scan)
        self.scan_button.grid(row=0, column=0, padx=(0, 8))
        self.execute_button = ttk.Button(frame, text="执行重命名", command=self._confirm_execute, state="disabled")
        self.execute_button.grid(row=0, column=1, padx=(0, 14))
        ttk.Label(frame, textvariable=self.stats_var, style="Stats.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(frame, text="每类预览：").grid(row=0, column=3, padx=(8, 4))
        preview_spin = ttk.Spinbox(
            frame,
            from_=1,
            to=100,
            width=6,
            textvariable=self.preview_limit_var,
            command=self._render_preview,
        )
        preview_spin.grid(row=0, column=4)
        ttk.Label(frame, text="条").grid(row=0, column=5, padx=(4, 0))
        ToolTip(self.scan_button, "只读取目录并生成预览，不会修改任何名称。修改规则后必须重新扫描。")
        ToolTip(self.execute_button, "显示最终汇总并要求二次确认；只执行状态为“可修改”的项目。")
        ToolTip(preview_spin, "仅控制表格显示数量，不改变扫描统计和最终执行数量。")
        self._input_widgets.append(preview_spin)

    def _build_preview_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="3. 分类预览", style="Section.TLabelframe")
        frame.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        notebook = ttk.Notebook(frame)
        notebook.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        directory_tab = ttk.Frame(notebook)
        file_tab = ttk.Frame(notebook)
        notebook.add(directory_tab, text="文件夹（0）")
        notebook.add(file_tab, text="文件（0）")
        self.preview_notebook = notebook
        self.directory_tree = self._create_tree(directory_tab)
        self.file_tree = self._create_tree(file_tab)

    def _create_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        columns = ("old", "new", "parent", "status", "detail")
        tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        headings = {
            "old": "原名称",
            "new": "新名称",
            "parent": "所在目录",
            "status": "状态",
            "detail": "说明",
        }
        widths = {"old": 190, "new": 190, "parent": 350, "status": 100, "detail": 230}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=80, stretch=column in {"parent", "detail"})
        ybar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        tree.tag_configure("blocked", foreground="#9b2c2c")
        tree.tag_configure("ready", foreground="#176b34")
        ToolTip(tree, "双击或横向滚动可查看长路径。红色项目会被跳过，绿色项目将在确认后执行。")
        return tree

    def _build_progress_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=5, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, textvariable=self.progress_text_var, width=42).grid(row=0, column=1, sticky="e")
        self.details_button = ttk.Button(frame, text="查看结果详情", command=self._show_execution_details, state="disabled")
        self.details_button.grid(row=0, column=2, padx=(8, 0))
        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4))
        status.pack(fill="x", side="bottom")
        ToolTip(status, "状态栏会提示当前结果和建议的下一步操作。")

    def _bind_change_tracking(self) -> None:
        variables = [
            self.directory_var,
            self.depth_mode_var,
            self.depth_var,
            self.search_var,
            self.replacement_var,
            self.regex_var,
            self.rename_extension_var,
            self.include_dirs_var,
            self.include_files_var,
        ]
        for variable in variables:
            variable.trace_add("write", self._on_input_changed)
        self.preview_limit_var.trace_add("write", lambda *_: self._render_preview())

    def _on_input_changed(self, *_args) -> None:
        if self._last_scan is not None and not self._busy:
            self._last_scan = None
            self.execute_button.configure(state="disabled")
            self.status_var.set("设置已改变，请重新点击“扫描预览”生成有效预览。")
        search_text = self.search_var.get()
        if not search_text:
            self.rule_feedback_var.set("请输入查找内容；该字段不能为空。")
            return
        try:
            RenameRule(
                search_text,
                self.replacement_var.get(),
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

    def _collect_options(self) -> ScanOptions:
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
            self.replacement_var.get(),
            use_regex=self.regex_var.get(),
            rename_extension=self.rename_extension_var.get(),
        )
        return ScanOptions(
            root=Path(directory_text),
            search=self.search_var.get(),
            replacement=self.replacement_var.get(),
            use_regex=self.regex_var.get(),
            max_depth=max_depth,
            include_files=self.include_files_var.get(),
            include_dirs=self.include_dirs_var.get(),
            rename_extension=self.rename_extension_var.get(),
        )

    def _start_scan(self) -> None:
        if self._busy:
            return
        try:
            options = self._collect_options()
        except (RuleError, ScanError) as exc:
            messagebox.showwarning("设置需要修正", str(exc), parent=self.root)
            self.status_var.set(f"无法扫描：{exc}")
            return
        self._last_scan = None
        self._last_execution = None
        self.details_button.configure(state="disabled")
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_text_var.set("正在读取目录，请稍候…")
        self.status_var.set("正在扫描；此阶段只读取名称，不会修改任何项目。")
        threading.Thread(target=self._scan_worker, args=(options,), daemon=True).start()

    def _scan_worker(self, options: ScanOptions) -> None:
        try:
            result = scan(options)
        except Exception as exc:
            self._messages.put(("error", "扫描失败", str(exc)))
        else:
            self._messages.put(("scan_done", result))

    def _handle_scan_done(self, result: ScanResult) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self._set_busy(False)
        self._last_scan = result
        summary = summarize_candidates(result.candidates)
        self.stats_var.set(
            f"匹配：{summary['matched_total']} 项  |  可修改：{summary['ready_total']} 项  |  "
            f"名称未变化：{summary['unchanged_total']} 项  |  阻止执行：{summary['blocked_total']} 项"
        )
        self.progress_text_var.set(f"扫描完成：找到 {summary['matched_total']} 个名称匹配")
        self._render_preview()
        if summary["ready_total"]:
            self.execute_button.configure(state="normal")
            self.status_var.set("预览已生成。请检查新名称和状态，确认无误后点击“执行重命名”。")
        else:
            self.execute_button.configure(state="disabled")
            if summary["matched_total"]:
                self.status_var.set(
                    f"已匹配 {summary['matched_total']} 项，但本次没有可执行动作；请查看状态说明或调整替换内容。"
                )
            else:
                self.status_var.set("没有找到符合搜索条件的名称，请检查目录、层级和查找内容。")
        if result.errors:
            messagebox.showwarning(
                "扫描完成，但有提示",
                f"已完成其余目录扫描，但有 {len(result.errors)} 个位置无法读取。\n\n"
                + "\n".join(result.errors[:8]),
                parent=self.root,
            )

    def _render_preview(self) -> None:
        if not hasattr(self, "directory_tree"):
            return
        try:
            limit = max(1, int(self.preview_limit_var.get()))
        except (ValueError, tk.TclError):
            return
        items = self._last_scan.candidates if self._last_scan is not None else []
        directories, files = partition_preview(items, limit)
        self._fill_tree(self.directory_tree, directories)
        self._fill_tree(self.file_tree, files)
        directory_total = sum(item.kind is ItemKind.DIRECTORY for item in items)
        file_total = sum(item.kind is ItemKind.FILE for item in items)
        self.preview_notebook.tab(0, text=f"文件夹（显示 {len(directories)}/{directory_total}）")
        self.preview_notebook.tab(1, text=f"文件（显示 {len(files)}/{file_total}）")

    @staticmethod
    def _fill_tree(tree: ttk.Treeview, items: Iterable[RenameCandidate]) -> None:
        tree.delete(*tree.get_children())
        for item in items:
            tag = "ready" if item.status is CandidateStatus.READY else "blocked"
            tree.insert(
                "",
                "end",
                values=(item.old_name, item.new_name, str(item.source.parent), item.status.value, item.detail),
                tags=(tag,),
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
        self._last_scan = None
        self.execute_button.configure(state="disabled")
        self.details_button.configure(state="normal")
        self.progress.configure(value=max(len(result.records), 1))
        self.progress_text_var.set(
            f"完成：成功 {result.succeeded}，跳过 {result.skipped}，失败 {result.failed}"
        )
        self.status_var.set("批量处理已结束。可查看结果详情；如需继续修改，请重新扫描。")
        level = messagebox.showinfo if result.failed == 0 else messagebox.showwarning
        level(
            "处理完成",
            f"成功：{result.succeeded} 项\n跳过：{result.skipped} 项\n失败：{result.failed} 项\n\n"
            "点击主窗口中的“查看结果详情”可查看每一项的处理记录。",
            parent=self.root,
        )

    def _poll_messages(self) -> None:
        try:
            while True:
                message = self._messages.get_nowait()
                kind = message[0]
                if kind == "scan_done":
                    self._handle_scan_done(message[1])
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
        self.scan_button.configure(state=state)
        for widget in self._input_widgets:
            widget.configure(state=state)
        if busy:
            self.execute_button.configure(state="disabled")
        self._update_depth_state()

    def _show_execution_details(self) -> None:
        if self._last_execution is None:
            return
        window = tk.Toplevel(self.root)
        window.title("重命名结果详情")
        window.geometry("1000x560")
        window.transient(self.root)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                f"成功 {self._last_execution.succeeded} 项；"
                f"跳过 {self._last_execution.skipped} 项；"
                f"失败 {self._last_execution.failed} 项"
            ),
            style="Stats.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        text = tk.Text(frame, wrap="none", font=("Consolas", 9))
        ybar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        text.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        for index, record in enumerate(self._last_execution.records, start=1):
            text.insert(
                "end",
                f"{index:>4}. [{record.outcome}] {record.kind.value}\n"
                f"      原：{record.source}\n"
                f"      新：{record.target}\n"
                f"      说明：{record.detail}\n\n",
            )
        text.configure(state="disabled")
        xbar.pack(side="bottom", fill="x")

    def _show_help(self) -> None:
        help_text = """使用流程

1. 选择根目录。根目录本身不会改名，只处理其内部项目。
2. 保持“全部层级”，或限制为 1–N 层。第 1 层是根目录中的直接子项。
3. 输入查找内容和替换内容，选择处理文件夹、文件或两者。
4. 点击“扫描预览”。扫描只读取名称，不会修改磁盘。
5. 检查文件夹和文件两个标签页中的原名称、新名称及状态。
6. 点击“执行重命名”，核对汇总并二次确认。执行期间会显示逐项进度。

普通文本模式

查找内容按原样匹配，并替换名称中的每一处。例如查找“旧版”、替换为“新版”。替换内容可留空，表示删除匹配文本。

正则表达式模式

使用 Python 正则语法。示例：查找 (\\d{4})-(\\d{2})-(\\d{2})，替换为 \\1\\2\\3，可把 2026-08-27 改为 20260827。输入的表达式或捕获组引用无效时，规则说明区会立即提示。

文件扩展名

默认只修改文件主名称，保护最后一个扩展名。例如查找 jpg 不会改变“照片.jpg”的扩展名。只有明确勾选“允许修改文件扩展名”后，才会处理完整文件名。

安全与跳过策略

工具不会覆盖已有项目。目标已存在、多个项目生成同一目标、名称含 Windows 非法字符、名称为空或使用 CON 等保留名时，预览会用红色标出并跳过。执行前还会再次检查磁盘状态。子项目先于父文件夹处理；符号链接不会被跟随。

注意：执行完成后本工具不提供自动撤销。建议对重要目录先备份，并认真检查预览。"""
        window = tk.Toplevel(self.root)
        window.title("使用说明")
        window.geometry("760x640")
        window.transient(self.root)
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", padx=10, pady=10, font=("Microsoft YaHei UI", 10), spacing2=3)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text.insert("1.0", help_text)
        text.configure(state="disabled")

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
    root = tk.Tk()
    BatchRenameApp(root)
    root.mainloop()
