from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from .icons import IconManager

class EmptyStateWidget(QWidget):
    """Modern placeholder widget for empty tables, queues, and history lists"""
    def __init__(self, icon_name: str, title: str, subtitle: str, btn_text: str = "", btn_callback=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(12)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(IconManager.get_vector_pixmap(icon_name, "#64748b", 48))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(icon_lbl)
        
        lbl_t = QLabel(title)
        lbl_t.setObjectName("empty_title")
        lbl_t.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl_t.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_t)
        
        lbl_s = QLabel(subtitle)
        lbl_s.setObjectName("empty_details")
        lbl_s.setFont(QFont("Segoe UI", 10))
        lbl_s.setAlignment(Qt.AlignCenter)
        lbl_s.setWordWrap(True)
        lbl_s.setMaximumWidth(460)
        lay.addWidget(lbl_s)
        
        if btn_text and btn_callback:
            btn = QPushButton(btn_text)
            btn.setObjectName("btn_sync")
            btn.setFixedHeight(34)
            btn.setFixedWidth(180)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(btn_callback)
            lay.addSpacing(6)
            lay.addWidget(btn, alignment=Qt.AlignCenter)
