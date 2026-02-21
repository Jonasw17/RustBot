import asyncio
import io
import logging
import json as _json
import time as _time_module
import discord
from pathlib import Path as _Path
from datetime import datetime, timezone
from rustplus import RustError
from typing import Optional
from status_embed import build_server_status_embed, _parse_time_to_float, _fmt_time_val

from server_manager_multiuser import MultiUserServerManager
from multi_user_auth import UserManager, cmd_register, cmd_whoami, cmd_users, cmd_unregister
from timers import timer_manager
from storage_monitor import storage_manager, format_storage_embed
from death_tracker import death_tracker, format_death_embed, format_death_history_embed
from rust_info_db import (
    get_all_vehicle_costs,
    get_all_car_module_costs,
    get_vehicle_cost,
    get_car_module_cost,
    get_blueprint_fragment_info,
    search_info,
    DEVICE_CATEGORIES,
    CRAFT_DATA,
    RESEARCH_DATA,
    RECYCLE_DATA,
    DECAY_DATA,
    UPKEEP_DATA,
    CCTV_DATA,
    BLUEPRINT_FRAGMENT_DATA
)
log = logging.getLogger("Commands")

_BOT_START_TIME = _time_module.time()

#  Clear Chat cmd
async def cmd_clear(args: str, ctx) -> str | None:
    """
    !clear [amount]  - Delete last N messages (default 10, max 1000)
    !clear all       - Delete all messages in channel (up to 1000)
    """
    if ctx is None:
        return "Clear command only works from Discord (not in-game)."

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
        deleted = await ctx.channel.purge(limit=amount + 1)
        confirmation = await ctx.channel.send(f"Cleared **{len(deleted) - 1}** message(s).")
        await asyncio.sleep(5)
        await confirmation.delete()
        return None
    except discord.Forbidden:
        return "Bot lacks **Manage Messages** permission in this channel."
    except discord.HTTPException as e:
        return f"Failed to clear messages: `{e}`"


#  Event timestamp cache
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

#  Smart Switch registry
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

async def cmd_timer(args: str) -> str:
    """
    Timer commands:
    !timer add <duration> [text] - Add a new timer
    !timer remove <id> - Remove a timer
    !timer list - List all active timers

    Duration format: 15m, 2h30m, 1h15m30s
    """
    if not args:
        return timer_manager.list_timers()

    parts = args.split(None, 1)
    subcommand = parts[0].lower()

    if subcommand in ("list", "ls"):
        return timer_manager.list_timers()

    elif subcommand in ("add", "set", "create"):
        if len(parts) < 2:
            return (
                "Usage: `!timer add <duration> [text]`\n"
                "Examples:\n"
                "* `!timer add 15m Furnace check`\n"
                "* `!timer add 2h30m Raid defense`\n"
                "* `!timer add 1h Base upkeep`"
            )

        rest = parts[1].split(None, 1)
        duration = rest[0]
        text = rest[1] if len(rest) > 1 else None

        success, message = timer_manager.add(duration, text)
        return message

    elif subcommand in ("remove", "rm", "delete", "del"):
        if len(parts) < 2:
            return "Usage: `!timer remove <id>`"

        timer_id = parts[1]
        success, message = timer_manager.remove(timer_id)
        return message

    else:
        return (
            "**Timer Commands:**\n"
            "`!timer` or `!timer list` - Show active timers\n"
            "`!timer add <duration> [text]` - Create timer\n"
            "`!timer remove <id>` - Delete timer\n\n"
            "**Duration Examples:**\n"
            "`15m` = 15 minutes\n"
            "`2h30m` = 2 hours 30 minutes\n"
            "`1h15m30s` = 1 hour 15 min 30 sec"
        )


async def cmd_smart_switch(
        cmd: str,
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    Smart switch control commands:
    !sson <name> - Turn on a smart switch
    !ssoff <name> - Turn off a smart switch
    """
    if not args:
        return f"Usage: `!{cmd} <switch_name>`\nExample: `!{cmd} maingate`"

    switch_name = args.strip()

    # Check user registration
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    # Get active server
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected. Use `!change <server>` to connect first."

    # Get socket
    socket = manager.get_socket_for_user(discord_id)
    if not socket:
        return "Not connected to server."

    # Find the switch
    server_key = f"{active['ip']}:{active['port']}"
    full_key = f"{discord_id}_{server_key}_{switch_name}"

    if full_key not in _switches:
        return (
            f"Switch `{switch_name}` not found on **{active.get('name', active['ip'])}**.\n"
            f"Use `!switches` to see registered switches."
        )

    entity_id = _switches[full_key]

    # Determine action
    turn_on = (cmd == "sson")
    action_text = "ON" if turn_on else "OFF"

    try:
        # Send the command to toggle the smart switch
        result = await socket.turn_on_smart_switch(entity_id) if turn_on else await socket.turn_off_smart_switch(entity_id)

        if isinstance(result, RustError):
            return f"Error toggling switch: {result.reason}"

        return f"Smart switch **{switch_name}** turned **{action_text}** ✓"

    except Exception as e:
        log.error(f"Error toggling smart switch: {e}")
        return f"Failed to toggle switch: {str(e)}"


def cmd_fragments(args: str) -> str:
    """
    !fragments [basic|advanced] - Show blueprint fragment information
    """
    if not args:
        return get_blueprint_fragment_info()

    fragment_type = args.strip().lower()
    if fragment_type in ("basic", "advanced"):
        return get_blueprint_fragment_info(fragment_type)

    return "Usage: `!fragments` or `!fragments basic` or `!fragments advanced`"


#  Main Router
async def handle_query(
        query: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        ctx=None,
        discord_id: Optional[str] = None
) -> str | tuple:
    """
    Main command router - MULTI-USER ONLY.
    All commands use per-user credentials and connections.
    """
    parts = query.strip().split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    # User registration commands
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
        return cmd_servers(manager, user_manager, discord_id)
    if cmd == "clear":
        return await cmd_clear(args, ctx)
    if cmd == "change":
        return await cmd_change_server(args, manager, user_manager, discord_id)
    if cmd in ("removeserver", "delserver", "rmserver"):
        return await cmd_remove_server(args, manager, user_manager, discord_id)
    if cmd == "help":
        return cmd_help()
    if cmd in ("timer", "timers"):
        return await cmd_timer(args)
    if cmd in ("sson", "ssoff"):
        return await cmd_smart_switch(cmd, args, manager, user_manager, discord_id)

    if cmd in ("fragments", "fragment", "bp"):
        return cmd_fragments(args)

    # Smart item commands (separate from server pairing)
    if cmd == "smartitems":
        return await cmd_smart_items(manager, user_manager, discord_id)
    if cmd == "addswitch":
        return await cmd_add_switch(args, manager, user_manager, discord_id)
    if cmd == "removeswitch":
        return await cmd_remove_switch(args, manager, user_manager, discord_id)
    if cmd == "switches":
        return cmd_list_switches(manager, user_manager, discord_id)

    # Storage Monitor commands
    if cmd in ("addsm", "addstoragem", "addstorage"):
        return await cmd_add_storage(args, manager, user_manager, discord_id)
    if cmd in ("viewsm", "viewstorage", "storage"):
        return await cmd_view_storage(args, manager, user_manager, discord_id)
    if cmd in ("deletesm", "removesm", "delstorage"):
        return await cmd_remove_storage(args, manager, user_manager, discord_id)
    if cmd in ("storages", "listsm"):
        return cmd_list_storages(manager, user_manager, discord_id)

    # Death tracker commands
    if cmd in ("deaths", "deathhistory"):
        return await cmd_death_history(manager, user_manager, discord_id)
    if cmd in ("cleardeaths",):
        return await cmd_clear_deaths(manager, user_manager, discord_id)

    # Info commands (vehicles, costs, etc.)
    if cmd in ("vehicles", "vehiclecosts"):
        return cmd_vehicle_costs()
    if cmd in ("carmodules", "modules"):
        return cmd_car_module_costs()
    if cmd == "price":
        return cmd_price(args)

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
        # Check user registration
        if not discord_id or not user_manager.has_user(discord_id):
            return (
                "**Not registered**\n"
                "This command requires a Rust+ connection.\n\n"
                "DM the bot with `!register <steam_id>` and attach your `rustplus.config.json` file."
            )
        # Get user's active server
        active = manager.get_active_server_for_user(discord_id)
        if not active:
            return (
                "No server connected.\n"
                "This command requires an active Rust+ connection.\n\n"
                "**To connect:**\n"
                "1. Join any Rust server in-game\n"
                "2. Press **ESC -> Rust+ -> Pair Server**\n"
                "3. The bot will auto-connect to your server"
            )

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


#  Meta Commands
def cmd_servers(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """List servers paired by this user"""
    if not discord_id or not user_manager.has_user(discord_id):
        return (
            "You need to register first.\n"
            "DM the bot with `!register` to get started."
        )

    servers = manager.list_servers_for_user(discord_id)
    active = manager.get_active_server_for_user(discord_id)

    if not servers:
        return (
            "**No servers paired yet.**\n"
            "Join any Rust server and press **ESC -> Rust+ -> Pair Server**."
        )

    lines = []
    for i, s in enumerate(servers, 1):
        is_active = active and s["ip"] == active["ip"] and s["port"] == active["port"]
        tag = "`active`" if is_active else f"`{i}.`"
        lines.append(f"{tag} **{s.get('name', s['ip'])}** `{s['ip']}:{s['port']}`")

    return "**Your Paired Servers:**\n" + "\n".join(lines) + \
        "\n\nUse `!change <name or number>` to switch."


async def cmd_change_server(
        identifier: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """Switch user's active server"""
    if not identifier:
        return "Usage: `!change <server name or number>`"

    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first. DM the bot with `!register`"

    try:
        server = await manager.switch_server_for_user(discord_id, identifier)
        if not server:
            return f"No server found matching `{identifier}`."
        return f"Switched to **{server.get('name', server['ip'])}**"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Could not connect: `{e}`"


async def cmd_remove_server(
        identifier: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """Remove a server from user's paired servers"""
    if not identifier:
        return (
            "Usage: `!removeserver <server name or number>`\n"
            "Example: `!removeserver 2` or `!removeserver Rustoria`"
        )

    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    success, message = user_manager.remove_user_server(discord_id, identifier)

    if success:
        # If removed server was active, clear the connection
        active = manager.get_active_server_for_user(discord_id)
        if active and identifier in active.get("name", ""):
            # Disconnect from removed server
            if discord_id in manager._active_sockets:
                try:
                    await manager._active_sockets[discord_id].disconnect()
                except Exception:
                    pass
                del manager._active_sockets[discord_id]
            if discord_id in manager._active_servers:
                del manager._active_servers[discord_id]

            message += "\n\nServer was active - disconnected. Use `!servers` to connect to another."

    return message


def cmd_help() -> str:
    return (
        "**Rust+ Companion Bot** - prefix: `!`\n\n"
        "**Server Management:**\n"
        "`servers` - `switch <n or #>` - `removeserver <n or #>` - `register` - `whoami`\n\n"
        "**Server Info:**\n"
        "`status` - `players` - `pop` - `time` - `map` - `wipe` - `uptime`\n\n"
        "**Team:**\n"
        "`team` - `online` - `offline` - `afk` - `alive [name]` - `leader [name]`\n\n"
        "**Events:**\n"
        "`events` - `heli` - `cargo` - `chinook` - `large` - `small`\n\n"
        "**Smart Items:** (separate from server pairing)\n"
        "`smartitems` - `addswitch <n> <id>` - `removeswitch <n>`\n"
        "`sson <n>` - `ssoff <n>` - `switches`\n\n"
        "**Storage Monitors:**\n"
        "`addSM <name> <id>` - `viewSM [name]` - `deleteSM <name>` - `storages`\n\n"
        "**Death Tracking:**\n"
        "`deaths` - `cleardeaths`\n\n"
        "**Costs & Info:**\n"
        "`vehicles` - `carmodules` - `price <item>`\n\n"
        "**Utilities:**\n"
        "`timer add <time> <label>` - `timer remove <id>` - `timers`\n"
        "`clear [amount]` - `clear all`\n\n"
        "**Game Info:**\n"
        "`craft <item>` - `recycle <item>` - `research <item>`\n"
        "`decay <item>` - `upkeep <item>` - `item <n>` - `cctv <monument>`\n\n"
        "**Q&A:** Ask any Rust question!"
    )


def _resolve_switch(identifier: str) -> int | None:
    """Resolve a switch name or numeric ID to an entity_id int."""
    if identifier.isdigit():
        return int(identifier)
    key = identifier.lower()
    for k, v in _switches.items():
        if key == k.lower() or key in k.lower():
            return int(v)
    return None


# New Smart Item Management Commands
async def cmd_smart_items(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    Show all smart items (switches, alarms, etc.) paired to the current server.
    Separate from server pairing - this is for in-game controllable devices.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected. Use `!change <server>` to connect to a server first."

    server_key = f"{active['ip']}:{active['port']}"
    user_switches = {k: v for k, v in _switches.items() if k.startswith(f"{discord_id}_{server_key}_")}

    if not user_switches:
        return (
            f"**Smart Items on {active.get('name', active['ip'])}**\n"
            "No smart items paired yet.\n\n"
            "Use `!addswitch <name> <entity_id>` to add a smart switch.\n"
            "Get entity IDs from the Rust+ app when pairing devices."
        )

    lines = []
    for full_key, entity_id in user_switches.items():
        # Extract just the name part (after discord_id_server_key_)
        name = full_key.split('_', 3)[-1] if '_' in full_key else full_key
        lines.append(f"`{name}` - Entity ID: `{entity_id}`")

    return (
            f"**Smart Items on {active.get('name', active['ip'])}**\n" +
            "\n".join(lines) +
            "\n\nControl with: `!sson <name>` / `!ssoff <name>`"
    )


async def cmd_add_switch(
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !addswitch <name> <entity_id>
    Add a smart switch to the current server.
    """
    if not args:
        return (
            "Usage: `!addswitch <name> <entity_id>`\n"
            "Example: `!addswitch maingate 12345678`\n\n"
            "Get entity IDs from Rust+ app when pairing devices."
        )

    parts = args.split(None, 1)
    if len(parts) != 2:
        return "Usage: `!addswitch <name> <entity_id>`"

    name, entity_id_str = parts

    # Validate entity ID
    try:
        entity_id = int(entity_id_str)
    except ValueError:
        return f"Invalid entity ID: `{entity_id_str}`. Must be a number."

    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected. Use `!change <server>` to connect first."

    # Store with user and server prefix to keep switches separate
    server_key = f"{active['ip']}:{active['port']}"
    full_key = f"{discord_id}_{server_key}_{name}"

    _switches[full_key] = entity_id
    _save_switches(_switches)

    return (
        f"Smart switch **{name}** added to **{active.get('name', active['ip'])}**.\n"
        f"Entity ID: `{entity_id}`\n\n"
        f"Control it with: `!sson {name}` / `!ssoff {name}`"
    )


async def cmd_remove_switch(
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !removeswitch <name>
    Remove a smart switch from the current server.
    """
    if not args:
        return "Usage: `!removeswitch <name>`"

    name = args.strip()

    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."

    server_key = f"{active['ip']}:{active['port']}"
    full_key = f"{discord_id}_{server_key}_{name}"

    if full_key not in _switches:
        return f"Switch `{name}` not found on this server."

    del _switches[full_key]
    _save_switches(_switches)

    return f"Smart switch **{name}** removed from **{active.get('name', active['ip'])}**."


def cmd_list_switches(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !switches
    List all switches across all servers for this user.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    user_switches = {k: v for k, v in _switches.items() if k.startswith(f"{discord_id}_")}

    if not user_switches:
        return (
            "No smart switches registered yet.\n"
            "Use `!addswitch <name> <entity_id>` to add one."
        )

    # Group by server
    by_server = {}
    for full_key, entity_id in user_switches.items():
        parts = full_key.split('_', 3)
        if len(parts) >= 3:
            server_key = parts[1]  # IP:Port
            name = parts[3] if len(parts) > 3 else full_key
            if server_key not in by_server:
                by_server[server_key] = []
            by_server[server_key].append((name, entity_id))

    lines = []
    for server_key, switches in by_server.items():
        lines.append(f"\n**{server_key}:**")
        for name, entity_id in switches:
            lines.append(f"  `{name}` - Entity ID: `{entity_id}`")

    return "**Your Smart Switches:**" + "\n".join(lines)


# Info Commands (Vehicle/Module Costs)
def cmd_vehicle_costs() -> str:
    """Show all vehicle costs (boats and helicopters)"""
    return (
            "**Vehicle Costs**\n\n" +
            get_all_vehicle_costs() +
            "\n\nUse `!price <vehicle>` for specific details."
    )


def cmd_car_module_costs() -> str:
    """Show car module costs from electrical branch down"""
    return (
            "**Modular Car Components (Electrical Branch Down)**\n\n" +
            get_all_car_module_costs() +
            "\n\nAll modules cost to branch down at Level 2 Workbench."
    )


def cmd_price(args: str) -> str:
    """
    !price <item>
    Get specific price/cost information for vehicles or car modules.
    """
    if not args:
        return (
            "Usage: `!price <item>`\n"
            "Examples: `!price minicopter`, `!price camper module`, `!price rhib`"
        )

    # Try vehicle first
    vehicle = get_vehicle_cost(args)
    if vehicle:
        msg = f"**{vehicle['name']}**\n"
        msg += f"> Cost: **{vehicle['scrap']} scrap**\n"
        msg += f"> Location: {vehicle['location']}"
        if 'note' in vehicle:
            msg += f"\n> Note: {vehicle['note']}"
        return msg

    # Try car module
    module = get_car_module_cost(args)
    if module:
        msg = f"**{module['name']}**\n"
        msg += f"> Branch Down Cost: **{module['scrap']} scrap**\n"
        msg += f"> Workbench: {module['workbench']}"
        if 'storage' in module:
            msg += f"\n> Storage: {module['storage']}"
        if 'features' in module:
            msg += f"\n> Features: {', '.join(module['features'])}"
        return msg

    # Try searching in info database
    results = search_info(args)
    if results:
        msg_parts = []
        for result in results[:3]:  # Limit to 3 results
            if result['type'] == 'vehicle':
                v = result['data']
                msg_parts.append(f"**{v['name']}**: {v['scrap']} scrap at {v['location']}")
            elif result['type'] == 'car_module':
                m = result['data']
                msg_parts.append(f"**{m['name']}**: {m['scrap']} scrap (Branch down)")
            elif result['type'] == 'qa':
                qa = result['data']
                msg_parts.append(f"**{qa['question']}**\n> {qa['answer']}")
        return "\n\n".join(msg_parts)

    return f"No price information found for `{args}`.\nTry: `!vehicles` or `!carmodules`"


#  Live Command Dispatcher
async def _dispatch_live(cmd: str, args: str, socket, active: dict) -> str | tuple | discord.Embed:
    name = active.get("name", active["ip"])

    if cmd in ("status", "info"):   return await _cmd_status(socket, active)
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

async def _cmd_status(socket, active: dict) -> discord.Embed:
    """Get server status - returns rich embed"""
    try:
        embed = await build_server_status_embed(active, socket, user_info=None)
        return embed
    except Exception as e:
        log.error(f"Status command error: {e}")
        embed = discord.Embed(
            title=f" {active.get('name', active['ip'])}",
            description=f"Error fetching status: {str(e)[:100]}",
            color=0xFFA500
        )
        return embed

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
    return f"**{name}** ” Last wipe: **{_fmt_ts(info.wipe_time)}** ({elapsed} ago)"


def _cmd_uptime(name: str) -> str:
    elapsed = _fmt_elapsed(int(_time_module.time() - _BOT_START_TIME))
    return f"**Uptime**\n> Bot: {elapsed}\n> Server: `{name}`"


async def _cmd_time(socket, name: str) -> str:
    t = await socket.get_time()
    if isinstance(t, RustError):
        return f"Error: {t.reason}"
    now_f = _parse_time_to_float(t.time)
    sunrise = _parse_time_to_float(t.sunrise)
    sunset = _parse_time_to_float(t.sunset)
    is_day = sunrise <= now_f < sunset
    till_change = _time_till(now_f, sunset if is_day else sunrise)
    phase = f"Till night: {till_change}" if is_day else f"Till day: {till_change}"
    return (
        f"**{name} ” In-Game Time**\n"
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
    url = f"https://rustmaps.com/map/{info.size}_{info.seed}"

    try:
        map_obj = await socket.get_map(add_icons=True, add_events=True, add_vending_machines=False)
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
        log.warning(f"Map image fetch failed: {e} ” falling back to text")
        return (
            f"**{name}**\n"
            f"> **Map:** {info.map}  |  **Seed:** `{info.seed}`  |  **Size:** {info.size}\n"
            f"> [View on RustMaps]({url})"
        )


#  Team Commands
async def _cmd_team(socket) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    if not team.members:
        return "No team members found. Are you in a team in-game?"
    lines = []
    for m in team.members:
        status = "Online" if m.is_online else "Offline"
        alive = "" if m.is_alive else " ” Dead"
        lines.append(f"> **{m.name}** ” {status}{alive}")
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
            + "\n_AFK detection requires position history ” not available via Rust+ API._"
    )


async def _cmd_alive(socket, args: str) -> str:
    team = await socket.get_team_info()
    if isinstance(team, RustError):
        return f"Error: {team.reason}"
    if args:
        match = next((m for m in team.members if args.lower() in m.name.lower()), None)
        if not match:
            return f"No team member found matching `{args}`."
        return f"**{match.name}** ” {'Alive' if match.is_alive else 'Dead'}"
    alive = [m for m in team.members if m.is_alive]
    dead = [m for m in team.members if not m.is_alive]
    lines = [f"> **{m.name}** ” Alive" for m in alive] + \
            [f"> **{m.name}** ” Dead" for m in dead]
    return f"**Team Status ({len(alive)}/{len(team.members)} alive)**\n" + "\n".join(lines)


async def _cmd_leader(socket, args: str) -> str:
    """
    !leader           ” promote self
    !leader <name>    ” promote teammate by name
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


#  Event Commands
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
        return f"**{name}** ” No active events right now."

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
        lines.append(f"> **{EVENT_TYPES[type_id]}** ” active for {age}")

    return f"**{name} ” Active Events**\n" + "\n".join(lines)


async def _cmd_heli(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    helis = list({m.type: m for m in markers if m.type == 3}.values())
    if not helis:
        return f"**{name}** ” No Patrol Helicopter on the map right now."
    h = helis[0]
    return f"**{name} ” Patrol Helicopter**\n> On the map ” Position: `{int(h.x)}, {int(h.y)}`"


async def _cmd_cargo(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ships = list({m.type: m for m in markers if m.type == 4}.values())
    if not ships:
        return f"**{name}** ” No Cargo Ship on the map right now."
    s = ships[0]
    return f"**{name} ” Cargo Ship**\n> On the map ” Position: `{int(s.x)}, {int(s.y)}`"


async def _cmd_chinook(socket, name: str) -> str:
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"
    ch47s = list({m.type: m for m in markers if m.type == 7}.values())
    if not ch47s:
        return f"**{name}** ” No Chinook CH-47 on the map right now."
    c = ch47s[0]
    return f"**{name} ” Chinook CH-47**\n> On the map ” Position: `{int(c.x)}, {int(c.y)}`"


async def _cmd_large(socket, name: str) -> str:
    """Large Oil Rig locked crate tracking"""
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    crates = [m for m in markers if m.type == 6]
    now = _time_module.time()
    LARGE_CRATE_UNLOCK_SECS = 15 * 60

    if not crates:
        last = _event_first_seen.get(60)
        if last:
            ago = int(now - last)
            return (
                f"**{name} ” Large Oil Rig**\n"
                f"> No crate active. Last trigger: **{_fmt_elapsed(ago)} ago**."
            )
        return f"**{name} ” Large Oil Rig**\n> No locked crate active on the map right now."

    if 60 not in _event_first_seen:
        _event_first_seen[60] = now
        _save_event_cache(_event_first_seen)

    elapsed = int(now - _event_first_seen[60])
    remaining = max(0, LARGE_CRATE_UNLOCK_SECS - elapsed)

    if remaining > 0:
        return (
            f"**{name} ” Large Oil Rig**\n"
            f"> Locked Crate active ” unlocks in **{_fmt_elapsed(remaining)}**\n"
            f"> (approx ” based on crate first seen {_fmt_elapsed(elapsed)} ago)"
        )
    else:
        return (
            f"**{name} ” Large Oil Rig**\n"
            f"> Locked Crate should be **unlocked** (crate active for {_fmt_elapsed(elapsed)})"
        )


async def _cmd_small(socket, name: str) -> str:
    """Small Oil Rig locked crate tracking"""
    markers = await socket.get_markers()
    if isinstance(markers, RustError):
        return f"Error: {markers.reason}"

    crates = [m for m in markers if m.type == 6]
    now = _time_module.time()
    UNLOCK = 15 * 60

    if not crates:
        last = _event_first_seen.get(61)
        if last:
            ago = int(now - last)
            return (
                f"**{name} ” Small Oil Rig**\n"
                f"> No crate active. Last trigger: **{_fmt_elapsed(ago)} ago**."
            )
        return f"**{name} ” Small Oil Rig**\n> No locked crate active on the map right now."

    if 61 not in _event_first_seen:
        _event_first_seen[61] = now
        _save_event_cache(_event_first_seen)

    elapsed = int(now - _event_first_seen[61])
    remaining = max(0, UNLOCK - elapsed)

    if remaining > 0:
        return (
            f"**{name} ” Small Oil Rig**\n"
            f"> Locked Crate active ” unlocks in **{_fmt_elapsed(remaining)}**\n"
            f"> (approx ” based on crate first seen {_fmt_elapsed(elapsed)} ago)"
        )
    return (
        f"**{name} ” Small Oil Rig**\n"
        f"> Locked Crate should be **unlocked** (active for {_fmt_elapsed(elapsed)})"
    )



# Game Info Commands (imported from rust_info_db.py)

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
    k, data = _fuzzy_match(args, CRAFT_DATA)
    if not data:
        return f"No craft data for `{args}`."
    return f"**Craft: {k.title()}**\n> " + ", ".join(f"**{v}x {n}**" for n, v in data.items())


def _cmd_recycle(args: str) -> str:
    if not args:
        return "Usage: `!recycle <item>`"
    k, data = _fuzzy_match(args, RECYCLE_DATA)
    if not data:
        return f"No recycle data for `{args}`."
    return f"**Recycle: {k.title()}**\n> " + ", ".join(f"**{v}x {n}**" for n, v in data.items())


def _cmd_research(args: str) -> str:
    if not args:
        return "Usage: `!research <item>`"
    k, cost = _fuzzy_match(args, RESEARCH_DATA)
    if cost is None:
        return f"No research data for `{args}`."
    return f"**Research: {k.title()}**\n> Cost: **{cost} Scrap**"


def _cmd_decay(args: str) -> str:
    if not args:
        return "Usage: `!decay <item>`"
    k, hours = _fuzzy_match(args, DECAY_DATA)
    if hours is None:
        return f"No decay data for `{args}`."
    return f"**Decay: {k.title()}**\n> Full HP decays in **{hours}h**"


def _cmd_upkeep_item(args: str) -> str:
    if not args:
        return "Usage: `!upkeep <item>`"
    k, data = _fuzzy_match(args, UPKEEP_DATA)
    if not data:
        return f"No upkeep data for `{args}`."
    cost = ", ".join(f"**{v}x {n}**" for n, v in data.items())
    return f"**Upkeep: {k.title()}**\n> Per hour (TC range): {cost}"


def _cmd_item(args: str) -> str:
    if not args:
        return "Usage: `!item <name>`"
    lines = []
    _, craft = _fuzzy_match(args, CRAFT_DATA)
    _, research = _fuzzy_match(args, RESEARCH_DATA)
    _, recycle = _fuzzy_match(args, RECYCLE_DATA)
    _, decay = _fuzzy_match(args, DECAY_DATA)
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
        keys = ", ".join(f"`{k}`" for k in sorted(CCTV_DATA))
        return f"Usage: `!cctv <monument>`\nAvailable: {keys}"
    k, codes = _fuzzy_match(args, CCTV_DATA)
    if not codes:
        return f"No CCTV codes for `{args}`."
    return f"**CCTV ” {k.title()}**\n" + "\n".join(f"> `{c}`" for c in codes)


#  Game Q&A (fallback)
def cmd_game_question(query: str) -> str:
    q = query.lower()
    qa = {
        ("sulfur", "stone", "wall"): "**Stone Wall:** Satchels: **10** | C4: **2** | Rockets: **4** (~1,500 sulfur)",
        ("sulfur", "sheet", "metal"): "**Sheet Metal Wall:** Satchels: **4** | C4: **1** | Rockets: **2** (~1,000 sulfur)",
        ("sulfur", "armored"): "**Armored Wall:** C4: **4** | Rockets: **8** | Satchels: **12** (~4,000 sulfur)",
        ("scrap", "farm"): "**Best Scrap Farming:**\n> Tier 1 monuments (Gas Station, Supermarket)\n> Recycle components\n> Oil Rig = massive scrap (high risk)",
        ("best", "weapon", "early"): "**Best Early Weapons:**\n> 1. Bow\n> 2. Crossbow\n> 3. Pipe Shotgun",
        ("bradley", "apc"): "**Bradley APC:**\n> Launch Site\n> HV rockets or 40mm HE\n> Drops 3 Bradley Crates",
        ("cargo", "ship"): "**Cargo Ship:**\n> Spawns ~every 2 hours\n> 2 locked crates every ~15min\n> Heavy scientists ” bring armor",
        ("radiation",): "**Radiation:**\n> Gas Station/Supermarket: 4 RAD\n> Airfield: 10 RAD\n> Water Treatment: 15 RAD\n> Launch Site: 50 RAD",
    }
    for keywords, answer in qa.items():
        if all(kw in q for kw in keywords):
            return answer
    return f"No answer for: *\"{query}\"*\n\nTry: `help`"


#  Helper Functions
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
    """
    Calculate real-world time until target in-game time.

    Rust time mechanics:
    - 24-hour in-game cycle = 60 real minutes
    - 1 in-game hour = 2.5 real minutes
    - Day: ~45 minutes (sunrise to sunset)
    - Night: ~15 minutes (sunset to sunrise)
    """
    # Calculate in-game hours until target
    diff = (target - now) % 24

    # Convert to real-world minutes: 1 in-game hour = 2.5 real minutes
    real_minutes = diff * 2.5

    # Format output
    if real_minutes < 1:
        seconds = int(real_minutes * 60)
        return f"{seconds}s"
    elif real_minutes < 60:
        return f"{int(real_minutes)}m"
    else:
        hours = int(real_minutes // 60)
        mins = int(real_minutes % 60)
        return f"{hours}h {mins}m"


# ===== Storage Monitor Commands =====

async def cmd_add_storage(
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !addSM <name> <entity_id>
    Add a storage monitor to track a storage container.
    """
    if not args:
        return (
            "Usage: `!addSM <name> <entity_id>`\n"
            "Example: `!addSM main_loot 12345678`\n\n"
            "Get entity IDs from Rust+ app when pairing storage containers."
        )
    
    parts = args.split(None, 1)
    if len(parts) != 2:
        return "Usage: `!addSM <name> <entity_id>`"
    
    name, entity_id_str = parts
    
    # Validate entity ID
    try:
        entity_id = int(entity_id_str)
    except ValueError:
        return f"Invalid entity ID: `{entity_id_str}`. Must be a number."
    
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected. Use `!change <server>` to connect first."
    
    server_key = f"{active['ip']}:{active['port']}"
    
    success, message = storage_manager.add_monitor(
        discord_id, server_key, name, entity_id
    )
    
    if success:
        message += f"\n\nCheck it with: `!viewSM {name}`"
    
    return message


async def cmd_view_storage(
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str | discord.Embed | tuple:
    """
    !viewSM [name]
    View contents of a storage monitor (or all if no name given).
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."
    
    socket = manager.get_socket_for_user(discord_id)
    if not socket:
        return "Not connected to server."
    
    server_key = f"{active['ip']}:{active['port']}"
    user = user_manager.get_user(discord_id)
    
    if not args:
        # Show all storage monitors
        results = await storage_manager.check_all_for_user(socket, discord_id, server_key)
        
        if not results:
            return (
                f"**Storage Monitors on {active.get('name', active['ip'])}**\n"
                "No storage monitors configured yet.\n\n"
                "Use `!addSM <name> <entity_id>` to add one."
            )
        
        # Return first storage as embed
        embed = format_storage_embed(results[0], user.get('discord_name'))
        
        # If multiple storages, add summary
        if len(results) > 1:
            other_names = [s['name'] for s in results[1:]]
            embed.add_field(
                name=f"Other Storages ({len(results) - 1})",
                value=", ".join(f"`{n}`" for n in other_names),
                inline=False
            )
        
        return embed
    
    # View specific storage
    name = args.strip()
    success, data = await storage_manager.check_storage(
        socket, discord_id, server_key, name
    )
    
    if not success:
        return data  # Error message
    
    embed = format_storage_embed(data, user.get('discord_name'))
    return embed


async def cmd_remove_storage(
        args: str,
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !deleteSM <name>
    Remove a storage monitor.
    """
    if not args:
        return "Usage: `!deleteSM <name>`"
    
    name = args.strip()
    
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."
    
    server_key = f"{active['ip']}:{active['port']}"
    
    success, message = storage_manager.remove_monitor(discord_id, server_key, name)
    return message


def cmd_list_storages(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !storages
    List all storage monitors for the current server.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."
    
    server_key = f"{active['ip']}:{active['port']}"
    monitors = storage_manager.get_monitors_for_user(discord_id, server_key)
    
    if not monitors:
        return (
            f"**Storage Monitors on {active.get('name', active['ip'])}**\n"
            "No storage monitors configured yet.\n\n"
            "Use `!addSM <name> <entity_id>` to add one."
        )
    
    lines = []
    for monitor in monitors:
        lines.append(f"`{monitor['name']}` - Entity ID: `{monitor['entity_id']}`")
    
    return (
        f"**Storage Monitors on {active.get('name', active['ip'])}** ({len(monitors)})\n" +
        "\n".join(lines) +
        "\n\nCheck contents: `!viewSM <name>`"
    )


# ===== Death Tracker Commands =====

async def cmd_death_history(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> discord.Embed:
    """
    !deaths
    Show recent death history for the current server.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return discord.Embed(
            title="Death History",
            description="You need to register first.",
            color=0xFF0000
        )
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return discord.Embed(
            title="Death History",
            description="No server connected.",
            color=0xFF0000
        )
    
    server_key = f"{active['ip']}:{active['port']}"
    deaths = death_tracker.get_recent_deaths(discord_id, server_key, count=10)
    
    embed = format_death_history_embed(deaths, active.get('name', active['ip']))
    return embed


async def cmd_clear_deaths(
        manager: MultiUserServerManager,
        user_manager: UserManager,
        discord_id: str
) -> str:
    """
    !cleardeaths
    Clear death history for the current server.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."
    
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."
    
    server_key = f"{active['ip']}:{active['port']}"
    success, message = death_tracker.clear_history(discord_id, server_key)
    
    return message


