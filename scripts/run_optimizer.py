"""Run the deck optimizer to find the best deck."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from poktcg.cards.card_db import get_card_db
from poktcg.optimizer.deck import Deck
from poktcg.optimizer.genetic import GeneticOptimizer, OptimizerConfig
from poktcg.optimizer.coevolution import CoevolutionOptimizer, CoevolutionConfig
from poktcg.optimizer.simulator import Simulator
from poktcg.optimizer.analysis import matchup_table, deck_report
from poktcg.optimizer.archetypes import make_haymaker, make_raindance, make_damage_swap


def main():
    db = get_card_db()
    print(f"Loaded {len(db)} cards")

    # Create seed decks
    haymaker = make_haymaker()
    raindance = make_raindance()
    damage_swap = make_damage_swap()

    seed_decks = [haymaker, raindance, damage_swap]
    seed_names = ["Haymaker", "Raindance", "Damage Swap"]

    # Validate
    for name, deck in zip(seed_names, seed_decks):
        valid, err = deck.validate()
        print(f"{name}: {deck.total_cards()} cards, valid={valid}" +
              (f" ({err})" if err else ""))

    # Quick tournament between seed decks
    print("\n=== Seed Deck Tournament ===")
    sim = Simulator(num_workers=1)
    for i, (name_a, deck_a) in enumerate(zip(seed_names, seed_decks)):
        for j, (name_b, deck_b) in enumerate(zip(seed_names, seed_decks)):
            if i >= j:
                continue
            result = sim.evaluate_matchup(deck_a, deck_b, num_games=100)
            print(f"  {name_a} vs {name_b}: {result.win_rate*100:.1f}% "
                  f"({result.wins}W-{result.losses}L, avg {result.avg_turns:.0f} turns)")

    # Run optimizer
    print("\n=== Running Genetic Optimizer ===")
    config = OptimizerConfig(
        population_size=30,
        generations=20,
        games_per_eval=20,
        mutation_rate=0.3,
        num_workers=1,  # Use single process for stability
    )

    optimizer = GeneticOptimizer(config=config, seed=42)
    start = time.time()
    results = optimizer.run(
        seed_decks=seed_decks,
        opponent_decks=seed_decks,  # Optimize against the known archetypes
        verbose=True,
    )
    elapsed = time.time() - start

    print(f"\nOptimization complete in {elapsed/60:.1f} minutes")
    print(f"\n=== Top 3 Decks ===")
    for i, (deck, fitness) in enumerate(results[:3]):
        print(f"\n--- #{i+1} (win rate: {fitness*100:.1f}%) ---")
        print(deck.summary())

    # Final tournament: top deck vs seed decks
    best_deck = results[0][0]
    print(f"\n=== Best Deck vs Seed Decks ===")
    for name, seed_deck in zip(seed_names, seed_decks):
        result = sim.evaluate_matchup(best_deck, seed_deck, num_games=100)
        print(f"  Best vs {name}: {result.win_rate*100:.1f}%")


def run_coevolution():
    db = get_card_db()
    print(f"Loaded {len(db)} cards")

    # Create seed decks
    haymaker = make_haymaker()
    raindance = make_raindance()
    damage_swap = make_damage_swap()

    seed_decks = [haymaker, raindance, damage_swap]
    seed_names = ["Haymaker", "Raindance", "Damage Swap"]

    # Validate
    for name, deck in zip(seed_names, seed_decks):
        valid, err = deck.validate()
        print(f"{name}: {deck.total_cards()} cards, valid={valid}" +
              (f" ({err})" if err else ""))

    # Run coevolution optimizer
    print("\n=== Running Coevolution Optimizer ===")
    config = CoevolutionConfig(
        population_size=30,
        generations=30,
        games_per_eval=20,
        mutation_rate=0.3,
        elite_ratio=0.1,
        num_workers=6,
        hof_size=10,
        hof_weight=0.4,
        hof_add_interval=3,
        games_per_hof_eval=20,
        self_play_opponents=4,
        final_tournament_games=50,
        diversity_bonus=0.03,
        novelty_threshold=0.20,
    )

    optimizer = CoevolutionOptimizer(config=config, seed=42)
    start = time.time()
    results = optimizer.run(seed_decks=seed_decks, verbose=True)
    elapsed = time.time() - start

    print(f"\nCoevolution complete in {elapsed/60:.1f} minutes")
    print(f"\n=== Top 3 Decks ===")
    for i, (deck, fitness) in enumerate(results[:3]):
        print(f"\n--- #{i+1} (win rate: {fitness*100:.1f}%) ---")
        print(deck.summary())

    # Final matchup table: best coevolved deck vs seed decks
    best_deck = results[0][0]
    sim = Simulator(num_workers=6)
    print(f"\n=== Best Coevolved Deck vs Seed Archetypes ===")
    for name, seed_deck in zip(seed_names, seed_decks):
        result = sim.evaluate_matchup(best_deck, seed_deck, num_games=100)
        print(f"  Best vs {name}: {result.win_rate*100:.1f}%")

    # Full matchup table of top decks + HoF
    top_for_table = [r[0] for r in results[:5]]
    top_names = [f"#{i+1}" for i in range(len(top_for_table))]
    all_decks = top_for_table + seed_decks
    all_names = top_names + seed_names

    print(f"\n=== Full Matchup Table ===")
    print(matchup_table(all_decks, all_names, games_per_pair=50))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--coevolution", action="store_true",
                        help="Run coevolution optimizer instead of genetic")
    args = parser.parse_args()

    if args.coevolution:
        run_coevolution()
    else:
        main()
