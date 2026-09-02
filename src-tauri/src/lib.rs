pub mod commands;
pub mod domain;
pub mod services;
pub mod state;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(state::job_manager::JobManager::default())
        .manage(services::journal::OperationStore::default_for_user())
        .manage(services::preferences::PreferencesStore::default_for_user())
        .invoke_handler(tauri::generate_handler![
            commands::scan::start_scan,
            commands::scan::cancel_active_job,
            commands::preview::build_rename_preview,
            commands::preview::get_preview_page,
            commands::history::query_operations,
            commands::history::get_operation,
            commands::execute::execute_rename,
            commands::undo::check_undo,
            commands::undo::undo_operation,
            commands::preferences::load_preferences,
            commands::preferences::save_preferences
        ])
        .run(tauri::generate_context!())
        .expect("批量重命名启动失败");
}
