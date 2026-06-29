"""Modlist model — QAbstractTableModel over the ModEntry list.

Columns: Mod Name, Flags, Conflicts, Installed, Version, Priority (the checkbox
is painted into column 0 by the delegate). Fed by read_modlist; version /
installed / flags / conflicts are optional dicts keyed by mod name (blank when
absent). Index 0 = highest priority; the Priority column shows a descending
number (highest-priority row = largest value).
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QMimeData, QByteArray,
)

from Utils.modlist import ModEntry, read_modlist


# Column indices.
COL_NAME = 0
COL_FLAGS = 1
COL_CONFLICTS = 2
COL_INSTALLED = 3
COL_VERSION = 4
COL_PRIORITY = 5
COLUMNS = ["Mod Name", "Flags", "Conflicts", "Installed", "Version", "Priority"]

# Custom roles for the delegate.
EntryRole = Qt.UserRole + 1        # the ModEntry
ConflictRole = Qt.UserRole + 2     # int: 0 none, 1 wins, -1 loses, 2 mixed
PriorityRole = Qt.UserRole + 3     # int display priority
FlagsRole = Qt.UserRole + 4        # int bitmask (gui_qt.modlist_data.FLAG_*)

_MIME = "application/x-amethyst-modrows"


class ModListModel(QAbstractTableModel):
    def __init__(self, entries: list[ModEntry] | None = None,
                 versions: dict[str, str] | None = None,
                 installed: dict[str, str] | None = None,
                 conflicts: dict[str, int] | None = None):
        super().__init__()
        self._entries: list[ModEntry] = entries or []
        self._versions = versions or {}
        self._installed = installed or {}
        self._conflicts = conflicts or {}
        self._flags: dict[str, int] = {}

    # ---- loading ----------------------------------------------------------
    @classmethod
    def from_modlist(cls, modlist_path, **kw) -> "ModListModel":
        return cls(read_modlist(modlist_path), **kw)

    def set_entries(self, entries: list[ModEntry]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def set_flags(self, flags: dict[str, int]) -> None:
        self._flags = flags or {}
        if self._entries:
            self.dataChanged.emit(self.index(0, COL_FLAGS),
                                  self.index(len(self._entries) - 1, COL_FLAGS),
                                  [FlagsRole, Qt.DisplayRole])

    def set_conflicts(self, conflicts: dict[str, int]) -> None:
        self._conflicts = conflicts or {}
        if self._entries:
            self.dataChanged.emit(self.index(0, COL_NAME),
                                  self.index(len(self._entries) - 1, COL_CONFLICTS),
                                  [ConflictRole, Qt.DisplayRole])

    # ---- Qt model interface ----------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def _priority_for_row(self, row: int) -> int:
        """Descending priority number among non-separator rows (top = highest)."""
        # Count non-separator entries at-or-below this row.
        e = self._entries[row]
        if e.is_separator:
            return -1
        below = sum(1 for x in self._entries[row:] if not x.is_separator)
        return below - 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        col = index.column()

        if role == EntryRole:
            return e
        if role == ConflictRole:
            return 0 if e.is_separator else self._conflicts.get(e.name, 0)
        if role == FlagsRole:
            return 0 if e.is_separator else self._flags.get(e.name, 0)
        if role == PriorityRole:
            return self._priority_for_row(index.row())

        if role == Qt.DisplayRole:
            if e.is_separator:
                return e.display_name if col == COL_NAME else ""
            if col == COL_NAME:
                return e.display_name
            if col == COL_VERSION:
                return self._versions.get(e.name, "")
            if col == COL_INSTALLED:
                return self._installed.get(e.name, "")
            if col == COL_PRIORITY:
                p = self._priority_for_row(index.row())
                return str(p) if p >= 0 else ""
            return ""
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsDropEnabled
        e = self._entries[index.row()]
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        # Locked rows (e.g. Overwrite / Root Folder boundary separators, and
        # locked mods) cannot be dragged. Bundle/locked mods remain selectable.
        if not e.locked:
            f |= Qt.ItemIsDragEnabled
        if not e.is_separator:
            f |= Qt.ItemIsDropEnabled
        return f

    # ---- drop-validity (keep boundary separators pinned) ------------------
    def _movable_span(self) -> tuple[int, int]:
        """[lo, hi) row range mods may live in: below a leading locked
        separator (Overwrite) and above a trailing locked one (Root Folder)."""
        lo, hi = 0, len(self._entries)
        if self._entries and self._entries[0].is_separator and self._entries[0].locked:
            lo = 1
        if (self._entries and self._entries[-1].is_separator
                and self._entries[-1].locked):
            hi = len(self._entries) - 1
        return lo, hi

    def canDropMimeData(self, data, action, row, col, parent):
        if action != Qt.MoveAction or not data.hasFormat(_MIME):
            return False
        dest = row if row != -1 else (parent.row() if parent.isValid()
                                      else len(self._entries))
        lo, hi = self._movable_span()
        return lo <= dest <= hi

    # ---- toggling ---------------------------------------------------------
    def toggle(self, row: int) -> None:
        e = self._entries[row]
        if e.is_separator or e.locked:
            return
        e.enabled = not e.enabled
        idx = self.index(row, COL_NAME)
        self.dataChanged.emit(idx, idx, [EntryRole, Qt.DisplayRole])

    def entry(self, row: int) -> ModEntry:
        return self._entries[row]

    # ---- structural edits (context-menu actions) --------------------------
    def rename(self, row: int, new_name: str) -> None:
        e = self._entries[row]
        if e.locked:
            return
        # Separators keep their suffix so they stay separators on write-out.
        from Utils.modlist import _SEPARATOR_SUFFIX
        e.name = (new_name + _SEPARATOR_SUFFIX) if e.is_separator else new_name
        idx = self.index(row, COL_NAME)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, EntryRole])

    def set_priority(self, row: int, priority: int) -> None:
        """Move a mod so its descending-priority number becomes *priority*.
        Re-positions within the non-separator ordering (clamped)."""
        e = self._entries[row]
        if e.is_separator:
            return
        nonsep = [i for i, x in enumerate(self._entries) if not x.is_separator]
        n = len(nonsep)
        target_from_top = max(0, min(n - 1, n - 1 - priority))
        dest_row = nonsep[target_from_top]
        if dest_row != row:
            self.move_block([row], dest_row if dest_row < row else dest_row + 1)

    def add_separator(self, row: int, name: str, above: bool) -> None:
        from Utils.modlist import _SEPARATOR_SUFFIX
        at = row if above else row + 1
        sep = ModEntry(name + _SEPARATOR_SUFFIX, True, False, True)
        self.beginInsertRows(QModelIndex(), at, at)
        self._entries.insert(at, sep)
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        if self._entries[row].locked:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._entries[row]
        self.endRemoveRows()

    # ---- drag-reorder (beginMoveRows; selection/scroll preserved) ---------
    def supportedDropActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return [_MIME]

    def mimeData(self, indexes):
        rows = sorted({i.row() for i in indexes})
        md = QMimeData()
        md.setData(_MIME, QByteArray(",".join(map(str, rows)).encode()))
        return md

    def dropMimeData(self, data, action, row, col, parent):
        if action != Qt.MoveAction or not data.hasFormat(_MIME):
            return False
        src = [int(x) for x in bytes(data.data(_MIME)).decode().split(",")]
        dest = row if row != -1 else (parent.row() if parent.isValid()
                                      else len(self._entries))
        return self.move_block(src, dest)

    def move_block(self, src_rows: list[int], dest: int) -> bool:
        """Move a contiguous block of rows to *dest* using beginMoveRows so the
        view animates and keeps selection/scroll (unlike a full reset)."""
        if not src_rows:
            return False
        src_rows = sorted(src_rows)
        first, last = src_rows[0], src_rows[-1]
        # Don't move locked rows (boundary separators, locked mods).
        if any(self._entries[r].locked for r in src_rows):
            return False
        # Keep within the movable span (below Overwrite, above Root Folder).
        lo, hi = self._movable_span()
        if first < lo or last >= hi or not (lo <= dest <= hi):
            return False
        # Qt's beginMoveRows requires dest outside the moved range.
        if first <= dest <= last + 1:
            return False
        if not self.beginMoveRows(QModelIndex(), first, last,
                                  QModelIndex(), dest):
            return False
        block = self._entries[first:last + 1]
        del self._entries[first:last + 1]
        insert_at = dest if dest < first else dest - len(block)
        self._entries[insert_at:insert_at] = block
        self.endMoveRows()
        return True
