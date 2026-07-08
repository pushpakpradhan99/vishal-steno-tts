import os
import shutil
import subprocess
import sys

def check_and_install_packages():
    print("Checking required packages...")
    packages = {
        "PySide6": "PySide6",
        "edge-tts": "edge-tts",
        "pyinstaller": "pyinstaller",
        "PIL": "Pillow"
    }
    for import_name, pip_name in packages.items():
        try:
            __import__(import_name)
            print(f"  {import_name} is already installed.")
        except ImportError:
            print(f"  {import_name} is missing. Installing {pip_name}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pip_name], check=True)

def build_app():
    check_and_install_packages()

    print("Starting PyInstaller compilation...")
    # --noconsole hides the command prompt window when the GUI launches
    cmd = [sys.executable, "-m", "PyInstaller", "--noconsole", "--clean", "--noconfirm", "--icon", "app_icon.ico", "--name", "Vishal Steno", "main.py"]
    subprocess.run(cmd, check=True)
    
    print("Starting keygen compilation...")
    cmd_keygen = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", "--clean", "--noconfirm", "--icon", "app_icon.ico", "--name", "Vishal Keygen", "keygen_gui.py"]
    subprocess.run(cmd_keygen, check=True)
    print("PyInstaller compilation completed.")

    # Target build dir
    dist_dir = os.path.join("dist", "Vishal Steno")
    if not os.path.exists(dist_dir):
        print(f"Error: Build directory {dist_dir} was not created!")
        sys.exit(1)

    print("Copying gui.py, version.json, app_icon.png and User_Guide.txt...")
    shutil.copy("gui.py", os.path.join(dist_dir, "gui.py"))
    shutil.copy("version.json", os.path.join(dist_dir, "version.json"))
    if os.path.exists("app_icon.png"):
        shutil.copy("app_icon.png", os.path.join(dist_dir, "app_icon.png"))
    if os.path.exists("User_Guide.txt"):
        shutil.copy("User_Guide.txt", os.path.join(dist_dir, "User_Guide.txt"))

    print("Copying FFmpeg binaries...")
    ffmpeg_target_dir = os.path.join(dist_dir, "ffmpeg")
    os.makedirs(ffmpeg_target_dir, exist_ok=True)

    ffmpeg_src_dir = r"C:\Users\Pushpak\Downloads\ffmpeg-2026-06-10-git-b29bdd3715-essentials_build\ffmpeg-2026-06-10-git-b29bdd3715-essentials_build\bin"
    
    binaries = ["ffmpeg.exe", "ffprobe.exe"]
    for binary in binaries:
        src = os.path.join(ffmpeg_src_dir, binary)
        dst = os.path.join(ffmpeg_target_dir, binary)
        if os.path.exists(src):
            print(f"  Copying {binary} to local folder...")
            shutil.copy(src, dst)
        else:
            print(f"  Warning: {binary} not found at {src}!")

    # Rename to target distribution name
    final_dist = os.path.join("dist", "Vishal Steno TTS")
    if os.path.exists(final_dist):
        shutil.rmtree(final_dist)
    
    os.rename(dist_dir, final_dist)
    print(f"\nSUCCESS: Portable application is ready in: {os.path.abspath(final_dist)}")

if __name__ == "__main__":
    build_app()
