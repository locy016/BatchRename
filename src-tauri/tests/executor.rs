use batch_rename_lib::domain::models::*;
use batch_rename_lib::services::executor::{ExecutionOptions, execute_preview};
use batch_rename_lib::services::journal::OperationStore;
use std::fs;
use tempfile::tempdir;

#[test]
fn renames_children_before_parent_and_records_each_item() {
    let root = tempdir().unwrap();
    let logs = tempdir().unwrap();
    let folder = root.path().join("旧目录");
    fs::create_dir(&folder).unwrap();
    fs::write(folder.join("旧文件.txt"), "内容").unwrap();
    let preview = PreviewResult {
        root: root.path().to_path_buf(),
        warnings: vec![],
        summary: PreviewSummary {
            matched: 2,
            ready: 2,
            ..Default::default()
        },
        candidates: vec![
            RenameCandidate {
                source: folder.clone(),
                target: root.path().join("新目录"),
                kind: ItemKind::Directory,
                status: CandidateStatus::Ready,
                detail: "可以安全修改".into(),
            },
            RenameCandidate {
                source: folder.join("旧文件.txt"),
                target: folder.join("新文件.txt"),
                kind: ItemKind::File,
                status: CandidateStatus::Ready,
                detail: "可以安全修改".into(),
            },
        ],
    };
    let store = OperationStore::new(logs.path());
    let result = execute_preview(
        &preview,
        &ExecutionOptions::demo("旧", "新"),
        &store,
        |_| {},
    )
    .unwrap();
    assert!(root.path().join("新目录").join("新文件.txt").exists());
    let operation = store.load(&result.operation_id).unwrap();
    assert_eq!(operation.status, OperationStatus::Completed);
    assert_eq!(
        operation
            .items
            .iter()
            .filter(|item| item.outcome == "成功")
            .count(),
        2
    );
}

#[test]
fn rechecks_disappeared_source_and_new_target() {
    let root = tempdir().unwrap();
    let logs = tempdir().unwrap();
    let source = root.path().join("旧.txt");
    let target = root.path().join("新.txt");
    fs::write(&target, "占用").unwrap();
    let preview = PreviewResult {
        root: root.path().into(),
        warnings: vec![],
        summary: PreviewSummary {
            matched: 1,
            ready: 1,
            ..Default::default()
        },
        candidates: vec![RenameCandidate {
            source,
            target,
            kind: ItemKind::File,
            status: CandidateStatus::Ready,
            detail: String::new(),
        }],
    };
    let result = execute_preview(
        &preview,
        &ExecutionOptions::demo("旧", "新"),
        &OperationStore::new(logs.path()),
        |_| {},
    )
    .unwrap();
    assert_eq!(result.skipped, 1);
}
