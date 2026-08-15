"""Block-Level Delta Transfer for Smart File Sync.

Instead of copying entire files, this module compares source and destination
at the block level (4KB chunks) and only transfers the changed blocks.

For a 500MB file with 1 line changed: transfers ~4KB instead of 500MB.
"""
from __future__ import annotations
import os
import hashlib
import shutil
import time
from typing import Callable, Any

from .platform_win import ensure_extended_path

# Block size for delta comparison (4KB = sweet spot for USB drives)
DELTA_BLOCK_SIZE = 4096

# Minimum file size to use delta transfer (below this, full copy is faster)
DELTA_MIN_FILE_SIZE = 1 * 1024 * 1024  # 1MB


def compute_block_signatures(filepath: str, block_size: int = DELTA_BLOCK_SIZE) -> list[bytes]:
    """Compute MD5 hash for each block of a file.
    
    Returns list of 16-byte MD5 digests, one per block.
    """
    signatures = []
    try:
        with open(ensure_extended_path(filepath), 'rb') as f:
            while True:
                block = f.read(block_size)
                if not block:
                    break
                signatures.append(hashlib.md5(block).digest())
    except Exception:
        return []
    return signatures


def delta_sync_file(
    src_path: str,
    dst_path: str,
    block_size: int = DELTA_BLOCK_SIZE,
    stop_flag: Callable[[], bool] | None = None,
    pause_event: Any | None = None,
    throttle_mbps: float = 0,
) -> tuple[bool, int, int]:
    """Perform block-level delta transfer from src to dst.
    
    Only overwrites blocks in dst that differ from src.
    
    Args:
        src_path: Source file path
        dst_path: Destination file path (must already exist)
        block_size: Size of each comparison block
        stop_flag: Callable that returns True to stop
        pause_event: Threading event for pause support
        throttle_mbps: Bandwidth limit in MB/s
    
    Returns:
        (success, bytes_transferred, total_blocks)
        - success: True if delta sync completed
        - bytes_transferred: Actual bytes written (only changed blocks)
        - total_blocks: Total number of blocks in source
    """
    src_ext = ensure_extended_path(src_path)
    dst_ext = ensure_extended_path(dst_path)
    
    if not os.path.exists(src_ext) or not os.path.exists(dst_ext):
        return False, 0, 0
    
    src_size = os.path.getsize(src_ext)
    dst_size = os.path.getsize(dst_ext)
    
    bytes_per_sec = throttle_mbps * 1024 * 1024 if throttle_mbps > 0 else 0
    bytes_transferred = 0
    blocks_changed = 0
    total_blocks = 0
    
    try:
        with open(src_ext, 'rb') as f_src, open(dst_ext, 'r+b') as f_dst:
            offset = 0
            while True:
                if stop_flag and stop_flag():
                    return False, bytes_transferred, total_blocks
                if pause_event:
                    pause_event.wait()
                
                chunk_start = time.time()
                
                src_block = f_src.read(block_size)
                if not src_block:
                    break
                
                total_blocks += 1
                
                # Read corresponding destination block
                f_dst.seek(offset)
                dst_block = f_dst.read(block_size)
                
                # Compare blocks using hash (faster than byte-by-byte for large blocks)
                if hashlib.md5(src_block).digest() != hashlib.md5(dst_block).digest():
                    # Block differs — write source block to destination
                    f_dst.seek(offset)
                    f_dst.write(src_block)
                    bytes_transferred += len(src_block)
                    blocks_changed += 1
                
                offset += len(src_block)
                
                # Throttle if needed
                if bytes_per_sec > 0 and bytes_transferred > 0:
                    expected_time = len(src_block) / bytes_per_sec
                    elapsed = time.time() - chunk_start
                    if elapsed < expected_time:
                        time.sleep(expected_time - elapsed)
            
            # If source is shorter than dest, truncate dest
            if src_size < dst_size:
                f_dst.truncate(src_size)
            
        # If source is longer than dest, the r+b mode already extended it.
        # But if source has MORE blocks, we need to append them.
        if src_size > dst_size:
            with open(src_ext, 'rb') as f_src, open(dst_ext, 'r+b') as f_dst:
                f_src.seek(dst_size)
                f_dst.seek(0, 2)  # Seek to end
                while True:
                    block = f_src.read(block_size)
                    if not block:
                        break
                    f_dst.write(block)
                    bytes_transferred += len(block)
                    blocks_changed += 1
                    total_blocks += 1
        
        # Preserve timestamps
        try:
            shutil.copystat(src_ext, dst_ext)
        except Exception:
            pass
        
        return True, bytes_transferred, total_blocks
        
    except Exception:
        return False, bytes_transferred, total_blocks


def should_use_delta(src_path: str, dst_path: str) -> bool:
    """Determine if delta transfer should be used instead of full copy.
    
    Delta is beneficial when:
    1. Destination file already exists
    2. Source file is large enough (> 1MB)
    3. Both files are similar size (within 50% — likely same file with edits)
    """
    try:
        src_ext = ensure_extended_path(src_path)
        dst_ext = ensure_extended_path(dst_path)
        
        if not os.path.exists(dst_ext):
            return False  # No existing file to delta against
        
        src_size = os.path.getsize(src_ext)
        if src_size < DELTA_MIN_FILE_SIZE:
            return False  # Too small, full copy is faster
        
        dst_size = os.path.getsize(dst_ext)
        if dst_size == 0:
            return False  # Empty dest, full copy needed
        
        # Check if files are similar size (within 50%)
        ratio = min(src_size, dst_size) / max(src_size, dst_size)
        if ratio < 0.5:
            return False  # Very different sizes, likely different files
        
        return True
        
    except Exception:
        return False
