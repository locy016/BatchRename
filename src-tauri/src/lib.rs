pub mod commands;
pub mod domain;
pub mod services;
pub mod state;
pub mod window_layout;

use tauri::{LogicalSize, Manager, PhysicalPosition, Position, Size};

fn configure_main_window(app: &tauri::App) -> tauri::Result<()> {
    let Some(window) = app.get_webview_window("main") else {
        return Ok(());
    };
    let monitor = window
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| window.primary_monitor().ok().flatten());
    if let Some(monitor) = monitor {
        let scale = monitor.scale_factor();
        let work_area = monitor.work_area();
        let logical_width = (work_area.size.width as f64 / scale).round() as u32;
        let logical_height = (work_area.size.height as f64 / scale).round() as u32;
        let (width, height) = window_layout::calculate_window_size(logical_width, logical_height);
        let _ = window.set_size(Size::Logical(LogicalSize::new(width as f64, height as f64)));

        let physical_width = (width as f64 * scale).round() as i32;
        let physical_height = (height as f64 * scale).round() as i32;
        let x = work_area.position.x + ((work_area.size.width as i32 - physical_width).max(0) / 2);
        let y =
            work_area.position.y + ((work_area.size.height as i32 - physical_height).max(0) / 2);
        let _ = window.set_position(Position::Physical(PhysicalPosition::new(x, y)));
    }
    window.show()?;
    window.set_focus()?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            configure_main_window(app)?;
            Ok(())
        })
        .manage(state::job_manager::JobManager::default())
        .manage(services::journal::OperationStore::default_for_user())
        .manage(services::preferences::PreferencesStore::default_for_user())
        .invoke_handler(tauri::generate_handler![
            commands::scan::start_scan,
            commands::scan::inspect_directory,
            commands::scan::list_root_items,
            commands::scan::get_scan_page,
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
        .expect("文件名管理启动失败");
}
