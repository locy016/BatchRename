use batch_rename_lib::window_layout::{MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, calculate_window_size};
use serde_json::Value;

#[test]
fn main_window_opens_at_product_workspace_size() {
    let config: Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
    let window = &config["app"]["windows"][0];

    assert_eq!(window["width"], MIN_WINDOW_WIDTH);
    assert_eq!(window["height"], MIN_WINDOW_HEIGHT);
    assert_eq!(window["minWidth"], 1180);
    assert_eq!(window["minHeight"], 760);
    assert_eq!(window["visible"], false);
}

#[test]
fn startup_size_uses_half_of_standard_screens_and_balanced_portrait_or_ultrawide_sizes() {
    assert_eq!(calculate_window_size(1920, 1080), (1180, 760));
    assert_eq!(calculate_window_size(2560, 1440), (1280, 760));
    assert_eq!(calculate_window_size(3840, 2160), (1920, 1080));
    assert_eq!(calculate_window_size(3440, 1440), (1582, 979));
    assert_eq!(calculate_window_size(1440, 2560), (1296, 1490));
}
