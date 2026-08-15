from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ...utils.formatters import fmt_size

class FolderMetaCard(QFrame):
    """Clean Directory Selection Card with Live Metadata Preview"""
    def __init__(self, title: str, placeholder: str, browse_callback, parent=None):
        super().__init__(parent)
        self.setObjectName("folder_card")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        
        # Header Row
        lbl_title = QLabel(title.upper())
        lbl_title.setObjectName("card_header")
        lbl_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lay.addWidget(lbl_title)
        
        # Input & Browse Button
        in_lay = QHBoxLayout()
        in_lay.setSpacing(8)
        
        self.input = QLineEdit()
        self.input.setObjectName("path_input")
        self.input.setPlaceholderText(placeholder)
        
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setObjectName("btn_browse")
        self.btn_browse.setFixedHeight(32)
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(browse_callback)
        
        in_lay.addWidget(self.input, 1)
        in_lay.addWidget(self.btn_browse)
        lay.addLayout(in_lay)
        
        # Metadata Frame
        meta_frame = QFrame()
        meta_frame.setObjectName("folder_stats_frame")
        grid = QGridLayout(meta_frame)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(6)
        
        self.lbl_size = QLabel("-")
        self.lbl_count = QLabel("-")
        self.lbl_mtime = QLabel("-")
        
        for lbl in [self.lbl_size, self.lbl_count, self.lbl_mtime]:
            lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl.setStyleSheet("color: #94a3b8; background: transparent;")
            
        t_size = QLabel("Total Size")
        t_count = QLabel("File Count")
        t_mtime = QLabel("Last Modified")
        
        for t in [t_size, t_count, t_mtime]:
            t.setObjectName("folder_meta_lbl")
            t.setFont(QFont("Segoe UI", 8))
            
        grid.addWidget(t_size, 0, 0); grid.addWidget(self.lbl_size, 0, 1)
        grid.addWidget(t_count, 1, 0); grid.addWidget(self.lbl_count, 1, 1)
        grid.addWidget(t_mtime, 2, 0); grid.addWidget(self.lbl_mtime, 2, 1)
        
        lay.addWidget(meta_frame)

    def set_stats(self, count: int, size_bytes: int, mtime_str: str):
        self.lbl_count.setText(f"{count:,} files" if count >= 0 else "-")
        self.lbl_size.setText(fmt_size(size_bytes) if size_bytes >= 0 else "-")
        self.lbl_mtime.setText(mtime_str or "-")

    def reset_stats(self):
        self.lbl_count.setText("-")
        self.lbl_size.setText("-")
        self.lbl_mtime.setText("-")
