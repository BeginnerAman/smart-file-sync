import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QStackedWidget, QFileDialog
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ..components.stat_card import StatCard
from ..components.empty_state import EmptyStateWidget
from ..dialogs.custom_dialogs import SmartConfirmActionDialog
from ...models.history_model import HistoryManager
from ...utils.formatters import fmt_size

class HistorySessionCard(QFrame):
    """Clean Session Card with Scoped Styling and Setup Loader"""
    def __init__(self, session_data: dict, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("history_session_card")
        self.main_win = main_win
        self.session_data = session_data
        self.setProperty("selected", False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # Header Row
        hdr = QHBoxLayout()
        t_lbl = QLabel(session_data.get("timestamp", ""))
        t_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        t_lbl.setStyleSheet("color: #f8fafc;" if main_win.dark_mode else "color: #1e293b;")

        status = session_data.get("status", "Success")
        status_lbl = QLabel(f" {status.upper()} ")
        status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        status_lbl.setFixedHeight(20)
        
        dark = main_win.dark_mode
        if status == "Success":
            bg = "#10b981" if dark else "#d1fae5"
            fg = "#ffffff" if dark else "#065f46"
        else:
            bg = "#ef4444" if dark else "#fee2e2"
            fg = "#ffffff" if dark else "#991b1b"
        status_lbl.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 4px;")

        btn_load = QPushButton("Load into Setup")
        btn_load.setObjectName("mini_btn")
        btn_load.setFixedHeight(26)
        btn_load.setMinimumWidth(115)
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.clicked.connect(self._load_config)

        hdr.addWidget(t_lbl)
        hdr.addWidget(status_lbl)
        hdr.addStretch()
        hdr.addWidget(btn_load)
        lay.addLayout(hdr)

        # Paths
        p_lay = QVBoxLayout(); p_lay.setSpacing(2)
        s_lbl = QLabel(f"Source:      {session_data.get('source', '')}")
        s_lbl.setFont(QFont("Segoe UI", 9)); s_lbl.setStyleSheet("color: #94a3b8;")
        d_lbl = QLabel(f"Destination: {session_data.get('destination', '')}")
        d_lbl.setFont(QFont("Segoe UI", 9)); d_lbl.setStyleSheet("color: #94a3b8;")
        p_lay.addWidget(s_lbl); p_lay.addWidget(d_lbl)
        lay.addLayout(p_lay)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #1f2937;" if dark else "background-color: #e2e8f0;")
        div.setFixedHeight(1)
        lay.addWidget(div)

        # Metrics
        m_lay = QHBoxLayout(); m_lay.setSpacing(16)
        m_dur = self._metric_item("DURATION", session_data.get("duration", "-"))
        m_files = self._metric_item("FILES SYNCED", str(session_data.get("copied", 0)))
        m_data = self._metric_item("DATA TRANSFERRED", session_data.get("copied_size", "0 B"))
        m_err = self._metric_item("ERRORS", str(session_data.get("errors", 0)), is_err=(int(session_data.get("errors", 0)) > 0))
        m_lay.addWidget(m_dur); m_lay.addWidget(m_files); m_lay.addWidget(m_data); m_lay.addWidget(m_err)
        lay.addLayout(m_lay)

    def _metric_item(self, label, value, is_err=False):
        w = QWidget(); w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(2)
        l = QLabel(label); l.setFont(QFont("Segoe UI", 8, QFont.Bold)); l.setStyleSheet("color: #64748b;")
        v = QLabel(value); v.setFont(QFont("Segoe UI", 10, QFont.Bold))
        v.setStyleSheet("color: #ef4444;" if is_err else ("color: #f8fafc;" if self.main_win.dark_mode else "color: #1e293b;"))
        lay.addWidget(l); lay.addWidget(v)
        return w

    def _load_config(self):
        try:
            src = self.session_data.get("source", "")
            dst = self.session_data.get("destination", "")
            self.main_win.folder_setup_page.card_src.input.setText(src)
            self.main_win.folder_setup_page.card_dst.input.setText(dst)
            
            filt = self.session_data.get("filter", "All Files")
            idx = self.main_win.folder_setup_page.filter_combo.findText(filt)
            if idx >= 0:
                self.main_win.folder_setup_page.filter_combo.setCurrentIndex(idx)
                
            self.main_win.folder_setup_page._trigger_metadata_scan("src")
            self.main_win.folder_setup_page._trigger_metadata_scan("dst")
            self.main_win._on_nav_clicked(0)
            self.main_win._add_log(f"Loaded configuration from history: '{src}' -> '{dst}'", "info")
            self.main_win.status_bar.showMessage("Loaded session configuration into Folder Setup.")
        except Exception as e:
            self.main_win._add_log(f"Failed to load history configuration: {e}", "error")

    def mousePressEvent(self, event):
        self.main_win.history_page.select_card(self)
        super().mousePressEvent(event)

    def setSelected(self, sel: bool):
        self.setProperty("selected", sel)
        self.style().unpolish(self)
        self.style().polish(self)

class HistoryPage(QWidget):
    """Step 5: Audit Logs and Sync Session History with Purge Option"""
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.cards = []
        self.selected_card = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # Header Title
        v_title = QVBoxLayout(); v_title.setSpacing(2)
        lbl_title = QLabel("Sync History")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Audit past directory scan configurations and completed file sync states.")
        lbl_sub.setObjectName("page_subtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        lay.addLayout(v_title)

        # Summary Row (Compact)
        sum_lay = QHBoxLayout(); sum_lay.setSpacing(10)
        self.card_total = StatCard("Total Sessions", "0", "#3b82f6")
        self.card_files = StatCard("Files Synced", "0", "#10b981")
        self.card_data = StatCard("Total Data", "0 B", "#06b6d4")
        self.card_rate = StatCard("Success Rate", "100%", "#f59e0b")
        
        for c in [self.card_total, self.card_files, self.card_data, self.card_rate]:
            sum_lay.addWidget(c)
        lay.addLayout(sum_lay)

        # Toolbar: Refresh, Export, Clear History, Search
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        ref_btn = QPushButton("Refresh Logs")
        ref_btn.setObjectName("mini_btn")
        ref_btn.setFixedHeight(30)
        ref_btn.setCursor(Qt.PointingHandCursor)
        ref_btn.clicked.connect(self.main_win._load_history)
        ctrl.addWidget(ref_btn)

        exp_btn = QPushButton("Export Log CSV")
        exp_btn.setObjectName("mini_btn")
        exp_btn.setFixedHeight(30)
        exp_btn.setCursor(Qt.PointingHandCursor)
        exp_btn.clicked.connect(self._export_csv)
        ctrl.addWidget(exp_btn)

        # Clear History Button
        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("mini_btn")
        clear_btn.setFixedHeight(30)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_history_clicked)
        ctrl.addWidget(clear_btn)

        ctrl.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("Search history logs...")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self._filter_history)
        ctrl.addWidget(self.search_input)

        self.lbl_session_count = QLabel("0 sessions")
        self.lbl_session_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ctrl.addWidget(self.lbl_session_count)
        lay.addLayout(ctrl)

        # History List Container
        self.hist_container = QStackedWidget()
        
        self.empty_state = EmptyStateWidget(
            "history",
            "No synchronization history available.",
            "Run your first directory scan and synchronization to begin recording history logs.",
            btn_text="Open Folder Setup",
            btn_callback=lambda: self.main_win._on_nav_clicked(0)
        )
        self.hist_container.addWidget(self.empty_state)

        self.hist_scroll = QScrollArea()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.hist_list_widget = QWidget()
        self.hist_list_widget.setStyleSheet("background: transparent;")
        self.hist_list_lay = QVBoxLayout(self.hist_list_widget)
        self.hist_list_lay.setContentsMargins(0, 0, 0, 0)
        self.hist_list_lay.setSpacing(10)
        self.hist_list_lay.addStretch()
        
        self.hist_scroll.setWidget(self.hist_list_widget)
        self.hist_container.addWidget(self.hist_scroll)

        lay.addWidget(self.hist_container, 1)

    def select_card(self, card):
        if self.selected_card:
            self.selected_card.setSelected(False)
        self.selected_card = card
        if card:
            card.setSelected(True)

    def _filter_history(self):
        text = self.search_input.text().strip().lower()
        vis = 0
        for c in self.cards:
            d = c.session_data
            match = not text or any(text in str(v).lower() for v in d.values())
            c.setVisible(match)
            if match: vis += 1
        self.lbl_session_count.setText(f"Showing {vis} of {len(self.cards)} sessions")

    def _export_csv(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export History CSV", "sync_history.csv", "CSV Files (*.csv)")
        if fn:
            if HistoryManager.export_csv(fn):
                self.main_win._add_log(f"Exported history log to: {fn}", "success")

    def _clear_history_clicked(self):
        diag = SmartConfirmActionDialog(
            "Clear History Logs",
            "Are you sure you want to permanently delete all synchronization history audit records?",
            action_button_text="Delete All",
            parent=self
        )
        if diag.exec() == SmartConfirmActionDialog.Accepted:
            HistoryManager.clear_history()
            self.main_win._load_history()
            self.main_win._add_log("History records cleared successfully.", "info")
