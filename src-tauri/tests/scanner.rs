use std::fs;
use std::sync::{Arc, Mutex};

use batch_rename_lib::domain::errors::DomainError;
use batch_rename_lib::domain::models::{ItemKind, MatchOptions};
use batch_rename_lib::services::scanner::{inspect_directory, search_matches};
use batch_rename_lib::state::job_manager::{CancellationToken, JobManager, JobType};
use tempfile::tempdir;

fn options(root: &std::path::Path) -> MatchOptions {
    MatchOptions {
        root: root.to_path_buf(),
        search: "项目".into(),
        use_regex: false,
        max_depth: None,
        include_files: true,
        include_dirs: true,
    }
}

#[test]
fn directory_overview_uses_the_same_depth_rules_as_search() {
    let root = tempdir().unwrap();
    fs::create_dir(root.path().join("一级目录")).unwrap();
    fs::create_dir(root.path().join("一级目录").join("二级目录")).unwrap();
    fs::write(root.path().join("根文件.txt"), "").unwrap();
    fs::write(root.path().join("一级目录").join("一级文件.txt"), "").unwrap();
    fs::write(
        root.path()
            .join("一级目录")
            .join("二级目录")
            .join("二级文件.txt"),
        "",
    )
    .unwrap();

    let all = inspect_directory(root.path(), None, &CancellationToken::new()).unwrap();
    assert_eq!(all.directories, 2);
    assert_eq!(all.files, 3);

    let first_level = inspect_directory(root.path(), Some(1), &CancellationToken::new()).unwrap();
    assert_eq!(first_level.directories, 1);
    assert_eq!(first_level.files, 1);
}

#[test]
fn scans_all_levels_and_sorts_each_root_group_naturally() {
    let root = tempdir().unwrap();
    fs::create_dir(root.path().join("项目2")).unwrap();
    fs::create_dir(root.path().join("项目10")).unwrap();
    fs::write(root.path().join("项目10.txt"), "").unwrap();
    fs::write(root.path().join("项目2.txt"), "").unwrap();
    fs::write(root.path().join("项目2").join("深层项目.txt"), "").unwrap();

    let snapshot =
        search_matches(&options(root.path()), &CancellationToken::new(), |_| {}).unwrap();
    let names: Vec<_> = snapshot
        .items
        .iter()
        .map(|item| {
            (
                item.kind,
                item.source
                    .file_name()
                    .unwrap()
                    .to_string_lossy()
                    .into_owned(),
            )
        })
        .collect();

    assert_eq!(snapshot.scanned_directory_count, 2);
    assert_eq!(snapshot.scanned_file_count, 3);
    assert_eq!(names[0], (ItemKind::Directory, "项目2".into()));
    assert_eq!(names[1], (ItemKind::Directory, "项目10".into()));
    assert_eq!(names[2], (ItemKind::File, "项目2.txt".into()));
    assert_eq!(names[3], (ItemKind::File, "项目10.txt".into()));
    assert_eq!(names[4], (ItemKind::File, "深层项目.txt".into()));
}

#[test]
fn sorts_by_kind_directory_then_natural_name() {
    let root = tempdir().unwrap();
    fs::create_dir(root.path().join("项目2")).unwrap();
    fs::create_dir(root.path().join("项目10")).unwrap();
    fs::create_dir(root.path().join("项目10").join("项目1子目录")).unwrap();
    fs::write(root.path().join("项目9.txt"), "").unwrap();
    fs::write(root.path().join("项目2").join("项目20.txt"), "").unwrap();
    fs::write(root.path().join("项目2").join("项目3.txt"), "").unwrap();
    fs::write(root.path().join("项目10").join("项目1.txt"), "").unwrap();

    let snapshot =
        search_matches(&options(root.path()), &CancellationToken::new(), |_| {}).unwrap();
    let relative_paths: Vec<_> = snapshot
        .items
        .iter()
        .map(|item| {
            item.source
                .strip_prefix(root.path())
                .unwrap()
                .to_string_lossy()
                .replace('\\', "/")
        })
        .collect();

    assert_eq!(
        relative_paths,
        vec![
            "项目2",
            "项目10",
            "项目10/项目1子目录",
            "项目9.txt",
            "项目2/项目3.txt",
            "项目2/项目20.txt",
            "项目10/项目1.txt",
        ]
    );
}

#[test]
fn depth_and_kind_filters_do_not_change_inventory_counts() {
    let root = tempdir().unwrap();
    fs::create_dir(root.path().join("项目目录")).unwrap();
    fs::write(root.path().join("项目文件.txt"), "").unwrap();
    fs::write(root.path().join("项目目录").join("深层项目.txt"), "").unwrap();
    let mut scan_options = options(root.path());
    scan_options.max_depth = Some(1);
    scan_options.include_dirs = false;

    let snapshot = search_matches(&scan_options, &CancellationToken::new(), |_| {}).unwrap();
    assert_eq!(snapshot.scanned_directory_count, 1);
    assert_eq!(snapshot.scanned_file_count, 1);
    assert_eq!(snapshot.items.len(), 1);
    assert_eq!(snapshot.items[0].kind, ItemKind::File);
}

#[test]
fn cancellation_stops_before_reading_the_directory() {
    let root = tempdir().unwrap();
    let token = CancellationToken::new();
    token.cancel();

    let error = search_matches(&options(root.path()), &token, |_| {}).unwrap_err();
    assert!(matches!(error, DomainError::Cancelled));
}

#[test]
fn emits_monotonic_progress() {
    let root = tempdir().unwrap();
    fs::write(root.path().join("项目1.txt"), "").unwrap();
    fs::write(root.path().join("项目2.txt"), "").unwrap();
    let progress = Arc::new(Mutex::new(Vec::new()));
    let collected = Arc::clone(&progress);

    search_matches(&options(root.path()), &CancellationToken::new(), |event| {
        collected.lock().unwrap().push(event.scanned_total);
    })
    .unwrap();

    let values = progress.lock().unwrap();
    assert!(values.windows(2).all(|pair| pair[0] <= pair[1]));
    assert_eq!(values.last(), Some(&2));
}

#[test]
fn job_manager_cancels_replaced_scan_and_blocks_during_mutation() {
    let manager = JobManager::default();
    let first = manager.begin(JobType::Scan).unwrap();
    let second = manager.begin(JobType::Scan).unwrap();
    assert!(first.token.is_cancelled());
    assert_ne!(first.id, second.id);

    manager.finish(&second.id);
    let execute = manager.begin(JobType::Execute).unwrap();
    let error = manager.begin(JobType::Scan).unwrap_err();
    assert!(matches!(error, DomainError::Busy));
    manager.finish(&execute.id);
}
