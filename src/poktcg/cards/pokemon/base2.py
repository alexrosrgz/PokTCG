"""Attack effects for Jungle Set (base2) Pokemon."""

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
# Clefable (base2-1) - Metronome, Minimize
# Duplicate: base2-17
# ============================================================
@register_attack("base2-1", 0)
def clefable_metronome(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Copy one of defending Pokemon's attacks (simplified: use their first attack's damage)
    opp = game.state.players[1 - player_idx]
    if opp.active:
        def_card = game.db.get(opp.active.card_id)
        if def_card.attacks:
            return def_card.attacks[0].base_damage
    return 0


@register_attack("base2-1", 1)
def clefable_minimize(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Reduce damage by 20 next turn (simplified: no persistent effect tracking)
    return 0


# ============================================================
# Electrode (base2-2) - Chain Lightning
# Duplicate: base2-18
# ============================================================
@register_attack("base2-2", 1)
def electrode_chain_lightning(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # If defending isn't Colorless, do 10 to each benched Pokemon of same type (both sides)
    opp = game.state.players[1 - player_idx]
    p = game.state.players[player_idx]
    if opp.active:
        def_card = game.db.get(opp.active.card_id)
        if def_card.types and "Colorless" not in def_card.types:
            def_type = def_card.types[0]
            # Damage to opponent's bench
            for slot in opp.bench:
                slot_card = game.db.get(slot.card_id)
                if slot_card.types and def_type in slot_card.types:
                    slot.damage += 10
            # Damage to own bench
            for slot in p.bench:
                slot_card = game.db.get(slot.card_id)
                if slot_card.types and def_type in slot_card.types:
                    slot.damage += 10
    return base_damage  # 20


# ============================================================
# Flareon (base2-3) - Quick Attack, Flamethrower
# Duplicate: base2-19
# ============================================================
@register_attack("base2-3", 0)
def flareon_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20  # 30 on heads
    return 10


@register_attack("base2-3", 1)
def flareon_flamethrower(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    discard_energy_from_slot(game, player_idx, p.active, "Fire", 1)
    return base_damage  # 60


# ============================================================
# Jolteon (base2-4) - Quick Attack, Pin Missile
# Duplicate: base2-20
# ============================================================
@register_attack("base2-4", 0)
def jolteon_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20  # 30 on heads
    return 10


@register_attack("base2-4", 1)
def jolteon_pin_missile(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(4)
    return 20 * heads


# ============================================================
# Kangaskhan (base2-5) - Fetch, Comet Punch
# Duplicate: base2-21
# ============================================================
@register_attack("base2-5", 0)
def kangaskhan_fetch(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if p.deck:
        card_id = p.deck.pop(0)
        p.hand.append(card_id)
    return 0


@register_attack("base2-5", 1)
def kangaskhan_comet_punch(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(4)
    return 20 * heads


# ============================================================
# Mr. Mime (base2-6) - Meditate
# Duplicate: base2-22
# ============================================================
@register_attack("base2-6", 0)
def mr_mime_meditate(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.active:
        counters = opp.active.damage // 10
        return 10 + counters * 10
    return 10


# ============================================================
# Nidoqueen (base2-7) - Boyfriends
# Duplicate: base2-23
# ============================================================
@register_attack("base2-7", 0)
def nidoqueen_boyfriends(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    nidoking_count = 0
    # Check active
    if p.active:
        active_card = game.db.get(p.active.card_id)
        if active_card.name == "Nidoking":
            nidoking_count += 1
    # Check bench
    for slot in p.bench:
        slot_card = game.db.get(slot.card_id)
        if slot_card.name == "Nidoking":
            nidoking_count += 1
    return 20 + nidoking_count * 20


# ============================================================
# Pidgeot (base2-8) - Hurricane
# Duplicate: base2-24
# ============================================================
@register_attack("base2-8", 1)
def pidgeot_hurricane(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Return defending Pokemon and all attached cards to opponent's hand
    # unless this KOs the defending Pokemon.
    # The KO check happens after damage is applied by the engine,
    # so we just return the damage here. The bounce effect is simplified.
    opp = game.state.players[1 - player_idx]
    if opp.active:
        def_card = game.db.get(opp.active.card_id)
        remaining_hp = def_card.hp - opp.active.damage
        # If this won't KO, return to hand
        if remaining_hp > base_damage:
            # Return attached energy to hand
            opp.hand.extend(opp.active.attached_energy)
            opp.active.attached_energy.clear()
            # Return the Pokemon card to hand
            opp.hand.append(opp.active.card_id)
            opp.active = None
            return 0  # Don't apply damage since we bounced
    return base_damage  # 30


# ============================================================
# Pinsir (base2-9) - Irongrip
# Duplicate: base2-25
# ============================================================
@register_attack("base2-9", 0)
def pinsir_irongrip(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 20


# ============================================================
# Scyther (base2-10) - Swords Dance
# Duplicate: base2-26
# ============================================================
@register_attack("base2-10", 0)
def scyther_swords_dance(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Boost Slash next turn to 60 instead of 30
    # Simplified: no persistent effect tracking, just mark intent
    return 0


# ============================================================
# Snorlax (base2-11) - Body Slam
# Duplicate: base2-27
# ============================================================
@register_attack("base2-11", 0)
def snorlax_body_slam(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 30


# ============================================================
# Vaporeon (base2-12) - Quick Attack, Water Gun
# Duplicate: base2-28
# ============================================================
@register_attack("base2-12", 0)
def vaporeon_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20  # 30 on heads
    return 10


@register_attack("base2-12", 1)
def vaporeon_water_gun(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    water = count_energy_of_type(p.active, "Water", game.db)
    # Cost is 2 Water + 1 Colorless; extra Water beyond 2, max 2 extra
    extra = max(0, min(water - 2, 2))
    return 30 + extra * 10


# ============================================================
# Venomoth (base2-13) - Venom Powder
# Duplicate: base2-29
# ============================================================
@register_attack("base2-13", 0)
def venomoth_venom_powder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 10


# ============================================================
# Victreebel (base2-14) - Lure, Acid
# Duplicate: base2-30
# ============================================================
@register_attack("base2-14", 0)
def victreebel_lure(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        old_active = opp.active
        opp.active = opp.bench.pop(0)
        if old_active:
            opp.bench.append(old_active)
    return 0


@register_attack("base2-14", 1)
def victreebel_acid(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = defending can't retreat next turn (simplified: no persistent tracking)
    game.rng.coin_flip()
    return base_damage  # 20


# ============================================================
# Vileplume (base2-15) - Petal Dance
# Duplicate: base2-31
# ============================================================
@register_attack("base2-15", 0)
def vileplume_petal_dance(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    # Vileplume is now Confused after doing damage
    apply_status(game, player_idx, 0, SpecialCondition.CONFUSED)
    return 40 * heads


# ============================================================
# Wigglytuff (base2-16) - Lullaby, Do the Wave
# Duplicate: base2-32
# ============================================================
@register_attack("base2-16", 0)
def wigglytuff_lullaby(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


@register_attack("base2-16", 1)
def wigglytuff_do_the_wave(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    bench_count = len(p.bench)
    return 10 + bench_count * 10


# ============================================================
# Butterfree (base2-33) - Whirlwind, Mega Drain
# ============================================================
@register_attack("base2-33", 0)
def butterfree_whirlwind(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        old_active = opp.active
        idx = game.rng.randint(0, len(opp.bench) - 1)
        opp.active = opp.bench.pop(idx)
        if old_active:
            opp.bench.append(old_active)
    return base_damage  # 20


@register_attack("base2-33", 1)
def butterfree_mega_drain(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Heal half the damage done (rounded up to nearest 10)
    # base_damage is 40; half is 20
    heal = ((base_damage // 2) + 9) // 10 * 10
    p.active.damage = max(0, p.active.damage - heal)
    return base_damage  # 40


# ============================================================
# Dodrio (base2-34) - Rage
# ============================================================
@register_attack("base2-34", 0)
def dodrio_rage(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return 10 + counters * 10


# ============================================================
# Exeggutor (base2-35) - Teleport, Big Eggsplosion
# ============================================================
@register_attack("base2-35", 0)
def exeggutor_teleport(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if p.bench:
        old_active = p.active
        p.active = p.bench.pop(0)
        if old_active:
            p.bench.append(old_active)
    return 0


@register_attack("base2-35", 1)
def exeggutor_big_eggsplosion(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    energy_count = len(p.active.attached_energy)
    heads = game.rng.flip_coins(energy_count)
    return 20 * heads


# ============================================================
# Fearow (base2-36) - Agility
# ============================================================
@register_attack("base2-36", 0)
def fearow_agility(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = prevent all effects of attacks next turn (simplified)
    game.rng.coin_flip()
    return base_damage  # 20


# ============================================================
# Gloom (base2-37) - Poisonpowder, Foul Odor
# ============================================================
@register_attack("base2-37", 0)
def gloom_poisonpowder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return 0


@register_attack("base2-37", 1)
def gloom_foul_odor(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Both defending and Gloom are now Confused
    apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    apply_status(game, player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 20


# ============================================================
# Lickitung (base2-38) - Tongue Wrap, Supersonic
# ============================================================
@register_attack("base2-38", 0)
def lickitung_tongue_wrap(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base2-38", 1)
def lickitung_supersonic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return 0


# ============================================================
# Marowak (base2-39) - Bonemerang, Call for Friend
# ============================================================
@register_attack("base2-39", 0)
def marowak_bonemerang(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


@register_attack("base2-39", 1)
def marowak_call_for_friend(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Search deck for a Fighting Basic Pokemon and put it on bench
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return 0  # Bench is full
    for i, card_id in enumerate(p.deck):
        card = game.db.get(card_id)
        if (card.supertype == "Pokémon"
                and "Basic" in card.subtypes
                and "Fighting" in card.types):
            p.deck.pop(i)
            from poktcg.engine.state import PokemonSlot
            slot = PokemonSlot(pokemon_stack=[card_id])
            p.bench.append(slot)
            break
    # Shuffle deck
    game.rng.shuffle(p.deck)
    return 0


# ============================================================
# Nidorina (base2-40) - Supersonic, Double Kick
# ============================================================
@register_attack("base2-40", 0)
def nidorina_supersonic(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.CONFUSED)
    return 0


@register_attack("base2-40", 1)
def nidorina_double_kick(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(2)
    return 30 * heads


# ============================================================
# Parasect (base2-41) - Spore
# ============================================================
@register_attack("base2-41", 0)
def parasect_spore(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


# ============================================================
# Persian (base2-42) - Pounce
# ============================================================
@register_attack("base2-42", 1)
def persian_pounce(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Reduce damage from defending's next attack by 10 (simplified: no persistent tracking)
    return base_damage  # 30


# ============================================================
# Primeape (base2-43) - Fury Swipes, Tantrum
# ============================================================
@register_attack("base2-43", 0)
def primeape_fury_swipes(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    return 20 * heads


@register_attack("base2-43", 1)
def primeape_tantrum(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if not game.rng.coin_flip():
        apply_status(game, player_idx, 0, SpecialCondition.CONFUSED)
    return base_damage  # 50


# ============================================================
# Rapidash (base2-44) - Stomp, Agility
# ============================================================
@register_attack("base2-44", 0)
def rapidash_stomp(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 20 + 10  # 30 on heads
    return 20


@register_attack("base2-44", 1)
def rapidash_agility(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = prevent all effects of attacks next turn (simplified)
    game.rng.coin_flip()
    return base_damage  # 30


# ============================================================
# Rhydon (base2-45) - Ram
# ============================================================
@register_attack("base2-45", 1)
def rhydon_ram(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    opp = game.state.players[1 - player_idx]
    # Rhydon does 20 damage to itself
    p.active.damage += 20
    # Opponent switches with a benched Pokemon (opponent chooses, simplified: random)
    if opp.bench:
        old_active = opp.active
        idx = game.rng.randint(0, len(opp.bench) - 1)
        opp.active = opp.bench.pop(idx)
        if old_active:
            opp.bench.append(old_active)
    return base_damage  # 50


# ============================================================
# Seaking (base2-46) - no effects (Horn Attack, Waterfall are simple)
# ============================================================


# ============================================================
# Tauros (base2-47) - Stomp, Rampage
# ============================================================
@register_attack("base2-47", 0)
def tauros_stomp(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 20 + 10  # 30 on heads
    return 20


@register_attack("base2-47", 1)
def tauros_rampage(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    damage = 20 + counters * 10
    if not game.rng.coin_flip():
        apply_status(game, player_idx, 0, SpecialCondition.CONFUSED)
    return damage


# ============================================================
# Weepinbell (base2-48) - Poisonpowder
# ============================================================
@register_attack("base2-48", 0)
def weepinbell_poisonpowder(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.POISONED)
    return base_damage  # 10


# ============================================================
# Bellsprout (base2-49) - Call for Family
# ============================================================
@register_attack("base2-49", 1)
def bellsprout_call_for_family(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Search deck for a Basic Pokemon named Bellsprout and put on bench
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return 0
    for i, card_id in enumerate(p.deck):
        card = game.db.get(card_id)
        if (card.supertype == "Pokémon"
                and "Basic" in card.subtypes
                and card.name == "Bellsprout"):
            p.deck.pop(i)
            from poktcg.engine.state import PokemonSlot
            slot = PokemonSlot(pokemon_stack=[card_id])
            p.bench.append(slot)
            break
    game.rng.shuffle(p.deck)
    return 0


# ============================================================
# Cubone (base2-50) - Snivel, Rage
# ============================================================
@register_attack("base2-50", 0)
def cubone_snivel(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Reduce damage by 20 next turn (simplified: no persistent effect tracking)
    return 0


@register_attack("base2-50", 1)
def cubone_rage(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    counters = p.active.damage // 10
    return 10 + counters * 10


# ============================================================
# Eevee (base2-51) - Tail Wag, Quick Attack
# ============================================================
@register_attack("base2-51", 0)
def eevee_tail_wag(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = defending can't attack Eevee next turn (simplified)
    game.rng.coin_flip()
    return 0


@register_attack("base2-51", 1)
def eevee_quick_attack(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        return 10 + 20  # 30 on heads
    return 10


# ============================================================
# Exeggcute (base2-52) - Hypnosis, Leech Seed
# ============================================================
@register_attack("base2-52", 0)
def exeggcute_hypnosis(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


@register_attack("base2-52", 1)
def exeggcute_leech_seed(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Remove 1 damage counter from Exeggcute (unless all damage prevented)
    if p.active.damage >= 10:
        p.active.damage -= 10
    return base_damage  # 20


# ============================================================
# Goldeen (base2-53) - no effects (Horn Attack is simple)
# ============================================================


# ============================================================
# Jigglypuff (base2-54) - Lullaby
# ============================================================
@register_attack("base2-54", 0)
def jigglypuff_lullaby(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


# ============================================================
# Mankey (base2-55) - Scratch (simple, no effect)
# ============================================================


# ============================================================
# Meowth (base2-56) - Pay Day
# ============================================================
@register_attack("base2-56", 0)
def meowth_pay_day(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    if game.rng.coin_flip():
        if p.deck:
            card_id = p.deck.pop(0)
            p.hand.append(card_id)
    return base_damage  # 10


# ============================================================
# Nidoran F (base2-57) - Fury Swipes, Call for Family
# ============================================================
@register_attack("base2-57", 0)
def nidoran_f_fury_swipes(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    heads = game.rng.flip_coins(3)
    return 10 * heads


@register_attack("base2-57", 1)
def nidoran_f_call_for_family(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Search deck for Nidoran M or Nidoran F and put on bench
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return 0
    for i, card_id in enumerate(p.deck):
        card = game.db.get(card_id)
        if (card.supertype == "Pokémon"
                and "Basic" in card.subtypes
                and card.name in ("Nidoran ♂", "Nidoran ♀")):
            p.deck.pop(i)
            from poktcg.engine.state import PokemonSlot
            slot = PokemonSlot(pokemon_stack=[card_id])
            p.bench.append(slot)
            break
    game.rng.shuffle(p.deck)
    return 0


# ============================================================
# Oddish (base2-58) - Stun Spore, Sprout
# ============================================================
@register_attack("base2-58", 0)
def oddish_stun_spore(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base2-58", 1)
def oddish_sprout(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Search deck for a Basic Pokemon named Oddish and put on bench
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return 0
    for i, card_id in enumerate(p.deck):
        card = game.db.get(card_id)
        if (card.supertype == "Pokémon"
                and "Basic" in card.subtypes
                and card.name == "Oddish"):
            p.deck.pop(i)
            from poktcg.engine.state import PokemonSlot
            slot = PokemonSlot(pokemon_stack=[card_id])
            p.bench.append(slot)
            break
    game.rng.shuffle(p.deck)
    return 0


# ============================================================
# Paras (base2-59) - Spore
# ============================================================
@register_attack("base2-59", 1)
def paras_spore(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    apply_status(game, 1 - player_idx, 0, SpecialCondition.ASLEEP)
    return 0


# ============================================================
# Pikachu (base2-60) - Spark
# ============================================================
@register_attack("base2-60", 0)
def pikachu_spark(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    opp = game.state.players[1 - player_idx]
    if opp.bench:
        # Choose 1 benched Pokemon and do 10 damage (simplified: first bench slot)
        opp.bench[0].damage += 10
    return base_damage  # 20


# ============================================================
# Rhyhorn (base2-61) - Leer
# ============================================================
@register_attack("base2-61", 0)
def rhyhorn_leer(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Flip: heads = defending can't attack Rhyhorn next turn (simplified)
    game.rng.coin_flip()
    return 0


# ============================================================
# Spearow (base2-62) - Mirror Move
# ============================================================
@register_attack("base2-62", 1)
def spearow_mirror_move(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    # Simplified: mirror move without last-attack tracking returns 0
    return 0


# ============================================================
# Venonat (base2-63) - Stun Spore, Leech Life
# ============================================================
@register_attack("base2-63", 0)
def venonat_stun_spore(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    if game.rng.coin_flip():
        apply_status(game, 1 - player_idx, 0, SpecialCondition.PARALYZED)
    return base_damage  # 10


@register_attack("base2-63", 1)
def venonat_leech_life(game: "Game", player_idx: int, attack_index: int, base_damage: int) -> int:
    p = game.state.players[player_idx]
    # Remove damage counters equal to the damage done (10 base, before W/R)
    # Simplified: heal 10 (base damage amount)
    heal = base_damage  # 10
    p.active.damage = max(0, p.active.damage - heal)
    return base_damage  # 10
