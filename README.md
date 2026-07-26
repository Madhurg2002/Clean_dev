# DevCleaner

DevCleaner is a high-performance, parallelized command-line utility written in Python to scan directories, discover space-consuming developer caches/dependencies, and clean them up interactively. 

It targets:
* **Node.js / JavaScript**: `node_modules`, `.yarn`, `bower_components`, `.turbo`, `.next`, `.nuxt`, `.expo`, `.parcel-cache`, `.angular`
* **Python**: Virtual environments (`venv`, `.venv`, `env`, etc., detecting `pyvenv.cfg` or python binaries inside)

---

## Features

* **Parallel Scanning**: Uses background thread pools to find directories rapidly.
* **Background Calculations**: Computes directory sizes concurrently to avoid UI lockups.
* **Interactive TUI**: Selection checkboxes and select menus powered by `questionary`.
* **Caching System**: Saves scan results in a cache (`~/.devcleaner_cache.json`) for instant reload/actions.
* **Windows Long Path Support**: Automatically formats long paths to bypass Windows path length limits.
* **Safety First**: Asks for confirmation before deletion, allows selective deletion, and prompts to make sure no active processes are lock-holding files.

---

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Clean_dev
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

Run the Python script by pointing it to any target directory you want to clean (defaults to the current directory if omitted):

```bash
# Scan the current directory (ordered by size descending)
python clean_dev.py

# Scan a specific directory and group targets by folder path
python clean_dev.py C:\Users\YourUser\Projects -g

# Simulate a deletion without modifying files (Dry-Run)
python clean_dev.py -d

# Exclude custom directories from scanning (case-insensitive folder names)
python clean_dev.py -e build -e test_cache

# View CLI help instructions
python clean_dev.py --help
```

### CLI Options Table:
| Option | Description |
|---|---|
| `target_dir` | The directory to scan for cleanup targets (default: current directory). |
| `-g, --group-by-folder` | Group (sort) targets by their folder path instead of size (descending). |
| `-d, --dry-run` | Simulate deletion without removing any files on disk. |
| `-e, --exclude <dir>` | Custom folder names to strictly ignore during target discovery (can be used multiple times). |
| `-h, --help` | Show usage options and exits. |

---

## Building a Standalone Executable

You can compile a standalone executable of DevCleaner (no Python installation required to run) using PyInstaller:

```bash
pyinstaller --onefile --console --name "DevCleaner" --noconfirm clean_dev.py
```

The output standalone executable will be generated at:
* **Windows**: `dist/DevCleaner.exe`
* **Linux / macOS**: `dist/DevCleaner`

Alternatively, build using the existing specification file:
```bash
pyinstaller --noconfirm DevCleaner.spec
```

---

## Automated Releases via GitHub Actions

This repository includes a GitHub Actions workflow that automates the building and releasing of multi-platform binaries.

### How it works:
1. When a new tag matching `v*` (e.g. `v1.0.0`) is pushed to GitHub, the workflow triggers automatically.
2. The workflow compiles the executable on a matrix of runner environments:
   * **Windows** (creating `DevCleaner-windows-amd64.exe`)
   * **macOS** (creating `DevCleaner-macos-arm64`)
   * **Linux** (creating `DevCleaner-linux-amd64`)
3. The build binaries are automatically uploaded to the matching GitHub Release page for that tag.
