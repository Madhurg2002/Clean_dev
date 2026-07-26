import os
import stat
from pathlib import Path

def support_long_path(path: Path) -> str:
    path_str = str(path.absolute().resolve())
    if os.name == "nt":
        if path_str.startswith("\\\\?\\"):
            return path_str
        elif path_str.startswith("\\\\"):
            return f"\\\\?\\UNC\\{path_str[2:]}"
        else:
            return f"\\\\?\\{path_str}"
    return path_str

def get_dir_size(path_str: str) -> int:
    total_size = 0
    try:
        with os.scandir(path_str) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total_size += get_dir_size(entry.path)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total_size

def format_size(size_in_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def is_python_env(path: Path) -> bool:
    try:
        windows_py = (path / "Scripts" / "python.exe").exists()
        unix_py = (path / "bin" / "python").exists()
        cfg = (path / "pyvenv.cfg").exists()
        return windows_py or unix_py or cfg
    except (PermissionError, OSError):
        return False

def is_conda_env(path: Path) -> bool:
    try:
        return (path / "conda-meta").exists()
    except (PermissionError, OSError):
        return False

def remove_readonly_handler(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        raise e

def enable_ansi_support():
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_stdout = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
                # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
                kernel32.SetConsoleMode(h_stdout, mode.value | 0x0004)
        except Exception:
            pass
