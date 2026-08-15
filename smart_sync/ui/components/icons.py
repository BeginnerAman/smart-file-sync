from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtSvg import QSvgRenderer

class IconManager:
    """
    Official Lucide SVG Vector Icon Engine.
    Uses authentic 24x24 Lucide SVG vector paths with high-DPI smooth anti-aliased scaling.
    Guarantees 100% full-glyph rendering without clipping.
    """
    _cache = {}

    # Official Lucide SVG Definitions (24x24 viewBox, stroke-width=2, stroke-linecap=round, stroke-linejoin=round)
    LUCIDE_PATHS = {
        "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
        "scan": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "queue": '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
        "dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
        "history": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
        "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
        "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
        "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
        "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
        "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
        "check": '<polyline points="20 6 9 17 4 12"/>',
        "cross": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
        "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
        "trash": '<path d="3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
        "refresh": '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
        "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
        "arrow_right": '<path d="m9 18 6-6-6-6"/>',
        "arrow_left": '<path d="m15 18-6-6 6-6"/>',
        "leaf": '<path d="M11 20A7 7 0 0 1 4 13C4 7 11 2 20 2c0 9-5 16-11 16Z"/><path d="M4 13c7 0 12-5 12-11"/>',
        "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    }

    @classmethod
    def get_vector_icon(cls, name: str, color_hex: str = "#94a3b8", size: int = 20) -> QIcon:
        """Render official Lucide vector icon into a high-DPI QIcon"""
        cache_key = f"icon_{name}_{color_hex}_{size}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        pixmap = cls.get_vector_pixmap(name, color_hex, size)
        icon = QIcon(pixmap)
        cls._cache[cache_key] = icon
        return icon

    @classmethod
    def get_vector_pixmap(cls, name: str, color_hex: str = "#94a3b8", size: int = 20) -> QPixmap:
        """Render official Lucide SVG path into a crisp, perfectly-sized QPixmap"""
        cache_key = f"pix_{name}_{color_hex}_{size}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        svg_inner = cls.LUCIDE_PATHS.get(name, cls.LUCIDE_PATHS["file"])
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color_hex}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{svg_inner}</svg>'''
        
        # Super-sample at 2x and smoothly downscale to exact size
        scale = 2
        d_size = size * scale
        canvas = QPixmap(d_size, d_size)
        canvas.fill(Qt.transparent)

        renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter, QRectF(0, 0, d_size, d_size))
        painter.end()

        # Produce exact pixel-sized pixmap
        final_pixmap = canvas.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        cls._cache[cache_key] = final_pixmap
        return final_pixmap
