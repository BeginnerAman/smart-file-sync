from __future__ import annotations
import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject
from .platform_win import ensure_extended_path
from typing import Generator

def fast_scandir(dir_path: str, exclusions: list[str] | None = None, allowed_exts: set[str] | list[str] | None = None) -> Generator[tuple[str, str, os.stat_result], None, None]:
    """
    Fast recursive directory scanner using os.scandir.
    Yields (relative_path, full_path, stat_result) tuples.
    """
    if exclusions is None:
        exclusions = []
    excl_set = set(e.lower() for e in exclusions)
    allow_set = set(a.lower() for a in allowed_exts) if allowed_exts else None
    
    base_ext = ensure_extended_path(dir_path)
    base_len = len(base_ext)
    
    def _scan(current_dir):
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        name_lower = entry.name.lower()
                        # Fast exclusion checks
                        if name_lower in excl_set or any(name_lower.endswith(e) for e in excl_set):
                            continue
                            
                        if entry.is_dir(follow_symlinks=False):
                            yield from _scan(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if allow_set:
                                ext = Path(name_lower).suffix
                                if ext not in allow_set:
                                    continue
                            # Derive relative path cleanly
                            rel = entry.path[base_len:].lstrip('\\/')
                            try:
                                st = entry.stat()
                                yield (rel, entry.path, st)
                            except OSError:
                                pass
                    except OSError:
                        continue
        except (PermissionError, OSError):
            pass

    yield from _scan(base_ext)

def fast_folder_stats(dir_path: str, exclusions: list[str] | None = None, allowed_exts: set[str] | list[str] | None = None) -> tuple[int, int, float]:
    """Return (total_files, total_bytes, latest_mtime) for a directory path"""
    total_files = 0
    total_bytes = 0
    latest_mtime = 0
    
    for _, _, st in fast_scandir(dir_path, exclusions, allowed_exts):
        total_files += 1
        total_bytes += st.st_size
        if st.st_mtime > latest_mtime:
            latest_mtime = st.st_mtime
            
    return total_files, total_bytes, latest_mtime

class MetadataScanner(QThread):
    """Background thread to calculate directory statistics without blocking GUI"""
    finished_signal = Signal(str, int, int, float) # (key, file_count, size_bytes, latest_mtime)

    def __init__(self, key: str, path: str, exclusions: list[str] | None = None, allowed_exts: set[str] | list[str] | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.path = path
        self.exclusions = exclusions or []
        self.allowed_exts = allowed_exts or []
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        self._stop = False
        if not self.path or not os.path.isdir(self.path):
            self.finished_signal.emit(self.key, 0, 0, 0)
            return

        total_files = 0
        total_bytes = 0
        latest_mtime = 0
        for _, _, st in fast_scandir(self.path, self.exclusions, self.allowed_exts):
            if self._stop:
                return
            total_files += 1
            total_bytes += st.st_size
            if st.st_mtime > latest_mtime:
                latest_mtime = st.st_mtime

        if not self._stop:
            self.finished_signal.emit(self.key, total_files, total_bytes, latest_mtime)


class DiffScanWorker(QThread):
    """Background thread for full source/destination diff scan with live progress."""
    progress = Signal(str, int)       # (phase_label, files_scanned_so_far)
    finished = Signal(dict, dict, list, int, int, int)  # (src_map, dst_map, missing_list, total, missing_ct, modified_ct)
    error = Signal(str)

    def __init__(self, src: str, dst: str, exclusions: list[str], allowed_exts: set[str] | None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.src = src
        self.dst = dst
        self.exclusions = exclusions
        self.allowed_exts = allowed_exts
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            self._stop = False
            allowed = self.allowed_exts

            # Phase 1: Scan source
            src_map = {}
            count = 0
            for rel, full, st in fast_scandir(self.src, self.exclusions):
                if self._stop:
                    return
                ext = Path(rel).suffix.lower()
                if allowed and ext not in allowed:
                    continue
                src_map[rel] = {"full": full, "size": st.st_size, "mtime": st.st_mtime}
                count += 1
                if count % 500 == 0:
                    self.progress.emit("Scanning source...", count)
            self.progress.emit("Source scan complete", count)

            # Phase 2: Scan destination
            dst_map = {}
            count = 0
            for rel, full, st in fast_scandir(self.dst, self.exclusions):
                if self._stop:
                    return
                ext = Path(rel).suffix.lower()
                if allowed and ext not in allowed:
                    continue
                dst_map[rel] = {"full": full, "size": st.st_size, "mtime": st.st_mtime}
                count += 1
                if count % 500 == 0:
                    self.progress.emit("Scanning destination...", count)
            self.progress.emit("Destination scan complete", count)

            # Phase 3: Compute differences (bidirectional)
            self.progress.emit("Computing differences...", 0)
            from datetime import datetime
            from ..utils.formatters import fmt_size

            diff_list = []
            total_scan_count = len(src_map)
            missing_count = 0
            modified_count = 0
            dest_only_count = 0

            for rel, s_data in src_map.items():
                if self._stop:
                    return
                s_full = s_data["full"]
                s_size = s_data["size"]
                s_mtime = s_data["mtime"]
                d_full = os.path.join(self.dst, rel)

                if rel not in dst_map:
                    missing_count += 1
                    diff_list.append({
                        "filename": Path(rel).name,
                        "rel_path": rel,
                        "src_path": s_full,
                        "dest_path": d_full,
                        "size_bytes": s_size,
                        "size_str": fmt_size(s_size),
                        "modified_str": datetime.fromtimestamp(s_mtime).strftime("%Y-%m-%d %H:%M"),
                        "reason": "Missing",
                        "direction": "source_to_dest"
                    })
                else:
                    d_data = dst_map[rel]
                    if s_size != d_data["size"] or abs(s_mtime - d_data["mtime"]) > 1.0:
                        modified_count += 1
                        if s_mtime > d_data["mtime"]:
                            reason = "Source Newer"
                            direction = "source_to_dest"
                        elif d_data["mtime"] > s_mtime:
                            reason = "Destination Newer"
                            direction = "dest_to_source"
                        else:
                            reason = "Size Differs"
                            direction = "source_to_dest"
                        diff_list.append({
                            "filename": Path(rel).name,
                            "rel_path": rel,
                            "src_path": s_full,
                            "dest_path": d_full,
                            "size_bytes": s_size,
                            "size_str": fmt_size(s_size),
                            "modified_str": datetime.fromtimestamp(s_mtime).strftime("%Y-%m-%d %H:%M"),
                            "reason": reason,
                            "direction": direction
                        })

            # Detect files only in destination (not in source)
            for rel, d_data in dst_map.items():
                if self._stop:
                    return
                if rel not in src_map:
                    dest_only_count += 1
                    diff_list.append({
                        "filename": Path(rel).name,
                        "rel_path": rel,
                        "src_path": os.path.join(self.src, rel),
                        "dest_path": d_data["full"],
                        "size_bytes": d_data["size"],
                        "size_str": fmt_size(d_data["size"]),
                        "modified_str": datetime.fromtimestamp(d_data["mtime"]).strftime("%Y-%m-%d %H:%M"),
                        "reason": "Destination Only",
                        "direction": "dest_only"
                    })

            self.finished.emit(src_map, dst_map, diff_list, total_scan_count, missing_count, modified_count)

        except Exception as e:
            self.error.emit(str(e))

