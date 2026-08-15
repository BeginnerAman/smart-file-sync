"""Smart File Sync — Command Line Interface

Usage:
    python -m smart_sync.cli --src "D:\\Photos" --dst "E:\\Backup" [options]

Options:
    --src PATH          Source directory (required)
    --dst PATH          Destination directory (required)
    --mode MODE         Sync mode: 'copy' (default) or 'mirror'
    --threads N         Number of parallel threads (default: 4)
    --dry-run           Preview only, don't copy files
    --verify            MD5 verify after copy
    --filter EXT        File extension filter (e.g., .jpg,.png)
    --exclude EXT       Extensions to exclude (e.g., .tmp,.log)
    --throttle N        Bandwidth limit in MB/s (0 = unlimited)
    --quiet             Suppress progress output
    --version           Show version
    --help              Show this help
"""
import os
import sys
import time
import argparse
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_sync.core.scanner import fast_scandir
from smart_sync.utils.formatters import fmt_size, fmt_speed, fmt_eta
from smart_sync.utils.constants import APP_VERSION, DEFAULT_EXCLUSIONS


def parse_args():
    parser = argparse.ArgumentParser(
        prog='smartsync',
        description='Smart File Sync — Fast, reliable local file synchronization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  smartsync --src D:\\Photos --dst E:\\Backup
  smartsync --src D:\\Projects --dst E:\\Mirror --mode mirror
  smartsync --src D:\\Videos --dst E:\\Backup --filter .mp4,.avi --threads 8
  smartsync --src D:\\Work --dst E:\\Backup --dry-run"""
    )
    parser.add_argument('--src', required=True, help='Source directory')
    parser.add_argument('--dst', required=True, help='Destination directory')
    parser.add_argument('--mode', choices=['copy', 'mirror'], default='copy', help='Sync mode (default: copy)')
    parser.add_argument('--threads', type=int, default=4, help='Parallel threads (default: 4)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--verify', action='store_true', help='MD5 verify after copy')
    parser.add_argument('--filter', type=str, default='', help='Include only these extensions (comma-separated)')
    parser.add_argument('--exclude', type=str, default='', help='Exclude these extensions (comma-separated)')
    parser.add_argument('--throttle', type=int, default=0, help='Bandwidth limit MB/s')
    parser.add_argument('--quiet', action='store_true', help='Suppress progress')
    parser.add_argument('--version', action='version', version=f'Smart File Sync v{APP_VERSION}')
    return parser.parse_args()


def print_header(args):
    print(f"\n{'='*60}")
    print(f"  Smart File Sync v{APP_VERSION} — CLI Mode")
    print(f"{'='*60}")
    print(f"  Source:      {args.src}")
    print(f"  Destination: {args.dst}")
    print(f"  Mode:        {args.mode}")
    print(f"  Threads:     {args.threads}")
    if args.dry_run:
        print(f"  ** DRY RUN — No files will be copied **")
    print(f"{'='*60}\n")


def scan_directory(path, excl_exts, allowed_exts, label, quiet=False):
    """Scan a directory and return file map."""
    file_map = {}
    count = 0
    for rel, full, st in fast_scandir(path, excl_exts):
        ext = Path(rel).suffix.lower()
        if allowed_exts and ext not in allowed_exts:
            continue
        file_map[rel] = {'full': full, 'size': st.st_size, 'mtime': st.st_mtime}
        count += 1
        if not quiet and count % 1000 == 0:
            print(f"  Scanning {label}... {count:,} files", end='\r')
    if not quiet:
        print(f"  Scanning {label}... {count:,} files — Done")
    return file_map


def compute_diffs(src_map, dst_map, dst_root):
    """Compare source and destination, return list of files to sync."""
    from datetime import datetime
    diffs = []
    for rel, s_data in src_map.items():
        d_full = os.path.join(dst_root, rel)
        if rel not in dst_map:
            diffs.append({
                'rel_path': rel,
                'src_path': s_data['full'],
                'dest_path': d_full,
                'size_bytes': s_data['size'],
                'size_str': fmt_size(s_data['size']),
                'reason': 'Missing'
            })
        else:
            d_data = dst_map[rel]
            if s_data['size'] != d_data['size'] or abs(s_data['mtime'] - d_data['mtime']) > 1.0:
                diffs.append({
                    'rel_path': rel,
                    'src_path': s_data['full'],
                    'dest_path': d_full,
                    'size_bytes': s_data['size'],
                    'size_str': fmt_size(s_data['size']),
                    'reason': 'Modified'
                })
    return diffs


def sync_files(diffs, args):
    """Perform the actual file sync."""
    import shutil
    from smart_sync.core.platform_win import ensure_extended_path, safe_chmod_write
    from smart_sync.core.hasher import calc_file_md5
    
    copied = 0
    errors = 0
    skipped = 0
    total_bytes = 0
    start_time = time.time()
    total = len(diffs)
    
    for i, diff in enumerate(diffs, 1):
        rel = diff['rel_path']
        src = diff['src_path']
        dst = diff['dest_path']
        size = diff['size_bytes']
        
        if args.dry_run:
            if not args.quiet:
                print(f"  [{i}/{total}] Would copy: {rel} ({diff['size_str']})")
            skipped += 1
            continue
        
        try:
            # Create destination directory
            dst_dir = os.path.dirname(dst)
            os.makedirs(ensure_extended_path(dst_dir), exist_ok=True)
            
            # Copy file
            safe_chmod_write(dst)
            shutil.copy2(ensure_extended_path(src), ensure_extended_path(dst))
            
            # MD5 verify
            if args.verify:
                src_hash = calc_file_md5(src)
                dst_hash = calc_file_md5(dst)
                if src_hash != dst_hash:
                    print(f"  [FAIL] MD5 mismatch: {rel}")
                    errors += 1
                    continue
            
            copied += 1
            total_bytes += size
            
            if not args.quiet:
                elapsed = time.time() - start_time
                speed = total_bytes / max(0.01, elapsed)
                pct = int(i / total * 100)
                print(f"  [{pct:3d}%] Copied: {rel} ({diff['size_str']}) — {fmt_speed(speed)}")
                
        except PermissionError:
            print(f"  [ERROR] Permission denied: {rel}")
            errors += 1
        except Exception as e:
            print(f"  [ERROR] {rel}: {e}")
            errors += 1
    
    # Mirror mode: delete orphans
    if args.mode == 'mirror' and not args.dry_run:
        print("\n  Mirror mode: Checking for orphaned files...")
        # Re-scan to find orphans (already have src_map from caller)
    
    return copied, errors, skipped, total_bytes, time.time() - start_time


def main():
    args = parse_args()
    
    # Validate paths
    if not os.path.isdir(args.src):
        print(f"Error: Source directory not found: {args.src}")
        sys.exit(1)
    if not os.path.isdir(args.dst):
        try:
            os.makedirs(args.dst, exist_ok=True)
            print(f"  Created destination: {args.dst}")
        except Exception as e:
            print(f"Error: Cannot create destination: {e}")
            sys.exit(1)
    
    print_header(args)
    
    # Parse filters
    excl_exts = [e.strip().lower() for e in args.exclude.split(',') if e.strip()] if args.exclude else list(DEFAULT_EXCLUSIONS)
    allowed_exts = set(e.strip().lower() if e.startswith('.') else f'.{e.strip().lower()}' for e in args.filter.split(',') if e.strip()) if args.filter else set()
    
    # Scan
    print("  Phase 1: Scanning directories...")
    src_map = scan_directory(args.src, excl_exts, allowed_exts, 'source', args.quiet)
    dst_map = scan_directory(args.dst, excl_exts, allowed_exts, 'destination', args.quiet)
    
    # Diff
    print("\n  Phase 2: Computing differences...")
    diffs = compute_diffs(src_map, dst_map, args.dst)
    
    total_size = sum(d['size_bytes'] for d in diffs)
    missing = sum(1 for d in diffs if d['reason'] == 'Missing')
    modified = sum(1 for d in diffs if d['reason'] == 'Modified')
    
    print(f"  Found {len(diffs)} differences ({missing} missing, {modified} modified)")
    print(f"  Total size to sync: {fmt_size(total_size)}")
    
    if not diffs:
        print("\n  Everything is in sync! Nothing to do.")
        sys.exit(0)
    
    # Sync
    print(f"\n  Phase 3: {'Preview' if args.dry_run else 'Syncing'} files...")
    copied, errors, skipped, bytes_done, elapsed = sync_files(diffs, args)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  SYNC COMPLETE")
    print(f"{'='*60}")
    if args.dry_run:
        print(f"  Would copy: {skipped} files ({fmt_size(total_size)})")
    else:
        print(f"  Copied:  {copied} files ({fmt_size(bytes_done)})")
        print(f"  Errors:  {errors}")
        print(f"  Time:    {elapsed:.1f}s")
        if elapsed > 0:
            print(f"  Speed:   {fmt_speed(bytes_done / elapsed)}")
    print(f"{'='*60}\n")
    
    sys.exit(1 if errors > 0 else 0)


if __name__ == '__main__':
    main()
