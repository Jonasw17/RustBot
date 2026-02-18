"""
server_manager_multiuser.py - DEBUG VERSION
────────────────────────────────────────────────────────────────────────────
Enhanced logging to debug pairing issues
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
    """

    def __init__(self, user_manager):
        self.user_manager = user_manager
        self._active_sockets: Dict[str, RustSocket] = {}
        self._active_servers: Dict[str, dict] = {}
        self._chat_callbacks: list[Callable] = []
        self._registered_chat_keys: set = set()
        self._fcm_listeners: Dict[str, threading.Thread] = {}

    def on_team_message(self, callback: Callable):
        """Register callback for team chat messages"""
        self._chat_callbacks.append(callback)

    # ── Per-User Connection Management ────────────────────────────────────────
    async def connect_for_user(self, discord_id: str, ip: str, port: str) -> RustSocket:
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError(f"User {discord_id} not registered. Use !register first.")

        key = f"{ip}:{port}"
        user_servers = user.get("paired_servers", {})
        server = user_servers.get(key)

        if not server:
            raise ValueError(
                f"Server {ip}:{port} not paired for this user.\n"
                f"Join the server in-game and press ESC → Rust+ → Pair Server"
            )

        if discord_id in self._active_sockets:
            try:
                await self._active_sockets[discord_id].disconnect()
            except Exception:
                pass

        log.info(f"Connecting {user['discord_name']} to {server.get('name', key)}")

        server_details = ServerDetails(
            ip,
            port,
            int(user["steam_id"]),
            int(server["player_token"])
        )

        socket = RustSocket(server_details)
        await socket.connect()

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

        self._active_sockets[discord_id] = socket
        self._active_servers[discord_id] = server

        log.info(f"Connected ({user['discord_name']})")
        return socket

    async def ensure_connected_for_user(self, discord_id: str):
        if discord_id in self._active_sockets:
            return

        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        servers = user.get("paired_servers", {})
        if not servers:
            raise ValueError(
                "No servers paired. Join a Rust server and use ESC → Rust+ → Pair Server"
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

    # ── Auto-Pairing via FCM (Per User) ───────────────────────────────────────
    async def start_fcm_listener_for_user(self, discord_id: str, callback: Callable):
        """
        DEBUG VERSION with extensive logging
        """
        user = self.user_manager.get_user(discord_id)
        if not user:
            log.warning(f"Cannot start FCM listener for unregistered user {discord_id}")
            return

        fcm_creds = user.get("fcm_credentials")
        if not fcm_creds:
            log.warning(f"User {discord_id} has no FCM credentials")
            return

        if not isinstance(fcm_creds, dict) or "gcm" not in fcm_creds or "fcm" not in fcm_creds:
            log.error(f"Invalid FCM credentials structure for {user['discord_name']}")
            return

        if discord_id in self._fcm_listeners:
            return

        loop = asyncio.get_event_loop()
        user_manager = self.user_manager

        class UserPairingListener(FCMListener):
            def on_notification(self_inner, obj, notification, data_message):
                try:
                    log.info(f"[DEBUG] on_notification called for {user['discord_name']}")

                    # Attempt to extract 'data' from multiple possible locations/shapes.
                    data = {}

                    # Quick win: if `notification` is already a dict, prefer its keys (it often contains channelId and body).
                    try:
                        if isinstance(notification, dict):
                            data.update(notification)
                    except Exception:
                        pass

                    # Short repr helper used for debug logs
                    def _short_repr(x, max_len=400):
                        try:
                            r = repr(x)
                        except Exception:
                            return f"<unreprable {type(x).__name__}>"
                        if len(r) > max_len:
                            return r[:max_len] + "..."
                        return r

                    # Debug: show incoming shapes early to help diagnose missing keys
                    try:
                        if isinstance(data, dict):
                            log.debug(f"[DEBUG] initial data keys: {list(data.keys())}")
                        if isinstance(notification, dict):
                            log.debug(f"[DEBUG] notification keys: {list(notification.keys())}")
                        if hasattr(data_message, 'app_data'):
                            entries = []
                            for entry in getattr(data_message, 'app_data') or []:
                                k = getattr(entry, 'key', None) or getattr(entry, 'name', None)
                                v = getattr(entry, 'value', None) or getattr(entry, 'val', None)
                                entries.append((k, _short_repr(v, 300)))
                            if entries:
                                log.debug(f"[DEBUG] data_message.app_data entries: {entries}")
                    except Exception:
                        pass

                    # If `data_message` exposes an app_data list (DataMessageStanza), merge its entries.
                    try:
                        if hasattr(data_message, 'app_data') and data_message.app_data:
                            for entry in getattr(data_message, 'app_data') or []:
                                k = getattr(entry, 'key', None) or getattr(entry, 'name', None)
                                v = getattr(entry, 'value', None) or getattr(entry, 'val', None)
                                if k is not None:
                                    # don't overwrite existing keys from notification unless absent
                                    if k not in data:
                                        data[k] = v
                    except Exception:
                        pass

                    # 1) data_message.data (common with some FCM libs)
                    try:
                        if hasattr(data_message, 'data') and data_message.data and not data:
                            raw = data_message.data
                            try:
                                data = dict(raw)
                            except Exception:
                                # raw may be mapping-like but not directly castable
                                if hasattr(raw, 'items'):
                                    data = {k: v for k, v in raw.items()}
                                else:
                                    data = dict(raw)

                        # 2) data_message is a dict-like object
                        elif isinstance(data_message, dict) and data_message and not data:
                            data = dict(data_message)

                        # 3) data_message is a simple object with attributes
                        elif data_message and not data:
                            try:
                                data = vars(data_message)
                            except Exception:
                                # Fallback: attempt to build from public attrs
                                items = {}
                                for k in dir(data_message):
                                    if k.startswith('_'):
                                        continue
                                    try:
                                        v = getattr(data_message, k)
                                    except Exception:
                                        continue
                                    items[k] = v
                                if items:
                                    data = items
                    except Exception as e:
                        log.debug(f"[DEBUG] Error extracting data_message: {e}")

                    # 4) If still empty, check the 'notification' or 'obj' for data
                    if not data:
                        try:
                            # If notification is a dict, its top-level keys often contain the pairing info
                            if isinstance(notification, dict):
                                # prefer a nested 'data' dict if present, otherwise use the notification itself
                                if 'data' in notification and isinstance(notification.get('data'), dict):
                                    data = notification.get('data')
                                else:
                                    data = dict(notification)

                            # Some libs attach data under a .data attribute
                            elif hasattr(notification, 'data') and notification.data:
                                try:
                                    data = dict(notification.data)
                                except Exception:
                                    data = {}

                            # DataMessageStanza often exposes an app_data list of AppData(key, value)
                            elif hasattr(data_message, 'app_data'):
                                try:
                                    items = {}
                                    for entry in getattr(data_message, 'app_data') or []:
                                        # entries may expose 'key' and 'value' attributes
                                        k = getattr(entry, 'key', None) or getattr(entry, 'name', None)
                                        v = getattr(entry, 'value', None) or getattr(entry, 'val', None)
                                        if k is not None:
                                            items[k] = v
                                    if items:
                                        data = items
                                except Exception:
                                    pass

                            # As a last resort, use obj top-level keys
                            elif isinstance(obj, dict):
                                if 'data' in obj and isinstance(obj.get('data'), dict):
                                    data = obj.get('data')
                                else:
                                    data = dict(obj)
                        except Exception as e:
                            log.debug(f"[DEBUG] Error extracting from notification/obj: {e}")

                    # Normalize byte values to strings
                    if isinstance(data, dict):
                        clean = {}
                        for k, v in data.items():
                            if isinstance(v, (bytes, bytearray)):
                                try:
                                    clean[k] = v.decode()
                                except Exception:
                                    clean[k] = v.decode(errors='ignore')
                            else:
                                clean[k] = v
                        data = clean

                    # Initialize body variables; may be set by fallback
                    body = None
                    body_from_fallback = False

                    if not data:
                        try:
                            # Log raw message shapes for debugging
                            def _short_repr(x, max_len=400):
                                try:
                                    r = repr(x)
                                except Exception:
                                    return f"<unreprable {type(x).__name__}>"
                                if len(r) > max_len:
                                    return r[:max_len] + "..."
                                return r

                            # helper to find a JSON object substring in a string
                            def _find_json_in_string(s: str):
                                if not s:
                                    return None
                                start = s.find('{')
                                if start == -1:
                                    return None
                                depth = 0
                                for i in range(start, len(s)):
                                    if s[i] == '{':
                                        depth += 1
                                    elif s[i] == '}':
                                        depth -= 1
                                        if depth == 0:
                                            return s[start:i+1]
                                return None

                            candidates = [_short_repr(obj), _short_repr(notification), _short_repr(data_message)]
                            found = None
                            for c in candidates:
                                try:
                                    j = _find_json_in_string(c)
                                    if j:
                                        # try parse
                                        parsed = json.loads(j)
                                        if isinstance(parsed, dict) and parsed.get('type') == 'server':
                                            found = parsed
                                            break
                                except Exception:
                                    continue

                            if found:
                                log.info('[DEBUG] Found JSON pairing payload in raw message; proceeding')
                                body = found
                                body_from_fallback = True
                                # proceed to process body (skip channelId check)
                            else:
                                log.warning('[DEBUG] No data in message')
                                return
                        except Exception as e:
                            log.debug(f"[DEBUG] Fallback JSON extraction failed: {e}")
                            return

                    # Directly extract channel ID and body when available from `notification` or DataMessageStanza.app_data
                    channel_id = None
                    body_str = None

                    try:
                        # Prefer explicit notification dict fields
                        if isinstance(notification, dict):
                            channel_id = (
                                notification.get('channelId') or notification.get('channelID') or notification.get('channel') or
                                notification.get('gcm.notification.android_channel_id') or notification.get('gcm.notification.channel_id') or
                                notification.get('gcm.notification.channel')
                            )
                            # notification['body'] often contains the JSON payload
                            nb = notification.get('body') or notification.get('message') or notification.get('gcm.notification.body')
                            if isinstance(nb, (bytes, bytearray)):
                                try:
                                    nb = nb.decode()
                                except Exception:
                                    nb = nb.decode(errors='ignore')
                            if isinstance(nb, str) and len(nb) > 2:
                                body_str = nb
                                body_source = 'notification'

                        # If body_str not found, inspect app_data entries on DataMessageStanza
                        if not body_str and hasattr(data_message, 'app_data'):
                            try:
                                for entry in getattr(data_message, 'app_data') or []:
                                    k = getattr(entry, 'key', None) or getattr(entry, 'name', None)
                                    v = getattr(entry, 'value', None) or getattr(entry, 'val', None)
                                    if k and k.lower() in ('body', 'message', 'gcm.notification.body') and v:
                                        if isinstance(v, (bytes, bytearray)):
                                            try:
                                                v = v.decode()
                                            except Exception:
                                                v = v.decode(errors='ignore')
                                        body_str = v
                                        body_source = 'app_data'
                                        break
                                    # also capture channel keys
                                    if k and channel_id is None and k.lower() in ('channelid', 'channel', 'gcm.notification.android_channel_id'):
                                        channel_id = v
                            except Exception:
                                pass

                        # If still missing, use heuristics against the `data` dict
                        if not body_str:
                            # Heuristic: pick the data value that looks like the pairing JSON (contains ip/playerToken/type)
                            body_candidates = []
                            try:
                                for k in ("body", "message", 'gcm.notification.body', 'gcm.notification.title'):
                                    v = data.get(k)
                                    if v is not None:
                                        body_candidates.append((k, v))
                                for k, v in (data.items() if isinstance(data, dict) else []):
                                    if isinstance(v, str):
                                        body_candidates.append((k, v))
                            except Exception:
                                body_candidates = []

                            def _is_pairing_text(s: str) -> bool:
                                s2 = s or ""
                                return ('"playerId"' in s2) or ('"playerToken"' in s2) or ('"ip"' in s2) or ('"type"' in s2)

                            # prefer candidate that contains clear markers
                            for k, v in body_candidates:
                                if isinstance(v, (bytes, bytearray)):
                                    try:
                                        v_dec = v.decode()
                                    except Exception:
                                        v_dec = v.decode(errors='ignore')
                                else:
                                    v_dec = v
                                if isinstance(v_dec, str) and _is_pairing_text(v_dec):
                                    body_str = v_dec
                                    body_source = f'data[{k}]'
                                    break

                            if not body_str:
                                # pick the longest string candidate
                                longest = ('', '')
                                for k, v in body_candidates:
                                    if isinstance(v, (bytes, bytearray)):
                                        try:
                                            v = v.decode()
                                        except Exception:
                                            v = v.decode(errors='ignore')
                                    if isinstance(v, str) and len(v) > len(longest[1]):
                                        longest = (k, v)
                                body_str = longest[1] if longest[1] else "{}"
                                if body_str and 'body_source' not in locals():
                                    body_source = 'data_longest'

                    except Exception as e:
                        log.debug(f"[DEBUG] Error while extracting channel/body: {e}")

                    # If we already found a body via fallback earlier, prefer that
                    if body_from_fallback and body is None:
                        # body variable already set from fallback
                        pass

                    # Now parse the body string if we haven't already
                    if not body and body_str:
                        log.info(f"[DEBUG] Channel ID: {channel_id}")
                        log.info(f"[DEBUG] Body string length: {len(body_str) if hasattr(body_str, '__len__') else 'N/A'}")
                        log.info(f"[DEBUG] Body source: {body_source if 'body_source' in locals() else 'unknown'}")
                        try:
                            body = json.loads(body_str)
                            log.info(f"[DEBUG] Parsed body successfully, type: {body.get('type')}")
                        except Exception as e:
                            log.error(f"[DEBUG] JSON parse failed: {e}")
                            return
                    elif not body:
                        # No body found, continue with earlier behavior (will likely skip)
                        log.info(f"[DEBUG] Channel ID: {channel_id}")
                        log.info("[DEBUG] No body string extracted")
                        # Show debug info about candidates
                        try:
                            if isinstance(data, dict):
                                log.debug(f"[DEBUG] final data keys: {list(data.keys())}")
                            if isinstance(notification, dict):
                                log.debug(f"[DEBUG] final notification keys: {list(notification.keys())}")
                        except Exception:
                            pass

                    # Allow processing if the body itself indicates a server pairing,
                    # even if channel_id is missing or body.type is absent.
                    body_type = None
                    if isinstance(body, dict):
                        body_type = body.get("type")

                    has_required_fields = False
                    if isinstance(body, dict):
                        ip_field = body.get("ip") or body.get("address")
                        player_token_field = body.get("playerToken") or body.get("playerId") or body.get("player_token")
                        if ip_field and player_token_field:
                            has_required_fields = True

                    # Decide whether to proceed: accept if explicit type 'server', channelId == 'pairing',
                    # or body contains the required fields (ip + player token/id).
                    if body_type == "server" or channel_id == "pairing" or has_required_fields:
                        log.info(f"[DEBUG] Processing pairing: body_type={body_type}, channel_id={channel_id}, has_required_fields={has_required_fields}")
                    else:
                        # Provide an INFO-level dump of the raw message shapes so operators
                        # can see why channelId is missing even when DEBUG is not enabled.
                        try:
                            def _short_repr(x, max_len=600):
                                try:
                                    r = repr(x)
                                except Exception:
                                    return f"<unreprable {type(x).__name__}>"
                                if len(r) > max_len:
                                    return r[:max_len] + "..."
                                return r

                            log.info(f"[DEBUG] Not a server notification (body_type={body_type}), channel {channel_id} != 'pairing', required_fields={has_required_fields}; skipping")
                            log.info(f"[RAW] obj type={type(obj).__name__} repr={_short_repr(obj)}")
                            log.info(f"[RAW] notification type={type(notification).__name__} repr={_short_repr(notification)}")
                            log.info(f"[RAW] data_message type={type(data_message).__name__} repr={_short_repr(data_message)}")
                        except Exception as e:
                            log.info(f"[DEBUG] Skipping and failed to dump raw content: {e}")
                        return

                    # Extract server info
                    ip = body.get("ip", "")
                    port = body.get("port", "28017")
                    name = body.get("name", ip)
                    player_token = int(body.get("playerToken", 0))

                    log.info(f"[DEBUG] Parsed server: {name} ({ip}:{port}), token: {player_token}")

                    if not ip or not player_token:
                        log.warning(f"[DEBUG] Missing data - IP: {ip}, Token: {player_token}")
                        return

                    log.info(f"Server paired by {user['discord_name']}: {name}")

                    # Add server to user's account
                    log.info(f"[DEBUG] Adding server to user account...")
                    result = user_manager.add_user_server(
                        discord_id,
                        ip,
                        port,
                        name,
                        player_token
                    )
                    log.info(f"[DEBUG] add_user_server returned: {result}")

                    # Auto-connect and notify
                    async def _connect_and_notify():
                        try:
                            log.info(f"[DEBUG] Starting auto-connect...")
                            socket = await self.connect_for_user(discord_id, ip, port)
                            log.info(f"[DEBUG] Connected, calling callback...")
                            await callback(discord_id, {
                                "ip": ip,
                                "port": port,
                                "name": name,
                                "player_token": player_token
                            })
                            log.info(f"[DEBUG] Callback completed")
                        except Exception as e:
                            log.error(f"Post-pairing connection failed: {e}", exc_info=True)

                    log.info(f"[DEBUG] Scheduling async connection...")
                    asyncio.run_coroutine_threadsafe(_connect_and_notify(), loop)
                    log.info(f"[DEBUG] Async task scheduled")

                except Exception as e:
                    log.error(f"FCM listener error: {e}", exc_info=True)

        def _run_fcm():
            try:
                listener_config = {"fcm_credentials": fcm_creds}
                UserPairingListener(listener_config).start()
            except KeyError as e:
                log.error(f"FCM credentials missing required field for {user['discord_name']}: {e}")
            except Exception as e:
                log.error(f"FCM listener crashed for {user['discord_name']}: {e}", exc_info=True)

        thread = threading.Thread(
            target=_run_fcm,
            daemon=True,
            name=f"FCM-{user['discord_name']}"
        )
        thread.start()
        self._fcm_listeners[discord_id] = thread
        log.info(f"FCM listener started for {user['discord_name']}")

    async def start_all_fcm_listeners(self, callback: Callable):
        """Start FCM listeners for all registered users"""
        for discord_id in self.user_manager._users.keys():
            await self.start_fcm_listener_for_user(discord_id, callback)

    # ── Server Switching ──────────────────────────────────────────────────────
    async def switch_server_for_user(self, discord_id: str, identifier: str) -> Optional[dict]:
        user = self.user_manager.get_user(discord_id)
        if not user:
            raise ValueError("User not registered")

        servers = list(user.get("paired_servers", {}).values())
        if not servers:
            raise ValueError("No servers paired")

        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(servers):
                server = servers[idx]
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        identifier_lower = identifier.lower()
        for server in servers:
            if identifier_lower in server.get("name", "").lower():
                await self.connect_for_user(discord_id, server["ip"], server["port"])
                return server

        return None

    def list_servers_for_user(self, discord_id: str) -> list:
        return self.user_manager.get_user_servers(discord_id)
