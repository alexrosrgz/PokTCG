"""Run the deck optimizer to find the best deck."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from poktcg.cards.card_db import get_card_db
from poktcg.optimizer.deck import Deck
from poktcg.optimizer.genetic import GeneticOptimizer, OptimizerConfig
from poktcg.optimizer.simulator import Simulator
from poktcg.optimizer.analysis import matchup_table, deck_report


def find(name):
    db = get_card_db()
    cards = db.find_by_name(name)
    return cards[0].id if cards else None


def make_haymaker() -> Deck:
    """Classic Haymaker deck."""
    cards = {}
    cards[find("Hitmonchan")] = 4
    cards[find("Electabuzz")] = 4
    scyther = find("Scyther")
    if scyther:
        cards[scyther] = 3

    cards[find("Bill")] = 4
    cards[find("Professor Oak")] = 3
    cards[find("Energy Removal")] = 4
    cards[find("Super Energy Removal")] = 2
    cards[find("Gust of Wind")] = 3
    cards[find("PlusPower")] = 4
    cards[find("Switch")] = 2
    cards[find("Computer Search")] = 2

    db = get_card_db()
    fighting = [c for c in db.all_energy() if "Fighting" in c.name][0].id
    lightning = [c for c in db.all_energy() if "Lightning" in c.name][0].id
    grass = [c for c in db.all_energy() if "Grass" in c.name][0].id

    cards[fighting] = 12
    cards[lightning] = 7
    if scyther:
        cards[grass] = 6
    else:
        cards[lightning] = 13

    cards = {k: v for k, v in cards.items() if k and v > 0}
    return Deck(cards=cards)


def make_raindance() -> Deck:
    """Rain Dance (Blastoise) deck."""
    cards = {}
    cards[find("Squirtle")] = 4
    cards[find("Wartortle")] = 1
    cards[find("Blastoise")] = 3
    lapras = find("Lapras")
    if lapras:
        cards[lapras] = 3

    cards[find("Bill")] = 4
    cards[find("Professor Oak")] = 3
    cards[find("Pokémon Breeder")] = 4
    cards[find("Computer Search")] = 3
    cards[find("Energy Retrieval")] = 3
    cards[find("Switch")] = 2
    cards[find("Gust of Wind")] = 2

    db = get_card_db()
    water = [c for c in db.all_energy() if "Water" in c.name][0].id
    cards[water] = 28

    cards = {k: v for k, v in cards.items() if k and v > 0}

    # Adjust to 60
    total = sum(cards.values())
    if total < 60:
        cards[water] += 60 - total
    elif total > 60:
        cards[water] -= total - 60

    return Deck(cards=cards)


def make_damage_swap() -> Deck:
    """Alakazam/Damage Swap control deck."""
    cards = {}
    cards[find("Abra")] = 4
    cards[find("Kadabra")] = 2
    cards[find("Alakazam")] = 3
    chansey = find("Chansey")
    if chansey:
        cards[chansey] = 3

    cards[find("Bill")] = 4
    cards[find("Professor Oak")] = 3
    cards[find("Pokémon Breeder")] = 3
    cards[find("Computer Search")] = 3
    cards[find("Switch")] = 2
    cards[find("Pokémon Center")] = 2
    cards[find("Gust of Wind")] = 2
    mr_mime = find("Mr. Mime")
    if mr_mime:
        cards[mr_mime] = 3

    db = get_card_db()
    psychic = [c for c in db.all_energy() if "Psychic" in c.name][0].id
    colorless_e = [c for c in db.all_energy() if "Colorless" in c.name]

    cards[psychic] = 20

    cards = {k: v for k, v in cards.items() if k and v > 0}
    total = sum(cards.values())
    if total < 60:
        cards[psychic] += 60 - total
    elif total > 60:
        cards[psychic] -= total - 60

    return Deck(cards=cards)


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


if __name__ == "__main__":
    main()
