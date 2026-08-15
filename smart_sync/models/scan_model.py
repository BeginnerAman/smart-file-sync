from __future__ import annotations
from typing import Any
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QObject
from PySide6.QtGui import QColor

class ScanResultsModel(QAbstractTableModel):
    """Table Model for fast, virtualized scan results presentation"""
    HEADERS = ["", "File Name", "Size", "Relative Path", "Modified", "Status"]

    def __init__(self, data: list[dict] | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data = data or []
        self.checked_rows = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any | None:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any | None:
        if not index.isValid() or index.row() >= len(self._data):
            return None
            
        row = index.row()
        col = index.column()
        item = self._data[row]

        if role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if row in self.checked_rows else Qt.Unchecked

        if role == Qt.DisplayRole:
            if col == 1:
                return item.get("filename", "")
            elif col == 2:
                return item.get("size_str", "")
            elif col == 3:
                return item.get("rel_path", "")
            elif col == 4:
                return item.get("modified_str", "")
            elif col == 5:
                return item.get("reason", "Missing")

        if role == Qt.TextAlignmentRole:
            if col in (0, 2, 4, 5):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.UserRole:
            return item

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            row = index.row()
            if value == Qt.Checked:
                self.checked_rows.add(row)
            else:
                self.checked_rows.discard(row)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        fl = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            fl |= Qt.ItemIsUserCheckable
        return fl

    def update_data(self, new_data: list[dict]) -> None:
        self.beginResetModel()
        self._data = new_data
        self.checked_rows = set(range(len(new_data))) # Check all by default
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._data = []
        self.checked_rows.clear()
        self.endResetModel()

class ScanResultsProxyModel(QSortFilterProxyModel):
    """Proxy model for high-speed client-side filtering and sorting"""
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.search_text = ""
        self.filter_reason = "All Reasons"

    def set_filters(self, text: str | None, reason: str) -> None:
        self.search_text = (text or "").strip().lower()
        self.filter_reason = reason
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model or source_row >= len(model._data):
            return True
            
        item = model._data[source_row]
        
        # Filter by Reason
        if self.filter_reason != "All Reasons":
            reason = item.get("reason", "")
            filter_map = {
                "Missing Only": "Missing",
                "Source Newer": "Source Newer",
                "Destination Newer": "Destination Newer",
                "Destination Only": "Destination Only",
                "Size Differs": "Size Differs",
                "Changed Only": "Modified / Newer",  # Legacy compatibility
            }
            expected = filter_map.get(self.filter_reason)
            if expected and reason != expected:
                return False

        # Filter by Search Text
        if self.search_text:
            fname = item.get("filename", "").lower()
            rel = item.get("rel_path", "").lower()
            if self.search_text not in fname and self.search_text not in rel:
                return False

        return True
