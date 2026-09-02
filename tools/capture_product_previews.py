"""生成 README 使用的真实、安全界面预览；不会执行任何文件操作。"""

from __future__ import annotations

import ctypes
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from batch_rename.app import BatchRenameApp
from batch_rename.models import (
    CandidateStatus,
    ItemKind,
    MatchedItem,
    MatchResult,
    RenameCandidate,
    ScanResult,
)


IMAGE_DIR = PROJECT_ROOT / "docs" / "images"
DEMO_ROOT = Path("D:/演示资料")


def candidate(
    relative_source: str,
    new_name: str,
    kind: ItemKind,
    status: CandidateStatus,
    detail: str,
) -> RenameCandidate:
    source = DEMO_ROOT / relative_source
    return RenameCandidate(
        source=source,
        target=source.with_name(new_name),
        kind=kind,
        status=status,
        detail=detail,
    )


DEMO_ITEMS = [
    candidate("项目归档", "客户归档", ItemKind.DIRECTORY, CandidateStatus.READY, "名称有效，可以执行重命名。"),
    candidate("合同/2026/项目交付", "客户交付", ItemKind.DIRECTORY, CandidateStatus.READY, "名称有效，可以执行重命名。"),
    candidate("项目说明.txt", "客户说明.txt", ItemKind.FILE, CandidateStatus.READY, "名称有效，可以执行重命名。"),
    candidate("合同/2026/项目清单.xlsx", "客户清单.xlsx", ItemKind.FILE, CandidateStatus.READY, "名称有效，可以执行重命名。"),
    candidate("合同/2026/项目项目记录.docx", "客户客户记录.docx", ItemKind.FILE, CandidateStatus.READY, "名称中的每一处匹配内容都会被替换。"),
    candidate("项目模板.docx", "项目模板.docx", ItemKind.FILE, CandidateStatus.UNCHANGED, "替换后名称与原名称相同，不会执行动作。"),
    candidate("历史/项目预算.xlsx", "客户预算.xlsx", ItemKind.FILE, CandidateStatus.CONFLICT, "目标名称已经存在，程序不会覆盖。"),
]


def populate(app: BatchRenameApp) -> None:
    app.directory_var.set(str(DEMO_ROOT))
    app.search_var.set("项目")
    app.replacement_var.set("客户")
    matches = MatchResult(
        root=DEMO_ROOT,
        search="项目",
        use_regex=False,
        items=[MatchedItem(item.source, item.kind) for item in DEMO_ITEMS],
        scanned_directory_count=18,
        scanned_file_count=205,
        errors=[],
    )
    app._last_matches = matches
    app._last_scan = ScanResult(root=DEMO_ROOT, candidates=list(DEMO_ITEMS))
    app._set_directory_inventory(matches)
    app._set_match_statistics(7, 5, 1, 1)
    app.status_var.set("结果预览已生成：请核对新名称、状态和说明，再确认执行。")
    app.progress_text_var.set("等待确认")
    app._fill_tree(app.result_tree, DEMO_ITEMS, root=DEMO_ROOT)
    app._sync_command_states()


def capture(root: tk.Tk, app: BatchRenameApp, path: Path) -> None:
    app.result_tree.focus_set()
    root.update_idletasks()
    root.update()
    app.new_name_overlay.refresh()
    app.result_icon_overlay.refresh()
    root.update_idletasks()
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    width = root.winfo_width()
    height = root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True).save(path)


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="batch-rename-preview-") as temp_dir:
        root = tk.Tk()
        app = BatchRenameApp(
            root,
            work_area_provider=lambda _root: (0, 0, 1920, 1080),
            preferences_path=Path(temp_dir) / "settings.json",
            system_light_provider=lambda: True,
        )
        app.set_appearance("light", persist=False)
        populate(app)
        root.geometry("1120x720+40+40")
        root.deiconify()
        root.lift()
        time.sleep(0.2)
        capture(root, app, IMAGE_DIR / "batch-rename-main.png")

        app._toggle_tool_panel("templates")
        time.sleep(0.2)
        capture(root, app, IMAGE_DIR / "batch-rename-regex-templates.png")
        app._close_tool_panel()

        app.set_appearance("dark", persist=False)
        root.geometry("1120x1000+40+40")
        root.update()
        app._apply_responsive_layout(1120, 1000)
        app.workflow_nav_button.invoke()
        time.sleep(0.2)
        capture(root, app, IMAGE_DIR / "batch-rename-compact.png")
        root.destroy()


if __name__ == "__main__":
    main()
