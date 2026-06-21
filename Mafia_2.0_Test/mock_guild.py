"""Minimal stand-ins for Discord guild/channel objects used by Mafia_2.0."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockMember:
    id: int
    display_name: str

    async def add_roles(self, role) -> None:
        pass


@dataclass
class MockRole:
    id: int = 1
    name: str = "Dead"
    members: list = field(default_factory=list)


@dataclass
class MockMessage:
    async def edit(self, **kwargs) -> None:
        pass

    async def delete(self) -> None:
        pass


class MockChannel:
    _next_id = 1000

    def __init__(self, name: str, broadcaster: "ConsoleBroadcaster"):
        self.id = MockChannel._next_id
        MockChannel._next_id += 1
        self.name = name
        self._broadcaster = broadcaster
        self.overwrites: dict = {}

    async def send(self, content=None, view=None, **kwargs) -> MockMessage:
        if content:
            label = self.name.upper() if self.name != "courtyard" else "TOWN"
            self._broadcaster.broadcast(label, content)
        return MockMessage()

    async def purge(self, limit: int = 100) -> None:
        pass

    async def set_permissions(self, *args, **kwargs) -> None:
        pass

    async def edit(self, overwrites=None, **kwargs) -> None:
        if overwrites is not None:
            self.overwrites = dict(overwrites)


class MockGuild:
    def __init__(self, broadcaster: "ConsoleBroadcaster"):
        self.default_role = MockRole()
        self.me = MockMember(0, "Bot")
        self.text_channels: list[MockChannel] = []
        self.roles: dict[int, MockRole] = {}
        self._channels: dict[int, MockChannel] = {}
        self._broadcaster = broadcaster

    def _register(self, channel: MockChannel) -> MockChannel:
        self._channels[channel.id] = channel
        self.text_channels.append(channel)
        return channel

    def get_channel(self, channel_id: int | None) -> MockChannel | None:
        if channel_id is None:
            return None
        return self._channels.get(channel_id)

    def get_role(self, role_id: int | None) -> MockRole | None:
        if role_id is None:
            return None
        return self.roles.get(role_id)


class ConsoleBroadcaster:
    """Prints in-game announcements to the terminal."""

    def broadcast(self, source: str, message: str) -> None:
        print(f"\n[{source}] {message}")

    def section(self, title: str) -> None:
        print(f"\n{'=' * 60}")
        print(title)
        print('=' * 60)
