use std::time::{Duration, Instant};

use tauri::State;
use tauri::ipc::Channel;

use crate::domain::models::{MatchOptions, ScanProgress};
use crate::services::scanner::search_matches;
use crate::state::job_manager::{JobManager, JobType};

#[tauri::command]
pub fn start_scan(
    options: MatchOptions,
    events: Channel<ScanProgress>,
    manager: State<'_, JobManager>,
) -> Result<String, String> {
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
                let final_event = ScanProgress {
                    job_id: task_identifier.clone(),
                    phase: "完成".into(),
                    scanned_total: snapshot.scanned_directory_count + snapshot.scanned_file_count,
                    matched_total: snapshot.items.len(),
                    warning: None,
                };
                manager.complete_scan(&task_identifier, snapshot);
                let _ = events.send(final_event);
            }
            Err(error) => {
                manager.finish(&task_identifier);
                let _ = events.send(ScanProgress {
                    job_id: task_identifier,
                    phase: error.code().into(),
                    scanned_total: 0,
                    matched_total: 0,
                    warning: Some(error.to_string()),
                });
            }
        }
    });
    Ok(identifier)
}

#[tauri::command]
pub fn cancel_active_job(manager: State<'_, JobManager>) {
    manager.cancel_active();
}
