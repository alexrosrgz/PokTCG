"""State evaluation / scoring for AI decision making."""

from __future__ import annotations

from poktcg.cards.card_db import CardData, get_card_db
from poktcg.engine.state import GameState, PlayerState, PokemonSlot, SpecialCondition
from poktcg.engine.actions import _can_pay_energy


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


def estimate_damage(attacker_slot: PokemonSlot, defender_slot: PokemonSlot,
                    attack_index: int) -> int:
    """Estimate damage an attack would do to a specific defender, including
    weakness/resistance and PlusPower/Defender."""
    db = get_card_db()
    attacker_card = db.get(attacker_slot.card_id)
    defender_card = db.get(defender_slot.card_id)

    if attack_index >= len(attacker_card.attacks):
        return 0

    attack = attacker_card.attacks[attack_index]
    damage = attack.base_damage
    if damage <= 0:
        return 0

    # PlusPower
    damage += attacker_slot.pluspower_count * 10

    # Weakness (x2)
    attacker_types = set(attacker_card.types)
    for w in defender_card.weaknesses:
        if w.energy_type in attacker_types:
            damage *= 2
            break

    # Resistance (-30)
    for r in defender_card.resistances:
        if r.energy_type in attacker_types:
            damage -= 30
            break

    # Defender trainer
    damage -= defender_slot.defender_count * 20

    return max(0, damage)


def can_ko(attacker_slot: PokemonSlot, defender_slot: PokemonSlot,
           attack_index: int) -> bool:
    """Check if an attack would KO the defender."""
    db = get_card_db()
    defender_card = db.get(defender_slot.card_id)
    remaining_hp = defender_card.hp - defender_slot.damage
    dmg = estimate_damage(attacker_slot, defender_slot, attack_index)
    return dmg >= remaining_hp


def score_gust_target(state: GameState, player_idx: int, bench_slot: PokemonSlot) -> float:
    """Score how good a Gust of Wind target is. Higher = better to pull in."""
    db = get_card_db()
    p = state.players[player_idx]
    target_card = db.get(bench_slot.card_id)
    remaining_hp = target_card.hp - bench_slot.damage
    score = 0.0

    # Can we KO it? Huge bonus.
    if p.active:
        active_card = db.get(p.active.card_id)
        for i, attack in enumerate(active_card.attacks):
            if _can_pay_energy(p.active, attack.cost, db):
                dmg = estimate_damage(p.active, bench_slot, i)
                if dmg >= remaining_hp:
                    score += 1000  # KO is the best outcome
                else:
                    score += dmg  # Partial credit for damage

    # Prefer pulling in Pokemon with low HP remaining
    score += (200 - remaining_hp)

    # Prefer pulling in Pokemon with high energy investment (waste their setup)
    score += len(bench_slot.attached_energy) * 20

    # Prefer pulling in unevolved basics that are part of evolution lines
    if len(bench_slot.pokemon_stack) == 1:
        card = db.get(bench_slot.card_id)
        # If it's a basic that evolves, KO'ing it ruins their evolution line
        score += 30

    # Prefer pulling in Pokemon with no attacks available (dead weight as active)
    has_attack = False
    for attack in target_card.attacks:
        if _can_pay_energy(bench_slot, attack.cost, db):
            has_attack = True
            break
    if not has_attack:
        score += 50  # They'll be stuck active with nothing to do

    # Penalize pulling in high-HP evolved Pokemon we can't KO
    if remaining_hp > 80 and score < 1000:
        score -= 50

    return score


def score_energy_removal_target(state: GameState, player_idx: int,
                                 opp_slot: PokemonSlot) -> float:
    """Score how valuable removing energy from this slot is."""
    db = get_card_db()
    card = db.get(opp_slot.card_id)
    score = 0.0

    if not opp_slot.attached_energy:
        return -1000  # Can't remove what doesn't exist

    # Check if removing energy would disable their attacks
    for attack in card.attacks:
        if _can_pay_energy(opp_slot, attack.cost, db):
            # They can attack now — would removing 1 energy stop them?
            if len(opp_slot.attached_energy) == len(attack.cost):
                score += 200  # Exact energy — removing one disables the attack
            else:
                score += 50

    # More valuable to remove from active (they need to attack now)
    # This is handled by the caller

    # More valuable if they have few energy (each one matters more)
    if len(opp_slot.attached_energy) <= 2:
        score += 50

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

    # Estimate actual damage
    dmg = estimate_damage(p.active, opp.active, attack_index)
    score += dmg * 2

    # Can we KO the defender?
    opp_card = db.get(opp.active.card_id)
    remaining_hp = opp_card.hp - opp.active.damage
    if dmg >= remaining_hp:
        score += 500  # KO bonus

    # Mr. Mime check: if damage >= 30 and defender is Mr. Mime, it gets blocked
    if opp_card.name == "Mr. Mime" and dmg >= 30:
        # Check if Mr. Mime's power is active (not statused, no Muk)
        mime_blocked = not (opp.active.conditions & {
            SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED
        })
        if mime_blocked:
            score -= dmg * 2 + 100  # Attack is mostly useless

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
