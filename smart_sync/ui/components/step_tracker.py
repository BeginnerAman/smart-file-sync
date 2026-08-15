from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

class VisualStepTracker(QFrame):
    """Modern horizontal workflow stage progress bar with connected step pills"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step_tracker")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        
        self.step1 = QLabel("1  Setup")
        self.step2 = QLabel("2  Scan")
        self.step3 = QLabel("3  Review")
        self.step4 = QLabel("4  Sync")
        
        self.arrows = [QLabel("→"), QLabel("→"), QLabel("→")]
        
        for lbl in self.arrows:
            lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl.setStyleSheet("color: #475569; background: transparent;")
            
        for s in [self.step1, self.step2, self.step3, self.step4]:
            s.setFont(QFont("Segoe UI", 9, QFont.Bold))
            s.setAlignment(Qt.AlignCenter)
            s.setFixedHeight(24)
            s.setStyleSheet("color: #64748b; background: transparent; padding: 2px 10px; border-radius: 12px;")
            
        lay.addWidget(self.step1)
        lay.addWidget(self.arrows[0])
        lay.addWidget(self.step2)
        lay.addWidget(self.arrows[1])
        lay.addWidget(self.step3)
        lay.addWidget(self.arrows[2])
        lay.addWidget(self.step4)
        lay.addStretch()
        
        self.set_active_step(1)
        
    def set_active_step(self, step_num: int):
        steps = [self.step1, self.step2, self.step3, self.step4]
        labels = ["Setup", "Scan", "Review", "Sync"]
        for i, s in enumerate(steps):
            if i + 1 < step_num:
                s.setText(f"✓  {labels[i]}")
                s.setStyleSheet("color: #10b981; font-weight: bold; background-color: rgba(16, 185, 129, 0.12); padding: 2px 10px; border-radius: 12px;")
            elif i + 1 == step_num:
                s.setText(f"●  {labels[i]}")
                s.setStyleSheet("color: #3b82f6; font-weight: bold; background-color: rgba(59, 130, 246, 0.16); padding: 2px 10px; border-radius: 12px;")
            else:
                s.setText(f"{i+1}  {labels[i]}")
                s.setStyleSheet("color: #64748b; background: transparent; padding: 2px 10px; border-radius: 12px;")
