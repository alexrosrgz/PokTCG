"""Coevolution optimizer with self-play and Hall of Fame."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from poktcg.optimizer.deck import Deck
from poktcg.optimizer.genetic import GeneticOptimizer, OptimizerConfig
from poktcg.optimizer.simulator import Simulator


@dataclass
class CoevolutionConfig(OptimizerConfig):
    hof_size: int = 10
    hof_weight: float = 0.4
    hof_add_interval: int = 3
    games_per_hof_eval: int = 20
    games_per_eval: int = 20
    self_play_opponents: int = 4
    final_tournament_games: int = 50
    diversity_bonus: float = 0.03
    novelty_threshold: float = 0.20


@dataclass
class HallOfFame:
    entries: list[Deck] = field(default_factory=list)
    max_size: int = 10

    def try_add(self, deck: Deck, novelty_threshold: float) -> bool:
        """Add deck if it's novel enough vs existing entries.

        Returns True if the deck was added.
        """
        if not self.entries:
            self.entries.append(deck.clone())
            return True

        # Check novelty against all existing entries
        for entry in self.entries:
            dist = deck_distance(deck, entry)
            if dist < novelty_threshold:
                return False

        self.entries.append(deck.clone())
        self._trim()
        return True

    def _trim(self) -> None:
        """Keep only max_size most recent entries."""
        if len(self.entries) > self.max_size:
            self.entries = self.entries[-self.max_size:]


def deck_distance(a: Deck, b: Deck) -> float:
    """Card-level Jaccard distance between two decks."""
    all_cards = set(a.cards.keys()) | set(b.cards.keys())
    if not all_cards:
        return 0.0
    intersection = 0
    union = 0
    for cid in all_cards:
        ca = a.cards.get(cid, 0)
        cb = b.cards.get(cid, 0)
        intersection += min(ca, cb)
        union += max(ca, cb)
    if union == 0:
        return 0.0
    return 1.0 - intersection / union


class CoevolutionOptimizer(GeneticOptimizer):
    def __init__(self, config: CoevolutionConfig | None = None, seed: int = 42):
        super().__init__(config or CoevolutionConfig(), seed)

    @property
    def coevo_config(self) -> CoevolutionConfig:
        return self.config  # type: ignore[return-value]

    def run(self, seed_decks: list[Deck] | None = None,
            opponent_decks: list[Deck] | None = None,
            verbose: bool = True,
            on_progress: Callable[[dict], None] | None = None) -> list[tuple[Deck, float]]:
        """Run coevolution with self-play and Hall of Fame.

        Args:
            seed_decks: Initial decks to seed population and HoF.
            opponent_decks: Ignored (kept for API compat). Opponents come from
                           self-play + HoF.
            verbose: Print progress.
            on_progress: Optional callback called each generation with
                        {"gen", "total", "best_fitness", "avg_fitness", "hof_size"}

        Returns:
            List of (deck, fitness) sorted by fitness descending,
            from final tournament.
        """
        cfg = self.coevo_config

        # Initialize population
        population: list[Deck] = []
        if seed_decks:
            population.extend([d.clone() for d in seed_decks])
        while len(population) < cfg.population_size:
            population.append(self._random_deck())

        # Initialize Hall of Fame with seed decks
        hof = HallOfFame(max_size=cfg.hof_size)
        if seed_decks:
            for deck in seed_decks:
                hof.try_add(deck, novelty_threshold=0.0)

        best_fitness = 0.0
        best_deck = None
        fitness = [0.0] * len(population)

        total_start = time.time()
        for gen in range(cfg.generations):
            gen_start = time.time()

            # Compute composite fitness
            sp_fitness = self._self_play_fitness(population, gen)
            hof_fitness = self._hof_fitness(population, hof, gen)

            w = cfg.hof_weight
            fitness = [
                (1 - w) * sp + w * hf
                for sp, hf in zip(sp_fitness, hof_fitness)
            ]

            # Add diversity bonus
            fitness = self._diversity_bonus(population, fitness)

            # Track best
            best_idx = max(range(len(population)), key=lambda i: fitness[i])
            if fitness[best_idx] > best_fitness:
                best_fitness = fitness[best_idx]
                best_deck = population[best_idx].clone()

            # HoF update
            hof_added = False
            if (gen + 1) % cfg.hof_add_interval == 0:
                champion = population[best_idx]
                hof_added = hof.try_add(champion, cfg.novelty_threshold)
                if verbose and hof_added:
                    print(f"  -> HoF entry added (total: {len(hof.entries)})")
                if on_progress and hof_added:
                    on_progress({
                        "event": "hof",
                        "message": f"HoF entry added (total: {len(hof.entries)})",
                    })

            elapsed = time.time() - gen_start
            avg = sum(fitness) / len(fitness)
            if verbose:
                print(f"Gen {gen+1}/{cfg.generations}: "
                      f"best={fitness[best_idx]:.3f} avg={avg:.3f} "
                      f"hof={len(hof.entries)} ({elapsed:.1f}s)")

            if on_progress:
                on_progress({
                    "gen": gen + 1,
                    "total": cfg.generations,
                    "best_fitness": fitness[best_idx],
                    "avg_fitness": avg,
                    "hof_size": len(hof.entries),
                })

            # Create next generation
            elite_count = max(1, int(cfg.population_size * cfg.elite_ratio))
            ranked = sorted(range(len(population)),
                            key=lambda i: fitness[i], reverse=True)

            new_pop: list[Deck] = []
            for i in ranked[:elite_count]:
                new_pop.append(population[i].clone())

            while len(new_pop) < cfg.population_size:
                parent_a = self._tournament_select(population, fitness)
                parent_b = self._tournament_select(population, fitness)
                child = self._crossover(parent_a, parent_b)

                if self.rng.random() < cfg.mutation_rate:
                    child = self._mutate(child)

                child = self._repair(child)
                valid, _ = child.validate()
                if valid:
                    new_pop.append(child)

            population = new_pop

        total_elapsed = time.time() - total_start
        if verbose:
            print(f"\nEvolution complete in {total_elapsed/60:.1f} minutes")

        # Final tournament
        if verbose:
            print("\n=== Final Tournament ===")
        results = self._final_tournament(population, fitness, hof)

        return results

    def _self_play_fitness(self, population: list[Deck],
                           gen: int) -> list[float]:
        """Sampled self-play matchups within population."""
        cfg = self.coevo_config
        n = len(population)
        wins = [0.0] * n
        games = [0] * n

        # Build all game args for batch execution
        matchups: list[tuple[int, int]] = []
        for i in range(n):
            opponents = self.rng.sample(
                [j for j in range(n) if j != i],
                min(cfg.self_play_opponents, n - 1)
            )
            for j in opponents:
                matchups.append((i, j))

        # Prepare game args: alternate first player for fairness
        game_args = []
        matchup_info: list[tuple[int, int, int]] = []  # (i, j, game_idx)
        for mi, (i, j) in enumerate(matchups):
            a_list = population[i].to_list()
            b_list = population[j].to_list()
            for g in range(cfg.games_per_eval):
                seed = gen * 1000000 + mi * 10000 + g
                if g % 2 == 0:
                    game_args.append((a_list, b_list, seed))
                else:
                    game_args.append((b_list, a_list, seed))
                matchup_info.append((i, j, g))

        # Run all games in one batch
        results = self.sim.batch_games(game_args)

        # Tally results
        for (i, j, g), (winner, _turns, _reason) in zip(matchup_info, results):
            if g % 2 == 0:
                if winner == 0:
                    wins[i] += 1
                else:
                    wins[j] += 1
            else:
                if winner == 1:
                    wins[i] += 1
                else:
                    wins[j] += 1
            games[i] += 1
            games[j] += 1

        return [wins[i] / max(1, games[i]) for i in range(n)]

    def _hof_fitness(self, population: list[Deck],
                     hof: HallOfFame, gen: int) -> list[float]:
        """Evaluate population against Hall of Fame entries."""
        if not hof.entries:
            return [0.5] * len(population)

        cfg = self.coevo_config
        n = len(population)
        h = len(hof.entries)

        # Build all game args
        game_args = []
        matchup_info: list[tuple[int, int]] = []  # (pop_idx, game_within)

        for i in range(n):
            a_list = population[i].to_list()
            for hi, hof_deck in enumerate(hof.entries):
                b_list = hof_deck.to_list()
                for g in range(cfg.games_per_hof_eval):
                    seed = gen * 2000000 + i * 100000 + hi * 1000 + g
                    if g % 2 == 0:
                        game_args.append((a_list, b_list, seed))
                    else:
                        game_args.append((b_list, a_list, seed))
                    matchup_info.append((i, g))

        results = self.sim.batch_games(game_args)

        # Tally
        wins = [0] * n
        total = [0] * n
        for (i, g), (winner, _turns, _reason) in zip(matchup_info, results):
            if g % 2 == 0:
                if winner == 0:
                    wins[i] += 1
            else:
                if winner == 1:
                    wins[i] += 1
            total[i] += 1

        return [wins[i] / max(1, total[i]) for i in range(n)]

    def _diversity_bonus(self, population: list[Deck],
                         fitness: list[float]) -> list[float]:
        """Add small bonus for structural novelty vs top-5 decks."""
        cfg = self.coevo_config
        n = len(population)
        result = list(fitness)

        # Find top-5 indices
        top5 = sorted(range(n), key=lambda i: fitness[i], reverse=True)[:5]

        for i in range(n):
            if i in top5:
                continue
            # Average distance to top-5
            avg_dist = sum(deck_distance(population[i], population[t])
                           for t in top5) / len(top5)
            # Bonus scales linearly: max bonus at distance >= 0.5
            bonus = min(avg_dist / 0.5, 1.0) * cfg.diversity_bonus
            result[i] += bonus

        return result

    def _final_tournament(self, population: list[Deck],
                          fitness: list[float],
                          hof: HallOfFame) -> list[tuple[Deck, float]]:
        """Top 8 from population + all HoF entries in full round-robin."""
        cfg = self.coevo_config

        # Select top 8 from population
        ranked = sorted(range(len(population)),
                        key=lambda i: fitness[i], reverse=True)
        top_decks = [population[i].clone() for i in ranked[:8]]
        names = [f"Pop#{i+1}" for i in range(len(top_decks))]

        # Add HoF entries (deduplicate if a pop deck is already in HoF)
        for hi, hof_deck in enumerate(hof.entries):
            is_dup = any(deck_distance(hof_deck, td) < 0.05 for td in top_decks)
            if not is_dup:
                top_decks.append(hof_deck.clone())
                names.append(f"HoF#{hi+1}")

        n = len(top_decks)
        if n < 2:
            return [(top_decks[0], 1.0)] if top_decks else []

        # Build all game args for round-robin
        game_args = []
        matchup_info: list[tuple[int, int, int]] = []  # (i, j, game_within)

        for i in range(n):
            a_list = top_decks[i].to_list()
            for j in range(i + 1, n):
                b_list = top_decks[j].to_list()
                for g in range(cfg.final_tournament_games):
                    seed = 9000000 + i * 100000 + j * 1000 + g
                    if g % 2 == 0:
                        game_args.append((a_list, b_list, seed))
                    else:
                        game_args.append((b_list, a_list, seed))
                    matchup_info.append((i, j, g))

        results = self.sim.batch_games(game_args)

        # Tally
        wins = [0] * n
        total = [0] * n
        for (i, j, g), (winner, _turns, _reason) in zip(matchup_info, results):
            if g % 2 == 0:
                if winner == 0:
                    wins[i] += 1
                else:
                    wins[j] += 1
            else:
                if winner == 1:
                    wins[i] += 1
                else:
                    wins[j] += 1
            total[i] += 1
            total[j] += 1

        # Print results
        for i in range(n):
            wr = wins[i] / max(1, total[i])
            print(f"  {names[i]}: {wr*100:.1f}% ({wins[i]}W/{total[i]}G)")

        # Return sorted results
        rated = [(top_decks[i], wins[i] / max(1, total[i])) for i in range(n)]
        rated.sort(key=lambda x: x[1], reverse=True)
        return rated
