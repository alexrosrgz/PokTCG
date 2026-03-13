"""Attack effects for Base Set Pokemon."""

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
# Alakazam (base1-1) - Confuse Ray
# ============================================================
@register_attack("base1-1", 0)
def alakazam_confuse_ray(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 30


# ============================================================
# Blastoise (base1-2) - Hydro Pump
# ============================================================
@register_attack("base1-2", 0)
def blastoise_hydro_pump(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # +10 per extra Water Energy beyond cost (3 Water needed, extra up to +20)
    water_count = count_energy_of_type(p.active, "Water", game.db)
    extra = max(0, min(water_count - 3, 2))  # Max +20 extra
    return base_damage + extra * 10  # 40 + up to 20


# ============================================================
# Chansey (base1-3) - Scrunch, Double-edge
# ============================================================
@register_attack("base1-3", 0)
def chansey_scrunch(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = prevent all damage next turn (simplified: no effect tracking yet)
    # TODO: implement prevention effect properly
    game.rng.coin_flip()  # Consume the flip for determinism
    return 0


@register_attack("base1-3", 1)
def chansey_double_edge(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.active.damage += 80  # Self-damage
    return base_damage  # 80


# ============================================================
# Charizard (base1-4) - Fire Spin
# ============================================================
@register_attack("base1-4", 0)
def charizard_fire_spin(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, count=2)
    return base_damage  # 100


# ============================================================
# Clefairy (base1-5) - Sing, Metronome
# ============================================================
@register_attack("base1-5", 0)
def clefairy_sing(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


@register_attack("base1-5", 1)
def clefairy_metronome(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Copy one of defending Pokemon's attacks (simplified: use their first attack's damage)
    opp = game.state.players[1 - player_idx]
    if opp.active:
        def_card = game.db.get(opp.active.card_id)
        if def_card.attacks:
            return def_card.attacks[0].base_damage
    return 0


# ============================================================
# Gyarados (base1-6) - Dragon Rage, Bubblebeam
# ============================================================
@register_attack("base1-6", 1)
def gyarados_bubblebeam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 40


# ============================================================
# Hitmonchan (base1-7) - Jab, Special Punch
# ============================================================
# Both are simple damage attacks, no effects needed


# ============================================================
# Machamp (base1-8) - Seismitoss
# ============================================================
# Seismitoss is simple 60 damage, Karate Chop has effect:
@register_attack("base1-8", 0)
def machamp_karate_chop(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # 50 minus 10 for each damage counter on Machamp
    damage_counters = p.active.damage // 10
    return max(0, 50 - damage_counters * 10)


# ============================================================
# Magneton (base1-9) - Thunder Wave, Selfdestruct
# ============================================================
@register_attack("base1-9", 0)
def magneton_thunder_wave(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 30


@register_attack("base1-9", 1)
def magneton_selfdestruct(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    # 20 to each benched Pokemon on both sides (no weakness/resistance)
    for slot in p.bench:
        slot.damage += 20
    for slot in opp.bench:
        slot.damage += 20
    # 100 to self
    p.active.damage += 100
    return base_damage  # 80 to defending


# ============================================================
# Mewtwo (base1-10) - Psychic, Barrier
# ============================================================
@register_attack("base1-10", 0)
def mewtwo_psychic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active:
        energy_count = len(opp.active.attached_energy)
        return 10 + energy_count * 10
    return 10


@register_attack("base1-10", 1)
def mewtwo_barrier(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Psychic", 1)
    # Prevent damage next turn (simplified: no persistent effect tracking yet)
    return 0


# ============================================================
# Nidoking (base1-11) - Thrash, Toxic
# ============================================================
@register_attack("base1-11", 0)
def nidoking_thrash(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if game.rng.coin_flip():
        return 30 + 10  # 40 on heads
    else:
        p.active.damage += 10  # 10 to self on tails
        return 30


@register_attack("base1-11", 1)
def nidoking_toxic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    # Toxic does 20 poison damage instead of 10 (simplified: just double poison)
    return base_damage  # 40


# ============================================================
# Ninetales (base1-12) - Lure, Fire Blast
# ============================================================
@register_attack("base1-12", 0)
def ninetales_lure(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        old_active = opp.active
        opp.active = opp.bench.pop(0)
        if old_active:
            opp.bench.append(old_active)
    return 0


@register_attack("base1-12", 1)
def ninetales_fire_blast(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    return base_damage  # 80


# ============================================================
# Poliwrath (base1-13) - Water Gun, Whirlpool
# ============================================================
@register_attack("base1-13", 0)
def poliwrath_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    extra = max(0, min(water - 2, 2))
    return 30 + extra * 10


@register_attack("base1-13", 1)
def poliwrath_whirlpool(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active and opp.active.attached_energy:
        eid = opp.active.attached_energy.pop(0)
        opp.discard.append(eid)
    return base_damage  # 40


# ============================================================
# Raichu (base1-14) - Agility, Thunder
# ============================================================
@register_attack("base1-14", 0)
def raichu_agility(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()  # Simplified: prevention not fully tracked
    return base_damage  # 20


@register_attack("base1-14", 1)
def raichu_thunder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if not game.rng.coin_flip():
        p.active.damage += 30  # Self-damage on tails
    return base_damage  # 60


# ============================================================
# Venusaur (base1-15) - Solarbeam (simple 60 damage)
# ============================================================


# ============================================================
# Zapdos (base1-16) - Thunder, Thunderbolt
# ============================================================
@register_attack("base1-16", 0)
def zapdos_thunder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if not game.rng.coin_flip():
        p.active.damage += 30
    return base_damage  # 60


@register_attack("base1-16", 1)
def zapdos_thunderbolt(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Discard all energy
    p.discard.extend(p.active.attached_energy)
    p.active.attached_energy.clear()
    return base_damage  # 100


# ============================================================
# Beedrill (base1-17) - Twineedle, Poison Sting
# ============================================================
@register_attack("base1-17", 0)
def beedrill_twineedle(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


@register_attack("base1-17", 1)
def beedrill_poison_sting(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 40


# ============================================================
# Dragonair (base1-18) - Slam, Hyper Beam
# ============================================================
@register_attack("base1-18", 0)
def dragonair_slam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


@register_attack("base1-18", 1)
def dragonair_hyper_beam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active and opp.active.attached_energy:
        eid = opp.active.attached_energy.pop(0)
        opp.discard.append(eid)
    return base_damage  # 20


# ============================================================
# Dugtrio (base1-19) - Slash, Earthquake
# ============================================================
@register_attack("base1-19", 1)
def dugtrio_earthquake(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    for slot in p.bench:
        slot.damage += 10
    return base_damage  # 70


# ============================================================
# Electabuzz (base1-20) - Thundershock, Thunderpunch
# ============================================================
@register_attack("base1-20", 0)
def electabuzz_thundershock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base1-20", 1)
def electabuzz_thunderpunch(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if game.rng.coin_flip():
        return 30 + 10  # 40 on heads
    else:
        p.active.damage += 10
        return 30


# ============================================================
# Electrode (base1-21) - Tackle (simple), Thunderbolt
# ============================================================
@register_attack("base1-21", 1)
def electrode_thunderbolt(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.discard.extend(p.active.attached_energy)
    p.active.attached_energy.clear()
    return base_damage  # 50


# ============================================================
# Pidgeotto (base1-22) - Whirlwind, Mirror Move
# ============================================================
@register_attack("base1-22", 0)
def pidgeotto_whirlwind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        old_active = opp.active
        idx = game.rng.randint(0, len(opp.bench) - 1)
        opp.active = opp.bench.pop(idx)
        if old_active:
            opp.bench.append(old_active)
    return base_damage  # 20


@register_attack("base1-22", 1)
def pidgeotto_mirror_move(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Simplified: mirror move without last-attack tracking returns 0
    return 0


# ============================================================
# Arcanine (base1-23) - Flamethrower, Take Down
# ============================================================
@register_attack("base1-23", 0)
def arcanine_flamethrower(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    return base_damage  # 50


@register_attack("base1-23", 1)
def arcanine_take_down(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.active.damage += 30
    return base_damage  # 80


# ============================================================
# Charmeleon (base1-24) - Slash (simple), Flamethrower
# ============================================================
@register_attack("base1-24", 1)
def charmeleon_flamethrower(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    return base_damage  # 50


# ============================================================
# Dewgong (base1-25) - Aurora Beam (simple), Ice Beam
# ============================================================
@register_attack("base1-25", 1)
def dewgong_ice_beam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 30


# ============================================================
# Dratini (base1-26) - Pound (simple)
# ============================================================


# ============================================================
# Farfetch'd (base1-27) - Leek Slap, Pot Smash
# ============================================================
@register_attack("base1-27", 0)
def farfetchd_leek_slap(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if not game.rng.coin_flip():
        return 0  # Does nothing on tails
    return base_damage  # 30


# ============================================================
# Growlithe (base1-28) - Flare
# ============================================================
# Simple 20 damage


# ============================================================
# Haunter (base1-29) - Hypnosis, Dream Eater
# ============================================================
@register_attack("base1-29", 0)
def haunter_hypnosis(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


@register_attack("base1-29", 1)
def haunter_dream_eater(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active and SpecialCondition.ASLEEP not in opp.active.conditions:
        return 0  # Only works if defending is asleep
    return base_damage  # 50


# ============================================================
# Ivysaur (base1-30) - Vine Whip (simple), Poisonpowder
# ============================================================
@register_attack("base1-30", 1)
def ivysaur_poisonpowder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


# ============================================================
# Jynx (base1-31) - Doubleslap, Meditate
# ============================================================
@register_attack("base1-31", 0)
def jynx_doubleslap(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 10 * heads


@register_attack("base1-31", 1)
def jynx_meditate(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active:
        counters = opp.active.damage // 10
        return 20 + counters * 10
    return 20


# ============================================================
# Kadabra (base1-32) - Recover, Super Psi
# ============================================================
@register_attack("base1-32", 0)
def kadabra_recover(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Psychic", 1)
    p.active.damage = 0  # Remove all damage
    return 0


# Super Psi is simple 50 damage


# ============================================================
# Kakuna (base1-33) - Stiffen, Poisonpowder
# ============================================================
@register_attack("base1-33", 0)
def kakuna_stiffen(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()  # Simplified prevention
    return 0


@register_attack("base1-33", 1)
def kakuna_poisonpowder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


# ============================================================
# Machoke (base1-34) - Karate Chop, Submission
# ============================================================
@register_attack("base1-34", 0)
def machoke_karate_chop(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return max(0, 50 - counters * 10)


@register_attack("base1-34", 1)
def machoke_submission(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    p.active.damage += 20
    return base_damage  # 60


# ============================================================
# Magikarp (base1-35) - Tackle, Flail
# ============================================================
@register_attack("base1-35", 1)
def magikarp_flail(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return 10 * counters


# ============================================================
# Nidorino (base1-37) - Double Kick, Horn Drill (simple)
# ============================================================
@register_attack("base1-37", 0)
def nidorino_double_kick(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


# ============================================================
# Poliwhirl (base1-38) - Amnesia, Doubleslap
# ============================================================
@register_attack("base1-38", 0)
def poliwhirl_amnesia(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Simplified: just does damage, doesn't track attack prevention
    return base_damage  # 20


@register_attack("base1-38", 1)
def poliwhirl_doubleslap(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


# ============================================================
# Porygon (base1-39) - Conversion, Agility
# ============================================================
@register_attack("base1-39", 0)
def porygon_conversion(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Change defender's weakness - simplified: no persistent effect
    return 0


@register_attack("base1-39", 1)
def porygon_agility(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()  # Simplified prevention
    return base_damage  # 20


# ============================================================
# Raticate (base1-40) - Bite, Super Fang
# ============================================================
@register_attack("base1-40", 1)
def raticate_super_fang(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active:
        card = game.db.get(opp.active.card_id)
        remaining_hp = card.hp - opp.active.damage
        half = remaining_hp // 2
        # Round up to nearest 10
        half = ((half + 9) // 10) * 10
        return half
    return 0


# ============================================================
# Seel (base1-41) - Headbutt (simple)
# ============================================================


# ============================================================
# Wartortle (base1-42) - Withdraw, Bite
# ============================================================
@register_attack("base1-42", 0)
def wartortle_withdraw(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()  # Simplified prevention
    return 0


# ============================================================
# Abra (base1-43) - Psyshock
# ============================================================
@register_attack("base1-43", 0)
def abra_psyshock(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


# ============================================================
# Bulbasaur (base1-44) - Leech Seed
# ============================================================
@register_attack("base1-44", 0)
def bulbasaur_leech_seed(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal 1 damage counter from self after damage
    if p.active.damage >= 10:
        p.active.damage -= 10
    return base_damage  # 20


# ============================================================
# Caterpie (base1-45) - String Shot
# ============================================================
@register_attack("base1-45", 0)
def caterpie_string_shot(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


# ============================================================
# Charmander (base1-46) - Scratch (simple), Ember
# ============================================================
@register_attack("base1-46", 1)
def charmander_ember(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    return base_damage  # 30


# ============================================================
# Diglett (base1-47) - Dig, Mud Slap
# ============================================================
# Both simple damage


# ============================================================
# Doduo (base1-48) - Fury Attack
# ============================================================
@register_attack("base1-48", 0)
def doduo_fury_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 10 * heads


# ============================================================
# Drowzee (base1-49) - Pound (simple), Confuse Ray
# ============================================================
@register_attack("base1-49", 1)
def drowzee_confuse_ray(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 10


# ============================================================
# Gastly (base1-50) - Sleeping Gas, Destiny Bond
# ============================================================
@register_attack("base1-50", 0)
def gastly_sleeping_gas(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


@register_attack("base1-50", 1)
def gastly_destiny_bond(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Simplified: discard energy, don't track destiny bond effect
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Psychic", 1)
    return 0


# ============================================================
# Koffing (base1-51) - Foul Gas
# ============================================================
@register_attack("base1-51", 0)
def koffing_foul_gas(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    else:
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 10


# ============================================================
# Machop (base1-52) - Low Kick (simple)
# ============================================================


# ============================================================
# Magnemite (base1-53) - Thunder Wave, Selfdestruct
# ============================================================
@register_attack("base1-53", 0)
def magnemite_thunder_wave(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base1-53", 1)
def magnemite_selfdestruct(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    for slot in p.bench:
        slot.damage += 10
    for slot in opp.bench:
        slot.damage += 10
    p.active.damage += 40
    return base_damage  # 40


# ============================================================
# Metapod (base1-54) - Stiffen, Stun Spore
# ============================================================
@register_attack("base1-54", 0)
def metapod_stiffen(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()
    return 0


@register_attack("base1-54", 1)
def metapod_stun_spore(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Nidoran M (base1-55) - Horn Hazard
# ============================================================
@register_attack("base1-55", 0)
def nidoran_m_horn_hazard(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if not game.rng.coin_flip():
        return 0
    return base_damage  # 30


# ============================================================
# Onix (base1-56) - Rock Throw (simple), Harden
# ============================================================
@register_attack("base1-56", 1)
def onix_harden(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Prevent <=30 damage next turn (simplified)
    game.rng.coin_flip()  # consume for determinism
    return 0


# ============================================================
# Pidgey (base1-57) - Whirlwind
# ============================================================
@register_attack("base1-57", 0)
def pidgey_whirlwind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        old_active = opp.active
        idx = game.rng.randint(0, len(opp.bench) - 1)
        opp.active = opp.bench.pop(idx)
        if old_active:
            opp.bench.append(old_active)
    return base_damage  # 10


# ============================================================
# Pikachu (base1-58) - Gnaw (simple), Thunder Jolt
# ============================================================
@register_attack("base1-58", 1)
def pikachu_thunder_jolt(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if not game.rng.coin_flip():
        p.active.damage += 10
    return base_damage  # 30


# ============================================================
# Poliwag (base1-59) - Water Gun
# ============================================================
@register_attack("base1-59", 0)
def poliwag_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    extra = max(0, min(water - 1, 2))
    return 10 + extra * 10


# ============================================================
# Ponyta (base1-60) - Smash Kick (simple), Flame Tail
# ============================================================
# Both simple damage


# ============================================================
# Rattata (base1-61) - Bite (simple)
# ============================================================


# ============================================================
# Sandshrew (base1-62) - Sand-attack
# ============================================================
@register_attack("base1-62", 0)
def sandshrew_sand_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Opponent must flip to attack next turn (simplified)
    return base_damage  # 10


# ============================================================
# Squirtle (base1-63) - Bubble, Withdraw
# ============================================================
@register_attack("base1-63", 0)
def squirtle_bubble(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base1-63", 1)
def squirtle_withdraw(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    game.rng.coin_flip()  # Simplified prevention
    return 0


# ============================================================
# Starmie (base1-64) - Recover, Star Freeze
# ============================================================
@register_attack("base1-64", 0)
def starmie_recover(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Water", 1)
    p.active.damage = 0
    return 0


@register_attack("base1-64", 1)
def starmie_star_freeze(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Staryu (base1-65) - Slap, Star Freeze (same pattern)
# ============================================================


# ============================================================
# Tangela (base1-66) - Bind, Poisonpowder
# ============================================================
@register_attack("base1-66", 0)
def tangela_bind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


@register_attack("base1-66", 1)
def tangela_poisonpowder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 20


# ============================================================
# Voltorb (base1-67) - Tackle (simple)
# ============================================================


# ============================================================
# Vulpix (base1-68) - Confuse Ray
# ============================================================
@register_attack("base1-68", 0)
def vulpix_confuse_ray(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 10


# ============================================================
# Weedle (base1-69) - Poison Sting
# ============================================================
@register_attack("base1-69", 0)
def weedle_poison_sting(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 10
