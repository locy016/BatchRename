import json
from pathlib import Path

ROOT = Path(__file__).parents[2]

def test_windows_release_configuration_is_complete():
    config = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert config["version"] == "2.0.0-alpha.1"
    assert config["productName"] == "文件名管理"
    assert config["bundle"]["targets"] == ["nsis"]
    assert config["bundle"]["icon"]
    assert "SimpChinese" in config["bundle"]["windows"]["nsis"]["languages"]
    window = config["app"]["windows"][0]
    assert window["minWidth"] >= 960 and window["minHeight"] >= 680
    assert config["build"]["beforeBuildCommand"] == "npm run build"
    assert (ROOT / "scripts/build-release.ps1").exists()
    assert (ROOT / "scripts/smoke-test-release.ps1").exists()
