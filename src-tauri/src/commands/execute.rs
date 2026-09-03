use crate::domain::models::{ExecutionProgress, ExecutionSummary};
use crate::services::executor::{ExecutionOptions, execute_preview};
use crate::services::journal::OperationStore;
use crate::state::job_manager::{JobManager, JobType};
use tauri::State;
use tauri::ipc::Channel;

#[tauri::command]
pub async fn execute_rename(
    job_id: String,
    options: ExecutionOptionsDto,
    events: Channel<ExecutionProgress>,
    manager: State<'_, JobManager>,
    store: State<'_, OperationStore>,
) -> Result<ExecutionSummary, String> {
    let handle = manager
        .begin(JobType::Execute)
        .map_err(|error| error.to_string())?;
    let manager = manager.inner().clone();
    let identifier = handle.id;
    let preview = match manager.preview(&job_id) {
        Some(preview) => preview,
        None => {
            manager.finish(&identifier);
            return Err("预览结果已经失效，请重新生成".to_owned());
        }
    };
    let store = store.inner().clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        execute_preview(&preview, &options.into(), &store, |event| {
            let _ = events.send(event);
        })
        .map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| format!("文件名处理任务异常结束：{error}"));
    manager.finish(&identifier);
    result?
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutionOptionsDto {
    search: String,
    replacement: String,
    use_regex: bool,
    max_depth: Option<usize>,
    include_files: bool,
    include_dirs: bool,
    rename_extension: bool,
}
impl From<ExecutionOptionsDto> for ExecutionOptions {
    fn from(value: ExecutionOptionsDto) -> Self {
        Self {
            search: value.search,
            replacement: value.replacement,
            use_regex: value.use_regex,
            max_depth: value.max_depth,
            include_files: value.include_files,
            include_dirs: value.include_dirs,
            rename_extension: value.rename_extension,
        }
    }
}
