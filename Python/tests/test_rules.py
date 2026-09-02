import re

import pytest

from batch_rename.core import RenameRule, RuleError, validate_windows_name


def test_plain_text_replaces_every_occurrence():
    rule = RenameRule("旧版", "新版")

    assert rule.rename("旧版-资料-旧版", is_file=False) == "新版-资料-新版"


def test_regex_supports_capture_group_replacement():
    rule = RenameRule(r"(\d{4})-(\d{2})-(\d{2})", r"\1\2\3", use_regex=True)

    assert rule.rename("照片-2026-08-27.jpg", is_file=True) == "照片-20260827.jpg"


def test_file_extension_is_protected_by_default():
    rule = RenameRule("jpg", "png")

    assert rule.rename("jpg-原图.jpg", is_file=True) == "png-原图.jpg"


def test_file_extension_can_be_renamed_explicitly():
    rule = RenameRule("jpg", "png", rename_extension=True)

    assert rule.rename("jpg-原图.jpg", is_file=True) == "png-原图.png"


@pytest.mark.parametrize(
    "name",
    ["", "CON.txt", "bad:name.txt", "尾随空格 ", "尾随点.", ".", ".."],
)
def test_windows_invalid_names_are_rejected(name):
    assert validate_windows_name(name) is not None


def test_chinese_name_is_valid():
    assert validate_windows_name("项目资料（最终版）.docx") is None


def test_empty_search_text_is_rejected():
    with pytest.raises(RuleError, match="查找内容不能为空"):
        RenameRule("", "任意")


def test_invalid_regular_expression_is_explained():
    with pytest.raises(RuleError, match="正则表达式无效"):
        RenameRule("(", "", use_regex=True)


def test_invalid_regular_expression_replacement_is_explained():
    with pytest.raises(RuleError, match="替换内容无效"):
        RenameRule(r"(a)", r"\2", use_regex=True)
