"""可直接套用并经过真实规则验证的正则表达式模板。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegexExample:
    category: str
    title: str
    purpose: str
    search: str
    replacement: str
    before: str
    after: str
    rename_extension: bool = False


REGEX_EXAMPLES: tuple[RegexExample, ...] = (
    RegexExample(
        category="日期时间",
        title="压缩标准日期",
        purpose="把名称中的年-月-日整理为连续八位日期，适合需要按日期快速排序的归档名称。",
        search=r"(\d{4})-(\d{2})-(\d{2})",
        replacement=r"\1\2\3",
        before="会议纪要_2026-08-27.docx",
        after="会议纪要_20260827.docx",
    ),
    RegexExample(
        category="日期时间",
        title="统一日期分隔符",
        purpose="把点号、斜杠或下划线分隔的日期统一为年-月-日格式。",
        search=r"(\d{4})[._/](\d{2})[._/](\d{2})",
        replacement=r"\1-\2-\3",
        before="会议纪要_2026.08.27.docx",
        after="会议纪要_2026-08-27.docx",
    ),
    RegexExample(
        category="日期时间",
        title="把末尾日期移到开头",
        purpose="把主体名称末尾的标准日期移到最前面，使同一目录更容易按时间排列。",
        search=r"^(.+?)[_-](\d{4}-\d{2}-\d{2})$",
        replacement=r"\2_\1",
        before="日报_2026-08-27.docx",
        after="2026-08-27_日报.docx",
    ),
    RegexExample(
        category="编号整理",
        title="保留图片序号",
        purpose="把相机默认前缀换成中文名称，同时原样保留后面的任意位数字序号。",
        search=r"IMG_(\d+)",
        replacement=r"照片_\1",
        before="IMG_001.jpg",
        after="照片_001.jpg",
    ),
    RegexExample(
        category="编号整理",
        title="规范开头数字编号",
        purpose="识别名称开头的数字，删除它后面的旧分隔符，并统一为“编号数字_”格式。",
        search=r"^(\d+)[-_ ]*",
        replacement=r"编号\1_",
        before="012-报告.txt",
        after="编号012_报告.txt",
    ),
    RegexExample(
        category="编号整理",
        title="整理中文编号",
        purpose="把“第12、名称”一类开头编号整理为便于排序的“12_名称”。",
        search=r"^第?(\d+)[-_、. ]+",
        replacement=r"\1_",
        before="第12、方案.docx",
        after="12_方案.docx",
    ),
    RegexExample(
        category="标签清理",
        title="删除方括号标签",
        purpose="删除名称中用半角方括号包围的状态标签，方括号以外的内容保持不变。",
        search=r"\[[^\]]+\]",
        replacement="",
        before="[已审核]合同.docx",
        after="合同.docx",
    ),
    RegexExample(
        category="标签清理",
        title="删除圆括号备注",
        purpose="删除中文或英文圆括号中的备注，适合清理“已审核”“最终版”等附加状态。",
        search=r"[\(（][^\)）]+[\)）]",
        replacement="",
        before="合同（已审核）.docx",
        after="合同.docx",
    ),
    RegexExample(
        category="文本清理",
        title="删除首尾空白",
        purpose="只清除名称开头和结尾的空格，不影响名称中间用于分词的单个空格。",
        search=r"^\s+|\s+$",
        replacement="",
        before="  会议纪要  .docx",
        after="会议纪要.docx",
    ),
    RegexExample(
        category="文本清理",
        title="合并连续空格",
        purpose="把名称中连续出现的两个或更多空白字符统一为一个半角空格。",
        search=r"\s{2,}",
        replacement=" ",
        before="项目  最终  版本.txt",
        after="项目 最终 版本.txt",
    ),
    RegexExample(
        category="文本清理",
        title="统一连续连接符",
        purpose="把连续的横线、下划线或空格统一为一个下划线，清理混乱的分隔符。",
        search=r"[-_\s]{2,}",
        replacement="_",
        before="项目---最终__版本.txt",
        after="项目_最终_版本.txt",
    ),
    RegexExample(
        category="文本清理",
        title="删除旧版或临时前缀",
        purpose="删除名称开头的“旧版”或“临时”标记，并顺便移除紧随其后的单个分隔符。",
        search=r"^(旧版|临时)[-_ ]?",
        replacement="",
        before="旧版-合同.docx",
        after="合同.docx",
    ),
    RegexExample(
        category="文本清理",
        title="删除副本后缀",
        purpose="删除主名称末尾的“_副本”“-副本”或英文 copy，文件扩展名仍保持不变。",
        search=r"[_-](副本|copy)$",
        replacement="",
        before="预算_副本.xlsx",
        after="预算.xlsx",
    ),
    RegexExample(
        category="片段调整",
        title="交换名称片段",
        purpose="把下划线后的大写状态移到名称前面，并保留下划线前的主体名称。",
        search=r"(.+)_([A-Z]+)",
        replacement=r"\2_\1",
        before="project_FINAL.txt",
        after="FINAL_project.txt",
    ),
    RegexExample(
        category="扩展名",
        title="统一 JPEG 扩展名",
        purpose="把 jpeg、JPEG 或 JPG 统一为小写 .jpg。此模板会自动开启扩展名处理。",
        search=r"(?i)\.jpe?g$",
        replacement=".jpg",
        before="照片.JPEG",
        after="照片.jpg",
        rename_extension=True,
    ),
)
