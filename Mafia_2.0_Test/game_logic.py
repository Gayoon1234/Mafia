"""Pure game logic copied from Mafia_2.0 (no Discord UI imports)."""

from __future__ import annotations

import sys
from pathlib import Path

from bootstrap import install_discord_stub

install_discord_stub()

MAFIA_ROOT = Path(__file__).resolve().parent.parent / "Mafia_2.0"
if str(MAFIA_ROOT) not in sys.path:
    sys.path.insert(0, str(MAFIA_ROOT))

from gamestate import GameState
from player import Player, Role
from utils import getByRole, get_target

townsFolk = " is a member of the Townsfolk.\n"
mafia = " is a member of the Mafia.\n"


def get_role_description(role: Role | None) -> str:
    if role == "Doctor":
        return "The Doctor" + townsFolk + "The Doctor can select one Player to heal each night (including yourself)."
    if role == "Mafioso":
        return "The Mafioso" + mafia + "The Mafioso can select one Player to murder each night.\n"
    if role == "Framer":
        return "The Framer" + mafia + "The Framer can select one Player to frame each night.\n"
    if role == "Janitor":
        return "The Janitor" + mafia + "The Janitor can select one Player to clean each night.\n"
    if role == "Escort":
        return "The Escort" + townsFolk + "The Escort can roleblock one Player each night.\n"
    if role == "Detective":
        return "The Detective" + townsFolk + "The Detective investigates one Player each night.\n"
    if role == "Medium":
        return "The Medium" + townsFolk + "The Medium can speak to the dead at night."
    if role == "Towny":
        return "The Towny" + townsFolk + "They do not have any special roles."
    if role == "Jailor":
        return "The Jailor" + townsFolk + "Jail someone during the day; execute them at night."
    if role == "Executioner":
        return "The Executioner wins by getting their target lynched."
    if role == "Jester":
        return "The Jester wins by getting lynched, then may kill a guilty voter."
    if role == "Mayor":
        return "The Mayor" + townsFolk + "Reveal during the day for triple vote weight."
    if role == "Serial Killer":
        return "The Serial Killer wins by being the last killer standing."
    if role == "Survivor":
        return "The Survivor wins by staying alive until the end."
    if role == "Veteran":
        return "The Veteran" + townsFolk + "Go on alert up to 3 times to kill visitors."
    return f"No description for role: {role}"


def get_action_description(game: GameState, player: Player) -> str | None:
    role = player.role
    if role == "Doctor":
        return "Who would you like to heal?"
    if role == "Mafioso":
        return "Who would you like to murder?"
    if role == "Framer":
        return "Who would you like to frame?"
    if role == "Janitor":
        return "Who would you like to clean?"
    if role == "Escort":
        return "Who would you like to escort?"
    if role == "Detective":
        return "Who would you like to investigate?"
    if role == "Serial Killer":
        return "Who would you like to kill?"
    if role == "Jester" and len(player.guiltyVoters) > 0 and not player.alive:
        return "Who would you like to seek revenge on?"
    if role in ("Veteran", "Survivor"):
        return f"You have {player.alerts} alerts remaining."
    return None


async def calculate_results(guild, game: GameState):
    """Night resolution — same logic as Mafia_2.0/dayNight.calculateResults."""
    deaths = []
    blocked = set()
    healed = set()
    attacked = []
    veteran_guard = False
    death_by_veteran = " was shot in the chest last night!"

    def is_dead(player: Player):
        return any(v_id == player.id for v_id, _, _ in deaths)

    def is_blocked(player: Player):
        return player.id in blocked

    def is_attacked(player: Player):
        return any(v_id == player.id for v_id, _, _ in attacked)

    def is_dead_or_blocked(player: Player):
        return is_dead(player) or is_blocked(player) or is_attacked(player)

    def visit_vet(visitor: Player, target: Player):
        if target.role == "Veteran" and veteran_guard:
            attacked.append((visitor.id, death_by_veteran, target.murderNote))
            return True
        return False

    jester, target = get_target(game, "Jester")
    if jester and target:
        deaths.append((target.id, " is dead! The Jester gets their revenge from the grave!", jester.murderNote))

    jailor, jailor_target = get_target(game, "Jailor")
    if jailor and jailor_target and not is_dead_or_blocked(jailor):
        blocked.add(jailor_target.id)
        if jailor.willExecute:
            deaths.append(
                (jailor_target.id, " was executed by the Jailor. Has justice been served?", jailor.murderNote)
            )

    def visitor_check(player, target):
        if is_dead(player) or is_blocked(player) or is_attacked(player):
            return False
        if jailor_target and target.id == jailor_target.id:
            return False
        return not visit_vet(player, target)

    veteran = getByRole(game.players, "Veteran")
    if veteran and veteran.onAlert and not is_dead_or_blocked(veteran):
        veteran_guard = True

    escort, target = get_target(game, "Escort")
    if escort and target and visitor_check(escort, target):
        blocked.add(target.id)
        if target.role == "Serial Killer":
            attacked.append(
                (escort.id, " was horrifically stabbed to death while out visiting last night!", target.murderNote)
            )
            will_channel_id = game.player_will_channels.get(escort.id)
            if will_channel_id:
                will_channel = guild.get_channel(will_channel_id)
                if will_channel:
                    await will_channel.purge(limit=100)

    doctor, target = get_target(game, "Doctor")
    if doctor and target and visitor_check(doctor, target):
        healed.add(target.id)

    survivor = getByRole(game.players, "Survivor")
    if survivor and not is_dead_or_blocked(survivor) and survivor.onAlert:
        healed.add(survivor.id)

    mafioso, target = get_target(game, "Mafioso")
    if mafioso and target and visitor_check(mafioso, target):
        attacked.append((target.id, " was murdered last night!", mafioso.murderNote))

    sk, target = get_target(game, "Serial Killer")
    if sk and target and visitor_check(sk, target):
        attacked.append((target.id, " was murdered last night!", sk.murderNote))

    framer, target = get_target(game, "Framer")
    if framer and target and visitor_check(framer, target):
        target.framed = True

    detective, target = get_target(game, "Detective")
    if detective:
        if not target or is_dead_or_blocked(detective):
            detective.targetInfo = "You either did not select anyone to investigate last night, or were blocked"
        elif jailor_target and target.id == jailor_target.id:
            detective.targetInfo = "Your target was in jail last night, you were unable to investigate them"
        else:
            if not visit_vet(detective, target):
                bloody = (
                    target.role in ["Doctor", "Mafioso", "Serial Killer"]
                    or target.framed
                    or is_attacked(target)
                    or is_dead(target)
                )
                if bloody:
                    detective.targetInfo = f"Your target, {target.name}, had blood on them last night."
                    target.framed = False
                else:
                    detective.targetInfo = f"Your target, {target.name}, did NOT have blood on them last night."

    can_janitor_clean = False
    janitor, janitor_target = get_target(game, "Janitor")
    if janitor and janitor_target:
        can_janitor_clean = visitor_check(janitor, janitor_target)

    for victim_id, msg, note in attacked:
        if victim_id not in healed:
            deaths.append((victim_id, msg, note))

    if can_janitor_clean and janitor_target:
        dead_ids = {victim_id for victim_id, _, _ in deaths}
        if janitor_target.id in dead_ids:
            janitor_target.cleaned = True
            janitor_target.role = "CLEANED"

    return deaths


def tally_votes(game: GameState):
    vote_count = {}
    for voter in game.players.values():
        if not voter.alive or voter.vote is None:
            continue
        weight = 3 if voter.role == "Mayor" and voter.revealed else 1
        vote_count[voter.vote] = vote_count.get(voter.vote, 0) + weight

    alive_players = [p for p in game.players.values() if p.alive]
    alive_count = len(alive_players)
    if alive_count == 0:
        return None

    majority_needed = (alive_count // 2) + 1
    for player_id, count in vote_count.items():
        if count >= majority_needed:
            return game.players.get(player_id)
    return None


def get_voted_for_player(game: GameState):
    return next((p for p in game.players.values() if p.votedFor), None)
