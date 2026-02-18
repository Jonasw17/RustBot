"""
commands.py
────────────────────────────────────────────────────────────────────────────
All !rust command handlers.
"""

import logging
import json as _json
import time as _time_module
import re as _re
from pathlib import Path as _Path
from datetime import datetime, timezone
from rustplus import RustError
from server_manager import ServerManager

log = logging.getLogger("Commands")

# ── Bot start time (for !uptime) ──────────────────────────────────────────────
_BOT_START_TIME = _time_module.time()

# ── Event timestamp cache ─────────────────────────────────────────────────────
_EVENT_CACHE_FILE = _Path("event_timestamps.json")

def _load_event_cache() -> dict:
    try:
        if _EVENT_CACHE_FILE.exists():
            raw = _json.loads(_EVENT_CACHE_FILE.read_text())
            cutoff = _time_module.time() - 7200
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


# ── Router ────────────────────────────────────────────────────────────────────
async def handle_query(query: str, manager: ServerManager) -> str:
    parts = query.strip().split(None, 1)
    cmd   = parts[0].lower()
    args  = parts[1].strip() if len(parts) > 1 else ""

    # Meta commands
    if cmd in ("servers", "server"):
        return cmd_servers(manager)
    if cmd == "switch":
        return await cmd_switch(args, manager)
    if cmd == "help":
        return cmd_help()

    # Commands that need a live socket
    live_cmds = {
        "status", "info",
        "players", "online", "offline", "pop",
        "time",
        "map",
        "team",
        "events",
        "wipe",
        "uptime",
        "heli", "cargo", "chinook", "large", "small",
        "afk", "alive",
        "craft", "recycle", "research", "decay", "upkeep", "item",
        "cctv",
    }

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
            return await _dispatch_live(cmd, args, socket, active)
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
        tag = "`active`" if is_active else f"`{i}.`"
        lines.append(f"{tag} **{s.get('name', s['ip'])}** — `{s['ip']}:{s['port']}`")

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
        "**Server Info:**\n"
        "`status` · `players` · `pop` · `time` · `map` · `wipe` · `uptime`\n\n"
        "**Team:**\n"
        "`team` · `online` · `offline` · `afk` · `alive`\n\n"
        "**Events:**\n"
        "`events` · `heli` · `cargo` · `chinook` · `large` · `small`\n\n"
        "**Game Info:**\n"
        "`craft <item>` · `recycle <item>` · `research <item>` · `decay <item>` · `upkeep <item>` · `item <name>` · `cctv <monument>`\n\n"
        "**Multi-Server:**\n"
        "`servers` · `switch <name or #>`\n\n"
        "**Q&A:** `!rust <question>` — e.g. `!rust how much sulfur for a rocket?`"
    )


# ── Live Dispatcher ───────────────────────────────────────────────────────────
async def _dispatch_live(cmd: str, args: str, socket, active: dict) -> str:
    name = active.get("name", active["ip"])

    if cmd in ("status", "info"):     return await _cmd_status(socket, name)
    if cmd in ("players", "pop"):     return await _cmd_players(socket, name)
    if cmd == "online":               return await _cmd_online(socket)
    if cmd == "offline":              return await _cmd_offline(socket)
    if cmd == "afk":                  return await _cmd_afk(socket)
    if cmd == "alive":                return await _cmd_alive(socket, args)
    if cmd == "time":                 return await _cmd_time(socket, name)
    if cmd == "map":                  return await _cmd_map(socket, active)
    if cmd == "team":                 return await _cmd_team(socket)
    if cmd == "events":               return await _cmd_events(socket, name)
    if cmd == "wipe":                 return await _cmd_wipe(socket, name)
    if cmd == "uptime":               return _cmd_uptime(name)
    if cmd == "heli":                 return await _cmd_heli(socket, name)
    if cmd == "cargo":                return await _cmd_cargo(socket, name)
    if cmd == "chinook":              return await _cmd_chinook(socket, name)
    if cmd == "large":                return await _cmd_large(socket, name)
    if cmd == "small":                return await _cmd_small(socket, name)
    if cmd == "craft":                return _cmd_craft(args)
    if cmd == "recycle":              return _cmd_recycle(args)
    if cmd == "research":             return _cmd_research(args)
    if cmd == "decay":                return _cmd_decay(args)
    if cmd == "upkeep":               return _cmd_upkeep_item(args)
    if cmd == "item":                 return _cmd_item(args)
    if cmd == "cctv":                 return _cmd_cctv(args)
    return "Unknown command."


# ── Server Info ───────────────────────────────────────────────────────────────
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
    return f"**{name}**\n> {info.players}/{info.max_players} players online{queued}"


async def _cmd_wipe(socket, name: str) -> str:
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"
    elapsed = _fmt_elapsed(int(_time_module.time()) - info.wipe_time) if info.wipe_time else "Unknown"
    return f"**{name}** — Last wipe: **{_fmt_ts(info.wipe_time)}** ({elapsed} ago)"


def _cmd_uptime(name: str) -> str:
    elapsed = _fmt_elapsed(int(_time_module.time() - _BOT_START_TIME))
    return f"**Uptime**\n> Bot: {elapsed}\n> Server: `{name}`"


async def _cmd_time(socket, name: str) -> str:
    t = await socket.get_time()
    if isinstance(t, RustError):
        return f"Error: {t.reason}"
    now_f   = _time_to_float(t.time)
    sunrise = _time_to_float(t.sunrise)
    sunset  = _time_to_float(t.sunset)
    till_day   = _time_till(now_f, sunrise) if now_f < sunrise or now_f > sunset else None
    till_night = _time_till(now_f, sunset)  if sunrise <= now_f < sunset else None
    extra = f"\n> Till night: {till_night}" if till_night else (f"\n> Till day: {till_day}" if till_day else "")
    return (
        f"**{name} — In-Game Time**\n"
        f"> **Now:** {_fmt_time(t.time)}\n"
        f"> **Sunrise:** {_fmt_time(t.sunrise)}  |  **Sunset:** {_fmt_time(t.sunset)}"
        f"{extra}"
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


# ── Team ──────────────────────────────────────────────────────────────────────
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


async def _cmd_online(socket) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    online = [m for m in team.members if m.is_online]
    if not online:
        return "No team members currently online."
    return "**Online**\n" + "\n".join(f"> **{m.name}**" for m in online)


async def _cmd_offline(socket) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    offline = [m for m in team.members if not m.is_online]
    if not offline:
        return "All team members are online."
    return "**Offline**\n" + "\n".join(f"> **{m.name}**" for m in offline)


async def _cmd_afk(socket) -> str:
    """AFK = online but position hasn't been tracked as moving.
    Since we don't track historical positions, we report who is online
    and note that AFK detection requires position history."""
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    online = [m for m in team.members if m.is_online]
    if not online:
        return "No team members online."
    return (
            "**Online Team Members** (AFK detection requires position tracking over time)\n"
            + "\n".join(f"> **{m.name}**" for m in online)
    )


async def _cmd_alive(socket, args: str) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    alive = [m for m in team.members if m.is_alive]
    dead  = [m for m in team.members if not m.is_alive]
    if args:
        name_lower = args.lower()
        match = next((m for m in team.members if name_lower in m.name.lower()), None)
        if not match:
            return f"No team member found matching `{args}`."
        status = "Alive" if match.is_alive else "Dead"
        return f"**{match.name}** — {status}"
    lines = [f"> **{m.name}** — Alive" for m in alive] + \
            [f"> **{m.name}** — Dead" for m in dead]
    return f"**Team Status ({len(alive)}/{len(team.members)} alive)**\n" + "\n".join(lines)


# ── Events ────────────────────────────────────────────────────────────────────
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

    active_types: set = set()
    for m in markers:
        if m.type in EVENT_TYPES:
            active_types.add(m.type)

    if not active_types:
        return f"**{name}** — No active events right now."

    now = _time_module.time()
    for type_id in active_types:
        if type_id not in _event_first_seen:
            _event_first_seen[type_id] = now
    for type_id in list(_event_first_seen):
        if type_id not in active_types:
            del _event_first_seen[type_id]
    _save_event_cache(_event_first_seen)

    lines = []
    for type_id in sorted(active_types):
        label     = EVENT_TYPES[type_id]
        elapsed_s = int(now - _event_first_seen[type_id])
        age = f"{elapsed_s}s" if elapsed_s < 60 else f"{elapsed_s // 60}m {elapsed_s % 60}s"
        lines.append(f"> **{label}** — active for {age}")

    return f"**{name} — Active Events**\n" + "\n".join(lines)


async def _cmd_heli(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    helis = [m for m in markers if m.type == 3]
    if not helis:
        return f"**{name}** — No Patrol Helicopter on the map right now."
    h = helis[0]
    return (
        f"**{name} — Patrol Helicopter**\n"
        f"> On the map\n"
        f"> Position: `{int(h.x)}, {int(h.y)}`"
    )


async def _cmd_cargo(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ships = [m for m in markers if m.type == 4]
    if not ships:
        return f"**{name}** — No Cargo Ship on the map right now."
    s = ships[0]
    return (
        f"**{name} — Cargo Ship**\n"
        f"> On the map\n"
        f"> Position: `{int(s.x)}, {int(s.y)}`"
    )


async def _cmd_chinook(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ch47s = [m for m in markers if m.type == 7]
    if not ch47s:
        return f"**{name}** — No Chinook CH-47 on the map right now."
    c = ch47s[0]
    return (
        f"**{name} — Chinook CH-47**\n"
        f"> On the map\n"
        f"> Position: `{int(c.x)}, {int(c.y)}`"
    )


async def _cmd_large(socket, name: str) -> str:
    # Large Oil Rig is a static monument — not in markers
    return (
        f"**{name} — Large Oil Rig**\n"
        f"> Static monument — always present on the map.\n"
        f"> Crate timer and trigger history require a Smart Alarm or Storage Monitor paired to the rig.\n"
        f"> Check [RustMaps]( https://rustmaps.com) for exact location."
    )


async def _cmd_small(socket, name: str) -> str:
    return (
        f"**{name} — Small Oil Rig**\n"
        f"> Static monument — always present on the map.\n"
        f"> Crate timer and trigger history require a Smart Alarm or Storage Monitor paired to the rig.\n"
        f"> Check [RustMaps](https://rustmaps.com) for exact location."
    )


# ── Game Info (static data) ───────────────────────────────────────────────────

# Craft costs: item_name -> {ingredients}, workbench level, time (seconds)
_CRAFT_DATA = {
    "assault rifle":     {"Metal Frags": 50, "HQM": 1, "Wood": 200,  "Springs": 4,  "Scrap": 0},
    "ak47":              {"Metal Frags": 50, "HQM": 1, "Wood": 200,  "Springs": 4,  "Scrap": 0},
    "bolt action rifle": {"Metal Frags": 25, "HQM": 3, "Wood": 50,   "Springs": 4,  "Scrap": 0},
    "semi-automatic rifle": {"Metal Frags": 450, "HQM": 4, "Springs": 2, "Scrap": 0},
    "lr-300":            {"Metal Frags": 30, "HQM": 2, "Wood": 100,  "Springs": 3,  "Scrap": 0},
    "mp5":               {"Metal Frags": 500, "Springs": 3, "Emptytins": 2, "Scrap": 0},
    "thompson":          {"Metal Frags": 450, "Wood": 100, "Springs": 4, "Scrap": 0},
    "python":            {"Metal Frags": 350, "HQM": 15, "Springs": 4, "Scrap": 0},
    "revolver":          {"Metal Frags": 125, "Springs": 1, "Scrap": 0},
    "shotgun":           {"Metal Frags": 150, "Wood": 75, "Springs": 2, "Scrap": 0},
    "pump shotgun":      {"Metal Frags": 100, "Wood": 75, "Springs": 4, "Scrap": 0},
    "rocket launcher":   {"Metal Frags": 50,  "HQM": 4,  "Wood": 200, "Springs": 4, "Scrap": 0},
    "rocket":            {"Explosives": 10,   "Metal Pipe": 2, "Gun Powder": 150, "Sulfur": 1400},
    "c4":                {"Explosives": 20,   "Tech Trash": 2, "Cloth": 5},
    "satchel charge":    {"Beancan Grenade": 4, "Small Stash": 1, "Rope": 1},
    "f1 grenade":        {"Metal Frags": 50,  "Gun Powder": 60},
    "beancan grenade":   {"Metal Frags": 60,  "Gun Powder": 40},
    "stone wall":        {"Stone": 300},
    "sheet metal wall":  {"Metal Frags": 200},
    "armored wall":      {"HQM": 25, "Metal Frags": 100},
    "wood wall":         {"Wood": 200},
    "furnace":           {"Stone": 200, "Wood": 100, "Low Grade": 50},
    "large furnace":     {"Stone": 500, "Wood": 500, "Low Grade": 75},
    "workbench t1":      {"Wood": 500, "Stone": 100, "Metal Frags": 50},
    "workbench t2":      {"Metal Frags": 500, "Scrap": 500, "Wood": 1000},
    "workbench t3":      {"HQM": 100, "Scrap": 1250, "Metal Frags": 1000},
}

# Research costs (scrap)
_RESEARCH_DATA = {
    "assault rifle": 500, "ak47": 500,
    "bolt action rifle": 750,
    "semi-automatic rifle": 125,
    "lr-300": 500,
    "mp5": 250,
    "thompson": 125,
    "python": 125,
    "revolver": 75,
    "pump shotgun": 125,
    "rocket launcher": 500,
    "c4": 500,
    "satchel charge": 75,
    "f1 grenade": 75,
    "stone wall": 75,
    "sheet metal wall": 125,
    "armored wall": 500,
    "furnace": 75,
    "large furnace": 125,
    "workbench t1": 75,
    "workbench t2": 500,
    "workbench t3": 1500,
}

# Recycle output: item -> components you get back
_RECYCLE_DATA = {
    "assault rifle":        {"Metal Frags": 25, "HQM": 1, "Springs": 2},
    "bolt action rifle":    {"Metal Frags": 13, "HQM": 2, "Springs": 2},
    "semi-automatic rifle": {"Metal Frags": 225, "HQM": 2, "Springs": 1},
    "rocket launcher":      {"Metal Frags": 25, "HQM": 2, "Springs": 2},
    "pump shotgun":         {"Metal Frags": 50, "Springs": 2},
    "revolver":             {"Metal Frags": 63, "Springs": 1},
    "sheet metal door":     {"Metal Frags": 75},
    "armored door":         {"HQM": 13, "Metal Frags": 50},
    "sheet metal wall":     {"Metal Frags": 100},
    "armored wall":         {"HQM": 13, "Metal Frags": 50},
    "gears":                {"Metal Frags": 25},
    "pipe":                 {"Metal Frags": 13},
    "springs":              {"Metal Frags": 13},
    "tech trash":           {"HQM": 1, "Scrap": 13},
}

# Decay times (hours at full HP)
_DECAY_DATA = {
    "twig wall": 1, "twig foundation": 1,
    "wood wall": 3, "wood foundation": 3, "wood door": 3,
    "stone wall": 5, "stone foundation": 5,
    "sheet metal wall": 8, "sheet metal door": 8,
    "armored wall": 12, "armored door": 12,
    "wooden base": 3, "stone base": 5,
    "furnace": 6, "large furnace": 6,
    "sleeping bag": 24, "bed": 24,
    "tool cupboard": 24, "tc": 24,
}

# CCTV codes per monument
_CCTV_DATA = {
    "airfield":         ["AIRFIELDLOOKOUT1", "AIRFIELDLOOKOUT2", "AIRFIELDHANGAR1", "AIRFIELDHANGAR2", "AIRFIELDTARMAC"],
    "bandit camp":      ["BANDITCAMP1", "BANDITCAMP2", "BANDITCAMP3"],
    "dome":             ["DOME1", "DOME2"],
    "gas station":      ["GASSTATION1"],
    "harbour":          ["HARBOUR1", "HARBOUR2"],
    "junkyard":         ["JUNKYARD1", "JUNKYARD2"],
    "launch site":      ["LAUNCHSITE1", "LAUNCHSITE2", "LAUNCHSITE3", "LAUNCHSITE4", "ROCKETFACTORY1"],
    "lighthouse":       ["LIGHTHOUSE1"],
    "military tunnel":  ["MILITARYTUNNEL1", "MILITARYTUNNEL2", "MILITARYTUNNEL3", "MILITARYTUNNEL4", "MILITARYTUNNEL5", "MILITARYTUNNEL6"],
    "oil rig":          ["OILRIG1", "OILRIG1L1", "OILRIG1L2", "OILRIG1L3", "OILRIG1L4", "OILRIG1DOCK"],
    "large oil rig":    ["OILRIG2", "OILRIG2L1", "OILRIG2L2", "OILRIG2L3", "OILRIG2L4", "OILRIG2L5", "OILRIG2L6", "OILRIG2DOCK"],
    "outpost":          ["OUTPOST1", "OUTPOST2", "OUTPOST3"],
    "power plant":      ["POWERPLANT1", "POWERPLANT2", "POWERPLANT3", "POWERPLANT4"],
    "satellite dish":   ["SATELLITEDISH1", "SATELLITEDISH2", "SATELLITEDISH3"],
    "sewer branch":     ["SEWERBRANCH1", "SEWERBRANCH2"],
    "supermarket":      ["SUPERMARKET1"],
    "train yard":       ["TRAINYARD1", "TRAINYARD2", "TRAINYARD3"],
    "water treatment":  ["WATERTREATMENT1", "WATERTREATMENT2", "WATERTREATMENT3", "WATERTREATMENT4", "WATERTREATMENT5"],
    "mining outpost":   ["MININGOUTPOST1"],
    "fishing village":  ["FISHINGVILLAGE1"],
}

# Upkeep per hour (rough, TC range)
_UPKEEP_DATA = {
    "wood wall": {"Wood": 7}, "wood foundation": {"Wood": 7},
    "stone wall": {"Stone": 5}, "stone foundation": {"Stone": 5},
    "sheet metal wall": {"Metal Frags": 3}, "sheet metal foundation": {"Metal Frags": 3},
    "armored wall": {"HQM": 1}, "armored foundation": {"HQM": 1},
}


def _cmd_craft(args: str) -> str:
    if not args:
        return "Usage: `!rust craft <item name>`\nExample: `!rust craft rocket`"
    key = args.lower().strip()
    # Try exact then partial match
    data = _CRAFT_DATA.get(key)
    if not data:
        for k, v in _CRAFT_DATA.items():
            if key in k:
                key, data = k, v
                break
    if not data:
        return f"No craft data found for `{args}`.\nTry: `!rust craft rocket`, `!rust craft assault rifle`, `!rust craft c4`"
    ingredients = ", ".join(f"**{v}x {k}**" for k, v in data.items() if v)
    return f"**Craft: {key.title()}**\n> {ingredients}"


def _cmd_recycle(args: str) -> str:
    if not args:
        return "Usage: `!rust recycle <item name>`\nExample: `!rust recycle assault rifle`"
    key = args.lower().strip()
    data = _RECYCLE_DATA.get(key)
    if not data:
        for k, v in _RECYCLE_DATA.items():
            if key in k:
                key, data = k, v
                break
    if not data:
        return f"No recycle data found for `{args}`."
    output = ", ".join(f"**{v}x {k}**" for k, v in data.items())
    return f"**Recycle: {key.title()}**\n> Yields: {output}"


def _cmd_research(args: str) -> str:
    if not args:
        return "Usage: `!rust research <item name>`\nExample: `!rust research rocket launcher`"
    key = args.lower().strip()
    cost = _RESEARCH_DATA.get(key)
    if cost is None:
        for k, v in _RESEARCH_DATA.items():
            if key in k:
                key, cost = k, v
                break
    if cost is None:
        return f"No research data found for `{args}`."
    return f"**Research: {key.title()}**\n> Cost: **{cost} Scrap**"


def _cmd_decay(args: str) -> str:
    if not args:
        return "Usage: `!rust decay <item name>`\nExample: `!rust decay stone wall`"
    key = args.lower().strip()
    hours = _DECAY_DATA.get(key)
    if hours is None:
        for k, v in _DECAY_DATA.items():
            if key in k:
                key, hours = k, v
                break
    if hours is None:
        return f"No decay data found for `{args}`."
    return f"**Decay: {key.title()}**\n> Full HP decays in **{hours} hour{'s' if hours != 1 else ''}**"


def _cmd_upkeep_item(args: str) -> str:
    if not args:
        return "Usage: `!rust upkeep <item name>`\nExample: `!rust upkeep stone wall`"
    key = args.lower().strip()
    data = _UPKEEP_DATA.get(key)
    if not data:
        for k, v in _UPKEEP_DATA.items():
            if key in k:
                key, data = k, v
                break
    if not data:
        return f"No upkeep data found for `{args}`."
    cost = ", ".join(f"**{v}x {k}**" for k, v in data.items())
    return f"**Upkeep: {key.title()}**\n> Per hour (within TC range): {cost}"


def _cmd_item(args: str) -> str:
    if not args:
        return "Usage: `!rust item <item name>`\nExample: `!rust item assault rifle`"
    key = args.lower().strip()
    lines = []
    craft    = _CRAFT_DATA.get(key) or next((v for k, v in _CRAFT_DATA.items() if key in k), None)
    research = _RESEARCH_DATA.get(key) or next((v for k, v in _RESEARCH_DATA.items() if key in k), None)
    recycle  = _RECYCLE_DATA.get(key) or next((v for k, v in _RECYCLE_DATA.items() if key in k), None)
    decay    = _DECAY_DATA.get(key) or next((v for k, v in _DECAY_DATA.items() if key in k), None)
    if not any([craft, research, recycle, decay]):
        return f"No data found for `{args}`."
    if craft:
        lines.append("**Craft:** " + ", ".join(f"{v}x {k}" for k, v in craft.items() if v))
    if research:
        lines.append(f"**Research:** {research} Scrap")
    if recycle:
        lines.append("**Recycle:** " + ", ".join(f"{v}x {k}" for k, v in recycle.items()))
    if decay:
        lines.append(f"**Decay:** {decay}h at full HP")
    return f"**{args.title()}**\n" + "\n".join(f"> {l}" for l in lines)


def _cmd_cctv(args: str) -> str:
    if not args:
        keys = ", ".join(f"`{k}`" for k in sorted(_CCTV_DATA))
        return f"Usage: `!rust cctv <monument>`\nAvailable: {keys}"
    key = args.lower().strip()
    codes = _CCTV_DATA.get(key)
    if not codes:
        for k, v in _CCTV_DATA.items():
            if key in k:
                key, codes = k, v
                break
    if not codes:
        return f"No CCTV codes found for `{args}`."
    code_list = "\n".join(f"> `{c}`" for c in codes)
    return f"**CCTV — {key.title()}**\n{code_list}"


# ── Game Q&A (fallback) ───────────────────────────────────────────────────────
def cmd_game_question(query: str) -> str:
    q = query.lower()

    qa = {
        ("sulfur", "stone", "wall"):   "**Stone Wall:** Satchels: **10** | C4: **2** | Rockets: **4** (~1,500 sulfur)",
        ("sulfur", "sheet", "metal"):  "**Sheet Metal Wall:** Satchels: **4** | C4: **1** | Rockets: **2** (~1,000 sulfur)",
        ("sulfur", "armored"):         "**Armored Wall:** C4: **4** | Rockets: **8** | Satchels: **12** (~4,000 sulfur)",
        ("scrap", "farm"):             "**Best Scrap Farming:**\n> Tier 1 monuments (Gas Station, Supermarket) — safe & quick\n> Recycle components for bulk scrap\n> Oil Rig = massive scrap (high risk)",
        ("best", "weapon", "early"):   "**Best Early Weapons:**\n> 1. Bow — free, great for farming & PvP\n> 2. Crossbow — silent, strong\n> 3. Pipe Shotgun — one-shot close range",
        ("starter", "base"):           "**Starter Base:**\n> 2x1 or 2x2 stone with airlock\n> Place TC in sealed room first\n> Stone up ASAP (wood burns)",
        ("bradley", "apc"):            "**Bradley APC:**\n> Location: Launch Site\n> Use HV rockets or 40mm HE\n> Stay mobile — 360 degree turret\n> Drops 3 Bradley Crates",
        ("cargo", "ship"):             "**Cargo Ship:**\n> Spawns every ~2 hours\n> 2 locked crates every ~15min\n> Heavy scientists — bring armor",
        ("radiation",):                "**Radiation:**\n> Gas Station/Supermarket: 4 RAD\n> Airfield: 10 RAD\n> Water Treatment: 15 RAD\n> Launch Site: 50 RAD (full Hazmat needed)",
    }

    for keywords, answer in qa.items():
        if all(kw in q for kw in keywords):
            return answer

    return (
        f"No answer for: *\"{query}\"*\n\n"
        "Try: `status` · `players` · `time` · `team` · `events` · `craft <item>` · `cctv <monument>`\n"
        "> [Rust Wiki](https://wiki.facepunch.com/rust/)  ·  [RustMaps](https://rustmaps.com)"
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _time_to_float(t) -> float:
    if isinstance(t, (int, float)):
        return float(t)
    if isinstance(t, str):
        try:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h + (m / 60)
        except Exception:
            return float(t)
    return float(t)

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
    if not ts:
        return "Unknown"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d, %Y")
    except Exception:
        return str(ts)


def _fmt_elapsed(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"


def _time_till(now: float, target: float) -> str:
    """How long (in-game hours as real minutes) until target time."""
    diff = (target - now) % 24
    # Rough: 1 in-game hour ~ 2.5 real minutes
    real_minutes = int(diff * 2.5)
    return f"~{real_minutes}m"