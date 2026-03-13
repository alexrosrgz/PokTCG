"""Abstract player interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from poktcg.engine.state import GameState
from poktcg.engine.actions import Action


class BasePlayer(ABC):
    @abstractmethod
    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        ...

    @abstractmethod
    def choose_active(self, state: GameState, player_idx: int) -> int:
        """Return index in hand of basic Pokémon to place as active."""
        ...

    @abstractmethod
    def choose_bench(self, state: GameState, player_idx: int, basics_in_hand: list[int]) -> list[int]:
        """Return list of hand indices of basics to bench."""
        ...

    @abstractmethod
    def choose_new_active(self, state: GameState, player_idx: int) -> int:
        """Return bench index for new active when current is KO'd."""
        ...
