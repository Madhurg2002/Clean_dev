from pathlib import Path

# Target names for Python Envs (strictly excluding .env)
VENV_NAMES = {
    "venv",
    ".venv",
    "env",
    "virtualenv",
    ".virtualenv",
}

# General ecosystem caches and directories
ECOSYSTEM_TARGET_CATEGORIES = {
    "node_modules": "Node Module",
    ".yarn": "Yarn Cache",
    "bower_components": "Bower Pkgs",
    ".turbo": "Turbo Cache",
    ".next": "Next.js Cache",
    ".nuxt": "Nuxt.js Cache",
    ".expo": "Expo Cache",
    ".parcel-cache": "Parcel Cache",
    ".angular": "Angular Cache",
    ".gradle": "Gradle Cache",
    ".pytest_cache": "pytest Cache",
    ".mypy_cache": "mypy Cache",
    ".tox": "Tox Env Cache",
    ".bundle": "Bundler Cache",
    ".sass-cache": "Sass Cache",
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

# ANSI escape codes for terminal coloring
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"