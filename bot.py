import asyncio
import io
import os
import logging
import re
import time

import discord
from discord.ext import commands
from dotenv import load_dotenv
from rustplus import RustError

from multi_user_auth import UserManager, cmd_register, cmd_whoami, cmd_users, cmd_unregister
from server_manager_multiuser import MultiUserServerManager
from commands import handle_query
from timers import timer_manager
from storage_monitor import storage_manager
from death_tracker import death_tracker, format_death_embed
from auto_pairing import auto_pairing_manager
from status_embed import build_server_status_embed, _parse_time_to_float, _fmt_time_val

# -- Config -------------------------------
load_dotenv()

DISCORD_TOKEN        = os.getenv("DISCORD_TOKEN")
COMMAND_CHANNEL      = int(os.getenv("COMMAND_CHANNEL_ID", "0"))
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))
CHAT_RELAY_CHANNEL   = int(os.getenv("CHAT_RELAY_CHANNEL_ID", "0"))
COMMAND_PREFIX       = "!"

# -- Logging -------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("RustBot")

# Reduce rustplus library verbosity
rustplus_logger = logging.getLogger("rustplus")
rustplus_logger.setLevel(logging.WARNING)

# -- Discord Client -------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Multi-user managers
user_manager = UserManager()
manager = MultiUserServerManager(user_manager)

# -- Connection Health Tracking -------------------------------
# -- Connection Health Tracking -------------------------------
_connection_health = {
    "last_successful_command": {},  # discord_id -> timestamp
    "reconnect_attempts": {},        # discord_id -> count
    "max_reconnect_attempts": 3
}

# -- Server Status Message Tracking -------------------------------
_status_messages = {}  # discord_id -> {"message_id": int, "server": dict, "last_update": float}


async def update_status_message(discord_id: str):
    """Update or create status message for a user's active server"""
    if not NOTIFICATION_CHANNEL:
        return

    # Get user's active connection
    socket = manager.get_socket_for_user(discord_id)
    server = manager.get_active_server_for_user(discord_id)

    if not socket or not server:
        # Clean up status message if no longer connected
        if discord_id in _status_messages:
            del _status_messages[discord_id]
        return

    user_info = user_manager.get_user(discord_id)
    channel = bot.get_channel(NOTIFICATION_CHANNEL)

    if not channel:
        return

    # Build the embed
    embed = await build_server_status_embed(server, socket, user_info)

    # Check if we have an existing message
    status_data = _status_messages.get(discord_id)

    if status_data and status_data.get("message_id"):
        # Try to update existing message
        try:
            message = await channel.fetch_message(status_data["message_id"])
            await message.edit(embed=embed)
            status_data["last_update"] = time.time()
            log.debug(f"Updated status message for {user_info.get('discord_name', discord_id)}")
            return
        except discord.NotFound:
            log.info(f"Status message deleted, creating new one for {user_info.get('discord_name', discord_id)}")
        except discord.HTTPException as e:
            log.warning(f"Failed to update status message: {e}")

    # Create new message
    try:
        message = await channel.send(embed=embed)
        _status_messages[discord_id] = {
            "message_id": message.id,
            "server": server,
            "last_update": time.time()
        }
        log.info(f"Created status message for {user_info.get('discord_name', discord_id)}")
    except discord.HTTPException as e:
        log.error(f"Failed to create status message: {e}")

async def server_status_loop():
    """Background task that updates all status messages every 45 seconds"""
    await bot.wait_until_ready()
    log.info("Server status loop started")

    while not bot.is_closed():
        try:
            # Update status for all users with active connections
            for discord_id in list(_status_messages.keys()):
                socket = manager.get_socket_for_user(discord_id)
                if socket:
                    await update_status_message(discord_id)
                else:
                    # Clean up if no longer connected
                    del _status_messages[discord_id]

        except Exception as e:
            log.error(f"Status update loop error: {e}")

        await asyncio.sleep(45)


async def death_tracking_loop():
    """Background task that checks for player deaths every 10 seconds"""
    await bot.wait_until_ready()
    log.info("Death tracking loop started")

    while not bot.is_closed():
        try:
            # Check deaths for all users with active connections
            for discord_id, socket in list(manager._active_sockets.items()):
                if not socket:
                    continue
                
                active = manager.get_active_server_for_user(discord_id)
                if not active:
                    continue
                
                server_key = f"{active['ip']}:{active['port']}"
                
                # Get map size for grid calculation
                try:
                    info = await asyncio.wait_for(socket.get_info(), timeout=5.0)
                    if not isinstance(info, RustError):
                        map_size = info.size if hasattr(info, 'size') else 4000
                        await death_tracker.check_team_deaths(
                            socket, discord_id, server_key, map_size
                        )
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    log.warning(f"Death tracking error for user {discord_id}: {e}")

        except Exception as e:
            log.error(f"Death tracking loop error: {e}")

        await asyncio.sleep(10)  # Check every 10 seconds


#  ----- Connection Health Check and Auto-Reconnect ---------------------

async def check_connection_health(discord_id: str) -> bool:
    """Monitor connection health and reconnect if needed"""
    global _connection_health

    socket = manager.get_socket_for_user(discord_id)
    if not socket:
        return False

    try:
        # Test connection with lightweight command
        info = await asyncio.wait_for(socket.get_info(), timeout=10.0)
        if info and not isinstance(info, RustError):
            _connection_health["last_successful_command"][discord_id] = time.time()
            _connection_health["reconnect_attempts"][discord_id] = 0
            return True
    except asyncio.TimeoutError:
        log.warning(f"Connection health check timed out for user {discord_id}")
    except Exception as e:
        log.warning(f"Connection health check failed for user {discord_id}: {e}")

    # Connection appears dead
    last_success = _connection_health["last_successful_command"].get(discord_id, 0)
    time_since_success = time.time() - last_success

    if time_since_success > 300:  # 5 minutes
        attempts = _connection_health["reconnect_attempts"].get(discord_id, 0)
        if attempts < _connection_health["max_reconnect_attempts"]:
            log.info(f"Attempting reconnection for user {discord_id} (attempt {attempts + 1})")
            try:
                await manager.ensure_connected_for_user(discord_id)
                _connection_health["reconnect_attempts"][discord_id] = attempts + 1
                return True
            except Exception as e:
                log.error(f"Reconnection failed for user {discord_id}: {e}")

    return False


async def auto_connect_single_user_server():
    """
    Auto-connect logic:
    - If only 1 registered user with 1 paired server → auto-connect
    - Reconnect to last active server on bot restart
    """
    users = user_manager.list_users()

    if len(users) == 1:
        discord_id = users[0]["discord_id"]
        servers = manager.list_servers_for_user(discord_id)

        if len(servers) == 1:
            # Only 1 user with 1 server - auto-connect
            server = servers[0]
            try:
                log.info(f"Auto-connecting to {server['name']} (1 user, 1 server)")
                await manager.connect_for_user(discord_id, server['ip'], server['port'])
                await asyncio.sleep(3)
                await update_status_message(discord_id)
                return True
            except Exception as e:
                log.error(f"Auto-connect failed: {e}")
                return False

    # Try to reconnect to last active servers for all users
    reconnected = False
    for discord_id in [u["discord_id"] for u in users]:
        # Check if user has an active server preference
        active_server = manager.get_active_server_for_user(discord_id)
        if active_server:
            try:
                log.info(f"Reconnecting to last server for user {discord_id}: {active_server['name']}")
                await manager.connect_for_user(discord_id, active_server['ip'], active_server['port'])
                await asyncio.sleep(3)
                await update_status_message(discord_id)
                reconnected = True
            except Exception as e:
                log.warning(f"Failed to reconnect user {discord_id}: {e}")
        else:
            # No active server, try first available
            servers = manager.list_servers_for_user(discord_id)
            if servers:
                server = servers[0]
                try:
                    log.info(f"Connecting to first available server for user {discord_id}: {server['name']}")
                    await manager.connect_for_user(discord_id, server['ip'], server['port'])
                    await asyncio.sleep(3)
                    await update_status_message(discord_id)
                    reconnected = True
                except Exception as e:
                    log.warning(f"Failed to connect user {discord_id}: {e}")

    return reconnected


async def execute_command_with_retry(discord_id: str, query: str, ctx, max_retries=2):
    """Execute command with automatic retry on connection failure"""

    for attempt in range(max_retries):
        try:
            # Check connection health on retry attempts
            if attempt > 0:
                log.info(f"Retry attempt {attempt + 1} for command: {query[:30]}")
                await check_connection_health(discord_id)
                await asyncio.sleep(2)  # Brief pause between retries

            response = await handle_query(
                query,
                manager,
                user_manager,
                ctx=ctx,
                discord_id=discord_id
            )

            # Update health tracking on success
            _connection_health["last_successful_command"][discord_id] = time.time()
            _connection_health["reconnect_attempts"][discord_id] = 0

            return response

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                log.warning(f"Command timed out (attempt {attempt + 1}), retrying...")
            else:
                return "[!] Command timed out. The server may be slow to respond."

        except Exception as e:
            if attempt < max_retries - 1:
                log.warning(f"Command failed (attempt {attempt + 1}), retrying: {e}")
                # Force reconnection
                try:
                    await manager.ensure_connected_for_user(discord_id)
                except Exception:
                    pass
            else:
                log.error(f"Command failed after {max_retries} attempts: {e}")
                return (
                    f"[!] **Command failed**: Connection issue.\n"
                    f"> Try `!servers` to verify connection status.\n"
                    f"> Error: `{str(e)[:100]}`"
                )

    return "[!] Command execution failed after multiple attempts."


# -- Notification helper -------------------------------
async def notify(embed: discord.Embed, file: discord.File = None):
    """Send an embed (optionally with a file) to the notification channel."""
    if not NOTIFICATION_CHANNEL:
        return
    channel = bot.get_channel(NOTIFICATION_CHANNEL)
    if channel:
        try:
            await channel.send(embed=embed, file=file)
        except Exception as e:
            log.error(f"Failed to send notification: {e}")
    else:
        log.warning(f"Notification channel {NOTIFICATION_CHANNEL} not found")

async def _clear_bot_channels():
    """Clear all messages in bot channels on startup"""
    channels_to_clear = [
        (NOTIFICATION_CHANNEL, "notification"),
        (COMMAND_CHANNEL, "command"),
        (CHAT_RELAY_CHANNEL, "chat relay")
    ]

    for channel_id, channel_name in channels_to_clear:
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if not channel:
            log.warning(f"{channel_name.title()} channel {channel_id} not found")
            continue

        try:
            log.info(f"Clearing {channel_name} channel...")
            deleted = await channel.purge(limit=100)
            log.info(f"Cleared {len(deleted)} message(s) from {channel_name} channel")
        except discord.Forbidden:
            log.error(f"Bot lacks permissions to clear {channel_name} channel")
        except discord.HTTPException as e:
            log.error(f"Failed to clear {channel_name} channel: {e}")

# -- Events -------------------------------
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    _log_channel_config()

    if NOTIFICATION_CHANNEL or COMMAND_CHANNEL or CHAT_RELAY_CHANNEL:
        await _clear_bot_channels()

    # Register chat relay callback
    if CHAT_RELAY_CHANNEL:
        manager.on_team_message(_on_rust_chat_message)
        log.info("Chat relay callback registered")

    # Wire timer expiry → notification channel
    timer_manager.set_notify_callback(_on_timer_expired)
    bot.loop.create_task(timer_manager.run_loop())
    log.info("Timer system started")

    # Wire death tracker notifications
    death_tracker.set_notify_callback(_on_player_death)
    bot.loop.create_task(death_tracking_loop())
    log.info("Death tracking system started")

    # Setup auto-pairing system
    auto_pairing_manager.set_dependencies(user_manager, bot)
    log.info("Auto-pairing system ready")

    # Start FCM listeners for all registered users
    bot.loop.create_task(manager.start_all_fcm_listeners(on_new_server_paired))

    # Show registration status
    user_count = len(user_manager.list_users())

    if user_count == 0:
        log.info("No users registered yet")
        await notify(discord.Embed(
            title="Bot Online",
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
        log.info(f" {user_count} user(s) registered")

        # Auto-connect to servers
        await asyncio.sleep(2)  # Brief delay for stability
        reconnected = await auto_connect_single_user_server()

        if reconnected:
            await notify(discord.Embed(
                title="Bot Online",
                description=f"**{user_count}** user(s) registered\n Auto-connected to servers",
                color=0x00FF00,
            ))
            bot.loop.create_task(server_status_loop())
        else:
            await notify(discord.Embed(
                title="Bot Online",
                description=(
                    f"**{user_count}** user(s) registered\n"
                    f"No active servers - pair one in-game"
                ),
                color=0xFFA500,
            ))

    log.info("Bot ready!")


def _log_channel_config():
    def _ch(cid):
        if not cid:
            return "[X] not set"
        ch = bot.get_channel(cid)
        return f" #{ch.name}" if ch else f" ID {cid} not found"

    log.info("Channel configuration:")
    log.info(f"  Commands      → {_ch(COMMAND_CHANNEL)}")
    log.info(f"  Notifications → {_ch(NOTIFICATION_CHANNEL)}")
    log.info(f"  Chat relay    → {_ch(CHAT_RELAY_CHANNEL)}")


async def on_new_server_paired(discord_id: str, server: dict):
    """Called when a user pairs a new server"""
    user = user_manager.get_user(discord_id)
    if not user:
        return

    name = server.get("name", server["ip"])
    log.info(f"New server paired by {user['discord_name']}: {name}")

    await update_status_message(discord_id)

async def _on_timer_expired(label: str, text: str):
    """Called by TimerManager when a timer fires"""
    embed = discord.Embed(
        title="[Timer] Expired",
        description=f"**{text}**\n_(was set for {label})_",
        color=0xCE422B,
    )
    await notify(embed)


async def _on_player_death(death_record: dict, server_key: str):
    """Called by DeathTracker when a player dies"""
    # Find server name from any user with this server
    server_name = None
    for discord_id in manager._active_servers:
        active = manager._active_servers[discord_id]
        if f"{active['ip']}:{active['port']}" == server_key:
            server_name = active.get('name', server_key)
            break
    
    embed = format_death_embed(death_record, server_name)
    await notify(embed)


@bot.command()
async def testpair(ctx, entity_id: int, entity_type: str = "2"):
    """
    Test the auto-pairing system without FCM

    Usage:
        !testpair 12345678 2       - Test storage container
        !testpair 87654321 1       - Test smart switch

    This simulates receiving an FCM pairing notification
    """
    discord_id = str(ctx.author.id)

    # Check if user is registered
    user = user_manager.get_user(discord_id)
    if not user:
        await ctx.reply("❌ You need to register first! Use `!register` in DM.")
        return

    # Get user's active server
    active_server = manager.get_active_server_for_user(discord_id)
    if not active_server:
        await ctx.reply("❌ You need to connect to a server first! Use `!connect <server>`")
        return

    # Create mock notification data
    notification_data = {
        "type": "entity",
        "entityId": entity_id,
        "entityType": entity_type,
        "entityName": f"Test Device #{entity_id}",
        "ip": active_server["ip"],
        "port": active_server["port"],
        "name": active_server["name"]
    }

    await ctx.reply(
        f"🧪 Testing auto-pairing with:\n"
        f"> Entity ID: `{entity_id}`\n"
        f"> Type: `{entity_type}` (1=switch, 2=storage)\n"
        f"> Server: `{active_server['name']}`\n\n"
        f"Check your DMs!"
    )

    # Trigger auto-pairing
    from auto_pairing import auto_pairing_manager
    await auto_pairing_manager.handle_pairing_notification(discord_id, notification_data)


@bot.command()
async def testdm(ctx):
    """Test if bot can send you DMs"""
    try:
        await ctx.author.send(
            "✅ **DM Test Successful!**\n\n"
            "If you see this message, the bot can send you DMs.\n"
            "Auto-pairing notifications should work."
        )
        await ctx.reply("✅ DM sent! Check your messages.")
    except discord.Forbidden:
        await ctx.reply(
            "❌ **I can't DM you!**\n\n"
            "To receive auto-pairing notifications, you need to:\n"
            "1. Go to **Settings** → **Privacy & Safety**\n"
            "2. Enable **'Allow direct messages from server members'**\n"
            "3. Try again"
        )
    except Exception as e:
        await ctx.reply(f"❌ Error: {e}")


@bot.command()
async def debugpair(ctx):
    """Check auto-pairing system status"""
    discord_id = str(ctx.author.id)

    # Check dependencies
    from auto_pairing import auto_pairing_manager

    bot_ready = auto_pairing_manager._bot is not None
    user_mgr_ready = auto_pairing_manager._user_manager is not None
    has_pending = auto_pairing_manager.has_pending_pairing(discord_id)

    # Check user registration
    user = user_manager.get_user(discord_id)
    is_registered = user is not None

    # Check active server
    active_server = manager.get_active_server_for_user(discord_id)
    is_connected = active_server is not None

    # Check FCM listener
    fcm_running = discord_id in manager._fcm_listeners

    embed = discord.Embed(
        title="🔍 Auto-Pairing Debug Info",
        color=0x00AAFF
    )

    embed.add_field(
        name="System Status",
        value=(
            f"{'✅' if bot_ready else '❌'} Bot object: {bot_ready}\n"
            f"{'✅' if user_mgr_ready else '❌'} User manager: {user_mgr_ready}\n"
            f"{'✅' if is_registered else '❌'} User registered: {is_registered}\n"
            f"{'✅' if is_connected else '❌'} Server connected: {is_connected}\n"
            f"{'✅' if fcm_running else '❌'} FCM listener: {fcm_running}"
        ),
        inline=False
    )

    embed.add_field(
        name="Pairing Status",
        value=(
            f"Pending pairing: {'Yes' if has_pending else 'No'}\n"
        ),
        inline=False
    )

    if not all([bot_ready, user_mgr_ready]):
        embed.add_field(
            name="⚠️ Issue Detected",
            value="Auto-pairing dependencies not set. Bot needs restart.",
            inline=False
        )

    if is_registered and not fcm_running:
        embed.add_field(
            name="⚠️ Issue Detected",
            value="FCM listener not running. Pairing notifications won't be received.",
            inline=False
        )

    if not is_registered:
        embed.add_field(
            name="ℹ️ Next Steps",
            value="Register first with `!register` in DM",
            inline=False
        )
    elif not is_connected:
        embed.add_field(
            name="ℹ️ Next Steps",
            value="Connect to a server with `!connect <name>`",
            inline=False
        )
    else:
        embed.add_field(
            name="ℹ️ Ready to Test",
            value=(
                "1. Test DMs: `!testdm`\n"
                "2. Simulate pairing: `!testpair <entity_id>`\n"
                "3. Or pair in-game and check for notification"
            ),
            inline=False
        )

    await ctx.reply(embed=embed)



# -- In-game → Discord -------------------------------
async def _on_rust_chat_message(event):
    """Callback fired when team chat message arrives in-game"""
    if not CHAT_RELAY_CHANNEL:
        return

    msg = event.message

    # Handle in-game commands
    if msg.message.lower().startswith("!"):
        query = msg.message[1:].strip()
        log.info(f"In-game command from [{msg.name}]: {query!r}")
        await _handle_ingame_command(query, msg.name)
        return

    # Relay to Discord
    channel = bot.get_channel(CHAT_RELAY_CHANNEL)
    if not channel:
        try:
            channel = await bot.fetch_channel(CHAT_RELAY_CHANNEL)
        except Exception as e:
            log.error(f"Could not fetch relay channel: {e}")
            return

    try:
        embed = discord.Embed(
            title=f"[Chat] {msg.name}",
            description=msg.message,
            color=0xCE422B
        )
        embed.set_footer(text="Rust+ Team Chat")
        await channel.send(embed=embed)
        log.info(f"<- Rust: [{msg.name}] {msg.message}")
    except Exception as e:
        log.error(f"Failed to relay Rust->Discord: {e}")


async def _handle_ingame_command(query: str, player_name: str):
    """Run command from in-game (uses first registered user's credentials)"""
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

        # Clean markdown for in-game display
        clean = re.sub(r"[*`_>\[\]()]", "", response)
        lines = [l for l in clean.splitlines() if l.strip()]

        # Send first 6 lines (128 char each)
        for line in lines[:6]:
            await socket.send_team_message(line[:128])
    except Exception as e:
        log.error(f"In-game command error: {e}")


# -- Message Handler -------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    discord_id = str(message.author.id)

    # Handle DMs for auto-pairing responses
    if isinstance(message.channel, discord.DMChannel):
        # Check if user has pending pairing
        if auto_pairing_manager.has_pending_pairing(discord_id):
            # User is responding to pairing prompt
            name = message.content.strip()
            success, response = await auto_pairing_manager.process_user_response(discord_id, name)
            
            if success:
                embed = discord.Embed(
                    title="[OK] Device Added!",
                    description=response,
                    color=0x00FF00
                )
            else:
                embed = discord.Embed(
                    title="[!] Error",
                    description=response,
                    color=0xFF0000
                )
            
            await message.reply(embed=embed)
            return

    # Chat relay: forward Discord → Rust
    if CHAT_RELAY_CHANNEL and message.channel.id == CHAT_RELAY_CHANNEL:
        if not content_lower.startswith(COMMAND_PREFIX):
            await _relay_discord_to_rust(message)
            return

    if not content_lower.startswith(COMMAND_PREFIX):
        await bot.process_commands(message)
        return

    # Ignore commands outside command channel (except DMs)
    if COMMAND_CHANNEL and message.channel.id != COMMAND_CHANNEL:
        if not (CHAT_RELAY_CHANNEL and message.channel.id == CHAT_RELAY_CHANNEL):
            if not isinstance(message.channel, discord.DMChannel):
                return

    query = message.content[len(COMMAND_PREFIX):].strip()
    log.info(f"[{message.author}] ! {query or '(empty)'}")

    # Handle empty command - show help
    if not query:
        user = user_manager.get_user(discord_id)
        if user:
            servers = manager.list_servers_for_user(discord_id)
            active = manager.get_active_server_for_user(discord_id)

            if active:
                server_info = f"[OK] Connected to **{active['name']}**"
            elif servers:
                server_info = f"[!] **{len(servers)}** paired server(s) - not connected"
            else:
                server_info = "[X] No servers paired"

            status_emoji = "[OK]" if active else "[!]" if servers else "[X]"
        else:
            server_info = "[X] Not registered"
            status_emoji = "[X]"

        await message.reply(
            f"**Rust+ Companion Bot - Multi-User Mode**\n"
            f"> {status_emoji} {server_info}\n\n"
            f"**Commands:**\n"
            f"`register` - `whoami` - `servers` - `status` - `players` - `time`\n"
            f"`map` - `team` - `events` - `wipe` - `switch <n>`\n"
            f"`timer add <time> <label>` - `timers`\n"
            f"`sson <id>` - `ssoff <id>`\n\n"
            f"**New user?** DM the bot with `!register`"
        )
        return

    async with message.channel.typing():
        try:
            # Use retry wrapper for better reliability
            response = await execute_command_with_retry(discord_id, query, message)
            if response is None:
                return
        except Exception as e:
            log.error(f"Command error: {e}", exc_info=True)
            response = f"[!] Error: `{e}`"

    # Handle different response types
    if isinstance(response, tuple):
        # Map command - (text, image)
        text, img_bytes = response
        try:
            file = discord.File(io.BytesIO(img_bytes), filename="map.jpg")
            await message.reply(content=text, file=file)
        except Exception as e:
            log.error(f"Could not send map image: {e}")
            await message.reply(text)
    elif isinstance(response, discord.Embed):
        # Status command - embed
        await message.reply(embed=response)
    else:
        # Regular text response
        for chunk in _split(response):
            await message.reply(chunk)


# -- Discord → In-game -------------------------------
async def _relay_discord_to_rust(message: discord.Message):
    """Forward Discord message to in-game team chat"""
    # Try to find an active socket
    for discord_id, socket in manager._active_sockets.items():
        if socket:
            try:
                text = f"[Discord] {message.author.display_name}: {message.content}"
                await socket.send_team_message(text[:128])
                log.info(f"-> Rust: {text[:70]}")
                return
            except Exception as e:
                log.warning(f"Could not relay to Rust: {e}")

    log.warning("Discord->Rust relay skipped: no active sockets")


# -- Helpers -------------------------------
def _split(text: str, limit: int = 1990) -> list[str]:
    """Split long messages into Discord-friendly chunks"""
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


# -- Run -------------------------------
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN not set in .env — see README")

    log.info("Starting Rust+ Companion Bot (Multi-User Architecture)...")
    bot.run(DISCORD_TOKEN, log_handler=None)