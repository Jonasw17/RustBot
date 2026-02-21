"""
Wraps the `rustplus` Python library (pip install rustplus) to provide
clean async access to Rust+ Companion API data:
  - Server info, time, map, team, markers (events)
  - Auto-reconnect on disconnect
  - Chat message streaming for the relay feature
"""

import asyncio
import os
import logging
from dataclasses import dataclass
from typing import Optional

from rustplus import RustSocket, ServerDetails, RustMarker
from dotenv import load_dotenv
from rustplus.structs import RustTime, RustTeamInfo, RustInfo

load_dotenv()
log = logging.getLogger("RustClient")


# ── Data Classes ──────────────────────────────────────────────────────────────
@dataclass
class ServerInfo:
    name: str
    players: int
    max_players: int
    queued_players: int
    map: str
    size: int
    seed: int
    wipe_time: str


@dataclass
class TimeInfo:
    raw: float
    sunrise: float
    sunset: float

    @property
    def formatted(self) -> str:
        return _fmt_rust_time(self.raw)

    @property
    def sunrise_formatted(self) -> str:
        return _fmt_rust_time(self.sunrise)

    @property
    def sunset_formatted(self) -> str:
        return _fmt_rust_time(self.sunset)


@dataclass
class TeamMember:
    name: str
    steam_id: int
    is_online: bool
    is_alive: bool
    x: float
    y: float


# ── Main Client ───────────────────────────────────────────────────────────────
class RustClient:
    """
    Manages the persistent WebSocket connection to your Rust+ server.
    Uses environment variables for credentials:
        RUST_SERVER_IP, RUST_APP_PORT, RUST_STEAM_ID, RUST_PLAYER_TOKEN
    """

    def __init__(self):
        self._ip    = os.getenv("RUST_SERVER_IP")
        self._port  = int(os.getenv("RUST_APP_PORT", "28017"))
        self._steam = int(os.getenv("RUST_STEAM_ID", "0"))
        self._token = int(os.getenv("RUST_PLAYER_TOKEN", "0"))

        self._socket: Optional[RustSocket] = None
        self._connected = False
        self._chat_callbacks: list = []

    # ── Connection ────────────────────────────────────────────────────────────
    async def connect(self):
        """Connect to the Rust+ WebSocket. Raises on failure."""
        if not all([self._ip, self._steam, self._token]):
            raise ValueError(
                "Missing Rust+ credentials. Set RUST_SERVER_IP, "
                "RUST_STEAM_ID, and RUST_PLAYER_TOKEN in your .env"
            )

        log.info(f"Connecting to Rust+ at {self._ip}:{self._port} ...")

        self._socket = RustSocket(
            self._ip,
            str(self._port),
            self._steam,
            self._token,
            raise_ratelimit_exception=False,   # Silently back off on rate limits
        )

        await self._socket.connect()
        self._connected = True
        log.info("Rust+ connected [OK]")

        # Register chat callback for relay
        @self._socket.on_team_message
        async def on_chat(message):
            for cb in self._chat_callbacks:
                await cb(message)

    async def ensure_connected(self):
        """Reconnect if the socket has dropped."""
        if not self._connected or self._socket is None:
            log.info("Rust+ not connected — reconnecting...")
            await self.connect()

    async def disconnect(self):
        if self._socket:
            await self._socket.disconnect()
            self._connected = False

    # ── API Methods ───────────────────────────────────────────────────────────
    async def get_info(self) -> ServerInfo:
        """Fetch server info (name, players, map, seed, wipe time)."""
        info: RustInfo = await self._socket.get_info()
        return ServerInfo(
            name=info.name,
            players=info.players,
            max_players=info.max_players,
            queued_players=info.queued_players,
            map=info.map,
            size=info.size,
            seed=info.seed,
            wipe_time=_fmt_timestamp(info.wipe_time),
        )

    async def get_time(self) -> TimeInfo:
        """Fetch the current in-game time."""
        t: RustTime = await self._socket.get_time()
        return TimeInfo(
            raw=t.time,
            sunrise=t.sunrise,
            sunset=t.sunset,
        )

    async def get_team(self) -> list[TeamMember]:
        """Fetch your team members and their online/alive status."""
        team: RustTeamInfo = await self._socket.get_team_info()
        return [
            TeamMember(
                name=m.name,
                steam_id=m.steam_id,
                is_online=m.is_online,
                is_alive=m.is_alive,
                x=m.x,
                y=m.y,
            )
            for m in team.members
        ]

    async def get_events(self) -> list[str]:
        """Return a list of human-readable active map events."""
        markers: list[RustMarker] = await self._socket.get_markers()

        event_map = {
            1: "[Explosion] Explosion",
            3: "[Heli] Patrol Helicopter",
            4: "[Ship] Cargo Ship",
            6: "[Crate] Locked Crate (Chinook drop)",
            7: "[Chinook] Chinook CH-47",
        }
        # Type 2 = Vending Machine, Type 5 = Player base — skip those
        events = [
            event_map[m.type]
            for m in markers
            if m.type in event_map
        ]
        return events

    async def get_raw_chat(self, count: int = 20) -> list:
        """Fetch recent team chat messages."""
        return await self._socket.get_team_chat()

    # ── Chat Relay ────────────────────────────────────────────────────────────
    def on_chat_message(self, callback):
        """Register an async callback for incoming team chat messages."""
        self._chat_callbacks.append(callback)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_rust_time(t: float) -> str:
    """Convert a Rust float time (e.g. 14.5) to 12-hour format (2:30 PM)."""
    hour = int(t)
    minute = int((t - hour) * 60)
    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {ampm}"


def _fmt_timestamp(ts: int) -> str:
    """Convert a Unix timestamp to a human-readable date string."""
    from datetime import datetime, timezone
    if not ts:
        return "Unknown"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(ts)