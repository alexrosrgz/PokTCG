"""Seeded RNG for deterministic coin flips."""

import random


class GameRNG:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def coin_flip(self) -> bool:
        """Returns True for heads, False for tails."""
        return self._rng.random() < 0.5

    def flip_coins(self, n: int) -> int:
        """Flip n coins, return number of heads."""
        return sum(1 for _ in range(n) if self.coin_flip())

    def shuffle(self, lst: list) -> None:
        """Shuffle a list in place."""
        self._rng.shuffle(lst)

    def choice(self, lst: list):
        """Pick a random element."""
        return self._rng.choice(lst)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def sample(self, lst: list, k: int) -> list:
        return self._rng.sample(lst, k)
