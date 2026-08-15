from __future__ import annotations
import re

def fmt_size(n_bytes: int | float | None) -> str:
    """Format bytes into clean human-readable string"""
    if n_bytes is None or n_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}" if unit != 'B' else f"{int(n_bytes)} B"
        n_bytes /= 1024
    return f"{n_bytes:.1f} EB"

def fmt_speed(bytes_per_sec: int | float) -> str:
    """Format byte throughput speed string"""
    if bytes_per_sec <= 0:
        return "0 B/s"
    return f"{fmt_size(bytes_per_sec)}/s"

def fmt_eta(seconds: int | float | None) -> str:
    """Format remaining time duration string without em-dashes"""
    if seconds is None or seconds < 0 or seconds == float('inf'):
        return "-"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s left"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{mins}m {secs:02d}s left"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins:02d}m left"

def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filenames"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def parse_size(size_str: str | None) -> int:
    """Parse human-readable size string (e.g. '35.7 KB', '1.2 MB') into byte integer"""
    if not size_str or not isinstance(size_str, str):
        return 0
    size_str = size_str.strip()
    match = re.match(r'^([\d.]+)\s*([A-Za-z]+)?$', size_str)
    if not match:
        return 0
    val = float(match.group(1))
    unit = (match.group(2) or 'B').upper()
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4, 'PB': 1024**5}
    return int(val * units.get(unit, 1))
