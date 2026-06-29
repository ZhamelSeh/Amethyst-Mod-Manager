"""Real modlist metadata (versions / installed dates / flags from meta.ini, and
conflicts from filemap overrides). Pure backend calls — no Qt, no gui.* — so
they can run on a worker thread.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from Utils.modlist import ModEntry


# Flag bits for the Flags column — only the ones the Tk app shows there.
# (FOMOD/BAIN are install methods, NOT flag icons; note.png = a real saved
#  user note, not FOMOD. brush = xedit-modified — both wired in a later pass.)
FLAG_UPDATE = 1 << 0       # has_update & not ignored
FLAG_ENDORSED = 1 << 1
FLAG_ROOT = 1 << 2


def read_meta_for_entries(entries: list[ModEntry], staging_dir: Path):
    """Return (versions, installed, flags) dicts keyed by mod name.

    versions[name]  -> version string ("" if none)
    installed[name] -> short date string ("" if none)
    flags[name]     -> int bitmask of FLAG_* above
    """
    versions: dict[str, str] = {}
    installed: dict[str, str] = {}
    flags: dict[str, int] = {}

    try:
        from Nexus.nexus_meta import read_meta
    except Exception:
        return versions, installed, flags

    for e in entries:
        if e.is_separator:
            continue
        meta_path = staging_dir / e.name / "meta.ini"
        if not meta_path.is_file():
            continue
        try:
            meta = read_meta(meta_path)
        except Exception:
            continue

        if meta.version:
            versions[e.name] = meta.version

        if meta.installed:
            try:
                installed[e.name] = datetime.fromisoformat(
                    meta.installed).strftime("%Y-%m-%d")
            except Exception:
                installed[e.name] = meta.installed[:10]

        bits = 0
        if meta.has_update and meta.latest_version != meta.ignored_version:
            bits |= FLAG_UPDATE
        if meta.endorsed:
            bits |= FLAG_ENDORSED
        if meta.root_folder:
            bits |= FLAG_ROOT
        if bits:
            flags[e.name] = bits

    return versions, installed, flags


def conflicts_from_filemap(overrides: dict, overridden_by: dict):
    """Map the filemap's override data to per-mod conflict codes.

    overrides[mod]      -> set/list of mods this mod overrides (it wins)
    overridden_by[mod]  -> set/list of mods that override this one (it loses)
    Returns {mod_name: code} where 1=wins, -1=loses, 2=both.
    """
    codes: dict[str, int] = {}
    wins = {m for m, v in (overrides or {}).items() if v}
    loses = {m for m, v in (overridden_by or {}).items() if v}
    for m in wins | loses:
        if m in wins and m in loses:
            codes[m] = 2
        elif m in wins:
            codes[m] = 1
        else:
            codes[m] = -1
    return codes
