use thiserror::Error;

#[derive(Debug, Error)]
pub enum DomainError {
    #[error("查找内容不能为空")]
    EmptySearch,
    #[error("正则表达式不能超过 4096 个字符")]
    RegexTooLong,
    #[error("正则表达式无效：{0}")]
    InvalidRegex(String),
    #[error("正则替换内容包含无效的捕获引用：{0}")]
    InvalidReplacementReference(String),
    #[error("正则表达式运行失败：{0}")]
    RegexRuntime(String),
    #[error("新名称不能为空")]
    EmptyName,
    #[error("新名称不能是 . 或 ..")]
    DotName,
    #[error("新名称不能超过 255 个字符")]
    NameTooLong,
    #[error("新名称包含 Windows 不允许的字符")]
    InvalidNameCharacter,
    #[error("新名称不能以空格或句点结尾")]
    TrailingDotOrSpace,
    #[error("{0} 是 Windows 保留名称")]
    ReservedName(String),
}

impl DomainError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::EmptySearch => "emptySearch",
            Self::RegexTooLong => "regexTooLong",
            Self::InvalidRegex(_) => "invalidRegex",
            Self::InvalidReplacementReference(_) => "invalidReplacementReference",
            Self::RegexRuntime(_) => "regexRuntimeError",
            Self::EmptyName => "emptyName",
            Self::DotName => "dotName",
            Self::NameTooLong => "nameTooLong",
            Self::InvalidNameCharacter => "invalidNameCharacter",
            Self::TrailingDotOrSpace => "trailingDotOrSpace",
            Self::ReservedName(_) => "reservedName",
        }
    }
}
