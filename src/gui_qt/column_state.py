"""Modlist column-state persistence: widths/order/hidden/sort saved to a
``[qt_columns]`` section of amethyst.ini, keyed by column NAME (not index) so it
never collides with the Tk app's index-based ``[columns]`` section.
"""

from __future__ import annotations

import configparser

from Utils.ui_config import get_ui_config_path
from Utils.atomic_write import write_atomic_text

_SECTION = "qt_columns"


def _make_parser():
    parser = configparser.ConfigParser()
    parser.optionxform = str   # preserve key case (column names are case-sensitive)
    return parser


def _read():
    path = get_ui_config_path()
    parser = _make_parser()
    if path.is_file():
        try:
            parser.read(path)
        except Exception:
            pass
    return parser


def _write(parser):
    import io
    buf = io.StringIO()
    parser.write(buf)
    try:
        write_atomic_text(get_ui_config_path(), buf.getvalue())
    except Exception:
        pass


def save_state(widths: dict[str, int], order: list[str],
               hidden: set[str], sort_col: str | None, ascending: bool) -> None:
    parser = _read()
    if not parser.has_section(_SECTION):
        parser.add_section(_SECTION)
    sec = parser[_SECTION]
    for name, w in widths.items():
        sec[f"w_{name}"] = str(int(w))
    sec["order"] = ",".join(order)
    sec["hidden"] = ",".join(sorted(hidden))
    sec["sort_col"] = sort_col or ""
    sec["sort_asc"] = "1" if ascending else "0"
    _write(parser)


def load_state():
    """Return dict(widths, order, hidden, sort_col, ascending) or empty defaults."""
    parser = _read()
    out = {"widths": {}, "order": [], "hidden": set(),
           "sort_col": None, "ascending": True}
    if not parser.has_section(_SECTION):
        return out
    sec = parser[_SECTION]
    for key, val in sec.items():
        if key.startswith("w_"):
            try:
                out["widths"][key[2:]] = int(val)
            except ValueError:
                pass
    if sec.get("order"):
        out["order"] = [s for s in sec["order"].split(",") if s]
    if sec.get("hidden"):
        out["hidden"] = {s for s in sec["hidden"].split(",") if s}
    out["sort_col"] = sec.get("sort_col") or None
    out["ascending"] = sec.get("sort_asc", "1") != "0"
    return out
