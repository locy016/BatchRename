import json
from pathlib import Path

from batch_rename.preferences import (
    AppPreferences,
    default_preferences_path,
    load_preferences,
    normalize_appearance,
    resolve_appearance,
    save_preferences,
)


def test_appearance_normalization_accepts_supported_modes_and_rejects_unknown():
    assert normalize_appearance("system") == "system"
    assert normalize_appearance("light") == "light"
    assert normalize_appearance("dark") == "dark"
    assert normalize_appearance("unknown") == "system"
    assert normalize_appearance(None) == "system"


def test_missing_or_malformed_preferences_fall_back_to_system(tmp_path):
    path = tmp_path / "settings.json"
    assert load_preferences(path) == AppPreferences(appearance="system")

    path.write_text("{broken", encoding="utf-8")
    assert load_preferences(path) == AppPreferences(appearance="system")

    path.write_text(json.dumps({"appearance": "sepia"}), encoding="utf-8")
    assert load_preferences(path) == AppPreferences(appearance="system")


def test_preferences_round_trip_uses_a_readable_json_file(tmp_path):
    path = tmp_path / "nested" / "settings.json"

    save_preferences(AppPreferences(appearance="dark"), path)

    assert load_preferences(path) == AppPreferences(appearance="dark")
    assert json.loads(path.read_text(encoding="utf-8")) == {"appearance": "dark"}
    assert not path.with_suffix(".json.tmp").exists()


def test_default_preferences_path_uses_local_app_data():
    path = default_preferences_path({"LOCALAPPDATA": r"C:\Users\Tester\AppData\Local"})

    assert path == Path(r"C:\Users\Tester\AppData\Local") / "BatchRename" / "settings.json"


def test_system_appearance_resolution_uses_an_injected_windows_provider():
    assert resolve_appearance("system", lambda: True) == "light"
    assert resolve_appearance("system", lambda: False) == "dark"
    assert resolve_appearance("light", lambda: False) == "light"
    assert resolve_appearance("dark", lambda: True) == "dark"
