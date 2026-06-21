"""Run Mafia 2.0 locally from the command line (no Discord bot required)."""

from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

from bootstrap import install_discord_stub

install_discord_stub()

from cli_engine import run_game
from local_setup import build_game
from scenario import get_scenario


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play-test Mafia 2.0 locally via CLI (no Discord connection)."
    )
    parser.add_argument(
        "--scenario",
        default="seven_players",
        help="Starting scenario name (default: seven_players)",
    )
    args = parser.parse_args()

    scenario = get_scenario(args.scenario)
    game, guild, broadcaster = build_game(scenario)

    print(f"\nLoaded scenario: {scenario['name']}")
    print(scenario["description"])
    print("Type 'help' for commands.\n")

    run_game(game, guild, broadcaster)


if __name__ == "__main__":
    main()
