"""Build a GameState from a scenario definition."""

from __future__ import annotations

import sys
from pathlib import Path

from bootstrap import install_discord_stub

install_discord_stub()

MAFIA_ROOT = Path(__file__).resolve().parent.parent / "Mafia_2.0"
if str(MAFIA_ROOT) not in sys.path:
    sys.path.insert(0, str(MAFIA_ROOT))

from gamestate import GameState
from player import Player

from mock_guild import MockChannel, MockGuild, MockMember, MockRole, ConsoleBroadcaster


def build_game(scenario: dict) -> tuple[GameState, MockGuild, ConsoleBroadcaster]:
    broadcaster = ConsoleBroadcaster()
    guild = MockGuild(broadcaster)
    game = GameState()

    town = guild._register(MockChannel("courtyard", broadcaster))
    dead = guild._register(MockChannel("dead-chat", broadcaster))
    mafia = guild._register(MockChannel("mafia-chat", broadcaster))

    game.town_channel_id = town.id
    game.dead_channel_id = dead.id
    game.mafia_channel_id = mafia.id

    dead_role = MockRole(id=99, name="Dead")
    guild.roles[dead_role.id] = dead_role
    game.dead_role_id = dead_role.id

    next_id = 100
    for index, spec in enumerate(scenario["players"], start=1):
        member = MockMember(id=next_id, display_name=spec["name"])
        next_id += 1

        player = Player(member)
        player.number = index
        player.role = spec["role"]
        player.originalRole = spec["role"]

        game.players[player.id] = player
        player_channel = guild._register(
            MockChannel(spec["name"].lower().replace(" ", "-"), broadcaster)
        )
        will_channel = guild._register(
            MockChannel(f"{spec['name'].lower().replace(' ', '-')}-will", broadcaster)
        )
        game.player_channels[player.id] = player_channel.id
        game.player_will_channels[player.id] = will_channel.id

    executioner_target = scenario.get("executioner_target")
    if executioner_target is not None:
        for player in game.players.values():
            if player.role == "Executioner":
                target = _player_by_number(game, executioner_target)
                if target:
                    player.executioner_target = target.id

    game.running = True
    game.is_day = True
    game.day_number = 1
    game.can_vote = True

    return game, guild, broadcaster


def _player_by_number(game: GameState, number: int) -> Player | None:
    return next((p for p in game.players.values() if p.number == number), None)
