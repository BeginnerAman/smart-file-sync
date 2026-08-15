from __future__ import annotations
import os
import time
import hashlib
from typing import Callable, Any, TextIO, BinaryIO
from ..utils.constants import MD5_CHUNK_SIZE
from .platform_win import ensure_extended_path

def calc_file_md5(filepath: str) -> str:
    """Calculate MD5 hash using 1MB streaming buffer"""
    hasher = hashlib.md5()
    try:
        with open(ensure_extended_path(filepath), 'rb') as f:
            for chunk in iter(lambda: f.read(MD5_CHUNK_SIZE), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def calc_streaming_hash(src_file: BinaryIO, dst_file: BinaryIO, compute_hash: bool = False, stop_flag_callable: Callable[[], bool] | None = None, pause_event: Any | None = None, throttle_mbps: int | float = 0) -> str | None:
    """Copy data stream and calculate MD5 digest simultaneously without double disk reads"""
    hasher = hashlib.md5() if compute_hash else None
    bytes_per_sec = throttle_mbps * 1024 * 1024 if throttle_mbps > 0 else 0
    
    while True:
        if stop_flag_callable and stop_flag_callable():
            raise InterruptedError("Sync stopped by user")
        if pause_event:
            pause_event.wait()
            
        chunk_start = time.time()
        buf = src_file.read(MD5_CHUNK_SIZE)
        if not buf:
            break
        dst_file.write(buf)
        if compute_hash and hasher:
            hasher.update(buf)
            
        if bytes_per_sec > 0:
            expected_time = len(buf) / bytes_per_sec
            elapsed = time.time() - chunk_start
            if elapsed < expected_time:
                time.sleep(expected_time - elapsed)
                
    return hasher.hexdigest() if compute_hash and hasher else None
