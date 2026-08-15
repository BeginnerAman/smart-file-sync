import os
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

class FileChangeEvent:
    def __init__(self, event_type: str, rel_path: str, full_path: str):
        self.event_type = event_type  # 'created', 'modified', 'deleted', 'moved'
        self.rel_path = rel_path
        self.full_path = full_path
        self.timestamp = time.time()

class SyncEventHandler(FileSystemEventHandler):
    """Watchdog handler that converts filesystem events to Qt signals"""
    def __init__(self, base_dir: str, callback):
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        self.callback = callback
        self._debounce = {}  # path -> timestamp
    
    def _handle(self, event, event_type):
        if event.is_directory:
            return
        full_path = os.path.abspath(event.src_path)
        # Debounce: ignore duplicate events within 500ms
        now = time.time()
        last = self._debounce.get(full_path, 0)
        if now - last < 0.5:
            return
        self._debounce[full_path] = now
        # Clean old entries
        if len(self._debounce) > 10000:
            cutoff = now - 5.0
            self._debounce = {k: v for k, v in self._debounce.items() if v > cutoff}
        
        rel_path = os.path.relpath(full_path, self.base_dir)
        self.callback(FileChangeEvent(event_type, rel_path, full_path))
    
    def on_created(self, event): self._handle(event, 'created')
    def on_modified(self, event): self._handle(event, 'modified')
    def on_deleted(self, event): self._handle(event, 'deleted')
    def on_moved(self, event): self._handle(event, 'moved')


class DirectoryWatcher(QThread):
    """Background thread that monitors a directory for file changes using watchdog."""
    file_changed = Signal(str, str, str)  # (event_type, rel_path, full_path)
    error = Signal(str)
    started_watching = Signal(str)  # dir_path
    stopped_watching = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.watch_path = ""
        self._stop_requested = False
        self._observer = None
        self._change_count = 0
    
    @property
    def change_count(self):
        return self._change_count
    
    def set_path(self, path: str):
        self.watch_path = path
    
    def request_stop(self):
        self._stop_requested = True
        if self._observer:
            self._observer.stop()
    
    def _on_event(self, event: FileChangeEvent):
        self._change_count += 1
        self.file_changed.emit(event.event_type, event.rel_path, event.full_path)
    
    def run(self):
        if not HAS_WATCHDOG:
            self.error.emit('watchdog library not installed. Run: pip install watchdog')
            return
        
        if not self.watch_path or not os.path.isdir(self.watch_path):
            self.error.emit(f'Invalid watch path: {self.watch_path}')
            return
        
        self._stop_requested = False
        self._change_count = 0
        
        try:
            handler = SyncEventHandler(self.watch_path, self._on_event)
            self._observer = Observer()
            self._observer.schedule(handler, self.watch_path, recursive=True)
            self._observer.start()
            self.started_watching.emit(self.watch_path)
            
            while not self._stop_requested:
                time.sleep(0.5)
            
            self._observer.stop()
            self._observer.join(timeout=3)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.stopped_watching.emit()
