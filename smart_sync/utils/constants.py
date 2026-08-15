from __future__ import annotations
import os
from pathlib import Path

APP_NAME = "Smart File Sync"
APP_VERSION = "3.0.0"
APP_ID = "SmartFileSync.Pro.v3.0"

# Assets
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PACKAGE_ROOT, "assets")
LOGO_PNG_PATH = os.path.join(ASSETS_DIR, "logo.png")
APP_ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")

# Application Directories & Files
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SmartFileSync")
os.makedirs(APPDATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")
HISTORY_FILE = os.path.join(APPDATA_DIR, "sync_history.json")
CACHE_FILE = os.path.join(APPDATA_DIR, "metadata_cache.json")
LOG_FILE = os.path.join(APPDATA_DIR, "smart_sync_activity.log")

# Hashing & I/O
MD5_CHUNK_SIZE = 1024 * 1024 # 1MB Streaming Buffer
DEFAULT_THREADS = 4
MAX_THREADS = 16

# File Filters Configuration
FILE_FILTERS = {
    "All Files": [],
    "Documents (*.pdf, *.docx, *.txt, *.xlsx, *.pptx)": [
        ".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".rtf", ".csv", ".md"
    ],
    "Images & Graphics (*.png, *.jpg, *.jpeg, *.svg, *.webp)": [
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".raw", ".psd", ".ai"
    ],
    "Audio & Music (*.mp3, *.wav, *.flac, *.aac, *.m4a)": [
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".mid"
    ],
    "Video & Media (*.mp4, *.mkv, *.avi, *.mov, *.webm)": [
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"
    ],
    "Archives & Zips (*.zip, *.rar, *.7z, *.tar, *.gz)": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab"
    ],
    "Code & Development (*.py, *.js, *.ts, *.html, *.css, *.json)": [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss", ".json", ".xml", ".yaml", ".yml",
        ".cpp", ".c", ".h", ".hpp", ".cs", ".java", ".go", ".rs", ".php", ".rb", ".sql", ".sh", ".bat", ".ps1"
    ]
}

# System Default Ignore Lists
DEFAULT_EXCLUSIONS = [
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".ds_store", "thumbs.db", "desktop.ini", "$recycle.bin",
    "system volume information"
]

from .log_manager import rotate_log_file
rotate_log_file(LOG_FILE)
