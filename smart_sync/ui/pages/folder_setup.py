import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QFrame, QFileDialog, QGridLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ...utils.constants import FILE_FILTERS
from ..components.folder_card import FolderMetaCard
from ..components.step_tracker import VisualStepTracker
from ..components.icons import IconManager
from ..components.multi_combo import MultiCheckFilterButton
from ...core.scanner import MetadataScanner

class FolderSetupPage(QWidget):
    """Step 1: Setup & Configuration Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # Header Title
        v_title = QVBoxLayout(); v_title.setSpacing(2)
        lbl_title = QLabel("Folder Configuration")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Step 1: Select source and destination directories to compare and synchronize.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        lay.addLayout(v_title)

        # Step tracker
        self.setup_steps_header = VisualStepTracker(self)
        self.setup_steps_header.set_active_step(1)
        self.step_tracker = self.setup_steps_header
        lay.addWidget(self.setup_steps_header)

        # Folders grid layout
        grid_folders = QGridLayout()
        grid_folders.setSpacing(14)

        self.card_src = FolderMetaCard("Source Directory", "Browse source directory path...", self._browse_src)
        self.card_dst = FolderMetaCard("Destination Directory", "Browse destination directory path...", self._browse_dst)
        self.card_src.input.editingFinished.connect(lambda: self._trigger_metadata_scan("src"))
        self.card_dst.input.editingFinished.connect(lambda: self._trigger_metadata_scan("dst"))

        grid_folders.addWidget(self.card_src, 0, 0)
        grid_folders.addWidget(self.card_dst, 0, 1)
        lay.addLayout(grid_folders)

        # Config & Filters Frame
        opt_frame = QFrame()
        opt_frame.setObjectName("options_panel")
        opt_lay = QVBoxLayout(opt_frame)
        opt_lay.setContentsMargins(18, 14, 18, 14)
        opt_lay.setSpacing(10)

        lbl_opt = QLabel("CONFIG FILTERS & RULES")
        lbl_opt.setObjectName("card_header")
        lbl_opt.setFont(QFont("Segoe UI", 9, QFont.Bold))
        opt_lay.addWidget(lbl_opt)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(14)

        # Multi-Select Filter button
        v1 = QVBoxLayout(); v1.setSpacing(6)
        lbl_f = QLabel("File Type Filter:"); lbl_f.setObjectName("small_lbl")
        self.filter_combo = MultiCheckFilterButton()
        self.filter_combo.selectionChanged.connect(self._on_filter_changed)
        v1.addWidget(lbl_f); v1.addWidget(self.filter_combo)
        opts_row.addLayout(v1, 1)

        # Exclusions button
        v2 = QVBoxLayout(); v2.setSpacing(6)
        lbl_e = QLabel("Rules & Limits:"); lbl_e.setObjectName("small_lbl")
        self.excl_btn = QPushButton("  Configure Exclusions")
        self.excl_btn.setObjectName("mini_btn")
        self.excl_btn.setFixedHeight(32)
        self.excl_btn.setIcon(IconManager.get_vector_icon("settings", "#38bdf8", 15))
        self.excl_btn.setCursor(Qt.PointingHandCursor)
        self.excl_btn.clicked.connect(self.main_win._open_exclude_dialog)
        v2.addWidget(lbl_e); v2.addWidget(self.excl_btn)
        opts_row.addLayout(v2, 1)

        # Dry run checkbox
        v3 = QVBoxLayout(); v3.setSpacing(6)
        lbl_d = QLabel("Safety Options:"); lbl_d.setObjectName("small_lbl")
        self.dry_run_chk = QCheckBox("Dry Run Preview Mode")
        self.dry_run_chk.setObjectName("opt_check")
        self.dry_run_chk.setFixedHeight(32)
        self.dry_run_chk.setToolTip("Preview differences without copying files.")
        v3.addWidget(lbl_d); v3.addWidget(self.dry_run_chk)
        opts_row.addLayout(v3, 1)

        # Sync Mode selector
        v4 = QVBoxLayout(); v4.setSpacing(6)
        lbl_m = QLabel("Sync Mode:"); lbl_m.setObjectName("small_lbl")
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems(["Copy Only (default)", "Mirror (delete extras)", "Bidirectional (two-way)"])
        self.sync_mode_combo.setFixedHeight(32)
        v4.addWidget(lbl_m); v4.addWidget(self.sync_mode_combo)
        opts_row.addLayout(v4, 1)

        opt_lay.addLayout(opts_row)
        lay.addWidget(opt_frame)

        # Bottom Actions
        act_row = QHBoxLayout()
        self.lbl_status_msg = QLabel("Select directories to start scan.")
        self.lbl_status_msg.setStyleSheet("color: #64748b; font-size: 11px;")
        
        self.scan_btn = QPushButton("Launch Directory Scan")
        self.scan_btn.setObjectName("btn_scan")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setMinimumWidth(180)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self.main_win._on_scan_clicked)

        act_row.addWidget(self.lbl_status_msg)
        act_row.addStretch()
        act_row.addWidget(self.scan_btn)
        lay.addLayout(act_row)
        lay.addStretch()

        self._active_scanners = {}

    def _browse_src(self):
        d = QFileDialog.getExistingDirectory(self, "Select Source Directory", self.card_src.input.text())
        if d:
            self.card_src.input.setText(d)
            self._trigger_metadata_scan("src")

    def _browse_dst(self):
        d = QFileDialog.getExistingDirectory(self, "Select Destination Directory", self.card_dst.input.text())
        if d:
            self.card_dst.input.setText(d)
            self._trigger_metadata_scan("dst")

    def _trigger_metadata_scan(self, key):
        path = self.card_src.input.text().strip() if key == "src" else self.card_dst.input.text().strip()
        if not path or not os.path.isdir(path):
            card = self.card_src if key == "src" else self.card_dst
            card.reset_stats()
            return
            
        # Safely disconnect and stop any existing scanner thread for this key
        old_scanner = self._active_scanners.get(key)
        if old_scanner is not None:
            try:
                old_scanner.finished_signal.disconnect()
            except Exception:
                pass
            if old_scanner.isRunning():
                old_scanner.request_stop()
                old_scanner.wait(500)

        allowed_exts = self.filter_combo.get_selected_extensions()
        scanner = MetadataScanner(key, path, self.main_win.excl_exts, allowed_exts, parent=self)
        scanner.finished_signal.connect(self._on_metadata_done)
        self._active_scanners[key] = scanner
        scanner.start()

    def _on_metadata_done(self, key, files, size, mtime):
        from datetime import datetime
        card = self.card_src if key == "src" else self.card_dst
        m_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime > 0 else "-"
        card.set_stats(files, size, m_str)
        self._validate_inputs()

    def _on_filter_changed(self):
        if self.card_src.input.text().strip():
            self._trigger_metadata_scan("src")
        if self.card_dst.input.text().strip():
            self._trigger_metadata_scan("dst")

    def _validate_inputs(self):
        src = self.card_src.input.text().strip()
        dst = self.card_dst.input.text().strip()
        valid = bool(src and dst and os.path.isdir(src) and os.path.isdir(dst) and os.path.abspath(src) != os.path.abspath(dst))
        self.scan_btn.setEnabled(valid)
        if valid:
            self.lbl_status_msg.setText("✓ Folders validated. Launch scan to compute differences.")
            self.lbl_status_msg.setStyleSheet("color: #10b981; font-size: 11px;")
        else:
            self.lbl_status_msg.setText("Please select valid, distinct source and destination folders.")
            self.lbl_status_msg.setStyleSheet("color: #64748b; font-size: 11px;")
