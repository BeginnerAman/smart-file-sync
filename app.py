#!/usr/bin/env python3
"""
Smart File Sync v4.2.0 -- Professional High-Speed File Synchronization Suite
Clean modular entry point supporting both GUI and Headless CLI modes.
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
    # If launched with CLI arguments, run headless CLI directly
    cli_flags = ('--src', '--dst', '--mode', '--dry-run', '--verify', '--throttle', '--filter', '--exclude', '--help', '-h', '--version', '-v')
    if len(sys.argv) > 1 and any(arg in sys.argv for arg in cli_flags):
        import ctypes
        try:
            # Attach to calling Windows console so print output is visible
            ctypes.windll.kernel32.AttachConsole(-1)
        except Exception:
            pass
        from smart_sync.cli import main as cli_main
        cli_main()
        return

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
