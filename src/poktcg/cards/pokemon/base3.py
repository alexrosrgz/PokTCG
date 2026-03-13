"""Attack effects for Fossil (base3) Pokemon."""

from __future__ import annotations
from typing import TYPE_CHECKING

from poktcg.cards.effects import (
    register_attack, apply_status, discard_energy_from_slot,
    count_energy_of_type, power_usable,
)
from poktcg.engine.state import SpecialCondition

if TYPE_CHECKING:
    from poktcg.engine.game import Game


# ============================================================
# Aerodactyl (base3-1) - Wing Attack (simple 30, no effect)
# Has Prehistoric Power ability (no attack effect needed)
# Duplicate: base3-16
# ============================================================


# ============================================================
# Articuno (base3-2) - Freeze Dry, Blizzard
# Duplicate: base3-17
# ============================================================
@register_attack("base3-2", 0)
def articuno_freeze_dry(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 30


@register_attack("base3-2", 1)
def articuno_blizzard(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    if game.rng.coin_flip():
        # Heads: 10 damage to each of opponent's benched Pokemon
        for slot in opp.bench:
            slot.damage += 10
    else:
        # Tails: 10 damage to each of your own benched Pokemon
        for slot in p.bench:
            slot.damage += 10
    return base_damage  # 50


# ============================================================
# Ditto (base3-3) - No attacks (Transform is a Pokemon Power)
# Duplicate: base3-18
# ============================================================


# ============================================================
# Dragonite (base3-4) - Slam
# Has Step In ability (no attack effect needed for it)
# Duplicate: base3-19
# ============================================================
@register_attack("base3-4", 0)
def dragonite_slam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 40 * heads


# ============================================================
# Gengar (base3-5) - Dark Mind
# Has Curse ability
# Duplicate: base3-20
# ============================================================
@register_attack("base3-5", 0)
def gengar_dark_mind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    # 10 damage to 1 benched Pokemon (choose randomly for engine)
    if opp.bench:
        target = game.rng.choice(opp.bench)
        target.damage += 10
    return base_damage  # 30


# ============================================================
# Haunter (base3-6) - Nightmare
# Has Transparency ability
# Duplicate: base3-21
# ============================================================
@register_attack("base3-6", 0)
def haunter_nightmare(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return base_damage  # 10


# ============================================================
# Hitmonlee (base3-7) - Stretch Kick, High Jump Kick (simple 50)
# Duplicate: base3-22
# ============================================================
@register_attack("base3-7", 0)
def hitmonlee_stretch_kick(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        target = game.rng.choice(opp.bench)
        target.damage += 20
    return 0  # No damage to active


# ============================================================
# Hypno (base3-8) - Prophecy, Dark Mind
# Duplicate: base3-23
# ============================================================
@register_attack("base3-8", 0)
def hypno_prophecy(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Look at top 3 cards of either deck and rearrange
    # Simplified: just shuffle top 3 cards of opponent's deck
    opp = game.state.players[1 - player_idx]
    if len(opp.deck) >= 3:
        top3 = opp.deck[-3:]
        game.rng.shuffle(top3)
        opp.deck[-3:] = top3
    return 0


@register_attack("base3-8", 1)
def hypno_dark_mind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        target = game.rng.choice(opp.bench)
        target.damage += 10
    return base_damage  # 30


# ============================================================
# Kabutops (base3-9) - Sharp Sickle (simple 30), Absorb
# Duplicate: base3-24
# ============================================================
@register_attack("base3-9", 1)
def kabutops_absorb(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal half the damage dealt (rounded up to nearest 10)
    # base_damage is 40; after W/R applied by engine, we approximate with base
    heal = ((base_damage // 2) + 9) // 10 * 10  # 20
    p.active.damage = max(0, p.active.damage - heal)
    return base_damage  # 40


# ============================================================
# Lapras (base3-10) - Water Gun, Confuse Ray
# Duplicate: base3-25
# ============================================================
@register_attack("base3-10", 0)
def lapras_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    # Cost is 1 Water, extra up to +20
    extra = max(0, min(water - 1, 2))
    return 10 + extra * 10


@register_attack("base3-10", 1)
def lapras_confuse_ray(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 10


# ============================================================
# Magneton (base3-11) - Sonicboom, Selfdestruct
# Duplicate: base3-26
# ============================================================
@register_attack("base3-11", 0)
def magneton_sonicboom(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Don't apply Weakness and Resistance (engine handles this via flag)
    # Simplified: just return base damage
    return base_damage  # 20


@register_attack("base3-11", 1)
def magneton_selfdestruct(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    # 20 to each benched Pokemon on both sides
    for slot in p.bench:
        slot.damage += 20
    for slot in opp.bench:
        slot.damage += 20
    # 100 to self
    p.active.damage += 100
    return base_damage  # 100 to defending


# ============================================================
# Moltres (base3-12) - Wildfire, Dive Bomb
# Duplicate: base3-27
# ============================================================
@register_attack("base3-12", 0)
def moltres_wildfire(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    # Discard any number of Fire Energy; discard that many from opponent's deck
    fire_count = count_energy_of_type(p.active, "Fire", game.db)
    # AI simplified: discard 1 Fire Energy if available
    discarded = discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    # Discard that many cards from top of opponent's deck
    for _ in range(discarded):
        if opp.deck:
            card_id = opp.deck.pop()
            opp.discard.append(card_id)
    return 0


@register_attack("base3-12", 1)
def moltres_dive_bomb(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if not game.rng.coin_flip():
        return 0  # Tails: attack does nothing
    return base_damage  # 80


# ============================================================
# Muk (base3-13) - Sludge
# Has Toxic Gas ability
# Duplicate: base3-28
# ============================================================
@register_attack("base3-13", 0)
def muk_sludge(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 30


# ============================================================
# Raichu (base3-14) - Gigashock
# Duplicate: base3-29
# ============================================================
@register_attack("base3-14", 0)
def raichu_gigashock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    # 10 damage to up to 3 benched Pokemon
    targets = opp.bench[:3]
    for slot in targets:
        slot.damage += 10
    return base_damage  # 30


# ============================================================
# Zapdos (base3-15) - Thunderstorm
# Duplicate: base3-30
# ============================================================
@register_attack("base3-15", 0)
def zapdos_thunderstorm(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    tails_count = 0
    for slot in opp.bench:
        if game.rng.coin_flip():
            slot.damage += 20  # Heads: 20 damage to that benched Pokemon
        else:
            tails_count += 1
    # Self-damage: 10 * number of tails
    p.active.damage += 10 * tails_count
    return base_damage  # 40


# ============================================================
# Arbok (base3-31) - Terror Strike, Poison Fang
# ============================================================
@register_attack("base3-31", 0)
def arbok_terror_strike(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if game.rng.coin_flip() and opp.bench:
        # Switch defending with a random benched Pokemon (after damage)
        old_active = opp.active
        idx = game.rng.randint(0, len(opp.bench) - 1)
        opp.active = opp.bench.pop(idx)
        if old_active:
            opp.bench.append(old_active)
    return base_damage  # 10


@register_attack("base3-31", 1)
def arbok_poison_fang(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


# ============================================================
# Cloyster (base3-32) - Clamp, Spike Cannon
# ============================================================
@register_attack("base3-32", 0)
def cloyster_clamp(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
        return base_damage  # 30
    else:
        return 0  # Tails: does nothing, not even damage


@register_attack("base3-32", 1)
def cloyster_spike_cannon(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


# ============================================================
# Gastly (base3-33) - Lick, Energy Conversion
# ============================================================
@register_attack("base3-33", 0)
def gastly_lick(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base3-33", 1)
def gastly_energy_conversion(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Put up to 2 Energy cards from discard pile into hand
    energy_found = 0
    to_remove = []
    for i, card_id in enumerate(p.discard):
        card = game.db.get(card_id)
        if card.supertype == "Energy" and energy_found < 2:
            to_remove.append(i)
            energy_found += 1
    for i in reversed(to_remove):
        card_id = p.discard.pop(i)
        p.hand.append(card_id)
    # Gastly does 10 damage to itself
    p.active.damage += 10
    return 0


# ============================================================
# Golbat (base3-34) - Wing Attack (simple 30), Leech Life
# ============================================================
@register_attack("base3-34", 1)
def golbat_leech_life(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal damage from Golbat equal to damage done (simplified: base_damage)
    heal = min(p.active.damage, base_damage)
    p.active.damage -= heal
    return base_damage  # 20


# ============================================================
# Golduck (base3-35) - Psyshock, Hyper Beam
# ============================================================
@register_attack("base3-35", 0)
def golduck_psyshock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base3-35", 1)
def golduck_hyper_beam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active and opp.active.attached_energy:
        eid = opp.active.attached_energy.pop(0)
        opp.discard.append(eid)
    return base_damage  # 20


# ============================================================
# Golem (base3-36) - Avalanche (simple 60), Selfdestruct
# ============================================================
@register_attack("base3-36", 1)
def golem_selfdestruct(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    for slot in p.bench:
        slot.damage += 20
    for slot in opp.bench:
        slot.damage += 20
    p.active.damage += 100
    return base_damage  # 100


# ============================================================
# Graveler (base3-37) - Harden, Rock Throw (simple 40)
# ============================================================
@register_attack("base3-37", 0)
def graveler_harden(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Prevent <=30 damage next turn (simplified: no persistent effect tracking)
    return 0


# ============================================================
# Kingler (base3-38) - Flail, Crabhammer (simple 40)
# ============================================================
@register_attack("base3-38", 0)
def kingler_flail(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return 10 * counters


# ============================================================
# Magmar (base3-39) - Smokescreen, Smog
# ============================================================
@register_attack("base3-39", 0)
def magmar_smokescreen(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Opponent must flip to attack next turn (simplified: no persistent effect tracking)
    return base_damage  # 10


@register_attack("base3-39", 1)
def magmar_smog(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


# ============================================================
# Omastar (base3-40) - Water Gun, Spike Cannon
# ============================================================
@register_attack("base3-40", 0)
def omastar_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    # Cost is 1 Water + 1 Colorless; extra Water beyond cost (1 Water needed)
    extra = max(0, min(water - 1, 2))
    return 20 + extra * 10


@register_attack("base3-40", 1)
def omastar_spike_cannon(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


# ============================================================
# Sandslash (base3-41) - Slash (simple 20), Fury Swipes
# ============================================================
@register_attack("base3-41", 1)
def sandslash_fury_swipes(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    return 20 * heads


# ============================================================
# Seadra (base3-42) - Water Gun, Agility
# ============================================================
@register_attack("base3-42", 0)
def seadra_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    # Cost is 1 Water + 1 Colorless; extra Water beyond 1
    extra = max(0, min(water - 1, 2))
    return 20 + extra * 10


@register_attack("base3-42", 1)
def seadra_agility(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = prevent all damage/effects next turn (simplified)
    game.rng.coin_flip()
    return base_damage  # 20


# ============================================================
# Slowbro (base3-43) - Psyshock
# Has Strange Behavior ability
# ============================================================
@register_attack("base3-43", 0)
def slowbro_psyshock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Tentacruel (base3-44) - Supersonic, Jellyfish Sting
# ============================================================
@register_attack("base3-44", 0)
def tentacruel_supersonic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return 0


@register_attack("base3-44", 1)
def tentacruel_jellyfish_sting(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 10


# ============================================================
# Weezing (base3-45) - Smog, Selfdestruct
# ============================================================
@register_attack("base3-45", 0)
def weezing_smog(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


@register_attack("base3-45", 1)
def weezing_selfdestruct(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    for slot in p.bench:
        slot.damage += 10
    for slot in opp.bench:
        slot.damage += 10
    p.active.damage += 60
    return base_damage  # 60


# ============================================================
# Ekans (base3-46) - Spit Poison, Wrap
# ============================================================
@register_attack("base3-46", 0)
def ekans_spit_poison(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return 0


@register_attack("base3-46", 1)
def ekans_wrap(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Geodude (base3-47) - Stone Barrage
# ============================================================
@register_attack("base3-47", 0)
def geodude_stone_barrage(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip until tails, 10 damage per heads
    heads = 0
    while game.rng.coin_flip():
        heads += 1
    return 10 * heads


# ============================================================
# Grimer (base3-48) - Nasty Goo, Minimize
# ============================================================
@register_attack("base3-48", 0)
def grimer_nasty_goo(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base3-48", 1)
def grimer_minimize(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Reduce damage by 20 next turn (simplified: no persistent effect tracking)
    return 0


# ============================================================
# Horsea (base3-49) - Smokescreen
# ============================================================
@register_attack("base3-49", 0)
def horsea_smokescreen(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Opponent must flip to attack next turn (simplified: no persistent effect tracking)
    return base_damage  # 10


# ============================================================
# Kabuto (base3-50) - Scratch (simple 10, no effect)
# Has Kabuto Armor ability
# ============================================================


# ============================================================
# Krabby (base3-51) - Call for Family, Irongrip (simple 20)
# ============================================================
@register_attack("base3-51", 0)
def krabby_call_for_family(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Search deck for a Basic Pokemon named Krabby and put onto bench
    if len(p.bench) < 5:
        for i, card_id in enumerate(p.deck):
            card = game.db.get(card_id)
            if card.name == "Krabby" and "Basic" in card.subtypes:
                p.deck.pop(i)
                from poktcg.engine.state import PokemonSlot
                slot = PokemonSlot(pokemon_stack=[card_id])
                p.bench.append(slot)
                break
        game.rng.shuffle(p.deck)
    return 0


# ============================================================
# Omanyte (base3-52) - Water Gun
# Has Clairvoyance ability
# ============================================================
@register_attack("base3-52", 0)
def omanyte_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    # Cost is 1 Water; extra up to +20
    extra = max(0, min(water - 1, 2))
    return 10 + extra * 10


# ============================================================
# Psyduck (base3-53) - Headache, Fury Swipes
# ============================================================
@register_attack("base3-53", 0)
def psyduck_headache(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Opponent can't play Trainer cards next turn (simplified: no persistent effect tracking)
    return 0


@register_attack("base3-53", 1)
def psyduck_fury_swipes(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    return 10 * heads


# ============================================================
# Shellder (base3-54) - Supersonic, Hide in Shell
# ============================================================
@register_attack("base3-54", 0)
def shellder_supersonic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return 0


@register_attack("base3-54", 1)
def shellder_hide_in_shell(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = prevent all damage next turn (simplified)
    game.rng.coin_flip()
    return 0


# ============================================================
# Slowpoke (base3-55) - Spacing Out, Scavenge
# ============================================================
@register_attack("base3-55", 0)
def slowpoke_spacing_out(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if p.active.damage > 0 and game.rng.coin_flip():
        p.active.damage = max(0, p.active.damage - 10)
    return 0


@register_attack("base3-55", 1)
def slowpoke_scavenge(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Discard 1 Psychic Energy
    discarded = discard_energy_from_slot(game, player_idx, p.active, "Psychic", 1)
    if discarded:
        # Put a Trainer card from discard into hand
        for i, card_id in enumerate(p.discard):
            card = game.db.get(card_id)
            if card.supertype == "Trainer":
                p.discard.pop(i)
                p.hand.append(card_id)
                break
    return 0


# ============================================================
# Tentacool (base3-56) - Acid (simple 10, no effect)
# Has Cowardice ability
# ============================================================


# ============================================================
# Zubat (base3-57) - Supersonic, Leech Life
# ============================================================
@register_attack("base3-57", 0)
def zubat_supersonic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return 0


@register_attack("base3-57", 1)
def zubat_leech_life(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal damage from Zubat equal to damage done (simplified: base_damage)
    heal = min(p.active.damage, base_damage)
    p.active.damage -= heal
    return base_damage  # 10
