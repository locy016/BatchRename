use std::fs;

use batch_rename_lib::domain::models::{CandidateStatus, ItemKind, MatchSnapshot, MatchedItem};
use batch_rename_lib::services::preview::{build_preview, preview_page};
use tempfile::tempdir;

fn snapshot(root: &std::path::Path, search: &str, names: &[&str]) -> MatchSnapshot {
    MatchSnapshot {
        root: root.to_path_buf(),
        search: search.into(),
        use_regex: false,
        items: names
            .iter()
            .map(|name| MatchedItem {
                source: root.join(name),
                kind: ItemKind::File,
            })
            .collect(),
        warnings: Vec::new(),
        scanned_directory_count: 0,
        scanned_file_count: names.len(),
    }
}

#[test]
fn unchanged_matches_remain_visible_and_counted() {
    let root = tempdir().unwrap();
    fs::write(root.path().join("报告.txt"), "").unwrap();
    let result =
        build_preview(&snapshot(root.path(), "报告", &["报告.txt"]), "报告", false).unwrap();

    assert_eq!(result.summary.matched, 1);
    assert_eq!(result.summary.ready, 0);
    assert_eq!(result.candidates[0].status, CandidateStatus::Unchanged);
    assert!(result.candidates[0].detail.contains("没有变化"));
}

#[test]
fn explains_when_only_the_protected_extension_matches() {
    let root = tempdir().unwrap();
    fs::write(root.path().join("说明.txt"), "").unwrap();
    let result = build_preview(&snapshot(root.path(), "txt", &["说明.txt"]), "md", false).unwrap();

    assert_eq!(result.candidates[0].status, CandidateStatus::Unchanged);
    assert!(result.candidates[0].detail.contains("扩展名"));
}

#[test]
fn detects_existing_and_in_batch_target_conflicts() {
    let root = tempdir().unwrap();
    for name in ["旧版.txt", "新版.txt", "甲1.txt", "甲2.txt"] {
        fs::write(root.path().join(name), "").unwrap();
    }
    let existing =
        build_preview(&snapshot(root.path(), "旧版", &["旧版.txt"]), "新版", false).unwrap();
    assert_eq!(existing.candidates[0].status, CandidateStatus::Conflict);

    let mut duplicate_snapshot = snapshot(root.path(), r"甲\d", &["甲1.txt", "甲2.txt"]);
    duplicate_snapshot.use_regex = true;
    let duplicate = build_preview(&duplicate_snapshot, "相同", false).unwrap();
    assert!(
        duplicate
            .candidates
            .iter()
            .all(|item| item.status == CandidateStatus::Duplicate)
    );
}

#[test]
fn marks_invalid_windows_target_names() {
    let root = tempdir().unwrap();
    fs::write(root.path().join("原名.txt"), "").unwrap();
    let result = build_preview(
        &snapshot(root.path(), "原名", &["原名.txt"]),
        "错误?",
        false,
    )
    .unwrap();
    assert_eq!(result.candidates[0].status, CandidateStatus::Invalid);
}

#[test]
fn pagination_does_not_change_complete_summary() {
    let root = tempdir().unwrap();
    let names: Vec<_> = (0..120).map(|index| format!("旧版{index}.txt")).collect();
    for name in &names {
        fs::write(root.path().join(name), "").unwrap();
    }
    let references: Vec<_> = names.iter().map(String::as_str).collect();
    let result = build_preview(&snapshot(root.path(), "旧版", &references), "新版", false).unwrap();
    let page = preview_page(&result, 100, 1000);

    assert_eq!(result.summary.matched, 120);
    assert_eq!(page.total, 120);
    assert_eq!(page.items.len(), 20);
}

#[test]
fn result_page_has_no_fixed_maximum() {
    let root = tempdir().unwrap();
    let names: Vec<_> = (0..620).map(|index| format!("旧版{index}.txt")).collect();
    let references: Vec<_> = names.iter().map(String::as_str).collect();
    let result = build_preview(&snapshot(root.path(), "旧版", &references), "新版", false).unwrap();

    let page = preview_page(&result, 0, 600);

    assert_eq!(page.items.len(), 600);
    assert_eq!(page.limit, 600);
}
