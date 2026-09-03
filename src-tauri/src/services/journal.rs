use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::domain::errors::DomainError;
use crate::domain::models::{OperationLogV1, OperationStatus};

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationQuery {
    pub query: String,
    pub status: Option<OperationStatus>,
    pub offset: usize,
    pub limit: usize,
}

impl Default for OperationQuery {
    fn default() -> Self {
        Self {
            query: String::new(),
            status: None,
            offset: 0,
            limit: 50,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationSummary {
    pub identifier: String,
    pub created_at: String,
    pub updated_at: String,
    pub root: PathBuf,
    pub search: String,
    pub replacement: String,
    pub status: OperationStatus,
    pub item_count: usize,
    pub success_count: usize,
    pub skipped_count: usize,
    pub failed_count: usize,
    pub undone_count: usize,
    pub pending_undo_count: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationPage {
    pub items: Vec<OperationSummary>,
    pub total: usize,
}

#[derive(Debug, Clone)]
pub struct OperationStore {
    directory: PathBuf,
}

impl OperationStore {
    pub fn new(directory: impl Into<PathBuf>) -> Self {
        Self {
            directory: directory.into(),
        }
    }

    pub fn default_for_user() -> Self {
        let base = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("AppData").join("Local"));
        Self::new(base.join("BatchRename").join("operations"))
    }

    pub fn create(&self, operation: &OperationLogV1) -> Result<(), DomainError> {
        let path = self.path_for(&operation.identifier)?;
        if path.exists() {
            return Err(DomainError::Io("操作档案已经存在".into()));
        }
        self.save(operation)
    }

    pub fn save(&self, operation: &OperationLogV1) -> Result<(), DomainError> {
        let target = self.path_for(&operation.identifier)?;
        fs::create_dir_all(&self.directory).map_err(io_error)?;
        let temporary = self.directory.join(format!(
            ".{}-{}.tmp",
            operation.identifier,
            Uuid::new_v4().simple()
        ));
        let result = (|| {
            let bytes = serde_json::to_vec_pretty(operation)
                .map_err(|error| DomainError::Io(error.to_string()))?;
            let mut file = File::create(&temporary).map_err(io_error)?;
            file.write_all(&bytes).map_err(io_error)?;
            file.write_all(b"\n").map_err(io_error)?;
            file.sync_all().map_err(io_error)?;
            replace_file(&temporary, &target)
        })();
        let _ = fs::remove_file(&temporary);
        result
    }

    pub fn load(&self, identifier: &str) -> Result<OperationLogV1, DomainError> {
        let path = self.path_for(identifier)?;
        let mut operation: OperationLogV1 =
            serde_json::from_slice(&fs::read(path).map_err(io_error)?)
                .map_err(|error| DomainError::Io(error.to_string()))?;
        match operation.status {
            OperationStatus::Preparing | OperationStatus::Running => {
                operation.status = OperationStatus::Interrupted;
                if operation.error.is_empty() {
                    operation.error = "程序在操作完成前退出".into();
                }
                self.save(&operation)?;
            }
            OperationStatus::Undoing => {
                operation.status = OperationStatus::PartiallyUndone;
                if operation.error.is_empty() {
                    operation.error = "程序在撤回完成前退出".into();
                }
                self.save(&operation)?;
            }
            _ => {}
        }
        Ok(operation)
    }

    pub fn query(&self, query: OperationQuery) -> Result<OperationPage, DomainError> {
        if !self.directory.exists() {
            return Ok(OperationPage {
                items: Vec::new(),
                total: 0,
            });
        }
        let mut summaries = Vec::new();
        for entry in fs::read_dir(&self.directory).map_err(io_error)? {
            let entry = entry.map_err(io_error)?;
            if entry.path().extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let identifier = entry
                .path()
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned();
            let operation = self
                .load(&identifier)
                .unwrap_or_else(|error| OperationLogV1 {
                    schema_version: 1,
                    identifier,
                    created_at: String::new(),
                    updated_at: String::new(),
                    root: self.directory.clone(),
                    search: String::new(),
                    replacement: String::new(),
                    use_regex: false,
                    max_depth: None,
                    include_files: true,
                    include_dirs: true,
                    rename_extension: false,
                    status: OperationStatus::Corrupt,
                    items: Vec::new(),
                    error: error.to_string(),
                });
            if query
                .status
                .is_some_and(|status| status != operation.status)
            {
                continue;
            }
            let keyword = query.query.trim().to_lowercase();
            let haystack = format!(
                "{}\n{}\n{}\n{}",
                operation.identifier,
                operation.root.display(),
                operation.search,
                operation.replacement
            )
            .to_lowercase();
            if !keyword.is_empty() && !haystack.contains(&keyword) {
                continue;
            }
            summaries.push(summary(&operation));
        }
        summaries.sort_by(|a, b| {
            b.created_at
                .cmp(&a.created_at)
                .then_with(|| b.identifier.cmp(&a.identifier))
        });
        let total = summaries.len();
        let limit = query.limit.clamp(1, 200);
        let items = summaries
            .into_iter()
            .skip(query.offset)
            .take(limit)
            .collect();
        Ok(OperationPage { items, total })
    }

    fn path_for(&self, identifier: &str) -> Result<PathBuf, DomainError> {
        if identifier.is_empty()
            || !identifier.chars().all(|character| {
                character.is_ascii_alphanumeric() || matches!(character, '-' | '_')
            })
        {
            return Err(DomainError::Io("操作标识包含不安全字符".into()));
        }
        Ok(self.directory.join(format!("{identifier}.json")))
    }
}

fn summary(operation: &OperationLogV1) -> OperationSummary {
    OperationSummary {
        identifier: operation.identifier.clone(),
        created_at: operation.created_at.clone(),
        updated_at: operation.updated_at.clone(),
        root: operation.root.clone(),
        search: operation.search.clone(),
        replacement: operation.replacement.clone(),
        status: operation.status,
        item_count: operation.items.len(),
        success_count: operation
            .items
            .iter()
            .filter(|item| item.outcome == "成功")
            .count(),
        skipped_count: operation
            .items
            .iter()
            .filter(|item| item.outcome == "跳过")
            .count(),
        failed_count: operation
            .items
            .iter()
            .filter(|item| item.outcome == "失败")
            .count(),
        undone_count: operation
            .items
            .iter()
            .filter(|item| item.undo_status == crate::domain::models::UndoStatus::Undone)
            .count(),
        pending_undo_count: operation
            .items
            .iter()
            .filter(|item| {
                item.outcome == "成功"
                    && item.undo_status != crate::domain::models::UndoStatus::Undone
            })
            .count(),
    }
}

fn io_error(error: std::io::Error) -> DomainError {
    DomainError::Io(error.to_string())
}

#[cfg(windows)]
fn replace_file(source: &Path, target: &Path) -> Result<(), DomainError> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::{
        MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH, MoveFileExW,
    };
    let source: Vec<u16> = source.as_os_str().encode_wide().chain(Some(0)).collect();
    let target: Vec<u16> = target.as_os_str().encode_wide().chain(Some(0)).collect();
    let success = unsafe {
        MoveFileExW(
            source.as_ptr(),
            target.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if success == 0 {
        Err(io_error(std::io::Error::last_os_error()))
    } else {
        Ok(())
    }
}

#[cfg(not(windows))]
fn replace_file(source: &Path, target: &Path) -> Result<(), DomainError> {
    fs::rename(source, target).map_err(io_error)
}
