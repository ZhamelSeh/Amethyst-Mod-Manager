"""SelectorButton — a dropdown that shows the current selection and exposes a
list of choices plus pinned action items at the bottom of the menu.

Used to consolidate the top bar's game and profile controls: one button each,
instead of a +/⚙/combo cluster. Selecting a list item changes the current
choice (fires on_select); the bottom action items fire their own callbacks and
never become the selection.
"""

from __future__ import annotations

from typing import Callable
from PySide6.QtWidgets import QToolButton, QMenu
from PySide6.QtCore import Qt, QSize


class SelectorButton(QToolButton):
    def __init__(self, *, items=None, current=None, actions=None,
                 on_select: "Callable[[str], None] | None" = None,
                 prefix="", min_width=170, icon=None, icon_px=18, parent=None):
        """*items*   — list of selectable labels.
        *current*   — initially selected label (defaults to items[0]).
        *actions*   — list of (label, callback) pinned below a separator.
        *on_select* — called with the chosen label when a list item is picked.
        *prefix*    — text shown before the current label on the button itself
                      (e.g. "Profile: "); not part of the selectable values.
        *icon*      — a QIcon to show INSTEAD of the current-label text (the
                      button becomes an icon button; the menu is unchanged).
        """
        super().__init__(parent)
        self._items: list[str] = list(items or [])
        self._actions = list(actions or [])
        self._on_select = on_select
        self._prefix = prefix
        self._icon = icon
        self._current = current or (self._items[0] if self._items else "")
        self.setObjectName("ActionButton")   # share the flat toolbar styling
        self.setPopupMode(QToolButton.InstantPopup)
        self.setCursor(Qt.PointingHandCursor)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(icon_px, icon_px))
            self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        else:
            self.setToolButtonStyle(Qt.ToolButtonTextOnly)
            self.setMinimumWidth(min_width)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self._rebuild()

    # -- public API ---------------------------------------------------------
    def set_items(self, items, current=None):
        self._items = list(items)
        if current is not None:
            self._current = current
        elif self._current not in self._items and self._items:
            self._current = self._items[0]
        self._rebuild()

    def current(self) -> str:
        return self._current

    def set_current(self, label: str):
        if label in self._items:
            self._current = label
            self._rebuild()

    # -- internals ----------------------------------------------------------
    def _rebuild(self):
        if self._icon is None:
            label = self._current or "—"
            self.setText(f"{self._prefix}{label}  ▾")
        self._menu.clear()
        for label in self._items:
            a = self._menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(label == self._current)
            a.triggered.connect(lambda _=False, l=label: self._choose(l))
        if self._items and self._actions:
            self._menu.addSeparator()
        for label, cb in self._actions:
            a = self._menu.addAction(label)
            if cb is not None:
                a.triggered.connect(lambda _=False, c=cb: c())

    def _choose(self, label):
        if label != self._current:
            self._current = label
            self._rebuild()
            if self._on_select:
                self._on_select(label)
