"""
Allows multiple Discord users to pair their own Rust+ accounts with the bot.

FIXES:
- Handles wrapped FCM config format: {"fcm_credentials": {"gcm": ..., "fcm": ...}}
- Users provide Steam ID manually (config doesn't contain it reliably)
- Backward compatible with old config format
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict
import discord

log = logging.getLogger("MultiUserAuth")

USERS_FILE = Path("users.json")


class UserManager:
    """
    Manages multiple users' Rust+ credentials.

    users.json schema:
    {
      "discord_user_id": {
        "discord_name": "Player#1234",
        "steam_id": 76561198...,
        "fcm_credentials": {
          "keys": {...},
          "fcm": {...},
          "gcm": {...}
        },
        "paired_servers": {
          "ip:port": {
            "name": "Server Name",
            "player_token": -123456789
          }
        }
      }
    }
    """

    def __init__(self):
        self._users: Dict = self._load()

    def _load(self) -> dict:
        if USERS_FILE.exists():
            try:
                return json.loads(USERS_FILE.read_text())
            except Exception as e:
                log.warning(f"Could not load users.json: {e}")
        return {}

    def _save(self):
        try:
            USERS_FILE.write_text(json.dumps(self._users, indent=2))
        except Exception as e:
            log.error(f"Could not save users: {e}")

    # ── User Registration ─────────────────────────────────────────────────────
    def add_user(self, discord_id: str, discord_name: str,
                 steam_id: int, fcm_creds: dict) -> bool:
        """
        Register a new user's Rust+ credentials.

        Args:
            discord_id: Discord user ID (str)
            discord_name: Discord username for display
            steam_id: Steam ID from their Rust+ pairing
            fcm_creds: Their FCM credentials from rustplus.config.json
        """
        try:
            self._users[discord_id] = {
                "discord_name": discord_name,
                "steam_id": steam_id,
                "fcm_credentials": fcm_creds,
                "paired_servers": {}
            }
            self._save()
            log.info(f"Registered user: {discord_name} (Steam: {steam_id})")
            return True
        except Exception as e:
            log.error(f"Failed to add user: {e}")
            return False

    def get_user(self, discord_id: str) -> Optional[dict]:
        """Get a user's credentials by Discord ID"""
        return self._users.get(str(discord_id))

    def has_user(self, discord_id: str) -> bool:
        """Check if a user is registered"""
        return str(discord_id) in self._users

    def list_users(self) -> list:
        """Get list of all registered users"""
        return [
            {
                "discord_id": uid,
                "discord_name": data["discord_name"],
                "steam_id": data["steam_id"],
                "server_count": len(data.get("paired_servers", {}))
            }
            for uid, data in self._users.items()
        ]

    # ── Server Pairing per User ───────────────────────────────────────────────
    def add_user_server(self, discord_id: str, ip: str, port: str,
                        name: str, player_token: int):
        """Add a paired server to a user's account"""
        user = self.get_user(discord_id)
        if not user:
            log.warning(f"Cannot add server for unregistered user {discord_id}")
            return False

        key = f"{ip}:{port}"
        user["paired_servers"][key] = {
            "name": name,
            "player_token": player_token,
            "ip": ip,
            "port": port
        }
        self._save()
        log.info(f"Added server {name} for user {user['discord_name']}")
        return True

    def get_user_servers(self, discord_id: str) -> list:
        """Get all servers paired by this user"""
        user = self.get_user(discord_id)
        if not user:
            return []
        return list(user.get("paired_servers", {}).values())

    def remove_user(self, discord_id: str) -> bool:
        """Remove a user's credentials"""
        if str(discord_id) in self._users:
            name = self._users[str(discord_id)]["discord_name"]
            del self._users[str(discord_id)]
            self._save()
            log.info(f"Removed user: {name}")
            return True
        return False


# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_register(message, user_manager: UserManager) -> str:
    """
    !register <steam_id>

    FIXED to handle wrapped FCM config format and manual Steam ID entry.
    """
    if not isinstance(message.channel, discord.DMChannel):
        return (
            "Please use this command in a **DM with the bot** for security.\n"
            "Send `!register <your_steam_id>` along with your `rustplus.config.json` file.\n\n"
            "**Find your Steam ID:**\n"
            "• Go to https://steamid.io\n"
            "• Enter your Steam profile URL\n"
            "• Copy your steamID64 (starts with 765...)"
        )

    # Parse Steam ID from command
    parts = message.content.split()
    if len(parts) < 2:
        return (
            "**Usage:** `!register <steam_id>`\n\n"
            "**Example:** `!register 76561198012345678`\n\n"
            "**Find your Steam ID:**\n"
            "1. Go to https://steamid.io\n"
            "2. Enter your Steam profile URL\n"
            "3. Copy your steamID64 (starts with 765...)\n\n"
            "Then attach your `rustplus.config.json` file with the command."
        )

    try:
        steam_id = int(parts[1])
        # Validate Steam64 ID format
        if steam_id < 76500000000000000 or steam_id > 76600000000000000:
            return (
                "That doesn't look like a valid Steam ID.\n"
                "Steam IDs start with 765... and are 17 digits long.\n\n"
                "Find yours at: https://steamid.io"
            )
    except ValueError:
        return (
            "Invalid Steam ID format. Must be a number like `76561198012345678`\n"
            "Find yours at: https://steamid.io"
        )

    # Check for attachment
    if not message.attachments:
        return (
            "Please attach your `rustplus.config.json` file.\n\n"
            "**How to get this file:**\n"
            "1. Run FCM registration (use pair.bat)\n"
            "2. Sign in with Steam when prompted\n"
            "3. File will be created on your Desktop\n"
            "4. Send that file to me here in DM with `!register <steam_id>`"
        )

    attachment = message.attachments[0]
    if not attachment.filename.endswith('.json'):
        return "Please send a JSON file (rustplus.config.json)"

    try:
        # Download and parse the FCM config
        file_bytes = await attachment.read()
        config = json.loads(file_bytes.decode('utf-8'))

        # Handle BOTH config formats
        if "fcm_credentials" in config:
            # New format: {"fcm_credentials": {"gcm": ..., "fcm": ...}}
            fcm_creds = config["fcm_credentials"]
        elif "gcm" in config and "fcm" in config:
            # Old format: {"gcm": ..., "fcm": ..., ...}
            fcm_creds = config
        else:
            return (
                "Invalid config file structure.\n\n"
                "Expected structure:\n"
                "```json\n"
                "{\n"
                '  "fcm_credentials": {\n'
                '    "gcm": {...},\n'
                '    "fcm": {...}\n'
                "  }\n"
                "}\n"
                "```\n\n"
                "Make sure you uploaded the correct `rustplus.config.json` file."
            )

        # Validate that fcm_creds has the required fields
        if "gcm" not in fcm_creds or "fcm" not in fcm_creds:
            return (
                "Config file is missing required FCM credentials.\n"
                "Make sure you uploaded `rustplus.config.json` from pair.bat"
            )

        # Register the user with provided Steam ID
        success = user_manager.add_user(
            str(message.author.id),
            str(message.author),
            steam_id,
            fcm_creds  # Store just the credentials part
        )

        if success:
            return (
                f"✅ **Registration successful!**\n\n"
                f"Your account is now linked:\n"
                f"> Steam ID: `{steam_id}`\n"
                f"> Discord: {message.author.mention}\n\n"
                f"**Next steps:**\n"
                f"1. Join any Rust server in-game\n"
                f"2. Press ESC → Rust+ → Pair Server\n"
                f"3. Use bot commands - they'll use YOUR account!\n\n"
                f"Your credentials are stored securely and only you can access your data."
            )
        else:
            return "Registration failed. Check bot logs for details."

    except json.JSONDecodeError:
        return "Invalid JSON file. Make sure you uploaded rustplus.config.json"
    except Exception as e:
        log.error(f"Registration error: {e}", exc_info=True)
        return f"Registration failed: {e}"


async def cmd_whoami(message, user_manager: UserManager) -> str:
    """!whoami - Check your registration status"""
    user = user_manager.get_user(str(message.author.id))
    if not user:
        return (
            "You're not registered yet.\n"
            "DM the bot with `!register <steam_id>` and your FCM config file to get started.\n\n"
            "Find your Steam ID at: https://steamid.io"
        )

    server_count = len(user.get("paired_servers", {}))
    return (
        f"**Your Account:**\n"
        f"> Discord: {message.author.mention}\n"
        f"> Steam ID: `{user['steam_id']}`\n"
        f"> Paired Servers: **{server_count}**\n\n"
        f"Use `!servers` to see your paired servers."
    )


async def cmd_users(message, user_manager: UserManager) -> str:
    """!users - List all registered users (admin only)"""
    admin_role = discord.utils.get(message.guild.roles, name="Admin")
    if admin_role not in message.author.roles:
        return "You don't have permission to use this command."

    users = user_manager.list_users()
    if not users:
        return "No users registered yet."

    lines = []
    for u in users:
        lines.append(
            f"> **{u['discord_name']}** - Steam: `{u['steam_id']}` - "
            f"{u['server_count']} server(s)"
        )

    return f"**Registered Users ({len(users)}):**\n" + "\n".join(lines)


async def cmd_unregister(message, user_manager: UserManager) -> str:
    """!unregister - Remove your credentials from the bot"""
    if not user_manager.has_user(str(message.author.id)):
        return "You're not registered."

    user_manager.remove_user(str(message.author.id))
    return "Your credentials have been removed from the bot."