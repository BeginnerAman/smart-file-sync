from __future__ import annotations
import os
import sys
import stat
import ctypes

def ensure_extended_path(p: str) -> str:
    """Prepend Windows extended-length path prefix \\\\?\\ or \\\\?\\UNC\\ for long paths (>260 chars)"""
    if sys.platform == 'win32' and p:
        p_abs = os.path.abspath(p)
        if p_abs.startswith('\\\\?\\'):
            return p_abs
        if p_abs.startswith('\\\\'):
            # Network share (UNC path): \\server\share -> \\?\UNC\server\share
            return f"\\\\?\\UNC\\{p_abs[2:]}"
        return f"\\\\?\\{p_abs}"
    return p

def clean_display_path(p: str) -> str:
    """Strip Windows extended-length prefix \\\\?\\ for clean, professional user UI display"""
    if not p:
        return ""
    if p.startswith("\\\\?\\UNC\\"):
        return "\\\\" + p[8:]
    elif p.startswith("\\\\?\\"):
        return p[4:]
    return p

def set_window_titlebar_theme(hwnd: int, dark_mode: bool) -> None:
    """Apply native Windows 10/11 DWM titlebar color & dark mode attributes"""
    if sys.platform != 'win32' or not hwnd:
        return
    try:
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11 / Windows 10 20H1+), 19 for older Win10
        value = ctypes.c_int(1 if dark_mode else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 19, ctypes.byref(value), ctypes.sizeof(value)
        )
        
        # DWMWA_CAPTION_COLOR = 35 (Windows 11 build 22000+)
        # COLORREF format: 0x00BBGGRR
        # Dark: #070b13 -> R=0x07, G=0x0b, B=0x13 -> 0x00130b07
        # Light: #ffffff -> 0x00ffffff
        color_ref = ctypes.c_uint32(0x00130b07 if dark_mode else 0x00ffffff)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(color_ref), ctypes.sizeof(color_ref)
        )
        
        # DWMWA_TEXT_COLOR = 36 (Windows 11)
        text_ref = ctypes.c_uint32(0x00f8fafc if dark_mode else 0x001e293b)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(text_ref), ctypes.sizeof(text_ref)
        )
    except Exception:
        pass

def safe_chmod_write(filepath: str) -> None:
    """Ensure file/directory is not marked read-only before writing or deleting"""
    try:
        ext_path = ensure_extended_path(filepath)
        if os.path.exists(ext_path):
            current_mode = os.stat(ext_path).st_mode
            if not (current_mode & stat.S_IWRITE):
                os.chmod(ext_path, current_mode | stat.S_IWRITE)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# WIN32 KERNEL FAST COPY (CopyFileExW)
# ─────────────────────────────────────────────────────────────────────────────
_copy_file_ex_w = None
if sys.platform == 'win32':
    try:
        from ctypes import wintypes
        _kernel32 = ctypes.windll.kernel32
        _copy_file_ex_w = _kernel32.CopyFileExW
        _copy_file_ex_w.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.BOOL),
            wintypes.DWORD
        ]
        _copy_file_ex_w.restype = wintypes.BOOL
    except Exception:
        _copy_file_ex_w = None

def native_fast_copy(src: str, dst: str, cancel_flag_callable=None) -> bool:
    """
    High-Performance Windows Kernel-Level File Copy using CopyFileExW.
    Preserves creation time, write time, and file attributes directly in kernel space.
    Falls back gracefully to shutil.copy2 on failure or non-Windows platforms.
    """
    import shutil
    src_ext = ensure_extended_path(src)
    dst_ext = ensure_extended_path(dst)

    if cancel_flag_callable and cancel_flag_callable():
        raise InterruptedError("Cancelled by user")

    if _copy_file_ex_w is not None:
        try:
            # 0x0800 = COPY_FILE_COPY_SYMLINK
            flags = 0x0800
            success = _copy_file_ex_w(src_ext, dst_ext, None, None, None, flags)
            if success:
                return True
            else:
                err = ctypes.GetLastError()
                if err in (2, 3):
                    raise FileNotFoundError(f"Source file not found (WinError {err})")
                elif err == 5:
                    raise PermissionError(f"Access denied (WinError 5)")
                # Fallback to standard copy2 on unexpected OS status
        except (FileNotFoundError, PermissionError, InterruptedError):
            raise
        except Exception:
            pass

    shutil.copy2(src_ext, dst_ext)
    return True

def set_windows_startup(app_name: str, app_path: str, enable: bool = True) -> bool:
    """Add or remove application from Windows user Run registry"""
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{app_path}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False
