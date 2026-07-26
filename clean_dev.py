import concurrent.futures
import os
import shutil
import stat
import sys
from pathlib import Path

try:
    import questionary
except ImportError:
    print("Error: The interactive menu requires the 'questionary' library.")
    print("Please install it by running: pip install questionary")
    sys.exit(1)

# Target names for Python Envs (strictly excluding .env)
VENV_NAMES = {
    "venv",
    ".venv",
    "env",
    "virtualenv",
    ".virtualenv",
}

# Directories to strictly skip during scans
SKIP_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "appdata",
    "proc",
    "sys",
    "dev",
    "private",
    ".git",
    ".svn",
    ".hg",
}

def support_long_path(path: Path) -> str:
    """Adds extended-path prefix on Windows, safely handling Network/UNC paths."""
    path_str = str(path.absolute().resolve())
    if os.name == "nt":
        if path_str.startswith("\\\\?\\"):
            return path_str
        elif path_str.startswith("\\\\"):
            # It's a network/UNC path (e.g., \\wsl.localhost\...)
            return f"\\\\?\\UNC\\{path_str[2:]}"
        else:
            # Standard local drive path (e.g., C:\...)
            return f"\\\\?\\{path_str}"
    return path_str

def get_dir_size(path_str: str) -> int:
    """Safely computes size, ignoring symlinks to prevent infinite loops."""
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

def calculate_item_size(item: dict) -> dict:
    item["size"] = get_dir_size(item["long_path"])
    return item

def scan_directories(root_dir: Path):
    raw_targets = []
    print(f"\n🔍 Searching for dev dependencies under: {root_dir} ...")

    for current_root, dirs, _ in os.walk(root_dir, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        current_path = Path(current_root)
        dirs_to_check = list(dirs)

        for d in dirs_to_check:
            folder_path = current_path / d
            name_lower = d.lower()

            is_node = name_lower == "node_modules"
            is_venv = name_lower in VENV_NAMES and is_python_env(folder_path)

            if is_node or is_venv:
                long_path = support_long_path(folder_path)
                folder_type = "Node Module" if is_node else "Python VENV"

                raw_targets.append({
                    "path": folder_path,
                    "long_path": long_path,
                    "type": folder_type,
                })
                dirs.remove(d)

    if not raw_targets:
        return []

    print(f"Found {len(raw_targets)} candidate target(s). Calculating sizes...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        found_targets = list(executor.map(calculate_item_size, raw_targets))

    return found_targets

def remove_readonly_handler(func, path, exc_info):
    """
    Attempts to remove read-only flags. If it fails (e.g., file locked by a running process),
    it raises the error so rmtree knows it failed, preventing fake 'success' messages.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        raise e

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # .absolute() ensures that "C:" becomes "C:\", preventing working-directory bugs
    root_path = Path(target_dir).absolute().resolve()

    if not root_path.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        return

    found = scan_directories(root_path)

    if not found:
        print("✨ No node_modules or Python environments found!")
        return

    found.sort(key=lambda x: x["size"], reverse=True)
    total_reclaimable = sum(item["size"] for item in found)

    print(f"\nTotal potential space recovery: {format_size(total_reclaimable)}\n")

    choices = [
        questionary.Choice(
            title=f"{item['type']:<12} | {format_size(item['size']):<10} | {item['path']}",
            value=item
        )
        for item in found
    ]

    to_delete = questionary.checkbox(
        "Select folders to delete (Space to check/uncheck, Enter to confirm, Ctrl+C to cancel):",
        choices=choices
    ).ask()

    # Catches both Ctrl+C (None) and pressing Enter without selecting anything ([])
    if not to_delete:
        print("Cancelled. Nothing was deleted.")
        return

    selected_size = sum(item["size"] for item in to_delete)
    
    print(f"\n⚠️  PERMANENTLY deleting {len(to_delete)} folder(s) ({format_size(selected_size)}).")
    print("💡 Tip: Make sure no local servers (npm start / python) are running in these folders.")
    
    confirm = input("Are you sure? (y/N): ").strip().lower()

    if confirm != "y":
        print("Aborted. No files were deleted.")
        return

    print("\nDeleting selected directories...")
    deleted_count = 0
    for item in to_delete:
        p_display = item["path"]
        p_target = item["long_path"]
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(p_target, onexc=remove_readonly_handler)
            else:
                shutil.rmtree(p_target, onerror=remove_readonly_handler)

            print(f"  [DELETED] {p_display}")
            deleted_count += 1
        except Exception as e:
            # We now properly catch failures (e.g. "Access Denied" because a file is open)
            print(f"  [ERROR] Failed to fully delete {p_display}.")
            print(f"          Reason: {e}")

    print(f"\nDone! Reclaimed {format_size(selected_size)} across {deleted_count} directory(ies).")

if __name__ == "__amain__":
    main()