"""Pokemon Power implementations for Base-Fossil format.

Activated powers: called when the AI chooses USE_POWER action.
  Signature: (game, player_idx, slot_idx) -> bool

Passive powers (before_damage): called before damage is applied to a Pokemon.
  Signature: (game, player_idx, slot_idx, damage, attacker_player_idx) -> int (modified damage)

Passive powers (on_damaged): called after damage is applied.
  Signature: (game, player_idx, slot_idx, damage, attacker_player_idx) -> None
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from poktcg.cards.effects import (
    register_power, power_usable, count_energy_of_type,
)
from poktcg.engine.state import SpecialCondition

if TYPE_CHECKING:
    from poktcg.engine.game import Game


# ============================================================
# ACTIVATED POWERS (player chooses to use during their turn)
# ============================================================

# ---- Blastoise: Rain Dance ----
# Attach unlimited Water Energy from hand to Water Pokemon
@register_power("base1-2", "activate")
def blastoise_rain_dance(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Find Water Energy in hand
    water_in_hand = [cid for cid in p.hand
                     if game.db.get(cid).is_energy and "Water" in game.db.get(cid).name]
    if not water_in_hand:
        return False

    # Find Water Pokemon to attach to
    water_slots = []
    for i, s in enumerate([p.active] + p.bench):
        if s and "Water" in game.db.get(s.card_id).types:
            water_slots.append((i, s))

    if not water_slots:
        return False

    # Attach one Water Energy to the Water Pokemon that needs it most
    # (AI will call this multiple times per turn)
    energy_id = water_in_hand[0]
    # Prefer active, then bench Pokemon that need energy for attacks
    best_target = water_slots[0]
    for idx, s in water_slots:
        card = game.db.get(s.card_id)
        for atk in card.attacks:
            needed = len(atk.cost) - len(s.attached_energy)
            if needed > 0:
                best_target = (idx, s)
                break

    target_slot = best_target[1]
    p.hand.remove(energy_id)
    target_slot.attached_energy.append(energy_id)
    return True


# ---- Venusaur: Energy Trans ----
# Move Grass Energy between your Pokemon
@register_power("base1-15", "activate")
def venusaur_energy_trans(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Find a Grass Energy on a Pokemon that doesn't need it, move to one that does
    all_slots = p.all_pokemon_slots()
    source = None
    target = None

    for s in all_slots:
        grass_count = count_energy_of_type(s, "Grass", game.db)
        card = game.db.get(s.card_id)
        if grass_count > 0:
            # Check if it has more than it needs
            needed = 0
            if card.attacks:
                for c in card.attacks[0].cost:
                    if c == "Grass":
                        needed += 1
            if grass_count > needed:
                source = s

    if source is None:
        return False

    # Find target that needs Grass Energy (prefer active)
    for s in [p.active] + p.bench:
        if s and s is not source:
            card = game.db.get(s.card_id)
            if "Grass" in card.types:
                target = s
                break

    if target is None:
        return False

    # Move one Grass Energy
    for i, eid in enumerate(source.attached_energy):
        if "Grass" in game.db.get(eid).name:
            source.attached_energy.pop(i)
            target.attached_energy.append(eid)
            return True

    return False


# ---- Charizard: Energy Burn ----
# Turn all energy into Fire Energy (for attack cost purposes)
# This is passive but also activatable - we handle it in damage calc
@register_power("base1-4", "activate")
def charizard_energy_burn(game: "Game", player_idx: int, slot_idx: int) -> bool:
    # Energy Burn is inherently passive - the engine handles it
    # by treating all energy as Fire when checking attack costs for Charizard
    return False  # No explicit activation needed


# ---- Alakazam: Damage Swap ----
# Move 1 damage counter between your Pokemon (can't KO)
@register_power("base1-1", "activate")
def alakazam_damage_swap(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Find a damaged Pokemon to move damage FROM
    all_slots = p.all_pokemon_slots()
    source = None
    target = None

    # Strategy: move damage away from active to a high-HP benched Pokemon
    if p.active and p.active.damage > 0:
        source = p.active
        # Find bench with most remaining HP
        for s in p.bench:
            card = game.db.get(s.card_id)
            remaining = card.hp - s.damage
            if remaining > 10:  # Can't KO the target
                if target is None or remaining > game.db.get(target.card_id).hp - target.damage:
                    target = s
    else:
        # Move damage from any damaged bench to one with more HP room
        for s in p.bench:
            if s.damage > 0:
                source = s
                break
        if source:
            for s in p.bench:
                if s is not source:
                    card = game.db.get(s.card_id)
                    if card.hp - s.damage > 10:
                        target = s
                        break
            if target is None and p.active:
                card = game.db.get(p.active.card_id)
                if card.hp - p.active.damage > 10:
                    target = p.active

    if source is None or target is None or source.damage < 10:
        return False

    source.damage -= 10
    target.damage += 10
    return True


# ---- Gengar: Curse ----
# Move 1 damage counter from one opponent's Pokemon to another
@register_power("base3-5", "activate")
@register_power("base3-20", "activate")
def gengar_curse(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot) or slot.used_power_this_turn:
        return False

    opp = game.state.players[1 - player_idx]
    # Move damage counter to opponent's active from a bench, or vice versa
    source = None
    target = None

    # Prefer moving damage TO the active (where it matters for KO)
    for s in opp.bench:
        if s.damage > 0:
            source = s
            break
    if source and opp.active:
        target = opp.active
    elif opp.active and opp.active.damage > 0 and opp.bench:
        # Move to a bench Pokemon that's close to KO
        source = opp.active
        for s in opp.bench:
            card = game.db.get(s.card_id)
            if card.hp - s.damage <= 10:
                target = s
                break
        if not target:
            target = opp.bench[0]

    if source is None or target is None or source.damage < 10:
        return False

    source.damage -= 10
    target.damage += 10
    slot.used_power_this_turn = True
    return True


# ---- Vileplume: Heal ----
# Flip coin, heads = remove 1 damage counter from one of your Pokemon
@register_power("base2-15", "activate")
@register_power("base2-31", "activate")
def vileplume_heal(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot) or slot.used_power_this_turn:
        return False

    # Find damaged Pokemon
    damaged = [s for s in p.all_pokemon_slots() if s.damage > 0]
    if not damaged:
        return False

    slot.used_power_this_turn = True
    if game.rng.coin_flip():
        # Heal the most damaged Pokemon
        target = max(damaged, key=lambda s: s.damage)
        target.damage = max(0, target.damage - 10)

    return True


# ---- Dragonite (Fossil): Step In ----
# Switch Dragonite from bench to active
@register_power("base3-4", "activate")
@register_power("base3-19", "activate")
def dragonite_step_in(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot) or slot.used_power_this_turn:
        return False

    # Must be on bench
    if slot_idx == 0:
        return False

    bench_idx = slot_idx - 1
    old_active = p.active
    p.active = p.bench.pop(bench_idx)
    if old_active:
        p.bench.append(old_active)
    slot.used_power_this_turn = True
    return True


# ---- Electrode: Buzzap ----
# KO Electrode, attach it as energy to another Pokemon
@register_power("base1-21", "activate")
def electrode_buzzap(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Find a Pokemon to attach to
    targets = []
    for i, s in enumerate([p.active] + p.bench):
        if s and s is not slot:
            targets.append((i, s))

    if not targets:
        return False

    # KO Electrode
    electrode_id = slot.card_id

    # Discard Electrode's cards
    for cid in slot.pokemon_stack:
        if cid != electrode_id:
            p.discard.append(cid)
    p.discard.extend(slot.attached_energy)

    # Remove from play
    if slot_idx == 0:
        p.active = None
    else:
        p.bench.pop(slot_idx - 1)

    # Attach Electrode as any energy type to target
    target_slot = targets[0][1]
    target_slot.attached_energy.append(electrode_id)

    # Opponent takes a prize
    opp = game.state.players[1 - player_idx]
    if opp.prizes:
        prize = opp.prizes.pop(0)
        opp.hand.append(prize)

    # Promote new active if needed
    if p.active is None and p.bench:
        ai = game.players[player_idx]
        bench_idx = ai.choose_new_active(game.state, player_idx)
        if bench_idx < 0 or bench_idx >= len(p.bench):
            bench_idx = 0
        p.active = p.bench.pop(bench_idx)

    return True


# ---- Slowbro: Strange Behavior ----
# Move damage counter from one of your Pokemon to Slowbro
@register_power("base3-43", "activate")
def slowbro_strange_behavior(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Find a damaged Pokemon (not Slowbro itself)
    slowbro_card = game.db.get(slot.card_id)
    slowbro_remaining = slowbro_card.hp - slot.damage
    if slowbro_remaining <= 10:
        return False  # Don't KO Slowbro

    source = None
    for s in p.all_pokemon_slots():
        if s is not slot and s.damage > 0:
            source = s
            break

    if source is None:
        return False

    source.damage -= 10
    slot.damage += 10
    return True


# ---- Tentacool: Cowardice ----
# Return Tentacool to hand
@register_power("base3-56", "activate")
def tentacool_cowardice(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return False

    # Return Tentacool to hand, discard attached cards
    card_id = slot.pokemon_stack[0]
    p.hand.append(card_id)
    for cid in slot.pokemon_stack[1:]:
        p.discard.append(cid)
    p.discard.extend(slot.attached_energy)

    if slot_idx == 0:
        p.active = None
        if p.bench:
            ai = game.players[player_idx]
            bench_idx = ai.choose_new_active(game.state, player_idx)
            if bench_idx < 0 or bench_idx >= len(p.bench):
                bench_idx = 0
            p.active = p.bench.pop(bench_idx)
    else:
        p.bench.pop(slot_idx - 1)

    return True


# ---- Promo Dragonite: Special Delivery ----
# Draw a card, put a card from hand on top of deck
@register_power("basep-5", "activate")
def promo_dragonite_special_delivery(game: "Game", player_idx: int, slot_idx: int) -> bool:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot) or slot.used_power_this_turn:
        return False

    if not p.deck:
        return False

    # Draw a card
    p.draw_card()

    # Put a card from hand on top of deck (AI picks the worst card)
    if p.hand:
        # Put back an energy card if we have too many, otherwise first card
        energies = [cid for cid in p.hand if game.db.get(cid).is_energy]
        if energies:
            card = energies[0]
        else:
            card = p.hand[0]
        p.hand.remove(card)
        p.deck.insert(0, card)

    slot.used_power_this_turn = True
    return True


# ============================================================
# PASSIVE POWERS (damage modification - hooked into damage pipeline)
# ============================================================

# ---- Mr. Mime: Invisible Wall ----
# Block damage >= 30 (after weakness/resistance)
@register_power("base2-6", "before_damage")
@register_power("base2-22", "before_damage")
def mr_mime_invisible_wall(game: "Game", player_idx: int, slot_idx: int,
                            damage: int, attacker_player_idx: int) -> int:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return damage
    if damage >= 30:
        return 0  # Prevent all damage
    return damage


# ---- Kabuto: Kabuto Armor ----
# Halve damage dealt to Kabuto (after weakness/resistance)
@register_power("base3-50", "before_damage")
def kabuto_armor(game: "Game", player_idx: int, slot_idx: int,
                  damage: int, attacker_player_idx: int) -> int:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return damage
    # Halve damage, round down to nearest 10
    halved = damage // 2
    return (halved // 10) * 10


# ---- Haunter (Fossil): Transparency ----
# Flip coin, heads = prevent all damage
@register_power("base3-6", "before_damage")
@register_power("base3-21", "before_damage")
def haunter_transparency(game: "Game", player_idx: int, slot_idx: int,
                          damage: int, attacker_player_idx: int) -> int:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return damage
    if game.rng.coin_flip():
        return 0
    return damage


# ---- Machamp: Strikes Back ----
# When damaged, deal 10 to attacker
@register_power("base1-8", "on_damaged")
def machamp_strikes_back(game: "Game", player_idx: int, slot_idx: int,
                          damage: int, attacker_player_idx: int) -> None:
    p = game.state.players[player_idx]
    slot = game._get_slot(p, slot_idx)
    if not slot or not power_usable(game, slot):
        return
    if damage > 0:
        opp = game.state.players[attacker_player_idx]
        if opp.active:
            opp.active.damage += 10


# ---- Snorlax: Thick Skinned ----
# Can't be affected by special conditions
# (Handled inline in apply_status - check for Snorlax before applying)


# ---- Dodrio: Retreat Aid ----
# Reduce active Pokemon's retreat cost by 1 while Dodrio is benched
# (Handled in retreat cost calculation)


# ---- Aerodactyl: Prehistoric Power ----
# No evolution cards can be played
# (Handled in legal action generation)


# ---- Muk: Toxic Gas ----
# Ignore all other Pokemon Powers
# (Already handled via is_muk_active() check)


# ---- Omanyte: Clairvoyance ----
# Opponent plays with hand face up (no mechanical effect in simulation)


# ---- Ditto: Transform ----
# Treat as defending Pokemon (complex - simplified for now)


# ---- Venomoth: Shift ----
# Change type to any other Pokemon's type (rarely useful in simulation)
