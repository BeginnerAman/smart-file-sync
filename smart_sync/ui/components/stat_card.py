from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtGui import QFont

class StatCard(QFrame):
    """Compact and modern metric card for dashboard and summary panels"""
    def __init__(self, title: str, value: str = "0", accent_color: str = "#3b82f6", parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card")
        self.accent_color = accent_color
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setObjectName("stat_label")
        self.lbl_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        
        self.lbl_val = QLabel(value)
        self.lbl_val.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.lbl_val.setStyleSheet(f"color: {accent_color}; background: transparent;")
        
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_val)

    def set_value(self, val):
        self.lbl_val.setText(str(val))
