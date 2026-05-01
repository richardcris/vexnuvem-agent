from __future__ import annotations

from pathlib import Path
import sys

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


STARTUP_ARGUMENT = "--windows-startup"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "VexNuvem Agent"


def is_windows_startup_supported() -> bool:
    return sys.platform.startswith("win") and winreg is not None


def was_started_from_windows(args: list[str] | None = None) -> bool:
    values = args if args is not None else sys.argv[1:]
    return STARTUP_ARGUMENT in values


def apply_start_with_windows(enabled: bool) -> None:
    if not is_windows_startup_supported():
        return

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as run_key:
        if enabled:
            winreg.SetValueEx(run_key, RUN_VALUE_NAME, 0, winreg.REG_SZ, build_startup_command())
        else:
            try:
                winreg.DeleteValue(run_key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def build_startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'{_quote(str(Path(sys.executable)))} {STARTUP_ARGUMENT}'

    executable = _resolve_python_startup_executable()
    project_root = Path(__file__).resolve().parents[2]
    main_script = project_root / "main.py"
    return f'{_quote(str(executable))} {_quote(str(main_script))} {STARTUP_ARGUMENT}'


def _resolve_python_startup_executable() -> Path:
    current = Path(sys.executable)
    if current.name.lower() == "python.exe":
        pythonw = current.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return current


def _quote(value: str) -> str:
    return f'"{value}"'