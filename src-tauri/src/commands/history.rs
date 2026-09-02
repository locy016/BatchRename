use crate::domain::models::OperationLogV1;
use crate::services::journal::{OperationPage, OperationQuery, OperationStore};
use tauri::State;

#[tauri::command]
pub fn query_operations(
    query: OperationQuery,
    store: State<'_, OperationStore>,
) -> Result<OperationPage, String> {
    store.query(query).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn get_operation(
    identifier: String,
    store: State<'_, OperationStore>,
) -> Result<OperationLogV1, String> {
    store.load(&identifier).map_err(|error| error.to_string())
}
