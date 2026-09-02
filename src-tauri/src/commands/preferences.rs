use crate::services::preferences::{Appearance, Preferences, PreferencesStore};
use tauri::State;
#[tauri::command]
pub fn load_preferences(store: State<'_, PreferencesStore>) -> Preferences {
    store.load()
}
#[tauri::command]
pub fn save_preferences(
    appearance: Appearance,
    store: State<'_, PreferencesStore>,
) -> Result<(), String> {
    store.save(appearance).map_err(|e| e.to_string())
}
