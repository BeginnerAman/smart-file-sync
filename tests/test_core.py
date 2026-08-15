import unittest
import os
import sys
import shutil
import tempfile
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_sync.core.scanner import fast_scandir, fast_folder_stats
from smart_sync.utils.formatters import fmt_size, fmt_speed, fmt_eta
from smart_sync.core.hasher import calc_file_md5, calc_streaming_hash
from smart_sync.core.scan_cache import ScanCache

class TestScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='smartsync_test_')
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_empty_directory(self):
        results = list(fast_scandir(self.test_dir))
        self.assertEqual(len(results), 0)
    
    def test_scan_finds_files(self):
        for i in range(5):
            with open(os.path.join(self.test_dir, f'file{i}.txt'), 'w') as f:
                f.write(f'content {i}')
        results = list(fast_scandir(self.test_dir))
        self.assertEqual(len(results), 5)
    
    def test_scan_respects_exclusions(self):
        with open(os.path.join(self.test_dir, 'keep.txt'), 'w') as f:
            f.write('keep')
        with open(os.path.join(self.test_dir, '.git'), 'w') as f:
            f.write('excluded')
        results = list(fast_scandir(self.test_dir, exclusions=['.git']))
        names = [r[0] for r in results]
        self.assertIn('keep.txt', names)
        self.assertNotIn('.git', names)
    
    def test_scan_respects_allowed_exts(self):
        with open(os.path.join(self.test_dir, 'doc.txt'), 'w') as f:
            f.write('text')
        with open(os.path.join(self.test_dir, 'img.png'), 'w') as f:
            f.write('image')
        results = list(fast_scandir(self.test_dir, allowed_exts=['.txt']))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 'doc.txt')
    
    def test_folder_stats(self):
        for i in range(3):
            with open(os.path.join(self.test_dir, f'f{i}.txt'), 'w') as f:
                f.write('x' * 100)
        count, total_bytes, mtime = fast_folder_stats(self.test_dir)
        self.assertEqual(count, 3)
        self.assertEqual(total_bytes, 300)
        self.assertGreater(mtime, 0)
    
    def test_nested_directories(self):
        sub = os.path.join(self.test_dir, 'sub', 'deep')
        os.makedirs(sub)
        with open(os.path.join(sub, 'nested.txt'), 'w') as f:
            f.write('deep')
        results = list(fast_scandir(self.test_dir))
        self.assertEqual(len(results), 1)
        self.assertIn('nested.txt', results[0][0])

class TestFormatters(unittest.TestCase):
    def test_fmt_size_bytes(self):
        self.assertEqual(fmt_size(0), '0 B')
        self.assertEqual(fmt_size(512), '512 B')
    
    def test_fmt_size_kb(self):
        result = fmt_size(1536)
        self.assertIn('KB', result)
    
    def test_fmt_size_mb(self):
        result = fmt_size(1024 * 1024 * 2.5)
        self.assertIn('MB', result)
    
    def test_fmt_size_negative(self):
        self.assertEqual(fmt_size(-1), '0 B')
    
    def test_fmt_speed(self):
        result = fmt_speed(1024 * 1024)
        self.assertIn('/s', result)
    
    def test_fmt_eta(self):
        self.assertEqual(fmt_eta(30), '30s left')
        self.assertIn('m', fmt_eta(90))
        self.assertEqual(fmt_eta(-1), '-')

class TestHasher(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='smartsync_hash_')
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_md5_known_value(self):
        path = os.path.join(self.test_dir, 'test.txt')
        with open(path, 'wb') as f:
            f.write(b'hello world')
        result = calc_file_md5(path)
        self.assertEqual(result, '5eb63bbbe01eeed093cb22bb8f5acdc3')
    
    def test_md5_nonexistent(self):
        result = calc_file_md5('/nonexistent/path')
        self.assertIsNone(result)
    
    def test_streaming_hash(self):
        src_path = os.path.join(self.test_dir, 'src.bin')
        dst_path = os.path.join(self.test_dir, 'dst.bin')
        with open(src_path, 'wb') as f:
            f.write(b'test data for streaming')
        with open(src_path, 'rb') as fin, open(dst_path, 'wb') as fout:
            h = calc_streaming_hash(fin, fout, compute_hash=True)
        self.assertIsNotNone(h)
        self.assertEqual(h, calc_file_md5(src_path))
        with open(dst_path, 'rb') as f:
            self.assertEqual(f.read(), b'test data for streaming')

class TestScanCache(unittest.TestCase):
    def test_cache_update_and_check(self):
        c = ScanCache()
        c.update_cache('C:/test_dir', {'file.txt': {'size': 100, 'mtime': 1000.0}})
        self.assertFalse(c.is_file_changed('C:/test_dir', 'file.txt', 100, 1000.0))
        self.assertTrue(c.is_file_changed('C:/test_dir', 'file.txt', 200, 1000.0))
        self.assertTrue(c.is_file_changed('C:/test_dir', 'new.txt', 50, 500.0))
        c.clear()

class TestDelta(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='smartsync_delta_')

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_delta_sync_modified_block(self):
        from smart_sync.core.delta import delta_sync_file, should_use_delta, compute_block_signatures
        src = os.path.join(self.test_dir, 'src.bin')
        dst = os.path.join(self.test_dir, 'dst.bin')
        data = b'A' * (2 * 1024 * 1024)
        with open(src, 'wb') as f:
            f.write(data)
        shutil.copy2(src, dst)
        with open(src, 'r+b') as f:
            f.seek(4096)
            f.write(b'MODIFIED_BLOCK_DATA')
        
        self.assertTrue(should_use_delta(src, dst))
        ok, bytes_written, total_blocks = delta_sync_file(src, dst)
        self.assertTrue(ok)
        self.assertLess(bytes_written, 10000)
        with open(src, 'rb') as f1, open(dst, 'rb') as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_should_use_delta_conditions(self):
        from smart_sync.core.delta import should_use_delta
        src = os.path.join(self.test_dir, 'small.txt')
        dst = os.path.join(self.test_dir, 'small_dst.txt')
        with open(src, 'w') as f:
            f.write('small')
        with open(dst, 'w') as f:
            f.write('small')
        # Small files (<1MB) should return False
        self.assertFalse(should_use_delta(src, dst))
        # Non-existent destination should return False
        self.assertFalse(should_use_delta(src, os.path.join(self.test_dir, 'none.txt')))

class TestDriveMonitor(unittest.TestCase):
    def test_get_removable_drives(self):
        from smart_sync.core.drive_monitor import get_removable_drives
        drives = get_removable_drives()
        self.assertIsInstance(drives, list)

if __name__ == '__main__':
    unittest.main()
