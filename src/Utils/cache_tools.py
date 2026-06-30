"""Neutral (toolkit-free) cache helpers for the download cache + orphaned temp
dirs.

The Tk Settings panel (``gui/status_bar.py``) grew these as private helpers, but
that module imports customtkinter so the Qt port can't reuse them. This module
holds the same logic with no GUI dependency, so both the Tk app and the Qt
Settings tab can call it.

The download cache stores extracted/queued mod archives under
``get_download_cache_dir()`` (honours ``[paths] download_cache_path``). Aborted
extractions can leave ``modmgr_*`` temp dirs scattered across every game's
staging path — :func:`orphaned_tmp_dirs` finds them and
:func:`clear_download_cache` removes both.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from Utils.config_paths import (
    get_config_dir, get_download_cache_dir, get_profiles_dir,
)


def format_size(n_bytes: int) -> str:
    """Human-readable byte count ("12.3 MB"); "—" for empty/unknown."""
    if n_bytes <= 0:
        return "—"
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n_bytes >= threshold:
            return f"{n_bytes / threshold:.1f} {unit}"
    return f"{n_bytes} B"


def dir_size(path: Path) -> int:
    """Total size in bytes of every regular file under *path* (0 if missing)."""
    if not path.is_dir():
        return 0
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def orphaned_tmp_dirs() -> list[Path]:
    """Orphaned ``modmgr_*`` temp dirs across all known staging paths.

    Collects staging roots from every game's ``paths.json`` plus the env-var
    profiles dir, then returns the ``modmgr_*`` directories found under them.
    """
    found: list[Path] = []
    search_roots: list[Path] = []

    try:
        games_dir = get_config_dir() / "games"
        for paths_json in games_dir.rglob("paths.json"):
            try:
                data = json.loads(paths_json.read_text(encoding="utf-8"))
                sp = data.get("staging_path", "")
                if sp:
                    search_roots.append(Path(sp))
            except Exception:
                pass
    except Exception:
        pass

    try:
        search_roots.append(get_profiles_dir())
    except Exception:
        pass

    seen: set[Path] = set()
    for root in search_roots:
        if root in seen or not root.is_dir():
            continue
        seen.add(root)
        try:
            for tmp_dir in root.rglob("modmgr_*"):
                if tmp_dir.is_dir():
                    found.append(tmp_dir)
        except Exception:
            pass
    return found


def total_cache_size() -> int:
    """Size of the download cache plus every orphaned ``modmgr_*`` temp dir."""
    return dir_size(get_download_cache_dir()) + sum(
        dir_size(d) for d in orphaned_tmp_dirs())


def clear_download_cache() -> int:
    """Delete the download cache contents + orphaned temp dirs.

    Removes the *contents* of the cache root (keeping the root itself so the
    path stays valid) and every ``modmgr_*`` orphan dir. Returns the number of
    top-level entries removed. Best-effort — individual failures are skipped.
    """
    removed = 0
    cache_root = get_download_cache_dir()
    try:
        for entry in cache_root.iterdir():
            try:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
                removed += 1
            except OSError:
                pass
    except OSError:
        pass
    for orphan in orphaned_tmp_dirs():
        try:
            shutil.rmtree(orphan, ignore_errors=True)
            removed += 1
        except OSError:
            pass
    return removed
