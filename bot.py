"""
bot_multiuser_updated.py
────────────────────────────────────────────────────────────────────────────
UPDATED bot.py for multi-user support.

KEY CHANGES FROM ORIGINAL:
1. Uses MultiUserServerManager instead of ServerManager
2. Uses UserManager for credential management
3. Passes discord_id to command handlers
4. Updated FCM listener and connection methods
5. Fixed smart switch and other method calls

MIGRATION:
- Back up your original bot.py
- Replace with this version
- Update imports as shown below
"""

import asyncio
import io
import os
import logging
import re

import discord
from discord.ext import commands
from dotenv import load_dotenv

# UPDATED IMPORTS
from multi_user_auth import UserManager, cmd_register, cmd_whoami, cmd_users, cmd_unregister
from server_manager_multiuser import MultiUserServerManager
from commands_multiuser_patch import handle_query
from timers import timer_manager

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN        = os.getenv("DISCORD_TOKEN")
COMMAND_CHANNEL      = int(os.getenv("COMMAND_CHANNEL_ID", "0"))
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))
CHAT_RELAY_CHANNEL   = int(os.getenv("CHAT_RELAY_CHANNEL_ID", "0"))
COMMAND_PREFIX       = "!"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("RustBot")

# ── Discord Client ────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# UPDATED: Use multi-user managers
user_manager = UserManager()
manager = MultiUserServerManager(user_manager)


# ── Notification helper ───────────────────────────────────────────────────────
async def notify(embed: discord.Embed, file: discord.File = None):
    """Send an embed (optionally with a file) to the notification channel."""
    if not NOTIFICATION_CHANNEL:
        return
    channel = bot.get_channel(NOTIFICATION_CHANNEL)
    if channel:
        await channel.send(embed=embed, file=file)
    else:
        log.warning(f"Notification channel {NOTIFICATION_CHANNEL} not found")


# ── Parse Time helper ─────────────────────────────────────────────────────────
def _parse_time_to_float(t) -> float:
    """Convert time from string ('19:21') or float (19.35) to float."""
    try:
        if isinstance(t, str) and ":" in t:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h + (m / 60.0)
        return float(t)
    except Exception:
        return 0.0


def _fmt_time_val(t) -> str:
    try:
        if isinstance(t, str) and ":" in t:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        h = int(float(t))
        m = int((float(t) - h) * 60)
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return str(t)


# ── Server connect embed ──────────────────────────────────────────────────────
async def _post_server_connect_embed(server: dict, socket):
    """
    UPDATED: Takes socket as parameter instead of getting from manager
    """
    if not socket:
        return

    name = server.get("name", server["ip"])
    ip = server["ip"]
    port = server.get("port", "28017")

    try:
        import time as _t
        from datetime import datetime, timezone

        info = await socket.get_info()
        time_obj = await socket.get_time()

        wipe_ts = getattr(info, "wipe_time", 0) or 0
        now_ts = int(_t.time())
        wipe_days = (now_ts - wipe_ts) / 86400 if wipe_ts else None
        wipe_str = f"{wipe_days:.1f} days" if wipe_days is not None else "Unknown"

        now_ig = _parse_time_to_float(time_obj.time)
        sunset = _parse_time_to_float(time_obj.sunset)
        sunrise = _parse_time_to_float(time_obj.sunrise)

        is_day = _parse_time_to_float(time_obj.sunrise) <= now_ig < sunset
        if is_day:
            diff_h = (sunset - now_ig) % 24
            till_night = f"~{int(diff_h * 2.5)}m"
        else:
            till_night = "Night"

        players_str = f"{info.players}/{info.max_players}"
        if info.queued_players:
            players_str += f" ({info.queued_players} queued)"

        embed = discord.Embed(
            title=f"Connected — {name}",
            color=0xCE422B,
        )
        embed.add_field(name="Players", value=players_str, inline=True)
        embed.add_field(name="In-Game Time", value=_fmt_time_val(time_obj.time), inline=True)
        embed.add_field(name="Till Night", value=till_night, inline=True)
        embed.add_field(name="Since Wipe", value=wipe_str, inline=True)
        embed.add_field(name="Map Size", value=str(info.size), inline=True)
        embed.add_field(name="Seed", value=str(info.seed), inline=True)
        embed.add_field(name="Map", value=info.map, inline=True)
        embed.add_field(name="Connect", value=f"`connect {ip}:{port}`", inline=False)
        embed.set_footer(text=f"{ip}:{port}")

        await notify(embed)

    except Exception as e:
        log.warning(f"Could not build server connect embed: {e}")
        await notify(discord.Embed(
            title=f"Connected — {name}",
            description=f"`{ip}:{port}`",
            color=0xCE422B,
        ))


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    _log_channel_config()

    # Register chat relay callback
    if CHAT_RELAY_CHANNEL:
        manager.on_team_message(_on_rust_chat_message)
        log.info("Chat callback registered")

    # Wire timer expiry → notification channel
    timer_manager.set_notify_callback(_on_timer_expired)
    bot.loop.create_task(timer_manager.run_loop())
    log.info("Timer loop started")

    # UPDATED: Start FCM listeners for all registered users
    bot.loop.create_task(manager.start_all_fcm_listeners(on_new_server_paired))
    log.info("Multi-user FCM listeners active")

    # Show registration status
    user_count = len(user_manager.list_users())
    if user_count == 0:
        log.info("No users registered yet. Users should DM bot with !register")
        await notify(discord.Embed(
            title="Bot Online - Multi-User Mode",
            description=(
                "No users registered yet.\n\n"
                "**To register:**\n"
                "1. Run `pair.bat` on your computer\n"
                "2. DM the bot with `!register` + your config file\n"
                "3. Join any Rust server and pair it in-game"
            ),
            color=0xCE422B,
        ))
    else:
        await notify(discord.Embed(
            title="Bot Online - Multi-User Mode",
            description=f"**{user_count}** user(s) registered and ready!",
            color=0xCE422B,
        ))


def _log_channel_config():
    def _ch(cid):
        if not cid:
            return "not set"
        ch = bot.get_channel(cid)
        return f"#{ch.name}" if ch else f"ID {cid} not found"

    log.info("Channel config:")
    log.info(f"  Commands      -> {_ch(COMMAND_CHANNEL)}")
    log.info(f"  Notifications -> {_ch(NOTIFICATION_CHANNEL)}")
    log.info(f"  Chat relay    -> {_ch(CHAT_RELAY_CHANNEL)}")


async def on_new_server_paired(discord_id: str, server: dict):
    """
    UPDATED: Called when a user pairs a new server.
    Now receives discord_id to identify which user paired it.
    """
    user = user_manager.get_user(discord_id)
    if not user:
        return

    name = server.get("name", server["ip"])
    log.info(f"New server paired by {user['discord_name']}: {name}")

    # Get the socket for this user
    socket = manager.get_socket_for_user(discord_id)
    if socket:
        await _post_server_connect_embed(server, socket)


async def _on_timer_expired(label: str, text: str):
    """Called by TimerManager when a timer fires."""
    embed = discord.Embed(
        title="Timer Expired",
        description=f"**{text}**\n_(was set for {label})_",
        color=0xCE422B,
    )
    await notify(embed)


# ── In-game → Discord ─────────────────────────────────────────────────────────
async def _on_rust_chat_message(event):
    """Callback fired when team chat message arrives in-game."""
    if not CHAT_RELAY_CHANNEL:
        return

    msg = event.message

    if msg.message.lower().startswith("!"):
        query = msg.message[1:].strip()
        log.info(f"In-game command from [{msg.name}]: {query!r}")
        # NOTE: In-game commands use bot owner's credentials by default
        # To support per-user in-game commands, would need to map steam_id to discord_id
        await _handle_ingame_command(query, msg.name)
        return

    channel = bot.get_channel(CHAT_RELAY_CHANNEL)
    if not channel:
        try:
            channel = await bot.fetch_channel(CHAT_RELAY_CHANNEL)
        except Exception as e:
            log.error(f"Could not fetch relay channel: {e}")
            return

    try:
        embed = discord.Embed(title=msg.name, description=msg.message, color=0xCE422B)
        embed.set_footer(text="Rust+ Team Chat")
        await channel.send(embed=embed)
        log.info(f"<- Rust: [{msg.name}] {msg.message}")
    except Exception as e:
        log.error(f"Failed to relay Rust->Discord: {e}")


async def _handle_ingame_command(query: str, player_name: str):
    """
    Run command from in-game.
    NOTE: Uses first registered user's credentials as fallback.
    """
    # Get first registered user
    users = user_manager.list_users()
    if not users:
        return

    discord_id = users[0]["discord_id"]
    socket = manager.get_socket_for_user(discord_id)
    
    if not socket:
        return

    try:
        response = await handle_query(query, manager, user_manager, ctx=None, discord_id=discord_id)
        if response is None:
            return
        if isinstance(response, tuple):
            response = response[0]
        clean = re.sub(r"[*`_>\[\]()]", "", response)
        lines = [l for l in clean.splitlines() if l.strip()]
        for line in lines[:6]:
            await socket.send_team_message(line[:128])
    except Exception as e:
        log.error(f"In-game command error: {e}")


# ── Message Handler ───────────────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.lower()

    # Chat relay: forward Discord → Rust
    if CHAT_RELAY_CHANNEL and message.channel.id == CHAT_RELAY_CHANNEL:
        if not content_lower.startswith(COMMAND_PREFIX):
            await _relay_discord_to_rust(message)
        return

    if not content_lower.startswith(COMMAND_PREFIX):
        await bot.process_commands(message)
        return

    # Ignore commands outside allowed channels (COMMAND, NOTIFICATION, CHAT_RELAY), except DMs for registration
    allowed_channel_ids = {cid for cid in (COMMAND_CHANNEL, NOTIFICATION_CHANNEL, CHAT_RELAY_CHANNEL) if cid}
    if allowed_channel_ids and message.channel.id not in allowed_channel_ids:
        # Allow DM commands for registration
        if not isinstance(message.channel, discord.DMChannel):
            return

    query = message.content[len(COMMAND_PREFIX):].strip()
    log.info(f"[{message.author}] ! {query or '(empty)'}")

    # Get Discord user ID for per-user commands
    discord_id = str(message.author.id)

    if not query:
        user = user_manager.get_user(discord_id)
        if user:
            servers = manager.list_servers_for_user(discord_id)
            server_info = f"**{len(servers)}** paired server(s)" if servers else "No servers paired"
        else:
            server_info = "Not registered"

        await message.reply(
            f"**Rust+ Companion Bot - Multi-User Mode**\n"
            f"> Your status: {server_info}\n\n"
            f"**Commands:**\n"
            f"`register` · `whoami` · `servers` · `status` · `players` · `time`\n"
            f"`map` · `team` · `events` · `wipe` · `switch <name>`\n"
            f"`timer add <time> <label>` · `timers`\n"
            f"`sson <id>` · `ssoff <id>`\n\n"
            f"**New user?** DM the bot with `!register`"
        )
        return

    async with message.channel.typing():
        try:
            # UPDATED: Pass discord_id to handler
            response = await handle_query(query, manager, user_manager, ctx=message, discord_id=discord_id)
            if response is None:
                return
        except Exception as e:
            log.error(f"Command error: {e}", exc_info=True)
            response = f"Error: `{e}`"

    # Handle text or (text, image) response
    if isinstance(response, tuple):
        text, img_bytes = response
        try:
            file = discord.File(io.BytesIO(img_bytes), filename="map.jpg")
            await message.reply(content=text, file=file)
        except Exception as e:
            log.error(f"Could not send map image: {e}")
            await message.reply(text)
    else:
        for chunk in _split(response):
            await message.reply(chunk)


# ── Discord → In-game ─────────────────────────────────────────────────────────
async def _relay_discord_to_rust(message: discord.Message):
    """
    Forward Discord message to in-game team chat.
    Uses first online user's socket.
    """
    # Try to find an active socket
    for discord_id, socket in manager._active_sockets.items():
        if socket:
            try:
                await socket.send_team_message(message.content[:128])
                log.info(f"-> Rust: {message.content[:70]}")
                return
            except Exception as e:
                log.warning(f"Could not relay to Rust: {e}")

    log.warning("Discord->Rust relay skipped: no active sockets")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _split(text: str, limit: int = 1990) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > limit:
            chunks.append(cur)
            cur = ""
        cur += line
    if cur:
        chunks.append(cur)
    return chunks


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN not set in .env — see README")
    bot.run(DISCORD_TOKEN, log_handler=None)
