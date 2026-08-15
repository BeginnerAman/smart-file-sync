"""Core synchronization and scanning package"""
from .platform_win import ensure_extended_path, safe_chmod_write, set_windows_startup
from .hasher import calc_file_md5, calc_streaming_hash
from .scanner import fast_scandir, fast_folder_stats, MetadataScanner
from .engine import SyncWorker, WorkerSignals
