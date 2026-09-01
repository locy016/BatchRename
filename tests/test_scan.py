from pathlib import Path

import pytest

from batch_rename.core import RuleError, ScanError, scan, search_matches
from batch_rename.models import CandidateStatus, ItemKind, MatchOptions, ScanOptions


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("测试", encoding="utf-8")
    return path


def test_search_matches_does_not_require_replacement(tmp_path):
    source = touch(tmp_path / "项目合同.docx")

    result = search_matches(MatchOptions(tmp_path, "项目"))

    assert [item.source for item in result.items] == [source]
    assert result.search == "项目"
    assert result.use_regex is False


def test_search_matches_validates_regex_without_replacement(tmp_path):
    with pytest.raises(RuleError, match="正则表达式"):
        search_matches(MatchOptions(tmp_path, "(", use_regex=True))


def test_search_matches_respects_object_type_and_depth(tmp_path):
    folder = tmp_path / "项目一级"
    folder.mkdir()
    nested = touch(folder / "项目二级.txt")
    direct = touch(tmp_path / "项目直属.txt")

    result = search_matches(
        MatchOptions(
            tmp_path,
            "项目",
            max_depth=1,
            include_files=True,
            include_dirs=False,
        )
    )

    assert [item.source for item in result.items] == [direct]
    assert nested not in {item.source for item in result.items}


def test_unlimited_depth_scans_files_and_directories(tmp_path):
    folder = tmp_path / "旧版目录"
    nested = touch(folder / "第二层" / "旧版文件.txt")

    result = scan(ScanOptions(tmp_path, "旧版", "新版"))

    assert {(item.kind, item.source) for item in result.candidates} == {
        (ItemKind.DIRECTORY, folder),
        (ItemKind.FILE, nested),
    }


def test_depth_one_only_scans_direct_children(tmp_path):
    folder = tmp_path / "旧版一级"
    folder.mkdir()
    nested = touch(folder / "旧版二级.txt")
    direct = touch(tmp_path / "旧版直属.txt")

    result = scan(ScanOptions(tmp_path, "旧版", "新版", max_depth=1))

    assert {item.source for item in result.candidates} == {folder, direct}
    assert nested not in {item.source for item in result.candidates}


def test_object_type_filter_can_select_only_directories(tmp_path):
    folder = tmp_path / "旧版目录"
    folder.mkdir()
    touch(tmp_path / "旧版文件.txt")

    result = scan(
        ScanOptions(tmp_path, "旧版", "新版", include_files=False, include_dirs=True)
    )

    assert [item.source for item in result.candidates] == [folder]


def test_existing_target_is_marked_as_conflict(tmp_path):
    source = touch(tmp_path / "旧版.txt")
    touch(tmp_path / "新版.txt")

    result = scan(ScanOptions(tmp_path, "旧版", "新版"))

    item = next(item for item in result.candidates if item.source == source)
    assert item.status is CandidateStatus.CONFLICT
    assert "已存在" in item.detail


def test_two_sources_with_same_target_are_both_marked_duplicate(tmp_path):
    first = touch(tmp_path / "资料1.txt")
    second = touch(tmp_path / "资料2.txt")

    result = scan(
        ScanOptions(tmp_path, r"\d", "", use_regex=True, include_dirs=False)
    )

    items = {item.source: item for item in result.candidates}
    assert items[first].status is CandidateStatus.DUPLICATE
    assert items[second].status is CandidateStatus.DUPLICATE


def test_invalid_generated_name_is_included_with_explanation(tmp_path):
    source = touch(tmp_path / "旧名.txt")

    result = scan(ScanOptions(tmp_path, "旧名", "bad:name"))

    assert result.candidates[0].source == source
    assert result.candidates[0].status is CandidateStatus.INVALID
    assert "不允许" in result.candidates[0].detail


def test_root_directory_itself_is_never_a_candidate(tmp_path):
    root = tmp_path / "旧版根目录"
    root.mkdir()

    result = scan(ScanOptions(root, "旧版", "新版"))

    assert result.candidates == []


@pytest.mark.parametrize("max_depth", [0, -1])
def test_depth_must_be_positive(max_depth, tmp_path):
    with pytest.raises(ScanError, match="层级"):
        scan(ScanOptions(tmp_path, "旧", "新", max_depth=max_depth))


def test_root_must_be_an_existing_directory(tmp_path):
    with pytest.raises(ScanError, match="不存在或不是文件夹"):
        scan(ScanOptions(tmp_path / "missing", "旧", "新"))


def test_same_replacement_still_lists_matching_name(tmp_path):
    source = touch(tmp_path / "众川合同.docx")

    result = scan(ScanOptions(tmp_path, "众川", "众川"))

    assert len(result.candidates) == 1
    assert result.candidates[0].source == source
    assert result.candidates[0].status is CandidateStatus.UNCHANGED
    assert "没有变化" in result.candidates[0].detail
    assert result.ready == []


def test_match_in_protected_extension_is_listed_as_unchanged(tmp_path):
    source = touch(tmp_path / "照片.jpg")

    result = scan(ScanOptions(tmp_path, "jpg", "png"))

    assert len(result.candidates) == 1
    assert result.candidates[0].source == source
    assert result.candidates[0].status is CandidateStatus.UNCHANGED
    assert "扩展名" in result.candidates[0].detail
