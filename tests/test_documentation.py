import re
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"
REQUIRED_VISUALS = {
    "docs/images/batch-rename-compact.png",
    "docs/images/batch-rename-main.png",
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
