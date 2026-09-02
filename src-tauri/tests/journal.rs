use std::fs;

use batch_rename_lib::domain::models::{OperationLogV1, OperationStatus};
use batch_rename_lib::services::journal::{OperationQuery, OperationStore};
use tempfile::tempdir;

fn fixture(name: &str) -> OperationLogV1 {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("logs")
        .join(name);
    serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
}

#[test]
fn atomically_saves_and_loads_python_compatible_log() {
    let directory = tempdir().unwrap();
    let store = OperationStore::new(directory.path());
    let operation = fixture("operation-completed-v1.json");
    store.create(&operation).unwrap();
    assert_eq!(store.load(&operation.identifier).unwrap(), operation);
    assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 1);
}

#[test]
fn queries_newest_first_and_isolates_corrupt_files() {
    let directory = tempdir().unwrap();
    let store = OperationStore::new(directory.path());
    let mut first = fixture("operation-completed-v1.json");
    first.identifier = "first".into();
    first.created_at = "2026-01-01T00:00:00+08:00".into();
    store.create(&first).unwrap();
    let mut second = fixture("operation-partial-v1.json");
    second.identifier = "second".into();
    second.created_at = "2026-02-01T00:00:00+08:00".into();
    store.create(&second).unwrap();
    fs::write(directory.path().join("broken.json"), "{").unwrap();

    let page = store
        .query(OperationQuery {
            query: "项目A".into(),
            status: None,
            offset: 0,
            limit: 20,
        })
        .unwrap();
    assert_eq!(page.items[0].identifier, "second");
    assert_eq!(page.items[1].identifier, "first");
    let all = store.query(OperationQuery::default()).unwrap();
    assert!(
        all.items
            .iter()
            .any(|item| item.status == OperationStatus::Corrupt)
    );
}

#[test]
fn recovers_unfinished_execution_as_interrupted() {
    let directory = tempdir().unwrap();
    let store = OperationStore::new(directory.path());
    let mut operation = fixture("operation-completed-v1.json");
    operation.identifier = "unfinished".into();
    operation.status = OperationStatus::Running;
    store.create(&operation).unwrap();
    let recovered = store.load("unfinished").unwrap();
    assert_eq!(recovered.status, OperationStatus::Interrupted);
}
