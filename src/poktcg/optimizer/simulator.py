"""Batch simulation runner for deck evaluation."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import multiprocessing as mp

from poktcg.optimizer.deck import Deck


@dataclass
class MatchResult:
    wins: int
    losses: int
    draws: int
    total_turns: int

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self) -> float:
        return self.wins / max(1, self.total)

    @property
    def avg_turns(self) -> float:
        return self.total_turns / max(1, self.total)


def _play_single_game(args: tuple) -> tuple[int, int]:
    """Play a single game. Returns (winner, turns).
    Must be top-level function for multiprocessing pickling.
    """
    deck0_list, deck1_list, seed = args

    # Import inside worker process to avoid pickling issues
    from poktcg.ai.heuristic_ai import HeuristicAI
    from poktcg.engine.game import Game

    p0 = HeuristicAI(seed=seed)
    p1 = HeuristicAI(seed=seed + 10000)
    game = Game(p0, p1, deck0_list, deck1_list, seed=seed)
    result = game.play()
    return result.winner, result.turns


class Simulator:
    def __init__(self, num_workers: int | None = None):
        self.num_workers = num_workers or min(mp.cpu_count(), 8)

    def evaluate_matchup(self, deck_a: Deck, deck_b: Deck,
                          num_games: int = 50, base_seed: int = 0) -> MatchResult:
        """Play deck_a vs deck_b, returns results from deck_a's perspective."""
        a_list = deck_a.to_list()
        b_list = deck_b.to_list()

        # Alternate who goes first each game for fairness
        args = []
        for i in range(num_games):
            seed = base_seed * 10000 + i
            if i % 2 == 0:
                args.append((a_list, b_list, seed))
            else:
                args.append((b_list, a_list, seed))

        # Run games
        results = []
        if self.num_workers <= 1:
            results = [_play_single_game(a) for a in args]
        else:
            with ProcessPoolExecutor(max_workers=self.num_workers) as pool:
                results = list(pool.map(_play_single_game, args))

        wins = 0
        losses = 0
        total_turns = 0
        for i, (winner, turns) in enumerate(results):
            total_turns += turns
            if i % 2 == 0:
                if winner == 0:
                    wins += 1
                else:
                    losses += 1
            else:
                if winner == 1:
                    wins += 1
                else:
                    losses += 1

        return MatchResult(
            wins=wins,
            losses=losses,
            draws=0,
            total_turns=total_turns,
        )

    def evaluate_vs_field(self, deck: Deck, field: list[Deck],
                           games_per_matchup: int = 20,
                           base_seed: int = 0) -> float:
        """Evaluate a deck against a field of opponents. Returns average win rate."""
        total_wins = 0
        total_games = 0
        for i, opp_deck in enumerate(field):
            result = self.evaluate_matchup(deck, opp_deck, games_per_matchup,
                                            base_seed=base_seed + i * 100)
            total_wins += result.wins
            total_games += result.total
        return total_wins / max(1, total_games)

    def batch_games(self, game_args: list[tuple[list[str], list[str], int]]
                     ) -> list[tuple[int, int]]:
        """Play many games in one ProcessPoolExecutor.map call.

        Args:
            game_args: list of (deck0_list, deck1_list, seed) tuples

        Returns:
            list of (winner, turns) tuples in the same order
        """
        if not game_args:
            return []
        if self.num_workers <= 1:
            return [_play_single_game(a) for a in game_args]
        with ProcessPoolExecutor(max_workers=self.num_workers) as pool:
            return list(pool.map(_play_single_game, game_args))

    def round_robin(self, decks: list[Deck], games_per_pair: int = 20,
                     base_seed: int = 0) -> list[tuple[int, float]]:
        """Round-robin tournament. Returns [(deck_index, win_rate)] sorted by win rate."""
        n = len(decks)
        wins = [0] * n
        total = [0] * n

        for i in range(n):
            for j in range(i + 1, n):
                result = self.evaluate_matchup(decks[i], decks[j], games_per_pair,
                                                base_seed=base_seed + i * 1000 + j)
                wins[i] += result.wins
                wins[j] += result.losses
                total[i] += result.total
                total[j] += result.total

        ratings = [(i, wins[i] / max(1, total[i])) for i in range(n)]
        ratings.sort(key=lambda x: x[1], reverse=True)
        return ratings
