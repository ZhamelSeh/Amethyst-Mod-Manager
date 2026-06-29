"""Right-click context menu for the modlist. Model-level actions work
(enable/disable, rename, add separator, set priority, open folder, remove);
Nexus/update/endorse items are disabled placeholders pending the Nexus pipeline.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu, QInputDialog
from PySide6.QtGui import QAction

from gui_qt.modlist_model import COL_NAME


def show_context_menu(view, global_pos, index):
    """Build + exec the context menu for *index* at *global_pos*."""
    model = view.model()
    if not index.isValid():
        return
    row = index.row()
    entry = model.entry(row)

    # Selected non-separator rows (for the *selected* bulk actions).
    sel_rows = sorted({i.row() for i in view.selectionModel().selectedRows()
                       or view.selectionModel().selectedIndexes()})
    sel_mods = [r for r in sel_rows if not model.entry(r).is_separator]
    multi = len(sel_mods) > 1

    menu = QMenu(view)

    def act(label, slot, enabled=True):
        a = QAction(label, menu)
        a.triggered.connect(slot)
        a.setEnabled(enabled)
        menu.addAction(a)
        return a

    from gui_qt.modlist_model import _BOUNDARY_NAMES
    if entry.is_separator and entry.name in _BOUNDARY_NAMES:
        return   # Overwrite / Root Folder: no context actions

    if entry.is_separator:
        # Separator-specific actions.
        collapsed = model.is_collapsed(entry.display_name)
        act("Expand" if collapsed else "Collapse",
            lambda: _toggle_collapse(view, model, row))
        locked = model.is_sep_locked(entry.display_name)
        act("Unlock separator" if locked else "Lock separator",
            lambda: _toggle_sep_lock(view, model, row))
        menu.addSeparator()
        act("Rename separator", lambda: _rename(view, model, row))
        act("Add separator above", lambda: _add_separator(view, model, row, True))
        act("Add separator below", lambda: _add_separator(view, model, row, False))
    else:
        # Mod actions.
        if multi:
            act(f"Enable selected ({len(sel_mods)})",
                lambda: _set_enabled(view, model, sel_mods, True))
            act(f"Disable selected ({len(sel_mods)})",
                lambda: _set_enabled(view, model, sel_mods, False))
        else:
            act("Disable" if entry.enabled else "Enable",
                lambda: model.toggle(row), enabled=not entry.locked)
        menu.addSeparator()
        act("Open folder", lambda: _open_folder(view, model, row))
        act("Rename mod", lambda: _rename(view, model, row),
            enabled=not entry.locked)
        act("Set priority…", lambda: _set_priority(view, model, row))
        menu.addSeparator()
        act("Add separator above", lambda: _add_separator(view, model, row, True))
        act("Add separator below", lambda: _add_separator(view, model, row, False))
        menu.addSeparator()
        # Placeholders — need the Nexus / game-load pipelines (not yet wired).
        act("Check Updates", lambda: None, enabled=False)
        act("Endorse Mod", lambda: None, enabled=False)
        act("Open on Nexus", lambda: None, enabled=False)
        menu.addSeparator()
        act("Remove mod", lambda: _remove(view, model, row),
            enabled=not entry.locked)

    menu.exec(global_pos)


# ---- action implementations (model-level; backend ops come later) ---------

def _set_enabled(view, model, rows, state):
    for r in rows:
        e = model.entry(r)
        if not e.is_separator and not e.locked and e.enabled != state:
            model.toggle(r)


def _open_folder(view, model, row):
    """Open the mod's staging folder via the platform opener (Utils.xdg)."""
    name = model.entry(row).name
    staging = getattr(view, "staging_dir", None)
    if staging is None:
        return
    path = staging / name
    try:
        from Utils.xdg import xdg_open
        xdg_open(str(path))
    except Exception:
        pass


def _toggle_collapse(view, model, row):
    view._toggle_collapse_row(row)


def _toggle_sep_lock(view, model, row):
    view._toggle_lock_row(row)


def _rename(view, model, row):
    e = model.entry(row)
    new, ok = QInputDialog.getText(view, "Rename", "New name:",
                                   text=e.display_name)
    if ok and new.strip():
        model.rename(row, new.strip())


def _set_priority(view, model, row):
    cur = model.data(model.index(row, COL_NAME), 0)
    val, ok = QInputDialog.getInt(view, "Set priority",
                                  f"Priority for {cur}:", 0, 0, 99999)
    if ok:
        model.set_priority(row, val)


def _add_separator(view, model, row, above):
    name, ok = QInputDialog.getText(view, "Add separator", "Separator name:")
    if ok and name.strip():
        model.add_separator(row, name.strip(), above)


def _remove(view, model, row):
    from PySide6.QtWidgets import QMessageBox
    e = model.entry(row)
    if QMessageBox.question(view, "Remove mod",
                            f"Remove '{e.display_name}' from the list?") \
            == QMessageBox.Yes:
        model.remove_row(row)
