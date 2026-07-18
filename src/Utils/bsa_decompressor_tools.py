"""
GUI-neutral core of the FNV BSA Decompressor wizard.

The FNV BSA Decompressor (nexusmods.com/newvegas/mods/65854) ships as a .mpi
package that the same native Linux MPI installer used by the TTW wizard can
run (Fallout 3 is not needed). This module holds the pieces the Qt view
shares with ttw_tools: locating the downloaded Nexus archive, pulling the
.mpi out of it and registering the installer's output as a mod.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from Utils.ttw_tools import applications_dir

if TYPE_CHECKING:
    from Games.base_game import BaseGame

NEXUS_URL = "https://www.nexusmods.com/newvegas/mods/65854?tab=files"
OUTPUT_NAME = "FNV BSA Decompressor"
ARCHIVE_KEYWORDS = ["bsa", "decompressor"]


def _noop(_msg: str) -> None:
    pass


def packages_dir(game: "BaseGame") -> Path:
    """Where extracted .mpi packages are kept (next to the installer)."""
    return applications_dir(game) / "packages"


def find_decompressor_archive() -> "Path | None":
    """Newest archive matching the BSA-Decompressor keywords across all
    configured download locations, or None."""
    from Utils.download_locations import get_effective_download_locations
    from Utils.wizard_archives import find_archive

    best: "Path | None" = None
    best_mtime = -1.0
    for directory in get_effective_download_locations():
        hit = find_archive(directory, ARCHIVE_KEYWORDS)
        if hit is None:
            continue
        try:
            mtime = hit.stat().st_mtime
        except OSError:
            continue
        if mtime > best_mtime:
            best, best_mtime = hit, mtime
    return best


def extract_mpi_from_archive(archive: Path, dest_dir: Path,
                             log_fn: Callable[[str], None] = _noop) -> Path:
    """Extract *archive* to a temp dir, move the .mpi inside it into
    *dest_dir* and return its path. An already-extracted .mpi of the same
    name is reused. Raises when the archive holds no .mpi."""
    import shutil
    import tempfile
    from Utils.wizard_archives import extract_to_dir

    tmp = Path(tempfile.mkdtemp())
    try:
        log_fn(f"extracting {archive.name}…")
        extract_to_dir(archive, tmp)
        mpis = sorted(tmp.rglob("*.mpi"))
        if not mpis:
            raise RuntimeError(f"No .mpi package found inside {archive.name}.")
        src = mpis[0]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.is_file() and dest.stat().st_size == src.stat().st_size:
            log_fn(f"reusing already-extracted {dest.name}")
            return dest
        shutil.move(str(src), str(dest))
        log_fn(f"extracted {dest.name} → {dest_dir}")
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def find_extracted_mpi(game: "BaseGame") -> "Path | None":
    """A previously-extracted decompressor .mpi in the packages dir, or None."""
    try:
        hits = sorted(packages_dir(game).glob("*.mpi"))
    except OSError:
        return None
    for p in hits:
        low = p.name.lower()
        if all(kw in low for kw in ARCHIVE_KEYWORDS):
            return p
    return None


def decompressor_mod_dir(game: "BaseGame") -> "Path | None":
    """Path to the already-built decompressor mod in staging, or None (only
    when it actually contains a .bsa, so a stray empty folder doesn't trip
    the already-installed page)."""
    try:
        staging = game.get_effective_mod_staging_path()
    except Exception:
        staging = None
    if staging is None:
        return None
    mod_dir = staging / OUTPUT_NAME
    try:
        if any(mod_dir.glob("*.bsa")):
            return mod_dir
    except OSError:
        pass
    return None


def register_output(game: "BaseGame",
                    log_fn: Callable[[str], None] = _noop) -> None:
    """Register the installer's Data/-rooted output as the decompressor mod
    (normal Data-relative mod, not rootFolder) and index it."""
    from Utils.install_as_mod import index_installed_mod, register_as_mod_neutral
    register_as_mod_neutral(
        game, OUTPUT_NAME, archive=None, log_fn=log_fn, root_folder=False)
    index_installed_mod(game, OUTPUT_NAME, log_fn=log_fn)
