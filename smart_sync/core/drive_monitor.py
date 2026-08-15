import os
import sys
import time
import string
from PySide6.QtCore import QThread, Signal, QTimer


class DriveMonitor(QThread):
    """Background thread that monitors for USB/removable drive plug/unplug events on Windows."""
    drive_connected = Signal(str, str)    # (drive_letter, volume_label)
    drive_disconnected = Signal(str)       # drive_letter
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = False
        self._known_drives = set()
        self._poll_interval = 2.0  # seconds
    
    def request_stop(self):
        self._stop_requested = True
    
    def _get_removable_drives(self) -> dict:
        """Get currently connected removable/USB drives with their labels."""
        drives = {}
        if sys.platform != 'win32':
            return drives
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    letter = chr(65 + i)
                    drive_path = f"{letter}:\\"
                    # Check drive type: 2 = REMOVABLE, 3 = FIXED, etc.
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
                    if drive_type == 2:  # DRIVE_REMOVABLE
                        # Get volume label
                        vol_buf = ctypes.create_unicode_buffer(261)
                        fs_buf = ctypes.create_unicode_buffer(261)
                        try:
                            ctypes.windll.kernel32.GetVolumeInformationW(
                                drive_path, vol_buf, 261, None, None, None, fs_buf, 261
                            )
                            label = vol_buf.value or f"USB Drive ({letter}:)"
                        except Exception:
                            label = f"USB Drive ({letter}:)"
                        drives[letter] = label
        except Exception:
            pass
        return drives
    
    def run(self):
        self._stop_requested = False
        self._known_drives = set(self._get_removable_drives().keys())
        
        while not self._stop_requested:
            time.sleep(self._poll_interval)
            if self._stop_requested:
                break
            
            current = self._get_removable_drives()
            current_set = set(current.keys())
            
            # Detect new drives
            for letter in current_set - self._known_drives:
                self.drive_connected.emit(f"{letter}:\\", current[letter])
            
            # Detect removed drives
            for letter in self._known_drives - current_set:
                self.drive_disconnected.emit(f"{letter}:\\")
            
            self._known_drives = current_set


def get_removable_drives() -> list:
    """Get list of currently connected removable drives as [(path, label), ...]"""
    monitor = DriveMonitor()
    drives = monitor._get_removable_drives()
    return [(f"{letter}:\\", label) for letter, label in sorted(drives.items())]
