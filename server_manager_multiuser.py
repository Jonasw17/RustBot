"""
ENHANCED ServerManager that supports multiple users.

Key Changes:
- Each command execution uses the Discord user's credentials
- Users can pair servers independently
- Bot can connect to any server any registered user has paired
- FCM listener uses multi-strategy parsing for maximum compatibility

This replaces the original server_manager.py
"""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional, Dict

from rustplus import RustSocket, ServerDetails, FCMListener, ChatEvent, ChatEventPayload

log = logging.getLogger("ServerManager")

ACTIVE_CONNECTIONS_FILE = Path("active_connections.json")


def _extract_pairing_data(obj, notification, data_message) -> Optional[dict]:
    """
    Try every known FCM notification format to find server pairing data.

    The Rust+ FCM notification can arrive in different formats depending on
    the rustplus library version and FCM delivery path. We try four strategies:

    Strategy 1 (most common): data_message is a dict with "channelId" == "pairing"
                              and a "body" key containing a JSON string of server info.

    Strategy 2 (flat format): data_message has the server fields directly at
                              the top level (ip, port, playerToken, playerId, type).

    Strategy 3: Same as strategies 1 and 2 but using the notification dict.

    Strategy 4: Fields are nested inside obj["data"].

    Returns a dict with server pairing fields, or None if nothing found.
    """

    def _try_body_json(d: dict) -> Optional[dict]:
        """Parse body JSON string from a data dict."""
        body_raw = d.get("body") or d.get("Body") or ""
        if isinstance(body_raw, dict):
            return body_raw
        if isinstance(body_raw, str) and body_raw.strip().startswith("{"):
            try:
                return json.loads(body_raw)
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    def _is_server_pairing(d: dict) -> bool:
        """Check if a dict looks like a server pairing payload."""
        return (
                isinstance(d, dict)
                and d.get("type") == "server"
                and bool(d.get("ip"))
        )

    def _is_pairing_channel(d: dict) -> bool:
        return isinstance(d, dict) and d.get("channelId") == "pairing"

    # --- Strategy 1: data_message with channelId + body JSON ---
    if isinstance(data_message, dict):
        if _is_pairing_channel(data_message):
            body = _try_body_json(data_message)
            if body and _is_server_pairing(body):
                return body
            # Maybe the body itself IS the server pairing dict
            if _is_server_pairing(data_message):
                return data_message

    # --- Strategy 2: data_message has flat server fields directly ---
    if isinstance(data_message, dict) and _is_server_pairing(data_message):
        return data_message

    # --- Strategy 3: notification dict ---
    if isinstance(notification, dict):
        if _is_pairing_channel(notification):
            body = _try_body_json(notification)
            if body and _is_server_pairing(body):
                return body
            if _is_server_pairing(notification):
                return notification
        if _is_server_pairing(notification):
            return notification

    # --- Strategy 4: obj["data"] or obj directly ---
    if isinstance(obj, dict):
        nested = obj.get("data", obj)
        if isinstance(nested, dict):
            if _is_pairing_channel(nested):
                body = _try_body_json(nested)
                if body and _is_server_pairing(body):
                    return body
            if _is_server_pairing(nested):
                return nested

    return None


class MultiUserServerManager:
    """
    Manages Rust+ connections for multiple Discord users.

    Each user has their own:
    - Steam ID
    - FCM credentials
    - Paired servers with unique player tokens

    When a user runs a command, the bot uses THEIR credentials.
    """

    def __init__(self, user_manager):
        self.user_manager = user_manager
        self._active_sockets: Dict[str, RustSocket] = {}
        self._active_servers: Dict[str, dict] = {}
        self._chat_callbacks: list = []
        self._registered_chat_keys: set = set()
        self._fcm_listeners: Dict[str, threading.Thread] = {}

    def on_team_message(self, callback: Callable):
        """Register callback for team chat messages"""
        self._chat_callbacks.append(callback)

    # -------------------------------------------------------------------------
    # Per-User Connection Management
    # -------------------------------------------------------------------------

    async def connect_for_user(self, discord_id: str, ip: str, port: str) -> RustSocket:
        """
        Connect to a server using a specific user's credentials.
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError(
                "User {} not registered. Use !register first.".format(discord_id)
            )

        key = "{}:{}".format(ip, port)
        user_servers = user.get("paired_servers", {})
        server = user_servers.get(key)

        if not server:
            raise ValueError(
                "Server {}:{} not paired for this user.\n"
                "Join the server in-game and press ESC -> Rust+ -> Pair Server".format(ip, port)
            )

        # Disconnect any existing socket for this user
        if discord_id in self._active_sockets:
            try:
                await self._active_sockets[discord_id].disconnect()
            except Exception:
                pass

        log.info(
            "Connecting {} to {}".format(user["discord_name"], server.get("name", key))
        )

        server_details = ServerDetails(
            ip,
            port,
            int(user["steam_id"]),
            int(server["player_token"])
        )

        socket = RustSocket(server_details)
        await socket.connect()

        # Register chat listener once per unique server
        chat_key = (ip, str(port), int(user["steam_id"]))
        if chat_key not in self._registered_chat_keys and self._chat_callbacks:
            self._registered_chat_keys.add(chat_key)
            _callbacks = list(self._chat_callbacks)

            @ChatEvent(server_details)
            async def _chat_handler(event: ChatEventPayload):
                for cb in _callbacks:
                    try:
                        await cb(event)
                    except Exception as exc:
                        log.error("Chat callback error: {}".format(exc))

            log.info("ChatEvent listener registered")

        self._active_sockets[discord_id] = socket
        self._active_servers[discord_id] = server

        log.info("Connected ({})".format(user["discord_name"]))
        return socket

    async def ensure_connected_for_user(self, discord_id: str):
        """Ensure user has an active connection to their last server"""
        if discord_id in self._active_sockets:
            return

        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        servers = user.get("paired_servers", {})
        if not servers:
            raise ValueError(
                "No servers paired. Join a Rust server and use "
                "ESC -> Rust+ -> Pair Server"
            )

        first_server = list(servers.values())[0]
        await self.connect_for_user(
            discord_id,
            first_server["ip"],
            first_server["port"]
        )

    def get_socket_for_user(self, discord_id: str) -> Optional[RustSocket]:
        return self._active_sockets.get(discord_id)

    def get_active_server_for_user(self, discord_id: str) -> Optional[dict]:
        return self._active_servers.get(discord_id)

    def disconnect_user(self, discord_id: str):
        """Remove all active connection state for a user."""
        if discord_id in self._active_sockets:
            try:
                asyncio.get_event_loop().create_task(
                    self._active_sockets[discord_id].disconnect()
                )
            except Exception:
                pass
            del self._active_sockets[discord_id]
            log.info("Removed active socket for user {}".format(discord_id))

        if discord_id in self._active_servers:
            del self._active_servers[discord_id]
            log.info("Cleared active server for user {}".format(discord_id))

    # -------------------------------------------------------------------------
    # FCM Auto-Pairing (Per User)
    # -------------------------------------------------------------------------

    async def start_fcm_listener_for_user(self, discord_id: str, callback: Callable):
        """
        Start FCM listener for a specific user.
        When they pair servers in-game, automatically adds to their account.
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            log.warning(
                "Cannot start FCM listener for unregistered user {}".format(discord_id)
            )
            return

        # Get FCM credentials from user data
        # The credentials are stored under 'fcm_credentials' key with 'gcm' and 'fcm' nested inside
        fcm_creds_nested = user.get("fcm_credentials")
        if not fcm_creds_nested:
            log.warning("User {} has no FCM credentials".format(discord_id))
            return

        # Validate that the credentials have the required structure
        if "gcm" not in fcm_creds_nested or "fcm" not in fcm_creds_nested:
            log.error(
                "User {} has invalid FCM credentials structure - "
                "missing 'gcm' or 'fcm' keys".format(discord_id)
            )
            return

        # FCMListener from rustplus library expects the FULL config structure
        # with 'fcm_credentials' as a top-level key (not just gcm/fcm directly)
        # Reconstruct the full structure as it would appear in rustplus.config.json
        fcm_creds = {
            "fcm_credentials": fcm_creds_nested
        }

        # Don't start duplicate listeners
        if discord_id in self._fcm_listeners:
            existing = self._fcm_listeners[discord_id]
            if existing.is_alive():
                log.debug(
                    "FCM listener already running for {}".format(user["discord_name"])
                )
                return

        loop = asyncio.get_event_loop()
        user_manager = self.user_manager
        manager_ref = self

        class UserPairingListener(FCMListener):
            def on_notification(self_inner, obj, notification, data_message):
                try:
                    # Log raw data at DEBUG level - enable debug logging to
                    # see exactly what the FCM notification contains
                    log.debug(
                        "[FCM] Notification for {} | obj={} | notification={} | "
                        "data_message={}".format(
                            user["discord_name"], obj, notification, data_message
                        )
                    )

                    # Try all strategies to extract pairing data
                    pairing_data = _extract_pairing_data(obj, notification, data_message)

                    if pairing_data is None:
                        # Not a pairing notification - silently ignore
                        log.debug(
                            "[FCM] No pairing data found for {} - "
                            "skipping notification".format(user["discord_name"])
                        )
                        return

                    # At this point pairing_data has type=="server" and ip set

                    ip = str(pairing_data.get("ip", "")).strip()
                    port = str(pairing_data.get("port", "28017")).strip()
                    name = str(pairing_data.get("name", ip)).strip() or ip

                    # playerToken is the per-server auth token
                    player_token_raw = (
                            pairing_data.get("playerToken")
                            or pairing_data.get("player_token")
                            or pairing_data.get("playerId")
                            or pairing_data.get("player_id")
                            or 0
                    )

                    try:
                        player_token = int(player_token_raw)
                    except (ValueError, TypeError):
                        log.warning(
                            "[FCM] Could not parse player_token "
                            "(got {!r}) for {}".format(
                                player_token_raw, user["discord_name"]
                            )
                        )
                        return

                    if not ip:
                        log.warning(
                            "[FCM] Missing IP in pairing data "
                            "for {}: {}".format(user["discord_name"], pairing_data)
                        )
                        return

                    if not player_token:
                        log.warning(
                            "[FCM] Missing player_token in pairing data "
                            "for {}: {}".format(user["discord_name"], pairing_data)
                        )
                        return

                    log.info(
                        "[Pairing] Server paired by {}: {} ({}:{}) "
                        "token={}".format(
                            user["discord_name"], name, ip, port, player_token
                        )
                    )

                    # Save to user account
                    success = user_manager.add_user_server(
                        discord_id, ip, port, name, player_token
                    )

                    if not success:
                        log.error(
                            "[FCM] Failed to save server {} for "
                            "{}".format(name, user["discord_name"])
                        )
                        return

                    async def _connect_and_notify():
                        try:
                            # Small delay to ensure data is persisted
                            await asyncio.sleep(1)
                            await manager_ref.connect_for_user(discord_id, ip, port)
                            await callback(discord_id, {
                                "ip": ip,
                                "port": port,
                                "name": name,
                                "player_token": player_token
                            })
                            log.info(
                                "[Pairing] Auto-connected {} to "
                                "{}".format(user["discord_name"], name)
                            )
                        except Exception as e:
                            log.error(
                                "[Pairing] Post-pairing connection failed "
                                "for {}: {}".format(name, e),
                                exc_info=True
                            )

                    asyncio.run_coroutine_threadsafe(_connect_and_notify(), loop)

                except Exception as e:
                    log.error(
                        "[FCM] Unhandled error in listener for "
                        "{}: {}".format(user.get("discord_name", discord_id), e),
                        exc_info=True
                    )

        def _run_fcm():
            retries = 0
            max_retries = 5
            while retries < max_retries:
                try:
                    log.info(
                        "[FCM] Starting listener for {} "
                        "(attempt {})".format(user["discord_name"], retries + 1)
                    )
                    log.debug(
                        "[FCM] Credentials keys for {}: {}".format(
                            user["discord_name"], list(fcm_creds.keys())
                        )
                    )
                    UserPairingListener(fcm_creds).start()
                    # .start() blocks until listener stops
                    log.warning(
                        "[FCM] Listener stopped for {} - "
                        "will not restart".format(user["discord_name"])
                    )
                    break
                except KeyError as e:
                    retries += 1
                    log.warning(
                        "[FCM] Listener startup key error for {} "
                        "(attempt {}): {} - Available keys: {}".format(
                            user["discord_name"], retries, e, list(fcm_creds.keys())
                        )
                    )
                    import time
                    time.sleep(2)
                except Exception as e:
                    retries += 1
                    log.error(
                        "[FCM] Listener crashed for {} "
                        "(attempt {}): {}".format(
                            user["discord_name"], retries, e
                        ),
                        exc_info=True
                    )
                    import time
                    time.sleep(2)

            if retries >= max_retries:
                log.error(
                    "[FCM] Listener failed after {} attempts for {} - "
                    "pairing notifications will not work".format(
                        max_retries, user["discord_name"]
                    )
                )

        thread = threading.Thread(
            target=_run_fcm,
            daemon=True,
            name="FCM-{}".format(user["discord_name"])
        )
        thread.start()
        self._fcm_listeners[discord_id] = thread
        log.info("FCM listener started for {}".format(user["discord_name"]))

    async def start_all_fcm_listeners(self, callback: Callable):
        """Start FCM listeners for all registered users"""
        users = list(self.user_manager._users.keys())
        log.info("Starting FCM listeners for {} user(s)".format(len(users)))
        for discord_id in users:
            await self.start_fcm_listener_for_user(discord_id, callback)

    # -------------------------------------------------------------------------
    # Server Switching
    # -------------------------------------------------------------------------

    async def switch_server_for_user(self, discord_id: str, identifier: str) -> dict:
        """
        Switch a user's active server by name or index.
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        servers = list(user.get("paired_servers", {}).values())
        if not servers:
            raise ValueError("No servers paired")

        # Try numeric index (1-based)
        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(servers):
                server = servers[idx]
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        # Try name match (case-insensitive substring)
        identifier_lower = identifier.lower()
        for server in servers:
            if identifier_lower in server.get("name", "").lower():
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        return None

    def list_servers_for_user(self, discord_id: str) -> list:
        """Get all servers paired by a user"""
        return self.user_manager.get_user_servers(discord_id)