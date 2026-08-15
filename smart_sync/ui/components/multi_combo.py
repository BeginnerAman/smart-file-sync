from PySide6.QtWidgets import (
    QPushButton, QMenu, QWidgetAction, QCheckBox, QVBoxLayout,
    QHBoxLayout, QLabel, QFrame, QScrollArea, QWidget
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal

from ...utils.constants import FILE_FILTERS
from .icons import IconManager

class MultiCheckFilterButton(QPushButton):
    """
    Rock-solid checkable multi-select dropdown button.
    Opens a styled checkable popup container where checkboxes can be toggled without premature closing.
    """
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filter_btn")
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("text-align: left; padding: 4px 10px;")

        self._menu = QMenu(self)
        self._menu.setObjectName("filter_menu")
        self.setMenu(self._menu)

        self._checkboxes = {}
        self._categories = list(FILE_FILTERS.keys())

        self._build_menu()
        self._update_button_text()

    def _build_menu(self):
        self._menu.clear()
        
        container = QFrame()
        container.setObjectName("filter_popup_frame")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        hdr = QLabel("SELECT FILE TYPES TO SCAN")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Bold))
        hdr.setStyleSheet("color: #38bdf8; padding-bottom: 2px;")
        lay.addWidget(hdr)

        for text in self._categories:
            chk = QCheckBox(text)
            chk.setFont(QFont("Segoe UI", 9))
            chk.setCursor(Qt.PointingHandCursor)
            
            if text == "All Files":
                chk.setChecked(True)
            else:
                chk.setChecked(False)

            chk.toggled.connect(lambda checked, t=text: self._on_check_toggled(t, checked))
            self._checkboxes[text] = chk
            lay.addWidget(chk)

        # Quick Actions Row (Select All / Clear)
        act_row = QHBoxLayout()
        act_row.setContentsMargins(0, 6, 0, 0)
        
        btn_all = QPushButton("All")
        btn_all.setObjectName("mini_btn")
        btn_all.setFixedHeight(24)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(self._select_all)
        act_row.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.setObjectName("mini_btn")
        btn_none.setFixedHeight(24)
        btn_none.setCursor(Qt.PointingHandCursor)
        btn_none.clicked.connect(self._clear_all)
        act_row.addWidget(btn_none)

        lay.addLayout(act_row)

        action = QWidgetAction(self._menu)
        action.setDefaultWidget(container)
        self._menu.addAction(action)

    def _on_check_toggled(self, category_text: str, checked: bool):
        # Block signals temporarily to prevent recursive loops
        for chk in self._checkboxes.values():
            chk.blockSignals(True)

        if category_text == "All Files":
            if checked:
                # If 'All Files' is checked, uncheck all others
                for t, chk in self._checkboxes.items():
                    if t != "All Files":
                        chk.setChecked(False)
        else:
            if checked:
                # If specific category checked, uncheck 'All Files'
                self._checkboxes["All Files"].setChecked(False)
            else:
                # If no specific category is checked, re-check 'All Files'
                any_checked = any(
                    chk.isChecked() for t, chk in self._checkboxes.items() if t != "All Files"
                )
                if not any_checked:
                    self._checkboxes["All Files"].setChecked(True)

        # Unblock signals
        for chk in self._checkboxes.values():
            chk.blockSignals(False)

        self._update_button_text()
        self.selectionChanged.emit()

    def _select_all(self):
        for chk in self._checkboxes.values():
            chk.blockSignals(True)
        self._checkboxes["All Files"].setChecked(True)
        for t, chk in self._checkboxes.items():
            if t != "All Files":
                chk.setChecked(False)
        for chk in self._checkboxes.values():
            chk.blockSignals(False)
        self._update_button_text()
        self.selectionChanged.emit()

    def _clear_all(self):
        self._select_all()

    def _update_button_text(self):
        if self._checkboxes.get("All Files") and self._checkboxes["All Files"].isChecked():
            self.setText("  All Files (Default)")
            return

        selected = []
        for t, chk in self._checkboxes.items():
            if t != "All Files" and chk.isChecked():
                short = t.split(" (")[0]
                selected.append(short)

        if not selected:
            self.setText("  All Files (Default)")
        elif len(selected) == 1:
            self.setText(f"  {selected[0]}")
        elif len(selected) == 2:
            self.setText(f"  {selected[0]}, {selected[1]}")
        else:
            self.setText(f"  {selected[0]}, +{len(selected)-1} more ({len(selected)} types)")

    def currentText(self) -> str:
        return self.text().strip()

    def findText(self, text: str) -> int:
        for idx, t in enumerate(self._categories):
            if text in t or t in text:
                return idx
        return -1

    def setCurrentIndex(self, idx: int):
        if 0 <= idx < len(self._categories):
            cat = self._categories[idx]
            for t, chk in self._checkboxes.items():
                chk.setChecked(t == cat)
            self._update_button_text()
            self.selectionChanged.emit()

    def get_selected_extensions(self) -> list:
        """Return list of lowercase extensions, or empty list for all files"""
        if self._checkboxes.get("All Files") and self._checkboxes["All Files"].isChecked():
            return []

        exts = []
        for t, chk in self._checkboxes.items():
            if t != "All Files" and chk.isChecked():
                category_exts = FILE_FILTERS.get(t, [])
                exts.extend(category_exts)
        return list(set(exts))
