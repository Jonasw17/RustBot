"""
Rust+ Discord Companion Bot — bot.py
────────────────────────────────────────────────────────────────────────────
Three dedicated channels:
  COMMAND_CHANNEL_ID      → ! commands and their replies
  NOTIFICATION_CHANNEL_ID → pairing alerts, server switches, bot status
  CHAT_RELAY_CHANNEL_ID   → in-game team chat ↔ Discord relay (bidirectional)
"""

import asyncio
import io
import os
import logging
import re

import discord
from discord.ext import commands
from dotenv import load_dotenv

from server_manager import ServerManager
from commands import handle_query
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

bot     = commands.Bot(command_prefix="!", intents=intents, help_command=None)
manager = ServerManager()


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

# ── Parse Time helper ───────────────────────────────────────────────────────
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
        # Handle string format like "19:21"
        if isinstance(t, str) and ":" in t:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        # Handle float format like 19.35
        h = int(float(t))
        m = int((float(t) - h) * 60)
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return str(t)

# ── Server connect embed ──────────────────────────────────────────────────────
async def _post_server_connect_embed(server: dict):
    """
    Posts a rich embed to the notification channel when connected to a server.
    Includes: players online, in-game time, days since wipe, time till nightfall,
    map size, map seed, map id, and direct connect string.
    """
    socket = manager.get_socket()
    if not socket:
        return

    name = server.get("name", server["ip"])
    ip   = server["ip"]
    port = server.get("port", "28017")

    try:
        import time as _t
        from datetime import datetime, timezone

        info = await socket.get_info()
        time_obj = await socket.get_time()

        # Days since wipe (real-time)
        wipe_ts    = getattr(info, "wipe_time", 0) or 0
        now_ts     = int(_t.time())
        wipe_days  = (now_ts - wipe_ts) / 86400 if wipe_ts else None
        wipe_str   = f"{wipe_days:.1f} days" if wipe_days is not None else "Unknown"

        # Time till nightfall (in-game hours → real minutes, ~2.5 min per in-game hour)
        now_ig  = _parse_time_to_float(time_obj.time)
        sunset  = _parse_time_to_float(time_obj.sunset)
        sunrise = _parse_time_to_float(time_obj.sunrise)

        is_day   = _parse_time_to_float(time_obj.sunrise) <= now_ig < sunset
        if is_day:
            diff_h       = (sunset - now_ig) % 24
            till_night   = f"~{int(diff_h * 2.5)}m"
        else:
            till_night   = "Night"

        players_str = f"{info.players}/{info.max_players}"
        if info.queued_players:
            players_str += f" ({info.queued_players} queued)"

        embed = discord.Embed(
            title=f"Connected — {name}",
            color=0xCE422B,
        )
        embed.add_field(name="Players",        value=players_str,              inline=True)
        embed.add_field(name="In-Game Time",   value=_fmt_time_val(time_obj.time), inline=True)
        embed.add_field(name="Till Night",     value=till_night,               inline=True)
        embed.add_field(name="Since Wipe",     value=wipe_str,                 inline=True)
        embed.add_field(name="Map Size",       value=str(info.size),           inline=True)
        embed.add_field(name="Seed",           value=str(info.seed),           inline=True)
        embed.add_field(name="Map",            value=info.map,                 inline=True)
        embed.add_field(name="Connect",        value=f"`connect {ip}:{port}`", inline=False)
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

    # Register in-game → Discord chat callback
    if CHAT_RELAY_CHANNEL:
        manager.on_team_message(_on_rust_chat_message)
        log.info("Chat callback registered")

    # Wire timer expiry → notification channel
    timer_manager.set_notify_callback(_on_timer_expired)
    bot.loop.create_task(timer_manager.run_loop())
    log.info("Timer loop started")

    # Reconnect to last active server
    active = manager.get_active()
    if active:
        try:
            await manager.connect(active["ip"], active["port"])
            name = active.get("name", active["ip"])
            log.info(f"Reconnected to: {name}")
            await _post_server_connect_embed(active)
        except Exception as e:
            log.warning(f"Could not reconnect: {e}")
            await notify(discord.Embed(
                title="Reconnect Failed",
                description=f"Could not reach last server: `{e}`\nPair a server in-game to reconnect.",
                color=0xFF6B35,
            ))
    else:
        log.info("No saved servers. Pair one in-game (ESC -> Session -> Pairing).")
        await notify(discord.Embed(
            title="Bot Online",
            description=(
                "No server paired yet.\n"
                "Join a Rust server and press **ESC -> Session -> Pairing**."
            ),
            color=0xCE422B,
        ))

    # Start FCM pairing listener
    bot.loop.create_task(manager.listen_for_pairings(on_new_server_paired))
    log.info("FCM listener active")


def _log_channel_config():
    def _ch(cid):
        if not cid: return "not set"
        ch = bot.get_channel(cid)
        return f"#{ch.name}" if ch else f"ID {cid} not found"
    log.info("Channel config:")
    log.info(f"  Commands      -> {_ch(COMMAND_CHANNEL)}")
    log.info(f"  Notifications -> {_ch(NOTIFICATION_CHANNEL)}")
    log.info(f"  Chat relay    -> {_ch(CHAT_RELAY_CHANNEL)}")


async def on_new_server_paired(server: dict):
    """Called when a new server is paired in-game."""
    name = server.get("name", server["ip"])
    log.info(f"New server paired: {name}")
    await _post_server_connect_embed(server)


async def _on_timer_expired(label: str, text: str):
    """Called by TimerManager when a timer fires."""
    embed = discord.Embed(
        title="Timer Expired",
        description=f"**{text}**\n_(was set for {label})_",
        color=0xCE422B,
    )
    await notify(embed)
    # Also send to team chat in-game if connected
    socket = manager.get_socket()
    if socket:
        try:
            msg = f"[Timer] {text}"[:128]
            await socket.send_team_message(msg)
        except Exception:
            pass


# ── In-game → Discord ─────────────────────────────────────────────────────────
async def _on_rust_chat_message(event):
    """Callback fired by ChatEvent when a team chat message arrives in-game."""
    if not CHAT_RELAY_CHANNEL:
        return

    msg = event.message

    if msg.message.lower().startswith("!"):
        query = msg.message[5:].strip()
        log.info(f"In-game command from [{msg.name}]: {query!r}")
        await _handle_ingame_command(query, msg.name)
        return

    channel = bot.get_channel(CHAT_RELAY_CHANNEL)
    if not channel:
        try:
            channel = await bot.fetch_channel(CHAT_RELAY_CHANNEL)
        except discord.NotFound:
            log.error(f"Relay channel {CHAT_RELAY_CHANNEL} not found")
            return
        except discord.Forbidden:
            log.error(f"Bot lacks permission for channel {CHAT_RELAY_CHANNEL}")
            return
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
    """Run a ! command from in-game and send the result back to team chat."""
    socket = manager.get_socket()
    if not socket:
        return
    try:
        response = await handle_query(query, manager, ctx=None)
        if response is None:
            return
        # If response is a tuple (map command returns image), just send the text part
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
    is_command = content_lower.startswith(COMMAND_PREFIX)

    # !clear works in every channel — handle it before any channel gating
    if is_command:
        parts = message.content[len(COMMAND_PREFIX):].strip().split(None, 1)
        if parts and parts[0].lower() == "clear":
            args = parts[1].strip() if len(parts) > 1 else ""
            log.info(f"[{message.author}] !clear {args} in #{message.channel.name}")
            async with message.channel.typing():
                from commands import cmd_clear
                response = await cmd_clear(args, message)
            if response is not None:
                await message.reply(response)
            return

    # Chat relay channel: forward Discord → Rust (non-commands only)
    if CHAT_RELAY_CHANNEL and message.channel.id == CHAT_RELAY_CHANNEL:
        if not is_command:
            await _relay_discord_to_rust(message)
        return

    if not is_command:
        await bot.process_commands(message)
        return

    # Ignore other ! commands outside the command channel
    if COMMAND_CHANNEL and message.channel.id != COMMAND_CHANNEL:
        return

    query = message.content[len(COMMAND_PREFIX):].strip()
    log.info(f"[{message.author}] ! {query or '(empty)'}")

    if not query:
        active = manager.get_active()
        server_name = active.get("name", "none") if active else "none"
        await message.reply(
            f"**Rust+ Companion Bot**\n"
            f"> Currently on: **{server_name}**\n\n"
            f"**Commands:**\n"
            f"`status` - `players` - `time` - `map` - `team` - `events` - `wipe`\n"
            f"`timer add <time> <label>` - `timers` - `sson <id>` - `ssoff <id>`\n"
            f"`servers` - `switch <name or #>`\n\n"
            f"Join a Rust server and press **ESC -> Session -> Pairing** to connect."
        )
        return

    async with message.channel.typing():
        try:
            response = await handle_query(query, manager, ctx=message)
            # Add None check after getting response:
            if response is None:
                return
        except Exception as e:
            log.error(f"Command error: {e}", exc_info=True)
            response = f"Error: `{e}`"

    # handle_query may return a plain string or (text, image_bytes) for !map
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
    socket = manager.get_socket()
    if not socket:
        log.warning("Discord->Rust relay skipped: no active socket")
        return
    try:
        await socket.send_team_message(message.content[:128])
        log.info(f"-> Rust: {message.content[:70]}")
    except Exception as e:
        log.warning(f"Could not relay Discord->Rust: {e}")


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