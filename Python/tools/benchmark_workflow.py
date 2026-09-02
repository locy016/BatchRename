"""以可重复场景测量 Python 版扫描与预览耗时。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from batch_rename.core import build_preview, search_matches
from batch_rename.models import MatchOptions


def benchmark_scenario(
    root: Path,
    options: MatchOptions,
    *,
    replacement: str,
) -> dict[str, object]:
    """执行只读扫描和预览，返回便于跨实现比较的毫秒指标。"""

    scan_started = perf_counter_ns()
    matches = search_matches(options)
    scan_finished = perf_counter_ns()
    preview = build_preview(matches, replacement)
    preview_finished = perf_counter_ns()
    return {
        "scenario": root.name,
        "entries": matches.scanned_directory_count + matches.scanned_file_count,
        "matched": len(matches.items),
        "ready": len(preview.ready),
        "scanMs": round((scan_finished - scan_started) / 1_000_000, 3),
        "previewMs": round((preview_finished - scan_finished) / 1_000_000, 3),
    }


def _populate(root: Path, entries: int) -> None:
    for index in range(entries):
        category = root / f"分类{index % 20:02d}"
        category.mkdir(exist_ok=True)
        (category / f"项目_{index:06d}.txt").touch()


def main() -> None:
    parser = argparse.ArgumentParser(description="测量 Python 版名称扫描与预览耗时")
    parser.add_argument("--entries", type=int, default=1_000)
    args = parser.parse_args()
    if args.entries < 1:
        parser.error("--entries 必须大于 0")

    with tempfile.TemporaryDirectory(prefix="batch-rename-benchmark-") as directory:
        root = Path(directory) / f"python-{args.entries}"
        root.mkdir()
        _populate(root, args.entries)
        result = benchmark_scenario(
            root,
            MatchOptions(root=root, search="项目"),
            replacement="客户",
        )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
