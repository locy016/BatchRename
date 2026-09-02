use std::fs;
use std::path::Path;

use chrono::Local;
use uuid::Uuid;

use crate::domain::errors::DomainError;
use crate::domain::models::{
    CandidateStatus, ExecutionProgress, ExecutionSummary, OperationItemV1, OperationLogV1,
    OperationStatus, PreviewResult, UndoStatus,
};
use crate::services::journal::OperationStore;

#[derive(Debug, Clone)]
pub struct ExecutionOptions {
    pub search: String,
    pub replacement: String,
    pub use_regex: bool,
    pub max_depth: Option<usize>,
    pub include_files: bool,
    pub include_dirs: bool,
    pub rename_extension: bool,
}

impl ExecutionOptions {
    pub fn demo(search: &str, replacement: &str) -> Self {
        Self {
            search: search.into(),
            replacement: replacement.into(),
            use_regex: false,
            max_depth: None,
            include_files: true,
            include_dirs: true,
            rename_extension: false,
        }
    }
}

pub fn execute_preview(
    preview: &PreviewResult,
    options: &ExecutionOptions,
    store: &OperationStore,
    mut progress: impl FnMut(ExecutionProgress),
) -> Result<ExecutionSummary, DomainError> {
    let timestamp = Local::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let identifier = format!(
        "{}-{}",
        Local::now().format("%Y%m%d-%H%M%S"),
        &Uuid::new_v4().simple().to_string()[..8]
    );
    let mut operation = OperationLogV1 {
        schema_version: 1,
        identifier: identifier.clone(),
        created_at: timestamp.clone(),
        updated_at: timestamp,
        root: preview.root.clone(),
        search: options.search.clone(),
        replacement: options.replacement.clone(),
        use_regex: options.use_regex,
        max_depth: options.max_depth,
        include_files: options.include_files,
        include_dirs: options.include_dirs,
        rename_extension: options.rename_extension,
        status: OperationStatus::Preparing,
        error: String::new(),
        items: preview
            .candidates
            .iter()
            .map(|candidate| OperationItemV1 {
                source: candidate.source.clone(),
                target: candidate.target.clone(),
                kind: candidate.kind,
                outcome: "待执行".into(),
                detail: candidate.detail.clone(),
                execution_index: None,
                undo_status: UndoStatus::NotApplicable,
                undo_detail: String::new(),
            })
            .collect(),
    };
    store.create(&operation)?;
    operation.status = OperationStatus::Running;
    store.save(&operation)?;

    let mut order: Vec<usize> = (0..preview.candidates.len()).collect();
    order.sort_by_key(|index| {
        std::cmp::Reverse(preview.candidates[*index].source.components().count())
    });
    let total = order.len();
    let mut succeeded = 0;
    let mut skipped = 0;
    let mut failed = 0;

    for (position, index) in order.into_iter().enumerate() {
        let candidate = &preview.candidates[index];
        let (outcome, detail) = if candidate.status != CandidateStatus::Ready {
            skipped += 1;
            ("跳过", candidate.detail.clone())
        } else if !candidate.source.exists() {
            skipped += 1;
            ("跳过", "来源在扫描后已不存在".into())
        } else if candidate.target.exists()
            && path_key(&candidate.target) != path_key(&candidate.source)
        {
            skipped += 1;
            ("跳过", "目标在扫描后已存在".into())
        } else {
            match rename_path(&candidate.source, &candidate.target) {
                Ok(()) => {
                    succeeded += 1;
                    ("成功", "重命名完成".into())
                }
                Err(error) => {
                    failed += 1;
                    ("失败", error.to_string())
                }
            }
        };
        let item = &mut operation.items[index];
        item.outcome = outcome.into();
        item.detail = detail.clone();
        item.execution_index = Some(position + 1);
        item.undo_status = if outcome == "成功" {
            UndoStatus::Pending
        } else {
            UndoStatus::NotApplicable
        };
        if let Err(error) = store.save(&operation) {
            operation.status = OperationStatus::Interrupted;
            operation.error = format!("逐项操作档案保存失败：{error}");
            let _ = store.save(&operation);
            return Err(error);
        }
        progress(ExecutionProgress {
            current: position + 1,
            total,
            relative_path: candidate
                .source
                .strip_prefix(&preview.root)
                .unwrap_or(&candidate.source)
                .to_path_buf(),
            outcome: outcome.into(),
            detail,
        });
    }
    operation.status = if failed > 0 {
        OperationStatus::Partial
    } else {
        OperationStatus::Completed
    };
    store.save(&operation)?;
    Ok(ExecutionSummary {
        operation_id: identifier,
        succeeded,
        skipped,
        failed,
    })
}

fn rename_path(source: &Path, target: &Path) -> Result<(), DomainError> {
    if source != target && path_key(source) == path_key(target) {
        let temporary =
            source.with_file_name(format!(".__batch_rename_{}__", Uuid::new_v4().simple()));
        fs::rename(source, &temporary).map_err(io_error)?;
        if let Err(error) = fs::rename(&temporary, target) {
            let _ = fs::rename(&temporary, source);
            return Err(io_error(error));
        }
        Ok(())
    } else {
        fs::rename(source, target).map_err(io_error)
    }
}

pub(crate) fn path_key(path: &Path) -> String {
    path.to_string_lossy().replace('/', "\\").to_lowercase()
}
fn io_error(error: std::io::Error) -> DomainError {
    DomainError::Io(error.to_string())
}
