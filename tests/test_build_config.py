from pathlib import Path


def test_build_script_is_compatible_with_windows_powershell_5_encoding():
    data = Path("build.ps1").read_bytes()

    assert data.startswith(b"\xef\xbb\xbf") or data.isascii(), (
        "Windows PowerShell 5 treats UTF-8 without BOM as an ANSI code page; "
        "build.ps1 must have a UTF-8 BOM or contain ASCII only"
    )
