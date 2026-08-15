import os

def rotate_log_file(log_path: str, max_size_mb: float = 5.0, keep_lines: int = 2000):
    try:
        if not os.path.exists(log_path):
            return
            
        size_bytes = os.path.getsize(log_path)
        if size_bytes > max_size_mb * 1024 * 1024:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if len(lines) > keep_lines:
                lines = lines[-keep_lines:]
                
            with open(log_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
    except Exception:
        pass
