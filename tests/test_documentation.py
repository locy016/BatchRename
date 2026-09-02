import re
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"
REQUIRED_VISUALS = {
    "docs/images/batch-rename-compact.png",
    "docs/images/batch-rename-main.png",
    "docs/images/batch-rename-operation-history.png",
    "docs/images/batch-rename-regex-templates.png",
    "docs/images/batch-rename-workflow.svg",
}


def _local_readme_images() -> set[str]:
    markdown = README_PATH.read_text(encoding="utf-8")
    targets = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown))
    return {
        target
        for target in targets
        if not target.startswith(("http://", "https://", "data:"))
    }


def test_readme_references_complete_product_visuals():
    assert REQUIRED_VISUALS <= _local_readme_images()


def test_every_local_readme_image_exists():
    for target in _local_readme_images():
        assert (PROJECT_ROOT / target).is_file(), f"README 图片不存在：{target}"


def test_workflow_visual_is_valid_svg_xml():
    workflow_path = PROJECT_ROOT / "docs/images/batch-rename-workflow.svg"

    root = ET.parse(workflow_path).getroot()

    assert root.tag.endswith("svg")
    assert root.attrib["viewBox"] == "0 0 1440 360"


def test_readme_describes_current_compact_result_table_and_window_minimum():
    markdown = README_PATH.read_text(encoding="utf-8")

    assert "1120×720" in markdown
    assert "（根目录）" in markdown
    assert "语义图标" in markdown
    assert "匹配结果详情" in markdown


def test_readme_describes_the_modern_workspace_inventory_and_appearance_modes():
    markdown = README_PATH.read_text(encoding="utf-8")

    assert "目录概况" in markdown
    assert "扫描范围、文件夹总数和文件总数" in markdown
    assert "匹配统计" in markdown and "结果表下方" in markdown
    assert "视图 → 外观" in markdown
    assert all(mode in markdown for mode in ("跟随系统", "浅色", "深色"))
    assert "正则模板" in markdown and "40%" in markdown and "60%" in markdown


def test_readme_describes_released_operation_history_and_safe_undo_without_stale_placeholders():
    markdown = README_PATH.read_text(encoding="utf-8")

    assert "1.1.0-beta.2" in markdown
    assert "%LOCALAPPDATA%\\BatchRename\\operations" in markdown
    assert "操作日志" in markdown
    assert "撤回管理" in markdown
    assert "整批安全检查" in markdown
    assert "batch-rename-operation-history.png" in markdown
    assert "撤回管理（开发中）" not in markdown
    assert "操作日志（开发中）" not in markdown
    assert "尚未提供自动撤回" not in markdown
