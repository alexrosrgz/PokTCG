"""Damage calculation pipeline for 1999 rules."""

from poktcg.cards.card_db import get_card_db
from poktcg.engine.state import PokemonSlot


def calculate_damage(
    attacker: PokemonSlot,
    defender: PokemonSlot,
    base_damage: int,
) -> int:
    """Calculate final damage using 1999 rules.

    Order: base → PlusPower (+10 each) → Weakness (×2) → Resistance (-30) → Defender (-20 each)
    """
    db = get_card_db()
    damage = base_damage

    if damage <= 0:
        return 0

    # Add PlusPower bonuses
    damage += attacker.pluspower_count * 10

    # Apply weakness (×2 in 1999)
    attacker_card = db.get(attacker.card_id)
    defender_card = db.get(defender.card_id)

    attacker_types = set(attacker_card.types)
    for weakness in defender_card.weaknesses:
        if weakness.energy_type in attacker_types:
            damage *= 2
            break  # Only apply once

    # Apply resistance (-30 in 1999)
    for resistance in defender_card.resistances:
        if resistance.energy_type in attacker_types:
            damage -= 30
            break

    # Apply Defender trainer (-20 each)
    damage -= defender.defender_count * 20

    return max(0, damage)
