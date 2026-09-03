use std::fs;
use std::path::PathBuf;

use batch_rename_lib::domain::models::{OperationLogV1, OperationStatus};

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("logs")
        .join(name)
}

#[test]
fn reads_all_legacy_operation_log_states() {
    let expected = [
        ("operation-completed-v1.json", OperationStatus::Completed),
        ("operation-partial-v1.json", OperationStatus::Partial),
        (
            "operation-interrupted-v1.json",
            OperationStatus::Interrupted,
        ),
        (
            "operation-partially-undone-v1.json",
            OperationStatus::PartiallyUndone,
        ),
    ];

    for (filename, expected_status) in expected {
        let payload = fs::read_to_string(fixture_path(filename)).unwrap();
        let operation: OperationLogV1 = serde_json::from_str(&payload).unwrap();
        assert_eq!(operation.schema_version, 1);
        assert_eq!(operation.status, expected_status);
        assert!(!operation.items.is_empty());
    }
}

#[test]
fn round_trips_persisted_chinese_enums() {
    let payload = fs::read_to_string(fixture_path("operation-completed-v1.json")).unwrap();
    let operation: OperationLogV1 = serde_json::from_str(&payload).unwrap();
    let encoded = serde_json::to_string(&operation).unwrap();

    assert!(encoded.contains("已完成"));
    assert!(encoded.contains("文件"));
    assert!(encoded.contains("待撤回"));
}
