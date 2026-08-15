import os
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

from ..components.stat_card import StatCard
from ..components.step_tracker import VisualStepTracker
from ...utils.formatters import fmt_size

class DashboardPage(QWidget):
    """
    Step 4: System Operational Dashboard & High-Visibility Activity Console.
    Optimized vertical proportions to guarantee 10+ activity log lines visible.
    """
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(10)

        # Header Title
        v_title = QVBoxLayout(); v_title.setSpacing(2)
        lbl_title = QLabel("Dashboard")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Operational statistics, system health, and real-time activity log.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        lay.addLayout(v_title)

        # Compact Top Grid: Row 1 (Health & Storage + Operational Summaries)
        top_grid = QHBoxLayout()
        top_grid.setSpacing(10)

        # Card 1: System Health & Drives
        c_health = QFrame(); c_health.setObjectName("stat_card")
        ch_lay = QVBoxLayout(c_health)
        ch_lay.setContentsMargins(14, 10, 14, 10)
        ch_lay.setSpacing(4)
        
        lbl_h_title = QLabel("SYNC HEALTH & CAPACITY")
        lbl_h_title.setObjectName("stat_label")
        lbl_h_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        ch_lay.addWidget(lbl_h_title)
        
        h_row = QHBoxLayout()
        self.lbl_health_score = QLabel("100%")
        self.lbl_health_score.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.lbl_health_score.setStyleSheet("color: #10b981; background: transparent;")
        
        v_hd = QVBoxLayout()
        self.lbl_health_desc = QLabel("System is fully synced.")
        self.lbl_health_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_disk_info = QLabel("Ready - Disks idle")
        self.lbl_disk_info.setStyleSheet("color: #64748b; font-size: 10px;")
        v_hd.addWidget(self.lbl_health_desc)
        v_hd.addWidget(self.lbl_disk_info)
        
        h_row.addWidget(self.lbl_health_score)
        h_row.addLayout(v_hd)
        h_row.addStretch()
        ch_lay.addLayout(h_row)
        top_grid.addWidget(c_health, 1)

        # Card 2: Last Sync Summary
        self.card_last_sync = QFrame(); self.card_last_sync.setObjectName("stat_card")
        cls_lay = QVBoxLayout(self.card_last_sync)
        cls_lay.setContentsMargins(14, 10, 14, 10)
        cls_lay.setSpacing(4)
        
        lbl_ls_title = QLabel("LAST SYNCHRONIZATION")
        lbl_ls_title.setObjectName("stat_label")
        lbl_ls_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        cls_lay.addWidget(lbl_ls_title)
        
        ls_grid = QGridLayout(); ls_grid.setSpacing(4)
        self.lbl_last_status = QLabel("Status: Idle"); self.lbl_last_status.setFont(QFont("Segoe UI", 9, QFont.Bold)); self.lbl_last_status.setStyleSheet("color: #10b981;")
        self.lbl_last_time = QLabel("Time: Never"); self.lbl_last_time.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_last_files = QLabel("Files: 0"); self.lbl_last_files.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_last_size = QLabel("Data: 0 B"); self.lbl_last_size.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        ls_grid.addWidget(self.lbl_last_status, 0, 0); ls_grid.addWidget(self.lbl_last_time, 0, 1)
        ls_grid.addWidget(self.lbl_last_files, 1, 0); ls_grid.addWidget(self.lbl_last_size, 1, 1)
        cls_lay.addLayout(ls_grid)
        top_grid.addWidget(self.card_last_sync, 1)

        # Card 3: Active Stage
        c_stage = QFrame(); c_stage.setObjectName("stat_card")
        cst_lay = QVBoxLayout(c_stage)
        cst_lay.setContentsMargins(14, 10, 14, 10)
        cst_lay.setSpacing(4)
        
        lbl_st_title = QLabel("ACTIVE WORKFLOW STAGE")
        lbl_st_title.setObjectName("stat_label")
        lbl_st_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        cst_lay.addWidget(lbl_st_title)
        
        self.workflow_tracker = VisualStepTracker(self)
        self.lbl_workflow_stage = QLabel("Stage: Idle")
        self.lbl_workflow_stage.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        cst_lay.addWidget(self.workflow_tracker)
        cst_lay.addWidget(self.lbl_workflow_stage)
        top_grid.addWidget(c_stage, 1)

        lay.addLayout(top_grid)

        # Compact Metric Chips Row (5 Cards)
        stats_lay = QHBoxLayout()
        stats_lay.setSpacing(10)
        self.stat_scanned = StatCard("Scanned", "0", "#3b82f6")
        self.stat_missing = StatCard("Missing", "0", "#f59e0b")
        self.stat_modified = StatCard("Changed", "0", "#10b981")
        self.stat_copied = StatCard("Synced", "0", "#06b6d4")
        self.stat_errors = StatCard("Errors", "0", "#ef4444")

        for sc in [self.stat_scanned, self.stat_missing, self.stat_modified, self.stat_copied, self.stat_errors]:
            stats_lay.addWidget(sc)
        lay.addLayout(stats_lay)

        # Large, Spacious Activity Log Panel (Major Screen Priority)
        log_panel = QFrame()
        log_panel.setObjectName("dashboard_panel")
        lp_lay = QVBoxLayout(log_panel)
        lp_lay.setContentsMargins(16, 14, 16, 14)
        lp_lay.setSpacing(8)

        lbl_lp = QLabel("LIVE SYSTEM ACTIVITY LOG")
        lbl_lp.setObjectName("card_header")
        lbl_lp.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lp_lay.addWidget(lbl_lp)

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
        self.list_activity.setMinimumHeight(280) # Ample space for 10+ rows!

        lp_lay.addWidget(self.list_activity, 1)
        lay.addWidget(log_panel, 1)

    def log_activity(self, message: str, kind: str = "info"):
        """Log event with clean timestamp and high-contrast status bullet"""
        r = self.list_activity.rowCount()
        self.list_activity.insertRow(r)
        now = datetime.now().strftime("%H:%M:%S")

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

    def update_stats(self, scanned, missing, modified, copied, errors):
        self.stat_scanned.set_value(scanned)
        self.stat_missing.set_value(missing)
        self.stat_modified.set_value(modified)
        self.stat_copied.set_value(copied)
        self.stat_errors.set_value(errors)

        try:
            sc, m, mod, err = int(scanned), int(missing), int(modified), int(errors)
            score = max(0, int((sc - m - mod - err) / sc * 100)) if sc > 0 else 100
            self.lbl_health_score.setText(f"{score}%")
            if score == 100:
                self.lbl_health_desc.setText("System is fully synced.")
                self.lbl_health_score.setStyleSheet("color: #10b981; font-size: 18px; font-weight: bold;")
            elif score > 80:
                self.lbl_health_desc.setText("Needs minor updates.")
                self.lbl_health_score.setStyleSheet("color: #f59e0b; font-size: 18px; font-weight: bold;")
            else:
                self.lbl_health_desc.setText("Requires immediate sync.")
                self.lbl_health_score.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold;")
        except ValueError:
            self.lbl_health_score.setText("-")
            self.lbl_health_desc.setText("Start scan to evaluate health.")

    def update_last_sync_summary(self, status, time_str, files_count, size_str):
        self.lbl_last_status.setText(f"Status: {status}")
        color = "#10b981" if "Success" in status or "Complete" in status else ("#ef4444" if "Error" in status else "#f59e0b")
        self.lbl_last_status.setStyleSheet(f"font-weight: bold; color: {color}; background: transparent;")
        self.lbl_last_time.setText(f"Time: {time_str}")
        self.lbl_last_files.setText(f"Files: {files_count}")
        self.lbl_last_size.setText(f"Data: {size_str}")

    def update_disk_usage(self, src_path, dst_path):
        try:
            txts = []
            if src_path and os.path.exists(src_path):
                u_src = shutil.disk_usage(src_path)
                txts.append(f"Src: {Path(src_path).drive or '/'} ({fmt_size(u_src.free)} free)")
            if dst_path and os.path.exists(dst_path):
                u_dst = shutil.disk_usage(dst_path)
                txts.append(f"Dst: {Path(dst_path).drive or '/'} ({fmt_size(u_dst.free)} free)")
            self.lbl_disk_info.setText(" | ".join(txts) if txts else "Ready - Disks idle")
        except Exception:
            pass
