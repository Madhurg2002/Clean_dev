# DevCleaner

DevCleaner is a high-performance, colorized command-line utility written in Python to scan directories, discover space-consuming developer caches/dependencies, and clean them up interactively. 

It targets:
* **Node.js / JavaScript**: `node_modules`, `.yarn`, `bower_components`, `.turbo`, `.next`, `.nuxt`, `.expo`, `.parcel-cache`, `.angular`, `.sass-cache`
* **Python**: Virtual environments (`venv`, `.venv`, `env`, etc., detecting `pyvenv.cfg` or binaries), `.pytest_cache`, `.mypy_cache`, `.tox`
* **Rust**: `target` build directories (safe checking for `Cargo.toml` in parent folder)
* **Java**: `.gradle` caches, and `target` build directories (safe checking for Maven `pom.xml` in parent folder)
* **C / C++**: `build` build directories (safe checking for CMake `CMakeLists.txt` in parent folder)
* **Ruby**: `.bundle` caches

---

## Features

* **Parallel Scanning**: Uses background thread pools to find directories rapidly.
* **Background Calculations**: Computes directory sizes concurrently to avoid UI lockups.
* **Colorized Console**: Rich ANSI color support (Green for FOUND, Blue for SIZES, Bold Cyan for headers, Red for errors) with automated Windows VT processing.
* **Interactive Configuration Wizard**: Running without arguments launches a setup wizard containing step-by-step options and path autocompletion.
* **Cache Management**: Saves scan results in a cache (`~/.devcleaner_cache.json`) for instant reloads. Cleans itself up automatically when cache entries become empty.
* **Windows Long Path Support**: Automatically formats long paths to bypass Windows path length limits.
* **Safety First**: Simulated deletions (Dry-Run mode) and safety prompts ensure files are only deleted when confirmed.

---

## Code Architecture

The codebase is partitioned into modular, single-responsibility files for easier readability:
*   [constants.py](file:///c:/Code/Study/Clean_dev/constants.py): Holds scan categories, SKIP list, cache files, and ANSI colors.
*   [fs_utils.py](file:///c:/Code/Study/Clean_dev/fs_utils.py): Holds size math, path conversion utilities, and Windows terminal color initialization.
*   [scanner.py](file:///c:/Code/Study/Clean_dev/scanner.py): Contains parallel scanning executors and JSON caching algorithms.
*   [clean_dev.py](file:///c:/Code/Study/Clean_dev/clean_dev.py): Orchestrates arguments, launches the custom scan wizard, and executes deletion flows.

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

### 1. Interactive Wizard Mode
To scan interactively (pick scan folder with autocomplete, choose sorting, toggles exclusions and dry-run), simply run without arguments:
```bash
python clean_dev.py
```

### 2. Direct CLI Automation Mode
Run the Python script by pointing it to any target directory and passing optional parameter flags:

```bash
# Scan a specific directory and group targets by folder path
python clean_dev.py C:\Users\YourUser\Projects -g

# Simulate a deletion without modifying files (Dry-Run)
python clean_dev.py -d

# Exclude custom directories from scanning (case-insensitive folder names)
python clean_dev.py -e build -e test_cache

# Clear the DevCleaner cache entirely and exit
python clean_dev.py --clear-cache

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
| `--clear-cache` | Clear the persistent scan cache file entirely and exit. |
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
   * **Windows 64-bit** (creating `DevCleaner-windows-amd64.exe`)
   * **Windows 32-bit** (creating `DevCleaner-windows-386.exe` for older or emulation architectures)
   * **macOS** (creating `DevCleaner-macos-arm64`)
   * **Linux** (creating `DevCleaner-linux-amd64`)
3. The build binaries are automatically uploaded to the matching GitHub Release page for that tag.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
