"""Results analysis and reporting."""

from __future__ import annotations

from poktcg.cards.card_db import get_card_db
from poktcg.optimizer.deck import Deck
from poktcg.optimizer.simulator import Simulator


def matchup_table(decks: list[Deck], names: list[str],
                   games_per_pair: int = 50) -> str:
    """Generate a matchup table between decks."""
    sim = Simulator(num_workers=1)
    n = len(decks)
    win_rates = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                win_rates[i][j] = 0.5
                continue
            if i < j:
                result = sim.evaluate_matchup(decks[i], decks[j], games_per_pair)
                win_rates[i][j] = result.win_rate
                win_rates[j][i] = 1 - result.win_rate

    # Format table
    max_name = max(len(n) for n in names)
    header = " " * (max_name + 2) + "  ".join(f"{n[:8]:>8}" for n in names)
    lines = [header]
    for i in range(n):
        row = f"{names[i]:<{max_name}}  "
        row += "  ".join(f"{win_rates[i][j]*100:>7.1f}%" for j in range(n))
        avg = sum(win_rates[i][j] for j in range(n) if j != i) / max(1, n - 1)
        row += f"  avg:{avg*100:.1f}%"
        lines.append(row)

    return "\n".join(lines)


def deck_report(deck: Deck, name: str = "Deck") -> str:
    """Generate a detailed deck report."""
    db = get_card_db()
    lines = [f"=== {name} ===", deck.summary()]

    # Type analysis
    types = {}
    for cid, count in deck.cards.items():
        card = db.get(cid)
        if card.is_pokemon:
            for t in card.types:
                types[t] = types.get(t, 0) + count

    if types:
        lines.append(f"\nType distribution: {types}")

    # Energy analysis
    energy_types = {}
    for cid, count in deck.cards.items():
        card = db.get(cid)
        if card.is_energy:
            energy_types[card.name] = count

    if energy_types:
        lines.append(f"Energy: {energy_types}")

    return "\n".join(lines)
