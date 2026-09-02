use crate::domain::models::{UndoCheckResult, UndoProgress, UndoSummary};
use crate::services::journal::OperationStore;
use crate::services::undo::{execute_undo, preflight_undo};
use crate::state::job_manager::{JobManager, JobType};
use tauri::State;
use tauri::ipc::Channel;

#[tauri::command]
pub fn check_undo(
    identifier: String,
    store: State<'_, OperationStore>,
) -> Result<UndoCheckResult, String> {
    Ok(preflight_undo(
        &store.load(&identifier).map_err(|error| error.to_string())?,
    ))
}

#[tauri::command]
pub fn undo_operation(
    identifier: String,
    token: String,
    events: Channel<UndoProgress>,
    manager: State<'_, JobManager>,
    store: State<'_, OperationStore>,
) -> Result<UndoSummary, String> {
    let handle = manager
        .begin(JobType::Undo)
        .map_err(|error| error.to_string())?;
    let mut operation = store.load(&identifier).map_err(|error| error.to_string())?;
    let result = execute_undo(&mut operation, &token, store.inner(), |event| {
        let _ = events.send(event);
    })
    .map_err(|error| error.to_string());
    manager.finish(&handle.id);
    result
}
