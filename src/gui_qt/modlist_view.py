"""Modlist view — QTreeView + ModListModel + ModRowDelegate.

Internal-move drag-reorder (model.beginMoveRows preserves selection/scroll);
TkStyleHeader owns column resizing; column state persists via column_state.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QTreeView, QAbstractItemView, QHeaderView

from gui_qt.modlist_model import (
    ModListModel, COLUMNS, COL_NAME, COL_PRIORITY, COL_FLAGS, COL_CONFLICTS,
    COL_INSTALLED, COL_VERSION,
)
from gui_qt.modlist_delegate import ModRowDelegate
from gui_qt import column_state
from gui_qt.modlist_header import TkStyleHeader

# Per-column default width + minimum (design px), mirroring the Tk app's
# _layout_columns data_defaults / data_mins. Name auto-fills the leftover.
COL_DEFAULTS = {
    COL_FLAGS: 70, COL_CONFLICTS: 95, COL_INSTALLED: 100,
    COL_VERSION: 90, COL_PRIORITY: 75,
}
COL_MINS = {
    COL_NAME: 120, COL_FLAGS: 60, COL_CONFLICTS: 90, COL_INSTALLED: 90,
    COL_VERSION: 80, COL_PRIORITY: 70,
}
NAME_MIN = COL_MINS[COL_NAME]


class ModListView(QTreeView):
    def __init__(self, model: ModListModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setItemDelegate(ModRowDelegate(self))

        self.setRootIsDecorated(False)        # flat list, not a tree
        self.setUniformRowHeights(False)      # separators are taller
        self.setAlternatingRowColors(False)   # delegate paints zebra itself
        self.setMouseTracking(True)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # Internal drag-reorder.
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

        # Right-click context menu.
        self.staging_dir = None   # set by the window for Open-folder
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        # Separator state persistence (profile dir set by the window on reload).
        self.profile_dir = None
        self.doubleClicked.connect(self._on_double_click)

        self._restoring = True
        self._configure_header()
        self._restore_column_state()
        self._restoring = False

        # Persist on user changes (debounced to coalesce drag-resize bursts).
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_column_state)
        h = self.header()
        # sectionResized is handled by _on_section_resized (which saves);
        # only moves + sort-indicator need a direct save hook here.
        h.sectionMoved.connect(lambda *a: self._schedule_save())
        h.sortIndicatorChanged.connect(lambda *a: self._schedule_save())

    def _configure_header(self):
        # Custom Tk-style header: owns all resizing (boundary drag moves the
        # line between two columns, total constant, no overflow). All sections
        # Fixed so Qt never auto-resizes.
        h = TkStyleHeader(self, COL_MINS, COL_DEFAULTS)
        self.setHeader(h)
        h.setMinimumSectionSize(min(COL_MINS.values()))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # NOTE: live sorting intentionally NOT enabled — the modlist is
        # priority-ordered and the Tk app's column-sort has special semantics.
        for col, w in COL_DEFAULTS.items():
            self.setColumnWidth(col, w)
        self._fitting = False
        h.sectionResized.connect(lambda *a: self._schedule_save())
        h.sectionMoved.connect(lambda *a: self._schedule_save())

    # ---- separator collapse/expand ---------------------------------------
    def load_separator_state(self):
        """Read collapsed/lock state for the active profile into the model and
        apply row hiding. Called by the window after a modlist reload."""
        collapsed, locks = set(), {}
        if self.profile_dir is not None:
            try:
                from Utils.profile_state import (
                    read_collapsed_seps, read_separator_locks)
                collapsed = read_collapsed_seps(self.profile_dir)
                locks = read_separator_locks(self.profile_dir)
            except Exception:
                pass
        self.model().set_separator_state(collapsed, locks)
        self._apply_separator_spanning()
        self.apply_collapse()

    def _apply_separator_spanning(self):
        """Separator rows span all columns so the band + centred name + the
        right-side lock box use the full row width."""
        m = self.model()
        for r in range(m.rowCount()):
            self.setFirstColumnSpanned(r, self.rootIndex(),
                                       m.entry(r).is_separator)

    def apply_collapse(self):
        """Hide rows under collapsed separators (Qt setRowHidden)."""
        hidden = self.model().hidden_rows()
        for r in range(self.model().rowCount()):
            self.setRowHidden(r, self.rootIndex(), r in hidden)

    def _on_double_click(self, index):
        if index.isValid() and self.model().entry(index.row()).is_separator:
            self._toggle_collapse_row(index.row())

    def _toggle_collapse_row(self, row):
        self.model().toggle_collapse(row)
        self.apply_collapse()
        self._save_separator_state()
        self.viewport().update()

    def _toggle_lock_row(self, row):
        self.model().toggle_sep_lock(row)
        self._save_separator_state()
        self.viewport().update()

    def _save_separator_state(self):
        if self.profile_dir is None:
            return
        try:
            from Utils.profile_state import (
                write_collapsed_seps, write_separator_locks)
            m = self.model()
            write_collapsed_seps(self.profile_dir, m._collapsed)
            write_separator_locks(self.profile_dir, m._sep_locks)
        except Exception as exc:
            print(f"[gui_qt] separator state save failed: {exc}", flush=True)

    # ---- fill width: Name absorbs leftover on window resize ---------------
    def showEvent(self, event):
        super().showEvent(event)
        self._fit_name_to_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_name_to_width()

    def _fit_name_to_width(self):
        """Keep the table exactly filling the viewport on window resize.

        Growing window: Name absorbs the extra. Shrinking window: Name gives
        back down to its minimum, then the data columns cascade down to their
        own minimums (so columns never get cut off / overflow the panel)."""
        vp = self.viewport().width()
        if vp <= 0:
            return
        h = self.header()
        others = sum(self.columnWidth(c) for c in range(len(COLUMNS))
                     if c != COL_NAME and not self.isColumnHidden(c))
        target_name = vp - others

        if target_name >= NAME_MIN:
            if target_name != self.columnWidth(COL_NAME):
                h.resizeSection(COL_NAME, target_name)
            return

        # Not enough room even at Name's minimum: pin Name to min, then shrink
        # the data columns (right-to-left) toward their minimums to fit.
        h.resizeSection(COL_NAME, NAME_MIN)
        deficit = (NAME_MIN + others) - vp
        for c in reversed([c for c in range(len(COLUMNS))
                           if c != COL_NAME and not self.isColumnHidden(c)]):
            if deficit <= 0:
                break
            room = self.columnWidth(c) - COL_MINS.get(c, 60)
            if room <= 0:
                continue
            take = min(room, deficit)
            h.resizeSection(c, self.columnWidth(c) - take)
            deficit -= take

    # ---- context menu -----------------------------------------------------
    def _on_context_menu(self, pos):
        from gui_qt.modlist_menu import show_context_menu
        index = self.indexAt(pos)
        if index.isValid():
            show_context_menu(self, self.viewport().mapToGlobal(pos), index)

    # ---- column-state persistence (keyed by logical column name) ----------
    def _schedule_save(self):
        if not self._restoring:
            self._save_timer.start()

    def _save_column_state(self):
        h = self.header()
        widths = {COLUMNS[c]: self.columnWidth(c) for c in range(len(COLUMNS))}
        order = [COLUMNS[h.logicalIndex(v)] for v in range(len(COLUMNS))]
        hidden = {COLUMNS[c] for c in range(len(COLUMNS)) if self.isColumnHidden(c)}
        sc = h.sortIndicatorSection()
        sort_col = COLUMNS[sc] if 0 <= sc < len(COLUMNS) else None
        ascending = h.sortIndicatorOrder() == Qt.AscendingOrder
        column_state.save_state(widths, order, hidden, sort_col, ascending)

    def _restore_column_state(self):
        st = column_state.load_state()
        if not (st["widths"] or st["order"] or st["hidden"] or st["sort_col"]):
            return
        name_to_col = {n: i for i, n in enumerate(COLUMNS)}
        for name, w in st["widths"].items():
            if name in name_to_col and name != "Mod Name":  # name stays stretch
                self.setColumnWidth(name_to_col[name], w)
        for name in st["hidden"]:
            if name in name_to_col:
                self.setColumnHidden(name_to_col[name], True)
        h = self.header()
        for visual, name in enumerate(st["order"]):
            if name in name_to_col:
                cur = h.visualIndex(name_to_col[name])
                if cur != -1 and cur != visual:
                    h.moveSection(cur, visual)
        if st["sort_col"] in name_to_col:
            order = Qt.AscendingOrder if st["ascending"] else Qt.DescendingOrder
            # Set the indicator only (live sort not enabled yet).
            self.header().setSortIndicator(name_to_col[st["sort_col"]], order)
