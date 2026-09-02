use batch_rename_lib::domain::models::*;
use batch_rename_lib::services::journal::OperationStore;
use batch_rename_lib::services::undo::{execute_undo, preflight_undo};
use std::fs;
use tempfile::tempdir;

fn fixture(name: &str) -> OperationLogV1 {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests/fixtures/logs")
        .join(name);
    serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
}

#[test]
fn preflight_blocks_when_original_name_is_occupied() {
    let root = tempdir().unwrap();
    let mut operation = fixture("operation-completed-v1.json");
    operation.root = root.path().into();
    operation.items[0].source = root.path().join("旧.txt");
    operation.items[0].target = root.path().join("新.txt");
    fs::write(&operation.items[0].source, "占用").unwrap();
    fs::write(&operation.items[0].target, "当前").unwrap();
    let check = preflight_undo(&operation);
    assert!(!check.safe);
    assert!(check.items[0].detail.contains("占用"));
}

#[test]
fn restores_nested_items_in_reverse_and_marks_log_undone() {
    let root = tempdir().unwrap();
    let logs = tempdir().unwrap();
    let new_folder = root.path().join("新目录");
    fs::create_dir(&new_folder).unwrap();
    fs::write(new_folder.join("新文件.txt"), "内容").unwrap();
    let mut operation = fixture("operation-completed-v1.json");
    operation.identifier = "nested-undo".into();
    operation.root = root.path().into();
    operation.items = vec![
        OperationItemV1 {
            source: root.path().join("旧目录/旧文件.txt"),
            target: root.path().join("旧目录/新文件.txt"),
            kind: ItemKind::File,
            outcome: "成功".into(),
            detail: String::new(),
            execution_index: Some(1),
            undo_status: UndoStatus::Pending,
            undo_detail: String::new(),
        },
        OperationItemV1 {
            source: root.path().join("旧目录"),
            target: new_folder.clone(),
            kind: ItemKind::Directory,
            outcome: "成功".into(),
            detail: String::new(),
            execution_index: Some(2),
            undo_status: UndoStatus::Pending,
            undo_detail: String::new(),
        },
    ];
    let store = OperationStore::new(logs.path());
    store.create(&operation).unwrap();
    let check = preflight_undo(&operation);
    assert!(check.safe);
    let result = execute_undo(&mut operation, &check.token, &store, |_| {}).unwrap();
    assert_eq!(result.succeeded, 2);
    assert!(root.path().join("旧目录/旧文件.txt").exists());
    assert_eq!(operation.status, OperationStatus::Undone);
}
