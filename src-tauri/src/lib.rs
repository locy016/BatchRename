pub mod commands;
pub mod domain;
pub mod services;
pub mod state;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(state::job_manager::JobManager::default())
        .invoke_handler(tauri::generate_handler![
            commands::scan::start_scan,
            commands::scan::cancel_active_job
        ])
        .run(tauri::generate_context!())
        .expect("批量重命名启动失败");
}
