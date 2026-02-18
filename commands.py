"""
commands.py
────────────────────────────────────────────────────────────────────────────
All !command handlers.
"""

import asyncio
import io
import logging
import json as _json
import time as _time_module
import discord
from pathlib import Path as _Path
from datetime import datetime, timezone
from rustplus import RustError
from server_manager import ServerManager
from timers import timer_manager

from bot import user_manager
from multi_user_auth import cmd_register, cmd_whoami, cmd_users, cmd_unregister
from multi_user_auth import UserManager
from server_manager_multiuser import MultiUserServerManager


log = logging.getLogger("Commands")

_BOT_START_TIME = _time_module.time()

# ── Clear Chat cmd ─────────────────────────────────────────────────────
async def cmd_clear(args: str, ctx) -> str | None:
    """
    !clear [amount]  - Delete last N messages (default 10, max 1000)
    !clear all       - Delete all messages in channel (up to 1000)

    Requires ctx to be the Discord message context.
    """
    if ctx is None:
        return "Clear command only works from Discord (not in-game)."

    # Check if user has manage messages permission
    if not ctx.channel.permissions_for(ctx.author).manage_messages:
        return "You need **Manage Messages** permission to use this command."

    # Parse arguments
    if not args:
        amount = 10
    elif args.lower() == "all":
        amount = 1000
    else:
        try:
            amount = int(args)
            if amount < 1:
                return "Amount must be at least 1."
            if amount > 1000:
                return "Maximum 1000 messages can be cleared at once."
        except ValueError:
            return "Usage: `!clear [amount]` or `!clear all`\nExample: `!clear 50`"

    try:
        # Delete messages (including the command message)
        deleted = await ctx.channel.purge(limit=amount + 1)

        # Send confirmation message that self-deletes after 5 seconds
        confirmation = await ctx.channel.send(
            f"Cleared **{len(deleted) - 1}** message(s)."
        )
        await asyncio.sleep(5)
        await confirmation.delete()

        return None  # Don't send another message since we already sent confirmation
    except discord.Forbidden:
        return "Bot lacks **Manage Messages** permission in this channel."
    except discord.HTTPException as e:
        return f"Failed to clear messages: `{e}`"



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

# ── Smart Switch registry (name -> entity_id) ─────────────────────────────────
_SWITCHES_FILE = _Path("switches.json")

def _load_switches() -> dict:
    try:
        if _SWITCHES_FILE.exists():
            return _json.loads(_SWITCHES_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_switches(switches: dict):
    try:
        _SWITCHES_FILE.write_text(_json.dumps(switches, indent=2))
    except Exception:
        pass

_switches: dict = _load_switches()


# ── Router ────────────────────────────────────────────────────────────────────
async def handle_query(
        query: str,
        manager,
        user_manager=None,
        ctx=None,
        discord_id=None
) -> str | tuple:
    parts = query.strip().split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    # User registration commands (new)
    if cmd == "register":
        return await cmd_register(ctx, user_manager)
    if cmd == "whoami":
        return await cmd_whoami(ctx, user_manager)
    if cmd == "users":
        return await cmd_users(ctx, user_manager)
    if cmd == "unregister":
        return await cmd_unregister(ctx, user_manager)

    # Meta / no-socket commands
    if cmd in ("servers", "server"):
        return cmd_servers_multiuser(manager)
    if cmd == "clear":
        return await cmd_clear(args, ctx)
    if cmd == "switch":
        return await cmd_switch_multiuser(args, manager)
    if cmd == "help":
        return cmd_help()
    if cmd in ("timer", "timers"):
        return await cmd_timer(args)
    if cmd in ("sson", "ssoff"):
        return await cmd_smart_switch_multiuser(cmd, args, manager)

    # Commands needing a live socket
    live_cmds = {
        "status", "info",
        "players", "online", "offline", "pop",
        "time", "map", "team", "events", "wipe", "uptime",
        "heli", "cargo", "chinook", "large", "small",
        "afk", "alive", "leader",
        "craft", "recycle", "research", "decay", "upkeep", "item", "cctv",
    }

    if cmd in live_cmds:
        active = manager.get_active()
        if not active:
            return (
                "No server connected.\n"
                "Join a Rust server and press **ESC -> Session -> Pairing**."
            )
        if not user_manager.has_user(discord_id):
            return "You need to register first. DM the bot with `!register`"

        try:
            await manager.ensure_connected_for_user(discord_id)
            socket = manager.get_socket_for_user(discord_id)
            return await _dispatch_live(cmd, args, socket, active)
        except Exception as e:
            log.error(f"Live command error: {e}", exc_info=True)
            return (
                f"Couldn't reach Rust+ server: `{e}`\n"
                "The server may be offline or App Port may be blocked."
            )

    return cmd_game_question(query)


# ── Meta Commands ─────────────────────────────────────────────────────────────
def cmd_servers_multiuser(manager: ServerManager) -> str:
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
        "\n\nUse `!switch <name or number>` to switch."


async def cmd_switch_multiuser(identifier: str, manager: ServerManager) -> str:
    if not identifier:
        return "Usage: `!switch <server name or number>`"
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
        "**Rust+ Companion Bot** — prefix: `!`\n\n"
        "**Server Info:**\n"
        "`status` · `players` · `pop` · `time` · `map` · `wipe` · `uptime`\n\n"
        "**Team:**\n"
        "`team` · `online` · `offline` · `afk` · `alive [name]` · `leader [name]`\n\n"
        "**Events:**\n"
        "`events` · `heli` · `cargo` · `chinook` · `large` · `small`\n\n"
        "**Utilities:**\n"
        "`timer add <time> <label>` · `timer remove <id>` · `timers`\n"
        "`sson <name or id>` · `ssoff <name or id>`\n"
        "`clear [amount]` · `clear all`\n\n"
        "**Game Info:**\n"
        "`craft <item>` · `recycle <item>` · `research <item>`\n"
        "`decay <item>` · `upkeep <item>` · `item <n>` · `cctv <monument>`\n\n"
        "**Multi-Server:**\n"
        "`servers` · `switch <name or #>`\n\n"
        "**Q&A:** `!<question>`"
    )


# ── Timer Command ─────────────────────────────────────────────────────────────
async def cmd_timer(args: str) -> str:
    if not args or args == "list":
        return timer_manager.list_timers()

    parts = args.split(None, 1)
    sub   = parts[0].lower()
    rest  = parts[1].strip() if len(parts) > 1 else ""

    if sub == "add":
        # !timer add 15m TC running low
        sub_parts = rest.split(None, 1)
        if not sub_parts:
            return "Usage: `!timer add <time> <label>`\nExample: `!timer add 15m TC is low`"
        duration = sub_parts[0]
        label    = sub_parts[1] if len(sub_parts) > 1 else ""
        ok, msg  = timer_manager.add(duration, label)
        return msg

    if sub == "remove":
        if not rest:
            return "Usage: `!timer remove <id>`"
        ok, msg = timer_manager.remove(rest.split()[0])
        return msg

    # Bare "!timer" shows list
    return timer_manager.list_timers()


# ── Smart Switch Commands ─────────────────────────────────────────────────────
async def cmd_smart_switch_multiuser(cmd: str, args: str, manager: ServerManager) -> str:
    """
    !sson <name or entity_id>
    !ssoff <name or entity_id>

    Entity IDs are registered via the pairing notification or stored manually
    in switches.json as {"my tc light": 1234567}.
    """
    if not args:
        registered = ", ".join(f"`{k}` ({v})" for k, v in _switches.items())
        hint = f"\nRegistered switches: {registered}" if registered else \
            "\nNo switches registered yet. Add them to `switches.json` as `{\"name\": entity_id}`."
        return f"Usage: `!sson <name or id>` / `!ssoff <name or id>`{hint}"

    entity_id = _resolve_switch(args)
    if entity_id is None:
        return (
            f"Switch `{args}` not found.\n"
            f"Add it to `switches.json` as `{{\"name\": entity_id}}`, "
            f"or use the entity ID directly."
        )

    active = manager.get_active()
    if not active:
        return "No server connected."

    try:
        await manager.ensure_connected()
        socket = manager.get_socket()
        if cmd == "sson":
            result = await socket.set_entity_value(entity_id, True)
        else:
            result = await socket.set_entity_value(entity_id, False)

        if isinstance(result, RustError):
            return f"Error: {result.reason}"

        state  = "ON" if cmd == "sson" else "OFF"
        label  = args if args.isdigit() else f"{args} ({entity_id})"
        return f"Smart Switch **{label}** turned **{state}**."
    except Exception as e:
        return f"Could not toggle switch: `{e}`"


def _resolve_switch(identifier: str) -> int | None:
    """Resolve a switch name or numeric ID to an entity_id int."""
    if identifier.isdigit():
        return int(identifier)
    key = identifier.lower()
    for k, v in _switches.items():
        if key == k.lower() or key in k.lower():
            return int(v)
    return None


# ── Live Dispatcher ───────────────────────────────────────────────────────────
async def _dispatch_live(cmd: str, args: str, socket, active: dict) -> str | tuple:
    name = active.get("name", active["ip"])

    if cmd in ("status", "info"):   return await _cmd_status(socket, name)
    if cmd in ("players", "pop"):   return await _cmd_players(socket, name)
    if cmd == "online":             return await _cmd_online(socket)
    if cmd == "offline":            return await _cmd_offline(socket)
    if cmd == "afk":                return await _cmd_afk(socket)
    if cmd == "alive":              return await _cmd_alive(socket, args)
    if cmd == "leader":             return await _cmd_leader(socket, args)
    if cmd == "time":               return await _cmd_time(socket, name)
    if cmd == "map":                return await _cmd_map(socket, active)
    if cmd == "team":               return await _cmd_team(socket)
    if cmd == "events":             return await _cmd_events(socket, name)
    if cmd == "wipe":               return await _cmd_wipe(socket, name)
    if cmd == "uptime":             return _cmd_uptime(name)
    if cmd == "heli":               return await _cmd_heli(socket, name)
    if cmd == "cargo":              return await _cmd_cargo(socket, name)
    if cmd == "chinook":            return await _cmd_chinook(socket, name)
    if cmd == "large":              return await _cmd_large(socket, name)
    if cmd == "small":              return await _cmd_small(socket, name)
    if cmd == "craft":              return _cmd_craft(args)
    if cmd == "recycle":            return _cmd_recycle(args)
    if cmd == "research":           return _cmd_research(args)
    if cmd == "decay":              return _cmd_decay(args)
    if cmd == "upkeep":             return _cmd_upkeep_item(args)
    if cmd == "item":               return _cmd_item(args)
    if cmd == "cctv":               return _cmd_cctv(args)
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
    now_f   = float(t.time)
    sunrise = float(t.sunrise)
    sunset  = float(t.sunset)
    is_day  = sunrise <= now_f < sunset
    till_change = _time_till(now_f, sunset if is_day else sunrise)
    phase   = f"Till night: {till_change}" if is_day else f"Till day: {till_change}"
    return (
        f"**{name} — In-Game Time**\n"
        f"> **Now:** {_fmt_time(t.time)}\n"
        f"> **Sunrise:** {_fmt_time(t.sunrise)}  |  **Sunset:** {_fmt_time(t.sunset)}\n"
        f"> {phase}"
    )


async def _cmd_map(socket, active: dict) -> str | tuple[str, bytes]:
    """Fetches the map JPEG and returns (caption_text, jpeg_bytes)."""
    info = await socket.get_info()
    if isinstance(info, RustError):
        return f"Error: {info.reason}"

    name = active.get("name", active["ip"])
    url  = f"https://rustmaps.com/map/{info.size}_{info.seed}"

    try:
        map_obj = await socket.get_map(add_icons=True, add_events=True, add_vending_machines=False)
        # get_map() returns a RustMap object; .jpg_image is PIL Image or raw bytes
        img = map_obj.jpg_image
        if hasattr(img, "save"):
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
        else:
            img_bytes = bytes(img)

        caption = (
            f"**{name}**\n"
            f"> **Seed:** `{info.seed}`  |  **Size:** {info.size}  |  **Map:** {info.map}\n"
            f"> [View on RustMaps]({url})"
        )
        return (caption, img_bytes)
    except Exception as e:
        log.warning(f"Map image fetch failed: {e} — falling back to text")
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
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    online = [m for m in team.members if m.is_online]
    if not online:
        return "No team members online."
    return (
            "**Online Team Members**\n"
            + "\n".join(f"> **{m.name}**" for m in online)
            + "\n_AFK detection requires position history — not available via Rust+ API._"
    )


async def _cmd_alive(socket, args: str) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    if args:
        match = next((m for m in team.members if args.lower() in m.name.lower()), None)
        if not match:
            return f"No team member found matching `{args}`."
        return f"**{match.name}** — {'Alive' if match.is_alive else 'Dead'}"
    alive = [m for m in team.members if m.is_alive]
    dead  = [m for m in team.members if not m.is_alive]
    lines = [f"> **{m.name}** — Alive" for m in alive] + \
            [f"> **{m.name}** — Dead"  for m in dead]
    return f"**Team Status ({len(alive)}/{len(team.members)} alive)**\n" + "\n".join(lines)


async def _cmd_leader(socket, args: str) -> str:
    """
    !leader           — promote self
    !leader <name>    — promote teammate by name
    """
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"

    if args:
        match = next((m for m in team.members if args.lower() in m.name.lower()), None)
        if not match:
            return f"No team member found matching `{args}`."
        target = match
    else:
        # Promote the bot's steam_id (the account that set up the bot)
        # We use the first online member as fallback if no match
        target = next((m for m in team.members if m.is_online), None)
        if not target:
            return "No online team members found."

    try:
        result = await socket.promote_to_team_leader(target.steam_id)
        if isinstance(result, RustError):
            return f"Error: {result.reason}"
        return f"**{target.name}** has been given team leadership."
    except Exception as e:
        return f"Could not transfer leadership: `{e}`"


# ── Events ────────────────────────────────────────────────────────────────────
async def _cmd_events(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    EVENT_TYPES = {1: "Explosion", 3: "Patrol Helicopter", 4: "Cargo Ship",
                   6: "Locked Crate", 7: "Chinook CH-47"}

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
        elapsed_s = int(now - _event_first_seen[type_id])
        age = f"{elapsed_s}s" if elapsed_s < 60 else f"{elapsed_s // 60}m {elapsed_s % 60}s"
        lines.append(f"> **{EVENT_TYPES[type_id]}** — active for {age}")

    return f"**{name} — Active Events**\n" + "\n".join(lines)


async def _cmd_heli(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    helis = list({m.type: m for m in markers if m.type == 3}.values())
    if not helis:
        return f"**{name}** — No Patrol Helicopter on the map right now."
    h = helis[0]
    return f"**{name} — Patrol Helicopter**\n> On the map — Position: `{int(h.x)}, {int(h.y)}`"


async def _cmd_cargo(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ships = list({m.type: m for m in markers if m.type == 4}.values())
    if not ships:
        return f"**{name}** — No Cargo Ship on the map right now."
    s = ships[0]
    return f"**{name} — Cargo Ship**\n> On the map — Position: `{int(s.x)}, {int(s.y)}`"


async def _cmd_chinook(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ch47s = list({m.type: m for m in markers if m.type == 7}.values())
    if not ch47s:
        return f"**{name}** — No Chinook CH-47 on the map right now."
    c = ch47s[0]
    return f"**{name} — Chinook CH-47**\n> On the map — Position: `{int(c.x)}, {int(c.y)}`"


async def _cmd_large(socket, name: str) -> str:
    """
    Large Oil Rig locked crate unlocks 15 minutes after the scientists are killed.
    We track when a Locked Crate marker (type 6) first appears on the map as a proxy.
    """
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    # Locked crate markers (type 6) appear when the crate is dropped / active
    crates = [m for m in markers if m.type == 6]

    now = _time_module.time()
    LARGE_CRATE_UNLOCK_SECS = 15 * 60  # 15 minutes

    if not crates:
        # Check cache for last-seen time
        last = _event_first_seen.get(60)  # key 60 = large rig crate
        if last:
            ago = int(now - last)
            return (
                f"**{name} — Large Oil Rig**\n"
                f"> No crate active. Last trigger: **{_fmt_elapsed(ago)} ago**."
            )
        return (
            f"**{name} — Large Oil Rig**\n"
            f"> No locked crate active on the map right now."
        )

    # Use the first crate's first-seen time
    if 60 not in _event_first_seen:
        _event_first_seen[60] = now
        _save_event_cache(_event_first_seen)

    elapsed = int(now - _event_first_seen[60])
    remaining = max(0, LARGE_CRATE_UNLOCK_SECS - elapsed)

    if remaining > 0:
        return (
            f"**{name} — Large Oil Rig**\n"
            f"> Locked Crate active — unlocks in **{_fmt_elapsed(remaining)}**\n"
            f"> (approx — based on crate first seen {_fmt_elapsed(elapsed)} ago)"
        )
    else:
        return (
            f"**{name} — Large Oil Rig**\n"
            f"> Locked Crate should be **unlocked** (crate active for {_fmt_elapsed(elapsed)})"
        )


async def _cmd_small(socket, name: str) -> str:
    """Same logic as large for Small Oil Rig — crate unlocks after 15 min."""
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    crates  = [m for m in markers if m.type == 6]
    now     = _time_module.time()
    UNLOCK  = 15 * 60

    if not crates:
        last = _event_first_seen.get(61)
        if last:
            ago = int(now - last)
            return (
                f"**{name} — Small Oil Rig**\n"
                f"> No crate active. Last trigger: **{_fmt_elapsed(ago)} ago**."
            )
        return f"**{name} — Small Oil Rig**\n> No locked crate active on the map right now."

    if 61 not in _event_first_seen:
        _event_first_seen[61] = now
        _save_event_cache(_event_first_seen)

    elapsed   = int(now - _event_first_seen[61])
    remaining = max(0, UNLOCK - elapsed)

    if remaining > 0:
        return (
            f"**{name} — Small Oil Rig**\n"
            f"> Locked Crate active — unlocks in **{_fmt_elapsed(remaining)}**\n"
            f"> (approx — based on crate first seen {_fmt_elapsed(elapsed)} ago)"
        )
    return (
        f"**{name} — Small Oil Rig**\n"
        f"> Locked Crate should be **unlocked** (active for {_fmt_elapsed(elapsed)})"
    )


# ── Game Info (static data) ───────────────────────────────────────────────────
_CRAFT_DATA = {
    "assault rifle":        {"Metal Frags": 50,  "HQM": 1,  "Wood": 200, "Springs": 4},
    "ak47":                 {"Metal Frags": 50,  "HQM": 1,  "Wood": 200, "Springs": 4},
    "bolt action rifle":    {"Metal Frags": 25,  "HQM": 3,  "Wood": 50,  "Springs": 4},
    "semi-automatic rifle": {"Metal Frags": 450, "HQM": 4,  "Springs": 2},
    "lr-300":               {"Metal Frags": 30,  "HQM": 2,  "Wood": 100, "Springs": 3},
    "mp5":                  {"Metal Frags": 500, "Springs": 3, "Empty Tins": 2},
    "thompson":             {"Metal Frags": 450, "Wood": 100, "Springs": 4},
    "python":               {"Metal Frags": 350, "HQM": 15, "Springs": 4},
    "revolver":             {"Metal Frags": 125, "Springs": 1},
    "pump shotgun":         {"Metal Frags": 100, "Wood": 75, "Springs": 4},
    "rocket launcher":      {"Metal Frags": 50,  "HQM": 4,  "Wood": 200, "Springs": 4},
    "rocket":               {"Explosives": 10,   "Metal Pipe": 2, "Gun Powder": 150},
    "c4":                   {"Explosives": 20,   "Tech Trash": 2, "Cloth": 5},
    "satchel charge":       {"Beancan Grenade": 4, "Small Stash": 1, "Rope": 1},
    "f1 grenade":           {"Metal Frags": 50,  "Gun Powder": 60},
    "beancan grenade":      {"Metal Frags": 60,  "Gun Powder": 40},
    "stone wall":           {"Stone": 300},
    "sheet metal wall":     {"Metal Frags": 200},
    "armored wall":         {"HQM": 25, "Metal Frags": 100},
    "wood wall":            {"Wood": 200},
    "furnace":              {"Stone": 200, "Wood": 100, "Low Grade": 50},
    "large furnace":        {"Stone": 500, "Wood": 500, "Low Grade": 75},
    "workbench t1":         {"Wood": 500,  "Stone": 100, "Metal Frags": 50},
    "workbench t2":         {
        "Metal Frags": 500,
        "HQM": 20,
        "Scrap": 250,
        "Basic Blueprint Fragments": 5
    },
    "workbench t3":         {
        "Metal Frags": 1000,
        "HQM": 100,
        "Scrap": 500,
        "Advanced Blueprint Fragments": 5
    },
}


_RESEARCH_DATA = {
    "assault rifle": 500, "ak47": 500,
    "bolt action rifle": 750,
    "semi-automatic rifle": 125,
    "lr-300": 500, "mp5": 250, "thompson": 125,
    "python": 125, "revolver": 75,
    "pump shotgun": 125, "rocket launcher": 500,
    "c4": 500, "satchel charge": 75, "f1 grenade": 75,
    "stone wall": 75, "sheet metal wall": 125, "armored wall": 500,
    "furnace": 75, "large furnace": 125,
    "workbench t1": 75, "workbench t2": 500, "workbench t3": 1500,
}

_RECYCLE_DATA = {
    "assault rifle":        {"Metal Frags": 25, "HQM": 1,  "Springs": 2},
    "bolt action rifle":    {"Metal Frags": 13, "HQM": 2,  "Springs": 2},
    "semi-automatic rifle": {"Metal Frags": 225,"HQM": 2,  "Springs": 1},
    "rocket launcher":      {"Metal Frags": 25, "HQM": 2,  "Springs": 2},
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

_DECAY_DATA = {
    "twig wall": 1, "twig foundation": 1,
    "wood wall": 3, "wood foundation": 3, "wood door": 3,
    "stone wall": 5, "stone foundation": 5,
    "sheet metal wall": 8, "sheet metal door": 8,
    "armored wall": 12, "armored door": 12,
    "furnace": 6, "large furnace": 6,
    "sleeping bag": 24, "bed": 24,
    "tool cupboard": 24, "tc": 24,
}

_UPKEEP_DATA = {
    "wood wall":          {"Wood": 7},
    "wood foundation":    {"Wood": 7},
    "stone wall":         {"Stone": 5},
    "stone foundation":   {"Stone": 5},
    "sheet metal wall":   {"Metal Frags": 3},
    "sheet metal foundation": {"Metal Frags": 3},
    "armored wall":       {"HQM": 1},
    "armored foundation": {"HQM": 1},
}

_CCTV_DATA = {
    "airfield":        ["AIRFIELDLOOKOUT1", "AIRFIELDLOOKOUT2", "AIRFIELDHANGAR1", "AIRFIELDHANGAR2", "AIRFIELDTARMAC"],
    "bandit camp":     ["BANDITCAMP1", "BANDITCAMP2", "BANDITCAMP3"],
    "dome":            ["DOME1", "DOME2"],
    "gas station":     ["GASSTATION1"],
    "harbour":         ["HARBOUR1", "HARBOUR2"],
    "junkyard":        ["JUNKYARD1", "JUNKYARD2"],
    "launch site":     ["LAUNCHSITE1", "LAUNCHSITE2", "LAUNCHSITE3", "LAUNCHSITE4", "ROCKETFACTORY1"],
    "lighthouse":      ["LIGHTHOUSE1"],
    "military tunnel": ["MILITARYTUNNEL1","MILITARYTUNNEL2","MILITARYTUNNEL3","MILITARYTUNNEL4","MILITARYTUNNEL5","MILITARYTUNNEL6"],
    "oil rig":         ["OILRIG1","OILRIG1L1","OILRIG1L2","OILRIG1L3","OILRIG1L4","OILRIG1DOCK"],
    "large oil rig":   ["OILRIG2","OILRIG2L1","OILRIG2L2","OILRIG2L3","OILRIG2L4","OILRIG2L5","OILRIG2L6","OILRIG2DOCK"],
    "outpost":         ["OUTPOST1", "OUTPOST2", "OUTPOST3"],
    "power plant":     ["POWERPLANT1", "POWERPLANT2", "POWERPLANT3", "POWERPLANT4"],
    "satellite dish":  ["SATELLITEDISH1", "SATELLITEDISH2", "SATELLITEDISH3"],
    "sewer branch":    ["SEWERBRANCH1", "SEWERBRANCH2"],
    "supermarket":     ["SUPERMARKET1"],
    "train yard":      ["TRAINYARD1", "TRAINYARD2", "TRAINYARD3"],
    "water treatment": ["WATERTREATMENT1","WATERTREATMENT2","WATERTREATMENT3","WATERTREATMENT4","WATERTREATMENT5"],
    "mining outpost":  ["MININGOUTPOST1"],
    "fishing village": ["FISHINGVILLAGE1"],
}


def _fuzzy_match(query: str, data: dict):
    key = query.lower().strip()
    if key in data:
        return key, data[key]
    for k, v in data.items():
        if key in k:
            return k, v
    return None, None


def _cmd_craft(args: str) -> str:
    if not args:
        return "Usage: `!craft <item>`  e.g. `!craft rocket`"
    k, data = _fuzzy_match(args, _CRAFT_DATA)
    if not data:
        return f"No craft data for `{args}`."
    return f"**Craft: {k.title()}**\n> " + ", ".join(f"**{v}x {n}**" for n, v in data.items())


def _cmd_recycle(args: str) -> str:
    if not args:
        return "Usage: `!recycle <item>`"
    k, data = _fuzzy_match(args, _RECYCLE_DATA)
    if not data:
        return f"No recycle data for `{args}`."
    return f"**Recycle: {k.title()}**\n> " + ", ".join(f"**{v}x {n}**" for n, v in data.items())


def _cmd_research(args: str) -> str:
    if not args:
        return "Usage: `!research <item>`"
    k, cost = _fuzzy_match(args, _RESEARCH_DATA)
    if cost is None:
        return f"No research data for `{args}`."
    return f"**Research: {k.title()}**\n> Cost: **{cost} Scrap**"


def _cmd_decay(args: str) -> str:
    if not args:
        return "Usage: `!decay <item>`"
    k, hours = _fuzzy_match(args, _DECAY_DATA)
    if hours is None:
        return f"No decay data for `{args}`."
    return f"**Decay: {k.title()}**\n> Full HP decays in **{hours}h**"


def _cmd_upkeep_item(args: str) -> str:
    if not args:
        return "Usage: `!upkeep <item>`"
    k, data = _fuzzy_match(args, _UPKEEP_DATA)
    if not data:
        return f"No upkeep data for `{args}`."
    cost = ", ".join(f"**{v}x {n}**" for n, v in data.items())
    return f"**Upkeep: {k.title()}**\n> Per hour (TC range): {cost}"


def _cmd_item(args: str) -> str:
    if not args:
        return "Usage: `!item <name>`"
    lines = []
    _, craft    = _fuzzy_match(args, _CRAFT_DATA)
    _, research = _fuzzy_match(args, _RESEARCH_DATA)
    _, recycle  = _fuzzy_match(args, _RECYCLE_DATA)
    _, decay    = _fuzzy_match(args, _DECAY_DATA)
    if not any([craft, research, recycle, decay]):
        return f"No data found for `{args}`."
    if craft:
        lines.append("**Craft:** " + ", ".join(f"{v}x {n}" for n, v in craft.items()))
    if research:
        lines.append(f"**Research:** {research} Scrap")
    if recycle:
        lines.append("**Recycle:** " + ", ".join(f"{v}x {n}" for n, v in recycle.items()))
    if decay:
        lines.append(f"**Decay:** {decay}h")
    return f"**{args.title()}**\n" + "\n".join(f"> {l}" for l in lines)


def _cmd_cctv(args: str) -> str:
    if not args:
        keys = ", ".join(f"`{k}`" for k in sorted(_CCTV_DATA))
        return f"Usage: `!cctv <monument>`\nAvailable: {keys}"
    k, codes = _fuzzy_match(args, _CCTV_DATA)
    if not codes:
        return f"No CCTV codes for `{args}`."
    return f"**CCTV — {k.title()}**\n" + "\n".join(f"> `{c}`" for c in codes)


# ── Game Q&A (fallback) ───────────────────────────────────────────────────────
def cmd_game_question(query: str) -> str:
    q = query.lower()
    qa = {
        ("sulfur", "stone", "wall"):  "**Stone Wall:** Satchels: **10** | C4: **2** | Rockets: **4** (~1,500 sulfur)",
        ("sulfur", "sheet", "metal"): "**Sheet Metal Wall:** Satchels: **4** | C4: **1** | Rockets: **2** (~1,000 sulfur)",
        ("sulfur", "armored"):        "**Armored Wall:** C4: **4** | Rockets: **8** | Satchels: **12** (~4,000 sulfur)",
        ("scrap", "farm"):            "**Best Scrap Farming:**\n> Tier 1 monuments (Gas Station, Supermarket)\n> Recycle components\n> Oil Rig = massive scrap (high risk)",
        ("best", "weapon", "early"):  "**Best Early Weapons:**\n> 1. Bow\n> 2. Crossbow\n> 3. Pipe Shotgun",
        ("bradley", "apc"):           "**Bradley APC:**\n> Launch Site\n> HV rockets or 40mm HE\n> Drops 3 Bradley Crates",
        ("cargo", "ship"):            "**Cargo Ship:**\n> Spawns ~every 2 hours\n> 2 locked crates every ~15min\n> Heavy scientists — bring armor",
        ("radiation",):               "**Radiation:**\n> Gas Station/Supermarket: 4 RAD\n> Airfield: 10 RAD\n> Water Treatment: 15 RAD\n> Launch Site: 50 RAD",
    }
    for keywords, answer in qa.items():
        if all(kw in q for kw in keywords):
            return answer
    return (
        f"No answer for: *\"{query}\"*\n\n"
        "Try: `help`"
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
        h = int(float(t)); m = int((float(t) - h) * 60)
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
    if seconds < 60:    return f"{seconds}s"
    if seconds < 3600:  return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600; m = (seconds % 3600) // 60
    return f"{h}h {m}m"


def _time_till(now: float, target: float) -> str:
    diff = (target - now) % 24
    real_minutes = int(diff * 2.5)
