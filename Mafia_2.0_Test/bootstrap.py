"""Install a minimal discord module stub so Mafia_2.0 imports work without discord.py."""

from __future__ import annotations

import sys
import types


class _Stub:
    """Accepts any constructor args; attribute access returns more stubs."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __call__(self, *args, **kwargs) -> "_Stub":
        return _Stub()

    def __getattr__(self, name: str) -> "_Stub":
        return _Stub()

    def __iter__(self):
        return iter([])


def install_discord_stub() -> None:
    if "discord" in sys.modules:
        return

    discord = types.ModuleType("discord")

    class Intents(_Stub):
        @staticmethod
        def default():
            return Intents()

    class Client(_Stub):
        pass

    class PermissionOverwrite(_Stub):
        pass

    class TextChannel(_Stub):
        pass

    class Thread(_Stub):
        pass

    discord.Intents = Intents
    discord.Client = Client
    discord.PermissionOverwrite = PermissionOverwrite
    discord.TextChannel = TextChannel
    discord.Thread = Thread

    def _discord_getattr(name: str) -> _Stub:
        return _Stub()

    discord.__getattr__ = _discord_getattr  # type: ignore[attr-defined]

    utils = types.ModuleType("discord.utils")

    def _utils_get(container, **kwargs):
        name = kwargs.get("name")
        if name and hasattr(container, "text_channels"):
            for channel in container.text_channels:
                if getattr(channel, "name", None) == name:
                    return channel
        return None

    utils.get = _utils_get
    discord.utils = utils

    ui = types.ModuleType("discord.ui")

    class View(_Stub):
        def add_item(self, item) -> None:
            pass

    class Select(_Stub):
        pass

    class SelectOption(_Stub):
        pass

    class Button(_Stub):
        pass

    class Modal(_Stub):
        pass

    ui.View = View
    ui.Select = Select
    ui.SelectOption = SelectOption
    ui.Button = Button

    def button(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    ui.button = button

    def _ui_getattr(name: str) -> _Stub:
        return _Stub()

    ui.__getattr__ = _ui_getattr  # type: ignore[attr-defined]
    discord.ui = ui

    ext = types.ModuleType("discord.ext")
    commands = types.ModuleType("discord.ext.commands")

    class Bot(_Stub):
        def command(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def event(self, func):
            return func

        def run(self, *args, **kwargs) -> None:
            pass

    commands.Bot = Bot
    ext.commands = commands
    discord.ext = ext

    sys.modules["discord"] = discord
    sys.modules["discord.utils"] = utils
    sys.modules["discord.ui"] = ui
    sys.modules["discord.ext"] = ext
    sys.modules["discord.ext.commands"] = commands
