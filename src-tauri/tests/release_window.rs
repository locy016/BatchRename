#[test]
fn release_binary_uses_windows_gui_subsystem() {
    let main_source = include_str!("../src/main.rs");
    assert!(
        main_source.contains("windows_subsystem = \"windows\""),
        "发行入口必须声明 Windows 图形子系统，避免同时显示命令行窗口"
    );
}
