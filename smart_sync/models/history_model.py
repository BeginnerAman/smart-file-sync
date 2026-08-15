from __future__ import annotations
import os
import json
import csv
from datetime import datetime
from ..utils.constants import HISTORY_FILE

class HistoryManager:
    """Manager for persisting, loading, exporting, and purging sync audit records"""
    
    @staticmethod
    def load_history() -> list[dict]:
        """Load history sessions array from JSON store"""
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def save_session(session_data: dict) -> bool:
        """Append new sync session record to top of history list"""
        history = HistoryManager.load_history()
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **session_data
        }
        history.insert(0, record)
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history[:100], f, indent=2) # Keep last 100 sessions
            return True
        except Exception:
            return False

    @staticmethod
    def clear_history() -> bool:
        """Purge all history sessions safely"""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def export_csv(filepath: str) -> bool:
        """Export history records to CSV file"""
        history = HistoryManager.load_history()
        if not history:
            return False
        try:
            keys = ["timestamp", "status", "source", "destination", "copied", "copied_size", "errors", "duration", "filter"]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                for row in history:
                    writer.writerow(row)
            return True
        except Exception:
            return False
