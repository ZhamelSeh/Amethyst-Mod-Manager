"""Modlist delegate — paints rows for the QTreeView.

Graduates the spike's painting onto the multi-column model:
  - separator rows: full-width band + bold label
  - Name column: conflict strip, checkbox, lock glyph, elided name
  - other columns: plain text via the base delegate

Colours come from the active palette so themes carry over.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QSize, QEvent
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from gui_qt.theme_qt import active_palette, _c
from gui_qt.icons import icon
from gui_qt.modlist_model import (
    EntryRole, ConflictRole, FlagsRole, COL_NAME, COL_FLAGS,
)
from gui_qt.modlist_data import (
    FLAG_UPDATE, FLAG_ENDORSED, FLAG_FOMOD, FLAG_BAIN, FLAG_ROOT,
)

# Flag bit → icon filename, painted left-to-right in the Flags column.
_FLAG_ICONS = [
    (FLAG_UPDATE, "update.png"),
    (FLAG_ENDORSED, "endorsed.png"),
    (FLAG_ROOT, "root.png"),
    (FLAG_FOMOD, "note.png"),
    (FLAG_BAIN, "tag.png"),
]

# Match the Tk app's row height (ROW_H = 30 at scale 1.0).
ROW_H = 30
SEP_H = 30
CHECK_BOX = 16


class ModRowDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        p = active_palette()
        self.c_sep_bg = QColor(_c(p, "BG_SEP"))
        self.c_sep_text = QColor(_c(p, "TEXT_SEP"))
        self.c_row = QColor(_c(p, "BG_ROW"))
        self.c_row_alt = QColor(_c(p, "BG_ROW_ALT"))
        self.c_sel = QColor(_c(p, "BG_SELECT"))
        self.c_hover = QColor(_c(p, "BG_ROW_HOVER"))
        self.c_text = QColor(_c(p, "TEXT_MAIN"))
        self.c_text_dim = QColor(_c(p, "TEXT_DIM"))
        self.c_text_on_sel = QColor(_c(p, "TEXT_ON_ACCENT"))
        self.c_border = QColor(_c(p, "BORDER"))
        self.c_lock = QColor(_c(p, "TEXT_WARN"))
        self.c_win = QColor(_c(p, "TEXT_OK_BRIGHT"))
        self.c_lose = QColor(_c(p, "TEXT_ERR_BRIGHT"))
        self.c_check = QColor(_c(p, "BTN_SUCCESS"))   # checkbox fill when enabled
        self.c_check_off = QColor(_c(p, "BG_DEEP"))   # checkbox fill when disabled

    def sizeHint(self, opt, index):
        e = index.data(EntryRole)
        h = SEP_H if (e and e.is_separator) else ROW_H
        return QSize(opt.rect.width(), h)

    def paint(self, p, opt, index):
        e = index.data(EntryRole)
        if e is None:
            super().paint(p, opt, index)
            return
        r = opt.rect
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, False)

        # Separator: paint a full band only on the name column; blank elsewhere
        # so the band reads as one strip across the row.
        if e.is_separator:
            p.fillRect(r, self.c_sep_bg)
            if index.column() == COL_NAME:
                f = QFont(); f.setBold(True); p.setFont(f)
                p.setPen(self.c_sep_text)
                p.drawText(r.adjusted(10, 0, -10, 0),
                           Qt.AlignVCenter | Qt.AlignLeft, e.display_name)
            p.restore()
            return

        # Row background.
        selected = bool(opt.state & QStyle.State_Selected)
        if selected:
            p.fillRect(r, self.c_sel)
        elif opt.state & QStyle.State_MouseOver:
            p.fillRect(r, self.c_hover)
        else:
            p.fillRect(r, self.c_row_alt if index.row() % 2 else self.c_row)

        text_color = self.c_text_on_sel if selected else (
            self.c_text if e.enabled else self.c_text_dim)

        if index.column() == COL_NAME:
            self._paint_name(p, r, e, index, text_color)
        elif index.column() == COL_FLAGS:
            self._paint_flags(p, r, index.data(FlagsRole) or 0)
        else:
            # Plain columns: text from the model, dim + right-pad.
            val = index.data(Qt.DisplayRole) or ""
            p.setPen(text_color)
            align = Qt.AlignVCenter | (
                Qt.AlignRight if index.column() in (4, 5) else Qt.AlignLeft)
            pad = QRect(r.left() + 8, r.top(), r.width() - 16, r.height())
            p.drawText(pad, align, str(val))

        p.restore()

    def _paint_name(self, p, r, e, index, text_color):
        x = r.left()

        # Conflict strip (left edge).
        conflict = index.data(ConflictRole) or 0
        cw = 4
        if conflict == 1:
            p.fillRect(QRect(x, r.top(), cw, r.height()), self.c_win)
        elif conflict == -1:
            p.fillRect(QRect(x, r.top(), cw, r.height()), self.c_lose)
        elif conflict == 2:
            half = r.height() // 2
            p.fillRect(QRect(x, r.top(), cw, half), self.c_win)
            p.fillRect(QRect(x, r.top() + half, cw, r.height() - half), self.c_lose)

        # Checkbox (accent fill + white tick when enabled; hollow when not).
        box = QRect(x + 10, r.top() + (r.height() - CHECK_BOX) // 2,
                    CHECK_BOX, CHECK_BOX)
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        p.setPen(QPen(self.c_border, 1))
        p.setBrush(QBrush(self.c_check if e.enabled else self.c_check_off))
        p.drawRoundedRect(box, 3, 3)
        if e.enabled:
            p.setPen(QPen(QColor("white"), 2))
            p.drawLine(box.left() + 4, box.center().y() + 1,
                       box.center().x() - 1, box.bottom() - 4)
            p.drawLine(box.center().x() - 1, box.bottom() - 4,
                       box.right() - 3, box.top() + 4)
        p.setRenderHint(p.RenderHint.Antialiasing, False)

        tx = box.right() + 10

        # Lock glyph.
        if e.locked:
            p.setPen(self.c_lock)
            p.drawText(QRect(tx, r.top(), 16, r.height()),
                       Qt.AlignVCenter, "\U0001F512")
            tx += 18

        # Name (elided).
        p.setPen(text_color)
        p.setFont(QFont())
        name_rect = QRect(tx, r.top(), r.right() - tx - 6, r.height())
        elided = opt_fm(p).elidedText(e.display_name, Qt.ElideRight,
                                      name_rect.width())
        p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

    def _paint_flags(self, p, r, bits):
        if not bits:
            return
        sz = 16
        x = r.left() + 6
        y = r.top() + (r.height() - sz) // 2
        for bit, name in _FLAG_ICONS:
            if bits & bit:
                ic = icon(name, sz)
                if not ic.isNull():
                    ic.paint(p, QRect(x, y, sz, sz))
                    x += sz + 3
                if x > r.right() - sz:
                    break

    def editorEvent(self, event, model, opt, index):
        # Toggle when the checkbox area of the name column is clicked.
        if (event.type() == QEvent.MouseButtonRelease
                and index.column() == COL_NAME):
            box = QRect(opt.rect.left() + 6, opt.rect.top(), 26, opt.rect.height())
            if box.contains(event.position().toPoint()):
                model.toggle(index.row())
                return True
        return False


def opt_fm(painter):
    """Font metrics from the painter's current font (for eliding)."""
    return painter.fontMetrics()
