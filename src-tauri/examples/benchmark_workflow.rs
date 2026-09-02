use batch_rename_lib::domain::models::MatchOptions;
use batch_rename_lib::services::preview::build_preview;
use batch_rename_lib::services::scanner::search_matches;
use batch_rename_lib::state::job_manager::CancellationToken;
use std::fs;
use std::time::Instant;
fn main() {
    let count: usize = std::env::args()
        .nth(1)
        .and_then(|v| v.parse().ok())
        .unwrap_or(1000);
    let root = tempfile::tempdir().unwrap();
    for i in 0..count {
        fs::write(root.path().join(format!("项目旧版_{i:06}.txt")), "").unwrap()
    }
    let options = MatchOptions {
        root: root.path().into(),
        search: "旧版".into(),
        use_regex: false,
        max_depth: None,
        include_files: true,
        include_dirs: true,
    };
    let started = Instant::now();
    let snapshot = search_matches(&options, &CancellationToken::new(), |_| {}).unwrap();
    let scan = started.elapsed().as_secs_f64() * 1000.;
    let started = Instant::now();
    let preview = build_preview(&snapshot, "新版", false).unwrap();
    let preview_ms = started.elapsed().as_secs_f64() * 1000.;
    println!(
        r#"{{"entries":{count},"matched":{},"scanMs":{scan:.3},"previewMs":{preview_ms:.3}}}"#,
        preview.summary.matched
    )
}
