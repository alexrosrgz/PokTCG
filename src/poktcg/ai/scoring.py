"""State evaluation / scoring for AI decision making."""

from __future__ import annotations

from poktcg.cards.card_db import get_card_db
from poktcg.engine.state import GameState, PlayerState, PokemonSlot, SpecialCondition


def score_state(state: GameState, player_idx: int) -> float:
    """Evaluate how good the game state is for the given player.

    Higher score = better position. Designed for comparing states
    after simulating different actions.
    """
    db = get_card_db()
    p = state.players[player_idx]
    opp = state.players[1 - player_idx]
    score = 0.0

    # Win/loss (overwhelming weight)
    if state.winner == player_idx:
        return 100000.0
    if state.winner == 1 - player_idx:
        return -100000.0

    # Prizes taken (most important objective)
    my_prizes_taken = 6 - len(p.prizes)
    opp_prizes_taken = 6 - len(opp.prizes)
    score += my_prizes_taken * 1000
    score -= opp_prizes_taken * 1000

    # Active Pokemon health
    if p.active:
        card = db.get(p.active.card_id)
        remaining_hp = card.hp - p.active.damage
        score += remaining_hp * 0.5
        # Energy on active
        score += len(p.active.attached_energy) * 15
        # Penalty for bad status on own active
        for cond in p.active.conditions:
            if cond == SpecialCondition.PARALYZED:
                score -= 40
            elif cond == SpecialCondition.ASLEEP:
                score -= 30
            elif cond == SpecialCondition.CONFUSED:
                score -= 20
            elif cond == SpecialCondition.POISONED:
                score -= 15
    else:
        score -= 200  # No active is very bad

    # Bench
    score += len(p.bench) * 20
    for slot in p.bench:
        card = db.get(slot.card_id)
        remaining_hp = card.hp - slot.damage
        score += remaining_hp * 0.2
        score += len(slot.attached_energy) * 8

    # Opponent's active damage (good for us)
    if opp.active:
        score += opp.active.damage * 0.3
        for cond in opp.active.conditions:
            score += 10

    # Hand size (cards = options)
    score += len(p.hand) * 3
    score -= len(opp.hand) * 1.5

    # Deck size (running out = bad)
    if len(p.deck) < 5:
        score -= (5 - len(p.deck)) * 20

    # Opponent's bench damage
    for slot in opp.bench:
        score += slot.damage * 0.1

    return score


def evaluate_attack(state: GameState, player_idx: int, attack_index: int) -> float:
    """Quick heuristic score for an attack without simulation."""
    db = get_card_db()
    p = state.players[player_idx]
    opp = state.players[1 - player_idx]

    if not p.active or not opp.active:
        return 0.0

    card = db.get(p.active.card_id)
    if attack_index >= len(card.attacks):
        return 0.0

    attack = card.attacks[attack_index]
    score = 0.0

    # Base damage value
    base_dmg = attack.base_damage
    score += base_dmg * 2

    # Can we KO the defender?
    opp_card = db.get(opp.active.card_id)
    remaining_hp = opp_card.hp - opp.active.damage

    # Apply weakness estimate
    attacker_types = set(card.types)
    for w in opp_card.weaknesses:
        if w.energy_type in attacker_types:
            base_dmg *= 2
            break
    for r in opp_card.resistances:
        if r.energy_type in attacker_types:
            base_dmg = max(0, base_dmg - 30)
            break

    if base_dmg >= remaining_hp:
        score += 500  # KO bonus

    # Penalty if attack has self-damage text
    text = attack.text.lower()
    if "itself" in text or "to self" in text:
        score -= 30
    if "discard" in text and "energy" in text:
        score -= 20

    # Bonus for status effects
    if "paralyze" in text or "paralyz" in text:
        score += 30
    if "asleep" in text:
        score += 20
    if "confus" in text:
        score += 15
    if "poison" in text:
        score += 15

    return score
