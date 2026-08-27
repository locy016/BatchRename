from pathlib import Path

from PIL import Image


def test_build_script_is_compatible_with_windows_powershell_5_encoding():
    data = Path("build.ps1").read_bytes()

    assert data.startswith(b"\xef\xbb\xbf") or data.isascii(), (
        "Windows PowerShell 5 treats UTF-8 without BOM as an ANSI code page; "
        "build.ps1 must have a UTF-8 BOM or contain ASCII only"
    )


def test_application_icon_has_transparent_png_and_windows_sizes():
    png_path = Path("assets/app-icon.png")
    ico_path = Path("assets/app-icon.ico")

    assert png_path.is_file()
    assert ico_path.is_file()
    with Image.open(png_path) as image:
        assert image.size[0] == image.size[1] >= 512
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema()[0] < 255
    with Image.open(ico_path) as image:
        assert image.format == "ICO"
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= image.ico.sizes()


def test_pyinstaller_uses_application_icon():
    spec = Path("BatchRename.spec").read_text(encoding="utf-8")

    assert 'icon="assets/app-icon.ico"' in spec
