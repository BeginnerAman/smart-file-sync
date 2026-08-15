from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QIcon
from PySide6.QtCore import Qt, QRect, QSize

from .icons import IconManager

class BadgeDelegate(QStyledItemDelegate):
    """Paints modern, high-contrast status pill badges in table columns"""
    def __init__(self, is_dark_mode_callable, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode_callable

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        text = index.data(Qt.DisplayRole)
        if not text:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        dark = self.is_dark_mode() if callable(self.is_dark_mode) else True
        
        # Color mapping by status
        if text in ("Missing", "Pending"):
            bg = QColor("#0f766e") if dark else QColor("#ccfbf1")
            fg = QColor("#ffffff") if dark else QColor("#0f766e")
        elif "Modified" in text or text in ("In Progress", "Active"):
            bg = QColor("#d97706") if dark else QColor("#fef3c7")
            fg = QColor("#ffffff") if dark else QColor("#92400e")
        elif text in ("Completed", "Success", "Synced"):
            bg = QColor("#10b981") if dark else QColor("#d1fae5")
            fg = QColor("#ffffff") if dark else QColor("#065f46")
        elif text in ("Error", "Failed", "Stopped"):
            bg = QColor("#dc2626") if dark else QColor("#fee2e2")
            fg = QColor("#ffffff") if dark else QColor("#991b1b")
        else:
            bg = QColor("#2563eb") if dark else QColor("#dbeafe")
            fg = QColor("#ffffff") if dark else QColor("#1e40af")

        # Pill dimensions
        rect = option.rect
        badge_w = min(rect.width() - 14, 96)
        badge_h = 22
        badge_x = rect.x() + (rect.width() - badge_w) // 2
        badge_y = rect.y() + (rect.height() - badge_h) // 2
        badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QPen(fg))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignCenter, text)

        painter.restore()

class FileIconDelegate(QStyledItemDelegate):
    """Paints clean Lucide vector file icon next to filenames without clipping or selection bugs"""
    def __init__(self, is_dark_mode_callable, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode_callable

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # Draw background and selection state natively first
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        else:
            super().paint(painter, option, index)

    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        if index.column() == 1:
            dark = self.is_dark_mode() if callable(self.is_dark_mode) else True
            color = "#94a3b8" if dark else "#64748b"
            option.icon = IconManager.get_vector_icon("file", color, 16)
            option.decorationSize = QSize(16, 16)
            option.features |= QStyleOptionViewItem.HasDecoration
