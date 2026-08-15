"""
Smart File Sync App v3.0 — Premium Edition
===========================================
A complete modern UI/UX redesign of the sync application matching premium design patterns
(Notion, Linear, Raycast, Fluent Design style).

Features:
  - Permanent Left Sidebar Navigation
  - Step-based Guided Workflow
  - Dashboard Page with Stat Cards & Recommendations
  - Folder Setup Page with Drag & Drop & Async Metadata Scanner
  - Scan Results comparison table with badges & custom sorting & context menu
  - Live Sync Queue tracker separating Pending, Processing, Completed, Failed
  - History log list and preset triggers
  - Multi-category Settings page (General, Performance, File Rules, Advanced)
  - Sleek Fluent theme stylesheet matching spacing grid (8px-32px)
"""

import sys, os, shutil, json, time, csv, threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit,
    QProgressBar, QComboBox, QCheckBox, QTabWidget, QFrame,
    QMessageBox, QStatusBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QSystemTrayIcon, QMenu, QDialog, QDialogButtonBox,
    QSizePolicy, QScrollArea, QSplitter, QStackedWidget, QButtonGroup,
    QSlider, QGridLayout, QTableView, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer, QSize, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QRectF
from PySide6.QtGui import QFont, QColor, QIcon, QTextCursor, QAction, QPalette, QLinearGradient, QPainter, QBrush, QPen

# ───────────────────────────────────────────────
# CONSTANTS & CONFIG
# ───────────────────────────────────────────────
APP_NAME = "Smart File Sync"
APP_VER  = "3.0"
LOG_FILE = os.path.join(os.path.expanduser("~"), "smart_sync_log.json")
MD5_CHUNK_SIZE = 1024 * 1024  # Fast 1 MB streaming buffer

FILE_FILTERS = {
    "All Files"  : [],
    "Photos"     : [".jpg",".jpeg",".png",".gif",".bmp",".webp",".heic",".raw",".tiff"],
    "Videos"     : [".mp4",".avi",".mkv",".mov",".wmv",".flv",".m4v",".3gp"],
    "Documents"  : [".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".csv",".odt",".ods",".rtf"],
    "Audio"      : [".mp3",".wav",".flac",".aac",".ogg",".m4a"],
}
DEFAULT_EXCLUDES = [".tmp", ".log", ".ds_store", "thumbs.db", ".lnk", ".ini", ".sys"]
LARGE_FILE_THRESH = 50 * 1024 * 1024  # 50 MB

# Semantic status colors
STATUS_COLORS_DARK = {
    "Missing"          : ("#10b981", "#ffffff"), # Emerald Green
    "Modified"         : ("#3b82f6", "#ffffff"), # Blue
    "Source Newer"     : ("#3b82f6", "#ffffff"), # Blue
    "Dest Newer"       : ("#8b5cf6", "#ffffff"), # Purple
    "Size Differs"     : ("#f59e0b", "#000000"), # Amber
    "Stat Error"       : ("#ef4444", "#ffffff"), # Coral Red
}
STATUS_COLORS_LIGHT = {
    "Missing"          : ("#d1fae5", "#065f46"),
    "Modified"         : ("#dbeafe", "#1e40af"),
    "Source Newer"     : ("#dbeafe", "#1e40af"),
    "Dest Newer"       : ("#ede9fe", "#5b21b6"),
    "Size Differs"     : ("#fef3c7", "#92400e"),
    "Stat Error"       : ("#fee2e2", "#991b1b"),
}

# ───────────────────────────────────────────────
# HELPERS & PLATFORM UTILS
# ───────────────────────────────────────────────
def ensure_extended_path(p):
    """Adds Windows \\?\\ extended path prefix for paths >= 240 chars to prevent MAX_PATH crash."""
    if sys.platform == "win32" and isinstance(p, str) and not p.startswith(("\\\\?\\", "\\\\.\\")):
        abs_p = os.path.abspath(p)
        if len(abs_p) >= 240:
            if abs_p.startswith("\\\\"):
                return "\\\\?\\UNC\\" + abs_p[2:]
            return "\\\\?\\" + abs_p
        return abs_p
    return p

def strip_extended_path(p):
    """Strips Windows \\?\\ extended path prefix for clean user-facing display."""
    if sys.platform == "win32" and isinstance(p, str):
        if p.startswith("\\\\?\\UNC\\"):
            return "\\\\" + p[8:]
        if p.startswith("\\\\?\\"):
            return p[4:]
    return p

def safe_chmod_write(filepath):
    """Clears Read-Only attribute on Windows/POSIX before file operations to prevent PermissionError."""
    try:
        if os.path.exists(ensure_extended_path(filepath)):
            import stat
            os.chmod(ensure_extended_path(filepath), stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass

def fast_scandir(dir_path, allowed_exts=None, excl_exts=None, stop_flag_callable=None):
    """
    High-performance, non-blocking directory scanner using os.scandir.
    Returns: (files_list, total_size, total_count, latest_mod_timestamp)
    Guards against symlink infinite loops and Windows MAX_PATH errors.
    """
    files = []
    total_size = 0
    total_count = 0
    latest_mod = 0.0

    ext_norm = [e.lower().lstrip("*") for e in (excl_exts or [])]
    allow_norm = [a.lower() for a in (allowed_exts or [])]

    clean_base = os.path.abspath(dir_path).rstrip("/\\")
    base_len = len(clean_base) + 1

    stack = [clean_base]
    visited_inodes = set()

    while stack:
        if stop_flag_callable and stop_flag_callable():
            break
        current_dir = stack.pop()
        try:
            with os.scandir(ensure_extended_path(current_dir)) as it:
                for entry in it:
                    if stop_flag_callable and stop_flag_callable():
                        break
                    name = entry.name
                    if name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stat_res = entry.stat(follow_symlinks=False)
                            inode = (getattr(stat_res, "st_ino", 0), getattr(stat_res, "st_dev", 0))
                            if inode != (0, 0):
                                if inode in visited_inodes:
                                    continue
                                visited_inodes.add(inode)
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            ext = Path(name).suffix.lower()
                            if ext_norm and ext in ext_norm:
                                continue
                            if allow_norm and ext not in allow_norm:
                                continue

                            stat_res = entry.stat(follow_symlinks=False)
                            sz = stat_res.st_size
                            mtime = stat_res.st_mtime
                            total_size += sz
                            total_count += 1
                            if mtime > latest_mod:
                                latest_mod = mtime

                            full_p = strip_extended_path(entry.path)
                            rel_p = full_p[base_len:] if len(full_p) > base_len else name
                            files.append((rel_p, full_p, sz, mtime))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    return files, total_size, total_count, latest_mod

def fmt_size(b):
    if b < 1024:    return f"{b} B"
    if b < 1<<20:   return f"{b/1024:.1f} KB"
    if b < 1<<30:   return f"{b/(1<<20):.1f} MB"
    return f"{b/(1<<30):.2f} GB"

def fmt_speed(bps):
    if bps < 1024:  return f"{bps:.0f} B/s"
    if bps < 1<<20: return f"{bps/1024:.1f} KB/s"
    return f"{bps/(1<<20):.1f} MB/s"

def fmt_eta(secs):
    if secs < 0 or secs > 86400: return "calculating..."
    h, r = divmod(int(secs), 3600)
    m, s = divmod(r, 60)
    if h:   return f"{h}h {m}m left"
    if m:   return f"{m}m {s}s left"
    return f"{s}s left"

def get_drives():
    drives = []
    try:
        import psutil
        for p in psutil.disk_partitions(all=False):
            drives.append(p.mountpoint)
    except Exception:
        if sys.platform == "win32":
            import string
            for L in string.ascii_uppercase:
                d = f"{L}:\\"
                if os.path.exists(d): drives.append(d)
        else:
            drives = ["/", os.path.expanduser("~")]
    return drives

# ───────────────────────────────────────────────
# CUSTOM WIDGETS
# ───────────────────────────────────────────────
class DropLineEdit(QLineEdit):
    """QLineEdit that accepts folder drag & drops with visual highlights"""
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet("border: 1px solid #3b82f6; background-color: #0b0f19;")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("")

    def dropEvent(self, e):
        self.setStyleSheet("")
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.setText(path)
                self.editingFinished.emit()

class SizeWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically by size"""
    def __init__(self, size_str, size_bytes):
        super().__init__(size_str)
        self.size_bytes = size_bytes

    def __lt__(self, other):
        if isinstance(other, SizeWidgetItem):
            return self.size_bytes < other.size_bytes
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)

class StatCard(QFrame):
    """Premium vertically-stacked dashboard statistics card"""
    def __init__(self, label, value="—", accent="#3b82f6", parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(4)

        self._val_lbl = QLabel(str(value))
        self._val_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self._val_lbl.setAlignment(Qt.AlignCenter)
        self._val_lbl.setStyleSheet(f"color: {accent}; line-height: 1.1;")

        self._txt_lbl = QLabel(label.upper())
        self._txt_lbl.setObjectName("stat_label")
        self._txt_lbl.setAlignment(Qt.AlignCenter)
        self._txt_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))

        lay.addWidget(self._val_lbl)
        lay.addWidget(self._txt_lbl)
        self.setMinimumHeight(68)

    def set_value(self, v, accent=None):
        self._val_lbl.setText(str(v))
        if accent:
            self._val_lbl.setStyleSheet(f"color: {accent}; line-height: 1.1;")

class FolderMetaCard(QFrame):
    """Styled dashboard card representing a folder with live stats"""
    def __init__(self, title, placeholder_path, browse_slot, parent=None):
        super().__init__(parent)
        self.setObjectName("folder_card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Header Title
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(6)
        
        folder_icon = QLabel(IconManager.get("folder"))
        folder_icon.setFont(IconManager.get_font(12))
        folder_icon.setStyleSheet("background: transparent;")
        
        hdr = QLabel(title.upper())
        hdr.setObjectName("card_header")
        hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        hdr.setStyleSheet("background: transparent;")
        
        hdr_row.addWidget(folder_icon)
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        lay.addLayout(hdr_row)

        # Input Row
        inp_row = QHBoxLayout()
        inp_row.setSpacing(8)
        self.input = DropLineEdit(placeholder_path)
        self.input.setObjectName("path_input")
        self.input.setFixedHeight(34)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("browse_btn")
        self.browse_btn.setFixedHeight(34)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(browse_slot)

        inp_row.addWidget(self.input, 1)
        inp_row.addWidget(self.browse_btn)
        lay.addLayout(inp_row)

        # Stats Area
        stats_frame = QFrame()
        stats_frame.setObjectName("folder_stats_frame")
        sf_lay = QGridLayout(stats_frame)
        sf_lay.setContentsMargins(16, 12, 16, 12)
        sf_lay.setSpacing(10)

        lbl_size_title = QLabel("Total Size")
        lbl_size_title.setObjectName("stat_label_dim")
        lbl_size_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_size = QLabel("—")
        self.lbl_size.setObjectName("stat_value_aligned")
        self.lbl_size.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lbl_files_title = QLabel("File Count")
        lbl_files_title.setObjectName("stat_label_dim")
        lbl_files_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_files = QLabel("—")
        self.lbl_files.setObjectName("stat_value_aligned")
        self.lbl_files.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_files.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lbl_mod_title = QLabel("Last Modified")
        lbl_mod_title.setObjectName("stat_label_dim")
        lbl_mod_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_modified = QLabel("—")
        self.lbl_modified.setObjectName("stat_value_aligned")
        self.lbl_modified.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_modified.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        sf_lay.addWidget(lbl_size_title, 0, 0)
        sf_lay.addWidget(self.lbl_size, 0, 1)
        sf_lay.addWidget(lbl_files_title, 1, 0)
        sf_lay.addWidget(self.lbl_files, 1, 1)
        sf_lay.addWidget(lbl_mod_title, 2, 0)
        sf_lay.addWidget(self.lbl_modified, 2, 1)
        sf_lay.setColumnStretch(0, 1)
        sf_lay.setColumnStretch(1, 2)

        lay.addWidget(stats_frame)

    def update_stats(self, size, count, mod_str):
        self.lbl_size.setText(fmt_size(size))
        self.lbl_files.setText(f"{count} files")
        self.lbl_modified.setText(mod_str)

    def reset_stats(self, calculating=False):
        txt = "Calculating..." if calculating else "—"
        self.lbl_size.setText(txt)
        self.lbl_files.setText(txt)
        self.lbl_modified.setText(txt)

class IconManager:
    FONT_FAMILY = "Segoe UI"
    HAS_MDL2 = False
    MAP = {}

    @classmethod
    def init(cls):
        from PySide6.QtGui import QFontDatabase
        db = QFontDatabase()
        families = db.families()
        if "Segoe MDL2 Assets" in families:
            cls.FONT_FAMILY = "Segoe MDL2 Assets"
            cls.HAS_MDL2 = True
            cls.MAP = {
                "dashboard": "\uE80F",
                "folder": "\uE8B7",
                "scan": "\uE946",
                "queue": "\uE91C",
                "history": "\uE81C",
                "settings": "\uE713",
                "refresh": "\uE72C",
                "info": "\uE946",
                "warning": "\uE7BA",
                "error": "\uEA39",
                "success": "\uE930",
                "arrow_left": "◀",
                "arrow_right": "▶",
                "step_done": "\uE930",
                "step_todo": "\uEA3A",
                "bell": "\uEA8F",
                "sun": "\uE706",
                "moon": "\uE708"
            }
        else:
            cls.FONT_FAMILY = "Segoe UI"
            cls.HAS_MDL2 = False
            cls.MAP = {
                "dashboard": "📊",
                "folder": "📂",
                "scan": "🔍",
                "queue": "📋",
                "history": "📜",
                "settings": "⚙️",
                "refresh": "🔄",
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "success": "✅",
                "arrow_left": "◀",
                "arrow_right": "▶",
                "step_done": "✓",
                "step_todo": "○",
                "bell": "🔔",
                "sun": "☀️",
                "moon": "🌙"
            }

    @classmethod
    def get(cls, name):
        return cls.MAP.get(name, "")

    @classmethod
    def get_font(cls, size=10, bold=False):
        return QFont(cls.FONT_FAMILY, size, QFont.Bold if bold else QFont.Normal)

class EmptyStateWidget(QFrame):
    """Clean Fluent empty state message with custom title, details, and action guidance"""
    def __init__(self, icon_name, title, details, btn_text=None, btn_callback=None, parent=None):
        super().__init__(parent)
        self.setObjectName("empty_state_panel")
        self.setStyleSheet("background: transparent; border: none;")
        
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)
        
        lbl_icon = QLabel(IconManager.get(icon_name))
        lbl_icon.setFont(IconManager.get_font(36))
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent;")
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("empty_title")
        lbl_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("background: transparent;")
        
        lbl_details = QLabel(details)
        lbl_details.setObjectName("empty_details")
        lbl_details.setFont(QFont("Segoe UI", 10))
        lbl_details.setAlignment(Qt.AlignCenter)
        lbl_details.setStyleSheet("background: transparent; color: #94a3b8;")
        lbl_details.setWordWrap(True)
        lbl_details.setMaximumWidth(450)
        
        lay.addWidget(lbl_icon)
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_details)

        if btn_text and btn_callback:
            self.action_btn = QPushButton(btn_text)
            self.action_btn.setObjectName("btn_scan")
            self.action_btn.setFixedHeight(34)
            self.action_btn.setMinimumWidth(160)
            self.action_btn.setCursor(Qt.PointingHandCursor)
            self.action_btn.clicked.connect(btn_callback)
            lay.addWidget(self.action_btn, 0, Qt.AlignCenter)

class NavItemWidget(QPushButton):
    """Custom navigation item with shortcuts and status badges"""
    def __init__(self, icon_name, text, index, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_btn")
        self.setCheckable(True)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        
        self.icon_name = icon_name
        self.text = text
        self.index = index
        self.badge_count = 0
        self.is_collapsed = False
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)
        
        self.lbl_icon = QLabel(IconManager.get(icon_name))
        self.lbl_icon.setObjectName("nav_icon")
        self.lbl_icon.setFont(IconManager.get_font(11))
        self.lbl_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lbl_icon.setFixedWidth(20)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        
        self.lbl_text = QLabel(text)
        self.lbl_text.setObjectName("nav_lbl")
        self.lbl_text.setFont(QFont("Segoe UI", 10))
        self.lbl_text.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.lbl_badge = QLabel("")
        self.lbl_badge.setObjectName("nav_badge")
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self.lbl_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lbl_badge.setVisible(False)
        
        self.lbl_shortcut = QLabel(f"Ctrl+{index+1}")
        self.lbl_shortcut.setObjectName("nav_shortcut")
        self.lbl_shortcut.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lbl_shortcut.setFont(QFont("Segoe UI", 8))
        
        lay.addWidget(self.lbl_icon)
        lay.addWidget(self.lbl_text, 1)
        lay.addWidget(self.lbl_badge)
        lay.addWidget(self.lbl_shortcut)

    def set_badge(self, count):
        self.badge_count = count
        if count > 0 and not self.is_collapsed:
            self.lbl_badge.setText(str(count))
            self.lbl_badge.setVisible(True)
        else:
            self.lbl_badge.setVisible(False)

    def set_collapsed(self, collapsed):
        self.is_collapsed = collapsed
        if collapsed:
            self.lbl_text.setVisible(False)
            self.lbl_shortcut.setVisible(False)
            self.lbl_badge.setVisible(False)
            self.layout().setContentsMargins(0, 0, 0, 0)
            self.lbl_icon.setFixedWidth(64)
            self.setToolTip(f"{self.text} (Ctrl+{self.index+1})")
        else:
            self.lbl_text.setVisible(True)
            self.lbl_shortcut.setVisible(True)
            self.lbl_badge.setVisible(self.badge_count > 0)
            if self.badge_count > 0:
                self.lbl_badge.setText(str(self.badge_count))
            self.layout().setContentsMargins(16, 0, 16, 0)
            self.lbl_icon.setFixedWidth(20)
            self.setToolTip("")

# ───────────────────────────────────────────────
# MODEL/VIEW DESIGN FOR SCAN RESULTS TABLE
# ───────────────────────────────────────────────
# ───────────────────────────────────────────────
# MODEL/VIEW DESIGN FOR SCAN RESULTS TABLE
# ───────────────────────────────────────────────
class ScanResultsModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._app_win = parent
        self.files = []
        self.checked_rows = set()

    def set_files(self, files):
        self.beginResetModel()
        self.files = files
        self.checked_rows = set(range(len(files)))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.files)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.files)):
            return None
            
        row = index.row()
        col = index.column()
        fi = self.files[row]
        
        dark = self._app_win.dark_mode if self._app_win else True
        
        if role == Qt.DisplayRole:
            if col == 1:
                ext = fi.get("type", "")
                icon = "📄"
                if ext in FILE_FILTERS["Photos"]: icon = "🖼️"
                elif ext in FILE_FILTERS["Videos"]: icon = "🎥"
                elif ext in FILE_FILTERS["Audio"]: icon = "🎵"
                elif ext == ".pdf": icon = "📕"
                elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]: icon = "📦"
                elif ext in [".txt", ".csv", ".json", ".xml", ".ini", ".log"]: icon = "📝"
                elif ext in [".exe", ".msi", ".bat", ".cmd", ".sh", ".py"]: icon = "⚙️"
                return f" {icon}  {Path(fi['rel_path']).name}"
            elif col == 2:
                return fi["size_str"]
            elif col == 3:
                return fi["modified"]
            elif col == 4:
                return f" {fi['reason']} "
                
        elif role == Qt.CheckStateRole:
            if col == 0:
                return Qt.Checked if row in self.checked_rows else Qt.Unchecked
                
        elif role == Qt.ToolTipRole:
            if col in (0, 1):
                folder_hint = fi["folder"] if fi["folder"] != "." else ""
                return f"{fi['rel_path']}\n📁 {folder_hint}" if folder_hint else fi["rel_path"]
            elif col == 4:
                return f"Sync Status: {fi['reason']}"
                
        elif role == Qt.TextAlignmentRole:
            if col == 2: return Qt.AlignRight | Qt.AlignVCenter
            elif col in (3, 4): return Qt.AlignCenter
            
        elif role == Qt.BackgroundRole:
            if col == 4:
                reason_map = STATUS_COLORS_DARK if dark else STATUS_COLORS_LIGHT
                bg, _ = reason_map.get(fi["reason"], ("#475569", "#cbd5e1"))
                return QColor(bg)
                
        elif role == Qt.ForegroundRole:
            if col == 4:
                reason_map = STATUS_COLORS_DARK if dark else STATUS_COLORS_LIGHT
                _, fg = reason_map.get(fi["reason"], ("#f8fafc", "#1e293b"))
                return QColor(fg)
            elif col in (2, 3):
                return QColor("#94a3b8") if dark else QColor("#64748b")
            else:
                return QColor("#f8fafc") if dark else QColor("#1e293b")
                
        elif role == Qt.UserRole:
            return fi
            
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            row = index.row()
            if value == Qt.Checked:
                self.checked_rows.add(row)
            else:
                self.checked_rows.discard(row)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        if index.column() == 0:
            return Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = ["", "File Name", "Size", "Modified", "Status"]
            if section < len(headers):
                return headers[section]
        return None

class ScanResultsProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.reason_filter = "All Reasons"

    def set_filters(self, search_text, reason_filter):
        self.search_text = search_text.strip().lower()
        self.reason_filter = reason_filter
        self.invalidate()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model or source_row >= len(model.files):
            return False
            
        fi = model.files[source_row]
        if self.search_text and self.search_text not in fi["rel_path"].lower():
            return False
        if self.reason_filter != "All Reasons" and self.reason_filter.lower() != fi["reason"].lower():
            return False
        return True

    def lessThan(self, left, right):
        model = self.sourceModel()
        left_fi = model.files[left.row()]
        right_fi = model.files[right.row()]
        col = left.column()
        
        if col == 0:
            left_checked = left.row() in model.checked_rows
            right_checked = right.row() in model.checked_rows
            return left_checked < right_checked
        elif col == 2:
            return left_fi["size"] < right_fi["size"]
        elif col == 3:
            return left_fi["modified"] < right_fi["modified"]
            
        left_data = model.data(left, Qt.DisplayRole)
        right_data = model.data(right, Qt.DisplayRole)
        if left_data is None: return True
        if right_data is None: return False
        return str(left_data) < str(right_data)

class BadgeDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        fi = index.data(Qt.UserRole)
        if not fi:
            super().paint(painter, option, index)
            return

        reason = fi.get("reason", "Missing")
        display_map = {
            "Missing": "Missing",
            "Modified": "Changed",
            "Source Newer": "Updated",
            "Dest Newer": "Conflict",
            "Size Differs": "Conflict",
            "Stat Error": "Error"
        }
        display_text = display_map.get(reason, reason)

        dark = True
        try:
            dark = option.widget.window().dark_mode
        except Exception:
            pass

        reason_map = STATUS_COLORS_DARK if dark else STATUS_COLORS_LIGHT
        bg, fg = reason_map.get(reason, ("#475569", "#cbd5e1"))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        rect = option.rect
        margin_h = 10
        margin_v = 6
        badge_w = rect.width() - (margin_h * 2)
        badge_h = rect.height() - (margin_v * 2)
        
        badge_rect = QRectF(
            rect.x() + margin_h,
            rect.y() + margin_v,
            badge_w,
            badge_h
        )

        painter.setBrush(QBrush(QColor(bg)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(QPen(QColor(fg)))
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignCenter, display_text)

        painter.restore()

# ───────────────────────────────────────────────
# ASYNC METADATA SCANNER THREAD
# ───────────────────────────────────────────────
class MetadataScanner(QThread):
    """QThread to calculate folder size, count, and last modified time asynchronously using fast_scandir"""
    done = Signal(str, str, float, int, str)  # folder_id, path, size (float), count, mod_str

    def __init__(self, folder_id, path):
        super().__init__()
        self.folder_id = folder_id
        self.path = path
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            if not self.path or not os.path.isdir(self.path):
                self.done.emit(self.folder_id, self.path, 0.0, 0, "N/A")
                return
            
            _, size, count, latest_mod = fast_scandir(
                self.path,
                stop_flag_callable=lambda: self._stopped
            )
            
            mod_str = datetime.fromtimestamp(latest_mod).strftime("%Y-%m-%d %H:%M") if latest_mod else "N/A"
            self.done.emit(self.folder_id, self.path, float(size), count, mod_str)
        except Exception:
            self.done.emit(self.folder_id, self.path, 0.0, 0, "Error")

# ───────────────────────────────────────────────
# WORKER SYNC THREAD
# ───────────────────────────────────────────────
class SyncWorker(QThread):
    progress_signal = Signal(int, str)  # pct, detail
    log_signal      = Signal(str, str)  # msg, kind
    scan_done       = Signal(list)
    sync_done       = Signal(dict)
    error_signal    = Signal(str)
    consec_fail_signal = Signal()
    
    # Reports status changes on specific files to sync queue page live: (rel_path, status, error_msg)
    file_status_changed = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self._pause_ev  = threading.Event()
        self._pause_ev.set()
        self._stop      = False
        self.mode       = "scan"
        self.source     = ""
        self.destination= ""
        self.file_filter= "All Files"
        self.dry_run    = False
        self.excl_exts  = []
        self.files_to_sync = []
        self.threads    = 3
        self.consec_errors = 0
        self.consec_lock = threading.Lock()

    def setup_scan(self, src, dest, filt, excl):
        self.mode = "scan"
        self.source = src
        self.destination = dest
        self.file_filter = filt
        self.excl_exts = excl
        self._stop = False
        self._pause_ev.set()

    def setup_sync(self, src, dest, files, dry, threads, safe_renames=True, md5_verify=False):
        self.mode = "sync"
        self.source = src
        self.destination = dest
        self.files_to_sync = files
        self.dry_run = dry
        self.threads = threads
        self.use_safe_renames = safe_renames
        self.use_md5_verify = md5_verify
        self._stop = False
        self._pause_ev.set()
        self.consec_errors = 0

    def pause(self):  self._pause_ev.clear()
    def resume(self): self._pause_ev.set()
    def stop(self):   self._stop = True; self._pause_ev.set()

    @property
    def is_paused(self): return not self._pause_ev.is_set()

    def run(self):
        try:
            if self.mode == "scan":   self._do_scan()
            elif self.mode == "sync": self._do_sync()
        except Exception as e:
            self.error_signal.emit(str(e))

    def _do_scan(self):
        self.log_signal.emit("🔍 Starting fast scan...", "info")
        clean_src = os.path.abspath(self.source)
        clean_dest = os.path.abspath(self.destination)
        if not os.path.isdir(clean_src):
            self.error_signal.emit(f"Source folder not found:\n{self.source}"); return
        if not os.path.isdir(clean_dest):
            self.error_signal.emit(f"Destination folder not found:\n{self.destination}"); return

        allowed = FILE_FILTERS.get(self.file_filter, [])
        excl    = [e.lower().lstrip("*") for e in self.excl_exts]

        src_files, total_src_size, total_src_count, _ = fast_scandir(
            clean_src, allowed_exts=allowed, excl_exts=excl,
            stop_flag_callable=lambda: self._stop
        )
        if self._stop: return
        total = len(src_files)
        self.log_signal.emit(f"📊 {total} files discovered in source", "info")

        missing = []
        for i, (rel, src_p, sz, mtime) in enumerate(src_files):
            if self._stop: break
            self._pause_ev.wait()

            dest_p = os.path.join(clean_dest, rel)
            self.progress_signal.emit(
                int((i+1)/max(total,1)*100), f"Comparing {i+1}/{total}"
            )

            needs_copy, reason = False, ""
            dest_ext_p = ensure_extended_path(dest_p)
            if not os.path.exists(dest_ext_p):
                needs_copy, reason = True, "Missing"
            else:
                try:
                    ds = os.stat(dest_ext_p)
                    if sz != ds.st_size:
                        needs_copy, reason = True, "Size Differs"
                    elif mtime > ds.st_mtime + 2:
                        needs_copy, reason = True, "Source Newer"
                    elif ds.st_mtime > mtime + 2:
                        needs_copy, reason = True, "Dest Newer"
                except OSError:
                    needs_copy, reason = True, "Stat Error"

            if needs_copy:
                missing.append({
                    "rel_path" : rel,
                    "src_path" : src_p,
                    "dest_path": dest_p,
                    "size"     : sz,
                    "size_str" : fmt_size(sz),
                    "modified" : datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "reason"   : reason,
                    "type"     : Path(rel).suffix.lower(),
                    "folder"   : str(Path(rel).parent),
                })

        self.progress_signal.emit(100, f"Scan complete — {len(missing)} items need sync")
        self.log_signal.emit(f"✅ Scan complete! {len(missing)} items require sync", "success")
        self.scan_done.emit(missing)

    def _do_sync(self):
        files = self.files_to_sync
        total = len(files)
        if not total:
            self.log_signal.emit("ℹ️ No files selected", "info"); return

        if not self.dry_run:
            dest_parent = os.path.dirname(os.path.abspath(self.destination))
            if not os.path.exists(dest_parent) and not os.path.exists(os.path.splitdrive(self.destination)[0] + "\\"):
                self.error_signal.emit(
                    f"Destination Drive Missing!\n\n"
                    f"The destination directory '{self.destination}' is not accessible.\n\n"
                    "Suggested fix:\n"
                    "1. Ensure the external drive or USB is plugged in.\n"
                    "2. Verify that the drive letter is correct.\n"
                    "3. If syncing to a network location, check your network connection."
                ); return
                
            needed = sum(f["size"] for f in files)
            try:
                free = shutil.disk_usage(self.destination).free
                if needed > free:
                    self.error_signal.emit(
                        f"Insufficient disk space!\n"
                        f"Required : {fmt_size(needed)}\n"
                        f"Available: {fmt_size(free)}"
                    ); return
            except Exception as e:
                self.log_signal.emit(f"⚠️ Space check skip: {e}", "warning")

        mode_txt = "DRY RUN" if self.dry_run else "SYNC"
        self.log_signal.emit(f"🚀 Starting {mode_txt} — {total} files", "info")

        small = [f for f in files if f["size"] <= LARGE_FILE_THRESH]
        large = [f for f in files if f["size"] >  LARGE_FILE_THRESH]

        c = {"copied":0,"skipped":0,"errors":0,"size":0}
        done = [0]
        t0   = time.time()

        def progress():
            pct  = int(done[0]/max(total,1)*100)
            elapsed = max(time.time()-t0, 0.001)
            spd  = c["size"]/elapsed
            eta  = (total-done[0])*(elapsed/max(done[0],1))
            self.progress_signal.emit(
                pct, f"{done[0]}/{total} files  ·  {fmt_speed(spd)}  ·  {fmt_eta(eta)}"
            )

        # Notify UI about all files being pending initially
        for f in files:
            self.file_status_changed.emit(f["rel_path"], "pending", "")

        # Small files — parallel execution
        if small and not self._stop:
            with ThreadPoolExecutor(max_workers=self.threads) as ex:
                fmap = {ex.submit(self._copy_one_wrapper, f): f for f in small}
                for fut in as_completed(fmap):
                    if self._stop:
                        ex.shutdown(wait=False, cancel_futures=True); break
                    self._pause_ev.wait()
                    fi  = fmap[fut]
                    res = fut.result() if not fut.cancelled() else "error"
                    self._tally(res, fi, c)
                    done[0] += 1; progress()

        # Large files — sequential execution
        for fi in large:
            if self._stop: break
            self._pause_ev.wait()
            res = self._copy_one_wrapper(fi)
            self._tally(res, fi, c)
            done[0] += 1; progress()

        self.progress_signal.emit(100, f"Done — {c['copied']} copied, {c['errors']} errors")
        elapsed = time.time() - t0
        dur_str = f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed)//60}m {int(elapsed)%60}s"
        status_val = "Error" if c["errors"] > 0 else "Success"
        summary = {
            "total":total,"copied":c["copied"],"skipped":c["skipped"],
            "errors":c["errors"],"copied_size":fmt_size(c["size"]),
            "dry_run":self.dry_run,"source":self.source,"destination":self.destination,
            "filter":self.file_filter,
            "duration": dur_str,
            "status": status_val
        }
        if not self.dry_run and c["copied"]>0:
            self._save_log(summary)
        self.sync_done.emit(summary)

    def _tally(self, res, fi, c):
        if res == "stopped":
            return
        if res == "copied":
            c["copied"] += 1
            c["size"] += fi["size"]
        elif res == "skipped":
            c["skipped"] += 1
        else:
            c["errors"] += 1

    def _copy_one_wrapper(self, fi):
        if self._stop:
            return "stopped"
        self.file_status_changed.emit(fi["rel_path"], "processing", "")
        res, err = self._copy_one(fi)
        self.file_status_changed.emit(fi["rel_path"], "completed" if res == "copied" else "failed", err)
        
        if res == "copied":
            with self.consec_lock:
                self.consec_errors = 0
        elif res == "error":
            with self.consec_lock:
                self.consec_errors += 1
                if self.consec_errors >= 5:
                    self._stop = True
                    self.consec_fail_signal.emit()
        return res

    def _calc_md5(self, filepath):
        import hashlib
        hasher = hashlib.md5()
        try:
            with open(ensure_extended_path(filepath), 'rb') as f:
                for chunk in iter(lambda: f.read(MD5_CHUNK_SIZE), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def _copy_and_hash(self, src, dst, compute_hash=False):
        import hashlib
        hasher_src = hashlib.md5() if compute_hash else None
        
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        safe_chmod_write(dst)
        
        with open(ensure_extended_path(src), 'rb') as f_src, open(ensure_extended_path(dst), 'wb') as f_dst:
            while True:
                if self._stop:
                    raise InterruptedError("Sync stopped by user")
                self._pause_ev.wait()
                buf = f_src.read(MD5_CHUNK_SIZE)
                if not buf:
                    break
                f_dst.write(buf)
                if compute_hash:
                    hasher_src.update(buf)
                    
        try:
            shutil.copystat(ensure_extended_path(src), ensure_extended_path(dst))
        except Exception:
            pass
        return hasher_src.hexdigest() if compute_hash else None

    def _copy_one(self, fi):
        src = fi["src_path"]
        dest = fi["dest_path"]
        tmp = f"{dest}.smartsync.{os.getpid()}_{int(time.time()*1000)}.tmp"
        try:
            if not os.path.exists(ensure_extended_path(src)):
                self.log_signal.emit(f"⚠️ Source missing: {Path(fi['rel_path']).name}", "warning")
                return "error", "Source file missing"
            if self.dry_run:
                self.log_signal.emit(f"[DRY] {Path(fi['rel_path']).name} ({fi['size_str']})", "info")
                return "copied", ""

            os.makedirs(os.path.dirname(dest), exist_ok=True)

            if self.use_safe_renames:
                src_hash = self._copy_and_hash(src, tmp, compute_hash=self.use_md5_verify)
                if self.use_md5_verify:
                    tmp_hash = self._calc_md5(tmp)
                    if tmp_hash is None or src_hash != tmp_hash:
                        return "error", "MD5 integrity check failed: source and copied hashes differ"
                safe_chmod_write(dest)
                os.replace(ensure_extended_path(tmp), ensure_extended_path(dest))
            else:
                src_hash = self._copy_and_hash(src, dest, compute_hash=self.use_md5_verify)
                if self.use_md5_verify:
                    dest_hash = self._calc_md5(dest)
                    if dest_hash is None or src_hash != dest_hash:
                        return "error", "MD5 integrity check failed: source and copied hashes differ"

            self.log_signal.emit(f"✅ Synced {Path(fi['rel_path']).name} ({fi['size_str']})", "success")
            return "copied", ""
        except InterruptedError:
            return "stopped", "Sync stopped by user"
        except PermissionError:
            err_msg = (
                f"Permission Denied: Access to '{fi['rel_path']}' was blocked. "
                "Suggested fix: Ensure the file is not open in another application, "
                "verify write access permissions on the destination folder, "
                "or run the application as Administrator."
            )
            self.log_signal.emit(f"❌ {err_msg}", "error")
            return "error", err_msg
        except OSError as e:
            err_msg = f"OS error: {e.strerror or str(e)}"
            self.log_signal.emit(f"❌ OSError on {Path(fi['rel_path']).name}: {err_msg}", "error")
            return "error", err_msg
        except Exception as e:
            self.log_signal.emit(f"❌ Error syncing {Path(fi['rel_path']).name} — {e}", "error")
            return "error", str(e)
        finally:
            if self.use_safe_renames and os.path.exists(ensure_extended_path(tmp)):
                try:
                    safe_chmod_write(tmp)
                    os.remove(ensure_extended_path(tmp))
                except:
                    pass

    def _save_log(self, summary):
        try:
            hist = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, encoding="utf-8") as f: hist = json.load(f)
            hist.insert(0,{"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),**summary})
            with open(LOG_FILE,"w", encoding="utf-8") as f: json.dump(hist[:100], f, indent=2)
        except Exception as e:
            self.log_signal.emit(f"⚠️ Log save: {e}", "warning")

# ───────────────────────────────────────────────
# REDESIGNED PAGES
# ───────────────────────────────────────────────

class VisualStepTracker(QFrame):
    """Horizontal modern workflow step indicator with connected pills"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step_tracker")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)
        
        self.step1 = QLabel("1  Setup")
        self.step2 = QLabel("2  Scan")
        self.step3 = QLabel("3  Review")
        self.step4 = QLabel("4  Sync")
        
        self.arrows = [QLabel("→"), QLabel("→"), QLabel("→")]
        
        for lbl in self.arrows:
            lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            lbl.setStyleSheet("color: #475569; background: transparent;")
            
        for s in [self.step1, self.step2, self.step3, self.step4]:
            s.setFont(QFont("Segoe UI", 9, QFont.Bold))
            s.setAlignment(Qt.AlignCenter)
            s.setFixedHeight(26)
            s.setStyleSheet("color: #64748b; background: transparent; padding: 2px 10px; border-radius: 13px;")
            
        lay.addWidget(self.step1)
        lay.addWidget(self.arrows[0])
        lay.addWidget(self.step2)
        lay.addWidget(self.arrows[1])
        lay.addWidget(self.step3)
        lay.addWidget(self.arrows[2])
        lay.addWidget(self.step4)
        lay.addStretch()
        
        self.set_active_step(1)
        
    def set_active_step(self, step_num):
        steps = [self.step1, self.step2, self.step3, self.step4]
        labels = ["Setup", "Scan", "Review", "Sync"]
        for i, s in enumerate(steps):
            if i + 1 < step_num:
                s.setText(f"✓  {labels[i]}")
                s.setStyleSheet("color: #10b981; font-weight: bold; background-color: rgba(16, 185, 129, 0.12); padding: 2px 10px; border-radius: 13px;")
            elif i + 1 == step_num:
                s.setText(f"●  {labels[i]}")
                s.setStyleSheet("color: #3b82f6; font-weight: bold; background-color: rgba(59, 130, 246, 0.16); padding: 2px 10px; border-radius: 13px;")
            else:
                s.setText(f"{i+1}  {labels[i]}")
                s.setStyleSheet("color: #64748b; background: transparent; padding: 2px 10px; border-radius: 13px;")

class DashboardPage(QWidget):
    """Redesigned Dashboard Overview Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(0)

        # Welcome Card (Lightweight First-Run Experience)
        self.welcome_card = QFrame()
        self.welcome_card.setObjectName("dashboard_panel")
        wc_lay = QVBoxLayout(self.welcome_card)
        wc_lay.setContentsMargins(32, 32, 32, 32)
        wc_lay.setSpacing(20)
        wc_lay.setAlignment(Qt.AlignCenter)

        wc_icon = QLabel("👋")
        wc_icon.setFont(QFont("Segoe UI", 36))
        wc_icon.setAlignment(Qt.AlignCenter)
        wc_icon.setStyleSheet("background: transparent;")

        wc_title = QLabel("Welcome to Smart File Sync")
        wc_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        wc_title.setAlignment(Qt.AlignCenter)
        wc_title.setStyleSheet("color: #3b82f6; background: transparent;")

        wc_desc = QLabel("Get started by setting up your synchronization directories in a few simple steps:")
        wc_desc.setFont(QFont("Segoe UI", 11))
        wc_desc.setAlignment(Qt.AlignCenter)
        wc_desc.setStyleSheet("color: #94a3b8; background: transparent; margin-bottom: 10px;")

        steps_container = QWidget()
        steps_container.setStyleSheet("background: transparent;")
        steps_lay = QVBoxLayout(steps_container)
        steps_lay.setSpacing(10)
        steps_lay.setAlignment(Qt.AlignCenter)

        steps = [
            "1. Select Source Folder — The directory containing files you want to copy.",
            "2. Select Destination Folder — The target directory where files should sync.",
            "3. Run Scan — Analyze differences between folders with filters and exclusions.",
            "4. Review Changes — Inspect missing or modified files in the comparison table.",
            "5. Start Synchronization — Safely sync files with high speed and reliability."
        ]
        for step in steps:
            lbl = QLabel(step)
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #cbd5e1; background: transparent;")
            steps_lay.addWidget(lbl)

        btn_configure = QPushButton("Configure Folders Now")
        btn_configure.setObjectName("btn_scan")
        btn_configure.setFixedHeight(40)
        btn_configure.setMinimumWidth(220)
        btn_configure.setCursor(Qt.PointingHandCursor)
        btn_configure.clicked.connect(self._go_to_folder_setup)

        wc_lay.addWidget(wc_icon)
        wc_lay.addWidget(wc_title)
        wc_lay.addWidget(wc_desc)
        wc_lay.addWidget(steps_container)
        wc_lay.addWidget(btn_configure, 0, Qt.AlignCenter)

        lay.addWidget(self.welcome_card)

        # Main Content Container
        self.content_container = QWidget()
        self.content_container.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(self.content_container)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(16)

        # Header Title
        lbl_title = QLabel("Dashboard")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc; background: transparent;")
        lbl_sub = QLabel("Operational statistics, storage capacity, and recent activities overview.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        content_lay.addWidget(lbl_title)
        content_lay.addWidget(lbl_sub)

        # Workspace Row 1: Diagnostics Grid (Horizontal layout containing 3 cards)
        diag_lay = QHBoxLayout()
        diag_lay.setSpacing(12)

        # Card 1: Storage Diagnostics
        self.card_storage = QFrame()
        self.card_storage.setObjectName("stat_card")
        cs_lay = QVBoxLayout(self.card_storage)
        cs_lay.setContentsMargins(16, 12, 16, 12)
        cs_lay.setSpacing(8)
        
        lbl_st_title = QLabel("STORAGE CAPACITY")
        lbl_st_title.setObjectName("stat_label")
        self.lbl_src_disk = QLabel("Source Drive: —")
        self.lbl_src_disk.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        self.src_disk_bar = QProgressBar()
        self.src_disk_bar.setObjectName("main_progress")
        self.src_disk_bar.setFixedHeight(6)
        self.src_disk_bar.setTextVisible(False)

        self.lbl_dst_disk = QLabel("Dest Drive: —")
        self.lbl_dst_disk.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        self.dst_disk_bar = QProgressBar()
        self.dst_disk_bar.setObjectName("main_progress")
        self.dst_disk_bar.setFixedHeight(6)
        self.dst_disk_bar.setTextVisible(False)

        cs_lay.addWidget(lbl_st_title)
        cs_lay.addWidget(self.lbl_src_disk)
        cs_lay.addWidget(self.src_disk_bar)
        cs_lay.addWidget(self.lbl_dst_disk)
        cs_lay.addWidget(self.dst_disk_bar)
        cs_lay.addStretch()
        diag_lay.addWidget(self.card_storage, 1)

        # Card 2: Sync Health Rating
        self.card_health = QFrame()
        self.card_health.setObjectName("stat_card")
        ch_lay = QVBoxLayout(self.card_health)
        ch_lay.setContentsMargins(16, 12, 16, 12)
        ch_lay.setSpacing(6)
        lbl_hl_title = QLabel("SYNC HEALTH")
        lbl_hl_title.setObjectName("stat_label")
        self.lbl_health_score = QLabel("100%")
        self.lbl_health_score.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.lbl_health_score.setStyleSheet("color: #10b981; background: transparent;")
        self.lbl_health_desc = QLabel("All directories fully healthy.")
        self.lbl_health_desc.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        
        ch_lay.addWidget(lbl_hl_title)
        ch_lay.addWidget(self.lbl_health_score)
        ch_lay.addWidget(self.lbl_health_desc)
        ch_lay.addStretch()
        diag_lay.addWidget(self.card_health, 1)

        # Card 3: Guided Step Workflow
        self.card_workflow = QFrame()
        self.card_workflow.setObjectName("stat_card")
        cw_lay = QVBoxLayout(self.card_workflow)
        cw_lay.setContentsMargins(16, 12, 16, 12)
        cw_lay.setSpacing(6)
        lbl_wf_title = QLabel("ACTIVE WORKFLOW STEP")
        lbl_wf_title.setObjectName("stat_label")
        self.workflow_tracker = VisualStepTracker(self)
        
        self.lbl_workflow_stage = QLabel("Stage: Ready")
        self.lbl_workflow_stage.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        
        cw_lay.addWidget(lbl_wf_title)
        cw_lay.addWidget(self.workflow_tracker)
        cw_lay.addWidget(self.lbl_workflow_stage)
        cw_lay.addStretch()
        diag_lay.addWidget(self.card_workflow, 1)

        content_lay.addLayout(diag_lay)

        # Workspace Row 1b: Operational Summary Cards (Last Sync & Folder Comparison)
        summary_lay = QHBoxLayout()
        summary_lay.setSpacing(12)

        # Card 1b.1: Last Sync Summary
        self.card_last_sync = QFrame()
        self.card_last_sync.setObjectName("stat_card")
        cls_lay = QVBoxLayout(self.card_last_sync)
        cls_lay.setContentsMargins(16, 12, 16, 12)
        cls_lay.setSpacing(8)
        
        lbl_sync_title = QLabel("LAST SYNCHRONIZATION SUMMARY")
        lbl_sync_title.setObjectName("stat_label")
        lbl_sync_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        cls_lay.addWidget(lbl_sync_title)
        
        sync_grid = QGridLayout()
        sync_grid.setSpacing(6)
        
        self.lbl_last_status = QLabel("Status: Idle")
        self.lbl_last_status.setStyleSheet("font-weight: bold; color: #94a3b8; background: transparent;")
        self.lbl_last_time = QLabel("Time: Never")
        self.lbl_last_time.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_files = QLabel("Files Synced: 0")
        self.lbl_last_files.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_size = QLabel("Data Transferred: 0 B")
        self.lbl_last_size.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_duration = QLabel("Duration: —")
        self.lbl_last_duration.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_scan = QLabel("Last Scan: Never")
        self.lbl_last_scan.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_error = QLabel("Last Error: None")
        self.lbl_last_error.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_last_error.setWordWrap(True)
        
        sync_grid.addWidget(self.lbl_last_status, 0, 0)
        sync_grid.addWidget(self.lbl_last_time, 0, 1)
        sync_grid.addWidget(self.lbl_last_files, 1, 0)
        sync_grid.addWidget(self.lbl_last_size, 1, 1)
        sync_grid.addWidget(self.lbl_last_duration, 2, 0)
        sync_grid.addWidget(self.lbl_last_scan, 2, 1)
        sync_grid.addWidget(self.lbl_last_error, 3, 0, 1, 2)
        cls_lay.addLayout(sync_grid)
        cls_lay.addStretch()
        summary_lay.addWidget(self.card_last_sync, 1)

        # Card 1b.2: Folder Comparison Summary
        self.card_comparison = QFrame()
        self.card_comparison.setObjectName("stat_card")
        comp_card_lay = QVBoxLayout(self.card_comparison)
        comp_card_lay.setContentsMargins(16, 12, 16, 12)
        comp_card_lay.setSpacing(8)
        
        lbl_comp_title = QLabel("FOLDER COMPARISON SUMMARY")
        lbl_comp_title.setObjectName("stat_label")
        lbl_comp_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        comp_card_lay.addWidget(lbl_comp_title)
        
        comp_grid = QGridLayout()
        comp_grid.setSpacing(6)
        
        lbl_hdr_src = QLabel("Source")
        lbl_hdr_src.setStyleSheet("font-weight: bold; color: #3b82f6; background: transparent;")
        lbl_hdr_dst = QLabel("Destination")
        lbl_hdr_dst.setStyleSheet("font-weight: bold; color: #10b981; background: transparent;")
        lbl_hdr_diff = QLabel("Difference")
        lbl_hdr_diff.setStyleSheet("font-weight: bold; color: #f59e0b; background: transparent;")
        
        comp_grid.addWidget(lbl_hdr_src, 0, 0)
        comp_grid.addWidget(lbl_hdr_dst, 0, 1)
        comp_grid.addWidget(lbl_hdr_diff, 0, 2)
        
        self.lbl_comp_src_files = QLabel("Files: 0")
        self.lbl_comp_src_files.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_comp_src_size = QLabel("Size: 0 B")
        self.lbl_comp_src_size.setStyleSheet("color: #94a3b8; background: transparent;")
        
        self.lbl_comp_dst_files = QLabel("Files: 0")
        self.lbl_comp_dst_files.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_comp_dst_size = QLabel("Size: 0 B")
        self.lbl_comp_dst_size.setStyleSheet("color: #94a3b8; background: transparent;")
        
        self.lbl_comp_diff_files = QLabel("Missing Files: 0")
        self.lbl_comp_diff_files.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_comp_diff_size = QLabel("Size Difference: 0 B")
        self.lbl_comp_diff_size.setStyleSheet("color: #94a3b8; background: transparent;")
        
        comp_grid.addWidget(self.lbl_comp_src_files, 1, 0)
        comp_grid.addWidget(self.lbl_comp_src_size, 2, 0)
        comp_grid.addWidget(self.lbl_comp_dst_files, 1, 1)
        comp_grid.addWidget(self.lbl_comp_dst_size, 2, 1)
        comp_grid.addWidget(self.lbl_comp_diff_files, 1, 2)
        comp_grid.addWidget(self.lbl_comp_diff_size, 2, 2)
        comp_card_lay.addLayout(comp_grid)
        comp_card_lay.addStretch()
        summary_lay.addWidget(self.card_comparison, 1)

        content_lay.addLayout(summary_lay)

        # Stats Row
        stats_lay = QHBoxLayout()
        stats_lay.setSpacing(12)
        self.stat_scanned = StatCard("Total Scanned", "0", "#3b82f6")
        self.stat_missing = StatCard("Missing", "0", "#10b981")
        self.stat_modified = StatCard("Changed", "0", "#f59e0b")
        self.stat_copied = StatCard("Synced", "0", "#06b6d4")
        self.stat_errors = StatCard("Errors", "0", "#ef4444")

        for sc in [self.stat_scanned, self.stat_missing, self.stat_modified, self.stat_copied, self.stat_errors]:
            stats_lay.addWidget(sc)
        content_lay.addLayout(stats_lay)

        # Bottom Workspace split layout: 2 Columns
        grid_lay = QHBoxLayout()
        grid_lay.setSpacing(16)

        # Left side: Scrolling Console Activity Log
        col_left = QFrame()
        col_left.setObjectName("dashboard_panel")
        cl_lay = QVBoxLayout(col_left)
        cl_lay.setContentsMargins(16, 16, 16, 16)
        cl_lay.setSpacing(10)
        lbl_cl = QLabel("LIVE SYSTEM ACTIVITY LOG")
        lbl_cl.setObjectName("card_header")
        lbl_cl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        cl_lay.addWidget(lbl_cl)

        self.list_activity = QTableWidget(0, 2)
        self.list_activity.setObjectName("dashboard_table")
        self.list_activity.setHorizontalHeaderLabels(["Time", "Event Detail"])
        self.list_activity.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.list_activity.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.list_activity.verticalHeader().setVisible(False)
        self.list_activity.verticalHeader().setDefaultSectionSize(32)
        self.list_activity.setShowGrid(False)
        self.list_activity.setAlternatingRowColors(True)
        self.list_activity.setSelectionBehavior(QTableWidget.SelectRows)
        self.list_activity.setEditTriggers(QTableWidget.NoEditTriggers)
        self.list_activity.setMinimumHeight(240)
        cl_lay.addWidget(self.list_activity)
        grid_lay.addWidget(col_left, 1)
        content_lay.addLayout(grid_lay)

        lay.addWidget(self.content_container, 1)

    def _go_to_folder_setup(self):
        self.main_win._on_nav_clicked(0)

    def check_first_run(self):
        src = self.main_win.folder_setup_page.card_src.input.text().strip()
        dest = self.main_win.folder_setup_page.card_dst.input.text().strip()
        is_first_run = not (src and dest and os.path.isdir(src) and os.path.isdir(dest))
        self.welcome_card.setVisible(is_first_run)
        self.content_container.setVisible(not is_first_run)

    def showEvent(self, event):
        super().showEvent(event)
        self.check_first_run()

    def _apply_preset(self, filter_name, preset_desc):
        # Trigger preset selection and jump to folder config
        idx = self.main_win.folder_setup_page.filter_combo.findText(filter_name)
        if idx >= 0:
            self.main_win.folder_setup_page.filter_combo.setCurrentIndex(idx)
        self.main_win._on_nav_clicked(0) # Switch to Folder Setup screen
        self.main_win.folder_setup_page._add_log_message(f"Applied preset filter: {filter_name} ({preset_desc})")

    def update_stats(self, scanned, missing, modified, copied, errors):
        self.stat_scanned.set_value(scanned)
        self.stat_missing.set_value(missing)
        self.stat_modified.set_value(modified)
        self.stat_copied.set_value(copied)
        self.stat_errors.set_value(errors)
        
        # Calculate health score dynamically
        try:
            sc = int(scanned)
            m = int(missing)
            mod = int(modified)
            err = int(errors)
            if sc > 0:
                score = max(0, int((sc - m - mod - err) / sc * 100))
            else:
                score = 100
            self.lbl_health_score.setText(f"{score}%")
            if score == 100:
                self.lbl_health_desc.setText("System is fully synced.")
                self.lbl_health_score.setStyleSheet("color: #10b981; font-size: 24px; font-weight: bold; background: transparent;")
            elif score > 80:
                self.lbl_health_desc.setText("Needs minor updates.")
                self.lbl_health_score.setStyleSheet("color: #f59e0b; font-size: 24px; font-weight: bold; background: transparent;")
            else:
                self.lbl_health_desc.setText("Requires immediate sync.")
                self.lbl_health_score.setStyleSheet("color: #ef4444; font-size: 24px; font-weight: bold; background: transparent;")
        except ValueError:
            self.lbl_health_score.setText("—")
            self.lbl_health_desc.setText("Start scan to evaluate health.")

    def populate_recent_pairs(self, src, dest):
        pass

    def _quick_load(self, src, dest):
        self.main_win.folder_setup_page.card_src.input.setText(src)
        self.main_win.folder_setup_page.card_dst.input.setText(dest)
        self.main_win.folder_setup_page._trigger_metadata_scan("src")
        self.main_win.folder_setup_page._trigger_metadata_scan("dst")
        self.main_win._on_nav_clicked(0) # Go to setup

    def log_activity(self, message, kind="info"):
        r = self.list_activity.rowCount()
        self.list_activity.insertRow(r)
        now = datetime.now().strftime("%H:%M:%S")
        
        # Clean text by removing any leading redundant emoji prefixes if already present
        clean_msg = message.strip()
        for prefix in ["🔍", "📊", "🚀", "✅", "⚠️", "❌", "ℹ️", "💥", "🧹", "✓", "⚠", "✕"]:
            if clean_msg.startswith(prefix):
                clean_msg = clean_msg[len(prefix):].strip()
        
        color = "#10b981" if kind == "success" else ("#f59e0b" if kind == "warning" else ("#ef4444" if kind == "error" else "#3b82f6"))
        icon = "●"
        if kind == "error": icon = "✕"
        elif kind == "warning": icon = "▲"
        elif kind == "success": icon = "✓"
        
        dark = self.main_win.dark_mode if hasattr(self, "main_win") and self.main_win else True
        time_item = QTableWidgetItem(f" {now} ")
        time_item.setFont(QFont("Segoe UI", 9))
        time_item.setTextAlignment(Qt.AlignCenter)
        time_item.setForeground(QColor("#94a3b8" if dark else "#64748b"))
        
        msg_item = QTableWidgetItem(f" {icon}  {clean_msg}")
        msg_item.setFont(QFont("Segoe UI", 10))
        msg_item.setForeground(QColor(color))
        
        self.list_activity.setItem(r, 0, time_item)
        self.list_activity.setItem(r, 1, msg_item)
        self.list_activity.scrollToBottom()

    def update_last_sync_summary(self, status, time_str, files_count, size_str, duration_str):
        self.lbl_last_status.setText(f"Status: {status}")
        if "Success" in status or "Complete" in status:
            self.lbl_last_status.setStyleSheet("font-weight: bold; color: #10b981; background: transparent;")
        elif "Error" in status or "Failed" in status or "Interrupted" in status:
            self.lbl_last_status.setStyleSheet("font-weight: bold; color: #ef4444; background: transparent;")
        else:
            self.lbl_last_status.setStyleSheet("font-weight: bold; color: #f59e0b; background: transparent;")
            
        self.lbl_last_time.setText(f"Time: {time_str}")
        self.lbl_last_files.setText(f"Files Synced: {files_count}")
        self.lbl_last_size.setText(f"Data Transferred: {size_str}")
        self.lbl_last_duration.setText(f"Duration: {duration_str}")

    def update_comparison_summary(self, src_count, src_size, dst_count, dst_size):
        self.lbl_comp_src_files.setText(f"Files: {src_count}")
        self.lbl_comp_src_size.setText(f"Size: {fmt_size(src_size)}")
        
        self.lbl_comp_dst_files.setText(f"Files: {dst_count}")
        self.lbl_comp_dst_size.setText(f"Size: {fmt_size(dst_size)}")
        
        diff_count = abs(src_count - dst_count)
        diff_size = abs(src_size - dst_size)
        
        self.lbl_comp_diff_files.setText(f"Missing Files: {diff_count}")
        self.lbl_comp_diff_size.setText(f"Size Difference: {fmt_size(diff_size)}")

    def update_last_error(self, err_msg):
        self.lbl_last_error.setText(f"Last Error: {err_msg}")
        if err_msg != "None":
            self.lbl_last_error.setStyleSheet("color: #ef4444; background: transparent; font-weight: 500;")
        else:
            self.lbl_last_error.setStyleSheet("color: #94a3b8; background: transparent;")

    def update_workflow_stage(self, state):
        self.lbl_workflow_stage.setText(f"Stage: {state}")

    def update_disk_usage(self, src_path, dst_path):
        try:
            if src_path and os.path.exists(src_path):
                usage = shutil.disk_usage(src_path)
                pct = int(usage.used / usage.total * 100)
                self.lbl_src_disk.setText(f"Source: {Path(src_path).drive or '/'} ({fmt_size(usage.free)} free)")
                self.src_disk_bar.setValue(pct)
                self.src_disk_bar.setVisible(True)
                self.lbl_src_disk.setVisible(True)
            else:
                self.src_disk_bar.setVisible(False)
                self.lbl_src_disk.setVisible(False)
                
            if dst_path and os.path.exists(dst_path):
                usage = shutil.disk_usage(dst_path)
                pct = int(usage.used / usage.total * 100)
                self.lbl_dst_disk.setText(f"Dest: {Path(dst_path).drive or '/'} ({fmt_size(usage.free)} free)")
                self.dst_disk_bar.setValue(pct)
                self.dst_disk_bar.setVisible(True)
                self.lbl_dst_disk.setVisible(True)
            else:
                self.dst_disk_bar.setVisible(False)
                self.lbl_dst_disk.setVisible(False)
        except Exception:
            pass

class FolderSetupPage(QWidget):
    """Redesigned Step-based Folder Selection and Configuration Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Header Title
        lbl_title = QLabel("Folder Configuration")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        lbl_sub = QLabel("Step 1: Select directories and configure synchronization filters.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_sub)

        # Visual Steps Header
        self.setup_steps_header = VisualStepTracker(self)
        self.setup_steps_header.set_active_step(1)
        lay.addWidget(self.setup_steps_header)

        # Cards Layout
        cards_lay = QHBoxLayout()
        cards_lay.setSpacing(16)

        self.card_src = FolderMetaCard("Source Directory", "Browse source directory path...", self._browse_src)
        self.card_dst = FolderMetaCard("Destination Directory", "Browse destination directory path...", self._browse_dst)

        # Connect text changes to trigger live background scans
        self.card_src.input.editingFinished.connect(lambda: self._trigger_metadata_scan("src"))
        self.card_dst.input.editingFinished.connect(lambda: self._trigger_metadata_scan("dst"))

        # Connect returnPressed to move focus
        self.card_src.input.returnPressed.connect(self.card_dst.input.setFocus)
        self.card_dst.input.returnPressed.connect(lambda: self.scan_btn.setFocus() if self.scan_btn.isEnabled() else None)

        cards_lay.addWidget(self.card_src)
        cards_lay.addWidget(self.card_dst)
        lay.addLayout(cards_lay)

        # Options Container
        opt_frame = QFrame()
        opt_frame.setObjectName("options_panel")
        opt_lay = QVBoxLayout(opt_frame)
        opt_lay.setContentsMargins(16, 14, 16, 14)
        opt_lay.setSpacing(12)

        lbl_opt = QLabel("CONFIG FILTERS & EXCLUSIONS")
        lbl_opt.setObjectName("card_header")
        lbl_opt.setFont(QFont("Segoe UI", 9, QFont.Bold))
        opt_lay.addWidget(lbl_opt)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(16)

        # Filter combo
        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_f = QLabel("File Type Filter:")
        lbl_f.setObjectName("small_lbl")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(FILE_FILTERS.keys()))
        v1.addWidget(lbl_f)
        v1.addWidget(self.filter_combo)
        opts_row.addLayout(v1, 1)

        # Exclusions trigger button
        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_e = QLabel("Rules & Limits:")
        lbl_e.setObjectName("small_lbl")
        self.excl_btn = QPushButton("⚙  Configure Exclusions")
        self.excl_btn.setFixedHeight(30)
        self.excl_btn.setCursor(Qt.PointingHandCursor)
        self.excl_btn.clicked.connect(self.main_win._open_exclude_dialog)
        v2.addWidget(lbl_e)
        v2.addWidget(self.excl_btn)
        opts_row.addLayout(v2, 1)

        # Dry run checkbox
        self.dry_run_chk = QCheckBox("Dry Run Preview Mode")
        self.dry_run_chk.setObjectName("opt_check")
        self.dry_run_chk.setToolTip("Preview sync changes without copying actual data.")
        opts_row.addWidget(self.dry_run_chk, 1)

        opt_lay.addLayout(opts_row)
        lay.addWidget(opt_frame)

        # Workflow Action row
        act_row = QHBoxLayout()
        act_row.setContentsMargins(0, 10, 0, 0)
        
        self.workflow_lbl = QLabel("📁 Select folders to initialize the scan workflow.")
        self.workflow_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-style: italic;")
        
        self.scan_btn = QPushButton("Launch Directory &Scan")
        self.scan_btn.setObjectName("btn_scan")
        self.scan_btn.setFixedHeight(40)
        self.scan_btn.setMinimumWidth(200)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.main_win._on_scan_click)

        act_row.addWidget(self.workflow_lbl)
        act_row.addStretch()
        act_row.addWidget(self.scan_btn)
        lay.addLayout(act_row)
        lay.addStretch()

    def _browse_src(self):
        start = self.card_src.input.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Source Directory", start)
        if path:
            self.card_src.input.setText(path)
            self._trigger_metadata_scan("src")
            # Auto-focus destination selection
            self.card_dst.input.setFocus()

    def _browse_dst(self):
        start = self.card_dst.input.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Destination Directory", start)
        if path:
            self.card_dst.input.setText(path)
            self._trigger_metadata_scan("dst")
            # Auto check validation states
            self._validate_paths()

    def _trigger_metadata_scan(self, folder_id, force=False):
        path = self.card_src.input.text().strip() if folder_id == "src" else self.card_dst.input.text().strip()
        if not path or not os.path.isdir(path):
            if folder_id == "src": self.card_src.reset_stats()
            else: self.card_dst.reset_stats()
            self._validate_paths()
            return

        if not hasattr(self, "_last_src_path"): self._last_src_path = ""
        if not hasattr(self, "_last_src_mtime"): self._last_src_mtime = 0.0
        if not hasattr(self, "_last_dst_path"): self._last_dst_path = ""
        if not hasattr(self, "_last_dst_mtime"): self._last_dst_mtime = 0.0

        try:
            current_mtime = os.path.getmtime(path)
        except Exception:
            current_mtime = 0.0

        if not force:
            if folder_id == "src":
                if path == self._last_src_path and abs(current_mtime - self._last_src_mtime) < 0.1:
                    return
            else:
                if path == self._last_dst_path and abs(current_mtime - self._last_dst_mtime) < 0.1:
                    return

        if folder_id == "src":
            self._last_src_path = path
            self._last_src_mtime = current_mtime
            self.card_src.reset_stats(calculating=True)
            self.src_scanner = MetadataScanner("src", path)
            self.src_scanner.done.connect(self._on_metadata_scanned)
            self.src_scanner.start()
        else:
            self._last_dst_path = path
            self._last_dst_mtime = current_mtime
            self.card_dst.reset_stats(calculating=True)
            self.dst_scanner = MetadataScanner("dst", path)
            self.dst_scanner.done.connect(self._on_metadata_scanned)
            self.dst_scanner.start()

    def _on_metadata_scanned(self, folder_id, path, size, count, mod_str):
        try:
            current_mtime = os.path.getmtime(path)
        except Exception:
            current_mtime = 0.0
            
        settings = self.main_win.settings
        settings.setValue(f"cached_{folder_id}_path", path)
        settings.setValue(f"cached_{folder_id}_size", size)
        settings.setValue(f"cached_{folder_id}_count", count)
        settings.setValue(f"cached_{folder_id}_mod", mod_str)
        settings.setValue(f"cached_{folder_id}_mtime", current_mtime)

        if folder_id == "src":
            self.main_win.src_file_count = count
            self.main_win.src_size = size
            self.card_src.update_stats(size, count, mod_str)
        else:
            self.main_win.dst_file_count = count
            self.main_win.dst_size = size
            self.card_dst.update_stats(size, count, mod_str)
            self.main_win._cleanup_orphaned_tmps(path)
            
        self._validate_paths()
        self.main_win.dashboard_page.update_disk_usage(
            self.card_src.input.text().strip(),
            self.card_dst.input.text().strip()
        )
        self.main_win.dashboard_page.update_comparison_summary(
            self.main_win.src_file_count,
            self.main_win.src_size,
            self.main_win.dst_file_count,
            self.main_win.dst_size
        )

    def _validate_paths(self):
        src = self.card_src.input.text().strip()
        dst = self.card_dst.input.text().strip()
        is_ready = bool(src and dst and os.path.isdir(src) and os.path.isdir(dst) and os.path.normcase(src) != os.path.normcase(dst))
        self.scan_btn.setEnabled(is_ready)
        
        if is_ready:
            self.workflow_lbl.setText("✅ Folders validated. Launch the scan workflow to compute file status comparisons.")
            self.workflow_lbl.setStyleSheet("color: #10b981; font-weight: 500; font-size: 12px;")
            self.main_win.dashboard_page.workflow_tracker.set_active_step(2)
            self.setup_steps_header.set_active_step(2)
            self.scan_btn.setFocus()
        else:
            self.workflow_lbl.setText("📁 Source and destination paths must be distinct, valid directories.")
            self.workflow_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-style: italic;")
            self.main_win.dashboard_page.workflow_tracker.set_active_step(1)
            self.setup_steps_header.set_active_step(1)

        self.main_win.dashboard_page.check_first_run()

    def _add_log_message(self, msg):
        self.main_win._add_log(msg, "info")

class ScanResultsPage(QWidget):
    """Phase 4: Redesigned Scan Results with dual-pane layout, stat chips, and metadata details panel."""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self._current_fi = None  # Currently selected file info dict
        
        # Initialize custom model and proxy
        self.source_model = ScanResultsModel(main_win)
        self.proxy_model = ScanResultsProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(0)

        # ── HEADER: Title + Stat Chips ──
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Scan Results")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc; margin: 0; padding: 0;")
        lbl_sub = QLabel("Review detected differences and select files to synchronize.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b; margin: 0; padding: 0;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        header_row.addLayout(title_col)
        header_row.addStretch()

        # Stat Chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        self.chip_total = self._make_stat_chip("Total", "0", "#3b82f6")
        self.chip_missing = self._make_stat_chip("Missing", "0", "#f59e0b")
        self.chip_modified = self._make_stat_chip("Changed", "0", "#8b5cf6")
        self.chip_errors = self._make_stat_chip("Errors", "0", "#ef4444")
        for chip in [self.chip_total, self.chip_missing, self.chip_modified, self.chip_errors]:
            chips_row.addWidget(chip)
        header_row.addLayout(chips_row)
        lay.addLayout(header_row)
        lay.addSpacing(16)

        # ── TOOLBAR: Search + Filter + Actions ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("🔍  Search files...")
        self.search_input.setFixedHeight(32)
        self.search_input.setMinimumWidth(200)
        
        # Debounce search timer (250ms)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._filter_results_table)
        self.search_input.textChanged.connect(lambda: self.search_timer.start(250))

        self.filter_reason_combo = QComboBox()
        self.filter_reason_combo.setObjectName("filter_reason_combo")
        self.filter_reason_combo.setFixedHeight(32)
        self.filter_reason_combo.setFixedWidth(145)
        self.filter_reason_combo.addItems(["All Reasons", "Missing", "Size Differs", "Modified", "Source Newer", "Dest Newer", "Stat Error"])
        self.filter_reason_combo.currentIndexChanged.connect(self._filter_results_table)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet("background-color: #1f2937;")

        sel_all = QPushButton("✓  Select All")
        sel_none = QPushButton("✕  Deselect All")
        for btn in [sel_all, sel_none]:
            btn.setObjectName("mini_btn")
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
        sel_all.clicked.connect(self._on_select_all_clicked)
        sel_none.clicked.connect(self._on_deselect_all_clicked)

        toolbar.addWidget(self.search_input, 2)
        toolbar.addWidget(self.filter_reason_combo)
        toolbar.addWidget(sep)
        toolbar.addWidget(sel_all)
        toolbar.addWidget(sel_none)
        toolbar.addStretch()
        lay.addLayout(toolbar)
        lay.addSpacing(12)

        # ── MAIN CONTENT: Splitter (Table Left | Details Right) ──
        self.content_stack = QStackedWidget()

        # Empty State (shown when no results)
        self.empty_state_widget = EmptyStateWidget(
            "scan",
            "No scan results available",
            "Select source and destination folders and run a scan to discover differences.",
            btn_text="Launch Folder Setup",
            btn_callback=lambda: self.main_win._on_nav_clicked(0)
        )
        self.content_stack.addWidget(self.empty_state_widget)

        # Dual-Pane Splitter (shown when results exist)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("scan_splitter")
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)

        # ── LEFT: File Comparison Table ──
        table_container = QWidget()
        table_lay = QVBoxLayout(table_container)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.setSpacing(0)

        # Replaced QTableWidget with QTableView
        self.files_table = QTableView()
        self.files_table.setObjectName("compare_table")
        self.files_table.setModel(self.proxy_model)
        
        self.badge_delegate = BadgeDelegate(self)
        self.files_table.setItemDelegateForColumn(4, self.badge_delegate)

        hdr = self.files_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.files_table.setColumnWidth(0, 40)
        hdr.setMinimumSectionSize(75)
        self.files_table.setSelectionBehavior(QTableView.SelectRows)
        self.files_table.setSelectionMode(QTableView.SingleSelection)
        self.files_table.setEditTriggers(QTableView.NoEditTriggers)
        self.files_table.setAlternatingRowColors(True)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setShowGrid(False)
        self.files_table.verticalHeader().setDefaultSectionSize(36)
        
        # Sorting
        self.files_table.setSortingEnabled(True)

        # Connect row selection and model change signals
        self.files_table.selectionModel().currentChanged.connect(self._on_current_changed)
        self.source_model.dataChanged.connect(self._on_model_data_changed)

        # Connect Context Menu
        self.files_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_table.customContextMenuRequested.connect(self._show_comparison_context_menu)

        table_lay.addWidget(self.files_table)
        self.splitter.addWidget(table_container)

        # ── RIGHT: Metadata Details Panel ──
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("scan_detail_panel")
        self.detail_panel.setMinimumWidth(260)
        self.detail_panel.setMaximumWidth(360)
        detail_lay = QVBoxLayout(self.detail_panel)
        detail_lay.setContentsMargins(20, 20, 20, 20)
        detail_lay.setSpacing(0)

        # Detail Panel Header
        dp_header = QLabel("FILE DETAILS")
        dp_header.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: #64748b; margin-bottom: 12px;")
        detail_lay.addWidget(dp_header)

        # File Icon + Name
        self.dp_icon = QLabel("📄")
        self.dp_icon.setStyleSheet("font-size: 36px; margin-bottom: 4px;")
        self.dp_icon.setAlignment(Qt.AlignLeft)
        detail_lay.addWidget(self.dp_icon)

        self.dp_filename = QLabel("No file selected")
        self.dp_filename.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc; margin-bottom: 2px;")
        self.dp_filename.setWordWrap(True)
        detail_lay.addWidget(self.dp_filename)

        self.dp_extension = QLabel("")
        self.dp_extension.setStyleSheet("font-size: 11px; color: #64748b; margin-bottom: 16px;")
        detail_lay.addWidget(self.dp_extension)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet("color: #1f2937; margin: 4px 0;")
        detail_lay.addWidget(div1)
        detail_lay.addSpacing(12)

        # Metadata Rows
        self.dp_reason_badge = QLabel("")
        self.dp_reason_badge.setAlignment(Qt.AlignCenter)
        self.dp_reason_badge.setFixedHeight(26)
        self.dp_reason_badge.setStyleSheet(
            "font-size: 11px; font-weight: 700; letter-spacing: 0.5px; border-radius: 6px; padding: 2px 14px;"
        )
        detail_lay.addWidget(self.dp_reason_badge)
        detail_lay.addSpacing(14)

        # Properties grid — updated to match user request exactly
        props_grid = QGridLayout()
        props_grid.setSpacing(8)
        props_grid.setColumnStretch(1, 1)

        self._dp_props = {}
        prop_defs = [
            ("Full Path", "dp_full_path"),
            ("Relative Path", "dp_rel_path"),
            ("File Size", "dp_size"),
            ("Extension", "dp_ext"),
            ("Modified Date", "dp_modified"),
            ("Status", "dp_status"),
        ]
        for i, (label_text, key) in enumerate(prop_defs):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
            val = QLabel("—")
            val.setStyleSheet("font-size: 11px; color: #cbd5e1;")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            props_grid.addWidget(lbl, i, 0, Qt.AlignTop)
            props_grid.addWidget(val, i, 1, Qt.AlignTop)
            self._dp_props[key] = val

        detail_lay.addLayout(props_grid)
        detail_lay.addSpacing(16)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("color: #1f2937; margin: 4px 0;")
        detail_lay.addWidget(div2)
        detail_lay.addSpacing(12)

        # Quick Action Buttons
        qa_lbl = QLabel("ACTIONS")
        qa_lbl.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: #64748b; margin-bottom: 8px;")
        detail_lay.addWidget(qa_lbl)

        self.dp_btn_open_src = QPushButton("Open Source Location")
        self.dp_btn_open_dst = QPushButton("Open Destination")
        self.dp_btn_copy_path = QPushButton("Copy File Path")
        self.dp_btn_exclude = QPushButton("Exclude Extension")

        for btn in [self.dp_btn_open_src, self.dp_btn_open_dst, self.dp_btn_copy_path, self.dp_btn_exclude]:
            btn.setObjectName("detail_action_btn")
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            detail_lay.addWidget(btn)
            detail_lay.addSpacing(4)

        self.dp_btn_open_src.clicked.connect(self._action_open_src)
        self.dp_btn_open_dst.clicked.connect(self._action_open_dst)
        self.dp_btn_copy_path.clicked.connect(self._action_copy_path)
        self.dp_btn_exclude.clicked.connect(self._action_exclude_ext)

        detail_lay.addStretch()

        self.splitter.addWidget(self.detail_panel)
        self.splitter.setSizes([600, 300])

        self.content_stack.addWidget(self.splitter)
        lay.addWidget(self.content_stack, 1)
        lay.addSpacing(12)

        # ── FOOTER: Summary + Action Buttons ──
        foot_row = QHBoxLayout()
        foot_row.setSpacing(10)
        self.lbl_summary = QLabel("0 files selected for synchronization.")
        self.lbl_summary.setStyleSheet("color: #64748b; font-size: 12px;")

        self.btn_sync_sel = QPushButton("Sync Selected")
        self.btn_sync_sel.setObjectName("btn_sel")
        self.btn_sync_sel.setFixedHeight(36)
        self.btn_sync_sel.setEnabled(False)
        self.btn_sync_sel.setCursor(Qt.PointingHandCursor)
        self.btn_sync_sel.clicked.connect(self.main_win._on_sync_sel)

        self.btn_sync_all = QPushButton("Sync All Files")
        self.btn_sync_all.setObjectName("btn_sync")
        self.btn_sync_all.setFixedHeight(36)
        self.btn_sync_all.setEnabled(False)
        self.btn_sync_all.setCursor(Qt.PointingHandCursor)
        self.btn_sync_all.clicked.connect(self.main_win._on_sync_all)

        foot_row.addWidget(self.lbl_summary)
        foot_row.addStretch()
        foot_row.addWidget(self.btn_sync_sel)
        foot_row.addWidget(self.btn_sync_all)
        lay.addLayout(foot_row)

        self._update_table_visibility()

    # ── Stat Chip Factory ──
    def _make_stat_chip(self, label, value, color):
        chip = QFrame()
        chip.setObjectName("scan_stat_chip")
        chip.setFixedHeight(36)
        chip_lay = QHBoxLayout(chip)
        chip_lay.setContentsMargins(10, 4, 10, 4)
        chip_lay.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 8px; color: {color};")
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        val = QLabel(value)
        val.setObjectName("chip_value")
        val.setStyleSheet(f"font-size: 13px; color: {color}; font-weight: 700;")
        chip_lay.addWidget(dot)
        chip_lay.addWidget(lbl)
        chip_lay.addWidget(val)
        chip._value_label = val
        return chip

    def update_stat_chips(self, total=0, missing=0, changed=0, errors=0):
        self.chip_total._value_label.setText(str(total))
        self.chip_missing._value_label.setText(str(missing))
        self.chip_modified._value_label.setText(str(changed))
        self.chip_errors._value_label.setText(str(errors))

    # ── Visibility Toggling ──
    def _update_table_visibility(self):
        has_rows = self.source_model.rowCount() > 0
        self.content_stack.setCurrentIndex(1 if has_rows else 0)
        self.btn_sync_all.setEnabled(has_rows)
        self.btn_sync_sel.setEnabled(has_rows and len(self.source_model.checked_rows) > 0)

    # ── Filtering ──
    def _filter_results_table(self):
        search_txt = self.search_input.text()
        filter_reason = self.filter_reason_combo.currentText()
        self.proxy_model.set_filters(search_txt, filter_reason)
        self._update_checked_count()

    # ── Select/Deselect All ──
    def _on_select_all_clicked(self):
        self.source_model.beginResetModel()
        for r in range(self.proxy_model.rowCount()):
            proxy_idx = self.proxy_model.index(r, 0)
            src_idx = self.proxy_model.mapToSource(proxy_idx)
            self.source_model.checked_rows.add(src_idx.row())
        self.source_model.endResetModel()
        self._update_checked_count()

    def _on_deselect_all_clicked(self):
        self.source_model.beginResetModel()
        for r in range(self.proxy_model.rowCount()):
            proxy_idx = self.proxy_model.index(r, 0)
            src_idx = self.proxy_model.mapToSource(proxy_idx)
            self.source_model.checked_rows.discard(src_idx.row())
        self.source_model.endResetModel()
        self._update_checked_count()

    def _on_model_data_changed(self, topLeft, bottomRight, roles):
        if Qt.CheckStateRole in roles:
            self._update_checked_count()

    def _update_checked_count(self):
        visible_count = self.proxy_model.rowCount()
        checked_count = 0
        model = self.source_model
        for r in range(visible_count):
            proxy_idx = self.proxy_model.index(r, 0)
            src_idx = self.proxy_model.mapToSource(proxy_idx)
            if src_idx.row() in model.checked_rows:
                checked_count += 1
        self.lbl_summary.setText(f"{checked_count} of {visible_count} items selected for synchronization.")
        self.btn_sync_sel.setEnabled(checked_count > 0)

    # ── Row Selection → Details Panel ──
    def _on_current_changed(self, current, previous):
        if not current.isValid():
            self._clear_detail_panel()
            return
        src_idx = self.proxy_model.mapToSource(current)
        if 0 <= src_idx.row() < len(self.source_model.files):
            fi = self.source_model.files[src_idx.row()]
            self._current_fi = fi
            self._update_detail_panel(fi)
        else:
            self._clear_detail_panel()

    def _update_detail_panel(self, fi):
        rel_path = fi.get("rel_path", "")
        name = Path(rel_path).name
        ext = Path(rel_path).suffix.lower()

        # Icon
        icon = "📄"
        if ext in FILE_FILTERS.get("Photos", []):
            icon = "🖼️"
        elif ext in FILE_FILTERS.get("Videos", []):
            icon = "🎥"
        elif ext in FILE_FILTERS.get("Audio", []):
            icon = "🎵"
        elif ext in [".pdf"]:
            icon = "📕"
        elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            icon = "📦"
        elif ext in [".txt", ".csv", ".json", ".xml", ".ini", ".log"]:
            icon = "📝"
        elif ext in [".exe", ".msi", ".bat", ".cmd", ".sh", ".py"]:
            icon = "⚙️"
        self.dp_icon.setText(icon)
        self.dp_filename.setText(name)
        self.dp_extension.setText(ext.upper() + " file" if ext else "Unknown type")

        # Reason/Status Badge
        reason = fi.get("reason", "Unknown")
        reason_colors = {
            "Missing": ("#fef3c7", "#92400e"),
            "Size Differs": ("#ede9fe", "#5b21b6"),
            "Modified": ("#dbeafe", "#1e40af"),
            "Stat Error": ("#fee2e2", "#991b1b"),
        }
        bg, fg = reason_colors.get(reason, ("#1f2937", "#94a3b8"))
        self.dp_reason_badge.setText(reason)
        self.dp_reason_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; letter-spacing: 0.5px; border-radius: 6px; "
            f"padding: 2px 14px; background-color: {bg}; color: {fg};"
        )

        # Properties (6 fields as requested)
        self._dp_props["dp_full_path"].setText(fi.get("src_path", "—"))
        self._dp_props["dp_rel_path"].setText(fi.get("rel_path", "—"))
        self._dp_props["dp_size"].setText(fi.get("size_str", "—"))
        self._dp_props["dp_ext"].setText(fi.get("type", "—").upper() or "None")
        self._dp_props["dp_modified"].setText(fi.get("modified", "—"))
        self._dp_props["dp_status"].setText(fi.get("reason", "—"))

    def _clear_detail_panel(self):
        self._current_fi = None
        self.dp_icon.setText("📄")
        self.dp_filename.setText("No file selected")
        self.dp_extension.setText("")
        self.dp_reason_badge.setText("")
        self.dp_reason_badge.setStyleSheet(
            "font-size: 11px; font-weight: 700; letter-spacing: 0.5px; border-radius: 6px; padding: 2px 14px;"
        )
        for val in self._dp_props.values():
            val.setText("—")

    # ── Detail Panel Actions ──
    def _action_open_src(self):
        if self._current_fi:
            self.main_win._open_path_in_explorer(self._current_fi["src_path"])

    def _action_open_dst(self):
        if self._current_fi:
            self.main_win._open_path_in_explorer(os.path.dirname(self._current_fi["dest_path"]))

    def _action_copy_path(self):
        if self._current_fi:
            QApplication.clipboard().setText(self._current_fi["src_path"])

    def _action_exclude_ext(self):
        if self._current_fi:
            self.main_win._exclude_selected_ext(self._current_fi["type"])

    # ── Context Menu (legacy compatibility) ──
    def _show_comparison_context_menu(self, pos):
        idx = self.files_table.indexAt(pos)
        if not idx.isValid(): return
        src_idx = self.proxy_model.mapToSource(idx)
        if not (0 <= src_idx.row() < len(self.source_model.files)): return
        fi = self.source_model.files[src_idx.row()]

        menu = QMenu(self)
        a_src = QAction("📁  Open Source Location", self)
        a_dest = QAction("📂  Open Destination Location", self)
        a_excl = QAction("🚫  Exclude Extension", self)
        a_copy = QAction("📋  Copy Source Path", self)

        menu.addAction(a_src)
        menu.addAction(a_dest)
        menu.addSeparator()
        menu.addAction(a_excl)
        menu.addAction(a_copy)

        a_src.triggered.connect(lambda: self.main_win._open_path_in_explorer(fi["src_path"]))
        a_dest.triggered.connect(lambda: self.main_win._open_path_in_explorer(os.path.dirname(fi["dest_path"])))
        a_excl.triggered.connect(lambda: self.main_win._exclude_selected_ext(fi["type"]))
        a_copy.triggered.connect(lambda: QApplication.clipboard().setText(fi["src_path"]))

        menu.exec(self.files_table.mapToGlobal(pos))

class SyncQueuePage(QWidget):
    """Redesigned Live Sync Operations Page showing Real-Time Sync Statuses and Progress"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        # O(1) row trackers for lightning fast queue updates without UI freezes
        self._pending_map = {}
        self._active_map = {}
        self._completed_map = {}
        self._failed_map = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Header Title
        lbl_title = QLabel("Sync Queue")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        lbl_sub = QLabel("Step 3: Monitor active file writes and synchronization speeds.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_sub)

        # Performance Panel
        perf_frame = QFrame()
        perf_frame.setObjectName("options_panel")
        pf_lay = QVBoxLayout(perf_frame)
        pf_lay.setContentsMargins(16, 12, 16, 12)
        pf_lay.setSpacing(8)

        # Row 1: Details & Pct
        hdr_lay = QHBoxLayout()
        self.lbl_detail = QLabel("Idle — Start scan results sync to view updates.")
        self.lbl_detail.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setStyleSheet("font-size: 16px; font-weight: bold; color: #3b82f6;")
        hdr_lay.addWidget(self.lbl_detail)
        hdr_lay.addStretch()
        hdr_lay.addWidget(self.lbl_pct)
        pf_lay.addLayout(hdr_lay)

        # Row 2: Sleek thin Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("main_progress")
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        pf_lay.addWidget(self.progress_bar)

        # Row 2.5: Metrics Grid (Horizontal row of 5 styled stats labels)
        metrics_lay = QHBoxLayout()
        metrics_lay.setSpacing(16)
        
        self.lbl_curr_speed = QLabel("Current Speed: —")
        self.lbl_avg_speed = QLabel("Avg Speed: —")
        self.lbl_files_sec = QLabel("Throughput: —")
        self.lbl_eta = QLabel("Time Left: —")
        self.lbl_data_copied = QLabel("Data Copied: —")
        
        for lbl in [self.lbl_curr_speed, self.lbl_avg_speed, self.lbl_files_sec, self.lbl_eta, self.lbl_data_copied]:
            lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500; background: transparent;")
            metrics_lay.addWidget(lbl)
            
        pf_lay.addLayout(metrics_lay)

        # Row 3: Action Controls
        ctrl_lay = QHBoxLayout()
        self.btn_pause = QPushButton("Pause Sync")
        self.btn_stop = QPushButton("Stop Sync")
        for btn in [self.btn_pause, self.btn_stop]:
            btn.setObjectName("mini_btn")
            btn.setFixedHeight(30)
            btn.setEnabled(False)
            btn.setCursor(Qt.PointingHandCursor)
            ctrl_lay.addWidget(btn)
        
        self.btn_pause.clicked.connect(self.main_win._on_pause_click)
        self.btn_stop.clicked.connect(self.main_win._on_stop_click)

        ctrl_lay.addStretch()
        pf_lay.addLayout(ctrl_lay)
        lay.addWidget(perf_frame)

        # Queue Performance Cards Row (Metric cards)
        q_cards_lay = QHBoxLayout()
        q_cards_lay.setSpacing(12)
        self.card_q_pending = StatCard("Pending", "0", "#f59e0b")
        self.card_q_active = StatCard("Active", "0", "#3b82f6")
        self.card_q_completed = StatCard("Completed", "0", "#10b981")
        self.card_q_failed = StatCard("Error", "0", "#ef4444")
        
        for card in [self.card_q_pending, self.card_q_active, self.card_q_completed, self.card_q_failed]:
            card.setFixedHeight(54)
            card.layout().setContentsMargins(8, 6, 8, 6)
            card.layout().setSpacing(2)
            card._val_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
            card._txt_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
            q_cards_lay.addWidget(card)
        lay.addLayout(q_cards_lay)

        # Stacked Container for Queue Tabs vs Empty State
        self.queue_container = QStackedWidget()
        self.queue_container.setObjectName("queue_container")

        # Tab view dividing Pending, Processing, Completed, Error
        self.queue_tabs = QTabWidget()
        self.queue_tabs.setObjectName("queue_tabs")
        
        # Pending tab
        self.tbl_pending = self._create_queue_table()
        self.queue_tabs.addTab(self.tbl_pending, "Pending (0)")
        
        # Processing tab
        self.tbl_processing = self._create_queue_table()
        self.queue_tabs.addTab(self.tbl_processing, "Active (0)")
        
        # Completed tab
        self.tbl_completed = self._create_queue_table()
        self.queue_tabs.addTab(self.tbl_completed, "Completed (0)")
        
        # Failed tab (now Error tab)
        self.tbl_failed = self._create_queue_table()
        self.queue_tabs.addTab(self.tbl_failed, "Error (0)")
        
        self.queue_container.addWidget(self.queue_tabs)

        # Empty State Placeholder
        self.empty_state = EmptyStateWidget(
            "queue",
            "No active synchronization tasks.",
            "Start a scan and review changes before starting synchronization.",
            btn_text="Open Scan Results",
            btn_callback=lambda: self.main_win._on_nav_clicked(1)
        )
        self.queue_container.addWidget(self.empty_state)
        
        lay.addWidget(self.queue_container, 1)
        
        # Initialize to empty state on startup
        self.queue_container.setCurrentWidget(self.empty_state)

    def _create_queue_table(self):
        tbl = QTableWidget(0, 4)
        tbl.setObjectName("compare_table")
        tbl.setHorizontalHeaderLabels(["Filename", "Size", "Relative Path", "Details"])
        
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        tbl.setColumnWidth(1, 90)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        tbl.setColumnWidth(3, 150)
        
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(36)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)
        return tbl

    def update_tab_titles(self):
        c_pending = self.tbl_pending.rowCount()
        c_active = self.tbl_processing.rowCount()
        c_completed = self.tbl_completed.rowCount()
        c_failed = self.tbl_failed.rowCount()
        
        self.queue_tabs.setTabText(0, f"Pending ({c_pending})")
        self.queue_tabs.setTabText(1, f"Active ({c_active})")
        self.queue_tabs.setTabText(2, f"Completed ({c_completed})")
        self.queue_tabs.setTabText(3, f"Error ({c_failed})")
        
        self.card_q_pending.set_value(c_pending)
        self.card_q_active.set_value(c_active)
        self.card_q_completed.set_value(c_completed)
        self.card_q_failed.set_value(c_failed)

    def update_operational_metrics(self, curr_speed, avg_speed, files_sec, eta, copied_bytes, total_bytes):
        self.lbl_curr_speed.setText(f"Current Speed: {fmt_speed(curr_speed)}")
        self.lbl_avg_speed.setText(f"Avg Speed: {fmt_speed(avg_speed)}")
        self.lbl_files_sec.setText(f"Throughput: {files_sec:.1f} files/sec" if files_sec > 0 else "Throughput: —")
        self.lbl_eta.setText(f"Time Left: {fmt_eta(eta)}")
        self.lbl_data_copied.setText(f"Data Copied: {fmt_size(copied_bytes)} / {fmt_size(total_bytes)}")

    def reset_queues(self):
        self._pending_map.clear()
        self._active_map.clear()
        self._completed_map.clear()
        self._failed_map.clear()
        for tbl in [self.tbl_pending, self.tbl_processing, self.tbl_completed, self.tbl_failed]:
            tbl.setRowCount(0)
        self.update_tab_titles()
        
        self.lbl_curr_speed.setText("Current Speed: —")
        self.lbl_avg_speed.setText("Avg Speed: —")
        self.lbl_files_sec.setText("Throughput: —")
        self.lbl_eta.setText("Time Left: —")
        self.lbl_data_copied.setText("Data Copied: —")
        
        self.queue_container.setCurrentWidget(self.empty_state)


class HistorySessionCard(QFrame):
    """Modern styled card representing a single synchronization session"""
    def __init__(self, session_data, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("history_session_card")
        self.main_win = main_win
        self.session_data = session_data
        self.setProperty("selected", False)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        
        # Header Row: Timestamp + Status Badge + Load Button
        hdr_lay = QHBoxLayout()
        
        time_lbl = QLabel(session_data.get("timestamp", ""))
        time_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        time_lbl.setStyleSheet("color: #f8fafc; background: transparent;" if main_win.dark_mode else "color: #1e293b; background: transparent;")
        
        status = session_data.get("status", "Success")
        status_lbl = QLabel(f" {status.upper()} ")
        status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setFixedHeight(20)
        status_lbl.setContentsMargins(6, 0, 6, 0)
        
        dark = main_win.dark_mode
        if status == "Success":
            bg_color = "#10b981" if dark else "#d1fae5"
            fg_color = "#ffffff" if dark else "#065f46"
        else:
            bg_color = "#ef4444" if dark else "#fee2e2"
            fg_color = "#ffffff" if dark else "#991b1b"
            
        status_lbl.setStyleSheet(f"background-color: {bg_color}; color: {fg_color}; border-radius: 4px;")
        
        load_btn = QPushButton("Load into Setup")
        load_btn.setObjectName("mini_btn")
        load_btn.setFixedHeight(26)
        load_btn.setMinimumWidth(115)
        load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.clicked.connect(self._reload_config)
        
        hdr_lay.addWidget(time_lbl)
        hdr_lay.addWidget(status_lbl)
        hdr_lay.addStretch()
        hdr_lay.addWidget(load_btn)
        lay.addLayout(hdr_lay)
        
        # Path details
        path_lay = QVBoxLayout()
        path_lay.setSpacing(3)
        
        src_lbl = QLabel(f"Source:      {session_data.get('source', '')}")
        src_lbl.setFont(QFont("Segoe UI", 9))
        src_lbl.setStyleSheet("color: #94a3b8; background: transparent;" if dark else "color: #64748b; background: transparent;")
        
        dst_lbl = QLabel(f"Destination: {session_data.get('destination', '')}")
        dst_lbl.setFont(QFont("Segoe UI", 9))
        dst_lbl.setStyleSheet("color: #94a3b8; background: transparent;" if dark else "color: #64748b; background: transparent;")
        
        path_lay.addWidget(src_lbl)
        path_lay.addWidget(dst_lbl)
        lay.addLayout(path_lay)
        
        # Divider Line
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #1f2937;" if dark else "background-color: #e2e8f0;")
        divider.setFixedHeight(1)
        lay.addWidget(divider)
        
        # Metrics Grid
        metrics_lay = QHBoxLayout()
        metrics_lay.setSpacing(16)
        
        m_dur = self._make_metric_item("DURATION", session_data.get("duration", "—"))
        m_files = self._make_metric_item("FILES SYNCED", str(session_data.get("copied", 0)))
        m_data = self._make_metric_item("DATA TRANSFERRED", session_data.get("copied_size", "0 B"))
        m_err = self._make_metric_item("ERRORS", str(session_data.get("errors", 0)), is_error=(int(session_data.get("errors", 0)) > 0))
        
        metrics_lay.addWidget(m_dur)
        metrics_lay.addWidget(m_files)
        metrics_lay.addWidget(m_data)
        metrics_lay.addWidget(m_err)
        lay.addLayout(metrics_lay)
        
    def _make_metric_item(self, label, value, is_error=False):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        lbl.setStyleSheet("color: #64748b;")
        
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 11, QFont.Bold))
        if is_error:
            val.setStyleSheet("color: #ef4444;")
        else:
            val.setStyleSheet("color: #f8fafc;" if self.main_win.dark_mode else "color: #1e293b;")
            
        lay.addWidget(lbl)
        lay.addWidget(val)
        return w
        
    def _reload_config(self):
        self.main_win.folder_setup_page.card_src.input.setText(self.session_data.get("source", ""))
        self.main_win.folder_setup_page.card_dst.input.setText(self.session_data.get("destination", ""))
        idx = self.main_win.folder_setup_page.filter_combo.findText(self.session_data.get("filter", "All Files"))
        if idx >= 0:
            self.main_win.folder_setup_page.filter_combo.setCurrentIndex(idx)
        
        # Load exclusions
        excl_str = self.session_data.get("excl", "[]")
        try:
            excl = json.loads(excl_str)
            if isinstance(excl, list):
                self.main_win.excl_exts = excl
                self.main_win.settings_page.txt_excl.setText("\n".join(excl))
        except Exception:
            pass
            
        self.main_win.folder_setup_page.card_src.reset_stats()
        self.main_win.folder_setup_page.card_dst.reset_stats()
        self.main_win._on_nav_clicked(0) # Go to setup

    def mousePressEvent(self, event):
        self.main_win.history_page.select_card(self)
        super().mousePressEvent(event)

    def setSelected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

class HistoryPage(QWidget):
    """Redesigned History Page showing detailed sync logs with preset reload"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.cards = []
        self.selected_card = None
        self.selected_session_data = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Header Title
        lbl_title = QLabel("Sync History")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        lbl_sub = QLabel("Audit past directory scan configurations and completed file sync states.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_sub)

        # Top Summary Cards Row
        sum_lay = QHBoxLayout()
        sum_lay.setSpacing(12)
        
        self.card_total_sessions = StatCard("Total Sessions", "0", "#3b82f6")
        self.card_files_synced = StatCard("Files Synced", "0", "#10b981")
        self.card_total_data = StatCard("Total Data", "0 B", "#06b6d4")
        self.card_success_rate = StatCard("Success Rate", "100%", "#f59e0b")
        
        for card in [self.card_total_sessions, self.card_files_synced, self.card_total_data, self.card_success_rate]:
            sum_lay.addWidget(card)
        lay.addLayout(sum_lay)

        # Control panel row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(12)
        
        ref_btn = QPushButton("Refresh Logs")
        exp_btn = QPushButton("Export Log CSV")
        for btn in [ref_btn, exp_btn]:
            btn.setObjectName("mini_btn")
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            ctrl.addWidget(btn)
        
        ref_btn.clicked.connect(self.main_win._load_history)
        exp_btn.clicked.connect(self.main_win._export_csv)

        ctrl.addStretch()
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("Search history logs...")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(32)
        self.search_input.textChanged.connect(self._filter_history)
        ctrl.addWidget(self.search_input)
        
        # Session Count Label
        self.lbl_session_count = QLabel("Showing 0 of 0 sessions")
        self.lbl_session_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_session_count.setObjectName("small_lbl")
        ctrl.addWidget(self.lbl_session_count)
        
        lay.addLayout(ctrl)

        # History list scroll area
        self.hist_scroll = QScrollArea()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.hist_list_widget = QWidget()
        self.hist_list_widget.setStyleSheet("background: transparent;")
        self.hist_list_lay = QVBoxLayout(self.hist_list_widget)
        self.hist_list_lay.setContentsMargins(0, 0, 0, 0)
        self.hist_list_lay.setSpacing(12)
        self.hist_list_lay.addStretch()
        
        self.hist_scroll.setWidget(self.hist_list_widget)

        # Stacked Container for List Scroll vs Empty State
        self.hist_container = QStackedWidget()
        self.hist_container.setObjectName("hist_container")
        self.hist_container.addWidget(self.hist_scroll)
        
        # Empty State Placeholder
        self.empty_state = EmptyStateWidget(
            "history",
            "No synchronization history available.",
            "Run your first scan and synchronization to begin building activity history.",
            btn_text="Open Folder Setup",
            btn_callback=lambda: self.main_win._on_nav_clicked(0)
        )
        self.hist_container.addWidget(self.empty_state)
        
        lay.addWidget(self.hist_container, 1)

    def select_card(self, card):
        if self.selected_card:
            self.selected_card.setSelected(False)
        self.selected_card = card
        if card:
            card.setSelected(True)
            self.selected_session_data = card.session_data
        else:
            self.selected_session_data = None

    def _filter_history(self):
        text = self.search_input.text().strip().lower()
        visible_count = 0
        total_count = len(self.cards)
        
        for card in self.cards:
            match = False
            e = card.session_data
            if isinstance(e, dict):
                fields = [
                    e.get("timestamp", ""),
                    e.get("duration", ""),
                    str(e.get("copied", "")),
                    e.get("copied_size", ""),
                    str(e.get("errors", "")),
                    e.get("status", ""),
                    e.get("source", ""),
                    e.get("destination", ""),
                    e.get("filter", "")
                ]
                if any(text in str(f).lower() for f in fields):
                    match = True
            
            card.setVisible(match)
            if match:
                visible_count += 1
                
        self.lbl_session_count.setText(f"Showing {visible_count} of {total_count} sessions")

    def update_history_stats(self, hist):
        total_sessions = len(hist)
        total_copied = 0
        total_errors = 0
        total_bytes = 0.0
        success_sessions = 0
        
        for e in hist:
            copied = int(e.get("copied", 0))
            errors = int(e.get("errors", 0))
            size_str = e.get("copied_size", "0 B")
            
            total_copied += copied
            total_errors += errors
            total_bytes += self._parse_size(size_str)
            if errors == 0:
                success_sessions += 1
                
        success_rate = (success_sessions / total_sessions * 100) if total_sessions > 0 else 100.0
        
        if success_rate >= 95.0:
            rate_color = "#10b981"
        elif success_rate >= 80.0:
            rate_color = "#f59e0b"
        else:
            rate_color = "#ef4444"
            
        self.card_total_sessions.set_value(total_sessions)
        self.card_files_synced.set_value(total_copied)
        self.card_total_data.set_value(fmt_size(total_bytes))
        self.card_success_rate.set_value(f"{success_rate:.1f}%", rate_color)
        
        self.lbl_session_count.setText(f"Showing {total_sessions} of {total_sessions} sessions")
        self.search_input.clear()
        
        if total_sessions == 0:
            self.hist_container.setCurrentWidget(self.empty_state)
        else:
            self.hist_container.setCurrentWidget(self.hist_scroll)

    def _parse_size(self, size_str):
        try:
            parts = size_str.strip().split()
            if len(parts) != 2:
                return 0.0
            val, unit = float(parts[0]), parts[1].upper()
            if "GB" in unit: return val * (1 << 30)
            if "MB" in unit: return val * (1 << 20)
            if "KB" in unit: return val * 1024
            return val
        except Exception:
            return 0.0

class SettingsPage(QWidget):
    """Redesigned Multi-Category Settings Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Header Title
        lbl_title = QLabel("Settings")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        lbl_sub = QLabel("Adjust performance, default filter exclusions, and advanced parameters.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_sub)

        # Inner split layout
        split = QSplitter(Qt.Horizontal)
        split.setObjectName("settings_splitter")

        # Left: categories list
        self.cats_list = QTableWidget(4, 1)
        self.cats_list.setObjectName("settings_nav")
        self.cats_list.horizontalHeader().setVisible(False)
        self.cats_list.verticalHeader().setVisible(False)
        self.cats_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.cats_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cats_list.setColumnWidth(0, 150)
        self.cats_list.setFixedWidth(160)
        self.cats_list.setSelectionMode(QTableWidget.SingleSelection)
        self.cats_list.verticalHeader().setDefaultSectionSize(40)
        self.cats_list.setShowGrid(False)

        navs = ["  General", "  Performance", "  File Rules", "  Advanced"]
        for idx, text in enumerate(navs):
            item = QTableWidgetItem(text)
            item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.cats_list.setItem(idx, 0, item)
        self.cats_list.selectRow(0)
        self.cats_list.itemSelectionChanged.connect(self._on_category_changed)
        split.addWidget(self.cats_list)

        # Right: stacked panels
        self.stack = QStackedWidget()
        self.stack.setObjectName("settings_stack")

        # Category 1: General Settings Panel
        self.p_general = QFrame()
        self.p_general.setObjectName("settings_pane")
        pg_lay = QVBoxLayout(self.p_general)
        pg_lay.setContentsMargins(20, 20, 20, 20)
        pg_lay.setSpacing(16)

        lbl_g = QLabel("GENERAL SETTINGS")
        lbl_g.setObjectName("card_header")
        lbl_g.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pg_lay.addWidget(lbl_g)

        self.opt_dark_mode = QCheckBox("Use Dark Theme Mode")
        self.opt_dark_mode.setObjectName("opt_check")
        self.opt_dark_mode.setChecked(True)
        self.opt_dark_mode.stateChanged.connect(self._toggle_dark_mode_settings)
        
        row1 = self._make_setting_row(
            "Interface Theme Mode",
            "Toggle between dark mode (sleek, low-light) and light mode (high contrast) color palettes.",
            self.opt_dark_mode
        )
        pg_lay.addWidget(row1)

        self.opt_startup = QCheckBox("Start with Windows")
        self.opt_startup.setObjectName("opt_check")
        self.opt_startup.stateChanged.connect(self._on_startup_checkbox_changed)
        row2 = self._make_setting_row(
            "Launch on Windows Startup",
            "Automatically launch the directory background sync scan scheduler when Windows starts up.",
            self.opt_startup
        )
        pg_lay.addWidget(row2)

        self.opt_clean_session = QCheckBox("Start with a clean session")
        self.opt_clean_session.setObjectName("opt_check")
        self.opt_clean_session.stateChanged.connect(self._on_settings_checkbox_changed)
        row_clean = self._make_setting_row(
            "Clean Session Startup",
            "Do not restore source/destination directories and filters on startup.",
            self.opt_clean_session
        )
        pg_lay.addWidget(row_clean)
        
        pg_lay.addStretch()
        self.stack.addWidget(self.p_general)

        # Category 2: Performance
        self.p_perf = QFrame()
        self.p_perf.setObjectName("settings_pane")
        pp_lay = QVBoxLayout(self.p_perf)
        pp_lay.setContentsMargins(20, 20, 20, 20)
        pp_lay.setSpacing(16)

        lbl_p = QLabel("PERFORMANCE & SCALING")
        lbl_p.setObjectName("card_header")
        lbl_p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pp_lay.addWidget(lbl_p)

        # Thread count slider
        t_row = QHBoxLayout()
        self.thread_slider = QSlider(Qt.Horizontal)
        self.thread_slider.setRange(1, 8)
        self.thread_slider.setValue(3)
        self.thread_lbl = QLabel("3 threads")
        self.thread_lbl.setFixedWidth(80)
        self.thread_slider.valueChanged.connect(self._on_slider_changed)
        t_row.addWidget(self.thread_slider)
        t_row.addWidget(self.thread_lbl)
        
        t_widget = QWidget()
        t_w_lay = QHBoxLayout(t_widget)
        t_w_lay.setContentsMargins(0, 0, 0, 0)
        t_w_lay.addLayout(t_row)

        row3 = self._make_setting_row(
            "Worker Thread Limits",
            "Define the maximum concurrent write worker threads used during file copy. Higher values speed up sync but increase disk load.",
            t_widget
        )
        pp_lay.addWidget(row3)
        pp_lay.addStretch()
        self.stack.addWidget(self.p_perf)

        # Category 3: File Rules Exclusions list
        self.p_rules = QFrame()
        self.p_rules.setObjectName("settings_pane")
        pr_lay = QVBoxLayout(self.p_rules)
        pr_lay.setContentsMargins(20, 20, 20, 20)
        pr_lay.setSpacing(12)

        lbl_r = QLabel("FILE EXCLUSION CONSTRAINTS")
        lbl_r.setObjectName("card_header")
        lbl_r.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pr_lay.addWidget(lbl_r)

        self.txt_excl = QTextEdit()
        self.txt_excl.setObjectName("log_area")
        self.txt_excl.setPlaceholderText(".tmp\n.log\n.ds_store")
        
        self.save_excl_btn = QPushButton("Save Exclusions")
        self.save_excl_btn.setObjectName("mini_btn")
        self.save_excl_btn.setFixedHeight(30)
        self.save_excl_btn.clicked.connect(self._save_exclusions)

        rule_widget = QWidget()
        rule_w_lay = QVBoxLayout(rule_widget)
        rule_w_lay.setContentsMargins(0, 0, 0, 0)
        rule_w_lay.addWidget(self.txt_excl)
        rule_w_lay.addWidget(self.save_excl_btn)

        row4 = self._make_setting_row(
            "File Exclusion Extensions",
            "Define file extensions to ignore during directory synchronization. Files matching these patterns will not be compared or copied.",
            rule_widget
        )
        pr_lay.addWidget(row4)
        self.stack.addWidget(self.p_rules)

        # Category 4: Advanced
        self.p_adv = QFrame()
        self.p_adv.setObjectName("settings_pane")
        pa_lay = QVBoxLayout(self.p_adv)
        pa_lay.setContentsMargins(20, 20, 20, 20)
        pa_lay.setSpacing(16)

        lbl_a = QLabel("ADVANCED PARAMETERS")
        lbl_a.setObjectName("card_header")
        lbl_a.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pa_lay.addWidget(lbl_a)

        self.opt_verify = QCheckBox("Verify integrity via MD5")
        self.opt_verify.setObjectName("opt_check")
        self.opt_verify.setChecked(False)
        self.opt_verify.stateChanged.connect(self._on_settings_checkbox_changed)
        
        row5 = self._make_setting_row(
            "Enable MD5 Verification",
            "Verify copied files using MD5 cryptographic checksum hashes to guarantee that source and destination files are identical.",
            self.opt_verify
        )
        pa_lay.addWidget(row5)

        self.opt_renames = QCheckBox("Enable atomic safe renames")
        self.opt_renames.setObjectName("opt_check")
        self.opt_renames.setChecked(True)
        self.opt_renames.stateChanged.connect(self._on_settings_checkbox_changed)
        
        row6 = self._make_setting_row(
            "Use Safe Renames",
            "Perform write operations to a temporary file first, then atomically rename it to prevent half-written files in case of interruption.",
            self.opt_renames
        )
        pa_lay.addWidget(row6)
        pa_lay.addStretch()
        self.stack.addWidget(self.p_adv)

        split.addWidget(self.stack)
        lay.addWidget(split, 1)

    def _make_setting_row(self, title_text, desc_text, control_widget):
        card = QFrame()
        card.setObjectName("setting_row_card")
        
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 16, 16, 16)
        card_lay.setSpacing(12)
        
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_lay = QHBoxLayout(header_widget)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(12)
        
        text_w = QWidget()
        text_w.setStyleSheet("background: transparent;")
        text_lay = QVBoxLayout(text_w)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(4)
        
        title_lbl = QLabel(title_text)
        title_lbl.setObjectName("setting_title_lbl")
        
        desc_lbl = QLabel(desc_text)
        desc_lbl.setObjectName("setting_desc_lbl")
        desc_lbl.setWordWrap(True)
        
        text_lay.addWidget(title_lbl)
        text_lay.addWidget(desc_lbl)
        
        header_lay.addWidget(text_w, 1)
        
        is_checkbox = isinstance(control_widget, QCheckBox)
        
        if is_checkbox:
            control_widget.setText("") # Strip text
            control_widget.setStyleSheet("background: transparent;")
            header_lay.addWidget(control_widget)
            card_lay.addWidget(header_widget)
        else:
            card_lay.addWidget(header_widget)
            control_widget.setStyleSheet("background: transparent;")
            card_lay.addWidget(control_widget)
            
        return card

    def _on_category_changed(self):
        row = self.cats_list.currentRow()
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def _on_slider_changed(self, v):
        self.thread_lbl.setText(f"{v} threads")
        self.main_win.worker.threads = v
        self.main_win._save_settings()

    def _on_settings_checkbox_changed(self, state):
        self.main_win._save_settings()

    def _on_startup_checkbox_changed(self, state):
        enabled = (state == Qt.Checked)
        self.main_win._set_windows_startup(enabled)
        self.main_win._save_settings()

    def _toggle_dark_mode_settings(self, state=None):
        is_dark = self.opt_dark_mode.isChecked()
        self.main_win.dark_mode = is_dark
        self.main_win._apply_theme()
        if hasattr(self.main_win, "missing_files") and self.main_win.missing_files:
            self.main_win._populate_table(self.main_win.missing_files)
        self.main_win._load_history()
        self.main_win._save_settings()

    def _save_exclusions(self):
        excl = []
        for line in self.txt_excl.toPlainText().splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                if not line.startswith("."): line = "." + line
                excl.append(line)
        self.main_win.excl_exts = excl
        self.main_win._save_settings()
        self.main_win._add_log(f"Settings: Updated exclusions list.", "info")

# ───────────────────────────────────────────────
# MAIN WINDOW
# ───────────────────────────────────────────────
class SmartSyncApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker        = SyncWorker()
        self.missing_files = []
        self.settings      = QSettings("SmartSync", "AppV3")
        self.dark_mode     = True
        self.excl_exts     = list(DEFAULT_EXCLUDES)
        self.src_file_count = 0
        self.src_size      = 0
        self.dst_file_count = 0
        self.dst_size      = 0
        self.sidebar_collapsed = self.settings.value("sidebar_collapsed", False, type=bool)
        
        # Operational workflow stage
        self.current_workflow_state = "Ready"
        
        # Operational metrics tracking
        self.sync_total_files = 0
        self.sync_total_size = 0
        self.sync_copied_files = 0
        self.sync_copied_size = 0
        self.sync_start_time = 0.0
        self.sync_last_time = 0.0
        self.sync_last_size = 0
        self.sync_curr_speed = 0.0

        self._setup_signals()
        self._setup_tray()
        self._build_ui()
        self._load_settings()
        self._apply_theme()

        self.setWindowTitle(f"{APP_NAME} v{APP_VER}")
        self.setMinimumSize(1120, 760)
        self.resize(1200, 820)

    def _setup_signals(self):
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.log_signal.connect(self._on_log)
        self.worker.scan_done.connect(self._on_scan_done)
        self.worker.sync_done.connect(self._on_sync_done)
        self.worker.error_signal.connect(self._on_error)
        self.worker.file_status_changed.connect(self._on_file_status_changed)
        self.worker.consec_fail_signal.connect(self._on_consec_failures)

    def _setup_tray(self):
        from PySide6.QtWidgets import QStyle
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip(APP_NAME)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        m = QMenu()
        a1 = QAction("Show app window", self); a1.triggered.connect(self.show)
        a2 = QAction("Exit app", self); a2.triggered.connect(QApplication.quit)
        m.addAction(a1); m.addSeparator(); m.addAction(a2)
        self.tray.setContextMenu(m)
        self.tray.show()

    # ══════════════════════════════════════════
    # BUILD UI
    # ══════════════════════════════════════════
    def _build_ui(self):
        root_w = QWidget()
        self.setCentralWidget(root_w)
        main_lay = QHBoxLayout(root_w)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # ──────────────────────────────────────
        # SIDEBAR PANEL (240px Fixed)
        # ──────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        sb_lay = QVBoxLayout(self.sidebar)
        sb_lay.setContentsMargins(0, 16, 0, 16)
        sb_lay.setSpacing(8)

        # App Identity / Logo
        self.logo_lay = QHBoxLayout()
        self.logo_lay.setContentsMargins(20, 0, 20, 8)
        self.logo_lbl = QLabel(IconManager.get("folder"))
        self.logo_lbl.setFont(IconManager.get_font(18))
        self.app_title = QLabel(APP_NAME)
        self.app_title.setObjectName("app_title")
        self.app_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.logo_lay.addWidget(self.logo_lbl)
        self.logo_lay.addWidget(self.app_title)
        self.logo_lay.addStretch()
        sb_lay.addLayout(self.logo_lay)



        # Scrollable Nav container
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}

        navs = [
            ("folder", "Folder Setup", 0),
            ("scan", "Scan Results", 1),
            ("queue", "Sync Queue", 2),
            ("dashboard", "Dashboard", 3),
            ("history", "History Logs", 4),
            ("settings", "Settings", 5)
        ]

        for icon_name, name, index in navs:
            btn = NavItemWidget(icon_name, name, index, self)
            btn.clicked.connect(lambda checked, idx=index: self._on_nav_clicked(idx))
            self.nav_group.addButton(btn, index)
            sb_lay.addWidget(btn)
            self.nav_buttons[index] = btn

        sb_lay.addStretch()

        # Sidebar footer info details
        self.foot_frame = QFrame()
        self.foot_frame.setObjectName("sidebar_footer")
        ff_lay = QVBoxLayout(self.foot_frame)
        ff_lay.setContentsMargins(16, 8, 16, 8)
        ff_lay.setSpacing(6)
        
        self.lbl_tray_status = QLabel("Ready — Offline")
        self.lbl_tray_status.setStyleSheet("color: #475569; font-size: 11px;")
        ff_lay.addWidget(self.lbl_tray_status)
        
        self.btn_collapse = QPushButton(f"{IconManager.get('arrow_left')}  Collapse Sidebar")
        self.btn_collapse.setObjectName("collapse_btn")
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.setFixedHeight(28)
        self.btn_collapse.clicked.connect(self._toggle_sidebar)
        ff_lay.addWidget(self.btn_collapse)
        
        sb_lay.addWidget(self.foot_frame)

        main_lay.addWidget(self.sidebar)

        # ──────────────────────────────────────
        # MAIN CLIENT PANEL & TOP BAR
        # ──────────────────────────────────────
        client_w = QWidget()
        client_lay = QVBoxLayout(client_w)
        client_lay.setContentsMargins(0, 0, 0, 0)
        client_lay.setSpacing(0)

        # Top bar header
        client_lay.addWidget(self._make_topbar())

        # Page workspace stacked views
        self.stack = QStackedWidget()
        self.stack.setObjectName("page_stacked_workspace")
        
        self.dashboard_page = DashboardPage(self)
        self.folder_setup_page = FolderSetupPage(self)
        self.scan_results_page = ScanResultsPage(self)
        self.sync_queue_page = SyncQueuePage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)

        self.stack.addWidget(self.folder_setup_page) # index 0
        self.stack.addWidget(self.scan_results_page) # index 1
        self.stack.addWidget(self.sync_queue_page) # index 2
        self.stack.addWidget(self.dashboard_page) # index 3
        self.stack.addWidget(self.history_page) # index 4
        self.stack.addWidget(self.settings_page) # index 5

        client_lay.addWidget(self.stack, 1)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("status_bar")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — Select directories on Folder Setup to scan.")
        client_lay.addWidget(self.status_bar)

        main_lay.addWidget(client_w, 1)

        # Select first nav item by default
        self.nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(0)

        # Apply sidebar collapsed state
        self._update_sidebar_layout()

        # Initialize UI tables and empty states
        self._clear_table()

    def _make_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(50)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 16, 0)
        h.setSpacing(12)

        # Left: Breadcrumbs
        self.lbl_crumbs = QLabel("Workspace  ›  Setup")
        self.lbl_crumbs.setObjectName("breadcrumb_lbl")
        self.lbl_crumbs.setFont(QFont("Segoe UI", 9, QFont.Bold))
        h.addWidget(self.lbl_crumbs)

        h.addStretch()

        # Middle: Global Search
        self.global_search = QLineEdit()
        self.global_search.setObjectName("global_search_input")
        self.global_search.setPlaceholderText("Search files globally...")
        self.global_search.setFixedWidth(200)
        self.global_search.setFixedHeight(28)
        self.global_search.textChanged.connect(self._on_global_search_changed)
        h.addWidget(self.global_search)

        # Sync status badge
        self.top_sync_status = QLabel("●  Sync Idle")
        self.top_sync_status.setObjectName("top_sync_status")
        self.top_sync_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        h.addWidget(self.top_sync_status)

        # Last sync label
        self.lbl_last_sync = QLabel("Last Sync: Never")
        self.lbl_last_sync.setObjectName("lbl_last_sync")
        self.lbl_last_sync.setStyleSheet("color: #64748b; font-size: 11px;")
        h.addWidget(self.lbl_last_sync)

        # Notifications Button
        self.notif_btn = QPushButton(IconManager.get("bell"))
        self.notif_btn.setObjectName("icon_btn")
        self.notif_btn.setFont(IconManager.get_font(11))
        self.notif_btn.setFixedSize(28, 28)
        self.notif_btn.setCursor(Qt.PointingHandCursor)
        self.notif_btn.clicked.connect(self._show_notifications_dialog)
        h.addWidget(self.notif_btn)

        # Theme toggle button
        self.theme_btn = QPushButton(IconManager.get("sun"))
        self.theme_btn.setObjectName("icon_btn")
        self.theme_btn.setFont(IconManager.get_font(11))
        self.theme_btn.setFixedSize(28, 28)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        h.addWidget(self.theme_btn)

        return bar



    def _toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._update_sidebar_layout()
        self.settings.setValue("sidebar_collapsed", self.sidebar_collapsed)

    def _update_sidebar_layout(self):
        collapsed = self.sidebar_collapsed
        if collapsed:
            self.sidebar.setFixedWidth(64)
            self.app_title.setVisible(False)
            self.logo_lay.setContentsMargins(0, 0, 0, 8)
            self.logo_lbl.setAlignment(Qt.AlignCenter)
            self.lbl_tray_status.setVisible(False)
            self.btn_collapse.setText(IconManager.get("arrow_right"))
            self.btn_collapse.setToolTip("Expand Sidebar")
            self.btn_collapse.setStyleSheet("text-align: center;")
        else:
            self.sidebar.setFixedWidth(240)
            self.app_title.setVisible(True)
            self.logo_lay.setContentsMargins(20, 0, 20, 8)
            self.logo_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.lbl_tray_status.setVisible(True)
            self.btn_collapse.setText(f"{IconManager.get('arrow_left')}  Collapse Sidebar")
            self.btn_collapse.setToolTip("")
            self.btn_collapse.setStyleSheet("text-align: left;")
            
        for idx, btn in self.nav_buttons.items():
            btn.set_collapsed(collapsed)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            key = event.key()
            if Qt.Key_1 <= key <= Qt.Key_6:
                idx = key - Qt.Key_1
                self._on_nav_clicked(idx)
                event.accept()
                return
        super().keyPressEvent(event)

    def _on_global_search_changed(self, text):
        self.scan_results_page.search_input.setText(text)

    def _show_notifications_dialog(self):
        QMessageBox.information(
            self, "System Notifications",
            "Smart File Sync Notifications:\n\n"
            "• Background metadata monitor is running in idle mode.\n"
            "• All synchronization engines verified."
        )

    def _on_nav_clicked(self, index):
        self.stack.setCurrentIndex(index)
        btn = self.nav_group.button(index)
        if btn: btn.setChecked(True)
        
        # Update breadcrumbs based on navigation selections
        crumbs = [
            "Workspace  ›  Setup",
            "Workspace  ›  Scan Results",
            "Workspace  ›  Sync Queue",
            "Workspace  ›  Dashboard",
            "Workspace  ›  Sync History",
            "Workspace  ›  Settings"
        ]
        if index < len(crumbs):
            self.lbl_crumbs.setText(crumbs[index])

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()
        self.settings_page.opt_dark_mode.blockSignals(True)
        self.settings_page.opt_dark_mode.setChecked(self.dark_mode)
        self.settings_page.opt_dark_mode.blockSignals(False)

        # Refresh items visibility colors
        if self.missing_files:
            self._populate_table(self.missing_files)
        self._load_history()
        self._save_settings()

    # ══════════════════════════════════════════
    # INTERACTION HANDLERS & BUSINESS LOGIC
    # ══════════════════════════════════════════
    def _open_exclude_dialog(self):
        # Focus rule rules settings tab directly
        self._on_nav_clicked(5) # Settings
        self.settings_page.cats_list.selectRow(2) # File Rules

    def _on_scan_click(self):
        src = self.folder_setup_page.card_src.input.text().strip()
        dest = self.folder_setup_page.card_dst.input.text().strip()
        if not src or not dest:
            QMessageBox.warning(self, "Invalid Inputs", "Please select valid Source and Destination directories!"); return
        if os.path.normcase(src) == os.path.normcase(dest):
            QMessageBox.warning(self, "Validation Error", "Source and Destination paths cannot be identical."); return

        # Auto create target destination directory if missing
        if not os.path.isdir(dest):
            r = QMessageBox.question(
                self, "Directory Missing",
                f"Destination folder not found:\n{dest}\n\nCreate directory path now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if r == QMessageBox.Yes:
                try: os.makedirs(dest, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "OS Write Error", f"Failed to create directory:\n{e}"); return
            else: return

        # Reset states
        self.missing_files = []
        self._clear_table()
        self._set_running(True)
        
        # Start Worker thread
        self.worker.setup_scan(
            src, dest,
            self.folder_setup_page.filter_combo.currentText(),
            self.excl_exts
        )
        self.worker.start()
        self._update_status_indicator("Scanning")
        self.dashboard_page.workflow_tracker.set_active_step(2)
        
        # Navigate automatically to comparison page
        self._on_nav_clicked(1)

    def _on_sync_all(self):
        self._start_sync(self.missing_files)

    def _on_sync_sel(self):
        sel = self._get_checked()
        if not sel:
            QMessageBox.information(self, "Items Empty", "Check selection items inside the comparisons grid to sync."); return
        self._start_sync(sel)

    def _start_sync(self, files):
        if not files: return
        src = self.folder_setup_page.card_src.input.text().strip()
        dest = self.folder_setup_page.card_dst.input.text().strip()
        total_size = sum(f.get("size", 0) for f in files)
        dry = self.folder_setup_page.dry_run_chk.isChecked()
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Confirm Synchronization")
        
        info_text = (
            f"<b>Source:</b><br/>{src}<br/><br/>"
            f"<b>Destination:</b><br/>{dest}<br/><br/>"
            f"<b>Files Selected:</b> {len(files)}<br/>"
            f"<b>Transfer Size:</b> {fmt_size(total_size)}<br/>"
            f"<b>Dry Run Mode:</b> {'Enabled' if dry else 'Disabled'}<br/><br/>"
            "Continue synchronization?"
        )
        msg.setText(info_text)
        
        start_btn = msg.addButton("Start Sync", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        
        msg.setDefaultButton(start_btn)
        msg.exec()
        
        if msg.clickedButton() != start_btn:
            return
        
        self.sync_start_time = time.time()
        self._set_running(True)
        self.sync_queue_page.reset_queues()
        self.sync_queue_page.queue_container.setCurrentWidget(self.sync_queue_page.queue_tabs)
        
        # Navigate to Sync Queue page
        self._on_nav_clicked(2)
        
        self.worker.setup_sync(
            self.folder_setup_page.card_src.input.text().strip(),
            self.folder_setup_page.card_dst.input.text().strip(),
            files, dry,
            self.settings_page.thread_slider.value(),
            self.settings_page.opt_renames.isChecked(),
            self.settings_page.opt_verify.isChecked()
        )
        self.worker.start()
        self._update_status_indicator("Syncing")
        self.dashboard_page.workflow_tracker.set_active_step(4)

    def _on_pause_click(self):
        if not self.worker.isRunning(): return
        if self.worker.is_paused:
            self.worker.resume()
            self.sync_queue_page.btn_pause.setText("Pause Sync")
            self.status_bar.showMessage("Sync active...")
        else:
            self.worker.pause()
            self.sync_queue_page.btn_pause.setText("Resume Sync")
            self.status_bar.showMessage("Sync paused — Press Resume to write.")

    def _on_stop_click(self):
        self.worker.stop()
        self.sync_queue_page.btn_pause.setText("Pause Sync")
        self.status_bar.showMessage("Stopping sync worker...")

    # ══════════════════════════════════════════
    # THREADING CALL BACKS & VIEW UPDATES
    # ══════════════════════════════════════════
    def _on_progress(self, pct, detail):
        self.sync_queue_page.progress_bar.setValue(pct)
        self.sync_queue_page.lbl_pct.setText(f"{pct}%")
        self.sync_queue_page.lbl_detail.setText(detail)
        self.status_bar.showMessage(detail)
        
        if hasattr(self, "worker") and self.worker.isRunning() and self.worker.mode == "sync":
            now = time.time()
            elapsed = max(now - self.sync_start_time, 0.001)
            
            avg_speed = self.sync_copied_size / elapsed
            files_per_sec = self.sync_copied_files / elapsed
            
            dt = max(now - getattr(self, "sync_last_time", self.sync_start_time), 0.0001)
            db = max(self.sync_copied_size - getattr(self, "sync_last_size", 0), 0)
            
            curr_speed = db / dt
            prev_curr = getattr(self, "sync_curr_speed", 0.0)
            if prev_curr == 0.0:
                self.sync_curr_speed = curr_speed
            else:
                self.sync_curr_speed = 0.3 * curr_speed + 0.7 * prev_curr
                
            self.sync_last_time = now
            self.sync_last_size = self.sync_copied_size
            
            remaining_files = max(self.sync_total_files - self.sync_copied_files, 0)
            if self.sync_curr_speed > 1024:
                remaining_size = max(self.sync_total_size - self.sync_copied_size, 0)
                eta = remaining_size / self.sync_curr_speed
            elif files_per_sec > 0:
                eta = remaining_files / files_per_sec
            else:
                eta = -1.0
                
            self.sync_queue_page.update_operational_metrics(
                self.sync_curr_speed,
                avg_speed,
                files_per_sec,
                eta,
                self.sync_copied_size,
                self.sync_total_size
            )

    def _on_log(self, msg, kind):
        self._add_log(msg, kind)

    def _on_scan_done(self, missing):
        self.missing_files = missing
        self._set_running(False)

        # Update stats
        self.dashboard_page.update_stats(
            self.src_file_count,
            len(missing),
            sum(1 for f in missing if f["reason"] in ("Modified", "Size Differs")),
            0,
            0
        )
        self._populate_table(missing)
        
        # Update last scan time
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.settings.setValue("last_scan_time", now_str)
        self.dashboard_page.lbl_last_scan.setText(f"Last Scan: {now_str}")
        
        self._save_settings()
        
        # Update status indicators and active workflow steps
        self._update_status_indicator("Reviewing")
        self.dashboard_page.workflow_tracker.set_active_step(3)
        
        # Update sidebar badge for Scan Results (index 1)
        self.nav_buttons[1].set_badge(len(missing))

    def _on_sync_done(self, s):
        self._set_running(False)
        self.sync_queue_page.btn_pause.setEnabled(False)
        self.sync_queue_page.btn_stop.setEnabled(False)

        # Refresh dashboard stats
        self.dashboard_page.update_stats(
            self.src_file_count,
            0, 0, s["copied"], s["errors"]
        )

        # Clear sidebar badge for Scan Results (index 1)
        self.nav_buttons[1].set_badge(0)
        
        # Update last sync time in top bar Command Center
        now_str = datetime.now().strftime("%H:%M")
        self.lbl_last_sync.setText(f"Last Sync: {now_str}")

        # Update Last Sync Summary Card
        duration = time.time() - self.sync_start_time
        dur_str = f"{duration:.1f}s" if duration < 60 else f"{int(duration)//60}m {int(duration)%60}s"
        now_full_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if s["errors"] > 0:
            status_text = f"Complete w/ {s['errors']} errors"
            self._update_status_indicator("Error")
            self.dashboard_page.update_last_error(f"Sync completed with {s['errors']} errors")
        else:
            status_text = "Success"
            self._update_status_indicator("Completed")
            self.dashboard_page.update_last_error("None")
            
        self.dashboard_page.update_last_sync_summary(status_text, now_full_str, s["copied"], s["copied_size"], dur_str)
        
        # Save to settings
        self.settings.setValue("last_sync_status", status_text)
        self.settings.setValue("last_sync_time", now_full_str)
        self.settings.setValue("last_sync_files", s["copied"])
        self.settings.setValue("last_sync_size", s["copied_size"])
        self.settings.setValue("last_sync_duration", dur_str)

        self.tray.showMessage(
            f"{APP_NAME} — Complete",
            f"✅ {s['copied']} synced  |  ❌ {s['errors']} errors",
            QSystemTrayIcon.Information, 4000
        )
        self._cleanup_orphaned_tmps(self.folder_setup_page.card_dst.input.text().strip())
        self._load_history()

        QMessageBox.information(
            self, "Operation Complete",
            f"✅  Synced : {s['copied']} files\n"
            f"❌  Errors : {s['errors']}\n"
            f"📦  Size   : {s['copied_size']}"
        )

    def _on_error(self, msg):
        self._set_running(False)
        self._add_log(f"💥 ERROR: {msg}", "error")
        
        # Update Last Sync Summary Card as failed
        duration = time.time() - self.sync_start_time
        dur_str = f"{duration:.1f}s" if duration < 60 else f"{int(duration)//60}m {int(duration)%60}s"
        now_full_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = f"Error: {msg[:20]}..."
        
        self.dashboard_page.update_last_sync_summary(status_text, now_full_str, 0, "0 B", dur_str)
        
        # Update status indicators and error logs
        self._update_status_indicator("Error")
        self.dashboard_page.update_last_error(msg)
        self._cleanup_orphaned_tmps(self.folder_setup_page.card_dst.input.text().strip())
        
        # Save to settings
        self.settings.setValue("last_sync_status", status_text)
        self.settings.setValue("last_sync_time", now_full_str)
        self.settings.setValue("last_sync_files", 0)
        self.settings.setValue("last_sync_size", "0 B")
        self.settings.setValue("last_sync_duration", dur_str)
        
        QMessageBox.critical(self, "Process Error", msg)

    def _on_file_status_changed(self, rel_path, status, error_msg):
        # Accumulate status change event in high-speed buffer
        if not hasattr(self, "_status_update_queue"):
            self._status_update_queue = []
        if not hasattr(self, "_status_queue_timer"):
            self._status_queue_timer = QTimer(self)
            self._status_queue_timer.setInterval(40) # 40ms interval (~25 updates/sec max for butter-smooth UI)
            self._status_queue_timer.timeout.connect(self._flush_queue_updates)
            
        self._status_update_queue.append((rel_path, status, error_msg))
        if not self._status_queue_timer.isActive():
            self._status_queue_timer.start()

    def _flush_queue_updates(self):
        if not hasattr(self, "_status_update_queue") or not self._status_update_queue:
            if hasattr(self, "_status_queue_timer"):
                self._status_queue_timer.stop()
            return
            
        batch = self._status_update_queue
        self._status_update_queue = []
        
        files_dict = {f["rel_path"]: f for f in self.missing_files}
        
        for rel_path, status, error_msg in batch:
            fi = files_dict.get(rel_path, {})
            name = Path(rel_path).name
            size_str = fi.get("size_str", "—")
            size = fi.get("size", 0)
            
            if status in ("completed", "failed"):
                self.sync_copied_files += 1
                self.sync_copied_size += size
                
            if status == "pending":
                self._add_row_to_queue(self.sync_queue_page.tbl_pending, name, size_str, rel_path, "Queued", self.sync_queue_page._pending_map)
            elif status == "processing":
                self._remove_row_from_queue(self.sync_queue_page.tbl_pending, rel_path, self.sync_queue_page._pending_map)
                self._add_row_to_queue(self.sync_queue_page.tbl_processing, name, size_str, rel_path, "Writing...", self.sync_queue_page._active_map)
            elif status == "completed":
                self._remove_row_from_queue(self.sync_queue_page.tbl_processing, rel_path, self.sync_queue_page._active_map)
                self._add_row_to_queue(self.sync_queue_page.tbl_completed, name, size_str, rel_path, "Done", self.sync_queue_page._completed_map)
            elif status == "failed":
                self._remove_row_from_queue(self.sync_queue_page.tbl_processing, rel_path, self.sync_queue_page._active_map)
                self._add_row_to_queue(self.sync_queue_page.tbl_failed, name, size_str, rel_path, error_msg or "Error", self.sync_queue_page._failed_map)
                
        self.sync_queue_page.update_tab_titles()

    def _add_row_to_queue(self, table, name, size_str, rel_path, details, row_map=None):
        r = table.rowCount()
        table.setRowCount(r + 1)
        if row_map is not None:
            row_map[rel_path] = r
        
        ext = Path(rel_path).suffix.lower()
        icon = "📄"
        if ext in FILE_FILTERS["Photos"]:
            icon = "🖼️"
        elif ext in FILE_FILTERS["Videos"]:
            icon = "🎥"
        elif ext in FILE_FILTERS["Audio"]:
            icon = "🎵"
        elif ext in [".pdf"]:
            icon = "📕"
        elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            icon = "📦"
        elif ext in [".txt", ".csv", ".json", ".xml", ".ini", ".log"]:
            icon = "📝"
        elif ext in [".exe", ".msi", ".bat", ".cmd", ".sh", ".py"]:
            icon = "⚙️"
            
        display_name = f"  {icon}  {name}"
        dark = self.dark_mode
        text_color = QColor("#f8fafc") if dark else QColor("#1e293b")
        dim_color  = QColor("#94a3b8") if dark else QColor("#64748b")
        bold_font   = QFont("Segoe UI", 10, QFont.Bold)
        normal_font = QFont("Segoe UI", 10)
        
        item_name = QTableWidgetItem(display_name)
        item_name.setFont(bold_font)
        item_name.setForeground(text_color)
        
        item_size = QTableWidgetItem(size_str)
        item_size.setFont(normal_font)
        item_size.setForeground(dim_color)
        item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        item_path = QTableWidgetItem(rel_path)
        item_path.setFont(normal_font)
        item_path.setForeground(dim_color)
        
        item_details = QTableWidgetItem(details)
        item_details.setFont(bold_font)
        
        if "Done" in details:
            status_color = QColor("#10b981")
        elif "Failed" in details or "Error" in details:
            status_color = QColor("#ef4444")
        elif "Writing" in details:
            status_color = QColor("#3b82f6")
        else:
            status_color = QColor("#f59e0b")
        item_details.setForeground(status_color)
        
        table.setItem(r, 0, item_name)
        table.setItem(r, 1, item_size)
        table.setItem(r, 2, item_path)
        table.setItem(r, 3, item_details)

    def _remove_row_from_queue(self, table, rel_path, row_map=None):
        if row_map is not None and rel_path in row_map:
            target_row = row_map.pop(rel_path)
            if 0 <= target_row < table.rowCount():
                item = table.item(target_row, 2)
                if item and item.text() == rel_path:
                    table.removeRow(target_row)
                    for p, idx in list(row_map.items()):
                        if idx > target_row:
                            row_map[p] = idx - 1
                    return
        for r in range(table.rowCount()):
            item = table.item(r, 2)
            if item and item.text() == rel_path:
                table.removeRow(r)
                if row_map is not None:
                    row_map.pop(rel_path, None)
                    for p, idx in list(row_map.items()):
                        if idx > r:
                            row_map[p] = idx - 1
                break


    # ══════════════════════════════════════════
    # UTILITIES AND COMPONENT CONFIG
    # ══════════════════════════════════════════
    def _populate_table(self, files):
        # Calculate stat chip values immediately
        missing_count = sum(1 for f in files if f["reason"] == "Missing")
        changed_count = sum(1 for f in files if f["reason"] in ("Modified", "Size Differs"))
        error_count = sum(1 for f in files if f["reason"] == "Stat Error")

        self.scan_results_page.update_stat_chips(
            total=len(files),
            missing=missing_count,
            changed=changed_count,
            errors=error_count
        )

        # Populate model
        self.scan_results_page.source_model.set_files(files)
        self.scan_results_page._clear_detail_panel()
        self.scan_results_page._update_table_visibility()
        self.scan_results_page._filter_results_table()

    def _clear_table(self):
        self.scan_results_page.source_model.set_files([])
        self.scan_results_page._update_table_visibility()

    def _get_checked(self):
        checked = []
        model = self.scan_results_page.source_model
        for r in model.checked_rows:
            if r < len(model.files):
                checked.append(model.files[r])
        return checked

    def _set_running(self, running):
        self.folder_setup_page.scan_btn.setEnabled(not running)
        self.sync_queue_page.btn_pause.setEnabled(running)
        self.sync_queue_page.btn_stop.setEnabled(running)
        
        if running:
            if self.worker.mode == "scan":
                self._update_status_indicator("Scanning")
            else:
                self._update_status_indicator("Syncing")

    def _load_history(self):
        # Clear existing cards from scroll area
        layout = self.history_page.hist_list_lay
        while layout.count() > 0:
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.history_page.cards = []
        self.history_page.select_card(None)

        if not os.path.exists(LOG_FILE):
            self.history_page.update_history_stats([])
            return

        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:
            hist = []

        # Populate dashboard last error status
        if hist:
            last_hist_errors = int(hist[0].get("errors", 0))
            if last_hist_errors > 0:
                self.dashboard_page.update_last_error(f"Last sync had {last_hist_errors} errors")
            else:
                self.dashboard_page.update_last_error("None")
        else:
            self.dashboard_page.update_last_error("None")

        self.history_page.update_history_stats(hist)

        for e in hist:
            card = HistorySessionCard(e, self)
            layout.addWidget(card)
            self.history_page.cards.append(card)

        # Add stretch at the end
        layout.addStretch()

        # Toggle empty state stacked widget
        if not hist:
            self.history_page.hist_container.setCurrentWidget(self.history_page.empty_state)
        else:
            self.history_page.hist_container.setCurrentWidget(self.history_page.hist_scroll)

    def _export_csv(self):
        if not os.path.exists(LOG_FILE):
            QMessageBox.information(self,"Empty Logs","No sync events available to export."); return
        path,_ = QFileDialog.getSaveFileName(
            self,"Save CSV File", os.path.expanduser("~/sync_history.csv"), "CSV (*.csv)"
        )
        if not path: return
        try:
            with open(LOG_FILE, encoding="utf-8") as f: hist = json.load(f)
            with open(path,"w",newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=hist[0].keys())
                w.writeheader(); w.writerows(hist)
            QMessageBox.information(self,"Export Complete",f"CSV exported successfully:\n{path}")
        except Exception as e:
            QMessageBox.critical(self,"Export Error",str(e))

    def _repeat_sync(self):
        if not hasattr(self.history_page, "selected_session_data") or not self.history_page.selected_session_data:
            QMessageBox.information(self, "Select Card", "Choose a run configuration card to reload.")
            return
            
        e = self.history_page.selected_session_data
        src = e.get("source", "")
        dest = e.get("destination", "")
        filt = e.get("filter", "All Files")
        
        self.folder_setup_page.card_src.input.setText(src)
        self.folder_setup_page.card_dst.input.setText(dest)
        idx = self.folder_setup_page.filter_combo.findText(filt)
        if idx >= 0:
            self.folder_setup_page.filter_combo.setCurrentIndex(idx)
            
        # Load exclusions
        excl_str = e.get("excl", "[]")
        try:
            excl = json.loads(excl_str)
            if isinstance(excl, list):
                self.main_win.excl_exts = excl
                self.settings_page.txt_excl.setText("\n".join(excl))
        except Exception:
            pass
            
        self.folder_setup_page.card_src.reset_stats()
        self.folder_setup_page.card_dst.reset_stats()
        self._on_nav_clicked(0) # Switch back to Folder Setup


    def _open_path_in_explorer(self, path):
        path = os.path.normpath(path)
        if not os.path.exists(path):
            dir_path = os.path.dirname(path)
            if os.path.exists(dir_path): os.startfile(dir_path)
            else: QMessageBox.warning(self, "Not Found", f"Path not found: {path}")
            return
            
        if os.path.isdir(path):
            os.startfile(path)
        else:
            import subprocess
            subprocess.run(f'explorer.exe /select,"{path}"')

    def _exclude_selected_ext(self, ext):
        if not ext: return
        ext = ext.lower()
        if ext not in self.excl_exts:
            r = QMessageBox.question(
                self, "Exclude Extension?",
                f"Skip all '{ext}' files and rescan folders?",
                QMessageBox.Yes | QMessageBox.No
            )
            if r == QMessageBox.Yes:
                self.excl_exts.append(ext)
                self.settings_page.txt_excl.setText("\n".join(self.excl_exts))
                self._save_settings()
                self._on_scan_click()

    def _add_log(self, msg, kind="info"):
        self.status_bar.showMessage(msg)
        self.lbl_tray_status.setText(msg)
        self.dashboard_page.log_activity(msg, kind)

    def _update_status_indicator(self, state):
        self.current_workflow_state = state
        
        # States: "Ready", "Scanning", "Reviewing", "Syncing", "Completed", "Error"
        colors = {
            "Ready": ("#10b981", "●  Ready"),
            "Scanning": ("#3b82f6", "●  Scanning"),
            "Reviewing": ("#06b6d4", "●  Reviewing"),
            "Syncing": ("#f59e0b", "●  Syncing"),
            "Paused": ("#f59e0b", "●  Paused"),
            "Completed": ("#10b981", "●  Completed"),
            "Error": ("#ef4444", "●  Error")
        }
        
        color, text = colors.get(state, ("#94a3b8", f"●  {state}"))
        self.top_sync_status.setText(text)
        self.top_sync_status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;")
        
        # Update sidebar tray status footer
        self.lbl_tray_status.setText(f"System State: {state}")
        
        # Update dashboard stage
        self.dashboard_page.update_workflow_stage(state)
        
        # Save state to settings to persist (except transient errors)
        self.settings.setValue("current_workflow_state", state)

    # ══════════════════════════════════════════
    # SETTINGS STORAGE
    # ══════════════════════════════════════════
    def _save_settings(self):
        self.settings.setValue("src",    self.folder_setup_page.card_src.input.text())
        self.settings.setValue("dest",   self.folder_setup_page.card_dst.input.text())
        self.settings.setValue("filter", self.folder_setup_page.filter_combo.currentText())
        self.settings.setValue("dark",   self.dark_mode)
        self.settings.setValue("excl",   json.dumps(self.excl_exts))
        self.settings.setValue("threads", self.settings_page.thread_slider.value())
        self.settings.setValue("verify_md5", self.settings_page.opt_verify.isChecked())
        self.settings.setValue("safe_renames", self.settings_page.opt_renames.isChecked())
        self.settings.setValue("startup", self.settings_page.opt_startup.isChecked())
        self.settings.setValue("clean_session", self.settings_page.opt_clean_session.isChecked())
        self._saved_config = self.get_current_config()

    def _load_settings(self):
        clean_session = self.settings.value("clean_session", False, type=bool)
        self.settings_page.opt_clean_session.setChecked(clean_session)

        src_path = ""
        dst_path = ""
        
        if clean_session:
            self.folder_setup_page.card_src.input.setText("")
            self.folder_setup_page.card_dst.input.setText("")
            self.folder_setup_page.card_src.reset_stats()
            self.folder_setup_page.card_dst.reset_stats()
            self.folder_setup_page.filter_combo.setCurrentIndex(0)
        else:
            src_path = self.settings.value("src", "")
            dst_path = self.settings.value("dest", "")
            self.folder_setup_page.card_src.input.setText(src_path)
            self.folder_setup_page.card_dst.input.setText(dst_path)

            flt = self.settings.value("filter", "All Files")
            idx = self.folder_setup_page.filter_combo.findText(flt)
            if idx >= 0:
                self.folder_setup_page.filter_combo.setCurrentIndex(idx)

            def is_cache_valid(folder_id, path):
                if not path or not os.path.isdir(path):
                    return False
                cached_path = self.settings.value(f"cached_{folder_id}_path", "")
                if cached_path != path:
                    return False
                try:
                    current_mtime = os.path.getmtime(path)
                    cached_mtime = float(self.settings.value(f"cached_{folder_id}_mtime", 0.0))
                    if abs(current_mtime - cached_mtime) > 0.1:
                        return False
                except Exception:
                    return False
                return True

            # Restore cached src stats or scan
            if is_cache_valid("src", src_path):
                size = float(self.settings.value("cached_src_size", 0.0))
                count = int(self.settings.value("cached_src_count", 0))
                mod_str = self.settings.value("cached_src_mod", "N/A")
                self.src_file_count = count
                self.src_size = size
                self.folder_setup_page.card_src.update_stats(size, count, mod_str)
                try:
                    self.folder_setup_page._last_src_path = src_path
                    self.folder_setup_page._last_src_mtime = os.path.getmtime(src_path)
                except Exception:
                    pass
            else:
                if src_path and os.path.isdir(src_path):
                    self.folder_setup_page._trigger_metadata_scan("src")

            # Restore cached dst stats or scan
            if is_cache_valid("dst", dst_path):
                size = float(self.settings.value("cached_dst_size", 0.0))
                count = int(self.settings.value("cached_dst_count", 0))
                mod_str = self.settings.value("cached_dst_mod", "N/A")
                self.dst_file_count = count
                self.dst_size = size
                self.folder_setup_page.card_dst.update_stats(size, count, mod_str)
                try:
                    self.folder_setup_page._last_dst_path = dst_path
                    self.folder_setup_page._last_dst_mtime = os.path.getmtime(dst_path)
                except Exception:
                    pass
            else:
                if dst_path and os.path.isdir(dst_path):
                    self.folder_setup_page._trigger_metadata_scan("dst")

            # Validate paths to refresh launch scan state
            self.folder_setup_page._validate_paths()

            if src_path or dst_path:
                self.status_bar.showMessage("Last configuration restored", 4000)
                self._add_log("Last configuration restored", "success")
        
        self.dark_mode = self.settings.value("dark", True, type=bool)
        excl_raw = self.settings.value("excl", json.dumps(DEFAULT_EXCLUDES))
        try:    self.excl_exts = json.loads(excl_raw)
        except: self.excl_exts = list(DEFAULT_EXCLUDES)

        self.settings_page.txt_excl.setText("\n".join(self.excl_exts))
        self.settings_page.opt_dark_mode.setChecked(self.dark_mode)
        
        # Load persisted Advanced settings
        self.settings_page.opt_verify.setChecked(self.settings.value("verify_md5", False, type=bool))
        self.settings_page.opt_renames.setChecked(self.settings.value("safe_renames", True, type=bool))
        
        startup_enabled = self.settings.value("startup", False, type=bool)
        self.settings_page.opt_startup.setChecked(startup_enabled)
        self._set_windows_startup(startup_enabled)
        
        threads = int(self.settings.value("threads", 3))
        self.settings_page.thread_slider.setValue(threads)
        self.worker.threads = threads
        
        # Load last sync summary details
        last_status = self.settings.value("last_sync_status", "Never Synced")
        last_time = self.settings.value("last_sync_time", "Never")
        last_files = self.settings.value("last_sync_files", "0")
        last_size = self.settings.value("last_sync_size", "0 B")
        last_duration = self.settings.value("last_sync_duration", "—")
        self.dashboard_page.update_last_sync_summary(last_status, last_time, last_files, last_size, last_duration)

        # Trigger cleanup of orphaned temp files
        dest = self.folder_setup_page.card_dst.input.text().strip()
        if dest:
            self._cleanup_orphaned_tmps(dest)

        # Update topbar last sync label
        if last_time != "Never":
            try:
                dt_part = last_time.split()[1]
                top_time = dt_part[:5]
                self.lbl_last_sync.setText(f"Last Sync: {top_time}")
            except Exception:
                self.lbl_last_sync.setText(f"Last Sync: {last_time}")
        else:
            self.lbl_last_sync.setText("Last Sync: Never")

        self._load_history()
        self.dashboard_page.update_disk_usage(
            self.folder_setup_page.card_src.input.text().strip(),
            self.folder_setup_page.card_dst.input.text().strip()
        )
        self.dashboard_page.check_first_run()
        self._saved_config = self.get_current_config()

    def get_current_config(self):
        excl = []
        for line in self.settings_page.txt_excl.toPlainText().splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                if not line.startswith("."): line = "." + line
                excl.append(line)
        return {
            "src": self.folder_setup_page.card_src.input.text().strip(),
            "dest": self.folder_setup_page.card_dst.input.text().strip(),
            "filter": self.folder_setup_page.filter_combo.currentText(),
            "excl": sorted(excl),
            "threads": self.settings_page.thread_slider.value(),
            "verify_md5": self.settings_page.opt_verify.isChecked(),
            "safe_renames": self.settings_page.opt_renames.isChecked(),
            "startup": self.settings_page.opt_startup.isChecked(),
            "clean_session": self.settings_page.opt_clean_session.isChecked()
        }

    def _on_consec_failures(self):
        self.worker.stop()
        self._set_running(False)
        self._update_status_indicator("Error")
        self._add_log("💥 Synchronization stopped due to consecutive failures.", "error")
        QMessageBox.critical(
            self,
            "Synchronization Stopped",
            "The synchronization process was stopped automatically because 5 consecutive file operations failed.\n\n"
            "Suggested Fixes & Recovery Guidance:\n"
            "1. Verify that the destination disk is plugged in and accessible.\n"
            "2. Check if the destination drive is full or out of space.\n"
            "3. Ensure the target files are not currently open or locked by other programs.\n"
            "4. Verify that you have write permissions for the destination folder.\n\n"
            "Please fix the issues, click 'Scan' to refresh changes, and try syncing again."
        )

    def _cleanup_orphaned_tmps(self, dest_dir):
        if not dest_dir or not os.path.exists(dest_dir):
            return
        def _worker():
            cleaned_count = 0
            try:
                for root, dirs, files in os.walk(dest_dir):
                    for file in files:
                        if ".smartsync." in file and file.endswith(".tmp"):
                            file_path = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(ensure_extended_path(file_path))
                                age = time.time() - mtime
                                is_running = hasattr(self, "worker") and self.worker.isRunning() and self.worker.mode == "sync"
                                threshold = 300 if is_running else 5
                                if age > threshold:
                                    safe_chmod_write(file_path)
                                    os.remove(ensure_extended_path(file_path))
                                    cleaned_count += 1
                            except Exception:
                                pass
                if cleaned_count > 0:
                    QTimer.singleShot(0, lambda: self._add_log(f"🧹 Cleaned up {cleaned_count} orphaned temporary sync files.", "success"))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _set_windows_startup(self, enabled):
        if sys.platform != "win32":
            return
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "SmartFileSync"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}"'
                else:
                    script_path = os.path.abspath(sys.argv[0])
                    cmd = f'"{sys.executable}" "{script_path}" --minimized'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self._add_log(f"⚠️ Failed to set Windows startup registry: {e}", "warning")

    def closeEvent(self, e):
        current_config = self.get_current_config()
        if hasattr(self, "_saved_config") and current_config != self._saved_config:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Unsaved Changes")
            msg.setText("You have unsaved configuration changes.")
            
            save_exit = msg.addButton("Save & Exit", QMessageBox.AcceptRole)
            discard = msg.addButton("Discard Changes", QMessageBox.DestructiveRole)
            cancel = msg.addButton("Cancel", QMessageBox.RejectRole)
            
            msg.setDefaultButton(save_exit)
            msg.exec()
            
            clicked = msg.clickedButton()
            if clicked == save_exit:
                if self.worker.isRunning():
                    self.worker.stop(); self.worker.wait(3000)
                self._save_settings()
                e.accept()
            elif clicked == discard:
                if self.worker.isRunning():
                    self.worker.stop(); self.worker.wait(3000)
                e.accept()
            else:
                e.ignore()
        else:
            if self.worker.isRunning():
                self.worker.stop(); self.worker.wait(3000)
            self._save_settings()
            e.accept()

    # ══════════════════════════════════════════
    # PALETTE LAYOUT CSS
    # ══════════════════════════════════════════
    def _apply_theme(self):
        if hasattr(self, "theme_btn"):
            self.theme_btn.setText(IconManager.get("sun" if self.dark_mode else "moon"))
            self.theme_btn.setToolTip("Switch to Light Mode" if self.dark_mode else "Switch to Dark Mode")
        
        if self.dark_mode:
            self.setStyleSheet(self._dark_css())
        else:
            self.setStyleSheet(self._light_css())
            
        if hasattr(self, "settings_page") and hasattr(self.settings_page, "opt_dark_mode"):
            self.settings_page.opt_dark_mode.blockSignals(True)
            self.settings_page.opt_dark_mode.setChecked(self.dark_mode)
            self.settings_page.opt_dark_mode.blockSignals(False)

    def _dark_css(self):
        return """
        * { font-family: 'Segoe UI', sans-serif; font-size: 13px; outline: none; }

        QMainWindow {
            background-color: #090d16;
        }

        QWidget {
            color: #f8fafc;
        }

        /* ── SIDEBAR ── */
        QFrame#sidebar {
            background-color: #05080f;
            border-right: 1px solid #111827;
        }
        #app_title {
            color: #f8fafc;
        }
        
        /* Sidebar View Filter Search */
        #sidebar_search {
            background-color: #0d121f;
            border: 1px solid #1f2937;
            border-radius: 6px;
            padding: 4px 10px;
            color: #f8fafc;
            font-size: 12px;
        }
        #sidebar_search:focus {
            border-color: #3b82f6;
        }

        /* Navigation Buttons */
        #nav_btn {
            background-color: transparent; border: none; border-radius: 6px;
            margin: 2px 12px;
        }
        #nav_btn:hover { background-color: #111827; }
        #nav_btn:checked {
            background-color: #1f2937;
            border-left: 3px solid #3b82f6; border-top-left-radius: 0px; border-bottom-left-radius: 0px;
        }
        
        #nav_lbl { color: #94a3b8; font-size: 13px; background: transparent; }
        #nav_icon { color: #94a3b8; font-size: 13px; background: transparent; }
        #nav_shortcut { color: #475569; font-size: 10px; background: transparent; }
        #nav_badge {
            background-color: #3b82f6; color: #ffffff;
            border-radius: 7px; font-size: 9px; font-weight: bold;
            padding: 1px 5px; height: 14px; min-width: 10px;
        }
        
        #nav_btn:hover QLabel#nav_lbl { color: #f8fafc; }
        #nav_btn:hover QLabel#nav_icon { color: #f8fafc; }
        #nav_btn:checked QLabel#nav_lbl { color: #f8fafc; font-weight: 600; }
        #nav_btn:checked QLabel#nav_icon { color: #f8fafc; font-weight: 600; }
        #nav_btn:checked QLabel#nav_shortcut { color: #3b82f6; }

        #sidebar_footer {
            border-top: 1px solid #111827;
            background-color: transparent;
        }

        /* ── TOP BAR ── */
        #topbar {
            background-color: #090d16;
            border-bottom: 1px solid #111827;
        }
        #breadcrumb_lbl { color: #3b82f6; letter-spacing: 1.5px; }
        #small_lbl { color: #94a3b8; font-size: 11px; }

        #global_search_input {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-radius: 6px;
            padding: 4px 10px;
            color: #f8fafc;
        }
        #global_search_input:focus {
            border-color: #3b82f6;
        }

        #icon_btn {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 6px; color: #f8fafc; font-size: 14px;
        }
        #icon_btn:hover { background-color: #1f2937; }

        /* Drive combo top */
        #drive_combo_top {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 6px; padding: 2px 6px; color: #f8fafc;
        }
        #drive_combo_top::drop-down { border: none; width: 14px; }
        #drive_combo_top QAbstractItemView { background-color: #111827; color: #f8fafc; border: 1px solid #1f2937; }

        /* ── BUTTONS ── */
        #btn_scan {
            background-color: #2563eb; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 24px;
        }
        #btn_scan:hover { background-color: #3b82f6; }
        #btn_scan:disabled { background-color: #111827; color: #475569; }

        #btn_sync {
            background-color: #059669; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 24px;
        }
        #btn_sync:hover { background-color: #10b981; }
        #btn_sync:disabled { background-color: #111827; color: #475569; }

        #btn_sel {
            background-color: #d97706; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 20px;
        }
        #btn_sel:hover { background-color: #f59e0b; }
        #btn_sel:disabled { background-color: #111827; color: #475569; }

        #mini_btn, #preset_btn, #browse_btn {
            background-color: #111827; border: 1px solid #1f2937; border-radius: 6px;
            color: #f8fafc; padding: 4px 12px;
        }
        #mini_btn:hover, #preset_btn:hover, #browse_btn:hover { background-color: #1f2937; border-color: #3b82f6; }

        #collapse_btn {
            background-color: transparent; border: none;
            color: #94a3b8; font-size: 11px; text-align: left;
            padding: 4px 0px;
        }
        #collapse_btn:hover { color: #f8fafc; }

        #setting_desc_lbl { color: #94a3b8; }
        #setting_title_lbl { font-weight: bold; font-size: 13px; color: #f8fafc; }

        /* ── CARDS & PANELS ── */
        #stat_card, #folder_card, #dashboard_panel, #options_panel, #settings_pane, #setting_row_card {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 12px;
        }
        #history_session_card {
            background-color: #0d121f; border: 1px solid #1f2937;
            border-radius: 10px;
        }
        #history_session_card:hover {
            border-color: #374151; background-color: #111827;
        }
        #history_session_card[selected="true"] {
            border: 1px solid #3b82f6; background-color: #111827;
        }
        #stat_label, #card_header { color: #94a3b8; font-size: 10px; letter-spacing: 1px; }
        #folder_stats_frame {
            background-color: #090d16; border-radius: 8px;
        }
        #folder_meta_lbl { color: #94a3b8; font-size: 11px; }

        /* Input / Combo Fields */
        #path_input, #search_input, QLineEdit {
            background-color: #090d16; border: 1px solid #1f2937;
            border-radius: 6px; padding: 6px 12px; color: #f8fafc;
        }
        #path_input:focus, #search_input:focus, QLineEdit:focus { border-color: #3b82f6; outline: none; }

        QComboBox {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 6px; padding: 4px 10px; color: #f8fafc;
        }
        QComboBox:focus { border: 1px solid #3b82f6; outline: none; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox QAbstractItemView { background-color: #111827; color: #f8fafc; border: 1px solid #1f2937; }

        /* ── TABLES ── */
        QTableView {
            background-color: #111827; alternate-background-color: #0d121f;
            gridline-color: transparent; border: none; color: #f8fafc;
            border-radius: 8px;
        }
        QTableView::item { padding: 6px; border-bottom: 1px solid #1f2937; }
        QTableView::item:selected { background-color: #1f2937; color: #3b82f6; }
        QHeaderView::section {
            background-color: #111827; color: #94a3b8; padding: 8px;
            font-weight: bold; border: none; border-bottom: 2px solid #1f2937;
        }

        /* Dashboard Table Specific Styles */
        QTableWidget#dashboard_table {
            background-color: #0d121f; border: 1px solid #1f2937; border-radius: 8px; gridline-color: transparent;
        }
        QTableWidget#dashboard_table::item {
            padding: 6px 12px; border-bottom: 1px solid #151d2e; font-size: 12px; color: #f8fafc;
        }
        QTableWidget#dashboard_table QHeaderView::section {
            background-color: #090d16; color: #94a3b8; padding: 6px 12px;
            font-size: 11px; font-weight: bold; border: none; border-bottom: 1px solid #1f2937;
        }

        #empty_state_lbl { color: #475569; font-size: 14px; font-weight: 500; padding: 60px; line-height: 1.6; }

        /* Scan Results Detail Panel */
        #scan_detail_panel {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 10px;
        }
        #scan_stat_chip {
            background-color: #111827; border: 1px solid #1f2937;
            border-radius: 8px;
        }
        #scan_splitter::handle { background-color: transparent; width: 6px; }
        #detail_action_btn {
            background-color: #0d1117; border: 1px solid #1f2937;
            border-radius: 6px; color: #cbd5e1; font-size: 11px;
            text-align: left; padding: 4px 10px;
        }
        #detail_action_btn:hover { background-color: #1f2937; border-color: #3b82f6; color: #f8fafc; }

        /* Settings Splitter */
        #settings_splitter::handle { background-color: #1f2937; width: 1px; }
        #settings_nav { background-color: #05080f; border: none; }
        #settings_nav::item { padding: 8px 12px; margin: 4px; border-radius: 6px; color: #cbd5e1; }
        #settings_nav::item:hover { background-color: #111827; color: #f8fafc; }
        #settings_nav::item:selected { background-color: #1f2937; color: #3b82f6; font-weight: 600; }

        /* QCheckBox styling */
        QCheckBox { spacing: 8px; color: #cbd5e1; font-size: 13px; }
        QCheckBox:hover { color: #f8fafc; }
        QCheckBox:focus { border: 1px dotted #3b82f6; }

        /* QSlider styling */
        QSlider::groove:horizontal { border: none; height: 4px; background: #1f2937; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #3b82f6; border-radius: 2px; }
        QSlider::handle:horizontal { background: #ffffff; border: 1px solid #3b82f6; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        QSlider::handle:horizontal:hover { background: #3b82f6; }


        /* QTabWidget styling */
        QTabWidget::pane {
            border: none;
            background-color: transparent;
        }
        QTabBar::tab {
            background-color: transparent;
            color: #94a3b8;
            padding: 8px 16px;
            margin-right: 4px;
            border-bottom: 2px solid transparent;
            font-weight: 500;
        }
        QTabBar::tab:hover {
            color: #f8fafc;
            background-color: #111827;
            border-radius: 4px;
        }
        QTabBar::tab:selected {
            color: #3b82f6;
            border-bottom: 2px solid #3b82f6;
            font-weight: 600;
        }

        /* Progress Bar */
        #main_progress { background-color: #111827; border: none; border-radius: 3px; }
        #main_progress::chunk { background-color: #3b82f6; border-radius: 3px; }

        /* Status Bar */
        QStatusBar { color: #64748b; background-color: #05080f; border-top: 1px solid #111827; }

        /* Exclusions text area */
        #log_area { background-color: #090d16; border: 1px solid #1f2937; border-radius: 8px; color: #f8fafc; }

        /* Empty State */
        #empty_title { color: #f8fafc; }
        #empty_details { color: #94a3b8; }
        QPushButton:focus { border: 2px solid #3b82f6; }
        """

    def _light_css(self):
        return """
        * { font-family: 'Segoe UI', sans-serif; font-size: 13px; outline: none; }

        QMainWindow {
            background-color: #f1f5f9;
        }

        QWidget {
            color: #1e293b;
        }

        /* ── SIDEBAR ── */
        QFrame#sidebar {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        #app_title {
            color: #1e293b;
        }
        
        /* Sidebar View Filter Search */
        #sidebar_search {
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 10px;
            color: #1e293b;
            font-size: 12px;
        }
        #sidebar_search:focus {
            border-color: #2563eb;
        }

        /* Navigation Buttons */
        #nav_btn {
            background-color: transparent; border: none; border-radius: 6px;
            margin: 2px 12px;
        }
        #nav_btn:hover { background-color: #f1f5f9; }
        #nav_btn:checked {
            background-color: #e2e8f0;
            border-left: 3px solid #2563eb; border-top-left-radius: 0px; border-bottom-left-radius: 0px;
        }
        
        #nav_lbl { color: #64748b; font-size: 13px; background: transparent; }
        #nav_icon { color: #64748b; font-size: 13px; background: transparent; }
        #nav_shortcut { color: #94a3b8; font-size: 10px; background: transparent; }
        #nav_badge {
            background-color: #2563eb; color: #ffffff;
            border-radius: 7px; font-size: 9px; font-weight: bold;
            padding: 1px 5px; height: 14px; min-width: 10px;
        }
        
        #nav_btn:hover QLabel#nav_lbl { color: #1e293b; }
        #nav_btn:hover QLabel#nav_icon { color: #1e293b; }
        #nav_btn:checked QLabel#nav_lbl { color: #1e293b; font-weight: 600; }
        #nav_btn:checked QLabel#nav_icon { color: #1e293b; font-weight: 600; }
        #nav_btn:checked QLabel#nav_shortcut { color: #2563eb; }

        #sidebar_footer {
            border-top: 1px solid #e2e8f0;
            background-color: transparent;
        }

        /* ── TOP BAR ── */
        #topbar {
            background-color: #f1f5f9;
            border-bottom: 1px solid #e2e8f0;
        }
        #breadcrumb_lbl { color: #2563eb; letter-spacing: 1.5px; }
        #small_lbl { color: #64748b; font-size: 11px; }

        #global_search_input {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 10px;
            color: #1e293b;
        }
        #global_search_input:focus {
            border-color: #2563eb;
        }

        #icon_btn {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 6px; color: #1e293b; font-size: 14px;
        }
        #icon_btn:hover { background-color: #f1f5f9; }

        /* Drive combo top */
        #drive_combo_top {
            background-color: #ffffff; border: 1px solid #cbd5e1;
            border-radius: 6px; padding: 2px 6px; color: #1e293b;
        }
        #drive_combo_top::drop-down { border: none; width: 14px; }
        #drive_combo_top QAbstractItemView { background-color: #ffffff; color: #1e293b; border: 1px solid #e2e8f0; }

        /* ── BUTTONS ── */
        #btn_scan {
            background-color: #2563eb; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 24px;
        }
        #btn_scan:hover { background-color: #1d4ed8; }
        #btn_scan:disabled { background-color: #f1f5f9; color: #cbd5e1; }

        #btn_sync {
            background-color: #16a34a; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 24px;
        }
        #btn_sync:hover { background-color: #15803d; }
        #btn_sync:disabled { background-color: #f1f5f9; color: #cbd5e1; }

        #btn_sel {
            background-color: #d97706; border: none; border-radius: 8px;
            color: #ffffff; font-size: 13px; font-weight: 600;
            padding: 10px 20px;
        }
        #btn_sel:hover { background-color: #b45309; }
        #btn_sel:disabled { background-color: #f1f5f9; color: #cbd5e1; }

        #mini_btn, #preset_btn, #browse_btn {
            background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;
            color: #1e293b; padding: 4px 12px;
        }
        #mini_btn:hover, #preset_btn:hover, #browse_btn:hover { background-color: #f1f5f9; border-color: #2563eb; }

        #collapse_btn {
            background-color: transparent; border: none;
            color: #64748b; font-size: 11px; text-align: left;
            padding: 4px 0px;
        }
        #collapse_btn:hover { color: #1e293b; }

        #setting_desc_lbl { color: #64748b; }
        #setting_title_lbl { font-weight: bold; font-size: 13px; color: #1e293b; }

        /* ── CARDS & PANELS ── */
        #stat_card, #folder_card, #dashboard_panel, #options_panel, #settings_pane, #setting_row_card {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 12px;
        }
        #history_session_card {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        #history_session_card:hover {
            border-color: #cbd5e1; background-color: #f8fafc;
        }
        #history_session_card[selected="true"] {
            border: 1px solid #2563eb; background-color: #f8fafc;
        }
        #stat_label, #card_header { color: #64748b; font-size: 10px; letter-spacing: 1px; }
        #folder_stats_frame {
            background-color: #f8fafc; border-radius: 8px;
        }
        #folder_meta_lbl { color: #64748b; font-size: 11px; }

        /* Input / Combo Fields */
        #path_input, #search_input, QLineEdit {
            background-color: #f8fafc; border: 1px solid #e2e8f0;
            border-radius: 6px; padding: 6px 12px; color: #1e293b;
        }
        #path_input:focus, #search_input:focus, QLineEdit:focus { border-color: #2563eb; outline: none; }

        QComboBox {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 6px; padding: 4px 10px; color: #1e293b;
        }
        QComboBox:focus { border: 1px solid #2563eb; outline: none; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox QAbstractItemView { background-color: #ffffff; color: #1e293b; border: 1px solid #e2e8f0; }

        /* ── TABLES ── */
        QTableView {
            background-color: #ffffff; alternate-background-color: #f8fafc;
            gridline-color: transparent; border: none; color: #1e293b;
            border-radius: 8px;
        }
        QTableView::item { padding: 6px; border-bottom: 1px solid #e2e8f0; }
        QTableView::item:selected { background-color: #f1f5f9; color: #2563eb; }
        QHeaderView::section {
            background-color: #ffffff; color: #64748b; padding: 8px;
            font-weight: bold; border: none; border-bottom: 2px solid #e2e8f0;
        }

        /* Dashboard Table Specific Styles */
        QTableWidget#dashboard_table {
            background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; gridline-color: transparent;
        }
        QTableWidget#dashboard_table::item {
            padding: 6px 12px; border-bottom: 1px solid #f1f5f9; font-size: 12px; color: #1e293b;
        }
        QTableWidget#dashboard_table QHeaderView::section {
            background-color: #f1f5f9; color: #64748b; padding: 6px 12px;
            font-size: 11px; font-weight: bold; border: none; border-bottom: 1px solid #e2e8f0;
        }

        #empty_state_lbl { color: #94a3b8; font-size: 14px; font-weight: 500; padding: 60px; line-height: 1.6; }

        /* Scan Results Detail Panel */
        #scan_detail_panel {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        #scan_stat_chip {
            background-color: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 8px;
        }
        #scan_splitter::handle { background-color: transparent; width: 6px; }
        #detail_action_btn {
            background-color: #f8fafc; border: 1px solid #e2e8f0;
            border-radius: 6px; color: #475569; font-size: 11px;
            text-align: left; padding: 4px 10px;
        }
        #detail_action_btn:hover { background-color: #e2e8f0; border-color: #2563eb; color: #1e293b; }

        /* Settings Splitter */
        #settings_splitter::handle { background-color: #e2e8f0; width: 1px; }
        #settings_nav { background-color: #f8fafc; border: none; }
        #settings_nav::item { padding: 8px 12px; margin: 4px; border-radius: 6px; color: #475569; }
        #settings_nav::item:hover { background-color: #e2e8f0; color: #1e293b; }
        #settings_nav::item:selected { background-color: #cbd5e1; color: #2563eb; font-weight: 600; }

        /* QCheckBox styling */
        QCheckBox { spacing: 8px; color: #475569; font-size: 13px; }
        QCheckBox:hover { color: #1e293b; }
        QCheckBox:focus { border: 1px dotted #2563eb; }

        /* QSlider styling */
        QSlider::groove:horizontal { border: none; height: 4px; background: #e2e8f0; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #2563eb; border-radius: 2px; }
        QSlider::handle:horizontal { background: #ffffff; border: 1px solid #2563eb; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        QSlider::handle:horizontal:hover { background: #2563eb; }


        /* QTabWidget styling */
        QTabWidget::pane {
            border: none;
            background-color: transparent;
        }
        QTabBar::tab {
            background-color: transparent;
            color: #64748b;
            padding: 8px 16px;
            margin-right: 4px;
            border-bottom: 2px solid transparent;
            font-weight: 500;
        }
        QTabBar::tab:hover {
            color: #1e293b;
            background-color: #f1f5f9;
            border-radius: 4px;
        }
        QTabBar::tab:selected {
            color: #2563eb;
            border-bottom: 2px solid #2563eb;
            font-weight: 600;
        }

        /* Progress Bar */
        #main_progress { background-color: #e2e8f0; border: none; border-radius: 3px; }
        #main_progress::chunk { background-color: #2563eb; border-radius: 3px; }

        /* Status Bar */
        QStatusBar { color: #64748b; background-color: #ffffff; border-top: 1px solid #e2e8f0; }

        /* Exclusions text area */
        #log_area { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; color: #1e293b; }

        /* Empty State */
        #empty_title { color: #1e293b; }
        #empty_details { color: #64748b; }
        QPushButton:focus { border: 2px solid #2563eb; }
        """

# ───────────────────────────────────────────────
# ENTRY POINT
# ───────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    IconManager.init()
    win = SmartSyncApp()
    if "--minimized" in sys.argv:
        # App is launched on Windows startup minimized to system tray.
        # Do not call win.show(), it will stay hidden in the system tray.
        # Inform the user via system tray notification.
        win.tray.showMessage(
            "Smart File Sync",
            "Application started minimized in the system tray.",
            QSystemTrayIcon.Information,
            3000
        )
    else:
        win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
