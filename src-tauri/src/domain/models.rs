use std::path::PathBuf;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ItemKind {
    #[serde(rename = "文件夹")]
    Directory,
    #[serde(rename = "文件")]
    File,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CandidateStatus {
    #[serde(rename = "可修改")]
    Ready,
    #[serde(rename = "名称未变化")]
    Unchanged,
    #[serde(rename = "目标已存在")]
    Conflict,
    #[serde(rename = "批内目标重复")]
    Duplicate,
    #[serde(rename = "名称不合法")]
    Invalid,
    #[serde(rename = "无法处理")]
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MatchOptions {
    pub root: PathBuf,
    pub search: String,
    pub use_regex: bool,
    pub max_depth: Option<usize>,
    pub include_files: bool,
    pub include_dirs: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MatchedItem {
    pub source: PathBuf,
    pub kind: ItemKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RenameCandidate {
    pub source: PathBuf,
    pub target: PathBuf,
    pub kind: ItemKind,
    pub status: CandidateStatus,
    pub detail: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OperationStatus {
    #[serde(rename = "准备中")]
    Preparing,
    #[serde(rename = "执行中")]
    Running,
    #[serde(rename = "已完成")]
    Completed,
    #[serde(rename = "部分失败")]
    Partial,
    #[serde(rename = "已中断")]
    Interrupted,
    #[serde(rename = "撤回检查失败")]
    UndoCheckFailed,
    #[serde(rename = "撤回中")]
    Undoing,
    #[serde(rename = "已撤回")]
    Undone,
    #[serde(rename = "部分撤回")]
    PartiallyUndone,
    #[serde(rename = "记录损坏")]
    Corrupt,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UndoStatus {
    #[serde(rename = "待撤回")]
    Pending,
    #[serde(rename = "已撤回")]
    Undone,
    #[serde(rename = "撤回失败")]
    Failed,
    #[serde(rename = "无需撤回")]
    NotApplicable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperationItemV1 {
    pub source: PathBuf,
    pub target: PathBuf,
    pub kind: ItemKind,
    pub outcome: String,
    pub detail: String,
    pub execution_index: Option<usize>,
    pub undo_status: UndoStatus,
    pub undo_detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperationLogV1 {
    pub schema_version: u32,
    pub identifier: String,
    pub created_at: String,
    pub updated_at: String,
    pub root: PathBuf,
    pub search: String,
    pub replacement: String,
    pub use_regex: bool,
    pub max_depth: Option<usize>,
    pub include_files: bool,
    pub include_dirs: bool,
    pub rename_extension: bool,
    pub status: OperationStatus,
    pub items: Vec<OperationItemV1>,
    pub error: String,
}
