from __future__ import annotations
import os
import time
import shutil
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal, QObject

from ..utils.constants import MD5_CHUNK_SIZE, LOG_FILE
from ..utils import formatters as _formatters
from ..core import platform_win as _pw
from ..core import hasher as _hasher
from ..core import delta as _delta

class WorkerSignals(QObject):
    file_progress = Signal(int, str, str, str, str) # idx, rel_path, size_str, status, detail
    overall_progress = Signal(int, int, str, float, float, float) # done, total, status_text, speed, avg_speed, eta
    log_message = Signal(str, str) # text, kind ("info", "warning", "error", "success")
    finished = Signal(dict) # summary stats
    consecutive_fail_limit = Signal() # triggered on repeated error bursts

class SyncWorker(QThread):
    """
    High-Performance, Thread-Safe File Synchronization Engine.
    Supports Atomic File Writes, MD5 Verification, Throughput Tracking, and Safe Recovery.
    """
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.signals = WorkerSignals()
        self.files_to_sync = []
        self.threads = 4
        self.dry_run = False
        self.use_safe_renames = True
        self.use_md5_verify = False
        self.retry_count = 2
        self.source_dir = ""
        self.dest_dir = ""
        self.filter_applied = "All Files"
        self.excl_applied = []
        self.mirror_mode = False
        self.throttle_mbps = 0
        
        self._stop_requested = False
        self._pause_event = threading.Event()
        self._pause_event.set() # Unpaused by default
        
        self._lock = threading.Lock()
        self._consecutive_errors = 0
        self.version_count = 0
        self.use_delta_transfer = True  # Block-level delta: only copy changed blocks


    def request_stop(self) -> None:
        self._stop_requested = True
        self._pause_event.set() # Release if paused

    def request_pause(self, paused: bool) -> None:
        if paused:
            self._pause_event.clear()
        else:
            self._pause_event.set()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def run(self) -> None:
        self._stop_requested = False
        self._pause_event.set()
        with self._lock:
            self._consecutive_errors = 0
        
        total_files = len(self.files_to_sync)
        if total_files == 0:
            self.signals.finished.emit({
                "copied": 0, "errors": 0, "duration": "0.0s",
                "copied_size": "0 B", "status": "No Files to Sync"
            })
            return

        total_bytes = sum(f.get("size_bytes", 0) for f in self.files_to_sync)
        copied_bytes = 0
        copied_count = 0
        error_count = 0
        
        start_time = time.time()
        last_metric_time = start_time
        last_metric_bytes = 0
        current_speed = 0.0

        self.signals.log_message.emit(f"Starting synchronization of {total_files} files ({_formatters.fmt_size(total_bytes)})...", "info")

        # Bind module-level names for Python 3.13 closure compatibility
        _ensure = _pw.ensure_extended_path
        _chmod = _pw.safe_chmod_write
        _streaming = _hasher.calc_streaming_hash
        _md5 = _hasher.calc_file_md5
        _should_delta = _delta.should_use_delta
        _delta_sync = _delta.delta_sync_file
        _fmt = _formatters.fmt_size

        def _sync_single(idx, item):
            if self._stop_requested:
                return "stopped", 0, "Stopped by user"
                
            self._pause_event.wait()
            
            src = item["src_path"]
            dst = item["dest_path"]
            rel = item["rel_path"]
            size_b = item.get("size_bytes", 0)
            size_str = item.get("size_str", _fmt(size_b))
            
            # Emit in-progress status
            self.signals.file_progress.emit(idx, rel, size_str, "In Progress", "Copying...")
            
            if self.dry_run:
                time.sleep(0.01)
                self.signals.file_progress.emit(idx, rel, size_str, "Completed", "Dry run preview")
                return "copied", size_b, ""
                
            max_retries = self.retry_count
            for attempt in range(max_retries + 1):
                try:
                    if not os.path.exists(_ensure(src)):
                        msg = "Source file is missing or inaccessible"
                        self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                        return "error", 0, msg
                        
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    _chmod(dst)
                    
                    # Block-level delta transfer: only copy changed blocks
                    if self.use_delta_transfer and _should_delta(src, dst):
                        self.signals.file_progress.emit(idx, rel, size_str, "In Progress", "Delta sync...")
                        ok, delta_bytes, total_blocks = _delta_sync(
                            src, dst,
                            stop_flag=lambda: self._stop_requested,
                            pause_event=self._pause_event,
                            throttle_mbps=self.throttle_mbps
                        )
                        if ok:
                            saved = size_b - delta_bytes
                            pct = int((1 - delta_bytes / max(1, size_b)) * 100)
                            detail = f"Delta: {_fmt(delta_bytes)} transferred ({pct}% saved)"
                            self.signals.file_progress.emit(idx, rel, size_str, "Completed", detail)
                            self.signals.log_message.emit(
                                f"Delta sync: {rel} - {_fmt(delta_bytes)}/{size_str} ({pct}% saved)", "success"
                            )
                            return "copied", delta_bytes, ""
                    
                    # Full copy path (for new files or when delta not applicable)
                    tmp_dst = f"{dst}.smartsync.{os.getpid()}_{int(time.time()*1000)}.tmp" if self.use_safe_renames else dst
                    
                    with open(_ensure(src), 'rb') as f_in, open(_ensure(tmp_dst), 'wb') as f_out:
                        src_hash = _streaming(
                            f_in, f_out,
                            compute_hash=self.use_md5_verify,
                            stop_flag_callable=lambda: self._stop_requested,
                            pause_event=self._pause_event,
                            throttle_mbps=self.throttle_mbps
                        )
                        
                    # Preserve file timestamps
                    try:
                        shutil.copystat(_ensure(src), _ensure(tmp_dst))
                    except Exception:
                        pass
                        
                    if self.use_md5_verify:
                        dst_hash = _md5(tmp_dst)
                        if not dst_hash or src_hash != dst_hash:
                            if os.path.exists(_ensure(tmp_dst)):
                                os.remove(_ensure(tmp_dst))
                            msg = "Integrity check failed: MD5 hashes do not match"
                            self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                            return "error", 0, msg
                            
                    if self.use_safe_renames:
                        _chmod(dst)
                        
                        # File versioning
                        if self.version_count > 0 and os.path.exists(_ensure(dst)):
                            ver_dir = os.path.join(os.path.dirname(dst), '.smartsync_versions')
                            os.makedirs(ver_dir, exist_ok=True)
                            basename = os.path.basename(dst)
                            existing = sorted([f for f in os.listdir(ver_dir) if f.startswith(basename + '.v')])
                            ver_num = len(existing) + 1
                            ver_path = os.path.join(ver_dir, f'{basename}.v{ver_num}')
                            try:
                                shutil.copy2(_ensure(dst), _ensure(ver_path))
                                if len(existing) >= self.version_count:
                                    for old_ver in existing[:len(existing) - self.version_count + 1]:
                                        try:
                                            os.remove(os.path.join(ver_dir, old_ver))
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        
                        os.replace(_ensure(tmp_dst), _ensure(dst))
                        
                    self.signals.file_progress.emit(idx, rel, size_str, "Completed", "Synced successfully")
                    return "copied", size_b, ""
                    
                except InterruptedError:
                    if self.use_safe_renames and 'tmp_dst' in locals() and os.path.exists(_ensure(tmp_dst)):
                        try: os.remove(_ensure(tmp_dst))
                        except: pass
                    self.signals.file_progress.emit(idx, rel, size_str, "Stopped", "User stopped sync")
                    return "stopped", 0, "Sync stopped by user"
                    
                except PermissionError:
                    msg = f"Permission denied for '{rel}'. Check write permissions."
                    self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                    return "error", 0, msg
                    
                except OSError as e:
                    import errno
                    if e.errno == errno.ENOSPC or 'No space left' in str(e) or 'disk full' in str(e).lower():
                        msg = f"Disk full: Cannot write '{rel}'. Free up space on destination drive."
                        self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                        self._stop_requested = True
                        return "error", 0, msg
                    if self.use_safe_renames and 'tmp_dst' in locals():
                        try:
                            if os.path.exists(_ensure(tmp_dst)):
                                os.remove(_ensure(tmp_dst))
                        except Exception:
                            pass
                    msg = str(e)
                    self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                    return "error", 0, msg

                except Exception as e:
                    if self.use_safe_renames and 'tmp_dst' in locals() and os.path.exists(_ensure(tmp_dst)):
                        try: os.remove(_ensure(tmp_dst))
                        except: pass

                    if attempt < max_retries:
                        time.sleep(0.5 * (2 ** attempt))
                        self.signals.file_progress.emit(idx, rel, size_str, "In Progress", f"Retry {attempt + 1}/{max_retries}...")
                        continue
                    
                    if self.use_safe_renames and 'tmp_dst' in locals():
                        try:
                            if os.path.exists(_ensure(tmp_dst)):
                                os.remove(_ensure(tmp_dst))
                        except Exception:
                            pass

                    msg = str(e)
                    self.signals.file_progress.emit(idx, rel, size_str, "Error", msg)
                    return "error", 0, msg

        # Pre-sync disk space check
        try:
            import shutil as _shutil
            dest_usage = _shutil.disk_usage(self.dest_dir)
            free_bytes = dest_usage.free
            if total_bytes > free_bytes * 0.95:  # Leave 5% headroom
                self.signals.log_message.emit(
                    f"Warning: Destination disk may not have enough space. "
                    f"Need {_fmt(total_bytes)}, available {_fmt(free_bytes)}",
                    "warning"
                )
        except Exception:
            pass  # Non-critical, continue anyway

        # Execute transfers with thread pool
        with ThreadPoolExecutor(max_workers=max(1, self.threads)) as executor:
            futures = {
                executor.submit(_sync_single, idx, item): (idx, item)
                for idx, item in enumerate(self.files_to_sync)
            }
            
            for future in as_completed(futures):
                if self._stop_requested:
                    break
                    
                idx, item = futures[future]
                try:
                    status, bytes_done, err_msg = future.result()
                except Exception as e:
                    status, bytes_done, err_msg = "error", 0, str(e)
                    
                with self._lock:
                    if status == "copied":
                        copied_count += 1
                        copied_bytes += bytes_done
                        self._consecutive_errors = 0
                    elif status == "error":
                        error_count += 1
                        self._consecutive_errors += 1
                        if self._consecutive_errors >= 5:
                            self._stop_requested = True
                            self.signals.consecutive_fail_limit.emit()
                            
                    # Calculate live performance metrics
                    now = time.time()
                    elapsed = now - start_time
                    time_delta = now - last_metric_time
                    if time_delta >= 0.5:
                        current_speed = (copied_bytes - last_metric_bytes) / time_delta
                        last_metric_time = now
                        last_metric_bytes = copied_bytes
                        
                    avg_speed = copied_bytes / elapsed if elapsed > 0 else 0.0
                    remaining_bytes = max(0, total_bytes - copied_bytes)
                    eta = remaining_bytes / avg_speed if avg_speed > 0 else 0.0
                    
                    done_total = copied_count + error_count
                    status_text = f"Synced {copied_count}/{total_files} files ({_fmt(copied_bytes)})"
                    self.signals.overall_progress.emit(
                        done_total, total_files, status_text, current_speed, avg_speed, eta
                    )

        duration = time.time() - start_time
        summary_status = "Interrupted" if self._stop_requested else ("Success" if error_count == 0 else "Completed with Errors")
        
        summary = {
            "source": self.source_dir,
            "destination": self.dest_dir,
            "filter": self.filter_applied,
            "excl": str(self.excl_applied),
            "copied": copied_count,
            "errors": error_count,
            "total_files": total_files,
            "copied_size": _fmt(copied_bytes),
            "copied_bytes": copied_bytes,
            "duration": f"{duration:.1f}s",
            "status": summary_status
        }
        
        # Mirror Mode: Delete orphaned files from destination
        if getattr(self, 'mirror_mode', False) and not self.dry_run and not self._stop_requested:
            self.signals.log_message.emit('Mirror mode: Scanning for orphaned files...', 'info')
            from .scanner import fast_scandir
            orphan_count = 0
            for rel, full, st in fast_scandir(self.dest_dir, []):
                if self._stop_requested:
                    break
                src_equivalent = os.path.join(self.source_dir, rel)
                if not os.path.exists(_pw.ensure_extended_path(src_equivalent)):
                    try:
                        _pw.safe_chmod_write(full)
                        os.remove(_pw.ensure_extended_path(full))
                        orphan_count += 1
                        self.signals.log_message.emit(f'Mirror: Deleted orphan: {rel}', 'warning')
                    except Exception as e:
                        self.signals.log_message.emit(f'Mirror: Failed to delete {rel}: {e}', 'error')
            if orphan_count > 0:
                self.signals.log_message.emit(f'Mirror mode: Removed {orphan_count} orphaned files.', 'success')

        self.signals.finished.emit(summary)
