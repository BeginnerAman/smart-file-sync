/**
 * Smart File Sync - Interactive Landing Page Logic
 * Vanilla JavaScript (Zero External Dependencies)
 */

document.addEventListener('DOMContentLoaded', () => {

  // ── 1. APP SHOWCASE SCREEN SWITCHER (Interactive Desktop Mockup) ──
  const sidebarButtons = document.querySelectorAll('.preview-sidebar .sidebar-item');
  const previewScreens = document.querySelectorAll('.preview-screen');
  const previewCrumbs = document.getElementById('previewCrumbs');

  const crumbTitles = {
    'setup': 'Workspace › Folder Setup',
    'results': 'Workspace › Scan Differences (4 Items)',
    'queue': 'Workspace › Active Sync Queue (16 Threads)',
    'dashboard': 'Workspace › Health & Analytics Dashboard',
    'history': 'Workspace › Audit & Sync History',
    'settings': 'Workspace › Engine Preferences & Rules'
  };

  sidebarButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      if (!tabId) return;

      // Update active sidebar state
      sidebarButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Update screen view
      previewScreens.forEach(screen => {
        screen.classList.remove('active');
      });
      const activeScreen = document.getElementById(`screen-${tabId}`);
      if (activeScreen) {
        activeScreen.classList.add('active');
      }

      // Update breadcrumb
      if (previewCrumbs && crumbTitles[tabId]) {
        previewCrumbs.textContent = crumbTitles[tabId];
      }
    });
  });

  // ── 2. INTERACTIVE DELTA TRANSFER SIMULATOR ──
  const blockGrid = document.getElementById('blockGrid');
  const btnSimulate = document.getElementById('btnSimulateEdit');
  const simBytesTransferred = document.getElementById('simBytesTransferred');
  const simSavings = document.getElementById('simSavings');

  const TOTAL_BLOCKS = 120; // 120 blocks representing a 2MB file
  const BLOCK_SIZE_BYTES = 4096; // 4KB per block

  function initBlockGrid() {
    if (!blockGrid) return;
    blockGrid.innerHTML = '';
    for (let i = 0; i < TOTAL_BLOCKS; i++) {
      const block = document.createElement('div');
      block.className = 'block-unit';
      block.id = `block-${i}`;
      blockGrid.appendChild(block);
    }
  }

  function simulateEdit() {
    if (!blockGrid) return;
    
    // Reset all blocks
    const allBlocks = blockGrid.querySelectorAll('.block-unit');
    allBlocks.forEach(b => b.classList.remove('modified'));

    // Pick 1 random block to modify
    const randomIndex = Math.floor(Math.random() * TOTAL_BLOCKS);
    const targetBlock = document.getElementById(`block-${randomIndex}`);
    
    if (targetBlock) {
      targetBlock.classList.add('modified');
    }

    // Animate stats counter
    if (simBytesTransferred) {
      simBytesTransferred.textContent = `${BLOCK_SIZE_BYTES.toLocaleString()} Bytes (4.0 KB)`;
    }
    if (simSavings) {
      simSavings.textContent = '99.8% Time & Bandwidth Saved (1 of 120 blocks)';
    }
  }

  initBlockGrid();
  simulateEdit();

  if (btnSimulate) {
    btnSimulate.addEventListener('click', simulateEdit);
  }

  // ── 3. ONE-CLICK CLI CODE COPY ──
  const btnCopyCLI = document.getElementById('btnCopyCLI');
  const copyBtnText = document.getElementById('copyBtnText');

  if (btnCopyCLI) {
    btnCopyCLI.addEventListener('click', async () => {
      const commandText = 'python -m smart_sync --src "D:\\Photos" --dst "E:\\Backup" --mode mirror --threads 8 --verify';
      try {
        await navigator.clipboard.writeText(commandText);
        if (copyBtnText) {
          copyBtnText.textContent = 'Copied to Clipboard!';
          setTimeout(() => {
            copyBtnText.textContent = 'Copy Command';
          }, 2200);
        }
      } catch (err) {
        // Fallback for older browsers
        const tempInput = document.createElement('textarea');
        tempInput.value = commandText;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        if (copyBtnText) {
          copyBtnText.textContent = 'Copied!';
          setTimeout(() => {
            copyBtnText.textContent = 'Copy Command';
          }, 2200);
        }
      }
    });
  }

  // ── 4. FAQ ACCORDION INTERACTION ──
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    if (questionBtn) {
      questionBtn.addEventListener('click', () => {
        const isActive = item.classList.contains('active');
        // Close all other items
        faqItems.forEach(other => other.classList.remove('active'));
        // Toggle current item
        if (!isActive) {
          item.classList.add('active');
        }
      });
    }
  });

  // ── 5. SMOOTH SCROLL FOR NAV LINKS ──
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      const targetElem = document.querySelector(targetId);
      if (targetElem) {
        e.preventDefault();
        targetElem.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

});
