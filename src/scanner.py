import concurrent.futures
import json
import os
import time
from pathlib import Path
from src.constants import (ECOSYSTEM_TARGET_CATEGORIES, VENV_NAMES, CACHE_FILE,
                           COLOR_GREEN, COLOR_RED, COLOR_YELLOW, COLOR_BLUE,
                           COLOR_CYAN, COLOR_RESET, COLOR_BOLD)
from src.fs_utils import support_long_path, get_dir_size, format_size, is_python_env

def load_cache(root_path: Path):
    if not CACHE_FILE.exists():
        return None, None
    
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            
        root_key = str(root_path)
        if root_key in data:
            entry = data[root_key]
            
            # Handle new format vs old format
            if isinstance(entry, dict) and "items" in entry:
                cached_items = entry["items"]
                timestamp = entry.get("timestamp")
            else:
                cached_items = entry
                timestamp = None
                
            valid_items = []
            for item in cached_items:
                if Path(item["long_path"]).exists():
                    item["path"] = Path(item["path"])
                    valid_items.append(item)
                    
            return valid_items, timestamp
    except (json.JSONDecodeError, KeyError, OSError):
        return None, None
    return None, None

def save_cache(root_path: Path, items: list):
    data = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
            
    root_key = str(root_path)
    if not items:
        if root_key in data:
            del data[root_key]
    else:
        serialized_items = []
        for item in items:
            serialized = item.copy()
            serialized["path"] = str(item["path"])
            serialized_items.append(serialized)
            
        data[root_key] = {
            "timestamp": time.time(),
            "items": serialized_items
        }
    
    if not data:
        if CACHE_FILE.exists():
            try:
                os.remove(CACHE_FILE)
            except OSError:
                pass
    else:
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
        except OSError:
            pass

def process_dir(current_path: Path, skip_dirs: set):
    targets = []
    sub_dirs = []
    try:
        with os.scandir(current_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    d = entry.name
                    if d.lower() in skip_dirs:
                        continue
                    
                    folder_path = Path(entry.path)
                    name_lower = d.lower()
                    
                    is_eco_cache = name_lower in ECOSYSTEM_TARGET_CATEGORIES
                    is_venv = name_lower in VENV_NAMES and is_python_env(folder_path)
                    
                    # Parent-dependent targets
                    is_rust = (name_lower == "target" and (current_path / "Cargo.toml").exists())
                    is_maven = (name_lower == "target" and (current_path / "pom.xml").exists())
                    is_cmake = (name_lower == "build" and (current_path / "CMakeLists.txt").exists())
                    
                    if is_eco_cache or is_venv or is_rust or is_maven or is_cmake:
                        if is_eco_cache:
                            folder_type = ECOSYSTEM_TARGET_CATEGORIES.get(name_lower)
                        elif is_venv:
                            folder_type = "Python VENV"
                        elif is_rust:
                            folder_type = "Rust Target"
                        elif is_maven:
                            folder_type = "Maven Target"
                        else:  # is_cmake
                            folder_type = "CMake Build"
                            
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

def parallel_find_locations(root_dir: Path, skip_dirs: set):
    raw_targets = []
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}🔍 [PHASE 1] Parallel searching for targets under: {root_dir} ...{COLOR_RESET}\n")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_dir, root_dir, skip_dirs)}
        
        while futures:
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                futures.remove(fut)
                try:
                    targets, sub_dirs = fut.result()
                    for t in targets:
                        raw_targets.append(t)
                        print(f"  [{COLOR_GREEN}FOUND{COLOR_RESET}] {t['type']:<14} | {t['path']}")
                    for sub in sub_dirs:
                        futures.add(executor.submit(process_dir, sub, skip_dirs))
                except Exception:
                    pass
    return raw_targets

def calculate_item_size(item: dict) -> dict:
    item["size"] = get_dir_size(item["long_path"])
    return item

def parallel_calculate_sizes(raw_targets: list):
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}📊 [PHASE 2] Found {len(raw_targets)} targets. Calculating sizes in background threads...{COLOR_RESET}\n")
    found_targets = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_item = {executor.submit(calculate_item_size, item): item for item in raw_targets}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future.result()
            found_targets.append(item)
            print(f"  [{COLOR_BLUE}CALCULATED{COLOR_RESET}] {format_size(item['size']):<10} | {item['path']}")
    return found_targets

def run_full_scan(root_path: Path, skip_dirs: set):
    raw_targets = parallel_find_locations(root_path, skip_dirs)
    if not raw_targets:
        return []
    found = parallel_calculate_sizes(raw_targets)
    save_cache(root_path, found)
    return found
