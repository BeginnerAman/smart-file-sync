import os
import json
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QSlider, QTextEdit, QSplitter, QTableWidget, QTableWidgetItem,
    QStackedWidget, QFrame, QHeaderView, QFileDialog, QComboBox, QLineEdit
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal

from ...core.platform_win import set_windows_startup
from ...utils.constants import DEFAULT_EXCLUSIONS
from ..components.icons import IconManager
from ..dialogs.custom_dialogs import SmartNoticeDialog, SmartConfirmActionDialog

class PerformancePresetCard(QFrame):
    """Modern Selectable Card for Eco, Balanced, and Turbo Concurrency Presets"""
    clicked = Signal(int)

    def __init__(self, mode_id: str, title: str, threads: int, desc: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("preset_card")
        self.setCursor(Qt.PointingHandCursor)
        self.threads = threads
        self.mode_id = mode_id
        self._selected = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        # Header Row: Icon + Title + Thread badge
        h = QHBoxLayout()
        h.setSpacing(8)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(18, 18)
        self.icon_lbl.setScaledContents(True)
        self.icon_lbl.setPixmap(IconManager.get_vector_pixmap(icon_name, "#38bdf8", 18))
        h.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        h.addWidget(self.title_lbl)

        h.addStretch()

        self.badge_lbl = QLabel(f"{threads} Threads")
        self.badge_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.badge_lbl.setStyleSheet("color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 2px 8px; border-radius: 10px;")
        h.addWidget(self.badge_lbl)
        lay.addLayout(h)

        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.desc_lbl.setWordWrap(True)
        lay.addWidget(self.desc_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.threads)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool, dark_mode: bool = True):
        self._selected = selected
        if selected:
            border = "#3b82f6" if dark_mode else "#2563eb"
            bg = "#1e293b" if dark_mode else "#e0f2fe"
            self.setStyleSheet(f"#preset_card {{ background-color: {bg}; border: 2px solid {border}; border-radius: 10px; }}")
        else:
            self.setStyleSheet("")

class SettingsPage(QWidget):
    """Step 6: Configuration, Performance Tuning, and File Rules Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # Header Title
        v_title = QVBoxLayout(); v_title.setSpacing(2)
        lbl_title = QLabel("Settings & Tuning")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Customize theme preferences, concurrency presets, MD5 integrity checks, and exclusions.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        lay.addLayout(v_title)

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("settings_splitter")

        # Category List
        self.cats_list = QTableWidget(4, 1)
        self.cats_list.setObjectName("settings_nav")
        self.cats_list.horizontalHeader().setVisible(False)
        self.cats_list.verticalHeader().setVisible(False)
        self.cats_list.horizontalHeader().setStretchLastSection(True)
        self.cats_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.cats_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cats_list.setFixedWidth(160)
        self.cats_list.verticalHeader().setDefaultSectionSize(38)
        self.cats_list.setShowGrid(False)

        navs = ["  General", "  Performance", "  File Rules", "  Advanced"]
        for idx, text in enumerate(navs):
            item = QTableWidgetItem(text)
            item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.cats_list.setItem(idx, 0, item)
            
        self.cats_list.selectRow(0)
        self.cats_list.itemSelectionChanged.connect(self._on_cat_changed)
        split.addWidget(self.cats_list)

        # Stacked Panels
        self.stack = QStackedWidget()

        # Panel 1: General
        p_gen = QFrame(); p_gen.setObjectName("settings_pane")
        pg_lay = QVBoxLayout(p_gen); pg_lay.setContentsMargins(20, 20, 20, 20); pg_lay.setSpacing(14)
        
        lbl_g_hdr = QLabel("GENERAL PREFERENCES"); lbl_g_hdr.setObjectName("card_header"); lbl_g_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold)); pg_lay.addWidget(lbl_g_hdr)

        self.opt_dark_mode = QCheckBox("Enable Obsidian Dark Theme")
        self.opt_dark_mode.setChecked(self.main_win.dark_mode)
        self.opt_dark_mode.toggled.connect(self._toggle_dark_mode)
        pg_lay.addWidget(self.opt_dark_mode)

        self.opt_startup = QCheckBox("Launch Smart File Sync on Windows Startup")
        self.opt_startup.toggled.connect(self._toggle_startup)
        pg_lay.addWidget(self.opt_startup)

        self.opt_save_cfg = QCheckBox("Auto-save directory paths on scan")
        self.opt_save_cfg.setChecked(True)
        pg_lay.addWidget(self.opt_save_cfg)
        
        self.opt_watcher = QCheckBox("Enable Real-Time File Monitoring")
        self.opt_watcher.setChecked(False)
        pg_lay.addWidget(self.opt_watcher)
        
        lbl_sched_hdr = QLabel("AUTO SYNC SCHEDULE")
        lbl_sched_hdr.setObjectName("card_header")
        lbl_sched_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pg_lay.addWidget(lbl_sched_hdr)

        sched_lay = QHBoxLayout()
        sched_lay.setSpacing(10)
        lbl_sched_desc = QLabel("Sync frequency:")
        sched_lay.addWidget(lbl_sched_desc)
        
        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems(["Off", "Every 5 minutes", "Every 15 minutes", "Every 30 minutes", "Every 1 hour", "Every 2 hours"])
        sched_lay.addWidget(self.schedule_combo)
        sched_lay.addStretch()
        pg_lay.addLayout(sched_lay)
        
        self.lbl_next_sync = QLabel("Next sync: Not scheduled")
        self.lbl_next_sync.setStyleSheet("color: #64748b; font-size: 11px;")
        pg_lay.addWidget(self.lbl_next_sync)
        
        pg_lay.addStretch()
        self.stack.addWidget(p_gen)

        # Panel 2: Performance
        p_perf = QFrame(); p_perf.setObjectName("settings_pane")
        pp_lay = QVBoxLayout(p_perf); pp_lay.setContentsMargins(20, 20, 20, 20); pp_lay.setSpacing(14)
        
        lbl_p_hdr = QLabel("PERFORMANCE & CONCURRENCY"); lbl_p_hdr.setObjectName("card_header"); lbl_p_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold)); pp_lay.addWidget(lbl_p_hdr)
        
        # Detected Hardware Info
        self.total_cores = os.cpu_count() or 4
        lbl_cpu = QLabel(f"Detected System Hardware: {self.total_cores} CPU Logical Cores")
        lbl_cpu.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        pp_lay.addWidget(lbl_cpu)

        # 3 Smart Preset Cards
        self.eco_threads = min(2, self.total_cores)
        self.balanced_threads = max(2, self.total_cores // 2)
        self.turbo_threads = max(2, self.total_cores - 1)

        presets_lay = QHBoxLayout()
        presets_lay.setSpacing(10)

        self.card_eco = PerformancePresetCard(
            "eco", "Eco Mode", self.eco_threads,
            "Quiet background sync • Battery and CPU saver", "leaf"
        )
        self.card_bal = PerformancePresetCard(
            "balanced", "Balanced", self.balanced_threads,
            "Recommended • Optimal speed & PC responsiveness", "check"
        )
        self.card_turbo = PerformancePresetCard(
            "turbo", "Turbo Boost", self.turbo_threads,
            "Maximum SSD/NVMe multi-threaded transfer speed", "zap"
        )

        self.preset_cards = [self.card_eco, self.card_bal, self.card_turbo]
        for card in self.preset_cards:
            card.clicked.connect(self._on_preset_clicked)
            presets_lay.addWidget(card)

        pp_lay.addLayout(presets_lay)

        # Manual Override Slider
        th_lay = QHBoxLayout()
        lbl_th = QLabel("Concurrent Worker Threads:")
        self.thread_lbl = QLabel(f"{self.main_win.thread_count} threads")
        self.thread_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        th_lay.addWidget(lbl_th); th_lay.addStretch(); th_lay.addWidget(self.thread_lbl)
        pp_lay.addLayout(th_lay)

        self.thread_slider = QSlider(Qt.Horizontal)
        self.thread_slider.setRange(1, self.total_cores)
        self.thread_slider.setValue(min(self.total_cores, self.main_win.thread_count))
        self.thread_slider.valueChanged.connect(self._on_thread_slider_changed)
        pp_lay.addWidget(self.thread_slider)

        self._update_preset_selection(self.main_win.thread_count)

        lbl_bw_hdr = QLabel("BANDWIDTH LIMIT"); lbl_bw_hdr.setObjectName("card_header"); lbl_bw_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold)); pp_lay.addWidget(lbl_bw_hdr)
        
        bw_lay = QHBoxLayout()
        lbl_bw = QLabel("Max Transfer Speed:")
        self.lbl_throttle = QLabel("Unlimited")
        self.lbl_throttle.setFont(QFont("Segoe UI", 9, QFont.Bold))
        bw_lay.addWidget(lbl_bw); bw_lay.addStretch(); bw_lay.addWidget(self.lbl_throttle)
        pp_lay.addLayout(bw_lay)
        
        self.throttle_slider = QSlider(Qt.Horizontal)
        self.throttle_slider.setRange(0, 100)
        self.throttle_slider.setValue(0)
        def _update_throttle_lbl(v):
            self.lbl_throttle.setText("Unlimited" if v == 0 else f"{v} MB/s")
        self.throttle_slider.valueChanged.connect(_update_throttle_lbl)
        pp_lay.addWidget(self.throttle_slider)

        self.opt_renames = QCheckBox("Use Safe Atomic Temp Writes (Prevents corrupted files)")
        self.opt_renames.setChecked(True)
        pp_lay.addWidget(self.opt_renames)

        self.opt_verify = QCheckBox("Verify MD5 Integrity after write (Guarantees byte-for-byte fidelity)")
        pp_lay.addWidget(self.opt_verify)
        
        lbl_ver_hdr = QLabel("FILE VERSIONING")
        lbl_ver_hdr.setObjectName("card_header")
        lbl_ver_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pp_lay.addWidget(lbl_ver_hdr)
        
        self.version_combo = QComboBox()
        self.version_combo.addItems(["Disabled", "Keep 1 version", "Keep 3 versions", "Keep 5 versions"])
        pp_lay.addWidget(self.version_combo)
        
        lbl_delta_hdr = QLabel("DELTA TRANSFER")
        lbl_delta_hdr.setObjectName("card_header")
        lbl_delta_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pp_lay.addWidget(lbl_delta_hdr)
        
        self.opt_delta = QCheckBox("Enable Block-Level Delta Transfer (only copy changed blocks)")
        self.opt_delta.setChecked(True)
        self.opt_delta.setToolTip("For modified files > 1MB, only transfers the changed 4KB blocks instead of the entire file. Massively speeds up sync of large files with small edits.")
        pp_lay.addWidget(self.opt_delta)
        
        pp_lay.addStretch()
        self.stack.addWidget(p_perf)

        # Panel 3: File Rules
        p_rules = QFrame(); p_rules.setObjectName("settings_pane")
        pr_lay = QVBoxLayout(p_rules); pr_lay.setContentsMargins(20, 20, 20, 20); pr_lay.setSpacing(10)
        
        lbl_r_hdr = QLabel("EXCLUSIONS & IGNORE PATTERNS"); lbl_r_hdr.setObjectName("card_header"); lbl_r_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold)); pr_lay.addWidget(lbl_r_hdr)
        
        lbl_r_sub = QLabel("Specify file extensions or folder names to exclude (one per line):")
        lbl_r_sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
        pr_lay.addWidget(lbl_r_sub)

        self.txt_excl = QTextEdit()
        self.txt_excl.setObjectName("log_area")
        self.txt_excl.setPlaceholderText(".tmp\n.bak\nnode_modules\n.git")
        pr_lay.addWidget(self.txt_excl, 1)

        btn_save_excl = QPushButton("Save Exclusions List")
        btn_save_excl.setObjectName("mini_btn")
        btn_save_excl.setFixedHeight(30)
        btn_save_excl.setCursor(Qt.PointingHandCursor)
        btn_save_excl.clicked.connect(self._save_exclusions)
        pr_lay.addWidget(btn_save_excl, alignment=Qt.AlignRight)
        
        self.stack.addWidget(p_rules)

        # Panel 4: Advanced (Option B Power Tools Suite)
        p_adv = QFrame(); p_adv.setObjectName("settings_pane")
        pa_lay = QVBoxLayout(p_adv); pa_lay.setContentsMargins(20, 20, 20, 20); pa_lay.setSpacing(14)
        
        lbl_a_hdr = QLabel("ADVANCED SYSTEM & DIAGNOSTIC TOOLS"); lbl_a_hdr.setObjectName("card_header"); lbl_a_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold)); pa_lay.addWidget(lbl_a_hdr)

        # Tool 1: Clean Orphaned Temp Files
        c1 = QFrame(); c1.setObjectName("stat_card")
        c1_lay = QHBoxLayout(c1); c1_lay.setContentsMargins(16, 14, 16, 14); c1_lay.setSpacing(12)
        v1 = QVBoxLayout(); v1.setSpacing(3)
        t1 = QLabel("Clean Orphaned Temp Files"); t1.setFont(QFont("Segoe UI", 10, QFont.Bold))
        d1 = QLabel("Scans and purges leftover '.smartsync.tmp' files in destination directory from interrupted transfers."); d1.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v1.addWidget(t1); v1.addWidget(d1)
        b1 = QPushButton("Clean Temp Files"); b1.setObjectName("mini_btn"); b1.setFixedHeight(32); b1.setFixedWidth(140); b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self._clean_temp_files)
        c1_lay.addLayout(v1, 1); c1_lay.addWidget(b1)
        pa_lay.addWidget(c1)

        # Tool 2: Export Diagnostics & Logs
        c2 = QFrame(); c2.setObjectName("stat_card")
        c2_lay = QHBoxLayout(c2); c2_lay.setContentsMargins(16, 14, 16, 14); c2_lay.setSpacing(12)
        v2 = QVBoxLayout(); v2.setSpacing(3)
        t2 = QLabel("Export Diagnostic Logs"); t2.setFont(QFont("Segoe UI", 10, QFont.Bold))
        d2 = QLabel("Exports activity logs, hardware metrics, and session audit trails to a text archive for troubleshooting."); d2.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v2.addWidget(t2); v2.addWidget(d2)
        b2 = QPushButton("Export Logs"); b2.setObjectName("mini_btn"); b2.setFixedHeight(32); b2.setFixedWidth(140); b2.setCursor(Qt.PointingHandCursor)
        b2.clicked.connect(self._export_logs)
        c2_lay.addLayout(v2, 1); c2_lay.addWidget(b2)
        pa_lay.addWidget(c2)

        # Tool 3: Restore Factory Defaults
        c3 = QFrame(); c3.setObjectName("stat_card")
        c3_lay = QHBoxLayout(c3); c3_lay.setContentsMargins(16, 14, 16, 14); c3_lay.setSpacing(12)
        v3 = QVBoxLayout(); v3.setSpacing(3)
        t3 = QLabel("Restore Factory Defaults"); t3.setFont(QFont("Segoe UI", 10, QFont.Bold))
        d3 = QLabel("Restores all concurrency presets, scan rules, and theme settings back to original factory defaults."); d3.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v3.addWidget(t3); v3.addWidget(d3)
        b3 = QPushButton("Reset App"); b3.setObjectName("btn_danger"); b3.setFixedHeight(32); b3.setFixedWidth(140); b3.setCursor(Qt.PointingHandCursor)
        b3.clicked.connect(self._reset_to_defaults)
        c3_lay.addLayout(v3, 1); c3_lay.addWidget(b3)
        pa_lay.addWidget(c3)

        # PRE/POST SYNC SCRIPTS section
        lbl_scripts_hdr = QLabel("SYNC SCRIPTS")
        lbl_scripts_hdr.setObjectName("card_header")
        lbl_scripts_hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pa_lay.addWidget(lbl_scripts_hdr)

        lbl_pre = QLabel("Pre-Sync Script (runs before sync starts):")
        lbl_pre.setFont(QFont("Segoe UI", 9))
        pa_lay.addWidget(lbl_pre)
        
        self.pre_script_input = QLineEdit()
        self.pre_script_input.setPlaceholderText("e.g., C:\\scripts\\backup_db.bat")
        self.pre_script_input.setFixedHeight(32)
        pa_lay.addWidget(self.pre_script_input)

        lbl_post = QLabel("Post-Sync Script (runs after sync completes):")
        lbl_post.setFont(QFont("Segoe UI", 9))
        pa_lay.addWidget(lbl_post)
        
        self.post_script_input = QLineEdit()
        self.post_script_input.setPlaceholderText("e.g., C:\\scripts\\eject_usb.bat")
        self.post_script_input.setFixedHeight(32)
        pa_lay.addWidget(self.post_script_input)

        self.opt_script_on_error = QCheckBox("Run post-script even if sync had errors")
        pa_lay.addWidget(self.opt_script_on_error)

        pa_lay.addStretch()
        self.stack.addWidget(p_adv)

        split.addWidget(self.stack)
        lay.addWidget(split, 1)

    def _on_cat_changed(self):
        r = self.cats_list.currentRow()
        if r >= 0:
            self.stack.setCurrentIndex(r)

    def _toggle_dark_mode(self, checked):
        self.main_win.dark_mode = self.opt_dark_mode.isChecked()
        self.main_win._apply_theme()
        self.main_win._save_settings()

    def _toggle_startup(self, checked):
        import sys
        app_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        set_windows_startup("SmartFileSync", app_exe, checked)
        self.main_win._save_settings()

    def _on_preset_clicked(self, threads: int):
        self.thread_slider.setValue(threads)

    def _on_thread_slider_changed(self, v: int):
        self.thread_lbl.setText(f"{v} threads")
        self.main_win.thread_count = v
        if hasattr(self.main_win, 'worker') and self.main_win.worker:
            self.main_win.worker.threads = v
        self._update_preset_selection(v)
        self.main_win._save_settings()

    def _update_preset_selection(self, threads: int):
        for card in self.preset_cards:
            card.set_selected(card.threads == threads, self.main_win.dark_mode)

    def _save_exclusions(self):
        excl = []
        for line in self.txt_excl.toPlainText().splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                if not line.startswith("."): line = "." + line
                excl.append(line)
        self.main_win.excl_exts = excl
        self.main_win._save_settings()
        self.main_win._add_log("Updated exclusions rules list.", "info")

    def _clean_temp_files(self):
        dst = self.main_win.folder_setup_page.card_dst.input.text().strip()
        if dst and os.path.isdir(dst):
            self.main_win._cleanup_orphaned_tmps(dst)
            self.main_win._add_log(f"Cleaned temporary sync artifacts in {dst}", "info")
            diag = SmartNoticeDialog("Temp Files Cleaned", f"Successfully swept and cleaned temporary sync files in:\n{dst}", parent=self)
            diag.exec()
        else:
            diag = SmartNoticeDialog("Notice", "Please configure and select a valid destination folder on the Folder Setup page first.", parent=self)
            diag.exec()

    def _export_logs(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostic Logs", "smart_sync_diagnostics.txt", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("=== SMART FILE SYNC DIAGNOSTIC LOG ===\n")
                    f.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"System Cores: {self.total_cores}\n")
                    f.write(f"Configured Worker Threads: {self.main_win.thread_count}\n")
                    f.write(f"Dark Mode: {self.main_win.dark_mode}\n")
                    f.write(f"Active Exclusions: {', '.join(self.main_win.excl_exts)}\n\n")
                    f.write("--- RECENT SESSIONS ---\n")
                    from ...models.history_model import HistoryManager
                    sessions = HistoryManager.load_history()
                    for s in sessions:
                        f.write(f"Session {s.get('session_id')}: {s.get('status')} | {s.get('copied')} files ({s.get('copied_size')}) in {s.get('duration')}\n")
                
                diag = SmartNoticeDialog("Logs Exported", f"Diagnostic logs successfully saved to:\n{file_path}", parent=self)
                diag.exec()
            except Exception as e:
                diag = SmartNoticeDialog("Export Failed", f"Could not write log file: {str(e)}", parent=self)
                diag.exec()

    def _reset_to_defaults(self):
        confirm = SmartConfirmActionDialog(
            "Reset All Settings",
            "Are you sure you want to restore factory default settings?\n"
            "This will reset all performance presets, exclusions, and UI preferences.",
            action_button_text="Reset to Defaults",
            parent=self
        )
        if confirm.exec():
            self.main_win.settings.clear()
            self.main_win.dark_mode = True
            self.main_win.excl_exts = list(DEFAULT_EXCLUSIONS)
            self.main_win.thread_count = self.balanced_threads
            self.main_win._apply_theme()
            self.main_win._load_saved_state()
            diag = SmartNoticeDialog("Settings Reset", "All application settings have been restored to factory defaults.", parent=self)
            diag.exec()
