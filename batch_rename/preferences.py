"""应用外观偏好的容错读取、保存与系统模式解析。"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


APPEARANCE_MODES = {"system", "light", "dark"}


@dataclass(frozen=True, slots=True)
class AppPreferences:
    appearance: str = "system"


def normalize_appearance(value: object) -> str:
    """只接受受支持的外观值，其余内容安全回退到跟随系统。"""

    return value if isinstance(value, str) and value in APPEARANCE_MODES else "system"


def default_preferences_path(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """返回当前用户的外观配置文件位置。"""

    values = os.environ if environ is None else environ
    local_app_data = values.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "BatchRename" / "settings.json"


def load_preferences(path: Path | None = None) -> AppPreferences:
    """容错读取配置；缺失、损坏或未知值均不影响应用启动。"""

    target = default_preferences_path() if path is None else Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return AppPreferences()
    if not isinstance(payload, dict):
        return AppPreferences()
    return AppPreferences(appearance=normalize_appearance(payload.get("appearance")))


def save_preferences(
    preferences: AppPreferences,
    path: Path | None = None,
) -> None:
    """通过同目录临时文件保存配置，减少写入中断造成的损坏。"""

    target = default_preferences_path() if path is None else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    payload = {"appearance": normalize_appearance(preferences.appearance)}
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def system_prefers_light() -> bool:
    """读取Windows应用浅色设置；接口不可用时使用安全的浅色外观。"""

    if sys.platform != "win32":
        return True
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(int(value))
    except (OSError, ValueError, TypeError):
        return True


def resolve_appearance(
    mode: str,
    system_light_provider: Callable[[], bool] = system_prefers_light,
) -> str:
    """把请求的三态外观解析成可直接使用的浅色或深色。"""

    normalized = normalize_appearance(mode)
    if normalized == "system":
        try:
            return "light" if system_light_provider() else "dark"
        except Exception:
            return "light"
    return normalized
