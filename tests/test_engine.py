import unittest
import os
import sys
import shutil
import tempfile
import time
from PySide6.QtCore import QCoreApplication, Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_sync.core.engine import SyncWorker

class TestEngineOptimizations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix="engine_test_src_")
        self.dst_dir = tempfile.mkdtemp(prefix="engine_test_dst_")

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_directory_cache_and_fast_copy(self):
        # Create 100 test files across 10 folders
        files = []
        for i in range(100):
            sub = f"sub_{i % 10}"
            os.makedirs(os.path.join(self.src_dir, sub), exist_ok=True)
            rel = os.path.join(sub, f"test_{i}.txt")
            src_p = os.path.join(self.src_dir, rel)
            dst_p = os.path.join(self.dst_dir, rel)
            with open(src_p, "w") as f:
                f.write(f"Sample content for file {i}\n")
            files.append({
                "filename": f"test_{i}.txt",
                "rel_path": rel,
                "src_path": src_p,
                "dest_path": dst_p,
                "size_bytes": 25,
                "size_str": "25 B"
            })

        worker = SyncWorker()
        worker.files_to_sync = files
        worker.source_dir = self.src_dir
        worker.dest_dir = self.dst_dir
        worker.threads = 4
        worker.use_safe_renames = True
        worker.use_md5_verify = False

        completed_events = []
        worker.signals.file_progress.connect(
            lambda idx, rel, sz, st, dt: completed_events.append((rel, st)) if st == "Completed" else None,
            Qt.DirectConnection
        )

        t0 = time.time()
        worker.run()
        elapsed = time.time() - t0

        self.assertEqual(len(completed_events), 100)
        # Verify all destination files exist with exact content
        for item in files:
            self.assertTrue(os.path.exists(item["dest_path"]))
            with open(item["dest_path"], "r") as f:
                self.assertEqual(f.read(), f"Sample content for file {item['filename'].split('_')[1].split('.')[0]}\n")

        print(f"\n[TestEngineOptimizations] 100 files copied in {elapsed:.3f}s ({100/elapsed:.1f} files/s)")

    def test_missing_source_file_error(self):
        rel = "missing.txt"
        files = [{
            "filename": "missing.txt",
            "rel_path": rel,
            "src_path": os.path.join(self.src_dir, "nonexistent.txt"),
            "dest_path": os.path.join(self.dst_dir, rel),
            "size_bytes": 100,
            "size_str": "100 B"
        }]

        worker = SyncWorker()
        worker.files_to_sync = files
        worker.source_dir = self.src_dir
        worker.dest_dir = self.dst_dir
        worker.threads = 2

        error_events = []
        worker.signals.file_progress.connect(
            lambda idx, rel, sz, st, dt: error_events.append((rel, st, dt)) if st == "Error" else None,
            Qt.DirectConnection
        )

        worker.run()
        self.assertEqual(len(error_events), 1)
        self.assertIn("missing", error_events[0][2].lower())

    def test_native_fast_copy_direct(self):
        from smart_sync.core.platform_win import native_fast_copy
        src = os.path.join(self.src_dir, "test_native.bin")
        dst = os.path.join(self.dst_dir, "test_native_copied.bin")
        payload = b"WIN32_KERNEL_COPY_DATA_" * 1000
        with open(src, "wb") as f:
            f.write(payload)

        ok = native_fast_copy(src, dst)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(dst))
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), payload)

        # Verify missing file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            native_fast_copy(os.path.join(self.src_dir, "missing.bin"), dst)

        # Verify cancel flag raises InterruptedError
        with self.assertRaises(InterruptedError):
            native_fast_copy(src, dst, cancel_flag_callable=lambda: True)

    def test_sliding_window_high_concurrency(self):
        # 300 files with 16 threads to test sliding window replenishment
        files = []
        for i in range(300):
            sub = f"chunk_{i % 15}"
            os.makedirs(os.path.join(self.src_dir, sub), exist_ok=True)
            rel = os.path.join(sub, f"bulk_{i}.dat")
            src_p = os.path.join(self.src_dir, rel)
            dst_p = os.path.join(self.dst_dir, rel)
            with open(src_p, "wb") as f:
                f.write(b"SLIDING_WINDOW_CONCURRENCY_TEST_" * 50)
            files.append({
                "filename": f"bulk_{i}.dat",
                "rel_path": rel,
                "src_path": src_p,
                "dest_path": dst_p,
                "size_bytes": 1500,
                "size_str": "1.5 KB"
            })

        worker = SyncWorker()
        worker.files_to_sync = files
        worker.source_dir = self.src_dir
        worker.dest_dir = self.dst_dir
        worker.threads = 16
        worker.use_safe_renames = True
        worker.use_md5_verify = False

        completed = []
        worker.signals.file_progress.connect(
            lambda idx, rel, sz, st, dt: completed.append(rel) if st == "Completed" else None,
            Qt.DirectConnection
        )

        t0 = time.time()
        worker.run()
        elapsed = time.time() - t0

        self.assertEqual(len(completed), 300)
        rate = 300 / max(elapsed, 0.001)
        print(f"\n[TestSlidingWindow] 300 files with 16 threads: {elapsed:.3f}s -> {rate:.1f} files/s")

    def test_end_to_end_1000_files_benchmark(self):
        # 1,000 files benchmark measuring complete pipeline performance
        files = []
        for i in range(1000):
            sub = f"dir_{i % 25}"
            os.makedirs(os.path.join(self.src_dir, sub), exist_ok=True)
            rel = os.path.join(sub, f"data_{i}.txt")
            src_p = os.path.join(self.src_dir, rel)
            dst_p = os.path.join(self.dst_dir, rel)
            with open(src_p, "w") as f:
                f.write(f"E2E Performance verification data {i}\n")
            files.append({
                "filename": f"data_{i}.txt",
                "rel_path": rel,
                "src_path": src_p,
                "dest_path": dst_p,
                "size_bytes": 40,
                "size_str": "40 B"
            })

        worker = SyncWorker()
        worker.files_to_sync = files
        worker.source_dir = self.src_dir
        worker.dest_dir = self.dst_dir
        worker.threads = 16
        worker.use_safe_renames = True
        worker.use_md5_verify = False

        progress_emits = []
        worker.signals.overall_progress.connect(
            lambda done, total, txt, spd, avg_spd, eta: progress_emits.append(done),
            Qt.DirectConnection
        )

        t0 = time.time()
        worker.run()
        elapsed = time.time() - t0

        rate = 1000 / max(elapsed, 0.001)
        print(f"\n[E2E Benchmark 1,000 files]: {elapsed:.3f}s -> {rate:.1f} files/sec (Progress signals emitted: {len(progress_emits)})")
        
        # Verify all destination files exist
        for item in files:
            self.assertTrue(os.path.exists(item["dest_path"]))

        # Verify throttling worked: 1,000 files should NOT emit 1,000 signals, but a clean throttled stream
        self.assertLess(len(progress_emits), 500)
        self.assertEqual(progress_emits[-1], 1000)

if __name__ == "__main__":
    unittest.main()
