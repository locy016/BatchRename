"""可直接套用的正则表达式重命名示例。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegexExample:
    title: str
    purpose: str
    search: str
    replacement: str
    before: str
    after: str


REGEX_EXAMPLES: tuple[RegexExample, ...] = (
    RegexExample(
        title="压缩日期格式",
        purpose="把名称中的年-月-日整理为连续八位日期。括号创建捕获组，替换内容中的编号按原顺序取回对应部分。",
        search=r"(\d{4})-(\d{2})-(\d{2})",
        replacement=r"\1\2\3",
        before="会议纪要_2026-08-27.docx",
        after="会议纪要_20260827.docx",
    ),
    RegexExample(
        title="保留图片序号",
        purpose="把相机前缀换成中文名称，同时保留后面的任意位数字序号。",
        search=r"IMG_(\d+)",
        replacement=r"照片_\1",
        before="IMG_001.jpg",
        after="照片_001.jpg",
    ),
    RegexExample(
        title="删除方括号标签",
        purpose="删除名称中用半角方括号包围的标签，方括号以外的内容保持不变。",
        search=r"\[[^\]]+\]",
        replacement="",
        before="[已审核]合同.docx",
        after="合同.docx",
    ),
    RegexExample(
        title="交换名称片段",
        purpose="把下划线后的大写状态移到名称前面，并保留下划线前的主体名称。",
        search=r"(.+)_([A-Z]+)",
        replacement=r"\2_\1",
        before="project_FINAL.txt",
        after="FINAL_project.txt",
    ),
)
