import concurrent.futures
import json
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

# JS/Node/Yarn ecosystem caches and directories
JS_TARGET_CATEGORIES = {
    "node_modules": "Node Module",
    ".yarn": "Yarn Cache",
    "bower_components": "Bower Pkgs",
    ".turbo": "Turbo Cache",
    ".next": "Next.js Cache",
    ".nuxt": "Nuxt.js Cache",
    ".expo": "Expo Cache",
    ".parcel-cache": "Parcel Cache",
    ".angular": "Angular Cache",
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

# Location to store the persistent cache
CACHE_FILE = Path.home() / ".devcleaner_cache.json"

def load_cache(root_path: Path):
    if not CACHE_FILE.exists():
        return None
    
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            
        root_key = str(root_path)
        if root_key in data:
            cached_items = data[root_key]
            valid_items = []
            
            for item in cached_items:
                if Path(item["long_path"]).exists():
                    item["path"] = Path(item["path"])
                    valid_items.append(item)
                    
            return valid_items
    except (json.JSONDecodeError, KeyError, OSError):
        return None
    return None

def save_cache(root_path: Path, items: list):
    data = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
            
    serialized_items = []
    for item in items:
        serialized = item.copy()
        serialized["path"] = str(item["path"])
        serialized_items.append(serialized)
        
    data[str(root_path)] = serialized_items
    
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass

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

def process_dir(current_path: Path):
    targets = []
    sub_dirs = []
    try:
        with os.scandir(current_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    d = entry.name
                    if d.lower() in SKIP_DIRS:
                        continue
                    
                    folder_path = Path(entry.path)
                    name_lower = d.lower()
                    
                    is_js_env = name_lower in JS_TARGET_CATEGORIES
                    is_venv = name_lower in VENV_NAMES and is_python_env(folder_path)
                    
                    if is_js_env or is_venv:
                        folder_type = JS_TARGET_CATEGORIES.get(name_lower) if is_js_env else "Python VENV"
                        targets.append({
                            "path": folder_path,
                            "long_path": support_long_path(folder_path),
                            "type": folder_type,
                        })
                    else:
                        sub_dirs.append(folder_path)
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return targets, sub_dirs

def parallel_find_locations(root_dir: Path):
    raw_targets = []
    print(f"\n🔍 [PHASE 1] Parallel searching for targets under: {root_dir} ...\n")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_dir, root_dir)}
        
        while futures:
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                futures.remove(fut)
                try:
                    targets, sub_dirs = fut.result()
                    for t in targets:
                        raw_targets.append(t)
                        # Padding expanded to 14 to fit "Next.js Cache"
                        print(f"  [FOUND] {t['type']:<14} | {t['path']}")
                    for sub in sub_dirs:
                        futures.add(executor.submit(process_dir, sub))
                except Exception:
                    pass
    return raw_targets

def calculate_item_size(item: dict) -> dict:
    item["size"] = get_dir_size(item["long_path"])
    return item

def parallel_calculate_sizes(raw_targets: list):
    print(f"\n📊 [PHASE 2] Found {len(raw_targets)} targets. Calculating sizes in background threads...\n")
    found_targets = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_item = {executor.submit(calculate_item_size, item): item for item in raw_targets}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future.result()
            found_targets.append(item)
            print(f"  [CALCULATED] {format_size(item['size']):<10} | {item['path']}")
    return found_targets

def run_full_scan(root_path: Path):
    raw_targets = parallel_find_locations(root_path)
    if not raw_targets:
        return []
    found = parallel_calculate_sizes(raw_targets)
    save_cache(root_path, found)
    return found

def remove_readonly_handler(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        raise e

def main():
    group_by_folder = False
    target_dir = "."

    # Parse arguments manually
    args = sys.argv[1:]
    
    # Check for help
    if any(arg in ("-h", "--help") for arg in args):
        print("DevCleaner - Scan and clean development environments")
        print("\nUsage:")
        print("  DevCleaner [target_directory] [options]")
        print("\nArguments:")
        print("  target_directory   The directory to scan for cleanup targets (default: current directory)")
        print("\nOptions:")
        print("  -h, --help         Show this help message and exit")
        print("  -g, --group-by-folder  Group (sort) targets by their folder path instead of size")
        return

    # Check for group_by_folder flag
    if "--group-by-folder" in args:
        group_by_folder = True
        args.remove("--group-by-folder")
    if "-g" in args:
        group_by_folder = True
        args.remove("-g")

    # Target directory is the first remaining argument, if any
    if args:
        target_dir = args[0]

    root_path = Path(target_dir).absolute().resolve()

    if not root_path.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        return

    found = []
    
    try:
        cached_data = load_cache(root_path)
        
        if cached_data:
            print(f"\n⚡ Found a previous scan for: {root_path}")
            action = questionary.select(
                "What would you like to do?",
                choices=[
                    "Load previous list (Instant)",
                    "Refresh list (Rescan and calculate)"
                ]
            ).ask()
            
            if not action:
                print("Cancelled.")
                return
                
            if action.startswith("Load"):
                found = cached_data
                print(f"Loaded {len(found)} targets from cache.\n")
            else:
                found = run_full_scan(root_path)
        else:
            found = run_full_scan(root_path)
            
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user during scan.")
        return

    if not found:
        print("✨ No target directories found!")
        return

    if group_by_folder:
        print("Sorting targets by folder path...")
        found.sort(key=lambda x: str(x["path"]).lower())
    else:
        print("Sorting targets by size (descending)...")
        found.sort(key=lambda x: x["size"], reverse=True)

    total_reclaimable = sum(item["size"] for item in found)
    print(f"\nTotal potential space recovery: {format_size(total_reclaimable)}\n")

    choices = [
        questionary.Choice(
            title=f"{item['type']:<14} | {format_size(item['size']):<10} | {item['path']}",
            value=item
        )
        for item in found
    ]

    try:
        to_delete = questionary.checkbox(
            "Select folders to delete (Space to check/uncheck, Enter to confirm, Ctrl+C to cancel):",
            choices=choices
        ).ask()
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was deleted.")
        return

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
    successfully_deleted_long_paths = set()
    
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
            successfully_deleted_long_paths.add(p_target)
        except Exception as e:
            print(f"  [ERROR] Failed to fully delete {p_display}.")
            print(f"          Reason: {e}")

    if successfully_deleted_long_paths:
        updated_cache = [item for item in found if item["long_path"] not in successfully_deleted_long_paths]
        save_cache(root_path, updated_cache)

    print(f"\nDone! Reclaimed {format_size(selected_size)} across {deleted_count} directory(ies).")

if __name__ == "__main__":
    main()