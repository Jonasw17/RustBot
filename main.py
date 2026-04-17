"""
main.py
--------
Entry point for the Rust+ Companion Bot.
Run this file to start the bot: python main.py

Required .env file:
    DISCORD_TOKEN=your_bot_token_here
    COMMAND_CHANNEL_ID=123456789
    NOTIFICATION_CHANNEL_ID=123456789
    CHAT_RELAY_CHANNEL_ID=123456789   (optional)
"""

import asyncio
import logging
import os
import sys

import discord
from dotenv import load_dotenv

from commands import handle_query
from server_manager_multiuser import MultiUserServerManager
from multi_user_auth import UserManager
from timers import timer_manager
from error_logger import setup_error_logging
from death_tracker import death_tracker, format_death_embed
from storage_monitor import storage_manager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
setup_error_logging("errors.log")
log = logging.getLogger("Bot")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

TOKEN               = os.getenv("DISCORD_TOKEN", "")
COMMAND_CHANNEL_ID  = int(os.getenv("COMMAND_CHANNEL_ID", "0"))
NOTIFY_CHANNEL_ID   = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))
CHAT_RELAY_ID       = int(os.getenv("CHAT_RELAY_CHANNEL_ID", "0"))
COMMAND_PREFIX      = "!"

if not TOKEN:
    log.error("DISCORD_TOKEN is not set in .env - cannot start.")
    sys.exit(1)

if not COMMAND_CHANNEL_ID:
    log.warning("COMMAND_CHANNEL_ID is not set - bot will respond in all channels.")

# ---------------------------------------------------------------------------
# Discord client setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

# ---------------------------------------------------------------------------
# Managers (created once, shared everywhere)
# ---------------------------------------------------------------------------
user_manager = UserManager()
manager      = MultiUserServerManager(user_manager)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _channel_allowed(message: discord.Message) -> bool:
    """Return True if the message came from an allowed channel."""
    if COMMAND_CHANNEL_ID == 0:
        return True
    if isinstance(message.channel, discord.DMChannel):
        return True
    return message.channel.id == COMMAND_CHANNEL_ID


async def _send_response(channel, response) -> None:
    """Send a string, embed, or (caption, bytes) tuple to a channel."""
    if response is None:
        return

    if isinstance(response, discord.Embed):
        await channel.send(embed=response)

    elif isinstance(response, tuple) and len(response) == 2:
        caption, img_bytes = response
        if isinstance(img_bytes, bytes):
            file = discord.File(fp=__import__("io").BytesIO(img_bytes),
                                filename="map.jpg")
            await channel.send(content=caption, file=file)
        else:
            await channel.send(content=caption)

    elif isinstance(response, str):
        # Discord has a 2000 character limit per message
        if len(response) <= 2000:
            await channel.send(response)
        else:
            # Split on newlines to avoid cutting mid-word
            chunks = []
            current = ""
            for line in response.splitlines(keepends=True):
                if len(current) + len(line) > 1990:
                    chunks.append(current)
                    current = line
                else:
                    current += line
            if current:
                chunks.append(current)
            for chunk in chunks:
                await channel.send(chunk)

    else:
        await channel.send(str(response))


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    log.info("discord.py version: %s", discord.__version__)

    # Start background tasks
    bot.loop.create_task(timer_manager.run_loop())
    bot.loop.create_task(_status_update_loop())

    # Start FCM listeners for all registered users
    await manager.start_all_fcm_listeners(_on_server_paired)

    # Wire timer notifications to the notification channel
    async def _timer_notify(label: str, text: str):
        ch = bot.get_channel(NOTIFY_CHANNEL_ID)
        if ch:
            await ch.send(f"[Timer] **{text}** ({label})")

    timer_manager.set_notify_callback(_timer_notify)

    # Wire death tracker notifications
    async def _death_notify(death_record: dict, server_key: str):
        ch = bot.get_channel(NOTIFY_CHANNEL_ID)
        if ch:
            embed = format_death_embed(death_record, server_name=server_key)
            await ch.send(embed=embed)

    death_tracker.set_notify_callback(_death_notify)

    log.info("Bot is ready.")


@bot.event
async def on_message(message: discord.Message):
    # Ignore the bot's own messages
    if message.author.bot:
        return

    # Only process messages that start with the prefix
    if not message.content.startswith(COMMAND_PREFIX):
        return

    # Channel filter
    if not _channel_allowed(message):
        return

    query = message.content[len(COMMAND_PREFIX):].strip()
    if not query:
        return

    discord_id = str(message.author.id)

    # Show typing indicator while processing
    async with message.channel.typing():
        try:
            response = await handle_query(
                query=query,
                manager=manager,
                user_manager=user_manager,
                ctx=message,
                discord_id=discord_id,
            )
            await _send_response(message.channel, response)
        except Exception as e:
            log.error("Unhandled error in handle_query: %s", e, exc_info=True)
            await message.channel.send(
                f"An error occurred: `{type(e).__name__}: {e}`"
            )


# ---------------------------------------------------------------------------
# FCM pairing callback
# ---------------------------------------------------------------------------

async def _on_server_paired(discord_id: str, server: dict):
    """Called when a user pairs a new server in-game via ESC -> Rust+."""
    log.info("Server paired for user %s: %s", discord_id, server.get("name"))

    ch = bot.get_channel(NOTIFY_CHANNEL_ID)
    if not ch:
        return

    user = user_manager.get_user(discord_id)
    discord_name = user["discord_name"] if user else discord_id

    await ch.send(
        f"[Paired] **{discord_name}** connected to "
        f"**{server.get('name', server['ip'])}** "
        f"(`{server['ip']}:{server['port']}`)"
    )


# ---------------------------------------------------------------------------
# Background: periodic status update
# ---------------------------------------------------------------------------

async def _status_update_loop():
    """Post a server status embed to the notification channel every 45 seconds."""
    from status_embed import build_server_status_embed

    await bot.wait_until_ready()
    await asyncio.sleep(10)  # Give FCM listeners time to start

    while not bot.is_closed():
        try:
            ch = bot.get_channel(NOTIFY_CHANNEL_ID)
            if ch:
                # Update status for each connected user
                seen_servers = set()
                for discord_id, server in list(manager._active_servers.items()):
                    key = f"{server['ip']}:{server['port']}"
                    if key in seen_servers:
                        continue
                    seen_servers.add(key)

                    socket = manager.get_socket_for_user(discord_id)
                    if socket:
                        try:
                            embed = await build_server_status_embed(server, socket)
                            # Edit existing status message or post new one
                            # (simple approach: just post; for pinned status
                            # you would track the message ID)
                        except Exception as e:
                            log.debug("Status update skipped: %s", e)
        except Exception as e:
            log.error("Status update loop error: %s", e)

        await asyncio.sleep(45)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Starting Rust+ Companion Bot...")
    try:
        bot.run(TOKEN, log_handler=None)
    except discord.LoginFailure:
        log.error("Invalid Discord token. Check your .env file.")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Shutdown requested.")
