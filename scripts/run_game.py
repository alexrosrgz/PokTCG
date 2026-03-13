"""Run test games between two Random AIs."""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from poktcg.cards.card_db import get_card_db
from poktcg.ai.random_ai import RandomAI
from poktcg.engine.game import Game


def make_simple_deck(db) -> list[str]:
    """Build a simple 60-card deck from available basic Pokémon + energy."""
    basics = db.all_basic_pokemon()
    # Pick some basic Pokemon
    deck = []

    # Add 4 copies each of a few basics (up to ~20 Pokemon)
    selected = basics[:5]
    for card in selected:
        for _ in range(4):
            deck.append(card.id)

    # Fill rest with basic energy
    energy_cards = [c for c in db.all_energy() if c.is_basic_energy]
    if energy_cards:
        while len(deck) < 60:
            for e in energy_cards:
                if len(deck) >= 60:
                    break
                deck.append(e.id)

    return deck[:60]


def main():
    db = get_card_db()
    print(f"Loaded {len(db)} cards")
    print(f"  Pokemon: {len(db.all_pokemon())}")
    print(f"  Trainers: {len(db.all_trainers())}")
    print(f"  Energy: {len(db.all_energy())}")
    print()

    deck = make_simple_deck(db)
    print(f"Deck size: {len(deck)}")
    print(f"Deck Pokemon: {set(db.get(cid).name for cid in deck if db.get(cid).is_pokemon)}")
    print()

    # Run multiple games
    num_games = 100
    wins = [0, 0]
    reasons = {}
    total_turns = 0
    errors = 0

    start = time.time()
    for i in range(num_games):
        try:
            p0 = RandomAI(seed=i * 2)
            p1 = RandomAI(seed=i * 2 + 1)
            game = Game(p0, p1, deck, deck, seed=i)
            result = game.play()
            wins[result.winner] += 1
            reasons[result.reason] = reasons.get(result.reason, 0) + 1
            total_turns += result.turns
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"Game {i} error: {e}")
                import traceback
                traceback.print_exc()

    elapsed = time.time() - start

    print(f"=== Results ({num_games} games, {elapsed:.2f}s) ===")
    print(f"Player 0 wins: {wins[0]} ({wins[0] / num_games * 100:.1f}%)")
    print(f"Player 1 wins: {wins[1]} ({wins[1] / num_games * 100:.1f}%)")
    print(f"Errors: {errors}")
    print(f"Avg turns: {total_turns / max(1, num_games - errors):.1f}")
    print(f"Win reasons: {reasons}")
    print(f"Speed: {num_games / elapsed:.1f} games/sec")


if __name__ == "__main__":
    main()
