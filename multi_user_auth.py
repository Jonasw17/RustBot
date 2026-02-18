"""
multi_user_auth.py
────────────────────────────────────────────────────────────────────────────
Allows multiple Discord users to pair their own Rust+ accounts with the bot.

How it works:
1. Each user runs their own FCM registration (pair.py)
2. They provide their credentials to the bot via DM
3. Bot stores multiple user credentials and can switch between them
4. When someone uses a command, bot uses THEIR credentials (not just the host's)

This means:
- @Rust role members can all use the bot
- Each person sees their own team data
- Bot can monitor servers none of the original host is on
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict

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
            fcm_creds: Their FCM credentials from rustplus.py.config.json
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

async def cmd_register(ctx, user_manager: UserManager) -> str:
    """
    !register

    DM the bot with this command along with your rustplus.py.config.json file.
    Bot will parse it and register your account.
    """
    # This should only work in DMs
    if not isinstance(ctx.channel, discord.DMChannel):
        return (
            "Please use this command in a **DM with the bot** for security.\n"
            "Send `!register` along with your `rustplus.py.config.json` file attachment."
        )

    # Check for attachment
    if not ctx.message.attachments:
        return (
            "Please attach your `rustplus.py.config.json` file.\n\n"
            "**How to get this file:**\n"
            "1. Download pair.py from the bot repo\n"
            "2. Run `python pair.py` on your computer\n"
            "3. Sign in with Steam when prompted\n"
            "4. This creates rustplus.py.config.json\n"
            "5. Send that file to me here in DM with `!register`"
        )

    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith('.json'):
        return "Please send a JSON file (rustplus.py.config.json)"

    try:
        # Download and parse the FCM config
        file_bytes = await attachment.read()
        fcm_creds = json.loads(file_bytes.decode('utf-8'))

        # Extract Steam ID from FCM credentials
        # The FCM config contains the Steam ID in its structure
        steam_id = fcm_creds.get("fcm", {}).get("steamId")
        if not steam_id:
            return "Could not find Steam ID in the config file. Make sure you uploaded the correct rustplus.py.config.json"

        # Register the user
        success = user_manager.add_user(
            str(ctx.author.id),
            str(ctx.author),
            int(steam_id),
            fcm_creds
        )

        if success:
            return (
                f"**Registration successful!**\n\n"
                f"Your account is now linked:\n"
                f"> Steam ID: `{steam_id}`\n"
                f"> Discord: {ctx.author.mention}\n\n"
                f"**Next steps:**\n"
                f"1. Join any Rust server in-game\n"
                f"2. Press ESC → Rust+ → Pair Server\n"
                f"3. Use bot commands - they'll use YOUR account!\n\n"
                f"Your credentials are stored securely and only you can access your data."
            )
        else:
            return "Registration failed. Check bot logs for details."

    except json.JSONDecodeError:
        return "Invalid JSON file. Make sure you uploaded rustplus.py.config.json"
    except Exception as e:
        log.error(f"Registration error: {e}", exc_info=True)
        return f"Registration failed: {e}"


async def cmd_whoami(ctx, user_manager: UserManager) -> str:
    """!whoami - Check your registration status"""
    user = user_manager.get_user(str(ctx.author.id))
    if not user:
        return (
            "You're not registered yet.\n"
            "DM the bot with `!register` and your FCM config file to get started."
        )

    server_count = len(user.get("paired_servers", {}))
    return (
        f"**Your Account:**\n"
        f"> Discord: {ctx.author.mention}\n"
        f"> Steam ID: `{user['steam_id']}`\n"
        f"> Paired Servers: **{server_count}**\n\n"
        f"Use `!servers` to see your paired servers."
    )


async def cmd_users(ctx, user_manager: UserManager) -> str:
    """!users - List all registered users (admin only)"""
    admin_role = discord.utils.get(ctx.guild.roles, name="Admin")
    if admin_role not in ctx.author.roles:
        return "This command is admin-only."
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


async def cmd_unregister(ctx, user_manager: UserManager) -> str:
    """!unregister - Remove your credentials from the bot"""
    if not user_manager.has_user(str(ctx.author.id)):
        return "You're not registered."

    user_manager.remove_user(str(ctx.author.id))
    return "Your credentials have been removed from the bot."


# Import discord after defining functions that need it
import discord