import argparse
import os
import shutil
import sys
import time
from pathlib import Path

try:
    import questionary
except ImportError:
    print("Error: The interactive menu requires the 'questionary' library.")
    print("Please install it by running: pip install questionary")
    sys.exit(1)

from src.constants import (SKIP_DIRS, COLOR_GREEN, COLOR_RED, COLOR_YELLOW,
                           COLOR_BLUE, COLOR_CYAN, COLOR_RESET, COLOR_BOLD)
from src.fs_utils import format_size, remove_readonly_handler, enable_ansi_support
from src.scanner import load_cache, save_cache, run_full_scan
from src.tui import filter_checkbox_tui

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    enable_ansi_support()

    # If no arguments are passed, launch the Interactive Wizard
    if len(sys.argv) == 1:
        print(f"{COLOR_BOLD}💡 Welcome to DevCleaner!{COLOR_RESET}")
        
        wizard = questionary.select(
            "What would you like to do?",
            choices=[
                "Run standard scan (Scan '.', sort by size)",
                "Configure custom scan settings (Interactive Wizard)",
                "Clear entire cache"
            ]
        ).ask()

        if not wizard:
            return

        if wizard == "Clear entire cache":
            from src.constants import CACHE_FILE
            if CACHE_FILE.exists():
                try:
                    os.remove(CACHE_FILE)
                    print("🧹 Cache cleared successfully.")
                except OSError as e:
                    print(f"❌ Error clearing cache: {e}")
            else:
                print("🧹 Cache is already empty/cleared.")
            return

        if wizard.startswith("Run standard scan"):
            target_dir = "."
            group_by_folder = False
            dry_run = False
            custom_excludes = []
        else:
            # Interactive Configuration Wizard
            target_dir = questionary.path(
                "Enter the directory to scan:",
                default="."
            ).ask()
            if not target_dir:
                return

            sort_choice = questionary.select(
                "How should targets be ordered?",
                choices=[
                    "By size (descending)",
                    "Group by folder path"
                ]
            ).ask()
            if not sort_choice:
                return
            group_by_folder = (sort_choice == "Group by folder path")

            dry_run = questionary.confirm(
                "Enable Dry-Run mode? (Simulates deletion without deleting files)",
                default=False
            ).ask()
            if dry_run is None:
                return

            exclude_input = questionary.text(
                "Enter additional folder names to exclude (comma-separated, or leave blank):",
                default=""
            ).ask()
            if exclude_input is None:
                return
            custom_excludes = [x.strip() for x in exclude_input.split(",") if x.strip()]
    else:
        # CLI Mode
        parser = argparse.ArgumentParser(
            description="DevCleaner - Scan and clean development environments",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=r"""
Examples:
  python main.py                     # Interactive Wizard (when run without arguments)
  python main.py C:\Projects         # Scan custom directory directly
  python main.py -g                  # Group/sort targets by path directly
  python main.py -d                  # Dry-run mode directly
  python main.py -e build -e dist    # Exclude custom directories directly
"""
        )
        parser.add_argument("target_dir", nargs="?", default=".", help="The directory to scan for cleanup targets")
        parser.add_argument("-g", "--group-by-folder", action="store_true", help="Group (sort) targets by their folder path instead of size")
        parser.add_argument("-d", "--dry-run", action="store_true", help="Simulate deletion without removing files")
        parser.add_argument("-e", "--exclude", action="append", default=[], help="Additional directory names to exclude during scanning (case-insensitive)")
        parser.add_argument("--clear-cache", action="store_true", help="Clear the DevCleaner cache file entirely and exit")

        args = parser.parse_args()

        if args.clear_cache:
            from src.constants import CACHE_FILE
            if CACHE_FILE.exists():
                try:
                    os.remove(CACHE_FILE)
                    print("🧹 Cache cleared successfully.")
                except OSError as e:
                    print(f"❌ Error clearing cache: {e}")
            else:
                print("🧹 Cache is already empty/cleared.")
            return

        target_dir = args.target_dir
        group_by_folder = args.group_by_folder
        dry_run = args.dry_run
        custom_excludes = args.exclude

    root_path = Path(target_dir).absolute().resolve()

    if not root_path.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        return

    # Combine default skip dirs with custom user exclusions
    skip_dirs = {d.lower() for d in SKIP_DIRS}
    for excl in custom_excludes:
        skip_dirs.add(excl.lower())

    found = []

    try:
        cached_data, timestamp = load_cache(root_path)
        
        if cached_data:
            if timestamp:
                age_seconds = int(time.time() - timestamp)
                if age_seconds < 60:
                    age_str = "just now"
                elif age_seconds < 3600:
                    age_str = f"{age_seconds // 60}m ago"
                elif age_seconds < 86400:
                    age_str = f"{age_seconds // 3600}h ago"
                else:
                    age_str = f"{age_seconds // 86400}d ago"
                print(f"\n⚡ Found a previous scan for: {root_path} (Scanned {age_str})")
            else:
                print(f"\n⚡ Found a previous scan for: {root_path}")

            action = questionary.select(
                "What would you like to do?",
                choices=[
                    "Load previous list (Instant)",
                    "Refresh list (Rescan and calculate)",
                    "Clear cache for this directory"
                ]
            ).ask()
            
            if not action:
                print("Cancelled.")
                return
                
            if action.startswith("Load"):
                found = cached_data
                print(f"Loaded {len(found)} targets from cache.\n")
            elif action.startswith("Clear"):
                save_cache(root_path, [])
                print(f"🧹 Cache cleared for {root_path}.")
                return
            else:
                found = run_full_scan(root_path, skip_dirs)
        else:
            found = run_full_scan(root_path, skip_dirs)
            
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user during scan.")
        return

    if not found:
        print("✨ No target directories found!")
        return

    # Apply sorting option
    if group_by_folder:
        print("Sorting targets by folder path...")
        found.sort(key=lambda x: str(x["path"]).lower())
    else:
        print("Sorting targets by size (descending)...")
        found.sort(key=lambda x: x["size"], reverse=True)

    total_reclaimable = sum(item["size"] for item in found)
    print(f"\nTotal potential space recovery: {format_size(total_reclaimable)}\n")

    try:
        to_delete = filter_checkbox_tui(found, group_by_folder)
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was deleted.")
        return

    if not to_delete:
        print("Cancelled. Nothing was deleted.")
        return

    selected_size = sum(item["size"] for item in to_delete)
    
    if dry_run:
        print(f"\n{COLOR_BOLD}{COLOR_GREEN}✨ [DRY-RUN] Simulating deletion of {len(to_delete)} folder(s) ({format_size(selected_size)}).{COLOR_RESET}")
        for item in to_delete:
            print(f"  [{COLOR_YELLOW}WOULD DELETE{COLOR_RESET}] {item['path']}")
        print(f"\nDry run complete. No files were modified.")
        return

    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}⚠️  PERMANENTLY deleting {len(to_delete)} folder(s) ({format_size(selected_size)}).{COLOR_RESET}")
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

            print(f"  [{COLOR_GREEN}DELETED{COLOR_RESET}] {p_display}")
            deleted_count += 1
            successfully_deleted_long_paths.add(p_target)
        except Exception as e:
            print(f"  [{COLOR_RED}ERROR{COLOR_RESET}] Failed to fully delete {p_display}.")
            print(f"          Reason: {e}")

    if successfully_deleted_long_paths:
        updated_cache = [item for item in found if item["long_path"] not in successfully_deleted_long_paths]
        save_cache(root_path, updated_cache)

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Done! Reclaimed {format_size(selected_size)} across {deleted_count} directory(ies).{COLOR_RESET}")

if __name__ == "__main__":
    main()
