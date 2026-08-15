import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QTableView, QFrame, QSplitter, QHeaderView, QStackedWidget, QGridLayout, QApplication
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ..components.delegates import BadgeDelegate, FileIconDelegate
from ..components.empty_state import EmptyStateWidget
from ...models.scan_model import ScanResultsModel, ScanResultsProxyModel
from ...core.platform_win import clean_display_path

class ScanResultsPage(QWidget):
    """Step 2: Comparison Inspection and File Selection Page"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # Header Title + Status Summary Chips
        top_row = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel("Scan Results")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Step 2: Review detected differences and select files to synchronize.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        top_row.addLayout(v_title)

        top_row.addStretch()

        # Status Chips
        self.chip_total = self._make_stat_chip("Total", "0", "#3b82f6")
        self.chip_missing = self._make_stat_chip("Missing", "0", "#f59e0b")
        self.chip_modified = self._make_stat_chip("Changed", "0", "#10b981")
        self.chip_errors = self._make_stat_chip("Errors", "0", "#ef4444")
        
        for chip in [self.chip_total, self.chip_missing, self.chip_modified, self.chip_errors]:
            top_row.addWidget(chip)
        lay.addLayout(top_row)

        # Filter & Search Control Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("Search file names or paths...")
        self.search_input.setFixedWidth(240)
        self.search_input.setFixedHeight(32)
        self.search_input.textChanged.connect(self._filter_results_table)
        toolbar.addWidget(self.search_input)

        self.filter_reason_combo = QComboBox()
        self.filter_reason_combo.addItems([
            "All Reasons", "Missing Only", "Source Newer", "Destination Newer",
            "Destination Only", "Size Differs"
        ])
        self.filter_reason_combo.setFixedHeight(32)
        self.filter_reason_combo.currentTextChanged.connect(self._filter_results_table)
        toolbar.addWidget(self.filter_reason_combo)

        toolbar.addStretch()

        self.btn_select_all = QPushButton("✓  Select All")
        self.btn_select_all.setObjectName("mini_btn")
        self.btn_select_all.setFixedHeight(32)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self._on_select_all_clicked)

        self.btn_deselect_all = QPushButton("✕  Deselect All")
        self.btn_deselect_all.setObjectName("mini_btn")
        self.btn_deselect_all.setFixedHeight(32)
        self.btn_deselect_all.setCursor(Qt.PointingHandCursor)
        self.btn_deselect_all.clicked.connect(self._on_deselect_all_clicked)

        toolbar.addWidget(self.btn_select_all)
        toolbar.addWidget(self.btn_deselect_all)
        lay.addLayout(toolbar)

        # Content Splitter (Table + Details Panel)
        self.content_stack = QStackedWidget()
        
        self.empty_state = EmptyStateWidget(
            "scan",
            "No scan results available yet.",
            "Choose your source and destination directories in Folder Setup and click Launch Directory Scan.",
            btn_text="Open Folder Setup",
            btn_callback=lambda: self.main_win._on_nav_clicked(0)
        )
        self.content_stack.addWidget(self.empty_state)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("scan_splitter")

        # Table View
        self.table_view = QTableView()
        self.table_view.setObjectName("scan_table")
        self.source_model = ScanResultsModel()
        self.proxy_model = ScanResultsProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        
        self.badge_delegate = BadgeDelegate(lambda: self.main_win.dark_mode, self.table_view)
        self.table_view.setItemDelegateForColumn(5, self.badge_delegate)
        self.file_delegate = FileIconDelegate(lambda: self.main_win.dark_mode, self.table_view)
        self.table_view.setItemDelegateForColumn(1, self.file_delegate)

        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setShowGrid(False)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(32)
        
        hdr = self.table_view.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_view.setColumnWidth(0, 36)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table_view.setColumnWidth(5, 110)

        self.table_view.selectionModel().currentRowChanged.connect(self._on_current_changed)
        self.table_view.clicked.connect(self._on_table_clicked)
        self.table_view.doubleClicked.connect(self._on_table_double_clicked)
        self.source_model.dataChanged.connect(self._on_model_data_changed)
        self.source_model.modelReset.connect(self._update_checked_count)
        self.splitter.addWidget(self.table_view)

        # Details Panel
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("scan_detail_panel")
        self.detail_panel.setMinimumWidth(260)
        self.detail_panel.setMaximumWidth(360)
        dp_lay = QVBoxLayout(self.detail_panel)
        dp_lay.setContentsMargins(18, 16, 18, 16)
        dp_lay.setSpacing(8)

        lbl_dp = QLabel("FILE DETAILS")
        lbl_dp.setObjectName("card_header")
        lbl_dp.setFont(QFont("Segoe UI", 9, QFont.Bold))
        dp_lay.addWidget(lbl_dp)

        self.dp_filename = QLabel("No file selected")
        self.dp_filename.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.dp_filename.setWordWrap(True)
        dp_lay.addWidget(self.dp_filename)

        self.dp_extension = QLabel("-")
        self.dp_extension.setStyleSheet("color: #64748b; font-size: 11px;")
        dp_lay.addWidget(self.dp_extension)

        self.dp_reason_badge = QLabel("")
        self.dp_reason_badge.setAlignment(Qt.AlignCenter)
        self.dp_reason_badge.setFixedHeight(24)
        dp_lay.addWidget(self.dp_reason_badge)

        # Properties Grid
        props_grid = QGridLayout()
        props_grid.setSpacing(6)
        
        self._dp_props = {}
        prop_items = [("Full Path", "dp_full_path"), ("Relative Path", "dp_rel_path"), ("Size", "dp_size"), ("Modified", "dp_modified")]
        for i, (label, key) in enumerate(prop_items):
            l = QLabel(label); l.setFont(QFont("Segoe UI", 8, QFont.Bold)); l.setStyleSheet("color: #64748b;")
            v = QLabel("-"); v.setFont(QFont("Segoe UI", 8)); v.setWordWrap(True); v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            props_grid.addWidget(l, i, 0); props_grid.addWidget(v, i, 1)
            self._dp_props[key] = v
        dp_lay.addLayout(props_grid)
        dp_lay.addSpacing(8)

        lbl_act = QLabel("ACTIONS")
        lbl_act.setObjectName("card_header")
        lbl_act.setFont(QFont("Segoe UI", 9, QFont.Bold))
        dp_lay.addWidget(lbl_act)

        self.btn_open_src = QPushButton("Open Source Location")
        self.btn_open_dst = QPushButton("Open Destination")
        self.btn_copy_path = QPushButton("Copy File Path")
        self.btn_exclude_ext = QPushButton("Exclude Extension")

        for b in [self.btn_open_src, self.btn_open_dst, self.btn_copy_path, self.btn_exclude_ext]:
            b.setObjectName("detail_action_btn")
            b.setFixedHeight(28)
            b.setCursor(Qt.PointingHandCursor)
            dp_lay.addWidget(b)

        self.btn_open_src.clicked.connect(self._action_open_src)
        self.btn_open_dst.clicked.connect(self._action_open_dst)
        self.btn_copy_path.clicked.connect(self._action_copy_path)
        self.btn_exclude_ext.clicked.connect(self._action_exclude_ext)

        dp_lay.addStretch()
        self.splitter.addWidget(self.detail_panel)
        self.splitter.setSizes([600, 300])

        self.content_stack.addWidget(self.splitter)
        lay.addWidget(self.content_stack, 1)

        # Footer Actions
        foot_row = QHBoxLayout()
        self.lbl_summary = QLabel("0 files selected for synchronization.")
        self.lbl_summary.setStyleSheet("color: #64748b; font-size: 11px;")
        
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

    def _make_stat_chip(self, label, value, color):
        chip = QFrame()
        chip.setObjectName("scan_stat_chip")
        chip.setFixedHeight(32)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(6)
        
        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 8px; color: {color};")
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        val = QLabel(value)
        val.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 700;")
        
        lay.addWidget(dot); lay.addWidget(lbl); lay.addWidget(val)
        chip._val = val
        return chip

    def set_results(self, missing_files: list, total: int, missing: int, modified: int, errors: int = 0):
        """Populate scan results, update stats, auto-select all checkboxes, and enable sync buttons"""
        self.source_model.update_data(missing_files)
        self.content_stack.setCurrentIndex(1 if missing_files else 0)
        self.update_chips(total, missing, modified, errors)
        self._update_checked_count()
        if missing_files:
            self.table_view.selectRow(0)
            first_idx = self.proxy_model.index(0, 0)
            self._on_current_changed(first_idx, None)

    def _on_table_clicked(self, proxy_idx):
        if not proxy_idx.isValid():
            return
        if proxy_idx.column() == 0:
            src_idx = self.proxy_model.mapToSource(proxy_idx)
            row = src_idx.row()
            if row in self.source_model.checked_rows:
                self.source_model.checked_rows.discard(row)
            else:
                self.source_model.checked_rows.add(row)
            self.source_model.dataChanged.emit(src_idx, src_idx, [Qt.CheckStateRole])
            self._update_checked_count()
        self._on_current_changed(proxy_idx, None)

    def _on_table_double_clicked(self, proxy_idx):
        if not proxy_idx.isValid():
            return
        src_idx = self.proxy_model.mapToSource(proxy_idx)
        row = src_idx.row()
        if row in self.source_model.checked_rows:
            self.source_model.checked_rows.discard(row)
        else:
            self.source_model.checked_rows.add(row)
        self.source_model.dataChanged.emit(src_idx, src_idx, [Qt.CheckStateRole])
        self._update_checked_count()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            sel = self.table_view.selectionModel().selectedRows()
            if sel:
                first_src = self.proxy_model.mapToSource(sel[0])
                target_add = first_src.row() not in self.source_model.checked_rows
                for p_idx in sel:
                    s_idx = self.proxy_model.mapToSource(p_idx)
                    r = s_idx.row()
                    if target_add:
                        self.source_model.checked_rows.add(r)
                    else:
                        self.source_model.checked_rows.discard(r)
                self.source_model.beginResetModel()
                self.source_model.endResetModel()
                self._update_checked_count()
                event.accept()
                return
        super().keyPressEvent(event)

    def update_chips(self, total, missing, changed, errors):
        self.chip_total._val.setText(str(total))
        self.chip_missing._val.setText(str(missing))
        self.chip_modified._val.setText(str(changed))
        self.chip_errors._val.setText(str(errors))

    def _filter_results_table(self):
        self.proxy_model.set_filters(self.search_input.text(), self.filter_reason_combo.currentText())
        self._update_checked_count()

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

    def _on_model_data_changed(self):
        self._update_checked_count()

    def _update_checked_count(self):
        total = self.proxy_model.rowCount()
        cnt = sum(1 for r in range(total) if self.proxy_model.mapToSource(self.proxy_model.index(r, 0)).row() in self.source_model.checked_rows)
        self.lbl_summary.setText(f"{cnt} of {total} items selected for synchronization.")
        self.btn_sync_sel.setEnabled(cnt > 0)
        self.btn_sync_all.setEnabled(total > 0)

    def _on_current_changed(self, current, _):
        if not current.isValid():
            self.dp_filename.setText("No file selected")
            return
        src_idx = self.proxy_model.mapToSource(current)
        item = self.source_model._data[src_idx.row()]
        self.dp_filename.setText(item.get("filename", ""))
        ext = Path(item.get("filename", "")).suffix or "None"
        self.dp_extension.setText(f"Extension: {ext}")
        self._dp_props["dp_full_path"].setText(clean_display_path(item.get("src_path", "")))
        self._dp_props["dp_rel_path"].setText(item.get("rel_path", ""))
        self._dp_props["dp_size"].setText(item.get("size_str", ""))
        self._dp_props["dp_modified"].setText(item.get("modified_str", ""))

    def _action_open_src(self):
        curr = self.table_view.currentIndex()
        if curr.isValid():
            src_idx = self.proxy_model.mapToSource(curr)
            path = self.source_model._data[src_idx.row()].get("src_path", "")
            if path and os.path.exists(path):
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')

    def _action_open_dst(self):
        curr = self.table_view.currentIndex()
        if curr.isValid():
            src_idx = self.proxy_model.mapToSource(curr)
            path = self.source_model._data[src_idx.row()].get("dest_path", "")
            parent_dir = os.path.dirname(path)
            if parent_dir and os.path.isdir(parent_dir):
                subprocess.Popen(f'explorer "{os.path.normpath(parent_dir)}"')

    def _action_copy_path(self):
        curr = self.table_view.currentIndex()
        if curr.isValid():
            src_idx = self.proxy_model.mapToSource(curr)
            path = self.source_model._data[src_idx.row()].get("src_path", "")
            QApplication.clipboard().setText(path)

    def _action_exclude_ext(self):
        curr = self.table_view.currentIndex()
        if curr.isValid():
            src_idx = self.proxy_model.mapToSource(curr)
            ext = Path(self.source_model._data[src_idx.row()].get("filename", "")).suffix.lower()
            if ext and ext not in self.main_win.excl_exts:
                self.main_win.excl_exts.append(ext)
                self.main_win.settings_page.txt_excl.append(ext)
                self.main_win._save_settings()
                self.main_win._on_scan_clicked()
