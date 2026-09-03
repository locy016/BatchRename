use std::path::PathBuf;
use std::time::{Duration, Instant};

use tauri::State;
use tauri::ipc::Channel;

use crate::domain::models::{DirectoryOverview, MatchOptions, MatchPage, ScanProgress, ScanResult};
use crate::services::scanner::{
    inspect_directory as count_directory, list_root_items as read_root_items, search_matches,
};
use crate::state::job_manager::{CancellationToken, JobManager, JobType};

#[tauri::command]
pub async fn start_scan(
    options: MatchOptions,
    events: Channel<ScanProgress>,
    limit: Option<usize>,
    manager: State<'_, JobManager>,
) -> Result<ScanResult, String> {
    let handle = manager
        .begin(JobType::Scan)
        .map_err(|error| error.to_string())?;
    let identifier = handle.id.clone();
    let task_identifier = identifier.clone();
    let manager = manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut last_sent = Instant::now() - Duration::from_millis(50);
        let result = search_matches(&options, &handle.token, |mut event| {
            event.job_id.clone_from(&task_identifier);
            if event.warning.is_some()
                || event.scanned_total % 200 == 0
                || last_sent.elapsed() >= Duration::from_millis(50)
            {
                let _ = events.send(event);
                last_sent = Instant::now();
            }
        });
        match result {
            Ok(snapshot) => {
                let limit = limit.unwrap_or(snapshot.items.len()).max(1);
                let overview = DirectoryOverview {
                    directories: snapshot.scanned_directory_count,
                    files: snapshot.scanned_file_count,
                    warnings: snapshot.warnings.clone(),
                };
                let page = MatchPage {
                    items: snapshot.items.iter().take(limit).cloned().collect(),
                    total: snapshot.items.len(),
                    offset: 0,
                    limit,
                };
                let response = ScanResult {
                    job_id: task_identifier.clone(),
                    overview,
                    page,
                    warnings: snapshot.warnings.clone(),
                };
                let final_event = ScanProgress {
                    job_id: task_identifier.clone(),
                    phase: "完成".into(),
                    scanned_total: snapshot.scanned_directory_count + snapshot.scanned_file_count,
                    scanned_directory_count: snapshot.scanned_directory_count,
                    scanned_file_count: snapshot.scanned_file_count,
                    matched_total: snapshot.items.len(),
                    warning: None,
                };
                manager.complete_scan(&task_identifier, snapshot);
                let _ = events.send(final_event);
                Ok(response)
            }
            Err(error) => {
                manager.finish(&task_identifier);
                let _ = events.send(ScanProgress {
                    job_id: task_identifier,
                    phase: error.code().into(),
                    scanned_total: 0,
                    scanned_directory_count: 0,
                    scanned_file_count: 0,
                    matched_total: 0,
                    warning: Some(error.to_string()),
                });
                Err(error.to_string())
            }
        }
    })
    .await
    .map_err(|error| format!("扫描任务异常结束：{error}"))?
}

#[tauri::command]
pub async fn inspect_directory(
    root: PathBuf,
    max_depth: Option<usize>,
) -> Result<DirectoryOverview, String> {
    tauri::async_runtime::spawn_blocking(move || {
        count_directory(&root, max_depth, &CancellationToken::new())
            .map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| format!("目录统计异常结束：{error}"))?
}

#[tauri::command]
pub async fn list_root_items(root: PathBuf, limit: Option<usize>) -> Result<MatchPage, String> {
    tauri::async_runtime::spawn_blocking(move || {
        read_root_items(&root, limit).map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| format!("目录内容读取异常结束：{error}"))?
}

#[tauri::command]
pub fn get_scan_page(
    job_id: String,
    offset: usize,
    limit: Option<usize>,
    manager: State<'_, JobManager>,
) -> Result<MatchPage, String> {
    let snapshot = manager
        .snapshot(&job_id)
        .ok_or_else(|| "扫描结果已经失效，请重新扫描".to_owned())?;
    let limit = limit.unwrap_or(snapshot.items.len()).max(1);
    Ok(MatchPage {
        items: snapshot
            .items
            .iter()
            .skip(offset)
            .take(limit)
            .cloned()
            .collect(),
        total: snapshot.items.len(),
        offset,
        limit,
    })
}

#[tauri::command]
pub fn cancel_active_job(manager: State<'_, JobManager>) {
    manager.cancel_active();
}
