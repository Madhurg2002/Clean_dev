import os
import shutil
import subprocess
import sys
from pathlib import Path

def clean_and_build():
    root = Path(__file__).parent.resolve()
    build_dir = root / "build"
    dist_dir = root / "dist"
    spec_file = root / "DevCleaner.spec"
    
    print("[CLEAN] Cleaning local build artifacts...")
    # Remove build/
    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
            print(f"Removed {build_dir}")
        except Exception as e:
            print(f"Warning: Could not remove build folder: {e}")
            
    # Remove dist/
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
            print(f"Removed {dist_dir}")
        except Exception as e:
            print(f"Warning: Could not remove dist folder: {e}")

    # Remove any existing executable in root
    exe_name = "DevCleaner.exe" if os.name == "nt" else "DevCleaner"
    root_exe = root / exe_name
    if root_exe.exists():
        try:
            root_exe.unlink()
            print(f"Removed old binary from root: {root_exe}")
        except Exception as e:
            print(f"Warning: Could not remove old binary from root: {e}")

    if not spec_file.exists():
        print(f"Error: Spec file not found at {spec_file}")
        sys.exit(1)

    print("[BUILD] Compiling new version with PyInstaller...")
    try:
        subprocess.run(["pyinstaller", "--noconfirm", str(spec_file)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: PyInstaller build failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: PyInstaller is not installed or not in PATH.")
        sys.exit(1)

    # Copy output to root
    compiled_exe = dist_dir / exe_name
    if compiled_exe.exists():
        try:
            shutil.copy2(compiled_exe, root_exe)
            print(f"\n[SUCCESS] New version built and copied in place: {root_exe}")
            size_mb = root_exe.stat().st_size / (1024 * 1024)
            print(f"Binary Size: {size_mb:.2f} MB")
            
            # Post-build cleanup of temporary folders
            if build_dir.exists():
                shutil.rmtree(build_dir)
            if dist_dir.exists():
                shutil.rmtree(dist_dir)
        except Exception as e:
            print(f"Error: Failed during copy or cleanup: {e}")
            sys.exit(1)
    else:
        print(f"Error: Compiled executable not found at {compiled_exe}")
        sys.exit(1)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    clean_and_build()
