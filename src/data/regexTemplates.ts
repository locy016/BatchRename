export interface RegexTemplate{category:string;title:string;purpose:string;search:string;replacement:string;before:string;after:string;renameExtension:boolean}
export const regexTemplates:RegexTemplate[]=[
['日期时间','压缩标准日期','把日期整理为连续八位','(\\d{4})-(\\d{2})-(\\d{2})','\\1\\2\\3','纪要_2026-08-27.docx','纪要_20260827.docx',false],
['日期时间','统一日期分隔符','统一点号、斜杠和下划线','(\\d{4})[._/](\\d{2})[._/](\\d{2})','\\1-\\2-\\3','纪要_2026.08.27.docx','纪要_2026-08-27.docx',false],
['日期时间','末尾日期移到开头','让文件按日期排列','^(.+?)[_-](\\d{4}-\\d{2}-\\d{2})$','\\2_\\1','日报_2026-08-27.docx','2026-08-27_日报.docx',false],
['编号整理','保留图片序号','替换相机前缀并保留序号','IMG_(\\d+)','照片_\\1','IMG_001.jpg','照片_001.jpg',false],
['编号整理','规范开头数字编号','统一开头编号格式','^(\\d+)[-_ ]*','编号\\1_','012-报告.txt','编号012_报告.txt',false],
['编号整理','整理中文编号','整理“第12、”格式','^第?(\\d+)[-_、. ]+','\\1_','第12、方案.docx','12_方案.docx',false],
['标签清理','删除方括号标签','移除方括号状态标签','\\[[^\\]]+\\]','','[已审核]合同.docx','合同.docx',false],
['标签清理','删除圆括号备注','移除中英文括号备注','[\\(（][^\\)）]+[\\)）]','','合同（已审核）.docx','合同.docx',false],
['文本清理','删除首尾空白','保留名称中间空格','^\\s+|\\s+$','','  会议纪要  .docx','会议纪要.docx',false],
['文本清理','合并连续空格','连续空白改为一个空格','\\s{2,}',' ','项目  最终  版本.txt','项目 最终 版本.txt',false],
['文本清理','统一连续连接符','连续连接符改为下划线','[-_\\s]{2,}','_','项目---最终__版本.txt','项目_最终_版本.txt',false],
['文本清理','删除旧版或临时前缀','移除开头状态','^(旧版|临时)[-_ ]?','','旧版-合同.docx','合同.docx',false],
['文本清理','删除副本后缀','删除副本或 copy','[_-](副本|copy)$','','预算_副本.xlsx','预算.xlsx',false],
['片段调整','交换名称片段','交换主体与大写状态','(.+)_([A-Z]+)','\\2_\\1','project_FINAL.txt','FINAL_project.txt',false],
['扩展名','统一 JPEG 扩展名','统一为小写 jpg','(?i)\\.jpe?g$','.jpg','照片.JPEG','照片.jpg',true],
].map(([category,title,purpose,search,replacement,before,after,renameExtension])=>({category,title,purpose,search,replacement,before,after,renameExtension}as RegexTemplate))
