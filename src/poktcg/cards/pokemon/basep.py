"""Attack effects for Promo cards 1-15 (minus 11)."""

from __future__ import annotations
from typing import TYPE_CHECKING

from poktcg.cards.effects import (
    register_attack, apply_status, discard_energy_from_slot,
    count_energy_of_type,
)
from poktcg.engine.state import SpecialCondition

if TYPE_CHECKING:
    from poktcg.engine.game import Game


# ============================================================
# Promo 1 - Pikachu: Growl, Thundershock
# ============================================================
@register_attack("basep-1", 1)
def promo_pikachu_thundershock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Promo 2 - Electabuzz: Light Screen, Quick Attack
# ============================================================
@register_attack("basep-2", 0)
def promo_electabuzz_light_screen(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Prevent up to 10 damage next turn (simplified)
    return base_damage  # 20


@register_attack("basep-2", 1)
def promo_electabuzz_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20
    return 10


# ============================================================
# Promo 3 - Mewtwo: Energy Absorption, Psyburn
# ============================================================
@register_attack("basep-3", 0)
def promo_mewtwo_energy_absorption(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Attach up to 2 Energy from discard to Mewtwo
    p = game.state.players[player_idx]
    attached = 0
    discard_copy = p.discard[:]
    for cid in discard_copy:
        if attached >= 2:
            break
        card = game.db.get(cid)
        if card.is_energy:
            p.discard.remove(cid)
            p.active.attached_energy.append(cid)
            attached += 1
    return 0

# Psyburn is simple 60 damage


# ============================================================
# Promo 4 - Pikachu: Recharge, Thunderbolt
# ============================================================
@register_attack("basep-4", 0)
def promo_pikachu2_recharge(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Attach Lightning energy from deck
    p = game.state.players[player_idx]
    for i, cid in enumerate(p.deck):
        card = game.db.get(cid)
        if "Lightning" in card.name and card.is_energy:
            p.deck.pop(i)
            p.active.attached_energy.append(cid)
            game.rng.shuffle(p.deck)
            break
    return 0


@register_attack("basep-4", 1)
def promo_pikachu2_thunderbolt(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.discard.extend(p.active.attached_energy)
    p.active.attached_energy.clear()
    return base_damage  # 50


# ============================================================
# Promo 5 - Dragonite: Special Delivery (Power, not attack)
# Slam attack
# ============================================================
@register_attack("basep-5", 0)
def promo_dragonite_slam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 40 * heads


# ============================================================
# Promo 6 - Arcanine: Quick Attack, Flames of Rage
# ============================================================
@register_attack("basep-6", 0)
def promo_arcanine_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20
    return 10


@register_attack("basep-6", 1)
def promo_arcanine_flames_of_rage(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return 40 + counters * 10


# ============================================================
# Promo 7 - Jigglypuff: First Aid, Double-edge
# ============================================================
@register_attack("basep-7", 0)
def promo_jigglypuff_first_aid(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if p.active.damage >= 10:
        p.active.damage -= 10
    return 0


@register_attack("basep-7", 1)
def promo_jigglypuff_double_edge(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.active.damage += 20
    return base_damage  # 40


# ============================================================
# Promo 8 - Mew: Neutral Shield, Psyshock
# ============================================================
@register_attack("basep-8", 1)
def promo_mew_psyshock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Promo 9 - Mew: Devolution Beam, Psywave
# ============================================================
@register_attack("basep-9", 0)
def promo_mew_devolution_beam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Devolve a Pokemon - simplified: just do nothing for now
    return 0


@register_attack("basep-9", 1)
def promo_mew_psywave(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # 10x energy attached to defending
    opp = game.state.players[1 - player_idx]
    if opp.active:
        return 10 * len(opp.active.attached_energy)
    return 0


# ============================================================
# Promo 10 - Meowth: Cat Punch, Coin Hurl
# ============================================================
@register_attack("basep-10", 0)
def promo_meowth_cat_punch(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # 20 to a random benched Pokemon
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        target = game.rng.choice(opp.bench)
        target.damage += 20
    return 0


@register_attack("basep-10", 1)
def promo_meowth_coin_hurl(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Simple 20 damage but with a coin flip mechanic in some versions
    return base_damage  # 20


# ============================================================
# Promo 12 - Mewtwo: Energy Absorption, Psyburn
# Same as Promo 3, register separately
# ============================================================
@register_attack("basep-12", 0)
def promo_mewtwo2_energy_absorption(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    attached = 0
    discard_copy = p.discard[:]
    for cid in discard_copy:
        if attached >= 2:
            break
        card = game.db.get(cid)
        if card.is_energy:
            p.discard.remove(cid)
            p.active.attached_energy.append(cid)
            attached += 1
    return 0


# ============================================================
# Promo 13 - Venusaur: Mega Drain, Body Slam
# ============================================================
@register_attack("basep-13", 0)
def promo_venusaur_mega_drain(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal 20 from self
    p.active.damage = max(0, p.active.damage - 20)
    return base_damage  # 40


@register_attack("basep-13", 1)
def promo_venusaur_body_slam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 30


# ============================================================
# Promo 14 - Mewtwo: Swift
# ============================================================
@register_attack("basep-14", 0)
def promo_mewtwo3_swift(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Swift ignores all effects, weakness, resistance
    # Simplified: just return damage directly (skip damage pipeline)
    return base_damage  # 40


# ============================================================
# Promo 15 - Cool Porygon: Conversion, Tri Attack
# ============================================================
@register_attack("basep-15", 1)
def promo_porygon_tri_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    return 10 * heads
