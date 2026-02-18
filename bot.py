"""
Rust+ Discord Companion Bot — bot.py
────────────────────────────────────────────────────────────────────────────
Three dedicated channels:
  COMMAND_CHANNEL_ID      → !rust commands and their replies
  NOTIFICATION_CHANNEL_ID → pairing alerts, server switches, bot status
  CHAT_RELAY_CHANNEL_ID   → in-game team chat ↔ Discord relay (bidirectional)
"""

import asyncio
import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from server_manager import ServerManager
from commands import handle_query

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN        = os.getenv("DISCORD_TOKEN")
COMMAND_CHANNEL      = int(os.getenv("COMMAND_CHANNEL_ID", "0"))
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))
CHAT_RELAY_CHANNEL   = int(os.getenv("CHAT_RELAY_CHANNEL_ID", "0"))
COMMAND_PREFIX       = "!rust"

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
manager = ServerManager()


# ── Notification helper ───────────────────────────────────────────────────────
async def notify(embed: discord.Embed):
    """Send an embed to the notification channel."""
    if not NOTIFICATION_CHANNEL:
        return
    channel = bot.get_channel(NOTIFICATION_CHANNEL)
    if channel:
        await channel.send(embed=embed)
    else:
        log.warning(f"Notification channel {NOTIFICATION_CHANNEL} not found — check NOTIFICATION_CHANNEL_ID in .env")


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f" Logged in as {bot.user} (ID: {bot.user.id})")
    _log_channel_config()

    # Register in-game → Discord callback BEFORE connecting so no messages are missed
    if CHAT_RELAY_CHANNEL:
        manager.on_team_message(_on_rust_chat_message)
        log.info("Chat callback registered ")

    # Try reconnecting to last active server
    active = manager.get_active()
    if active:
        try:
            await manager.connect(active["ip"], active["port"])
            name = active.get("name", active["ip"])
            log.info(f" Reconnected to: {name}")
            await notify(discord.Embed(
                title=" Bot Restarted",
                description=f"Reconnected to **{name}**\n`{active['ip']}:{active['port']}`",
                color=0xCE422B,
            ))
        except Exception as e:
            log.warning(f"  Could not reconnect: {e}")
            await notify(discord.Embed(
                title=" Reconnect Failed",
                description=f"Could not reach last server: `{e}`\nPair a server in-game to reconnect.",
                color=0xFF6B35,
            ))
    else:
        log.info("No saved servers. Pair one in-game (ESC → Rust+ → Pair).")
        await notify(discord.Embed(
            title=" Bot Online",
            description=(
                "No server paired yet.\n"
                "Join a Rust server and press **ESC → Rust+ → Pair Server**."
            ),
            color=0xCE422B,
        ))

    # Start FCM pairing listener
    bot.loop.create_task(manager.listen_for_pairings(on_new_server_paired))
    log.info("👂 FCM listener active — pair any server to connect!")


def _log_channel_config():
    def _ch(cid):
        if not cid:
            return " not set"
        ch = bot.get_channel(cid)
        return f" #{ch.name}" if ch else f"  ID {cid} not found"
    log.info("Channel config:")
    log.info(f"  Commands      → {_ch(COMMAND_CHANNEL)}")
    log.info(f"  Notifications → {_ch(NOTIFICATION_CHANNEL)}")
    log.info(f"  Chat relay    → {_ch(CHAT_RELAY_CHANNEL)}")


async def on_new_server_paired(server: dict):
    """Called when a new server is paired in-game."""
    name = server.get("name", server["ip"])
    log.info(f"🔗 New server paired: {name}")
    cmd_mention = f"<#{COMMAND_CHANNEL}>" if COMMAND_CHANNEL else "`#rust-commands`"
    await notify(discord.Embed(
        title=" New Server Paired!",
        description=(
            f"**{name}**\n"
            f"`{server['ip']}:{server['port']}`\n\n"
            f"Bot is now connected to this server.\n"
            f"Use `/Rust status` in {cmd_mention} to check it out!"
        ),
        color=0xCE422B,
    ))


# ── In-game → Discord ─────────────────────────────────────────────────────────
async def _on_rust_chat_message(event):
    """Callback fired by ChatEvent when a team chat message arrives in-game."""
    if not CHAT_RELAY_CHANNEL:
        log.warning("Rust→Discord relay skipped: CHAT_RELAY_CHANNEL_ID not set in .env")
        return

    msg = event.message

    # If the message is a !rust command, handle it in-game only — never relay to Discord
    if msg.message.lower().startswith("!rust"):
        query = msg.message[5:].strip()  # strip "!rust"
        log.info(f"In-game command from [{msg.name}]: {query!r}")
        await _handle_ingame_command(query, msg.name)
        return  # Do NOT fall through to the Discord relay below

    # get_channel() only works if the channel is in the bot's cache.
    # Fall back to fetch_channel() (API call) if it isn't.
    channel = bot.get_channel(CHAT_RELAY_CHANNEL)
    if not channel:
        try:
            channel = await bot.fetch_channel(CHAT_RELAY_CHANNEL)
        except discord.NotFound:
            log.error(f"Rust→Discord relay failed: channel {CHAT_RELAY_CHANNEL} not found — check CHAT_RELAY_CHANNEL_ID in .env")
            return
        except discord.Forbidden:
            log.error(f"Rust→Discord relay failed: bot lacks permission to access channel {CHAT_RELAY_CHANNEL}")
            return
        except Exception as e:
            log.error(f"Rust→Discord relay failed: could not fetch channel: {e}")
            return

    try:
        # Player name as the embed title, message as the body
        embed = discord.Embed(
            title=f"{msg.name}",
            description=msg.message,
            color=0xCE422B,
        )
        embed.set_footer(text="Rust+ Team Chat")
        await channel.send(embed=embed)
        log.info(f"← Rust: [{msg.name}] {msg.message}")
    except Exception as e:
        log.error(f"Failed to relay Rust→Discord: {e}")


async def _handle_ingame_command(query: str, player_name: str):
    """Run an !rust command issued from in-game and send the result back to team chat."""
    socket = manager.get_socket()
    if not socket:
        return
    try:
        response = await handle_query(query, manager, ingame=True)
        # Strip markdown formatting that doesn't render in Rust chat
        import re
        clean = re.sub(r"[*`_>]", "", response)
        # Send in chunks — Rust team chat has a 128-char limit per message
        lines = [l for l in clean.splitlines() if l.strip()]
        for line in lines[:6]:  # cap at 6 lines to avoid spam
            await socket.send_team_message(line[:128])
    except Exception as e:
        log.error(f"In-game command error: {e}")


# ── Message Handler ───────────────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.lower()

    # ── Chat relay channel: forward Discord → Rust (no echo back to Discord) ──
    if CHAT_RELAY_CHANNEL and message.channel.id == CHAT_RELAY_CHANNEL:
        log.info(f"Relay channel message from {message.author}: {message.content[:60]!r}")
        if not content_lower.startswith(COMMAND_PREFIX):
            await _relay_discord_to_rust(message)
            # Message forwarded to Rust silently — no Discord echo
        return  # Never process commands from the relay channel

    # ── Only handle !rust commands from this point ────────────────────────────
    if not content_lower.startswith(COMMAND_PREFIX):
        await bot.process_commands(message)
        return

    # Silently ignore !rust commands outside the command channel
    if COMMAND_CHANNEL and message.channel.id != COMMAND_CHANNEL:
        return

    query = message.content[len(COMMAND_PREFIX):].strip()
    log.info(f"[{message.author}] !rust {query or '(empty)'}")

    if not query:
        active = manager.get_active()
        server_name = active.get("name", "none") if active else "none"
        await message.reply(
            f"**Rust+ Companion Bot**\n"
            f"> Currently on: **{server_name}**\n\n"
            f"**Commands** (prefix: `!rust`):\n"
            f"`status` · `players` · `time` · `map` · `team` · `events` · `wipe`\n"
            f"`servers` — list all your paired servers\n"
            f"`switch <name or #>` — switch to a different server\n"
            f"`<question>` — ask anything about Rust!\n\n"
            f"Join a Rust server and press **ESC → Rust+ → Pair** to connect."
        )
        return

    async with message.channel.typing():
        try:
            response = await handle_query(query, manager)
        except Exception as e:
            log.error(f"Command error: {e}", exc_info=True)
            response = f" Error: `{e}`"

    for chunk in _split(response):
        await message.reply(chunk)


# ── Discord → In-game ─────────────────────────────────────────────────────────
async def _relay_discord_to_rust(message: discord.Message):
    """Forward a Discord message from the relay channel to Rust team chat."""
    log.info(f"Discord→Rust: attempting relay for {message.author}: {message.content[:60]!r}")
    socket = manager.get_socket()
    if not socket:
        log.warning("Discord→Rust relay skipped: no active socket — is the server paired?")
        return
    try:
        await socket.send_team_message(message.content[:128])
        log.info(f"→ Rust: {message.content[:70]}")
    except Exception as e:
        log.warning(f"Could not relay Discord→Rust: {e}")


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