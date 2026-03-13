"""Genetic algorithm deck optimizer."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from poktcg.cards.card_db import get_card_db
from poktcg.optimizer.deck import Deck
from poktcg.optimizer.simulator import Simulator


@dataclass
class OptimizerConfig:
    population_size: int = 50
    generations: int = 100
    games_per_eval: int = 30
    mutation_rate: float = 0.3
    elite_ratio: float = 0.1
    tournament_size: int = 5
    num_workers: int = 1  # For simulation parallelism


class GeneticOptimizer:
    def __init__(self, config: OptimizerConfig | None = None, seed: int = 42):
        self.config = config or OptimizerConfig()
        self.rng = random.Random(seed)
        self.db = get_card_db()
        self.sim = Simulator(num_workers=self.config.num_workers)

        # Pre-compute available cards by category
        self._basic_pokemon = [c.id for c in self.db.all_basic_pokemon()]
        self._stage1_pokemon = [c.id for c in self.db.all_pokemon() if c.is_stage1]
        self._stage2_pokemon = [c.id for c in self.db.all_pokemon() if c.is_stage2]
        self._trainers = [c.id for c in self.db.all_trainers()]
        self._basic_energy = [c.id for c in self.db.all_energy() if c.is_basic_energy]
        self._all_pokemon = [c.id for c in self.db.all_pokemon()]

    def run(self, seed_decks: list[Deck] | None = None,
            opponent_decks: list[Deck] | None = None,
            verbose: bool = True,
            on_progress: Callable[[dict], None] | None = None) -> list[tuple[Deck, float]]:
        """Run the genetic algorithm.

        Args:
            seed_decks: Initial decks to include in population
            opponent_decks: Fixed opponent field to evaluate against.
                          If None, evaluates within population (round-robin).
            verbose: Print progress
            on_progress: Optional callback called each generation with
                        {"gen", "total", "best_fitness", "avg_fitness"}

        Returns:
            List of (deck, fitness) sorted by fitness descending
        """
        cfg = self.config

        # Initialize population
        population = []
        if seed_decks:
            population.extend([d.clone() for d in seed_decks])
        while len(population) < cfg.population_size:
            population.append(self._random_deck())

        best_fitness = 0.0
        best_deck = None

        for gen in range(cfg.generations):
            start = time.time()

            # Evaluate fitness
            if opponent_decks:
                fitness = self._evaluate_vs_field(population, opponent_decks, gen)
            else:
                fitness = self._evaluate_round_robin(population, gen)

            # Track best
            best_idx = max(range(len(population)), key=lambda i: fitness[i])
            if fitness[best_idx] > best_fitness:
                best_fitness = fitness[best_idx]
                best_deck = population[best_idx].clone()

            elapsed = time.time() - start

            avg = sum(fitness) / len(fitness)
            if verbose:
                print(f"Gen {gen+1}/{cfg.generations}: "
                      f"best={fitness[best_idx]:.3f} avg={avg:.3f} "
                      f"({elapsed:.1f}s)")

            if on_progress:
                on_progress({
                    "gen": gen + 1,
                    "total": cfg.generations,
                    "best_fitness": fitness[best_idx],
                    "avg_fitness": avg,
                })

            # Create next generation
            elite_count = max(1, int(cfg.population_size * cfg.elite_ratio))
            ranked = sorted(range(len(population)), key=lambda i: fitness[i], reverse=True)

            new_pop = []
            # Keep elites
            for i in ranked[:elite_count]:
                new_pop.append(population[i].clone())

            # Fill rest with crossover + mutation
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

        # Final ranking
        results = [(population[i], fitness[i] if i < len(fitness) else 0.0)
                    for i in range(len(population))]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _evaluate_vs_field(self, population: list[Deck],
                            opponents: list[Deck], gen: int) -> list[float]:
        """Evaluate each deck against the opponent field."""
        fitness = []
        for i, deck in enumerate(population):
            wr = self.sim.evaluate_vs_field(
                deck, opponents,
                games_per_matchup=self.config.games_per_eval,
                base_seed=gen * 100000 + i * 1000
            )
            fitness.append(wr)
        return fitness

    def _evaluate_round_robin(self, population: list[Deck], gen: int) -> list[float]:
        """Evaluate by round-robin within population (sample pairs for speed)."""
        n = len(population)
        wins = [0.0] * n
        games = [0] * n

        # Sample pairs instead of full round robin
        num_matchups = min(n * 3, n * (n - 1) // 2)
        pairs = []
        for _ in range(num_matchups):
            i, j = self.rng.sample(range(n), 2)
            pairs.append((i, j))

        for i, j in pairs:
            result = self.sim.evaluate_matchup(
                population[i], population[j],
                num_games=self.config.games_per_eval,
                base_seed=gen * 100000 + i * 1000 + j
            )
            wins[i] += result.win_rate
            wins[j] += 1 - result.win_rate
            games[i] += 1
            games[j] += 1

        return [wins[i] / max(1, games[i]) for i in range(n)]

    def _tournament_select(self, population: list[Deck],
                            fitness: list[float]) -> Deck:
        """Tournament selection."""
        indices = self.rng.sample(range(len(population)),
                                   min(self.config.tournament_size, len(population)))
        best = max(indices, key=lambda i: fitness[i])
        return population[best]

    def _random_deck(self) -> Deck:
        """Generate a random valid 60-card deck."""
        cards: dict[str, int] = {}

        # Pick 3-6 basic Pokemon lines
        num_basics = self.rng.randint(3, 6)
        chosen_basics = self.rng.sample(self._basic_pokemon,
                                         min(num_basics, len(self._basic_pokemon)))

        for basic_id in chosen_basics:
            count = self.rng.randint(2, 4)
            cards[basic_id] = count

        # Maybe add evolutions
        for basic_id in chosen_basics:
            basic_card = self.db.get(basic_id)
            # Find stage 1 evolutions
            stage1s = [cid for cid in self._stage1_pokemon
                       if self.db.get(cid).evolves_from == basic_card.name]
            if stage1s and self.rng.random() < 0.3:
                s1 = self.rng.choice(stage1s)
                cards[s1] = min(cards.get(basic_id, 2), self.rng.randint(1, 3))

        # Add trainers (15-25 cards)
        num_trainers = self.rng.randint(15, 25)
        trainer_pool = list(self._trainers)
        self.rng.shuffle(trainer_pool)
        trainers_added = 0
        for tid in trainer_pool:
            if trainers_added >= num_trainers:
                break
            count = self.rng.randint(1, 4)
            cards[tid] = count
            trainers_added += count

        # Fill rest with energy
        current = sum(cards.values())
        if current < 60:
            # Determine energy types needed
            pokemon_types = set()
            for cid in cards:
                card = self.db.get(cid)
                if card.is_pokemon:
                    pokemon_types.update(card.types)

            matching_energy = [eid for eid in self._basic_energy
                               if any(t in self.db.get(eid).name for t in pokemon_types)]
            if not matching_energy:
                matching_energy = self._basic_energy

            remaining = 60 - current
            per_type = remaining // max(1, len(matching_energy))
            for eid in matching_energy:
                cards[eid] = cards.get(eid, 0) + per_type

        return self._repair(Deck(cards=cards))

    def _crossover(self, parent_a: Deck, parent_b: Deck) -> Deck:
        """Combine two parent decks."""
        child_cards: dict[str, int] = {}

        # Take Pokemon from one parent, trainers from the other
        if self.rng.random() < 0.5:
            pokemon_parent, trainer_parent = parent_a, parent_b
        else:
            pokemon_parent, trainer_parent = parent_b, parent_a

        # Copy Pokemon from pokemon_parent
        for cid, count in pokemon_parent.cards.items():
            if self.db.get(cid).is_pokemon:
                child_cards[cid] = count

        # Copy trainers from trainer_parent
        for cid, count in trainer_parent.cards.items():
            if self.db.get(cid).is_trainer:
                child_cards[cid] = count

        # Mix energy from both
        energy_a = {cid: n for cid, n in parent_a.cards.items() if self.db.get(cid).is_energy}
        energy_b = {cid: n for cid, n in parent_b.cards.items() if self.db.get(cid).is_energy}
        all_energy = set(list(energy_a.keys()) + list(energy_b.keys()))
        for eid in all_energy:
            a_count = energy_a.get(eid, 0)
            b_count = energy_b.get(eid, 0)
            child_cards[eid] = (a_count + b_count) // 2

        return Deck(cards=child_cards)

    def _mutate(self, deck: Deck) -> Deck:
        """Apply random mutation to a deck."""
        cards = dict(deck.cards)

        mutation_type = self.rng.choice(["swap", "adjust_count", "add_remove"])

        if mutation_type == "swap":
            # Replace 1-3 copies of a card with a different card
            non_energy = [cid for cid, n in cards.items()
                          if not self.db.get(cid).is_basic_energy and n > 0]
            if non_energy:
                remove_id = self.rng.choice(non_energy)
                remove_count = self.rng.randint(1, min(3, cards[remove_id]))
                cards[remove_id] -= remove_count
                if cards[remove_id] <= 0:
                    del cards[remove_id]

                # Add a replacement
                card_type = self.db.get(remove_id).supertype
                if card_type == "Pokémon":
                    pool = self._all_pokemon
                else:
                    pool = self._trainers
                new_id = self.rng.choice(pool)
                cards[new_id] = cards.get(new_id, 0) + remove_count

        elif mutation_type == "adjust_count":
            # Change count of a random card by ±1
            non_energy = [cid for cid in cards if not self.db.get(cid).is_basic_energy]
            if non_energy:
                cid = self.rng.choice(non_energy)
                delta = self.rng.choice([-1, 1])
                cards[cid] = cards.get(cid, 0) + delta
                if cards[cid] <= 0:
                    del cards[cid]

        elif mutation_type == "add_remove":
            # Add a new card, remove energy to compensate
            pool = self._all_pokemon + self._trainers
            new_id = self.rng.choice(pool)
            cards[new_id] = cards.get(new_id, 0) + 1

        return Deck(cards=cards)

    def _repair(self, deck: Deck) -> Deck:
        """Fix an invalid deck to make it legal."""
        cards = dict(deck.cards)

        # Remove zero/negative counts
        cards = {k: v for k, v in cards.items() if v > 0}

        # Cap non-basic-energy at 4 copies
        for cid in list(cards.keys()):
            card = self.db.get(cid)
            if not (card.is_energy and card.is_basic_energy):
                cards[cid] = min(4, cards[cid])

        # Ensure at least 1 basic Pokemon
        has_basic = any(
            self.db.get(cid).is_pokemon and self.db.get(cid).is_basic
            for cid in cards
        )
        if not has_basic:
            basic = self.rng.choice(self._basic_pokemon)
            cards[basic] = cards.get(basic, 0) + 2

        # Remove energy that doesn't match any Pokemon type in the deck
        pokemon_types = set()
        for cid in cards:
            c = self.db.get(cid)
            if c.is_pokemon:
                pokemon_types.update(c.types)

        if pokemon_types:
            for cid in list(cards.keys()):
                c = self.db.get(cid)
                if c.is_energy and c.is_basic_energy:
                    if not any(t in c.name for t in pokemon_types):
                        del cards[cid]

        # Adjust total to 60
        total = sum(cards.values())

        if total > 60:
            # Remove excess (prefer removing energy, then trainers)
            excess = total - 60
            energy_ids = [cid for cid in cards if self.db.get(cid).is_energy]
            trainer_ids = [cid for cid in cards if self.db.get(cid).is_trainer]
            remove_order = energy_ids + trainer_ids

            for cid in remove_order:
                while cards.get(cid, 0) > 0 and excess > 0:
                    cards[cid] -= 1
                    excess -= 1
                if cards.get(cid, 0) <= 0:
                    cards.pop(cid, None)
                if excess <= 0:
                    break

            # If still over, remove any
            while sum(cards.values()) > 60:
                removable = [k for k, v in cards.items() if v > 1]
                if removable:
                    cid = self.rng.choice(removable)
                    cards[cid] -= 1
                else:
                    break

        elif total < 60:
            # Add energy to fill
            deficit = 60 - total

            matching = [eid for eid in self._basic_energy
                        if any(t in self.db.get(eid).name for t in pokemon_types)]
            if not matching:
                matching = self._basic_energy

            while deficit > 0 and matching:
                eid = self.rng.choice(matching)
                cards[eid] = cards.get(eid, 0) + 1
                deficit -= 1

        return Deck(cards=cards)
