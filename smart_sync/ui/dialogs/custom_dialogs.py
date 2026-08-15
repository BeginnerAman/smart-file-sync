from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout, QProgressBar,
    QScrollArea, QComboBox, QWidget
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

class BaseSmartDialog(QDialog):
    """Clean, single-header modal dialog with working close button and Esc dismiss"""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setMinimumWidth(400)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

class SmartConfirmDialog(BaseSmartDialog):
    """Modern Confirmation Modal for starting file synchronization"""
    def __init__(self, src: str, dst: str, files_count: int, size_str: str, dry_run: bool, parent=None):
        super().__init__("Confirm Synchronization", parent)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        
        # Heading
        lbl_h = QLabel("Confirm Synchronization")
        lbl_h.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lay.addWidget(lbl_h)
        
        # Details Card
        card = QFrame()
        card.setObjectName("stat_card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)
        
        t_src = QLabel("Source:"); t_src.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v_src = QLabel(src); v_src.setFont(QFont("Segoe UI", 9)); v_src.setWordWrap(True)
        
        t_dst = QLabel("Destination:"); t_dst.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v_dst = QLabel(dst); v_dst.setFont(QFont("Segoe UI", 9)); v_dst.setWordWrap(True)
        
        t_cnt = QLabel("Files Selected:"); t_cnt.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v_cnt = QLabel(f"{files_count:,} files"); v_cnt.setFont(QFont("Segoe UI", 9))
        
        t_sz = QLabel("Transfer Size:"); t_sz.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v_sz = QLabel(size_str); v_sz.setFont(QFont("Segoe UI", 9))
        
        t_dry = QLabel("Dry Run Mode:"); t_dry.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v_dry = QLabel("Enabled (Preview Only)" if dry_run else "Disabled (Live Transfer)")
        v_dry.setFont(QFont("Segoe UI", 9))
        v_dry.setStyleSheet("color: #f59e0b;" if dry_run else "color: #10b981;")
        
        grid.addWidget(t_src, 0, 0); grid.addWidget(v_src, 0, 1)
        grid.addWidget(t_dst, 1, 0); grid.addWidget(v_dst, 1, 1)
        grid.addWidget(t_cnt, 2, 0); grid.addWidget(v_cnt, 2, 1)
        grid.addWidget(t_sz, 3, 0); grid.addWidget(v_sz, 3, 1)
        grid.addWidget(t_dry, 4, 0); grid.addWidget(v_dry, 4, 1)
        lay.addWidget(card)
        
        lbl_q = QLabel("Do you want to start the synchronization process?")
        lbl_q.setFont(QFont("Segoe UI", 9))
        lbl_q.setStyleSheet("color: #94a3b8;")
        lay.addWidget(lbl_q)
        
        # Action Buttons
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)
        btn_lay.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QPushButton("Start Sync")
        self.btn_ok.setObjectName("btn_sync")
        self.btn_ok.setFixedHeight(32)
        self.btn_ok.setFixedWidth(110)
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        
        btn_lay.addWidget(self.btn_cancel)
        btn_lay.addWidget(self.btn_ok)
        lay.addLayout(btn_lay)

class SmartCompleteDialog(BaseSmartDialog):
    """Modern Completion Modal for completed synchronization runs"""
    def __init__(self, summary: dict, parent=None):
        super().__init__("Operation Complete", parent)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        
        status = summary.get("status", "Success")
        status_color = "#10b981" if "Success" in status else "#ef4444"
        
        lbl_h = QLabel("Sync Operation Complete")
        lbl_h.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lay.addWidget(lbl_h)
        
        # Summary Card
        card = QFrame()
        card.setObjectName("stat_card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)
        
        t1 = QLabel("Result Status:"); t1.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v1 = QLabel(status.upper()); v1.setFont(QFont("Segoe UI", 9, QFont.Bold)); v1.setStyleSheet(f"color: {status_color};")
        
        t2 = QLabel("Files Synced:"); t2.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v2 = QLabel(f"{summary.get('copied', 0):,} of {summary.get('total_files', 0):,} files"); v2.setFont(QFont("Segoe UI", 9))
        
        t3 = QLabel("Data Copied:"); t3.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v3 = QLabel(summary.get("copied_size", "0 B")); v3.setFont(QFont("Segoe UI", 9))
        
        t4 = QLabel("Elapsed Time:"); t4.setFont(QFont("Segoe UI", 9, QFont.Bold))
        v4 = QLabel(summary.get("duration", "0s")); v4.setFont(QFont("Segoe UI", 9))
        
        grid.addWidget(t1, 0, 0); grid.addWidget(v1, 0, 1)
        grid.addWidget(t2, 1, 0); grid.addWidget(v2, 1, 1)
        grid.addWidget(t3, 2, 0); grid.addWidget(v3, 2, 1)
        grid.addWidget(t4, 3, 0); grid.addWidget(v4, 3, 1)
        lay.addWidget(card)
        
        # Dismiss Button
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_ok = QPushButton("Dismiss")
        btn_ok.setObjectName("btn_sync")
        btn_ok.setFixedHeight(32)
        btn_ok.setFixedWidth(100)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)
        btn_lay.addWidget(btn_ok)
        lay.addLayout(btn_lay)

class SmartNoticeDialog(BaseSmartDialog):
    """Modern themed notification alert replacing raw OS QMessageBox"""
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(title, parent)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        
        lbl_h = QLabel(title)
        lbl_h.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lay.addWidget(lbl_h)
        
        card = QFrame()
        card.setObjectName("stat_card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 12)
        
        lbl_m = QLabel(message)
        lbl_m.setFont(QFont("Segoe UI", 10))
        lbl_m.setWordWrap(True)
        lbl_m.setStyleSheet("color: #94a3b8; line-height: 1.4;")
        c_lay.addWidget(lbl_m)
        lay.addWidget(card)
        
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_ok = QPushButton("Dismiss")
        btn_ok.setObjectName("mini_btn")
        btn_ok.setFixedHeight(30)
        btn_ok.setFixedWidth(90)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)
        btn_lay.addWidget(btn_ok)
        lay.addLayout(btn_lay)

class SmartConfirmActionDialog(BaseSmartDialog):
    """Modal confirmation for critical actions like Purging History"""
    def __init__(self, title: str, message: str, action_button_text: str = "Confirm", parent=None):
        super().__init__(title, parent)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        
        lbl_h = QLabel(title)
        lbl_h.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lay.addWidget(lbl_h)
        
        card = QFrame()
        card.setObjectName("stat_card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 12)
        
        lbl_m = QLabel(message)
        lbl_m.setFont(QFont("Segoe UI", 10))
        lbl_m.setWordWrap(True)
        lbl_m.setStyleSheet("color: #94a3b8;")
        c_lay.addWidget(lbl_m)
        lay.addWidget(card)
        
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)
        btn_lay.addStretch()
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setFixedWidth(90)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        
        btn_act = QPushButton(action_button_text)
        btn_act.setObjectName("btn_danger" if any(w in action_button_text for w in ["Delete", "Clear", "Reset"]) else "btn_sync")
        btn_act.setFixedHeight(32)
        btn_act.setMinimumWidth(130)
        btn_act.setCursor(Qt.PointingHandCursor)
        btn_act.setStyleSheet("padding: 4px 16px; font-weight: 600;")
        btn_act.clicked.connect(self.accept)
        
        btn_lay.addWidget(btn_cancel)
        btn_lay.addWidget(btn_act)
        lay.addLayout(btn_lay)


class ScanProgressDialog(BaseSmartDialog):
    """Non-blocking scan progress modal with cancel support"""
    def __init__(self, parent=None):
        super().__init__("Directory Scan in Progress", parent)
        self.setMinimumWidth(420)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        lbl_h = QLabel("Scanning Directories")
        lbl_h.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lay.addWidget(lbl_h)

        self.lbl_phase = QLabel("Initializing scan...")
        self.lbl_phase.setStyleSheet("font-size: 12px;")
        lay.addWidget(self.lbl_phase)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("main_progress")
        self.progress_bar.setRange(0, 0)  # Indeterminate initially
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        lay.addWidget(self.progress_bar)

        self.lbl_count = QLabel("0 files scanned")
        self.lbl_count.setStyleSheet("color: #64748b; font-size: 11px;")
        lay.addWidget(self.lbl_count)

        btn_cancel = QPushButton("Cancel Scan")
        btn_cancel.setObjectName("mini_btn")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        lay.addWidget(btn_cancel, alignment=Qt.AlignRight)

        self._cancelled = False

    def update_progress(self, phase: str, count: int):
        self.lbl_phase.setText(phase)
        self.lbl_count.setText(f"{count:,} files scanned")

    def close_finished(self):
        self._cancelled = False
        self.accept()

    def reject(self):
        self._cancelled = True
        super().reject()

    def was_cancelled(self) -> bool:
        return self._cancelled

class ConflictResolutionDialog(QDialog):
    """Dialog shown when bidirectional sync finds conflicts."""
    def __init__(self, conflicts: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Resolve Sync Conflicts')
        self.setMinimumSize(600, 400)
        self.conflicts = conflicts
        self.resolutions = {}  # rel_path -> 'source' | 'dest' | 'skip' | 'both'
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        hdr = QLabel(f'{len(conflicts)} Conflict(s) Found')
        hdr.setFont(QFont('Segoe UI', 14, QFont.Bold))
        layout.addWidget(hdr)
        
        desc = QLabel('These files were modified in both source and destination. Choose how to resolve each:')
        desc.setWordWrap(True)
        desc.setFont(QFont('Segoe UI', 10))
        layout.addWidget(desc)
        
        # Quick actions
        quick_row = QHBoxLayout()
        btn_all_source = QPushButton('All → Keep Source')
        btn_all_source.clicked.connect(lambda: self._set_all('source'))
        btn_all_dest = QPushButton('All → Keep Destination')
        btn_all_dest.clicked.connect(lambda: self._set_all('dest'))
        btn_all_newer = QPushButton('All → Keep Newer')
        btn_all_newer.clicked.connect(lambda: self._set_all('newer'))
        btn_all_both = QPushButton('All → Keep Both')
        btn_all_both.clicked.connect(lambda: self._set_all('both'))
        for btn in [btn_all_source, btn_all_dest, btn_all_newer, btn_all_both]:
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            quick_row.addWidget(btn)
        layout.addLayout(quick_row)
        
        # Scroll area with conflict items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.conflict_layout = QVBoxLayout(scroll_widget)
        self.conflict_layout.setSpacing(8)
        
        self.combos = {}
        for c in conflicts:
            rel = c['rel_path']
            row = QHBoxLayout()
            
            lbl = QLabel(rel)
            lbl.setFont(QFont('Segoe UI', 9))
            lbl.setToolTip(f"Source: {c.get('src_mtime', 'N/A')}\nDest: {c.get('dst_mtime', 'N/A')}")
            
            combo = QComboBox()
            combo.addItems(['Keep Source', 'Keep Destination', 'Keep Both (rename)', 'Skip'])
            combo.setFixedWidth(200)
            self.combos[rel] = combo
            
            row.addWidget(lbl, 1)
            row.addWidget(combo)
            self.conflict_layout.addLayout(row)
        
        self.conflict_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)
        
        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton('Cancel')
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton('Apply & Continue')
        btn_apply.setObjectName('btn_scan')
        btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_apply)
        layout.addLayout(btn_row)
    
    def _set_all(self, policy):
        for rel, combo in self.combos.items():
            if policy == 'source':
                combo.setCurrentIndex(0)
            elif policy == 'dest':
                combo.setCurrentIndex(1)
            elif policy == 'both':
                combo.setCurrentIndex(2)
            elif policy == 'newer':
                # Determine which is newer
                conflict = next((c for c in self.conflicts if c['rel_path'] == rel), None)
                if conflict:
                    if conflict.get('src_mtime', 0) >= conflict.get('dst_mtime', 0):
                        combo.setCurrentIndex(0)  # source newer
                    else:
                        combo.setCurrentIndex(1)  # dest newer
    
    def _apply(self):
        for rel, combo in self.combos.items():
            idx = combo.currentIndex()
            self.resolutions[rel] = ['source', 'dest', 'both', 'skip'][idx]
        self.accept()

