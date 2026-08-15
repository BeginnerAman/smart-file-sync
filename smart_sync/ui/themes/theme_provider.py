def get_theme_stylesheet(dark_mode: bool = True) -> str:
    """
    Centralized, comprehensive theme stylesheet.
    Guarantees crisp typography, proper contrast, and zero inline-style bleed.
    """
    if dark_mode:
        return """
        * {
            font-family: 'Segoe UI', -apple-system, sans-serif;
            font-size: 13px;
            outline: none;
        }

        QMainWindow, QDialog {
            background-color: #0b0f19;
            color: #f8fafc;
        }

        QWidget {
            color: #f8fafc;
        }

        /* ── PAGE TYPOGRAPHY ── */
        QLabel#page_title {
            font-size: 20px;
            font-weight: 700;
            color: #f8fafc;
        }
        QLabel#page_subtitle {
            font-size: 12px;
            color: #94a3b8;
        }
        QLabel#card_header, QLabel#stat_label {
            font-size: 9px;
            font-weight: 700;
            color: #94a3b8;
            letter-spacing: 1px;
        }
        QLabel#small_lbl {
            font-size: 11px;
            color: #94a3b8;
        }
        QLabel#chip_lbl {
            font-size: 11px;
            color: #94a3b8;
            font-weight: 500;
        }

        /* ── SIDEBAR ── */
        QFrame#sidebar {
            background-color: #060911;
            border-right: 1px solid #131b2e;
        }
        QLabel#app_title {
            color: #f8fafc;
            font-weight: 700;
            font-size: 13px;
        }
        QFrame#sidebar_footer {
            border-top: 1px solid #131b2e;
            background-color: transparent;
        }

        /* Nav Buttons */
        QPushButton#nav_btn {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            margin: 3px 6px;
            text-align: left;
        }
        QPushButton#nav_btn:hover {
            background-color: #131b2e;
        }
        QPushButton#nav_btn:checked {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
        }
        QLabel#nav_lbl {
            color: #94a3b8;
            font-size: 13px;
            background: transparent;
        }
        QLabel#nav_shortcut {
            color: #475569;
            font-size: 10px;
            background: transparent;
        }
        QLabel#nav_badge {
            background-color: #2563eb;
            color: #ffffff;
            border-radius: 7px;
            font-size: 9px;
            font-weight: bold;
            padding: 1px 6px;
            height: 14px;
        }
        QPushButton#nav_btn:hover QLabel#nav_lbl { color: #f8fafc; }
        QPushButton#nav_btn:checked QLabel#nav_lbl { color: #f8fafc; font-weight: 600; }
        QPushButton#nav_btn:checked QLabel#nav_shortcut { color: #3b82f6; }

        /* ── TOP BAR ── */
        QFrame#topbar {
            background-color: #0b0f19;
            border-bottom: 1px solid #131b2e;
        }
        QLabel#breadcrumb_lbl {
            color: #3b82f6;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
        }
        QLineEdit#global_search_input {
            background-color: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 4px 10px;
            color: #f8fafc;
        }
        QLineEdit#global_search_input:focus {
            border-color: #3b82f6;
        }

        QPushButton#icon_btn, QPushButton#mini_btn {
            background-color: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 6px;
            color: #f8fafc;
            padding: 4px 12px;
        }
        QPushButton#icon_btn:hover, QPushButton#mini_btn:hover {
            background-color: #1e293b;
            border-color: #334155;
        }

        /* ── PRIMARY BUTTONS ── */
        QPushButton#btn_scan, QPushButton#btn_sync {
            background-color: #2563eb;
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#btn_scan:hover, QPushButton#btn_sync:hover {
            background-color: #1d4ed8;
        }
        QPushButton#btn_scan:disabled, QPushButton#btn_sync:disabled {
            background-color: #1e293b;
            color: #475569;
        }

        QPushButton#btn_sel {
            background-color: #0d9488;
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#btn_sel:hover { background-color: #0f766e; }
        QPushButton#btn_sel:disabled { background-color: #1e293b; color: #475569; }

        QPushButton#btn_browse {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            color: #f8fafc;
            padding: 0 14px;
            font-weight: 500;
        }
        QPushButton#btn_browse:hover {
            background-color: #334155;
        }

        QPushButton#filter_btn {
            background-color: #0f1422;
            border: 1px solid #1e293b;
            border-radius: 6px;
            color: #f8fafc;
            text-align: left;
            padding: 4px 12px;
        }
        QPushButton#filter_btn:hover {
            border-color: #38bdf8;
            background-color: #131b2e;
        }
        QPushButton#filter_btn::menu-indicator {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            right: 8px;
        }
        QMenu#filter_menu {
            background-color: #0d121f;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 4px;
        }
        QFrame#filter_popup_frame {
            background-color: transparent;
        }

        QPushButton#btn_cancel {
            background-color: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 6px;
            color: #94a3b8;
        }
        QPushButton#btn_cancel:hover {
            background-color: #1e293b;
            color: #f8fafc;
        }

        QPushButton#btn_danger {
            background-color: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.35);
            border-radius: 6px;
            color: #f87171;
            font-weight: 600;
            padding: 4px 16px;
        }
        QPushButton#btn_danger:hover {
            background-color: #dc2626;
            color: #ffffff;
            border-color: #dc2626;
        }

        /* ── CARDS & PANELS ── */
        QFrame#stat_card, QFrame#folder_card, QFrame#dashboard_panel, QFrame#options_panel, QFrame#settings_pane {
            background-color: #111726;
            border: 1px solid #1e293b;
            border-radius: 10px;
        }
        QFrame#preset_card {
            background-color: #0f1422;
            border: 1px solid #1e293b;
            border-radius: 10px;
        }
        QFrame#preset_card:hover {
            border-color: #334155;
            background-color: #131b2e;
        }
        QFrame#history_session_card {
            background-color: #0f1422;
            border: 1px solid #1e293b;
            border-radius: 10px;
        }
        QFrame#history_session_card:hover {
            border-color: #334155;
            background-color: #131b2e;
        }
        QFrame#history_session_card[selected="true"] {
            border: 1px solid #3b82f6;
            background-color: #131b2e;
        }
        QFrame#folder_stats_frame {
            background-color: #0b0f19;
            border: 1px solid #1e293b;
            border-radius: 6px;
        }

        /* ── INPUTS & COMBOS ── */
        QLineEdit#path_input, QLineEdit#search_input, QLineEdit {
            background-color: #0b0f19;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 6px 12px;
            color: #f8fafc;
        }
        QLineEdit:focus {
            border-color: #3b82f6;
        }

        QComboBox {
            background-color: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 4px 10px;
            color: #f8fafc;
        }
        QComboBox:focus { border-color: #3b82f6; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox QAbstractItemView {
            background-color: #131b2e;
            color: #f8fafc;
            border: 1px solid #1e293b;
            selection-background-color: #1e293b;
        }

        /* ── TABLES ── */
        QTableView, QTableWidget {
            background-color: #0f1422;
            alternate-background-color: #0b0f19;
            gridline-color: transparent;
            border: 1px solid #1e293b;
            border-radius: 8px;
            color: #f8fafc;
        }
        QTableView::item, QTableWidget::item {
            padding: 6px 10px;
            border-bottom: 1px solid #151d2e;
        }
        QTableView::item:selected, QTableWidget::item:selected {
            background-color: #1e293b;
            color: #3b82f6;
        }
        QHeaderView::section {
            background-color: #0b0f19;
            color: #94a3b8;
            padding: 6px 10px;
            font-weight: 700;
            font-size: 11px;
            border: none;
            border-bottom: 1px solid #1e293b;
        }

        /* Scan Results Detail Panel */
        QFrame#scan_detail_panel {
            background-color: #111726;
            border: 1px solid #1e293b;
            border-radius: 10px;
        }
        QFrame#scan_stat_chip {
            background-color: #111726;
            border: 1px solid #1e293b;
            border-radius: 6px;
        }
        QPushButton#detail_action_btn {
            background-color: #0b0f19;
            border: 1px solid #1e293b;
            border-radius: 6px;
            color: #cbd5e1;
            font-size: 11px;
            text-align: left;
            padding: 4px 10px;
        }
        QPushButton#detail_action_btn:hover {
            background-color: #1e293b;
            border-color: #3b82f6;
            color: #f8fafc;
        }

        /* Tabs */
        QTabWidget::pane { border: none; background: transparent; }
        QTabBar::tab {
            background-color: transparent;
            color: #94a3b8;
            padding: 6px 14px;
            margin-right: 4px;
            border-bottom: 2px solid transparent;
            font-weight: 600;
        }
        QTabBar::tab:hover { color: #f8fafc; }
        QTabBar::tab:selected {
            color: #3b82f6;
            border-bottom: 2px solid #3b82f6;
        }

        /* Progress Bar */
        QProgressBar#main_progress {
            background-color: #1e293b;
            border: none;
            border-radius: 3px;
        }
        QProgressBar#main_progress::chunk {
            background-color: #3b82f6;
            border-radius: 3px;
        }

        QSlider::groove:horizontal { border: none; height: 4px; background: #1e293b; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #3b82f6; border-radius: 2px; }
        QSlider::handle:horizontal { background: #ffffff; border: 1px solid #3b82f6; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }

        QCheckBox { spacing: 8px; color: #cbd5e1; font-size: 13px; }
        QStatusBar { color: #64748b; background-color: #060911; border-top: 1px solid #131b2e; }
        QTextEdit#log_area { background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px; color: #f8fafc; }
        """
    else:
        return """
        * {
            font-family: 'Segoe UI', -apple-system, sans-serif;
            font-size: 13px;
            outline: none;
        }

        QMainWindow, QDialog {
            background-color: #f8fafc;
            color: #0f172a;
        }

        QWidget {
            color: #0f172a;
        }

        /* ── PAGE TYPOGRAPHY ── */
        QLabel#page_title {
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
        }
        QLabel#page_subtitle {
            font-size: 12px;
            color: #64748b;
        }
        QLabel#card_header, QLabel#stat_label {
            font-size: 9px;
            font-weight: 700;
            color: #64748b;
            letter-spacing: 1px;
        }
        QLabel#small_lbl {
            font-size: 11px;
            color: #64748b;
        }
        QLabel#chip_lbl {
            font-size: 11px;
            color: #64748b;
            font-weight: 500;
        }

        /* ── SIDEBAR ── */
        QFrame#sidebar {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        QLabel#app_title {
            color: #0f172a;
            font-weight: 700;
            font-size: 13px;
        }
        QFrame#sidebar_footer {
            border-top: 1px solid #e2e8f0;
            background-color: transparent;
        }

        /* Nav Buttons */
        QPushButton#nav_btn {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            margin: 3px 6px;
            text-align: left;
        }
        QPushButton#nav_btn:hover {
            background-color: #f1f5f9;
        }
        QPushButton#nav_btn:checked {
            background-color: #e2e8f0;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
        }
        QLabel#nav_lbl {
            color: #64748b;
            font-size: 13px;
            background: transparent;
        }
        QLabel#nav_shortcut {
            color: #94a3b8;
            font-size: 10px;
            background: transparent;
        }
        QLabel#nav_badge {
            background-color: #2563eb;
            color: #ffffff;
            border-radius: 7px;
            font-size: 9px;
            font-weight: bold;
            padding: 1px 6px;
            height: 14px;
        }
        QPushButton#nav_btn:hover QLabel#nav_lbl { color: #0f172a; }
        QPushButton#nav_btn:checked QLabel#nav_lbl { color: #0f172a; font-weight: 600; }
        QPushButton#nav_btn:checked QLabel#nav_shortcut { color: #2563eb; }

        /* ── TOP BAR ── */
        QFrame#topbar {
            background-color: #ffffff;
            border-bottom: 1px solid #e2e8f0;
        }
        QLabel#breadcrumb_lbl {
            color: #2563eb;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
        }
        QLineEdit#global_search_input {
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 10px;
            color: #0f172a;
        }
        QLineEdit#global_search_input:focus {
            border-color: #2563eb;
        }

        QPushButton#icon_btn, QPushButton#mini_btn {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            color: #0f172a;
            padding: 4px 12px;
        }
        QPushButton#icon_btn:hover, QPushButton#mini_btn:hover {
            background-color: #f1f5f9;
            border-color: #94a3b8;
        }

        /* ── PRIMARY BUTTONS ── */
        QPushButton#btn_scan, QPushButton#btn_sync {
            background-color: #2563eb;
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#btn_scan:hover, QPushButton#btn_sync:hover {
            background-color: #1d4ed8;
        }
        QPushButton#btn_scan:disabled, QPushButton#btn_sync:disabled {
            background-color: #e2e8f0;
            color: #94a3b8;
        }

        QPushButton#btn_sel {
            background-color: #0d9488;
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#btn_sel:hover { background-color: #0f766e; }
        QPushButton#btn_sel:disabled { background-color: #e2e8f0; color: #94a3b8; }

        QPushButton#btn_browse {
            background-color: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            color: #0f172a;
            padding: 0 14px;
            font-weight: 500;
        }
        QPushButton#btn_browse:hover {
            background-color: #e2e8f0;
        }

        QPushButton#filter_btn {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            color: #0f172a;
            text-align: left;
            padding: 4px 12px;
        }
        QPushButton#filter_btn:hover {
            border-color: #2563eb;
            background-color: #f8fafc;
        }
        QPushButton#filter_btn::menu-indicator {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            right: 8px;
        }
        QMenu#filter_menu {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 4px;
        }
        QFrame#filter_popup_frame {
            background-color: transparent;
        }

        QPushButton#btn_cancel {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            color: #64748b;
        }
        QPushButton#btn_cancel:hover {
            background-color: #f1f5f9;
            color: #0f172a;
        }

        QPushButton#btn_danger {
            background-color: #fee2e2;
            border: 1px solid #fca5a5;
            border-radius: 6px;
            color: #dc2626;
            font-weight: 600;
            padding: 4px 16px;
        }
        QPushButton#btn_danger:hover {
            background-color: #dc2626;
            color: #ffffff;
            border-color: #dc2626;
        }

        /* ── CARDS & PANELS ── */
        QFrame#stat_card, QFrame#folder_card, QFrame#dashboard_panel, QFrame#options_panel, QFrame#settings_pane {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        QFrame#preset_card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        QFrame#preset_card:hover {
            border-color: #cbd5e1;
            background-color: #f1f5f9;
        }
        QFrame#history_session_card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        QFrame#history_session_card:hover {
            border-color: #cbd5e1;
            background-color: #f8fafc;
        }
        QFrame#history_session_card[selected="true"] {
            border: 1px solid #2563eb;
            background-color: #f8fafc;
        }
        QFrame#folder_stats_frame {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }

        /* ── INPUTS & COMBOS ── */
        QLineEdit#path_input, QLineEdit#search_input, QLineEdit {
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 12px;
            color: #0f172a;
        }
        QLineEdit:focus {
            border-color: #2563eb;
        }

        QComboBox {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 10px;
            color: #0f172a;
        }
        QComboBox:focus { border-color: #2563eb; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
            selection-background-color: #f1f5f9;
        }

        /* ── TABLES ── */
        QTableView, QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f8fafc;
            gridline-color: transparent;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            color: #0f172a;
        }
        QTableView::item, QTableWidget::item {
            padding: 6px 10px;
            border-bottom: 1px solid #f1f5f9;
        }
        QTableView::item:selected, QTableWidget::item:selected {
            background-color: #f1f5f9;
            color: #2563eb;
        }
        QHeaderView::section {
            background-color: #f8fafc;
            color: #64748b;
            padding: 6px 10px;
            font-weight: 700;
            font-size: 11px;
            border: none;
            border-bottom: 1px solid #e2e8f0;
        }

        /* Scan Results Detail Panel */
        QFrame#scan_detail_panel {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        QFrame#scan_stat_chip {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }
        QPushButton#detail_action_btn {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            color: #475569;
            font-size: 11px;
            text-align: left;
            padding: 4px 10px;
        }
        QPushButton#detail_action_btn:hover {
            background-color: #f1f5f9;
            border-color: #2563eb;
            color: #0f172a;
        }

        /* Tabs */
        QTabWidget::pane { border: none; background: transparent; }
        QTabBar::tab {
            background-color: transparent;
            color: #64748b;
            padding: 6px 14px;
            margin-right: 4px;
            border-bottom: 2px solid transparent;
            font-weight: 600;
        }
        QTabBar::tab:hover { color: #0f172a; }
        QTabBar::tab:selected {
            color: #2563eb;
            border-bottom: 2px solid #2563eb;
        }

        /* Progress Bar */
        QProgressBar#main_progress {
            background-color: #e2e8f0;
            border: none;
            border-radius: 3px;
        }
        QProgressBar#main_progress::chunk {
            background-color: #2563eb;
            border-radius: 3px;
        }

        QSlider::groove:horizontal { border: none; height: 4px; background: #e2e8f0; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #2563eb; border-radius: 2px; }
        QSlider::handle:horizontal { background: #ffffff; border: 1px solid #2563eb; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        QCheckBox {
            spacing: 8px;
            color: #334155;
            font-size: 13px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1.5px solid #cbd5e1;
            background-color: #ffffff;
        }
        QCheckBox::indicator:hover {
            border-color: #2563eb;
            background-color: #f8fafc;
        }
        QCheckBox::indicator:checked {
            background-color: #2563eb;
            border-color: #2563eb;
        }
        QStatusBar { color: #94a3b8; background-color: #ffffff; border-top: 1px solid #e2e8f0; }
        QTextEdit#log_area { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; color: #0f172a; }
        """
