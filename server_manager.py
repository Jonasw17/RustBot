"""
server_manager.py
────────────────────────────────────────────────────────────────────────────
The heart of the multi-server companion system.

Responsibilities:
  - Persist all paired servers to servers.json
  - Hold the active RustSocket connection
  - Listen for new in-game pairing notifications via FCMListener
  - Switch active server on demand

Your Steam ID stays the same across all servers.
Your playerToken is UNIQUE per server — that's why we need FCM pairing.
"""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from rustplus import RustSocket, ServerDetails, FCMListener, ChatEvent, ChatEventPayload

log = logging.getLogger("ServerManager")

SERVERS_FILE = Path("servers.json")
FCM_CONFIG   = Path("rustplus.py.config.json")  # Created by `python pair.py`


def _load() -> dict:
    if SERVERS_FILE.exists():
        try:
            return json.loads(SERVERS_FILE.read_text())
        except Exception as e:
            log.warning(f"Could not load servers.json: {e}")
    return {"active": None, "servers": {}}


class ServerManager:
    """
    Manages multiple paired Rust servers and the active WebSocket connection.

    servers.json schema:
    {
      "active": "ip:port",
      "servers": {
        "ip:port": {
          "ip": "...",
          "port": "28017",
          "name": "...",
          "steam_id": 76561198...,
          "player_token": -123456789
        }
      }
    }
    """

    def __init__(self):
        self._data: dict = _load()
        self._socket: Optional[RustSocket] = None
        self._on_paired_callbacks: list[Callable] = []
        self._chat_callbacks: list[Callable] = []
        self._registered_chat_keys: set = set()

    def on_team_message(self, callback: Callable):
        """Register an async callback for in-game team chat messages.
        Callback receives a ChatEventPayload with .message.name and .message.message."""
        self._chat_callbacks.append(callback)


    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        SERVERS_FILE.write_text(json.dumps(self._data, indent=2))

    # ── Server Registry ───────────────────────────────────────────────────────
    def add_server(self, ip: str, port: str, name: str,
                   steam_id: int, player_token: int) -> dict:
        """Register or update a server from a pairing notification."""
        key = f"{ip}:{port}"
        server = {
            "ip": ip,
            "port": str(port),
            "name": name,
            "steam_id": steam_id,
            "player_token": player_token,
        }
        self._data["servers"][key] = server
        self._data["active"] = key
        self._save()
        log.info(f"Saved server: {name} ({key})")
        return server

    def get_active(self) -> Optional[dict]:
        """Return the currently active server dict, or None."""
        key = self._data.get("active")
        if key:
            return self._data["servers"].get(key)
        return None

    def list_servers(self) -> list[dict]:
        return list(self._data["servers"].values())

    def switch_to(self, identifier: str) -> Optional[dict]:
        """
        Switch active server by name substring or 1-based index string.
        Returns the server dict if found, None otherwise.
        """
        servers = self.list_servers()

        # Try index first ("1", "2", ...)
        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(servers):
                s = servers[idx]
                self._data["active"] = f"{s['ip']}:{s['port']}"
                self._save()
                return s

        # Try name substring match
        identifier_lower = identifier.lower()
        for s in servers:
            if identifier_lower in s.get("name", "").lower():
                self._data["active"] = f"{s['ip']}:{s['port']}"
                self._save()
                return s

        return None

    # ── Connection ────────────────────────────────────────────────────────────
    async def connect(self, ip: str, port: str) -> RustSocket:
        """Connect (or reconnect) to the given server IP:port."""
        key = f"{ip}:{port}"
        server = self._data["servers"].get(key)
        if not server:
            raise ValueError(f"Server {key} not found in servers.json — pair it in-game first.")

        # Disconnect existing socket cleanly
        if self._socket:
            try:
                await self._socket.disconnect()
            except Exception:
                pass
            self._socket = None

        log.info(f"Connecting to {server.get('name', key)} ...")

        # Create ServerDetails object (required in rustplus 6.x)
        server_details = ServerDetails(
            ip,
            port,
            int(server["steam_id"]),
            int(server["player_token"]),
        )

        self._socket = RustSocket(server_details)
        await self._socket.connect()

        # Register ChatEvent listener once per unique server.
        # ChatEvent is keyed by ServerDetails (ip/port/steamid) and survives reconnects.
        chat_key = (ip, str(port), int(server["steam_id"]))
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

            log.info("ChatEvent listener registered ✅")

        self._data["active"] = key
        self._save()
        log.info(f"Connected")
        return self._socket

    async def connect_active(self):
        """Connect to whichever server is currently marked active."""
        active = self.get_active()
        if not active:
            raise RuntimeError("No active server. Pair one in-game first.")
        return await self.connect(active["ip"], active["port"])

    async def ensure_connected(self):
        """Make sure we have a live socket; reconnect if needed."""
        if self._socket is None:
            await self.connect_active()

    def get_socket(self) -> Optional[RustSocket]:
        return self._socket

    # ── FCM Pairing Listener ─────────────────────────────────────────────────
    async def listen_for_pairings(self, callback: Callable):
        """
        Starts the FCMListener in a background thread.
        When you press ESC → Rust+ → Pair Server in-game, this fires `callback`
        with the new server's credentials, then auto-connects.

        Requires rustplus.py.config.json (generated by `python pair.py`).
        """
        if not FCM_CONFIG.exists():
            log.warning(
                "rustplus.py.config.json not found — run `python pair.py` first "
                "to enable automatic server pairing."
            )
            return

        try:
            fcm_details = json.loads(FCM_CONFIG.read_text())
        except Exception as e:
            log.error(f"Could not read FCM config: {e}")
            return

        loop = asyncio.get_event_loop()

        class PairingListener(FCMListener):
            def on_notification(self_inner, obj, notification, data_message):
                try:
                    # The pairing data is in data_message, not notification
                    data = data_message or {}

                    # Check if this is a pairing notification
                    if data.get("channelId") != "pairing":
                        return

                    # Parse the body JSON which contains the server info
                    body_str = data.get("body", "{}")
                    try:
                        body = json.loads(body_str)
                    except json.JSONDecodeError:
                        log.warning(f"Could not parse notification body: {body_str}")
                        return

                    # Only handle server pairing notifications
                    if body.get("type") != "server":
                        return

                    ip           = body.get("ip", "")
                    port         = body.get("port", "28017")
                    name         = body.get("name", ip)
                    steam_id     = int(body.get("playerId", 0))
                    player_token = int(body.get("playerToken", 0))

                    if not ip or not steam_id or not player_token:
                        log.warning(f"Incomplete pairing data received: {body}")
                        return

                    log.info(f"📲 Pairing notification: {name} ({ip}:{port})")

                    # Save server to registry
                    server = self.add_server(ip, port, name, steam_id, player_token)

                    # Schedule async work back on the event loop
                    async def _connect_and_notify():
                        try:
                            await self.connect(ip, port)
                            await callback(server)
                        except Exception as e:
                            log.error(f"Post-pairing connection failed: {e}")

                    asyncio.run_coroutine_threadsafe(_connect_and_notify(), loop)

                except Exception as e:
                    log.error(f"Pairing listener error: {e}", exc_info=True)

        # Run FCM listener in a daemon thread (it blocks internally)
        def _run_fcm():
            try:
                PairingListener(fcm_details).start()
            except Exception as e:
                log.error(f"FCM listener crashed: {e}")

        thread = threading.Thread(target=_run_fcm, daemon=True, name="FCMListener")
        thread.start()
        log.info("FCM listener running in background thread")