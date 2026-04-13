"""Trainer card effect implementations for Base-Fossil format.

All trainers are registered by name so they work across sets (e.g., both
base1 and base2 printings of the same trainer).
"""

from __future__ import annotations

from poktcg.cards.effects import (
    register_trainer_by_name,
    discard_energy_from_slot,
)
from poktcg.engine.state import SpecialCondition, PokemonSlot

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from poktcg.engine.game import Game


# ============================================================
# Draw / Hand Manipulation
# ============================================================

@register_trainer_by_name("Bill")
def bill(game: "Game", player_idx: int) -> bool:
    """Draw 2 cards."""
    game.state.players[player_idx].draw_cards(2)
    game._log(f"  {game._pname(player_idx)} drew 2 cards", player=player_idx)
    return True


@register_trainer_by_name("Professor Oak")
def professor_oak(game: "Game", player_idx: int) -> bool:
    """Discard your hand, then draw 7 cards."""
    p = game.state.players[player_idx]
    hand_size = len(p.hand)
    p.discard.extend(p.hand)
    p.hand.clear()
    p.draw_cards(7)
    game._log(f"  {game._pname(player_idx)} discarded {hand_size} cards, drew 7 new cards", player=player_idx)
    return True


@register_trainer_by_name("Maintenance")
def maintenance(game: "Game", player_idx: int) -> bool:
    """Shuffle 2 other cards from hand into deck to draw 1."""
    p = game.state.players[player_idx]
    # Need at least 2 other cards in hand (the trainer itself is already removed)
    if len(p.hand) < 2:
        return False
    # AI picks first 2 cards to shuffle back
    for _ in range(2):
        if p.hand:
            card = p.hand.pop(0)
            p.deck.append(card)
    game.rng.shuffle(p.deck)
    p.draw_card()
    game._log(f"  {game._pname(player_idx)} shuffled 2 cards into deck, drew 1", player=player_idx)
    return True


@register_trainer_by_name("Gambler")
def gambler(game: "Game", player_idx: int) -> bool:
    """Shuffle hand into deck. Flip coin: heads draw 8, tails draw 1."""
    p = game.state.players[player_idx]
    p.deck.extend(p.hand)
    p.hand.clear()
    game.rng.shuffle(p.deck)
    if game.rng.coin_flip():
        p.draw_cards(8)
        game._log(f"  {game._pname(player_idx)} shuffled hand into deck, flipped heads — drew 8 cards", player=player_idx)
    else:
        p.draw_cards(1)
        game._log(f"  {game._pname(player_idx)} shuffled hand into deck, flipped tails — drew 1 card", player=player_idx)
    return True


@register_trainer_by_name("Pokédex")
def pokedex(game: "Game", player_idx: int) -> bool:
    """Look at top 5 cards, rearrange. AI just shuffles top 5."""
    p = game.state.players[player_idx]
    top5 = p.deck[:5]
    game.rng.shuffle(top5)
    p.deck[:5] = top5
    game._log(f"  {game._pname(player_idx)} looked at top 5 cards and rearranged them", player=player_idx)
    return True


@register_trainer_by_name("Impostor Professor Oak")
def impostor_professor_oak(game: "Game", player_idx: int) -> bool:
    """Opponent shuffles hand into deck, draws 7."""
    opp_idx = 1 - player_idx
    opp = game.state.players[opp_idx]
    hand_size = len(opp.hand)
    opp.deck.extend(opp.hand)
    opp.hand.clear()
    game.rng.shuffle(opp.deck)
    opp.draw_cards(7)
    game._log(f"  {game._pname(opp_idx)} shuffled {hand_size} cards into deck, forced to draw 7", player=player_idx)
    return True


@register_trainer_by_name("Lass")
def lass(game: "Game", player_idx: int) -> bool:
    """Both players shuffle trainer cards from hand into deck."""
    counts = []
    for i in range(2):
        p = game.state.players[i]
        trainers = [cid for cid in p.hand if game.db.get(cid).is_trainer]
        counts.append(len(trainers))
        for cid in trainers:
            p.hand.remove(cid)
            p.deck.append(cid)
        game.rng.shuffle(p.deck)
    game._log(f"  {game._pname(player_idx)} shuffled {counts[player_idx]} trainers back; {game._pname(1 - player_idx)} shuffled {counts[1 - player_idx]} trainers back", player=player_idx)
    return True


# ============================================================
# Search / Retrieval
# ============================================================

@register_trainer_by_name("Computer Search")
def computer_search(game: "Game", player_idx: int) -> bool:
    """Discard 2 cards from hand, search deck for any card."""
    p = game.state.players[player_idx]
    if len(p.hand) < 2 or not p.deck:
        return False
    # Discard first 2 cards in hand
    for _ in range(2):
        if p.hand:
            p.discard.append(p.hand.pop(0))
    # AI picks first card from deck (random since deck is shuffled)
    found = None
    if p.deck:
        found = p.deck.pop(0)
        p.hand.append(found)
    game.rng.shuffle(p.deck)
    if found:
        game._log(f"  {game._pname(player_idx)} discarded 2 cards, searched deck for {game._card_name(found)}", player=player_idx)
    return True


@register_trainer_by_name("Item Finder")
def item_finder(game: "Game", player_idx: int) -> bool:
    """Discard 2 cards, retrieve a trainer from discard."""
    p = game.state.players[player_idx]
    trainers_in_discard = [cid for cid in p.discard if game.db.get(cid).is_trainer]
    if len(p.hand) < 2 or not trainers_in_discard:
        return False
    for _ in range(2):
        if p.hand:
            p.discard.append(p.hand.pop(0))
    # Get first trainer from discard
    chosen = trainers_in_discard[0]
    p.discard.remove(chosen)
    p.hand.append(chosen)
    game._log(f"  {game._pname(player_idx)} discarded 2 cards, retrieved {game._card_name(chosen)} from discard", player=player_idx)
    return True


@register_trainer_by_name("Pokémon Trader")
def pokemon_trader(game: "Game", player_idx: int) -> bool:
    """Trade a Pokemon in hand for one from deck."""
    p = game.state.players[player_idx]
    pokemon_in_hand = [cid for cid in p.hand if game.db.get(cid).is_pokemon]
    pokemon_in_deck = [cid for cid in p.deck if game.db.get(cid).is_pokemon]
    if not pokemon_in_hand or not pokemon_in_deck:
        return False
    # Put one back, get one
    give_back = pokemon_in_hand[0]
    p.hand.remove(give_back)
    p.deck.append(give_back)
    get_card = pokemon_in_deck[0]
    p.deck.remove(get_card)
    p.hand.append(get_card)
    game.rng.shuffle(p.deck)
    game._log(f"  {game._pname(player_idx)} traded {game._card_name(give_back)} for {game._card_name(get_card)} from deck", player=player_idx)
    return True


@register_trainer_by_name("Pokémon Breeder")
def pokemon_breeder(game: "Game", player_idx: int) -> bool:
    """Put Stage 2 directly on matching Basic (skip Stage 1)."""
    p = game.state.players[player_idx]
    # Find Stage 2 cards in hand
    stage2s = [cid for cid in p.hand if game.db.get(cid).is_pokemon and game.db.get(cid).is_stage2]
    if not stage2s:
        return False

    for s2_id in stage2s:
        s2_card = game.db.get(s2_id)
        # Find the Stage 1 it evolves from
        stage1_name = s2_card.evolves_from
        if not stage1_name:
            continue
        # Find what Basic the Stage 1 evolves from
        stage1_cards = game.db.find_by_name(stage1_name)
        if not stage1_cards:
            continue
        basic_name = stage1_cards[0].evolves_from
        if not basic_name:
            continue
        # Find a Basic in play matching
        for slot in p.all_pokemon_slots():
            top_card = game.db.get(slot.card_id)
            if top_card.name == basic_name and top_card.is_basic:
                if slot.turn_played < game.state.turn:
                    p.hand.remove(s2_id)
                    slot.pokemon_stack.append(s2_id)
                    slot.turn_evolved = game.state.turn
                    slot.conditions.clear()
                    game._log(f"  {game._pname(player_idx)} evolved {basic_name} directly into {s2_card.name} (skipped Stage 1)", player=player_idx)
                    return True
    return False


@register_trainer_by_name("Energy Search")
def energy_search(game: "Game", player_idx: int) -> bool:
    """Search deck for a basic Energy card."""
    p = game.state.players[player_idx]
    for i, cid in enumerate(p.deck):
        card = game.db.get(cid)
        if card.is_energy and card.is_basic_energy:
            p.deck.pop(i)
            p.hand.append(cid)
            game.rng.shuffle(p.deck)
            game._log(f"  {game._pname(player_idx)} searched deck for {card.name}", player=player_idx)
            return True
    return False


@register_trainer_by_name("Energy Retrieval")
def energy_retrieval(game: "Game", player_idx: int) -> bool:
    """Trade 1 card for up to 2 basic Energy from discard."""
    p = game.state.players[player_idx]
    energy_in_discard = [cid for cid in p.discard
                         if game.db.get(cid).is_energy and game.db.get(cid).is_basic_energy]
    if not p.hand or not energy_in_discard:
        return False
    # Discard 1 card
    p.discard.append(p.hand.pop(0))
    # Retrieve up to 2 energy
    retrieved = 0
    for _ in range(min(2, len(energy_in_discard))):
        if energy_in_discard:
            eid = energy_in_discard.pop(0)
            p.discard.remove(eid)
            p.hand.append(eid)
            retrieved += 1
    game._log(f"  {game._pname(player_idx)} discarded 1 card, retrieved {retrieved} energy from discard", player=player_idx)
    return True


@register_trainer_by_name("Recycle")
def recycle(game: "Game", player_idx: int) -> bool:
    """Flip coin. Heads: put a card from discard on top of deck."""
    p = game.state.players[player_idx]
    if not p.discard:
        return False
    if game.rng.coin_flip():
        card = p.discard.pop()
        p.deck.insert(0, card)
        game._log(f"  Flipped heads — put {game._card_name(card)} on top of deck", player=player_idx)
    else:
        game._log(f"  Flipped tails — no effect", player=player_idx)
    return True


@register_trainer_by_name("Poké Ball")
def poke_ball(game: "Game", player_idx: int) -> bool:
    """Flip coin. Heads: search deck for Basic/Evolution Pokemon."""
    p = game.state.players[player_idx]
    if game.rng.coin_flip():
        for i, cid in enumerate(p.deck):
            if game.db.get(cid).is_pokemon:
                p.deck.pop(i)
                p.hand.append(cid)
                game.rng.shuffle(p.deck)
                game._log(f"  Flipped heads — found {game._card_name(cid)}", player=player_idx)
                return True
        game._log(f"  Flipped heads — no Pokémon in deck", player=player_idx)
    else:
        game._log(f"  Flipped tails — no effect", player=player_idx)
    return True  # Even on tails, card was played


# ============================================================
# Disruption
# ============================================================

@register_trainer_by_name("Energy Removal")
def energy_removal(game: "Game", player_idx: int) -> bool:
    """Discard 1 Energy from an opponent's Pokemon."""
    opp_idx = 1 - player_idx
    opp = game.state.players[opp_idx]
    # Target opponent's active first, then bench
    for slot in opp.all_pokemon_slots():
        if slot.attached_energy:
            eid = slot.attached_energy.pop(0)
            opp.discard.append(eid)
            pokemon_name = game._card_name(slot.card_id)
            game._log(f"  Removed {game._card_name(eid)} from {game._pname(opp_idx)}'s {pokemon_name}", player=player_idx)
            return True
    return False


@register_trainer_by_name("Super Energy Removal")
def super_energy_removal(game: "Game", player_idx: int) -> bool:
    """Discard 1 own Energy to discard up to 2 from opponent's Pokemon."""
    p = game.state.players[player_idx]
    opp_idx = 1 - player_idx
    opp = game.state.players[opp_idx]

    # Find own energy to discard
    own_slot = None
    for slot in p.all_pokemon_slots():
        if slot.attached_energy:
            own_slot = slot
            break
    if not own_slot:
        return False

    # Discard 1 own energy
    own_eid = own_slot.attached_energy.pop(0)
    p.discard.append(own_eid)

    # Discard up to 2 from opponent
    removed = 0
    for slot in opp.all_pokemon_slots():
        while slot.attached_energy and removed < 2:
            eid = slot.attached_energy.pop(0)
            opp.discard.append(eid)
            removed += 1
        if removed >= 2:
            break

    game._log(f"  {game._pname(player_idx)} discarded own {game._card_name(own_eid)}, removed {removed} energy from {game._pname(opp_idx)}", player=player_idx)
    return True


@register_trainer_by_name("Gust of Wind")
def gust_of_wind(game: "Game", player_idx: int) -> bool:
    """Switch opponent's active with one of their benched Pokemon."""
    opp_idx = 1 - player_idx
    opp = game.state.players[opp_idx]
    if not opp.bench:
        return False
    # AI picks first bench Pokemon (could be smarter in heuristic AI)
    old_active = opp.active
    new_active = opp.bench.pop(0)
    opp.active = new_active
    if old_active:
        opp.bench.append(old_active)
    new_name = game._card_name(new_active.card_id)
    game._log(f"  Pulled {game._pname(opp_idx)}'s benched {new_name} to active", player=player_idx)
    return True


@register_trainer_by_name("Pokémon Flute")
def pokemon_flute(game: "Game", player_idx: int) -> bool:
    """Put a Basic Pokemon from opponent's discard onto their bench."""
    opp_idx = 1 - player_idx
    opp = game.state.players[opp_idx]
    if len(opp.bench) >= 5:
        return False
    for i, cid in enumerate(opp.discard):
        card = game.db.get(cid)
        if card.is_pokemon and card.is_basic:
            opp.discard.pop(i)
            opp.bench.append(PokemonSlot(
                pokemon_stack=[cid],
                turn_played=game.state.turn,
            ))
            game._log(f"  Put {card.name} from {game._pname(opp_idx)}'s discard onto their bench", player=player_idx)
            return True
    return False


# ============================================================
# Healing / Status
# ============================================================

@register_trainer_by_name("Potion")
def potion(game: "Game", player_idx: int) -> bool:
    """Remove up to 20 damage from one of your Pokemon."""
    p = game.state.players[player_idx]
    # Heal the most damaged Pokemon
    best_slot = None
    best_damage = 0
    for slot in p.all_pokemon_slots():
        if slot.damage > best_damage:
            best_damage = slot.damage
            best_slot = slot
    if best_slot and best_slot.damage > 0:
        healed = min(20, best_slot.damage)
        best_slot.damage = max(0, best_slot.damage - 20)
        game._log(f"  Healed {healed} damage from {game._card_name(best_slot.card_id)}", player=player_idx)
        return True
    return False


@register_trainer_by_name("Super Potion")
def super_potion(game: "Game", player_idx: int) -> bool:
    """Discard 1 Energy to remove up to 40 damage from that Pokemon."""
    p = game.state.players[player_idx]
    for slot in p.all_pokemon_slots():
        if slot.damage > 0 and slot.attached_energy:
            eid = slot.attached_energy.pop(0)
            p.discard.append(eid)
            healed = min(40, slot.damage)
            slot.damage = max(0, slot.damage - 40)
            game._log(f"  Discarded {game._card_name(eid)}, healed {healed} damage from {game._card_name(slot.card_id)}", player=player_idx)
            return True
    return False


@register_trainer_by_name("Full Heal")
def full_heal(game: "Game", player_idx: int) -> bool:
    """Remove all special conditions from active Pokemon."""
    p = game.state.players[player_idx]
    if p.active and p.active.conditions:
        conditions = ", ".join(c.name.lower() for c in p.active.conditions)
        p.active.conditions.clear()
        game._log(f"  Cured {game._card_name(p.active.card_id)} of {conditions}", player=player_idx)
        return True
    return p.active is not None  # Play even if no conditions


@register_trainer_by_name("Pokémon Center")
def pokemon_center(game: "Game", player_idx: int) -> bool:
    """Remove all damage from all your Pokemon, discard all Energy from healed ones."""
    p = game.state.players[player_idx]
    healed_names = []
    for slot in p.all_pokemon_slots():
        if slot.damage > 0:
            healed_names.append(game._card_name(slot.card_id))
            slot.damage = 0
            # Discard all energy
            p.discard.extend(slot.attached_energy)
            slot.attached_energy.clear()
    if healed_names:
        game._log(f"  Healed all damage from {', '.join(healed_names)} (discarded their energy)", player=player_idx)
    else:
        game._log(f"  No damaged Pokémon to heal", player=player_idx)
    return True


@register_trainer_by_name("Revive")
def revive(game: "Game", player_idx: int) -> bool:
    """Put Basic Pokemon from discard onto bench at half HP damage."""
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return False
    for i, cid in enumerate(p.discard):
        card = game.db.get(cid)
        if card.is_pokemon and card.is_basic:
            p.discard.pop(i)
            half_hp = card.hp // 2
            # Round to nearest 10
            half_hp = (half_hp // 10) * 10
            p.bench.append(PokemonSlot(
                pokemon_stack=[cid],
                damage=half_hp,
                turn_played=game.state.turn,
            ))
            game._log(f"  Revived {card.name} to bench with {card.hp - half_hp}/{card.hp} HP", player=player_idx)
            return True
    return False


# ============================================================
# Pokemon Manipulation
# ============================================================

@register_trainer_by_name("Switch")
def switch(game: "Game", player_idx: int) -> bool:
    """Switch active with a benched Pokemon."""
    p = game.state.players[player_idx]
    if not p.bench or not p.active:
        return False
    old_name = game._card_name(p.active.card_id)
    old_active = p.active
    p.active = p.bench.pop(0)
    new_name = game._card_name(p.active.card_id)
    p.bench.append(old_active)
    game._log(f"  Swapped active {old_name} with benched {new_name}", player=player_idx)
    return True


@register_trainer_by_name("Scoop Up")
def scoop_up(game: "Game", player_idx: int) -> bool:
    """Return a Pokemon's Basic card to hand, discard everything else."""
    p = game.state.players[player_idx]
    # Prefer scooping up damaged active
    target = None
    is_active = False
    if p.active and p.active.damage > 0:
        target = p.active
        is_active = True
    elif p.bench:
        for slot in p.bench:
            if slot.damage > 0:
                target = slot
                break

    if target is None:
        # Scoop up active anyway if we have bench
        if p.active and p.bench:
            target = p.active
            is_active = True
        else:
            return False

    # Return basic to hand
    basic_id = target.pokemon_stack[0]
    basic_name = game._card_name(basic_id)
    p.hand.append(basic_id)

    # Discard everything else
    for cid in target.pokemon_stack[1:]:
        p.discard.append(cid)
    p.discard.extend(target.attached_energy)

    if is_active:
        if p.bench:
            p.active = p.bench.pop(0)
        else:
            p.active = None
    else:
        p.bench.remove(target)

    game._log(f"  Scooped up {basic_name}, returned basic card to hand", player=player_idx)
    return True


@register_trainer_by_name("Devolution Spray")
def devolution_spray(game: "Game", player_idx: int) -> bool:
    """Devolve one of your Pokemon by removing top evolution card."""
    p = game.state.players[player_idx]
    for slot in p.all_pokemon_slots():
        if len(slot.pokemon_stack) > 1:
            evo_id = slot.pokemon_stack.pop()
            new_top = game._card_name(slot.card_id)
            p.discard.append(evo_id)
            game._log(f"  Devolved {game._card_name(evo_id)} back to {new_top}", player=player_idx)
            return True
    return False


@register_trainer_by_name("Mr. Fuji")
def mr_fuji(game: "Game", player_idx: int) -> bool:
    """Shuffle a benched Pokemon and all attached cards into deck."""
    p = game.state.players[player_idx]
    if not p.bench:
        return False
    slot = p.bench.pop(0)
    pokemon_name = game._card_name(slot.card_id)
    p.deck.extend(slot.pokemon_stack)
    p.deck.extend(slot.attached_energy)
    game.rng.shuffle(p.deck)
    game._log(f"  Shuffled benched {pokemon_name} and all attached cards into deck", player=player_idx)
    return True


# ============================================================
# Attach-to-Pokemon Trainers
# ============================================================

@register_trainer_by_name("PlusPower")
def pluspower(game: "Game", player_idx: int) -> bool:
    """Attach to active: +10 damage this turn."""
    p = game.state.players[player_idx]
    if p.active:
        p.active.pluspower_count += 1
        total = p.active.pluspower_count * 10
        game._log(f"  +10 damage to {game._card_name(p.active.card_id)}'s next attack (total +{total})", player=player_idx)
        return True
    return False


@register_trainer_by_name("Defender")
def defender(game: "Game", player_idx: int) -> bool:
    """Attach to a Pokemon: -20 damage received this turn."""
    p = game.state.players[player_idx]
    if p.active:
        p.active.defender_count += 1
        total = p.active.defender_count * 20
        game._log(f"  -20 damage to {game._card_name(p.active.card_id)} this turn (total -{total})", player=player_idx)
        return True
    return False


# ============================================================
# Special Trainers (played as Pokemon)
# ============================================================

@register_trainer_by_name("Clefairy Doll")
def clefairy_doll(game: "Game", player_idx: int) -> bool:
    """Play as Basic Pokemon with 10 HP. Can't attack or retreat."""
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return False
    # Find the Clefairy Doll in hand (it's already been removed by play_trainer)
    # We need to handle this specially - the card is already in discard
    # Move it from discard to bench as a pseudo-Pokemon
    for i, cid in enumerate(p.discard):
        card = game.db.get(cid)
        if card.name == "Clefairy Doll":
            p.discard.pop(i)
            p.bench.append(PokemonSlot(
                pokemon_stack=[cid],
                turn_played=game.state.turn,
            ))
            game._log(f"  Placed Clefairy Doll on bench as a Pokémon (10 HP)", player=player_idx)
            return True
    return False


@register_trainer_by_name("Mysterious Fossil")
def mysterious_fossil(game: "Game", player_idx: int) -> bool:
    """Play as Basic Pokemon with 10 HP. Can evolve into Fossil Pokemon."""
    p = game.state.players[player_idx]
    if len(p.bench) >= 5:
        return False
    for i, cid in enumerate(p.discard):
        card = game.db.get(cid)
        if card.name == "Mysterious Fossil":
            p.discard.pop(i)
            p.bench.append(PokemonSlot(
                pokemon_stack=[cid],
                turn_played=game.state.turn,
            ))
            game._log(f"  Placed Mysterious Fossil on bench as a Pokémon (10 HP)", player=player_idx)
            return True
    return False
