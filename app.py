#!/usr/bin/env python3
"""
Smart File Sync v3.0 -- Professional High-Speed File Synchronization Suite
Clean modular entry point.
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure package is resolvable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smart_sync.ui.main_window import SmartSyncApp
from smart_sync.utils.constants import APP_NAME, APP_VERSION

def main():
    # Set Windows High-DPI attributes
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    window = SmartSyncApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
