"""Random AI: picks random legal actions."""

from __future__ import annotations

import random

from poktcg.ai.player import BasePlayer
from poktcg.cards.card_db import get_card_db
from poktcg.engine.state import GameState
from poktcg.engine.actions import Action, ActionType


class RandomAI(BasePlayer):
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        # Bias slightly towards non-pass actions
        non_pass = [a for a in legal_actions if a.type != ActionType.PASS_TURN]
        if non_pass and self._rng.random() < 0.8:
            return self._rng.choice(non_pass)
        return self._rng.choice(legal_actions)

    def choose_active(self, state: GameState, player_idx: int) -> int:
        p = state.players[player_idx]
        db = get_card_db()
        basics = [
            i for i, cid in enumerate(p.hand)
            if db.get(cid).is_pokemon and db.get(cid).is_basic
        ]
        return self._rng.choice(basics) if basics else 0

    def choose_bench(self, state: GameState, player_idx: int, basics_in_hand: list[int]) -> list[int]:
        # Randomly bench 0 to all remaining basics
        if not basics_in_hand:
            return []
        n = self._rng.randint(0, len(basics_in_hand))
        return self._rng.sample(basics_in_hand, n)

    def choose_new_active(self, state: GameState, player_idx: int) -> int:
        p = state.players[player_idx]
        if not p.bench:
            return 0
        return self._rng.randint(0, len(p.bench) - 1)
