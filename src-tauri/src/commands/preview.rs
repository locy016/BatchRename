use tauri::State;

use crate::domain::models::PreviewPage;
use crate::services::preview::{build_preview, preview_page};
use crate::state::job_manager::JobManager;

#[tauri::command]
pub async fn build_rename_preview(
    job_id: String,
    replacement: String,
    rename_extension: bool,
    limit: Option<usize>,
    manager: State<'_, JobManager>,
) -> Result<PreviewPage, String> {
    let manager = manager.inner().clone();
    let snapshot = manager
        .snapshot(&job_id)
        .ok_or_else(|| "扫描结果已经失效，请重新扫描".to_owned())?;
    let preview = tauri::async_runtime::spawn_blocking(move || {
        build_preview(&snapshot, &replacement, rename_extension).map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| format!("结果预览任务异常结束：{error}"))??;
    let limit = limit.unwrap_or(preview.candidates.len()).max(1);
    let page = preview_page(&preview, 0, limit);
    manager
        .save_preview(&job_id, preview)
        .map_err(|error| error.to_string())?;
    Ok(page)
}

#[tauri::command]
pub fn get_preview_page(
    job_id: String,
    offset: usize,
    limit: Option<usize>,
    manager: State<'_, JobManager>,
) -> Result<PreviewPage, String> {
    let preview = manager
        .preview(&job_id)
        .ok_or_else(|| "预览结果已经失效，请重新生成".to_owned())?;
    let limit = limit.unwrap_or(preview.candidates.len()).max(1);
    Ok(preview_page(&preview, offset, limit))
}
