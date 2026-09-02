use batch_rename_lib::services::preferences::{Appearance, PreferencesStore};
use std::fs;
use tempfile::tempdir;
#[test]
fn missing_and_corrupt_settings_fall_back_to_system() {
    let d = tempdir().unwrap();
    let s = PreferencesStore::new(d.path().join("settings.json"));
    assert_eq!(s.load().appearance, Appearance::System);
    fs::write(d.path().join("settings.json"), "{").unwrap();
    assert_eq!(s.load().appearance, Appearance::System)
}
#[test]
fn reads_and_saves_python_appearance_field() {
    let d = tempdir().unwrap();
    let s = PreferencesStore::new(d.path().join("settings.json"));
    fs::write(d.path().join("settings.json"), r#"{"appearance":"dark"}"#).unwrap();
    assert_eq!(s.load().appearance, Appearance::Dark);
    s.save(Appearance::Light).unwrap();
    assert!(
        fs::read_to_string(d.path().join("settings.json"))
            .unwrap()
            .contains("light")
    )
}
