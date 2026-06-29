"""Game/profile state controller for the Qt UI.

Thin wrapper over the real (toolkit-neutral) helpers in gui.game_helpers and
Games.base_game so the Qt app drives the same load flow as the Tk app:
discover games, list profiles, switch the active game/profile, and resolve the
active modlist.txt + staging dir.
"""

from __future__ import annotations

from pathlib import Path

from gui.game_helpers import (
    _load_games, _profiles_for_game, _load_last_game, _save_last_game, _GAMES,
)


class GameState:
    def __init__(self):
        self.game_names: list[str] = []
        self.game_name: str | None = None
        self.profile: str | None = None

    # -- discovery / load ---------------------------------------------------
    def load(self) -> None:
        """Discover games and select the last-used (or first) game + its default
        profile. Populates game_names / game_name / profile."""
        self.game_names = _load_games()
        last = _load_last_game()
        if last and last in self.game_names:
            self.game_name = last
        elif self.game_names and self.game_names[0] != "No games configured":
            self.game_name = self.game_names[0]
        else:
            self.game_name = None
        self._select_default_profile()
        self._apply_active_profile()

    # -- current handler ----------------------------------------------------
    @property
    def game(self):
        return _GAMES.get(self.game_name) if self.game_name else None

    def profiles(self) -> list[str]:
        return _profiles_for_game(self.game_name) if self.game_name else []

    # -- switching ----------------------------------------------------------
    def set_game(self, name: str) -> None:
        if name == self.game_name or name not in self.game_names:
            return
        self.game_name = name
        _save_last_game(name)
        self._select_default_profile()
        self._apply_active_profile()

    def set_profile(self, profile: str) -> None:
        if profile == self.profile:
            return
        self.profile = profile
        self._apply_active_profile()

    # -- resolved paths -----------------------------------------------------
    def modlist_path(self) -> Path | None:
        g = self.game
        if g is None or not self.profile:
            return None
        return g.get_profile_root() / "profiles" / self.profile / "modlist.txt"

    def profile_dir(self) -> Path | None:
        """Active profile dir — where per-profile state (collapsed separators,
        separator locks, etc.) is stored."""
        g = self.game
        if g is None or not self.profile:
            return None
        return g.get_profile_root() / "profiles" / self.profile

    def staging_dir(self) -> Path | None:
        g = self.game
        if g is None:
            return None
        try:
            p = g.get_effective_mod_staging_path()
            return p if p.is_dir() else None
        except Exception:
            return None

    def build_conflicts(self, log_fn=None) -> dict[str, int]:
        """Build the filemap for the active game/profile and return per-mod
        conflict codes (1 win / -1 lose / 2 mixed). Expensive — run off-thread.
        Returns {} if no game/profile or on failure."""
        g = self.game
        if g is None or not self.profile:
            return {}
        from Utils.deploy_pipeline import _build_filemap_for_game
        from gui_qt.modlist_data import conflicts_from_filemap
        log = log_fn or (lambda _m: None)
        result = _build_filemap_for_game(g, self.profile, log_fn=log)
        if not result:
            return {}
        _count, _conflict_map, overrides, overridden_by = result
        return conflicts_from_filemap(overrides, overridden_by)

    # -- internals ----------------------------------------------------------
    def _select_default_profile(self) -> None:
        profs = self.profiles()
        self.profile = profs[0] if profs else None

    def _apply_active_profile(self) -> None:
        g = self.game
        if g is not None and self.profile:
            g.set_active_profile_dir(
                g.get_profile_root() / "profiles" / self.profile)
