from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QTabBar
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ..components.empty_state import EmptyStateWidget
from ..components.delegates import BadgeDelegate
from ...utils.formatters import fmt_speed, fmt_eta, fmt_size

class SyncQueuePage(QWidget):
    """
    Step 3: Multi-Threaded Sync Queue & Live Performance Metrics Page.
    Uses O(1) in-place row updates with fast filter tabs (Zero row-shifting bugs).
    """
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        self._file_statuses = {} # idx -> status_str

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(10)

        # Header Title
        v_title = QVBoxLayout(); v_title.setSpacing(2)
        lbl_title = QLabel("Sync Queue")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Step 3: Monitor active file writes, throughput speeds, and thread operations.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        lay.addLayout(v_title)

        # Progress Overview Bar
        prog_hdr = QHBoxLayout()
        self.lbl_progress_summary = QLabel("Ready - 0 files queued")
        self.lbl_progress_summary.setObjectName("small_lbl")
        self.lbl_percentage = QLabel("0%")
        self.lbl_percentage.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_percentage.setStyleSheet("color: #3b82f6;")
        prog_hdr.addWidget(self.lbl_progress_summary)
        prog_hdr.addStretch()
        prog_hdr.addWidget(self.lbl_percentage)
        lay.addLayout(prog_hdr)

        self.main_progress = QProgressBar()
        self.main_progress.setObjectName("main_progress")
        self.main_progress.setFixedHeight(6)
        self.main_progress.setTextVisible(False)
        lay.addWidget(self.main_progress)

        # Performance Metrics Row (Clean hyphens)
        metric_bar = QHBoxLayout()
        metric_bar.setSpacing(16)

        self.lbl_curr_speed = QLabel("Current Speed: -")
        self.lbl_avg_speed = QLabel("Avg Speed: -")
        self.lbl_files_sec = QLabel("Throughput: -")
        self.lbl_eta = QLabel("Time Left: -")
        self.lbl_data_copied = QLabel("Data Copied: -")

        for lbl in [self.lbl_curr_speed, self.lbl_avg_speed, self.lbl_files_sec, self.lbl_eta, self.lbl_data_copied]:
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #94a3b8; background: transparent;")
            metric_bar.addWidget(lbl)
        metric_bar.addStretch()
        lay.addLayout(metric_bar)

        # Control Toolbar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(10)

        self.btn_pause = QPushButton("Pause Sync")
        self.btn_pause.setObjectName("mini_btn")
        self.btn_pause.setFixedHeight(32)
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.clicked.connect(self.main_win._on_pause_clicked)

        self.btn_stop = QPushButton("Stop Sync")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.setFixedHeight(32)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.main_win._on_stop_clicked)

        ctrl_bar.addWidget(self.btn_pause)
        ctrl_bar.addWidget(self.btn_stop)
        ctrl_bar.addStretch()
        lay.addLayout(ctrl_bar)

        # Filter Tabs Bar
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.addTab("All Files (0)")
        self.tab_bar.addTab("Pending (0)")
        self.tab_bar.addTab("Active (0)")
        self.tab_bar.addTab("Completed (0)")
        self.tab_bar.addTab("Error (0)")
        self.tab_bar.currentChanged.connect(self._on_tab_filter_changed)
        lay.addWidget(self.tab_bar)

        # Stacked Container for Table vs Empty State
        self.queue_container = QStackedWidget()
        self.empty_state = EmptyStateWidget(
            "queue",
            "No active sync queue.",
            "Files queued for transfer will appear here with live speed and progress metrics.",
            btn_text="Open Folder Setup",
            btn_callback=lambda: self.main_win._on_nav_clicked(0)
        )
        self.queue_container.addWidget(self.empty_state)

        # Unified Queue Table
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setObjectName("queue_table")
        self.queue_table.setHorizontalHeaderLabels(["Filename", "Size", "Relative Path", "Status", "Details"])
        self.queue_table.setShowGrid(False)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.verticalHeader().setDefaultSectionSize(32)

        hdr = self.queue_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.queue_table.setColumnWidth(3, 110)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.badge_delegate = BadgeDelegate(lambda: self.main_win.dark_mode, self.queue_table)
        self.queue_table.setItemDelegateForColumn(3, self.badge_delegate)

        self.queue_container.addWidget(self.queue_table)
        lay.addWidget(self.queue_container, 1)

    def populate_queue(self, files: list):
        """Initialize unified queue table with pending files"""
        self.queue_table.setRowCount(len(files))
        self._file_statuses.clear()

        for idx, fi in enumerate(files):
            self._file_statuses[idx] = "Pending"
            self.queue_table.setItem(idx, 0, QTableWidgetItem(fi.get("filename", "")))
            self.queue_table.setItem(idx, 1, QTableWidgetItem(fi.get("size_str", "")))
            self.queue_table.setItem(idx, 2, QTableWidgetItem(fi.get("rel_path", "")))
            self.queue_table.setItem(idx, 3, QTableWidgetItem("Pending"))
            self.queue_table.setItem(idx, 4, QTableWidgetItem("Queued for transfer"))

        self.tab_bar.setCurrentIndex(0) # Default to 'All Files'
        self.queue_container.setCurrentWidget(self.queue_table)
        self._update_tab_counts()
        self._on_tab_filter_changed(0)

    def update_file_status(self, idx: int, status: str, detail: str = ""):
        """Update row status in-place at O(1) speed"""
        if idx < self.queue_table.rowCount():
            self._file_statuses[idx] = status
            item_status = self.queue_table.item(idx, 3)
            if item_status:
                item_status.setText(status)
            item_detail = self.queue_table.item(idx, 4)
            if item_detail:
                item_detail.setText(detail)

            # Apply current filter visibility and tab badges
            self._update_tab_counts()
            tab_idx = self.tab_bar.currentIndex()
            if tab_idx != 0:
                self._apply_row_filter(idx, tab_idx)

    def _apply_row_filter(self, row: int, tab_idx: int):
        status = self._file_statuses.get(row, "")
        if tab_idx == 0:
            self.queue_table.setRowHidden(row, False)
        elif tab_idx == 1:
            self.queue_table.setRowHidden(row, status != "Pending")
        elif tab_idx == 2:
            self.queue_table.setRowHidden(row, status != "In Progress")
        elif tab_idx == 3:
            self.queue_table.setRowHidden(row, status != "Completed")
        elif tab_idx == 4:
            self.queue_table.setRowHidden(row, status not in ("Error", "Stopped"))

    def _on_tab_filter_changed(self, tab_idx: int):
        for r in range(self.queue_table.rowCount()):
            self._apply_row_filter(r, tab_idx)

    def _update_tab_counts(self):
        counts = {"All": 0, "Pending": 0, "Active": 0, "Completed": 0, "Error": 0}
        for s in self._file_statuses.values():
            counts["All"] += 1
            if s == "Pending": counts["Pending"] += 1
            elif s == "In Progress": counts["Active"] += 1
            elif s == "Completed": counts["Completed"] += 1
            elif s in ("Error", "Stopped"): counts["Error"] += 1

        self.tab_bar.setTabText(0, f"All Files ({counts['All']})")
        self.tab_bar.setTabText(1, f"Pending ({counts['Pending']})")
        self.tab_bar.setTabText(2, f"Active ({counts['Active']})")
        self.tab_bar.setTabText(3, f"Completed ({counts['Completed']})")
        self.tab_bar.setTabText(4, f"Error ({counts['Error']})")

    def update_metrics(self, current_speed, avg_speed, throughput, eta_sec, copied_bytes, total_bytes):
        self.lbl_curr_speed.setText(f"Current Speed: {fmt_speed(current_speed)}")
        self.lbl_avg_speed.setText(f"Avg Speed: {fmt_speed(avg_speed)}")
        self.lbl_files_sec.setText(f"Throughput: {throughput:.1f} files/s" if throughput > 0 else "Throughput: -")
        self.lbl_eta.setText(f"Time Left: {fmt_eta(eta_sec)}")
        self.lbl_data_copied.setText(f"Data Copied: {fmt_size(copied_bytes)} / {fmt_size(total_bytes)}")
        self._update_tab_counts()

    def reset_view(self):
        self.queue_table.setRowCount(0)
        self._file_statuses.clear()
        self.main_progress.setValue(0)
        self.lbl_percentage.setText("0%")
        self.lbl_curr_speed.setText("Current Speed: -")
        self.lbl_avg_speed.setText("Avg Speed: -")
        self.lbl_files_sec.setText("Throughput: -")
        self.lbl_eta.setText("Time Left: -")
        self.lbl_data_copied.setText("Data Copied: -")
        self._update_tab_counts()
        self.queue_container.setCurrentWidget(self.empty_state)
