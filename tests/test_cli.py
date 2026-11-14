import unittest
import os
import sys
import shutil
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_sync.cli import parse_args, compute_diffs, sync_files, scan_directory


class TestCLIArgs(unittest.TestCase):
    def test_parse_args_defaults(self):
        args = parse_args(['--src', 'C:/src', '--dst', 'C:/dst'])
        self.assertEqual(args.src, 'C:/src')
        self.assertEqual(args.dst, 'C:/dst')
        self.assertEqual(args.mode, 'copy')
        self.assertEqual(args.threads, 4)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.verify)

    def test_parse_args_modes(self):
        for mode in ['copy', 'mirror', 'two-way', 'bidirectional']:
            args = parse_args(['--src', 'C:/src', '--dst', 'C:/dst', '--mode', mode])
            self.assertEqual(args.mode, mode)

    def test_parse_args_invalid_mode(self):
        from unittest.mock import patch
        import io
        with patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(['--src', 'C:/src', '--dst', 'C:/dst', '--mode', 'invalid_mode'])


class TestCLIDiffComputation(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix='cli_test_src_')
        self.dst_dir = tempfile.mkdtemp(prefix='cli_test_dst_')

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_two_way_diff_direction(self):
        # 1. File only in source
        src_map = {
            'src_only.txt': {'full': os.path.join(self.src_dir, 'src_only.txt'), 'size': 10, 'mtime': 1000.0},
            'src_newer.txt': {'full': os.path.join(self.src_dir, 'src_newer.txt'), 'size': 20, 'mtime': 2000.0},
            'dst_newer.txt': {'full': os.path.join(self.src_dir, 'dst_newer.txt'), 'size': 30, 'mtime': 1000.0},
            'identical.txt': {'full': os.path.join(self.src_dir, 'identical.txt'), 'size': 40, 'mtime': 1000.0},
        }
        # 2. File only in destination
        dst_map = {
            'dst_only.txt': {'full': os.path.join(self.dst_dir, 'dst_only.txt'), 'size': 15, 'mtime': 1000.0},
            'src_newer.txt': {'full': os.path.join(self.dst_dir, 'src_newer.txt'), 'size': 20, 'mtime': 1000.0},
            'dst_newer.txt': {'full': os.path.join(self.dst_dir, 'dst_newer.txt'), 'size': 30, 'mtime': 2000.0},
            'identical.txt': {'full': os.path.join(self.dst_dir, 'identical.txt'), 'size': 40, 'mtime': 1001.0}, # Within 2.0s tolerance
        }

        diffs = compute_diffs(src_map, dst_map, self.dst_dir, mode='two-way', src_root=self.src_dir)
        
        diff_by_rel = {d['rel_path']: d for d in diffs}
        
        # Identical file should be ignored
        self.assertNotIn('identical.txt', diff_by_rel)
        
        # src_only -> src_to_dst
        self.assertIn('src_only.txt', diff_by_rel)
        self.assertEqual(diff_by_rel['src_only.txt']['direction'], 'src_to_dst')
        self.assertEqual(diff_by_rel['src_only.txt']['reason'], 'Missing in Destination')
        
        # dst_only -> dst_to_src
        self.assertIn('dst_only.txt', diff_by_rel)
        self.assertEqual(diff_by_rel['dst_only.txt']['direction'], 'dst_to_src')
        self.assertEqual(diff_by_rel['dst_only.txt']['reason'], 'Missing in Source')
        
        # src_newer -> src_to_dst
        self.assertIn('src_newer.txt', diff_by_rel)
        self.assertEqual(diff_by_rel['src_newer.txt']['direction'], 'src_to_dst')
        self.assertEqual(diff_by_rel['src_newer.txt']['reason'], 'Source Newer')
        
        # dst_newer -> dst_to_src
        self.assertIn('dst_newer.txt', diff_by_rel)
        self.assertEqual(diff_by_rel['dst_newer.txt']['direction'], 'dst_to_src')
        self.assertEqual(diff_by_rel['dst_newer.txt']['reason'], 'Destination Newer')


class TestCLISyncExecution(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix='cli_sync_src_')
        self.dst_dir = tempfile.mkdtemp(prefix='cli_sync_dst_')

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_bidirectional_sync_files(self):
        # Create file in source only
        src_file = os.path.join(self.src_dir, 'a.txt')
        with open(src_file, 'w') as f:
            f.write('from source')

        # Create file in destination only
        dst_file = os.path.join(self.dst_dir, 'b.txt')
        with open(dst_file, 'w') as f:
            f.write('from destination')

        # Create shared file, newer in destination
        shared_src = os.path.join(self.src_dir, 'shared.txt')
        shared_dst = os.path.join(self.dst_dir, 'shared.txt')
        with open(shared_src, 'w') as f:
            f.write('old version')
        os.utime(shared_src, (1000.0, 1000.0))

        with open(shared_dst, 'w') as f:
            f.write('newer version from dst')
        os.utime(shared_dst, (2000.0, 2000.0))

        args = parse_args(['--src', self.src_dir, '--dst', self.dst_dir, '--mode', 'two-way', '--quiet'])
        
        src_map = scan_directory(self.src_dir, [], set(), 'source', quiet=True)
        dst_map = scan_directory(self.dst_dir, [], set(), 'destination', quiet=True)
        diffs = compute_diffs(src_map, dst_map, self.dst_dir, mode=args.mode, src_root=self.src_dir)
        
        copied, errors, skipped, total_bytes, elapsed = sync_files(diffs, args, src_map, dst_map)
        
        self.assertEqual(errors, 0)
        self.assertEqual(copied, 3) # a.txt (src->dst), b.txt (dst->src), shared.txt (dst->src)
        
        # Verify both directories now have both files and latest content
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, 'a.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, 'b.txt')))
        
        with open(os.path.join(self.src_dir, 'shared.txt'), 'r') as f:
            self.assertEqual(f.read(), 'newer version from dst')

    def test_mirror_mode_orphan_deletion(self):
        # Source has file1
        with open(os.path.join(self.src_dir, 'keep.txt'), 'w') as f:
            f.write('keep this')

        # Destination has file1 and an orphaned file
        with open(os.path.join(self.dst_dir, 'keep.txt'), 'w') as f:
            f.write('keep this')
        orphan_path = os.path.join(self.dst_dir, 'orphan.txt')
        with open(orphan_path, 'w') as f:
            f.write('orphan to delete')

        args = parse_args(['--src', self.src_dir, '--dst', self.dst_dir, '--mode', 'mirror', '--quiet'])
        
        src_map = scan_directory(self.src_dir, [], set(), 'source', quiet=True)
        dst_map = scan_directory(self.dst_dir, [], set(), 'destination', quiet=True)
        diffs = compute_diffs(src_map, dst_map, self.dst_dir, mode=args.mode, src_root=self.src_dir)
        
        copied, errors, skipped, total_bytes, elapsed = sync_files(diffs, args, src_map, dst_map)
        
        self.assertEqual(errors, 0)
        # Orphan should be deleted
        self.assertFalse(os.path.exists(orphan_path))
        # Keep should still exist
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, 'keep.txt')))


if __name__ == '__main__':
    unittest.main()
