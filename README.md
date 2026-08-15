<p align="center">
  <img src="assets/logo_transparent.png" alt="Smart File Sync Logo" width="130" />
</p>

<h1 align="center">Smart File Sync</h1>

<p align="center">
  <strong>High-Performance, 100% Offline File Synchronization Engine for Windows</strong>
</p>

<p align="center">
  <a href="https://github.com/BeginnerAman/smart-file-sync/releases"><img src="https://img.shields.io/badge/release-v4.0.0-0ea5e9?style=flat-square" alt="Release v4.0.0"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-38bdf8?style=flat-square" alt="Python 3.11+"></a>
  <a href="https://pyside.org/"><img src="https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-10b981?style=flat-square" alt="PySide6 Qt6"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-64748b?style=flat-square" alt="Windows 64-bit"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT License"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-19%2F19%20passing-success?style=flat-square" alt="Tests Passing"></a>
</p>

<p align="center">
  <a href="#key-features">Key Features</a> &bull;
  <a href="#how-delta-transfer-works">Delta Engine</a> &bull;
  <a href="#comparison">Comparison</a> &bull;
  <a href="#downloads">Downloads</a> &bull;
  <a href="#cli-usage">CLI Guide</a> &bull;
  <a href="#building-from-source">Build from Source</a>
</p>

---

## Overview

Smart File Sync is a modern, privacy-first desktop file synchronization and backup application engineered for Windows. It provides multi-threaded folder synchronization, block-level delta transfers, real-time filesystem monitoring, and hardware USB drive detection without cloud dependencies or subscription fees.

All synchronization operations run locally on your system. Zero network telemetry, zero background trackers, and zero external server communication.

---

## Key Features

* **Block-Level Delta Transfer:** Compares 4KB rolling block signatures on modified files. Only transfers changed blocks, saving up to 99.8% bandwidth and drive wear on large files.
* **100% Offline & Private:** Built strictly for local storage, external SSDs, USB drives, and local network shares.
* **USB Hot-Plug Auto-Detection:** Background hardware monitor detects when external drives are connected or disconnected.
* **Real-Time Filesystem Watcher:** File changes in watched directories are detected immediately and queued for synchronization.
* **Atomic Safe Writes:** Files stream to temporary staging files (`.smartsync.tmp`) and undergo checksum verification before atomic replacement, eliminating corruption risks during power interruptions.
* **Flexible Sync Modes:** Supports One-Way Copy, Exact Mirror (with automatic orphan cleanup), and True Bidirectional Sync.
* **Multi-Version File History:** Configurable automatic versioning (1, 3, or 5 versions) stored in structured version directories before file replacements.
* **Pre & Post Sync Scripting:** Execute custom batch or Python scripts before and after synchronization tasks.
* **Bandwidth Throttling:** Built-in transfer rate limiter for background operations.
* **Headless CLI Interface:** Full command-line support for automation via Windows Task Scheduler, PowerShell, or batch scripts.

---

## How Delta Transfer Works

When syncing modified large files (such as database containers, virtual disk images, or video project files), traditional file sync utilities re-copy the entire file across drives. 

Smart File Sync computes rolling 4KB block checksum signatures for both source and destination:

```
[Source File]      [Block 1] [Block 2] [MODIFIED Block 3] [Block 4] ... [Block N]
                      |         |               |              |            |
                      v         v               v              v            v
                 (Signatures Match)       (Delta Copied)   (Signatures Match)
                      |         |               |              |            |
[Destination File] [Block 1] [Block 2] [UPDATED Block 3]  [Block 4] ... [Block N]
```

### Benchmark Comparison (2MB Modified Test File)

| Sync Method | Data Transferred | Speedup / Savings |
| :--- | :--- | :--- |
| Traditional Full Copy | 2,080,000 Bytes (2.0 MB) | 0% (Baseline) |
| **Smart File Sync Delta** | **4,096 Bytes (4.0 KB)** | **99.8% Time & Write Savings** |

---

## Comparison: Smart File Sync vs Alternatives

| Feature | Smart File Sync v4.0 | GoodSync (Commercial) | FreeFileSync |
| :--- | :--- | :--- | :--- |
| **License & Price** | **100% Free & Open Source (MIT)** | $29.95 / year subscription | Free (Donation for auto features) |
| **Block-Level Delta Transfer** | **Yes (Built-in 4KB Engine)** | Yes | No (Full file re-copy) |
| **Offline Privacy** | **Strictly Offline (Zero Telemetry)** | Requires Account & Server Login | Offline |
| **USB Hot-Plug Detect** | **Yes (Integrated Thread)** | Yes | Requires Separate Utility |
| **Real-Time Watcher** | **Yes (Integrated Watchdog)** | Yes | Requires RealtimeSync |
| **UI Theme** | **Modern Native Dark Theme** | Legacy Light Interface | Classic Interface |
| **Portable Version** | **Yes (0.2s Instant Launch)** | Installer Required | Portable Available |
| **CLI Automation** | **Yes (Included Standard)** | Enterprise Add-on Only | Batch XML configurations |

---

## Downloads

Download the latest release from the [Releases Page](https://github.com/BeginnerAman/smart-file-sync/releases):

* **Standalone Executable (`SmartFileSync.exe` - 26.7 MB):** Self-contained single executable. Clean build with all bloat libraries stripped.
* **Portable Edition (`SmartFileSync-Portable.zip` - 26.7 MB):** Pre-extracted portable folder with instant 0.2s launch speed. Ideal for USB drives.

### System Requirements

* **Operating System:** Windows 10 (64-bit) or Windows 11 (64-bit)
* **Hardware:** Any x86_64 compatible CPU, 250 MB free RAM, local or USB storage

---

## CLI Usage

Smart File Sync includes a headless CLI mode for automated backup tasks:

```powershell
# Basic one-way synchronization
python -m smart_sync --src "D:\Projects" --dst "E:\Backup"

# Exact mirror mode with MD5 checksum verification and 8 parallel threads
python -m smart_sync --src "D:\Work" --dst "E:\Mirror" --mode mirror --threads 8 --verify

# Filter specific file extensions with 50 MB/s bandwidth limit
python -m smart_sync --src "D:\Videos" --dst "E:\Backup" --filter .mp4,.mkv --throttle 50

# Dry-run preview mode (no files copied)
python -m smart_sync --src "D:\Data" --dst "E:\Backup" --dry-run
```

### CLI Parameters Reference

* `--src <path>` : Source folder directory path (Required)
* `--dst <path>` : Destination folder directory path (Required)
* `--mode {copy,mirror}` : Synchronization mode (default: `copy`)
* `--threads <N>` : Parallel worker thread count (default: `4`)
* `--dry-run` : Preview operations without writing files
* `--verify` : Compute and verify MD5 hashes after writing
* `--filter <ext1,ext2>` : Comma-separated allowed file extensions
* `--exclude <ext1,ext2>` : Comma-separated excluded file extensions
* `--throttle <MB/s>` : Maximum transfer rate limit in megabytes per second
* `--quiet` : Suppress interactive terminal progress bars

---

## Project Structure

```
smart-file-sync/
├── smart_sync/
│   ├── core/
│   │   ├── engine.py          # Multi-threaded sync worker with atomic writes
│   │   ├── delta.py           # 4KB block-level delta comparison engine
│   │   ├── scanner.py         # Fast recursive scandir and metadata threads
│   │   ├── scan_cache.py      # Persistent JSON scan cache for instant diffs
│   │   ├── drive_monitor.py   # Windows USB hot-plug detection thread
│   │   ├── watcher.py         # Real-time filesystem watchdog monitor
│   │   ├── hasher.py          # Streaming MD5 checksum calculation
│   │   └── platform_win.py    # Windows native DWM dark titlebar & startup
│   ├── models/
│   │   ├── history_model.py   # Session history persistence & CSV export
│   │   └── scan_model.py      # Table models with multi-filter sorting
│   ├── ui/
│   │   ├── main_window.py     # Main window coordinator
│   │   ├── pages/             # Setup, Results, Queue, Dashboard, History, Settings
│   │   ├── components/        # Modern custom UI widgets and visual step trackers
│   │   └── dialogs/           # Progress dialogs and conflict resolvers
│   ├── utils/
│   │   ├── constants.py       # Default configurations & themes
│   │   ├── formatters.py      # File size, transfer speed, and ETA formatters
│   │   └── log_manager.py     # Log rotation manager
│   ├── cli.py                 # Headless CLI entry point
│   └── __main__.py            # Python package runner
├── tests/
│   └── test_core.py           # 19 automated unit tests
├── app.py                     # Main application entry point
├── SmartFileSync.spec         # PyInstaller dual build spec configuration
├── index.html                 # Showcase website
├── styles.css                 # Showcase website stylesheet
└── script.js                  # Showcase website interactive logic
```

---

## Building from Source

### 1. Clone the Repository

```bash
git clone https://github.com/BeginnerAman/smart-file-sync.git
cd smart-file-sync
```

### 2. Install Dependencies

```bash
pip install PySide6 watchdog
```

### 3. Run Automated Tests

```bash
python -m unittest tests.test_core -v
```

### 4. Build Executables with PyInstaller

```bash
pyinstaller SmartFileSync.spec --clean --noconfirm
```

Output binaries will be generated in the `dist/` directory:
* `dist/SmartFileSync.exe`
* `dist/SmartFileSync-Portable/`

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
