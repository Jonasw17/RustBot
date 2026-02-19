"""
Polls in-game team chat and forwards messages to a Discord channel.
Also handles the Discord → Rust direction (see bot.py).

Resets cleanly when the active server changes (new pairing).
"""

import asyncio
import logging
import discord
from rust_client import RustClient

log = logging.getLogger("ChatRelay")

POLL_INTERVAL = 5  # seconds between chat polls


class ChatRelay:
    """
    Bi-directional chat bridge between Discord and Rust in-game team chat.

    In-game  ──▶  Discord relay channel
    Discord  ──▶  In-game team chat  (messages from non-bot users in the relay channel)
    """

    def __init__(self, rust: RustClient, channel: discord.TextChannel):
        self.rust = rust
        self.channel = channel
        self._seen_messages: set[str] = set()

    async def start(self):
        """Main loop — polls Rust+ team chat every POLL_INTERVAL seconds."""
        log.info(f"Chat relay started → #{self.channel.name}")

        while True:
            try:
                await self.rust.ensure_connected()
                await self._poll_rust_chat()
            except Exception as e:
                log.warning(f"Chat relay poll error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    # ── In-Game → Discord ─────────────────────────────────────────────────────
    async def _poll_rust_chat(self):
        """Fetch recent team chat and send any new messages to Discord."""
        messages = await self.rust.get_raw_chat()

        for msg in messages:
            # Build a unique key so we don't re-send old messages
            key = f"{msg.steam_id}:{msg.time}:{msg.message}"
            if key in self._seen_messages:
                continue

            self._seen_messages.add(key)

            # Skip very old messages on startup (only relay fresh ones)
            if len(self._seen_messages) <= len(messages):
                continue  # Skip the initial batch — only new ones after boot

            # Format and send to Discord
            embed = discord.Embed(
                description=f" {msg.message}",
                color=0xCE422B,  # Rust orange
            )
            embed.set_author(name=f"{msg.name} (in-game)")
            embed.set_footer(text="Rust+ Team Chat")

            try:
                await self.channel.send(embed=embed)
                log.info(f"Relayed: [{msg.name}] {msg.message}")
            except discord.HTTPException as e:
                log.error(f"Discord send error: {e}")

        # Keep the seen set from growing forever — keep last 500 keys
        if len(self._seen_messages) > 500:
            to_remove = list(self._seen_messages)[:200]
            for k in to_remove:
                self._seen_messages.discard(k)


# ── Discord → In-Game ─────────────────────────────────────────────────────────
async def setup_discord_to_rust(
        rust: RustClient,
        relay_channel_id: int,
        bot: discord.Client,
):
    """
    Listen for Discord messages in the relay channel and forward them
    to the Rust+ team chat.

    Wire this up in bot.py's on_message if you want full bi-directional relay.
    Usage:
        In bot.py on_message, add:
            await discord_to_rust(message, rust, CHAT_RELAY_CHANNEL)
    """
    pass  # See bot.py — handled inline in on_message


async def discord_to_rust(
        message: discord.Message,
        rust: RustClient,
        relay_channel_id: int,
):
    """
    If a non-bot user sends a message in the relay channel,
    forward it as a Rust+ team chat message.
    """
    if message.author.bot:
        return
    if message.channel.id != relay_channel_id:
        return
    if message.content.startswith("!rust"):
        return  # Don't relay bot commands

    text = f"[Discord] {message.author.display_name}: {message.content}"

    try:
        await rust.ensure_connected()
        await rust._socket.send_team_message(text[:128])  # Rust chat has a char limit
        log.info(f"Sent to Rust: {text}")
    except Exception as e:
        log.warning(f"Could not send to Rust team chat: {e}")