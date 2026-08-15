import os
import json
import time
from ..utils.constants import APPDATA_DIR

CACHE_PATH = os.path.join(APPDATA_DIR, 'scan_cache.json')

class ScanCache:
    """Persistent file metadata cache for incremental scanning.
    Stores {rel_path: {size, mtime}} per directory.
    On re-scan, only files whose mtime differs need re-stat.
    """
    
    def __init__(self):
        self._cache = {}  # {dir_path: {rel_path: {size, mtime}}}
        self._load()
    
    def _load(self):
        try:
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}
    
    def save(self):
        try:
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f)
        except Exception:
            pass
    
    def get_cached(self, dir_path: str) -> dict:
        """Get cached file metadata for a directory"""
        key = os.path.abspath(dir_path).lower()
        return self._cache.get(key, {})
    
    def update_cache(self, dir_path: str, file_map: dict):
        """Update cache with fresh scan results.
        file_map: {rel_path: {size, mtime, full}}
        """
        key = os.path.abspath(dir_path).lower()
        cache_entry = {}
        for rel, data in file_map.items():
            cache_entry[rel] = {
                'size': data['size'],
                'mtime': data['mtime']
            }
        self._cache[key] = cache_entry
        self.save()
    
    def is_file_changed(self, dir_path: str, rel_path: str, current_size: int, current_mtime: float) -> bool:
        """Check if a file has changed since last cache."""
        cached = self.get_cached(dir_path)
        if rel_path not in cached:
            return True  # New file
        entry = cached[rel_path]
        return entry['size'] != current_size or abs(entry['mtime'] - current_mtime) > 0.5
    
    def clear(self):
        self._cache = {}
        self.save()

# Global singleton
_global_cache = None

def get_scan_cache() -> ScanCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = ScanCache()
    return _global_cache
