"""
commands.py [CORRECTED for rustplus 6.x API]
────────────────────────────────────────────────────────────────────────────
All !rust command handlers with proper API attribute access.
"""

import logging
import json as _json
import time as _time_module
from pathlib import Path as _Path
from rustplus import RustError
from server_manager import ServerManager

log = logging.getLogger("Commands")

# ── Event timestamp cache ─────────────────────────────────────────────────────
# Keyed by event type_id (int). Persisted so timestamps survive restarts.
_EVENT_CACHE_FILE = _Path("event_timestamps.json")

def _load_event_cache() -> dict:
    try:
        if _EVENT_CACHE_FILE.exists():
            raw = _json.loads(_EVENT_CACHE_FILE.read_text())
            cutoff = _time_module.time() - 7200  # discard entries older than 2 hours
            return {int(k): float(v) for k, v in raw.items() if float(v) >= cutoff}
    except Exception:
        pass
    return {}

def _save_event_cache(cache: dict):
    try:
        _EVENT_CACHE_FILE.write_text(_json.dumps({str(k): v for k, v in cache.items()}))
    except Exception:
        pass

_event_first_seen: dict = _load_event_cache()


async def handle_query(query: str, manager: ServerManager) -> str:
    """Route a !rust query to the right handler."""
    parts = query.strip().split(None, 1)
    cmd   = parts[0].lower()
    args  = parts[1] if len(parts) > 1 else ""

    if cmd == "servers":
        return cmd_servers(manager)
    if cmd == "switch":
        return await cmd_switch(args, manager)
    if cmd == "help":
        return cmd_help()

    live_cmds = {"status", "info", "players", "online", "time",
                 "map", "team", "events", "wipe"}

    if cmd in live_cmds:
        active = manager.get_active()
        if not active:
            return (
                "No server connected.\n"
                "Join a Rust server and press **ESC -> Session -> Pairing**."
            )
        try:
            await manager.ensure_connected()
            socket = manager.get_socket()
            return await _dispatch_live(cmd, socket, active)
        except Exception as e:
            log.error(f"Live command error: {e}", exc_info=True)
            return (
                f"Couldn't reach Rust+ server: `{e}`\n"
                "The server may be offline or App Port may be blocked."
            )

    return cmd_game_question(query)


# ── Meta Commands ─────────────────────────────────────────────────────────────
def cmd_servers(manager: ServerManager) -> str:
    servers = manager.list_servers()
    active  = manager.get_active()

    if not servers:
        return (
            "**No servers paired yet.**\n"
            "Join any Rust server and press **ESC -> Session -> Pairing**."
        )

    lines = []
    for i, s in enumerate(servers, 1):
        is_active = active and s["ip"] == active["ip"] and s["port"] == active["port"]
        marker = "active" if is_active else f"{i}."
        lines.append(f"`{marker}` **{s.get('name', s['ip'])}** — `{s['ip']}:{s['port']}`")

    return "**Your Paired Servers:**\n" + "\n".join(lines) + \
        "\n\nUse `!rust switch <name or number>` to switch."


async def cmd_switch(identifier: str, manager: ServerManager) -> str:
    if not identifier:
        return "Usage: `!rust switch <server name or number>`"

    server = manager.switch_to(identifier)
    if not server:
        return f"No server found matching `{identifier}`."

    try:
        await manager.connect(server["ip"], server["port"])
        return f"Switched to **{server.get('name', server['ip'])}**"
    except Exception as e:
        return f"Could not connect: `{e}`"


def cmd_help() -> str:
    return (
        "**Rust+ Companion Bot** — prefix: `!rust`\n\n"
        "**Live Commands:**\n"
        "`status` — Server name, players, map, wipe\n"
        "`players` — Online player count\n"
        "`time` — In-game time\n"
        "`map` — Seed, size + RustMaps link\n"
        "`team` — Team members & status\n"
        "`events` — Active map events\n"
        "`wipe` — Last wipe date\n\n"
        "**Multi-Server:**\n"
        "`servers` — List all paired servers\n"
        "`switch <n>` — Switch servers\n\n"
        "**Q&A:**\n"
        "`!rust <question>` — Ask about Rust!\n"
        "_e.g. `!rust how much sulfur for a stone wall?`_"
    )


# ── Live Stat Dispatcher ──────────────────────────────────────────────────────
async def _dispatch_live(cmd: str, socket, active: dict) -> str:
    name = active.get("name", active["ip"])

    if cmd in ("status", "info"):
        return await _cmd_status(socket, name)
    if cmd in ("players", "online"):
        return await _cmd_players(socket, name)
    if cmd == "time":
        return await _cmd_time(socket, name)
    if cmd == "map":
        return await _cmd_map(socket, active)
    if cmd == "team":
        return await _cmd_team(socket)
    if cmd == "events":
        return await _cmd_events(socket, name)
    if cmd == "wipe":
        return await _cmd_wipe(socket, name)
    return "Unknown command."


async def _cmd_status(socket, name: str) -> str:
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"

    queued = f" ({info.queued_players} queued)" if info.queued_players else ""
    return (
        f"**{name}**\n"
        f"> **Players:** {info.players}/{info.max_players}{queued}\n"
        f"> **Map:** {info.map}  |  **Size:** {info.size}  |  **Seed:** `{info.seed}`\n"
        f"> **Wipe:** {_fmt_ts(info.wipe_time)}"
    )


async def _cmd_players(socket, name: str) -> str:
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"

    queued = f"\n> {info.queued_players} in queue" if info.queued_players else ""
    return f"**{name}**\n> {info.players}/{info.max_players} players{queued}"


async def _cmd_time(socket, name: str) -> str:
    time = await socket.get_time()
    if isinstance(time, RustError):
        return f"Error: {time.reason}"

    return (
        f"**{name} — In-Game Time**\n"
        f"> **Now:** {_fmt_time(time.time)}\n"
        f"> **Sunrise:** {_fmt_time(time.sunrise)}  |  **Sunset:** {_fmt_time(time.sunset)}"
    )


async def _cmd_map(socket, active: dict) -> str:
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"

    name = active.get("name", active["ip"])
    url  = f"https://rustmaps.com/map/{info.size}_{info.seed}"
    return (
        f"**{name}**\n"
        f"> **Map:** {info.map}  |  **Seed:** `{info.seed}`  |  **Size:** {info.size}\n"
        f"> [View on RustMaps]({url})"
    )


async def _cmd_team(socket) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"

    if not team.members:
        return "No team members found. Are you in a team in-game?"

    lines = []
    for m in team.members:
        status = "Online" if m.is_online else "Offline"
        alive  = "" if m.is_alive else " — Dead"
        lines.append(f"> **{m.name}** — {status}{alive}")
    return f"**Team ({len(team.members)} members)**\n" + "\n".join(lines)


async def _cmd_events(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    EVENT_TYPES = {
        1: "Explosion",
        3: "Patrol Helicopter",
        4: "Cargo Ship",
        6: "Locked Crate",
        7: "Chinook CH-47",
    }

    # The API emits many marker objects per physical event (one per player
    # tracking it, per damage ring, etc.). Deduplicate by type_id only —
    # there is at most one of each event type active at a time on a server.
    active_types: set = set()
    for m in markers:
        if m.type in EVENT_TYPES:
            active_types.add(m.type)

    if not active_types:
        return f"**{name}** — No active events right now."

    now = _time_module.time()

    # Record first-seen timestamp per type (only written once, on first appearance)
    for type_id in active_types:
        if type_id not in _event_first_seen:
            _event_first_seen[type_id] = now

    # Remove types no longer on the map
    for type_id in list(_event_first_seen):
        if type_id not in active_types:
            del _event_first_seen[type_id]

    _save_event_cache(_event_first_seen)

    lines = []
    for type_id in sorted(active_types):
        label     = EVENT_TYPES[type_id]
        elapsed_s = int(now - _event_first_seen[type_id])
        if elapsed_s < 60:
            age = f"{elapsed_s}s"
        else:
            age = f"{elapsed_s // 60}m {elapsed_s % 60}s"
        lines.append(f"> **{label}** — active for {age}")

    return f"**{name} — Active Events**\n" + "\n".join(lines)


async def _cmd_wipe(socket, name: str) -> str:
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"

    return f"**{name}** — Last wipe: **{_fmt_ts(info.wipe_time)}**"


# ── Game Q&A ──────────────────────────────────────────────────────────────────
def cmd_game_question(query: str) -> str:
    q = query.lower()

    qa = {
        ("sulfur", "stone", "wall"): (
            "**Stone Wall Raid Cost:**\n"
            "> Satchels: **10** | C4: **2** | Rockets: **4**\n"
            "> Sulfur: ~1,500"
        ),
        ("sulfur", "sheet", "metal"): (
            "**Sheet Metal Wall:**\n"
            "> Satchels: **4** | C4: **1** | Rockets: **2**\n"
            "> Sulfur: ~1,000"
        ),
        ("sulfur", "armored"): (
            "**Armored Wall:**\n"
            "> C4: **4** | Rockets: **8** | Satchels: **12**\n"
            "> Sulfur: ~4,000"
        ),
        ("sulfur", "smelt", "fast"): (
            "**Fast Sulfur Smelting:**\n"
            "> Use **Large Furnace** (~3x faster)\n"
            "> Optimal mix: 3 sulfur ore per 1 wood\n"
            "> Stack multiple furnaces"
        ),
        ("scrap", "farm"): (
            "**Best Scrap Farming:**\n"
            "> **Tier 1 monuments** (Gas Station, Supermarket) — safe & quick\n"
            "> Recycle components for bulk scrap\n"
            "> **Oil Rig** = massive scrap (high risk)"
        ),
        ("best", "weapon", "early"): (
            "**Best Early Weapons:**\n"
            "> 1. **Bow** — free, great for farming & PvP\n"
            "> 2. **Crossbow** — silent, strong\n"
            "> 3. **Pipe Shotgun** — one-shot close range"
        ),
        ("ak", "assault rifle"): (
            "**AK-47:**\n"
            "> Workbench Lvl 3 required\n"
            "> Costs: 1 HQM + 200 Metal + 4 Springs\n"
            "> Recoil is hard — practice on aim servers!"
        ),
        ("starter", "base"): (
            "**Starter Base:**\n"
            "> 1. 2x1 or 2x2 stone with **airlock**\n"
            "> 2. Place **TC** in sealed room first\n"
            "> 3. Use **triangle** foundations\n"
            "> 4. Stone up ASAP (wood burns)"
        ),
        ("helicopter", "heli"): (
            "**Patrol Helicopter:**\n"
            "> Weak spots: main & tail rotors\n"
            "> ~800 HV rifle rounds solo\n"
            "> Drops **2 Elite Crates**"
        ),
        ("bradley", "apc"): (
            "**Bradley APC:**\n"
            "> Location: Launch Site\n"
            "> Use **HV rockets** or 40mm HE\n"
            "> Stay mobile — 360 degree turret\n"
            "> Drops **3 Bradley Crates**"
        ),
        ("cargo", "ship"): (
            "**Cargo Ship:**\n"
            "> Spawns ~every 2 hours\n"
            "> 2 locked crates drop every ~15min\n"
            "> Heavy scientists — bring armor!"
        ),
        ("radiation", "suit"): (
            "**Radiation Protection:**\n"
            "> Gas Station/Supermarket: 4 RAD\n"
            "> Airfield: 10 RAD\n"
            "> Water Treatment: 15 RAD\n"
            "> Launch Site: 50 RAD (full Hazmat needed)"
        ),
    }

    for keywords, answer in qa.items():
        if all(kw in q for kw in keywords):
            return answer

    return (
        f"No answer for: *\"{query}\"*\n\n"
        "Try: `status` - `players` - `time` - `team` - `events`\n\n"
        "Or check:\n"
        "> [Rust Wiki](https://wiki.facepunch.com/rust/)\n"
        "> [RustMaps](https://rustmaps.com)"
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_time(t) -> str:
    if isinstance(t, str):
        try:
            parts = t.split(":")
            h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        except Exception:
            return t
    try:
        h = int(float(t))
        m = int((float(t) - h) * 60)
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return str(t)


def _fmt_ts(ts: int) -> str:
    from datetime import datetime, timezone
    if not ts:
        return "Unknown"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d, %Y")
    except Exception:
        return str(ts)