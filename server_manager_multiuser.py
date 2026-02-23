"""
ENHANCED ServerManager that supports multiple users.

Key Changes:
- Each command execution uses the Discord user's credentials
- Users can pair servers independently
- Bot can connect to any server any registered user has paired

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
        self._active_sockets: Dict[str, RustSocket] = {}  # discord_id -> socket
        self._active_servers: Dict[str, dict] = {}  # discord_id -> server_info
        self._chat_callbacks: list[Callable] = []
        self._registered_chat_keys: set = set()
        self._fcm_listeners: Dict[str, threading.Thread] = {}  # discord_id -> thread

    def on_team_message(self, callback: Callable):
        """Register callback for team chat messages"""
        self._chat_callbacks.append(callback)

    # -- Per-User Connection Management ----------------------------------------
    async def connect_for_user(self, discord_id: str, ip: str, port: str) -> RustSocket:
        """
        Connect to a server using a specific user's credentials.

        Args:
            discord_id: Discord user ID
            ip: Server IP
            port: Server port

        Returns:
            Active RustSocket for this user
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError(f"User {discord_id} not registered. Use !register first.")

        # Find this server in user's paired servers
        key = f"{ip}:{port}"
        user_servers = user.get("paired_servers", {})
        server = user_servers.get(key)

        if not server:
            raise ValueError(
                f"Server {ip}:{port} not paired for this user.\n"
                f"Join the server in-game and press ESC -> Rust+ -> Pair Server"
            )

        # Disconnect any existing socket for this user
        if discord_id in self._active_sockets:
            try:
                await self._active_sockets[discord_id].disconnect()
            except Exception:
                pass

        log.info(f"Connecting {user['discord_name']} to {server.get('name', key)}")

        # Create connection using user's credentials
        server_details = ServerDetails(
            ip,
            port,
            int(user["steam_id"]),
            int(server["player_token"])
        )

        socket = RustSocket(server_details)
        await socket.connect()

        # Register chat listener
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
                        log.error(f"Chat callback error: {exc}")

            log.info("ChatEvent listener registered")

        # Store active connection
        self._active_sockets[discord_id] = socket
        self._active_servers[discord_id] = server

        log.info(f"Connected ({user['discord_name']})")
        return socket

    async def ensure_connected_for_user(self, discord_id: str):
        """Ensure user has an active connection to their last server"""
        if discord_id in self._active_sockets:
            return  # Already connected

        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        # Connect to first available server
        servers = user.get("paired_servers", {})
        if not servers:
            raise ValueError(
                "No servers paired. Join a Rust server and use ESC -> Rust+ -> Pair Server"
            )

        first_server = list(servers.values())[0]
        await self.connect_for_user(
            discord_id,
            first_server["ip"],
            first_server["port"]
        )

    def get_socket_for_user(self, discord_id: str) -> Optional[RustSocket]:
        """Get active socket for a user"""
        return self._active_sockets.get(discord_id)

    def get_active_server_for_user(self, discord_id: str) -> Optional[dict]:
        """Get the server a user is currently connected to"""
        return self._active_servers.get(discord_id)

    # -- Auto-Pairing via FCM (Per User) ---------------------------------------
    async def start_fcm_listener_for_user(self, discord_id: str, callback: Callable):
        """
        Start FCM listener for a specific user.
        When they pair servers OR smart devices in-game, automatically processes them.
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            log.warning(f"Cannot start FCM listener for unregistered user {discord_id}")
            return

        fcm_creds = user.get("fcm_credentials")
        if not fcm_creds:
            log.warning(f"User {discord_id} has no FCM credentials")
            return

        # Don't start duplicate listeners
        if discord_id in self._fcm_listeners:
            return

        loop = asyncio.get_event_loop()
        user_manager = self.user_manager

        class UserPairingListener(FCMListener):
            def on_notification(self_inner, obj, notification, data_message):
                try:
                    data = data_message or {}

                    if data.get("channelId") != "pairing":
                        return

                    body_str = data.get("body", "{}")
                    try:
                        body = json.loads(body_str)
                    except json.JSONDecodeError:
                        return

                    pairing_type = body.get("type", "")

                    # Handle SERVER pairing
                    if pairing_type == "server":
                        ip = body.get("ip", "")
                        port = body.get("port", "28017")
                        name = body.get("name", ip)
                        player_token = int(body.get("playerToken", 0))

                        if not ip or not player_token:
                            return

                        log.info(f"[Pairing] Server paired by {user['discord_name']}: {name}")

                        # Add server to user's account
                        user_manager.add_user_server(
                            discord_id,
                            ip,
                            port,
                            name,
                            player_token
                        )

                        # Auto-connect and notify
                        async def _connect_and_notify():
                            try:
                                socket = await self.connect_for_user(discord_id, ip, port)
                                await callback(discord_id, {
                                    "type": "server",
                                    "ip": ip,
                                    "port": port,
                                    "name": name,
                                    "player_token": player_token
                                })
                            except Exception as e:
                                log.error(f"Post-pairing connection failed: {e}")

                        asyncio.run_coroutine_threadsafe(_connect_and_notify(), loop)

                    # Handle SMART DEVICE pairing
                    elif pairing_type == "entity":
                        entity_id = body.get("entityId")
                        entity_type = body.get("entityType")
                        entity_name = body.get("entityName", f"Device {entity_id}")

                        if not entity_id:
                            return

                        log.info(f"[Pairing] Smart device paired by {user['discord_name']}: {entity_name} (ID: {entity_id}, Type: {entity_type})")

                        # Notify about smart device pairing
                        async def _notify_device():
                            try:
                                await callback(discord_id, {
                                    "type": "entity",
                                    "entity_id": entity_id,
                                    "entity_type": entity_type,
                                    "entity_name": entity_name
                                })
                            except Exception as e:
                                log.error(f"Smart device notification failed: {e}")

                        asyncio.run_coroutine_threadsafe(_notify_device(), loop)

                except Exception as e:
                    log.error(f"FCM listener error: {e}", exc_info=True)

        def _run_fcm():
            try:
                UserPairingListener(fcm_creds).start()
            except Exception as e:
                log.error(f"FCM listener crashed for {user['discord_name']}: {e}")

        thread = threading.Thread(
            target=_run_fcm,
            daemon=True,
            name=f"FCM-{user['discord_name']}"
        )
        thread.start()
        self._fcm_listeners[discord_id] = thread
        log.info(f"FCM listener started for {user['discord_name']} ")

    async def start_all_fcm_listeners(self, callback: Callable):
        """Start FCM listeners for all registered users"""
        for discord_id in self.user_manager._users.keys():
            await self.start_fcm_listener_for_user(discord_id, callback)

    # -- Server Switching ------------------------------------------------------
    async def switch_server_for_user(self, discord_id: str, identifier: str) -> dict:
        """
        Switch a user's active server by name or index.

        Args:
            discord_id: Discord user ID
            identifier: Server name substring or 1-based index

        Returns:
            Server dict if found
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        servers = list(user.get("paired_servers", {}).values())
        if not servers:
            raise ValueError("No servers paired")

        # Try numeric index
        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(servers):
                server = servers[idx]
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        # Try name match
        identifier_lower = identifier.lower()
        for server in servers:
            if identifier_lower in server.get("name", "").lower():
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        return None

    def list_servers_for_user(self, discord_id: str) -> list:
        """Get all servers paired by a user"""
        return self.user_manager.get_user_servers(discord_id)