import os
import sys
import re
import json
import asyncio
import tempfile
import traceback
import subprocess
import shutil
import hashlib
import base64
import urllib.request
from PySide6.QtCore import QThread, Signal, Slot, Qt, QUrl, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QTextEdit, QSlider, QComboBox,
    QProgressBar, QMessageBox, QFileDialog, QListWidget, QListWidgetItem, QSplitter
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PIL import Image, ImageOps, ImageDraw

# Add current folder and local ffmpeg to system path
app_dir = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)

ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
if os.path.exists(ffmpeg_dir):
    os.environ["PATH"] += os.pathsep + ffmpeg_dir

# Windows specific flag to hide subprocess console windows
creationflags = 0
if os.name == 'nt':
    creationflags = subprocess.CREATE_NO_WINDOW # 0x08000000

# ==============================================================================
# SETTINGS PERSISTENCE CONTROL (DESKTOP BY DEFAULT)
# ==============================================================================

def get_settings_file():
    db_dir = os.path.join(app_dir, "database")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "settings.json")

def load_save_directory():
    settings_file = get_settings_file()
    default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(default_dir):
        default_dir = app_dir # Fallback
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_dir = data.get("default_save_dir")
                if custom_dir and os.path.exists(custom_dir):
                    return custom_dir
        except Exception:
            pass
    return default_dir

def save_save_directory(custom_dir):
    settings_file = get_settings_file()
    try:
        data = {"default_save_dir": custom_dir}
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Failed to save settings: {e}")
        return False

# ==============================================================================
# AUTO-UPDATE APP_ICON LOGIC FOR EXISTING CLIENTS
# ==============================================================================

def check_and_update_icon_locally():
    """If client has old/missing app_icon.png, download the new compressed logo from GitHub."""
    icon_path = os.path.join(app_dir, "app_icon.png")
    github_icon_url = "https://raw.githubusercontent.com/pushpakpradhan99/vishal-steno-tts/main/app_icon.png"
    target_size = 242826 # Exact byte size of the compressed transparent logo
    
    try:
        needs_download = True
        if os.path.exists(icon_path):
            if os.path.getsize(icon_path) == target_size:
                needs_download = False
                
        if needs_download:
            print("Client has old/missing icon. Auto-downloading new logo from GitHub...")
            with urllib.request.urlopen(github_icon_url, timeout=5) as response:
                if response.status == 200:
                    data = response.read()
                    with open(icon_path, "wb") as f:
                        f.write(data)
                    print("App icon successfully auto-updated locally!")
    except Exception as e:
        print(f"Non-blocking update icon error: {e}")

# ==============================================================================
# CRYPTOGRAPHIC OFFLINE LICENSING CONTROL (RSA PUBLIC KEY ONLY)
# ==============================================================================

n = 124484595126548117481489410632012745818099415314085246803913294395814594355817893828886876474260975617030661874116414140863309392568758272381314926388952317527104692355122747277559442195925048622329862152643590701582746699287007318250273369063094606275229208675128862921767919126355453436035495589524808617817
e = 65537

def get_machine_uuid():
    """Retrieves unique motherboard hardware UUID on Windows."""
    try:
        out = subprocess.check_output("wmic csproduct get uuid", shell=True, creationflags=creationflags)
        uuid_str = out.decode().split('\n')[1].strip()
        if len(uuid_str) > 10 and "-" in uuid_str:
            return uuid_str.upper()
    except Exception:
        pass
    
    # Fallback to MAC address
    try:
        import uuid
        mac = str(uuid.getnode())
        return f"FALLBACK-{mac.upper()}"
    except Exception:
        return "UNKNOWN-MACHINE-ID-12345"

def get_hash_int(machine_id):
    mid_bytes = machine_id.strip().upper().encode('utf-8')
    h_hex = hashlib.sha256(mid_bytes).hexdigest()
    return int(h_hex, 16) % n

def verify_license_key(machine_id, key_str):
    """Verifies RSA signature key offline (pow(sig, e, n) == hash_int)."""
    try:
        if not key_str.startswith("VST-KEY-"):
            return False
        b64_part = key_str[8:]
        b64_part += "=" * ((4 - len(b64_part) % 4) % 4)
        sig_bytes = base64.b64decode(b64_part.encode('utf-8'))
        sig_int = int.from_bytes(sig_bytes, byteorder='big')
        
        h_calc = pow(sig_int, e, n)
        return h_calc == get_hash_int(machine_id)
    except Exception:
        return False

def verify_license():
    """Checks if the local license key is valid for this PC."""
    local_license_path = os.path.join(app_dir, "license.key")
    if not os.path.exists(local_license_path):
        return False
    try:
        with open(local_license_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
        mid = get_machine_uuid()
        return verify_license_key(mid, key)
    except Exception:
        return False

# ==============================================================================
# PERSISTENT DATABASE COUNTER
# ==============================================================================

def get_next_counter():
    db_dir = os.path.join(app_dir, "database")
    os.makedirs(db_dir, exist_ok=True)
    counter_file = os.path.join(db_dir, "counter.txt")
    counter = 1
    if os.path.exists(counter_file):
        try:
            with open(counter_file, "r") as f:
                counter = int(f.read().strip())
        except Exception:
            counter = 1
    return counter

def increment_counter():
    db_dir = os.path.join(app_dir, "database")
    os.makedirs(db_dir, exist_ok=True)
    counter_file = os.path.join(db_dir, "counter.txt")
    counter = get_next_counter()
    try:
        with open(counter_file, "w") as f:
            f.write(str(counter + 1))
    except Exception as e:
        print(f"Failed to increment counter: {e}")

# ==============================================================================
# SPEECH SYNTHESIS ENGINE INTERFACES
# ==============================================================================

class BaseSpeechEngine:
    async def synthesize(self, text, voice, rate_pct, out_path) -> bool:
        raise NotImplementedError

class EdgeSpeechEngine(BaseSpeechEngine):
    async def synthesize(self, text, voice, rate_pct, out_path) -> bool:
        import edge_tts
        rate_str = f"{rate_pct:+d}%"
        voice_short_name = "hi-IN-SwaraNeural" if "Swara" in voice else "hi-IN-MadhurNeural"
        communicate = edge_tts.Communicate(text, voice_short_name, rate=rate_str)
        await communicate.save(out_path)
        return True

class LocalSpeechEngine(BaseSpeechEngine):
    async def synthesize(self, text, voice, rate_pct, out_path) -> bool:
        raise NotImplementedError("Local Offline Speech Engine not yet integrated.")

# ==============================================================================
# ASYNCHRONOUS WORKERS (QTHREADS)
# ==============================================================================

class RenderWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, voice, rate_pct, out_path, use_local_engine=False):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate_pct = rate_pct
        self.out_path = out_path
        self.use_local_engine = use_local_engine

    def run(self):
        try:
            self.progress.emit("Synthesizing speech audio...")
            
            if self.use_local_engine:
                engine = LocalSpeechEngine()
            else:
                engine = EdgeSpeechEngine()

            async def run_async():
                return await engine.synthesize(self.text, self.voice, self.rate_pct, self.out_path)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_async())
            loop.close()

            self.finished.emit(self.out_path)
        except Exception as e:
            self.error.emit(str(e))


class VideoRenderWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, speech_mp3, images, pre_roll, post_roll, out_mp4):
        super().__init__()
        self.speech_mp3 = speech_mp3
        self.images = images
        self.pre_roll = pre_roll
        self.post_roll = post_roll
        self.out_mp4 = out_mp4

    def run(self):
        try:
            temp_dir = tempfile.gettempdir()
            processed_images = []
            
            # Step 1: Optimize images to exactly 1920x1080 center-cropped
            if self.images:
                self.progress.emit("Centering and cropping images to 16:9 (1080p)...")
                for idx, img_path in enumerate(self.images):
                    dest_img = os.path.join(temp_dir, f"vst_slide_{idx}.jpg")
                    with Image.open(img_path) as img:
                        img_fit = ImageOps.fit(img, (1920, 1080), centering=(0.5, 0.5))
                        img_fit.convert('RGB').save(dest_img, 'JPEG', quality=95)
                    processed_images.append(dest_img)
            else:
                # No images: Create a default dark brand background
                self.progress.emit("Creating default background card...")
                dest_img = os.path.join(temp_dir, "vst_default_bg.jpg")
                img = Image.new('RGB', (1920, 1080), color='#161824')
                draw = ImageDraw.Draw(img)
                draw.text((750, 480), "VISHAL STENO", fill="#66fcf1")
                draw.text((750, 520), "Text to Speech Studio", fill="#85929E")
                img.save(dest_img, 'JPEG', quality=95)
                processed_images.append(dest_img)

            # Step 2: Separate Pre/Post media into audio or video
            pre_audio = None
            pre_video = None
            if self.pre_roll and os.path.exists(self.pre_roll):
                if self.pre_roll.lower().endswith(('.mp3', '.wav', '.m4a')):
                    pre_audio = self.pre_roll
                elif self.pre_roll.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    pre_video = self.pre_roll
                    
            post_audio = None
            post_video = None
            if self.post_roll and os.path.exists(self.post_roll):
                if self.post_roll.lower().endswith(('.mp3', '.wav', '.m4a')):
                    post_audio = self.post_roll
                elif self.post_roll.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    post_video = self.post_roll

            # Step 3: Compile Audio Track
            self.progress.emit("Building audio timeline...")
            audio_inputs = []
            if pre_audio:
                audio_inputs.append(pre_audio)
            audio_inputs.append(self.speech_mp3)
            if post_audio:
                audio_inputs.append(post_audio)
                
            combined_audio = os.path.join(temp_dir, "vst_combined_audio.mp3")
            if len(audio_inputs) == 1:
                # Normalize speech volume to standard loudness target
                cmd = ["ffmpeg", "-y", "-i", audio_inputs[0], "-af", "loudnorm", combined_audio]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
            else:
                cmd = ["ffmpeg", "-y"]
                for a in audio_inputs:
                    cmd.extend(["-i", a])
                # Normalize each audio source to balance their volume levels before concatenation
                filter_str = ""
                for idx in range(len(audio_inputs)):
                    filter_str += f"[{idx}:a]loudnorm[a{idx}];"
                for idx in range(len(audio_inputs)):
                    filter_str += f"[a{idx}]"
                filter_str += f"concat=n={len(audio_inputs)}:v=0:a=1[a]"
                cmd.extend(["-filter_complex", filter_str, "-map", "[a]", combined_audio])
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)

            # Get combined audio duration using ffprobe (run silently)
            duration_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", combined_audio
            ]
            dur_out = subprocess.check_output(duration_cmd, creationflags=creationflags).decode().strip()
            total_audio_duration = float(dur_out)

            # Step 4: Compile main slideshow video matching exact audio duration
            self.progress.emit("Structuring slideshow timeline...")
            num_images = len(processed_images)
            dur_per_image = total_audio_duration / num_images
            
            # Write slideshow demuxer text config
            slideshow_txt = os.path.join(temp_dir, "vst_slideshow.txt")
            with open(slideshow_txt, "w", encoding="utf-8") as f_slide:
                for img_path in processed_images:
                    escaped_path = img_path.replace("\\", "/")
                    f_slide.write(f"file '{escaped_path}'\n")
                    f_slide.write(f"duration {dur_per_image:.3f}\n")
                escaped_path = processed_images[-1].replace("\\", "/")
                f_slide.write(f"file '{escaped_path}'\n")

            main_slideshow_mp4 = os.path.join(temp_dir, "vst_slideshow.mp4")
            
            self.progress.emit("Compiling images and audio to MP4...")
            cmd_slide = [
                "ffmpeg", "-y", "-safe", "0", "-f", "concat", "-i", slideshow_txt,
                "-i", combined_audio, "-c:v", "libx264", "-r", "25", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", main_slideshow_mp4
            ]
            subprocess.run(cmd_slide, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)

            # Step 5: Stitch Pre-video + Main Slideshow + Post-video if present
            video_inputs = []
            if pre_video:
                video_inputs.append(pre_video)
            video_inputs.append(main_slideshow_mp4)
            if post_video:
                video_inputs.append(post_video)
                
            if len(video_inputs) == 1:
                shutil.copy(main_slideshow_mp4, self.out_mp4)
            else:
                self.progress.emit("Stitching pre-roll and post-roll video tracks...")
                cmd_stitch = ["ffmpeg", "-y"]
                for v in video_inputs:
                    cmd_stitch.extend(["-i", v])
                    
                filter_complex_str = ""
                # Scale each video stream to 1080p
                for idx in range(len(video_inputs)):
                    filter_complex_str += f"[{idx}:v]scale=1920:1080,setsar=1,fps=25[v{idx}];"
                # Normalize each video's audio track to balance their volume levels
                for idx in range(len(video_inputs)):
                    filter_complex_str += f"[{idx}:a]loudnorm[a{idx}];"
                # Concatenate scaled videos and normalized audios
                for idx in range(len(video_inputs)):
                    filter_complex_str += f"[v{idx}][a{idx}]"
                filter_complex_str += f"concat=n={len(video_inputs)}:v=1:a=1[v][a]"
                
                cmd_stitch.extend([
                    "-filter_complex", filter_complex_str,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", self.out_mp4
                ])
                subprocess.run(cmd_stitch, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)

            self.finished.emit(self.out_mp4)
        except Exception as e:
            self.error.emit(str(e))

# ==============================================================================
# MODERN CSS STYLESHEET
# ==============================================================================

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #0b0c10;
}
QWidget {
    color: #c5c6c7;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}
QFrame#sidebar_card, QFrame#editor_card, QFrame#media_card {
    background-color: #1f2833;
    border: 1px solid #2f3e46;
    border-radius: 12px;
}
QFrame#player_card {
    background-color: #1f2833;
    border: 1px solid #2f3e46;
    border-radius: 12px;
    padding: 5px;
}
QTextEdit {
    background-color: #0b0c10;
    border: 1px solid #2f3e46;
    border-radius: 8px;
    padding: 10px;
    font-size: 16px;
    color: #f1f5f9;
}
QTextEdit:focus {
    border: 1px solid #66fcf1;
}
QPushButton {
    background-color: #1f2833;
    border: 1px solid #66fcf1;
    border-radius: 6px;
    color: #66fcf1;
    padding: 8px 14px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #66fcf1;
    color: #0b0c10;
}
QPushButton:pressed {
    background-color: #45a29e;
}
QPushButton#dictation_1_btn {
    background-color: #831843;
    border: 1px solid #be185d;
    color: #fbcfe8;
}
QPushButton#dictation_1_btn:hover {
    background-color: #be185d;
    color: #ffffff;
}
QPushButton#dictation_2_btn {
    background-color: #1e3a8a;
    border: 1px solid #2563eb;
    color: #dbeafe;
}
QPushButton#dictation_2_btn:hover {
    background-color: #2563eb;
    color: #ffffff;
}
QPushButton#generate_btn {
    background-color: #45a29e;
    color: #0b0c10;
    border: 1px solid #66fcf1;
    font-size: 14px;
    padding: 12px;
}
QPushButton#generate_btn:hover {
    background-color: #66fcf1;
}
QPushButton#save_audio_btn {
    color: #ffffff;
    border: 1px solid #ffffff;
}
QPushButton#save_audio_btn:hover {
    background-color: #ffffff;
    color: #0b0c10;
}
QComboBox {
    background-color: #0b0c10;
    border: 1px solid #2f3e46;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f1f5f9;
}
QComboBox:on {
    border: 1px solid #66fcf1;
}
QComboBox QAbstractItemView {
    background-color: #1f2833;
    color: #f1f5f9;
    selection-background-color: #66fcf1;
    selection-color: #0b0c10;
    outline: none;
}
QProgressBar {
    border: 1px solid #2f3e46;
    border-radius: 4px;
    text-align: center;
    background-color: #0b0c10;
    color: #ffffff;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #45a29e;
}
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #0b0c10;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #66fcf1;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #45a29e;
}
QListWidget {
    background-color: #0b0c10;
    border: 1px solid #2f3e46;
    border-radius: 6px;
    color: #f1f5f9;
}
"""

# ==============================================================================
# MAIN APPLICATION WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.generated_file = None
        self.worker = None
        self.video_worker = None
        
        # State tracking for dynamic dictation formatting
        self.raw_text = ""
        self.is_optimizing = False
        self.current_optimization = None
        
        # Media lists
        self.imported_images = []
        self.pre_roll_media = None
        self.post_roll_media = None
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Vishal Steno - Premium Text to Speech Studio v1.0.0")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        # Set taskbar window icon dynamically
        icon_path = os.path.join(app_dir, "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ----------------------------------------------------------------------
        # LEFT SIDEBAR - CONTROLS (SPACED DYNAMICALLY)
        # ----------------------------------------------------------------------
        sidebar = QFrame(self)
        sidebar.setObjectName("sidebar_card")
        sidebar.setFixedWidth(340)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(15)

        # App Header Brand with custom generated Logo next to it
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        logo_label = QLabel(self)
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        
        text_brand_layout = QVBoxLayout()
        text_brand_layout.setSpacing(2)
        brand_label = QLabel("VISHAL STENO", self)
        brand_label.setStyleSheet("font-weight: 800; font-size: 20px; color: #66fcf1; letter-spacing: 1px;")
        subtitle_label = QLabel("Speech Studio & Dictation Tool", self)
        subtitle_label.setStyleSheet("font-size: 11px; color: #85929E; font-weight: 500;")
        text_brand_layout.addWidget(brand_label)
        text_brand_layout.addWidget(subtitle_label)
        
        if os.path.exists(icon_path):
            header_layout.addWidget(logo_label)
        header_layout.addLayout(text_brand_layout)
        sidebar_layout.addLayout(header_layout)

        # Settings Configuration Row (Below header, above voice settings)
        settings_row_layout = QHBoxLayout()
        self.settings_btn = QPushButton("⚙️ Settings", self)
        self.settings_btn.setStyleSheet("margin-top: 5px;")
        self.settings_btn.clicked.connect(self.open_settings)
        settings_row_layout.addWidget(self.settings_btn)
        settings_row_layout.addStretch()
        sidebar_layout.addLayout(settings_row_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("background-color: #2f3e46; max-height: 1px; border: none;")
        sidebar_layout.addWidget(divider)

        # 1. Voice Settings
        voice_group = QVBoxLayout()
        voice_group.setSpacing(8)
        voice_label = QLabel("Select Hindi Voice", self)
        voice_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #85929E;")
        self.voice_combo = QComboBox(self)
        self.voice_combo.addItem("Female Voice (Swara style)")
        self.voice_combo.addItem("Male Voice (Madhur style)")
        voice_group.addWidget(voice_label)
        voice_group.addWidget(self.voice_combo)
        sidebar_layout.addLayout(voice_group)

        # 2. Voice Speed (Limited to ±30%)
        speed_group = QVBoxLayout()
        speed_group.setSpacing(8)
        speed_header_layout = QHBoxLayout()
        speed_label = QLabel("Speed of Speech", self)
        speed_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #85929E;")
        self.speed_value_label = QLabel("+0%", self)
        self.speed_value_label.setStyleSheet("font-weight: bold; color: #66fcf1;")
        speed_header_layout.addWidget(speed_label)
        speed_header_layout.addWidget(self.speed_value_label, 0, Qt.AlignRight)
        
        self.speed_slider = QSlider(Qt.Horizontal, self)
        self.speed_slider.setRange(-3, 3)
        self.speed_slider.setValue(0)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        
        speed_group.addLayout(speed_header_layout)
        speed_group.addWidget(self.speed_slider)
        sidebar_layout.addLayout(speed_group)

        # 3. Dictation Settings
        dictation_group = QVBoxLayout()
        dictation_group.setSpacing(8)
        dict_header_layout = QHBoxLayout()
        dict_label = QLabel("Dictation Interval", self)
        dict_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #85929E;")
        self.interval_value_label = QLabel("8 chars", self)
        self.interval_value_label.setStyleSheet("font-weight: bold; color: #66fcf1;")
        dict_header_layout.addWidget(dict_label)
        dict_header_layout.addWidget(self.interval_value_label, 0, Qt.AlignRight)
        
        self.interval_slider = QSlider(Qt.Horizontal, self)
        self.interval_slider.setRange(5, 14)
        self.interval_slider.setValue(8)
        self.interval_slider.setTickPosition(QSlider.TicksBelow)
        self.interval_slider.setTickInterval(1)
        self.interval_slider.valueChanged.connect(self.on_interval_changed)
        
        dictation_group.addLayout(dict_header_layout)
        dictation_group.addWidget(self.interval_slider)
        sidebar_layout.addLayout(dictation_group)

        # Dictation Optimization Buttons
        opt_buttons_layout = QVBoxLayout()
        opt_buttons_layout.setSpacing(8)
        
        self.opt1_btn = QPushButton("Optimize for Dictation 1 (Swara / Comma ,)", self)
        self.opt1_btn.setObjectName("dictation_1_btn")
        self.opt1_btn.clicked.connect(lambda: self.optimize_script(","))
        
        self.opt2_btn = QPushButton("Optimize for Dictation 2 (Madhur / Viram ।)", self)
        self.opt2_btn.setObjectName("dictation_2_btn")
        self.opt2_btn.clicked.connect(lambda: self.optimize_script("।"))
        
        opt_buttons_layout.addWidget(self.opt1_btn)
        opt_buttons_layout.addWidget(self.opt2_btn)
        sidebar_layout.addLayout(opt_buttons_layout)

        # ----------------------------------------------------------------------
        # SPACER PLACEMENT FOR SIDEBAR DYNAMIC GAP
        # ----------------------------------------------------------------------
        sidebar_layout.addStretch()

        # Divider 2
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.HLine)
        divider2.setFrameShadow(QFrame.Sunken)
        divider2.setStyleSheet("background-color: #2f3e46; max-height: 1px; border: none;")

        # Speech Generation Progress & Action (Anchored at the bottom)
        gen_layout = QVBoxLayout()
        gen_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Ready", self)
        self.status_label.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        
        self.generate_btn = QPushButton("Generate Speech", self)
        self.generate_btn.setObjectName("generate_btn")
        self.generate_btn.clicked.connect(self.on_generate_speech)
        
        gen_layout.addWidget(self.status_label)
        gen_layout.addWidget(self.progress_bar)
        gen_layout.addWidget(self.generate_btn)
        
        sidebar_layout.addWidget(divider2)
        sidebar_layout.addLayout(gen_layout)

        main_layout.addWidget(sidebar)

        # ----------------------------------------------------------------------
        # RIGHT CONTENT PANEL - ADJUSTABLE HEIGHT CARDS (QSplitter)
        # ----------------------------------------------------------------------
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)

        # 1. Editor Section Card
        editor_card = QFrame(self)
        editor_card.setObjectName("editor_card")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(15, 12, 15, 12)
        editor_layout.setSpacing(10)

        editor_header_layout = QHBoxLayout()
        editor_title = QLabel("Hindi Script Writing Editor", self)
        editor_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #85929E;")
        self.stats_label = QLabel("Chars: 0 | Words: 0", self)
        self.stats_label.setStyleSheet("font-size: 11px; color: #85929E;")
        editor_header_layout.addWidget(editor_title)
        editor_header_layout.addWidget(self.stats_label, 0, Qt.AlignRight)
        
        self.text_editor = QTextEdit(self)
        self.text_editor.setPlaceholderText("Paste or write your Hindi steno script here...")
        self.text_editor.textChanged.connect(self.on_text_changed)

        editor_layout.addLayout(editor_header_layout)
        editor_layout.addWidget(self.text_editor)

        # 2. Media Manager Card
        media_card = QFrame(self)
        media_card.setObjectName("media_card")
        media_layout = QVBoxLayout(media_card)
        media_layout.setContentsMargins(15, 12, 15, 12)
        media_layout.setSpacing(10)

        media_header_layout = QHBoxLayout()
        media_title = QLabel("Media Manager (Optional YouTube MP4 export)", self)
        media_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #85929E;")
        media_header_layout.addWidget(media_title)
        media_layout.addLayout(media_header_layout)

        # Import options rows
        import_row_layout = QHBoxLayout()
        import_row_layout.setSpacing(8)

        self.import_images_btn = QPushButton("Import Images", self)
        self.import_images_btn.clicked.connect(self.import_images)

        self.import_pre_btn = QPushButton("Import Pre-Roll (Intro)", self)
        self.import_pre_btn.clicked.connect(lambda: self.import_roll_media(True))

        self.import_post_btn = QPushButton("Import Post-Roll (Outro)", self)
        self.import_post_btn.clicked.connect(lambda: self.import_roll_media(False))

        self.clear_media_btn = QPushButton("Clear Media", self)
        self.clear_media_btn.clicked.connect(self.clear_all_media)

        import_row_layout.addWidget(self.import_images_btn)
        import_row_layout.addWidget(self.import_pre_btn)
        import_row_layout.addWidget(self.import_post_btn)
        import_row_layout.addWidget(self.clear_media_btn)
        media_layout.addLayout(import_row_layout)

        # Media status lists
        self.media_info_list = QListWidget(self)
        self.media_info_list.setFixedHeight(75)
        self.media_info_list.addItem(QListWidgetItem("No media files loaded."))
        media_layout.addWidget(self.media_info_list)

        # Compile and export video action
        video_action_layout = QHBoxLayout()
        self.video_status_label = QLabel("Generate speech to unlock video exporting.", self)
        self.video_status_label.setStyleSheet("font-size: 11px; color: #85929E;")
        
        self.export_video_btn = QPushButton("Export MP4 Video (16:9)", self)
        self.export_video_btn.setObjectName("generate_btn")
        self.export_video_btn.setEnabled(False)
        self.export_video_btn.clicked.connect(self.on_export_video)

        video_action_layout.addWidget(self.video_status_label)
        video_action_layout.addStretch()
        video_action_layout.addWidget(self.export_video_btn)
        media_layout.addLayout(video_action_layout)

        # 3. Audio Player Controls Card
        self.player_card = QFrame(self)
        self.player_card.setObjectName("player_card")
        player_layout = QVBoxLayout(self.player_card)
        player_layout.setContentsMargins(15, 12, 15, 12)
        player_layout.setSpacing(8)

        # Seek timeline slider
        seek_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00", self)
        self.time_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #66fcf1;")
        
        self.seek_slider = QSlider(Qt.Horizontal, self)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self.on_seek_moved)
        
        seek_layout.addWidget(self.seek_slider)
        seek_layout.addWidget(self.time_label)
        player_layout.addLayout(seek_layout)

        # Player Play / Pause / Save Actions row
        control_actions_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("Play", self)
        self.play_btn.setMinimumWidth(80)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.play_audio)
        
        self.pause_btn = QPushButton("Pause", self)
        self.pause_btn.setMinimumWidth(80)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_audio)
        
        self.stop_btn = QPushButton("Stop", self)
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_audio)

        # Volume slider
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(5)
        volume_icon = QLabel("Vol", self)
        volume_icon.setStyleSheet("font-size: 11px; color: #85929E;")
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.audio_output.setVolume(0.8)
        
        volume_layout.addWidget(volume_icon)
        volume_layout.addWidget(self.volume_slider)

        self.save_btn = QPushButton("Save Audio File", self)
        self.save_btn.setObjectName("save_audio_btn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_audio_as)

        control_actions_layout.addWidget(self.play_btn)
        control_actions_layout.addWidget(self.pause_btn)
        control_actions_layout.addWidget(self.stop_btn)
        control_actions_layout.addLayout(volume_layout)
        control_actions_layout.addStretch()
        control_actions_layout.addWidget(self.save_btn)
        player_layout.addLayout(control_actions_layout)

        # QSplitter to allow dynamic vertical card resizing
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(editor_card)
        right_splitter.addWidget(media_card)
        right_splitter.addWidget(self.player_card)
        right_splitter.setStyleSheet("QSplitter::handle { background-color: #2f3e46; height: 3px; }")
        
        right_panel.addWidget(right_splitter)
        main_layout.addLayout(right_panel)

        # Media Player Signals
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)

    # ==============================================================================
    # SETTINGS CONFIGURATION DIALOG
    # ==============================================================================

    def open_settings(self):
        from PySide6.QtWidgets import QDialog, QLineEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Application Settings")
        dialog.setMinimumSize(450, 180)
        dialog.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QLabel("Settings & Customizations", dialog)
        title.setStyleSheet("font-weight: 800; font-size: 15px; color: #66fcf1; letter-spacing: 0.5px;")
        layout.addWidget(title)
        
        desc = QLabel("Set your default save location for generated audios and compiled videos.", dialog)
        desc.setStyleSheet("color: #85929E; font-size: 12px;")
        layout.addWidget(desc)
        
        path_layout = QHBoxLayout()
        path_label = QLabel("Save Location:", dialog)
        path_label.setStyleSheet("font-weight: bold; color: #c5c6c7;")
        
        current_dir = load_save_directory()
        path_input = QLineEdit(current_dir, dialog)
        path_input.setReadOnly(True)
        path_input.setStyleSheet("background-color: #0b0c10; border: 1px solid #2f3e46; padding: 5px; color: #ffffff; font-family: monospace;")
        
        def browse_folder():
            selected = QFileDialog.getExistingDirectory(dialog, "Select Save Location", path_input.text())
            if selected:
                path_input.setText(selected)
                
        browse_btn = QPushButton("Browse...", dialog)
        browse_btn.clicked.connect(browse_folder)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings", dialog)
        save_btn.setObjectName("generate_btn")
        
        def save_and_close():
            new_dir = path_input.text().strip()
            if os.path.exists(new_dir):
                if save_save_directory(new_dir):
                    QMessageBox.information(dialog, "Success", "Default save location updated successfully!")
                    dialog.accept()
                else:
                    QMessageBox.critical(dialog, "Error", "Failed to save settings file.")
            else:
                QMessageBox.warning(dialog, "Invalid Directory", "The selected directory does not exist.")
                
        save_btn.clicked.connect(save_and_close)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()

    # ==============================================================================
    # HANDLERS & SLOTS
    # ==============================================================================

    @Slot(int)
    def on_speed_changed(self, value):
        self.speed_value_label.setText(f"{value * 10:+d}%")

    @Slot(int)
    def on_interval_changed(self, value):
        self.interval_value_label.setText(f"{value} chars")
        if self.current_optimization:
            self.optimize_script(self.current_optimization)

    def on_text_changed(self):
        text = self.text_editor.toPlainText()
        char_count = len(text)
        words = len(re.findall(r"\b\w+\b", text))
        self.stats_label.setText(f"Chars: {char_count} | Words: {words}")

    def optimize_script(self, punc):
        self.current_optimization = punc
        self.is_optimizing = True
        
        current_text = self.text_editor.toPlainText()
        if not current_text.strip():
            self.is_optimizing = False
            return
            
        # Strip out both commas and virams to ensure a clean slate
        cleaned_text = current_text.replace(",", "").replace("।", "")
        
        # Save cursor position so editing doesn't jump
        cursor = self.text_editor.textCursor()
        old_pos = cursor.position()
        
        N = self.interval_slider.value()
        optimized = optimize_text(cleaned_text, punc, N)
        
        self.text_editor.setPlainText(optimized)
        
        # Restore cursor position
        new_cursor = self.text_editor.textCursor()
        new_cursor.setPosition(min(old_pos, len(optimized)))
        self.text_editor.setTextCursor(new_cursor)
        
        self.is_optimizing = False

    def auto_save_audio(self, temp_path):
        """Saves generated speech to the configured save folder sequentially."""
        try:
            save_dir = load_save_directory()
            counter = get_next_counter()
            filename = f"vishal_steno{counter}.mp3"
            dst_path = os.path.join(save_dir, filename)
                
            shutil.copy(temp_path, dst_path)
            increment_counter()
            return dst_path, filename
        except Exception as e:
            print(f"Auto-save failed: {e}")
            return None, ""

    def on_generate_speech(self):
        text = self.text_editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Script", "Please write or paste your script in the editor first.")
            return

        self.generate_btn.setEnabled(False)
        self.export_video_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Status: Starting speech rendering...")
        self.status_label.setStyleSheet("color: #c5c6c7;")

        voice = self.voice_combo.currentText()
        speed_pct = self.speed_slider.value() * 10
        
        temp_dir = tempfile.gettempdir()
        self.generated_file = os.path.join(temp_dir, "vishal_steno_tts_output.mp3")

        self.worker = RenderWorker(text, voice, speed_pct, self.generated_file, use_local_engine=False)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    @Slot(str)
    def on_worker_progress(self, msg):
        self.status_label.setText(f"Status: {msg}")

    @Slot(str)
    def on_worker_finished(self, out_path):
        saved_path, filename = self.auto_save_audio(out_path)
        
        if saved_path:
            self.status_label.setText(f"Status: Success! Saved to configured directory as '{filename}'")
            self.status_label.setStyleSheet("color: #10b981;")
        else:
            self.status_label.setText("Status: Speech generated successfully.")
            
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)

        self.media_player.setSource(QUrl.fromLocalFile(out_path))
        self.play_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        
        self.export_video_btn.setEnabled(True)
        self.video_status_label.setText("Speech file generated. Ready to export MP4 Video!")
        self.video_status_label.setStyleSheet("color: #66fcf1;")

    @Slot(str)
    def on_worker_error(self, err_msg):
        self.status_label.setText("Status: Generation failed.")
        self.status_label.setStyleSheet("color: #ef4444;")
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        
        if "connect" in err_msg.lower() or "network" in err_msg.lower() or "websockets" in err_msg.lower():
            QMessageBox.critical(
                self, "Network Error", 
                "Connection failed! Premium neural voices require an active internet connection.\n"
                "Please connect your PC to the internet and try again."
            )
        else:
            QMessageBox.critical(
                self, "Speech Synthesis Error", 
                f"Speech synthesis failed:\n{err_msg}"
            )

    # ----------------------------------------------------------------------
    # MEDIA IMPORT HANDLERS
    # ----------------------------------------------------------------------

    def update_media_list(self):
        self.media_info_list.clear()
        
        has_media = False
        if self.imported_images:
            has_media = True
            self.media_info_list.addItem(f"📷 Slideshow Images: {len(self.imported_images)} loaded")
        if self.pre_roll_media:
            has_media = True
            name = os.path.basename(self.pre_roll_media)
            self.media_info_list.addItem(f"◀️ Pre-roll (Intro): {name}")
        if self.post_roll_media:
            has_media = True
            name = os.path.basename(self.post_roll_media)
            self.media_info_list.addItem(f"▶️ Post-roll (Outro): {name}")
            
        if not has_media:
            self.media_info_list.addItem("No media files loaded.")

    def import_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Slideshow Images", "", "Image Files (*.png *.jpg *.jpeg);;All Files (*)"
        )
        if files:
            self.imported_images = files
            self.update_media_list()

    def import_roll_media(self, is_pre_roll):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Pre/Post Media", "", "Media Files (*.mp3 *.wav *.mp4 *.avi *.mov);;All Files (*)"
        )
        if file_path:
            if is_pre_roll:
                self.pre_roll_media = file_path
            else:
                self.post_roll_media = file_path
            self.update_media_list()

    def clear_all_media(self):
        self.imported_images = []
        self.pre_roll_media = None
        self.post_roll_media = None
        self.update_media_list()

    def on_export_video(self):
        if not self.generated_file or not os.path.exists(self.generated_file):
            return
            
        save_dir = load_save_directory()
        counter = get_next_counter()
        default_video_name = f"vishal_steno{counter}.mp4"
        default_path = os.path.join(save_dir, default_video_name)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export MP4 Video", default_path, "Video Files (*.mp4);;All Files (*)"
        )
        if not file_path:
            return

        self.export_video_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Status: Starting video compilation...")
        self.status_label.setStyleSheet("color: #c5c6c7;")

        self.video_worker = VideoRenderWorker(
            self.generated_file, self.imported_images, 
            self.pre_roll_media, self.post_roll_media, file_path
        )
        self.video_worker.progress.connect(self.on_worker_progress)
        self.video_worker.finished.connect(self.on_video_finished)
        self.video_worker.error.connect(self.on_video_error)
        self.video_worker.start()

    @Slot(str)
    def on_video_finished(self, out_path):
        self.status_label.setText("Status: Video compiled successfully!")
        self.status_label.setStyleSheet("color: #10b981;")
        self.progress_bar.setVisible(False)
        self.export_video_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        increment_counter()
        QMessageBox.information(self, "Success", "Video (.mp4) exported successfully!")

    @Slot(str)
    def on_video_error(self, err_msg):
        self.status_label.setText("Status: Video compilation failed.")
        self.status_label.setStyleSheet("color: #ef4444;")
        self.progress_bar.setVisible(False)
        self.export_video_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Video Render Error", f"Video export failed:\n{err_msg}")

    # ----------------------------------------------------------------------
    # PLAYER SLOTS
    # ----------------------------------------------------------------------

    def play_audio(self):
        self.media_player.play()
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

    def pause_audio(self):
        self.media_player.pause()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

    def stop_audio(self):
        self.media_player.stop()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

    def on_seek_moved(self, pos):
        self.media_player.setPosition(pos)

    def on_volume_changed(self, val):
        self.audio_output.setVolume(val / 100.0)

    def on_position_changed(self, position):
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(position)
        self.seek_slider.blockSignals(False)
        self.time_label.setText(f"{self.format_time(position)} / {self.format_time(self.media_player.duration())}")

    def on_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.time_label.setText(f"{self.format_time(self.media_player.position())} / {self.format_time(duration)}")

    def format_time(self, ms):
        seconds = int(ms / 1000)
        minutes = int(seconds / 60)
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def save_audio_as(self):
        if not self.generated_file or not os.path.exists(self.generated_file):
            return
        
        save_dir = load_save_directory()
        counter = get_next_counter()
        default_audio_name = f"vishal_steno{counter}.mp3"
        default_path = os.path.join(save_dir, default_audio_name)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", default_path, "Audio Files (*.mp3);;All Files (*)"
        )
        if file_path:
            try:
                shutil.copy(self.generated_file, file_path)
                increment_counter()
                QMessageBox.information(self, "Success", "Audio file successfully saved!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save audio file:\n{e}")

# ==============================================================================
# ALGORITHM FOR PARSING AND INSERTING DICTATION PUNCTUATION
# ==============================================================================

def optimize_text(text, punc, N):
    escaped_punc = re.escape(punc)
    pattern = f"({escaped_punc})|(\\s+)|([.,!?;:।，、])|([^\\s.,!?;:।，、]+)"
    tokens = []
    
    for match in re.finditer(pattern, text):
        val = match.group(0)
        if match.group(1):
            tokens.append(('PUNC_TARGET', val))
        elif match.group(2):
            tokens.append(('SPACE', val))
        elif match.group(3):
            tokens.append(('PUNC_OTHER', val))
        else:
            tokens.append(('WORD', val))
            
    result = []
    char_count = 0
    
    for i, (tok_type, val) in enumerate(tokens):
        if tok_type == 'PUNC_TARGET':
            result.append(val)
            char_count = 0
        elif tok_type == 'SPACE':
            result.append(val)
            char_count += len(val)
        elif tok_type == 'PUNC_OTHER':
            result.append(val)
            char_count += len(val)
        elif tok_type == 'WORD':
            word_len = len(val)
            if char_count + word_len >= N:
                next_is_target = False
                for j in range(i + 1, len(tokens)):
                    next_tok_type, next_val = tokens[j]
                    if next_tok_type == 'SPACE':
                        continue
                    if next_tok_type == 'PUNC_TARGET':
                        next_is_target = True
                    break
                
                if next_is_target:
                    result.append(val)
                    char_count += word_len
                else:
                    result.append(val + punc)
                    char_count = 0
            else:
                result.append(val)
                char_count += word_len
                
    return "".join(result)

def run_app():
    # Sync and update app_icon.png from GitHub locally on start!
    check_and_update_icon_locally()

    app = QApplication(sys.argv)
    
    # Check Product Key License before opening
    if not verify_license():
        from PySide6.QtWidgets import QDialog, QLineEdit
        
        dialog = QDialog()
        dialog.setWindowTitle("Software Activation Required - Vishal Steno")
        dialog.setMinimumSize(480, 240)
        dialog.setStyleSheet(DARK_STYLESHEET)
        dialog.setWindowFlags(Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint)
        
        # Load custom app icon for dialog
        icon_path = os.path.join(app_dir, "app_icon.png")
        if os.path.exists(icon_path):
            dialog.setWindowIcon(QIcon(icon_path))
            
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QLabel("Activate Vishal Steno Speech Studio", dialog)
        title.setStyleSheet("font-weight: 800; font-size: 15px; color: #66fcf1; letter-spacing: 0.5px;")
        layout.addWidget(title)
        
        desc = QLabel("This software is locked to a single PC. Please copy your Machine ID below and send it to the creator to generate your unique Product Key.", dialog)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #85929E; font-size: 12px; line-height: 16px;")
        layout.addWidget(desc)
        
        mid_layout = QHBoxLayout()
        mid_label = QLabel("Machine ID:", dialog)
        mid_label.setStyleSheet("font-weight: bold; color: #c5c6c7;")
        mid_val = QLineEdit(get_machine_uuid(), dialog)
        mid_val.setReadOnly(True)
        mid_val.setStyleSheet("background-color: #0b0c10; border: 1px solid #2f3e46; padding: 5px; color: #66fcf1; font-family: monospace;")
        
        copy_btn = QPushButton("Copy", dialog)
        copy_btn.setFixedWidth(60)
        def copy_mid():
            app.clipboard().setText(mid_val.text())
            copy_btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: copy_btn.setText("Copy"))
        copy_btn.clicked.connect(copy_mid)
        
        mid_layout.addWidget(mid_label)
        mid_layout.addWidget(mid_val)
        mid_layout.addWidget(copy_btn)
        layout.addLayout(mid_layout)
        
        key_layout = QHBoxLayout()
        key_label = QLabel("Product Key:", dialog)
        key_label.setStyleSheet("font-weight: bold; color: #c5c6c7;")
        key_input = QLineEdit(dialog)
        key_input.setPlaceholderText("VST-KEY-...")
        key_input.setStyleSheet("background-color: #0b0c10; border: 1px solid #2f3e46; padding: 6px; color: #ffffff;")
        
        key_layout.addWidget(key_label)
        key_layout.addWidget(key_input)
        layout.addLayout(key_layout)
        
        btn_layout = QHBoxLayout()
        activate_btn = QPushButton("Activate Software", dialog)
        activate_btn.setObjectName("generate_btn")
        
        def attempt_activation():
            entered_key = key_input.text().strip()
            mid = get_machine_uuid()
            if verify_license_key(mid, entered_key):
                try:
                    local_license_path = os.path.join(app_dir, "license.key")
                    with open(local_license_path, "w", encoding="utf-8") as f:
                        f.write(entered_key)
                    QMessageBox.information(dialog, "Activation Successful", "Software successfully activated! The application will now open.")
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Error", f"Error writing license key file:\n{e}")
            else:
                QMessageBox.critical(dialog, "Activation Failed", "Invalid Product Key! Please check and enter the correct key.")
                
        activate_btn.clicked.connect(attempt_activation)
        btn_layout.addStretch()
        btn_layout.addWidget(activate_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.Accepted:
            sys.exit(0)
            
    # Load Main Application Window
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
