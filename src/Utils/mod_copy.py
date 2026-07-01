"""Copy / move a mod's staging folder to another profile — tkinter-free.

Ported from the Tk ``modlist_panel._copy_mod_to_profile`` / ``_copy_mods_to_profile``
file-work so the Qt (or any) GUI can reuse it. Collision decisions (replace / rename
/ skip) are the CALLER's: pass ``dest_name`` to rename, or pre-delete the existing
folder to replace.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def resolve_target_staging(game, target_profile_dir: Path) -> Path:
    """The staging folder a mod should be copied INTO for *target_profile_dir*:
    the profile's own ``mods/`` when it uses profile-specific mods, else the
    game's shared staging folder."""
    from Utils.profile_state import profile_uses_specific_mods
    if profile_uses_specific_mods(target_profile_dir):
        return target_profile_dir / "mods"
    return game.get_mod_staging_path()


def mod_exists_in_profile(target_staging: Path, name: str) -> bool:
    """True if a mod folder named *name* already exists in *target_staging*."""
    return (target_staging / name).is_dir()


def copy_fomod_choice(src_profile_dir: Path, dst_profile_dir: Path,
                      mod_name: str, dest_name: "str | None" = None) -> None:
    """Copy a mod's saved installer-choice JSON (FOMOD or BAIN) between profiles,
    if present. *dest_name* renames the choice file to match a renamed folder.
    Port of Tk ``_copy_fomod_choice``."""
    out = dest_name or mod_name
    for sub in ("fomod", "bain"):
        src = src_profile_dir / sub / f"{mod_name}.json"
        if not src.is_file():
            continue
        dst_dir = dst_profile_dir / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst_dir / f"{out}.json"))


def copy_mod_to_profile(src_staging: Path, src_profile_dir: Path,
                        target_staging: Path, target_profile_dir: Path,
                        mod_name: str, enabled: bool = True, *,
                        dest_name: "str | None" = None) -> "str | None":
    """Copy the ``<src_staging>/<mod_name>`` folder into *target_staging* (as
    *dest_name* if given), copy its FOMOD/BAIN choice, and register it in the
    target profile's ``modlist.txt`` (prepend = highest priority, dedup by name,
    preserving *enabled*). Returns the staged dest name, or None on failure.

    The caller must resolve collisions first: pass ``dest_name`` to install under
    a new name, or delete the existing folder to replace it. If the dest folder
    already exists (and wasn't handled), the copy fails and returns None."""
    src_folder = Path(src_staging) / mod_name
    if not src_folder.is_dir():
        return None
    out = dest_name or mod_name
    dest_folder = Path(target_staging) / out
    if dest_folder.exists():
        return None
    try:
        dest_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(src_folder), str(dest_folder))
    except Exception:
        return None
    copy_fomod_choice(src_profile_dir, target_profile_dir, mod_name,
                      dest_name=out)
    _register_in_modlist(target_profile_dir / "modlist.txt", out, enabled)
    return out


def _register_in_modlist(target_modlist: Path, name: str, enabled: bool) -> None:
    """Prepend *name* to the target modlist (dedup by name). No-op if already
    present."""
    from Utils.modlist import read_modlist, write_modlist, ModEntry
    try:
        entries = read_modlist(target_modlist) if target_modlist.exists() else []
    except Exception:
        entries = []
    if name in {e.name for e in entries}:
        return
    entries = [ModEntry(name=name, enabled=enabled, locked=False)] + entries
    write_modlist(target_modlist, entries)
