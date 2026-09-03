use std::fs;
use std::path::Path;

use crate::domain::errors::DomainError;
use crate::domain::models::{
    ItemKind, OperationLogV1, OperationStatus, UndoCheckItem, UndoCheckResult, UndoCheckState,
    UndoProgress, UndoStatus, UndoSummary,
};
use crate::services::executor::path_key;
use crate::services::journal::OperationStore;

pub fn preflight_undo(operation: &OperationLogV1) -> UndoCheckResult {
    let ordered = pending_order(operation);
    if operation.status == OperationStatus::Corrupt {
        return UndoCheckResult {
            operation_id: operation.identifier.clone(),
            token: operation.updated_at.clone(),
            items: Vec::new(),
            state: UndoCheckState::Unavailable,
            summary: "操作记录已损坏，无法进行安全撤回。".into(),
        };
    }
    if ordered.is_empty() {
        let successful_items: Vec<_> = operation
            .items
            .iter()
            .filter(|item| item.outcome == "成功")
            .collect();
        let completed = !successful_items.is_empty()
            && successful_items
                .iter()
                .all(|item| item.undo_status == UndoStatus::Undone);
        return UndoCheckResult {
            operation_id: operation.identifier.clone(),
            token: operation.updated_at.clone(),
            items: Vec::new(),
            state: if completed {
                UndoCheckState::Completed
            } else {
                UndoCheckState::Unavailable
            },
            summary: if completed {
                "这次操作已全部撤回，原名称已经恢复。".into()
            } else {
                "这次操作没有可撤回的成功项目。".into()
            },
        };
    }
    let mut checks = Vec::new();
    for index in ordered {
        let item = &operation.items[index];
        let current_source = current_path_after_later_directories(operation, index, &item.target);
        let restore_target = item.source.clone();
        let (safe, detail) = if !current_source.exists() {
            (
                false,
                format!("当前名称不存在：{}", current_source.display()),
            )
        } else if item.kind == ItemKind::Directory && !current_source.is_dir() {
            (false, "当前路径不再是文件夹，不能安全恢复。".into())
        } else if item.kind == ItemKind::File && !current_source.is_file() {
            (false, "当前路径不再是文件，不能安全恢复。".into())
        } else if restore_target.exists() && path_key(&restore_target) != path_key(&current_source)
        {
            (
                false,
                format!("原名称已被其他项目占用：{}", restore_target.display()),
            )
        } else {
            (true, "可以恢复原名称。".into())
        };
        checks.push(UndoCheckItem {
            item_index: index,
            current_source,
            restore_target,
            kind: item.kind,
            safe,
            detail,
        });
    }
    let unsafe_count = checks.iter().filter(|item| !item.safe).count();
    UndoCheckResult {
        operation_id: operation.identifier.clone(),
        token: operation.updated_at.clone(),
        state: if unsafe_count == 0 {
            UndoCheckState::Ready
        } else {
            UndoCheckState::Blocked
        },
        summary: if unsafe_count == 0 {
            format!("检查通过，可撤回 {} 项。", checks.len())
        } else {
            format!("发现 {unsafe_count} 项风险，整批撤回未获准。")
        },
        items: checks,
    }
}

pub fn execute_undo(
    operation: &mut OperationLogV1,
    token: &str,
    store: &OperationStore,
    mut progress: impl FnMut(UndoProgress),
) -> Result<UndoSummary, DomainError> {
    if operation.updated_at != token {
        return Err(DomainError::StaleSnapshot);
    }
    let check = preflight_undo(operation);
    if check.state != UndoCheckState::Ready {
        return Err(DomainError::Io(check.summary));
    }
    operation.status = OperationStatus::Undoing;
    store.save(operation)?;
    let total = check.items.len();
    let mut succeeded = 0;
    let mut failed = 0;
    for (position, check_item) in check.items.iter().enumerate() {
        let source = operation.items[check_item.item_index].target.clone();
        let target = operation.items[check_item.item_index].source.clone();
        match rename_case_safe(&source, &target) {
            Ok(()) => {
                succeeded += 1;
                let item = &mut operation.items[check_item.item_index];
                item.undo_status = UndoStatus::Undone;
                item.undo_detail = "已恢复原名称".into();
                store.save(operation)?;
                progress(UndoProgress {
                    current: position + 1,
                    total,
                    path: target,
                    outcome: "成功".into(),
                    detail: "已恢复原名称".into(),
                });
            }
            Err(error) => {
                failed += 1;
                let detail = error.to_string();
                let item = &mut operation.items[check_item.item_index];
                item.undo_status = UndoStatus::Failed;
                item.undo_detail.clone_from(&detail);
                operation.status = OperationStatus::PartiallyUndone;
                operation.error = format!("撤回在第 {} 项停止：{error}", position + 1);
                store.save(operation)?;
                progress(UndoProgress {
                    current: position + 1,
                    total,
                    path: source,
                    outcome: "失败".into(),
                    detail,
                });
                break;
            }
        }
    }
    if failed == 0 {
        let pending = operation
            .items
            .iter()
            .any(|item| item.outcome == "成功" && item.undo_status != UndoStatus::Undone);
        operation.status = if pending {
            OperationStatus::PartiallyUndone
        } else {
            OperationStatus::Undone
        };
        operation.error.clear();
        store.save(operation)?;
    }
    Ok(UndoSummary { succeeded, failed })
}

fn pending_order(operation: &OperationLogV1) -> Vec<usize> {
    let mut values: Vec<_> = operation
        .items
        .iter()
        .enumerate()
        .filter(|(_, item)| item.outcome == "成功" && item.undo_status != UndoStatus::Undone)
        .map(|(index, _)| index)
        .collect();
    values.sort_by_key(|index| {
        std::cmp::Reverse(
            operation.items[*index]
                .execution_index
                .unwrap_or(*index + 1),
        )
    });
    values
}

fn current_path_after_later_directories(
    operation: &OperationLogV1,
    item_index: usize,
    path: &Path,
) -> std::path::PathBuf {
    let execution = operation.items[item_index]
        .execution_index
        .unwrap_or(item_index + 1);
    let mut directories: Vec<_> = operation
        .items
        .iter()
        .enumerate()
        .filter(|(index, item)| {
            item.outcome == "成功"
                && item.kind == ItemKind::Directory
                && item.undo_status != UndoStatus::Undone
                && item.execution_index.unwrap_or(*index + 1) > execution
        })
        .collect();
    directories.sort_by_key(|(index, item)| item.execution_index.unwrap_or(*index + 1));
    let mut current = path.to_path_buf();
    for (_, directory) in directories {
        if let Ok(relative) = current.strip_prefix(&directory.source) {
            current = directory.target.join(relative);
        }
    }
    current
}

fn rename_case_safe(source: &Path, target: &Path) -> Result<(), DomainError> {
    if source != target && path_key(source) == path_key(target) {
        let temporary = source.with_file_name(format!(
            ".__batch_rename_{}__",
            uuid::Uuid::new_v4().simple()
        ));
        fs::rename(source, &temporary).map_err(|error| DomainError::Io(error.to_string()))?;
        fs::rename(&temporary, target).map_err(|error| DomainError::Io(error.to_string()))
    } else {
        fs::rename(source, target).map_err(|error| DomainError::Io(error.to_string()))
    }
}
