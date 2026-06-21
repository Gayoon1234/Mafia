"""Local CLI game engine — drives day/night without Discord."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from bootstrap import install_discord_stub

install_discord_stub()

MAFIA_ROOT = Path(__file__).resolve().parent.parent / "Mafia_2.0"
if str(MAFIA_ROOT) not in sys.path:
    sys.path.insert(0, str(MAFIA_ROOT))

import scoring
import timing
from gamestate import GameState
from player import Player
from roleActions import getPossibleOptions
from utils import (
    checkWin,
    getByRole,
    getPlayerList,
    getPlayerListEndgame,
    handleMafiosoDeathTransfer,
    isMafia,
    kill,
    isGameOver,
)

from game_logic import (
    calculate_results,
    get_action_description,
    get_role_description,
    get_voted_for_player,
    tally_votes,
)
from mock_guild import ConsoleBroadcaster, MockGuild

HELP_TEXT = """
Commands:
  help                         Show this help
  list                         Show alive/dead players (roles hidden)
  roles                        Show all roles (testing cheat sheet)
  status                       Show phase, day number, pending trial

Day phase:
  vote <voter#> <target#>      Cast a trial vote (majority triggers trial)
  reveal <#>                   Mayor reveals publicly
  jail <jailor#> <target#>     Jailor selects someone to jail tonight
  night                        End day and enter night phase

Trial (when someone is on trial):
  decide <voter#> guilty|innocent
  resolve                      Resolve the trial

Night phase:
  target <actor#> <target#>    Set a night action target
  alert <#>                    Veteran/Survivor goes on alert
  execute <jailor#>            Jailor executes the jailed player
  note <#> <message>           Set a murder note before killing
  day                          Resolve night and start the next day

General:
  quit                         Exit the test runner
"""


class CliGameEngine:
    def __init__(self, game: GameState, guild: MockGuild, broadcaster: ConsoleBroadcaster):
        self.game = game
        self.guild = guild
        self.broadcaster = broadcaster
        self._noop_countdown()

    def _noop_countdown(self) -> None:
        async def instant_countdown(channel, seconds: int, prefix: str = "Countdown"):
            return None

        timing.countdown = instant_countdown

    def _noop_scoring(self) -> None:
        scoring.updateWins = lambda game: None

    def _player(self, number: int) -> Player | None:
        return next((p for p in self.game.players.values() if p.number == number), None)

    def _print_roles(self) -> None:
        ordered = sorted(self.game.players.values(), key=lambda p: p.number)
        print("\n--- Role sheet (testing only) ---")
        for p in ordered:
            status = "alive" if p.alive else "dead"
            extra = ""
            if p.role == "Executioner" and p.executioner_target:
                target = self.game.players[p.executioner_target]
                extra = f" -> target: {target.name}"
            print(f"  {p.number}. {p.name}: {p.role} ({status}){extra}")
        print("---------------------------------\n")

    def _print_night_prompts(self) -> None:
        can_target_roles = {
            "Mafioso", "Framer", "Janitor", "Jester", "Serial Killer",
            "Doctor", "Escort", "Detective",
        }
        print("\nNight actions available:")
        for player in sorted(self.game.players.values(), key=lambda p: p.number):
            if not player.alive:
                continue
            desc = get_action_description(self.game, player)
            if player.role in ("Veteran", "Survivor"):
                print(f"  {player.number}. {player.name} ({player.role}): {desc} — use 'alert {player.number}'")
            elif player.role == "Jailor":
                target_id = player.roundInput
                if target_id:
                    target = self.game.players[target_id]
                    print(f"  {player.number}. {player.name} (Jailor): jailed {target.name} — use 'execute {player.number}' to kill")
                else:
                    print(f"  {player.number}. {player.name} (Jailor): no one jailed")
            elif player.role in can_target_roles:
                options = getPossibleOptions(self.game, player)
                if options:
                    targets = ", ".join(f"{t.number}" for t in options)
                    print(f"  {player.number}. {player.name} ({player.role}): {desc} — targets: {targets}")
            elif player.role == "Medium":
                print(f"  {player.number}. {player.name} (Medium): can speak with dead (no action needed)")
            else:
                print(f"  {player.number}. {player.name} ({player.role}): no action")

    def _print_day_prompts(self) -> None:
        print("\nDay actions available:")
        for player in sorted(self.game.players.values(), key=lambda p: p.number):
            if not player.alive:
                continue
            if player.role == "Mayor" and not player.revealed:
                print(f"  {player.number}. {player.name} (Mayor): use 'reveal {player.number}'")
            if player.role == "Jailor":
                options = getPossibleOptions(self.game, player)
                if options:
                    targets = ", ".join(f"{t.number}" for t in options)
                    print(f"  {player.number}. {player.name} (Jailor): pick jail target — targets: {targets}")
        print("  Alive players can vote: vote <voter#> <target#>")

    async def run(self) -> None:
        self._noop_scoring()
        self.broadcaster.section(f"Game started — {len(self.game.players)} players")
        self._print_role_assignments()
        await self._start_day(first=True)

        while self.game.running:
            try:
                raw = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not raw:
                continue

            parts = raw.split()
            cmd = parts[0].lower()

            try:
                if cmd in ("quit", "exit", "q"):
                    break
                if cmd == "help":
                    print(HELP_TEXT)
                elif cmd == "list":
                    print(getPlayerList(self.game))
                elif cmd == "roles":
                    self._print_roles()
                elif cmd == "status":
                    self._print_status()
                elif cmd == "vote":
                    await self._cmd_vote(parts)
                elif cmd == "reveal":
                    self._cmd_reveal(parts)
                elif cmd == "jail":
                    self._cmd_jail(parts)
                elif cmd == "decide":
                    await self._cmd_decide(parts)
                elif cmd == "resolve":
                    await self._cmd_resolve()
                elif cmd == "target":
                    self._cmd_target(parts)
                elif cmd == "alert":
                    self._cmd_alert(parts)
                elif cmd == "execute":
                    self._cmd_execute(parts)
                elif cmd == "note":
                    self._cmd_note(parts)
                elif cmd in ("night", "n"):
                    await self._cmd_night()
                elif cmd in ("day", "d"):
                    await self._cmd_day()
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for commands.")
            except (ValueError, IndexError) as exc:
                print(f"Invalid command: {exc}")

        if not self.game.running:
            print("\nGame over.")

    def _print_status(self) -> None:
        phase = "DAY" if self.game.is_day else "NIGHT"
        print(f"Phase: {phase} {self.game.day_number} | running={self.game.running} | can_vote={self.game.can_vote}")
        accused = get_voted_for_player(self.game)
        if accused:
            print(f"On trial: {accused.name} (#{accused.number})")

    def _print_role_assignments(self) -> None:
        print("\nRole assignments (testing view):")
        self._print_roles()
        for player in self.game.players.values():
            print(f"\n--- {player.name} ({player.role}) ---")
            print(get_role_description(player.role))
            if isMafia(player):
                teammates = [p for p in self.game.players.values() if isMafia(p)]
                print("\nMafia team:")
                for mate in teammates:
                    print(f"  - {mate.name}: {mate.role}")
            if player.role == "Executioner" and player.executioner_target:
                target = self.game.players[player.executioner_target]
                print(f"\nYour target is: {target.name}")

    async def _start_day(self, first: bool = False) -> None:
        self.game.is_day = True
        self.broadcaster.section(f"Day {self.game.day_number}")

        if not first:
            deaths = await calculate_results(self.guild, self.game)
            await self._deliver_detective_results()
            await self._check_executioner_target_deaths(deaths)

            if deaths:
                self.broadcaster.broadcast("TOWN", "Night Results")
                for victim_id, msg, note in deaths:
                    victim = self.game.players[victim_id]
                    await self._kill(victim, f"**{victim.name}**{msg}", note)
            else:
                self.broadcaster.broadcast("TOWN", "Night Results — no one died last night.")

            for player in self.game.players.values():
                player.reset_round()

        print(getPlayerList(self.game))
        if await self._check_game_over():
            return

        self.game.can_vote = True
        self.broadcaster.broadcast("TOWN", "Discussion and voting are open.")
        self._print_day_prompts()

    async def _start_night(self) -> None:
        self.game.is_day = False
        self.broadcaster.section(f"Night {self.game.day_number}")
        print(getPlayerList(self.game))
        self.broadcaster.broadcast("TOWN", "Perform your night actions.")
        self._print_night_prompts()

    async def _cmd_vote(self, parts: list[str]) -> None:
        if not self.game.is_day:
            print("Voting is only available during the day.")
            return
        if not self.game.can_vote:
            print("Voting is closed — someone is on trial. Use 'decide' or 'resolve'.")
            return

        voter_num, target_num = int(parts[1]), int(parts[2])
        voter = self._player(voter_num)
        target = self._player(target_num)

        if voter is None or target is None:
            print("Invalid player number.")
            return
        if not voter.alive or not target.alive:
            print("Dead players cannot vote or be voted for.")
            return
        if voter.id == target.id:
            print("You cannot vote for yourself.")
            return

        voter.vote = target.id
        self.broadcaster.broadcast("TOWN", f"{voter.name} voted for {target.name}.")

        accused = tally_votes(self.game)
        if accused:
            accused.votedFor = True
            self.game.can_vote = False
            self.broadcaster.broadcast("TOWN", f"{accused.name} has been put on trial!")
            print(f"Use 'decide <voter#> guilty|innocent' then 'resolve'.")

    def _cmd_reveal(self, parts: list[str]) -> None:
        if not self.game.is_day:
            print("Mayor can only reveal during the day.")
            return
        player = self._player(int(parts[1]))
        if player is None:
            print("Invalid player number.")
            return
        if player.role != "Mayor":
            print(f"{player.name} is not the Mayor.")
            return
        if player.revealed:
            print("Mayor has already revealed.")
            return
        player.revealed = True
        self.broadcaster.broadcast("TOWN", f"{player.name} has revealed themselves as the Mayor! Their vote counts triple.")

    def _cmd_jail(self, parts: list[str]) -> None:
        if not self.game.is_day:
            print("Jailor selects targets during the day.")
            return
        jailor = self._player(int(parts[1]))
        target = self._player(int(parts[2]))
        if jailor is None or target is None:
            print("Invalid player number.")
            return
        if jailor.role != "Jailor":
            print(f"{jailor.name} is not the Jailor.")
            return
        options = getPossibleOptions(self.game, jailor)
        if target not in options:
            print("Invalid jail target.")
            return
        jailor.roundInput = target.id
        print(f"{jailor.name} will jail {target.name} tonight.")

    async def _cmd_decide(self, parts: list[str]) -> None:
        accused = get_voted_for_player(self.game)
        if accused is None:
            print("Nobody is on trial.")
            return

        voter = self._player(int(parts[1]))
        choice = parts[2].lower()
        if voter is None:
            print("Invalid player number.")
            return
        if not voter.alive or voter.votedFor:
            print("This player cannot cast a trial decision.")
            return
        if choice not in ("guilty", "innocent"):
            print("Choice must be 'guilty' or 'innocent'.")
            return

        voter.decision = choice
        self.broadcaster.broadcast("TOWN", f"{voter.name} voted {choice.upper()}.")

    async def _cmd_resolve(self) -> None:
        accused = get_voted_for_player(self.game)
        if accused is None:
            print("Nobody is on trial.")
            return
        self.game.canDecide = True
        await self._resolve_trial()

    async def _resolve_trial(self) -> None:
        self.game.canDecide = False
        guilty = 0
        innocent = 0
        lines = ["Trial Results:"]

        accused = get_voted_for_player(self.game)
        ordered = sorted(self.game.players.values(), key=lambda p: p.number)

        for p in ordered:
            if accused and p.id == accused.id:
                continue
            if p.decision is None:
                lines.append(f"  {p.name} abstained")
            else:
                weight = 3 if p.role == "Mayor" and p.revealed else 1
                if p.decision == "guilty":
                    lines.append(f"  {p.name} voted GUILTY")
                    guilty += weight
                elif p.decision == "innocent":
                    lines.append(f"  {p.name} voted INNOCENT")
                    innocent += weight

        print("\n".join(lines))

        if accused is None:
            print("No accused player found.")
            return

        if guilty > innocent:
            if accused.role == "Jester":
                guilty_voters = [
                    p.id
                    for p in ordered
                    if p.alive and p.decision != "innocent" and p.id != accused.id
                ]
                accused.guiltyVoters = guilty_voters
                accused.win = True
                self.broadcaster.broadcast(
                    "TOWN",
                    f"You FOOLS! {accused.name} is the Jester! They will seek revenge...",
                )
            else:
                self.broadcaster.broadcast(
                    "TOWN",
                    f"The town voted to lynch {accused.name}.",
                )

            executioner = getByRole(self.game.players, "Executioner")
            if executioner and executioner.executioner_target == accused.id:
                executioner.win = True
                self.broadcaster.broadcast(
                    "TOWN",
                    f"The Executioner has succeeded! {accused.name} was their target.",
                )

            await kill(self.guild, self.game, accused, f"{accused.name} was lynched.", None)
            await isGameOver(self.guild, self.game)
        else:
            self.game.can_vote = True
            self.broadcaster.broadcast("TOWN", f"{accused.name} has been spared.")

        for p in self.game.players.values():
            p.vote = None
            p.decision = None
            p.votedFor = False

    def _cmd_target(self, parts: list[str]) -> None:
        if self.game.is_day:
            print("Night targets are set during the night phase.")
            return
        actor = self._player(int(parts[1]))
        target = self._player(int(parts[2]))
        if actor is None or target is None:
            print("Invalid player number.")
            return
        options = getPossibleOptions(self.game, actor)
        if target not in options:
            print(f"{actor.name} cannot target {target.name}.")
            return
        actor.roundInput = target.id
        print(f"{actor.name} will target {target.name}.")

    def _cmd_alert(self, parts: list[str]) -> None:
        if self.game.is_day:
            print("Alert is a night action.")
            return
        player = self._player(int(parts[1]))
        if player is None:
            print("Invalid player number.")
            return
        if player.role not in ("Veteran", "Survivor"):
            print(f"{player.name} cannot go on alert.")
            return
        if player.alerts <= 0:
            print("No alerts remaining.")
            return
        player.onAlert = True
        player.alerts -= 1
        print(f"{player.name} is on alert ({player.alerts} remaining).")

    def _cmd_execute(self, parts: list[str]) -> None:
        if self.game.is_day:
            print("Jailor executes during the night.")
            return
        jailor = self._player(int(parts[1]))
        if jailor is None or jailor.role != "Jailor":
            print("Invalid Jailor.")
            return
        if jailor.roundInput is None:
            print("No one is jailed.")
            return
        jailor.willExecute = True
        target = self.game.players[jailor.roundInput]
        print(f"{jailor.name} will execute {target.name}.")

    def _cmd_note(self, parts: list[str]) -> None:
        player = self._player(int(parts[1]))
        if player is None:
            print("Invalid player number.")
            return
        if player.role not in ("Mafioso", "Serial Killer", "Jester", "Jailor"):
            print("This role cannot leave a murder note.")
            return
        player.murderNote = " ".join(parts[2:])
        print(f"Note saved for {player.name}.")

    async def _cmd_night(self) -> None:
        if not self.game.is_day:
            print("Already night. Use 'day' to resolve.")
            return
        if get_voted_for_player(self.game):
            print("Resolve the trial first with 'resolve'.")
            return
        await self._start_night()

    async def _cmd_day(self) -> None:
        if self.game.is_day:
            print("Already day. Use 'night' to enter the night phase.")
            return
        self.game.day_number += 1
        await self._start_day()

    async def _kill(self, player: Player, reason: str, note: str | None) -> None:
        player.alive = False
        janitor = getByRole(self.game.players, "Janitor")

        role_revealed = player.role
        if player.cleaned:
            self.broadcaster.broadcast("TOWN", f"{reason} Their role was hidden.")
        else:
            self.broadcaster.broadcast("TOWN", f"{reason} Their role was: {role_revealed}")

        if note:
            self.broadcaster.broadcast("TOWN", f"Their killer left this message: {note}")

        await handleMafiosoDeathTransfer(self.guild, self.game, player)

        if player.cleaned and janitor and janitor.alive:
            self.broadcaster.broadcast(
                janitor.name.upper(),
                f"You cleaned {player.name}. Role: {player.role}",
            )

    async def _deliver_detective_results(self) -> None:
        detective = getByRole(self.game.players, "Detective")
        if detective and detective.alive and detective.targetInfo:
            print(f"\n[DETECTIVE -> {detective.name}] {detective.targetInfo}")
            detective.targetInfo = None

    async def _check_executioner_target_deaths(self, deaths: list) -> None:
        executioner = getByRole(self.game.players, "Executioner")
        if executioner is None:
            return
        dead_ids = {death[0] for death in deaths}
        target_id = executioner.executioner_target
        if target_id is None or target_id not in dead_ids:
            return

        target = self.game.players[target_id]
        executioner.role = "Jester"
        executioner.executioner_target = None
        print(
            f"\n[{executioner.name}] Your target {target.name} died before being lynched. "
            "You are now the Jester — get yourself lynched to win."
        )

    async def _check_game_over(self) -> bool:
        game_won, message = checkWin(self.game)
        if not game_won:
            return False

        self.game.running = False
        self.broadcaster.broadcast("TOWN", message)
        print(getPlayerListEndgame(self.game))
        return True


def run_game(game: GameState, guild: MockGuild, broadcaster: ConsoleBroadcaster) -> None:
    engine = CliGameEngine(game, guild, broadcaster)
    asyncio.run(engine.run())
