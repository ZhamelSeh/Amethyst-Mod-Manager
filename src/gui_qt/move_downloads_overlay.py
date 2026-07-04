"""Borderless in-window overlay to move selected download archives between the
*configured* download locations (default Downloads, Mod Manager cache, and any
extra locations) — NOT a native folder browser.

The list of targets comes from ``Utils.downloads_core.get_scan_dirs`` /
``section_label_for_dir`` so it matches the folders the Downloads tab already
scans. Picking a target invokes ``on_pick(Path)`` with the chosen destination.

Modeled on ``gui_qt/confirm_overlay.py`` (dimmed child overlay + centered card).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea,
)

from gui_qt.theme_qt import active_palette, _c
import Utils.downloads_core as dc


class MoveDownloadsOverlay(QWidget):
    CARD_W = 520
    CARD_H = 440

    def __init__(self, host: QWidget, count: int, game_name, on_pick):
        super().__init__(host)
        self._host = host
        self._on_pick = on_pick
        self._done = False
        p = active_palette()

        self.setObjectName("OverlayBackdrop")
        self.setStyleSheet("#OverlayBackdrop { background: rgba(0,0,0,150); }")
        self.setGeometry(host.rect())

        self._card = QFrame(self)
        self._card.setObjectName("MoveDownloadsCard")
        self._card.setStyleSheet(
            f"#MoveDownloadsCard {{ background:{_c(p,'BG_PANEL')};"
            f" border:1px solid {_c(p,'BORDER')}; border-radius:8px; }}"
            f" #LocRow {{ background:{_c(p,'BG_ROW')};"
            f" border:1px solid {_c(p,'BORDER')}; border-radius:6px; }}"
            f" #LocRow:hover {{ border:1px solid {_c(p,'BTN_INFO')}; }}")
        v = QVBoxLayout(self._card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)

        title_lbl = QLabel(self.tr("Move {0} archive(s) to…").format(count))
        title_lbl.setStyleSheet(
            f"color:{_c(p,'TEXT_MAIN')}; font-weight:600; font-size:16px;")
        v.addWidget(title_lbl)

        intro = QLabel(self.tr("Choose a configured download location."))
        intro.setStyleSheet(f"color:{_c(p,'TEXT_DIM')}; font-size:13px;")
        intro.setWordWrap(True)
        v.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)

        any_row = False
        for d in dc.get_scan_dirs(game_name):
            if not d.is_dir():
                continue
            any_row = True
            rows.addWidget(self._loc_row(d, game_name, p))
        rows.addStretch(1)
        if not any_row:
            empty = QLabel(self.tr("No configured download locations."))
            empty.setStyleSheet(f"color:{_c(p,'TEXT_DIM')}; font-size:13px;")
            rows.insertWidget(0, empty)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        cancel = QPushButton(self.tr("Cancel"))
        cancel.setObjectName("FormButton")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(lambda: self._finish(None))
        bar.addWidget(cancel)
        v.addLayout(bar)

        host.installEventFilter(self)
        self._reposition()
        self.show()
        self.raise_()

    @classmethod
    def show_over(cls, host, count, game_name, on_pick):
        top = host.window() if host is not None else None
        return cls(top or host, count, game_name, on_pick)

    # -- rows ---------------------------------------------------------------
    def _loc_row(self, d: Path, game_name, p) -> QWidget:
        label = dc.section_label_for_dir(d, game_name)
        row = QFrame()
        row.setObjectName("LocRow")
        row.setCursor(Qt.PointingHandCursor)
        rv = QVBoxLayout(row)
        rv.setContentsMargins(12, 8, 12, 8)
        rv.setSpacing(2)
        name = QLabel(label)
        name.setStyleSheet(
            f"color:{_c(p,'TEXT_MAIN')}; font-weight:600; font-size:13px;")
        rv.addWidget(name)
        sub = QLabel(str(d))
        sub.setStyleSheet(f"color:{_c(p,'TEXT_DIM')}; font-size:11px;")
        sub.setWordWrap(True)
        rv.addWidget(sub)
        row.mouseReleaseEvent = lambda _e, path=d: self._finish(path)
        return row

    # -- internals ----------------------------------------------------------
    def _reposition(self):
        self.setGeometry(self._host.rect())
        w = min(self.CARD_W, self._host.width() - 40)
        h = min(self.CARD_H, self._host.height() - 40)
        self._card.setFixedSize(max(360, w), max(240, h))
        self._card.move((self.width() - self._card.width()) // 2,
                        (self.height() - self._card.height()) // 2)

    def _finish(self, result):
        if self._done:
            return
        self._done = True
        self._host.removeEventFilter(self)
        cb = self._on_pick
        self.hide()
        self.deleteLater()
        if cb is not None:
            cb(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._finish(None)
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)
