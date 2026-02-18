"""
commands_multiuser_patch.py
────────────────────────────────────────────────────────────────────────────
This file contains the UPDATED versions of functions in commands.py that need
to be modified for multi-user support.

CHANGES NEEDED:
1. Add discord_id parameter to handle_query and other functions
2. Fix manager method calls to use multi-user equivalents
3. Fix smart switch methods to use correct API

Replace the corresponding functions in commands.py with these versions.
"""

from typing import Optional
from rustplus import RustSocket
from server_manager_multiuser import MultiUserServerManager
from multi_user_auth import UserManager

# ── UPDATED handle_query ──────────────────────────────────────────────────────
async def handle_query(
    query: str, 
    manager: MultiUserServerManager,
    user_manager: UserManager,
    ctx=None,
    discord_id: Optional[str] = None
) -> str | tuple:
    """
    UPDATED VERSION for multi-user support.
    
    Changes:
    - Added user_manager parameter
    - Added discord_id parameter
    - Uses per-user connection methods
    - Checks user registration before live commands
    """
    parts = query.strip().split(None, 1)
    cmd   = parts[0].lower()
    args  = parts[1].strip() if len(parts) > 1 else ""

    # User registration commands (NEW)
    if cmd == "register":
        from multi_user_auth import cmd_register
        return await cmd_register(ctx, user_manager)
    if cmd == "whoami":
        from multi_user_auth import cmd_whoami
        return await cmd_whoami(ctx, user_manager)
    if cmd == "users":
        from multi_user_auth import cmd_users
        return await cmd_users(ctx, user_manager)
    if cmd == "unregister":
        from multi_user_auth import cmd_unregister
        return await cmd_unregister(ctx, user_manager)

    # Meta / no-socket commands
    if cmd in ("servers", "server"):
        return cmd_servers_multiuser(manager, user_manager, discord_id)
    if cmd == "clear":
        return await cmd_clear(args, ctx)
    if cmd == "switch":
        return await cmd_switch_multiuser(args, manager, user_manager, discord_id)
    if cmd == "help":
        return cmd_help()
    if cmd in ("timer", "timers"):
        return await cmd_timer(args)
    if cmd in ("sson", "ssoff"):
        return await cmd_smart_switch_multiuser(cmd, args, manager, user_manager, discord_id)

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
                "You need to register first.\n"
                "DM the bot with `!register` and attach your `rustplus.config.json` file.\n"
                "Get the config file by running `pair.bat` on your computer."
            )

        # Get user's active server
        active = manager.get_active_server_for_user(discord_id)
        if not active:
            return (
                "No server connected.\n"
                "Join a Rust server and press **ESC → Rust+ → Pair Server**."
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


# ── UPDATED cmd_servers ───────────────────────────────────────────────────────
def cmd_servers_multiuser(
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
            "Join any Rust server and press **ESC → Rust+ → Pair Server**."
        )

    lines = []
    for i, s in enumerate(servers, 1):
        is_active = active and s["ip"] == active["ip"] and s["port"] == active["port"]
        tag = "`active`" if is_active else f"`{i}.`"
        lines.append(f"{tag} **{s.get('name', s['ip'])}** — `{s['ip']}:{s['port']}`")

    return "**Your Paired Servers:**\n" + "\n".join(lines) + \
        "\n\nUse `!switch <name or number>` to switch."


# ── UPDATED cmd_switch ────────────────────────────────────────────────────────
async def cmd_switch_multiuser(
    identifier: str,
    manager: MultiUserServerManager,
    user_manager: UserManager,
    discord_id: str
) -> str:
    """Switch user's active server"""
    if not identifier:
        return "Usage: `!switch <server name or number>`"

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


# ── UPDATED cmd_smart_switch ──────────────────────────────────────────────────
async def cmd_smart_switch_multiuser(
    cmd: str,
    args: str,
    manager: MultiUserServerManager,
    user_manager: UserManager,
    discord_id: str
) -> str:
    """
    !sson <name or entity_id>
    !ssoff <name or entity_id>
    
    FIXED: Uses correct RustSocket API methods
    """
    if not args:
        # Load registered switches
        from commands import _switches
        registered = ", ".join(f"`{k}` ({v})" for k, v in _switches.items())
        hint = f"\nRegistered switches: {registered}" if registered else \
            "\nNo switches registered yet. Add them to `switches.json` as `{\"name\": entity_id}`."
        return f"Usage: `!sson <name or id>` / `!ssoff <name or id>`{hint}"

    # Check user registration
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first."

    # Resolve switch name/ID
    from commands import _resolve_switch
    entity_id = _resolve_switch(args)
    if entity_id is None:
        return (
            f"Switch `{args}` not found.\n"
            f"Add it to `switches.json` as `{{\"name\": entity_id}}`, "
            f"or use the entity ID directly."
        )

    # Get active connection
    active = manager.get_active_server_for_user(discord_id)
    if not active:
        return "No server connected."

    try:
        await manager.ensure_connected_for_user(discord_id)
        socket = manager.get_socket_for_user(discord_id)

        if cmd == "sson":
            result = await socket.set_entity_value(entity_id, True)
        else:
            result = await socket.set_entity_value(entity_id, False)

        # Check for errors
        from rustplus import RustResponse
        if hasattr(result, 'error') and result.error:
            return f"Error: {result.error}"

        state = "ON" if cmd == "sson" else "OFF"
        label = args if args.isdigit() else f"{args} ({entity_id})"
        return f"Smart Switch **{label}** turned **{state}**."

    except AttributeError as e:
        return (
            f"Smart switch control failed: {e}\n"
            "Your rustplus library version may not support smart switches.\n"
            "Try: `pip install --upgrade rustplus`"
        )
    except Exception as e:
        return f"Could not toggle switch: `{e}`"


# ── Import dependencies ───────────────────────────────────────────────────────
import logging
from commands import (
    cmd_clear, cmd_help, cmd_timer, cmd_game_question,
    _dispatch_live, _switches, _resolve_switch
)

log = logging.getLogger("Commands")
