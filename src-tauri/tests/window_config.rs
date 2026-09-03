use serde_json::Value;

#[test]
fn main_window_opens_at_product_workspace_size() {
    let config: Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
    let window = &config["app"]["windows"][0];

    assert_eq!(window["width"], 1360);
    assert_eq!(window["height"], 840);
    assert_eq!(window["minWidth"], 1180);
    assert_eq!(window["minHeight"], 760);
}
