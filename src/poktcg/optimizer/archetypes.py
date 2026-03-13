"""Seed deck builders for classic archetypes."""

from __future__ import annotations

from poktcg.cards.card_db import get_card_db
from poktcg.optimizer.deck import Deck


def _find(name: str) -> str | None:
    db = get_card_db()
    cards = db.find_by_name(name)
    return cards[0].id if cards else None


def make_haymaker() -> Deck:
    """Classic Haymaker deck."""
    cards = {}
    cards[_find("Hitmonchan")] = 4
    cards[_find("Electabuzz")] = 4
    scyther = _find("Scyther")
    if scyther:
        cards[scyther] = 3

    cards[_find("Bill")] = 4
    cards[_find("Professor Oak")] = 3
    cards[_find("Energy Removal")] = 4
    cards[_find("Super Energy Removal")] = 2
    cards[_find("Gust of Wind")] = 3
    cards[_find("PlusPower")] = 4
    cards[_find("Switch")] = 2
    cards[_find("Computer Search")] = 2

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
    cards[_find("Squirtle")] = 4
    cards[_find("Wartortle")] = 1
    cards[_find("Blastoise")] = 3
    lapras = _find("Lapras")
    if lapras:
        cards[lapras] = 3

    cards[_find("Bill")] = 4
    cards[_find("Professor Oak")] = 3
    cards[_find("Pokémon Breeder")] = 4
    cards[_find("Computer Search")] = 3
    cards[_find("Energy Retrieval")] = 3
    cards[_find("Switch")] = 2
    cards[_find("Gust of Wind")] = 2

    db = get_card_db()
    water = [c for c in db.all_energy() if "Water" in c.name][0].id
    cards[water] = 28

    cards = {k: v for k, v in cards.items() if k and v > 0}

    total = sum(cards.values())
    if total < 60:
        cards[water] += 60 - total
    elif total > 60:
        cards[water] -= total - 60

    return Deck(cards=cards)


def make_damage_swap() -> Deck:
    """Alakazam/Damage Swap control deck."""
    cards = {}
    cards[_find("Abra")] = 4
    cards[_find("Kadabra")] = 2
    cards[_find("Alakazam")] = 3
    chansey = _find("Chansey")
    if chansey:
        cards[chansey] = 3

    cards[_find("Bill")] = 4
    cards[_find("Professor Oak")] = 3
    cards[_find("Pokémon Breeder")] = 3
    cards[_find("Computer Search")] = 3
    cards[_find("Switch")] = 2
    cards[_find("Pokémon Center")] = 2
    cards[_find("Gust of Wind")] = 2
    mr_mime = _find("Mr. Mime")
    if mr_mime:
        cards[mr_mime] = 3

    db = get_card_db()
    psychic = [c for c in db.all_energy() if "Psychic" in c.name][0].id

    cards[psychic] = 20

    cards = {k: v for k, v in cards.items() if k and v > 0}
    total = sum(cards.values())
    if total < 60:
        cards[psychic] += 60 - total
    elif total > 60:
        cards[psychic] -= total - 60

    return Deck(cards=cards)


ARCHETYPE_BUILDERS = {
    "haymaker": make_haymaker,
    "raindance": make_raindance,
    "damage_swap": make_damage_swap,
}

ARCHETYPE_NAMES = {
    "haymaker": "Haymaker",
    "raindance": "Raindance",
    "damage_swap": "Damage Swap",
}
