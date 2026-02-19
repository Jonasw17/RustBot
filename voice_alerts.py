"""
voice_alerts.py
────────────────────────────────────────────────────────────────────────────
Voice channel notifications when smart alarms trigger.

Usage:
    1. Add alarm entity IDs to alarms.json: {"raid_alarm": 123456789}
    2. Set VOICE_CHANNEL_ID in .env
    3. Bot will join voice and announce when alarms trigger
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Optional
import discord
import inspect
import re
from gtts import gTTS
import tempfile

log = logging.getLogger("VoiceAlerts")

ALARMS_FILE = Path("alarms.json")


async def _send_dm(bot_client: discord.Client, owner_id: int, text: str) -> tuple[bool, str]:
    """Try to DM a user by id. Returns (success, message).

    Attempts bot.get_user(owner_id) first (cached), then bot.fetch_user(owner_id).
    Returns (True, 'ok') on success, or (False, '<error>') on failure.
    """
    try:
        # Normalize/parse owner_id to an int if possible. Owner may have been stored incorrectly.
        owner_repr = repr(owner_id)
        owner_type = type(owner_id).__name__
        owner_int = None
        try:
            owner_int = int(owner_id)
        except Exception:
            # Try extracting digits from string-like values
            try:
                if isinstance(owner_id, str):
                    digits = re.sub(r"\D", "", owner_id)
                    if digits:
                        owner_int = int(digits)
            except Exception:
                owner_int = None

        if owner_int is None:
            return False, f"invalid_owner_id: repr={owner_repr}, type={owner_type}"

        user = None

        # 1) Try cached user object first (fast, avoids network)
        try:
            user = bot_client.get_user(owner_int)
        except Exception:
            user = None

        # 2) If not found, try to locate the user as a Member in any guild the bot is in
        if user is None:
            try:
                for g in getattr(bot_client, 'guilds', []):
                    try:
                        m = g.get_member(owner_int)
                        if m is not None:
                            user = m
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # 3) Fallback: try fetch_user as last resort (network call) — catch any internal errors
        fetch_exc = None
        if user is None:
            try:
                user = await bot_client.fetch_user(owner_int)
            except Exception as e:
                fetch_exc = e
                user = None

        if user is None:
            return False, f"user_not_found: repr={owner_repr}, type={owner_type}, fetch_exc={repr(fetch_exc)}"
        # Validate fetched object
        if not hasattr(user, 'send'):
            return False, f"invalid_user_object: repr={repr(user)}, type={type(user).__name__}, fetch_exc={repr(fetch_exc)}"
    except Exception as e:
        return False, f"unexpected: {e}"

    # Prefer direct user.send (works whether or not dm_channel exists). If that fails,
    # fall back to creating a DM channel explicitly. Return detailed errors for debugging.
    import traceback
    try:
        try:
            await user.send(text)
            return True, "ok"
        except Exception as send_exc:
            # Attempt to create DM channel and send
            try:
                dm = getattr(user, 'dm_channel', None)
                if dm is None:
                    dm = await user.create_dm()
                if dm is None:
                    return False, f"create_dm_returned_none (user={repr(user)})"
                if not hasattr(dm, 'send'):
                    return False, f"dm_channel_missing_send_attr: {type(dm).__name__}"
                await dm.send(text)
                return True, "ok"
            except Exception as dm_exc:
                tb = traceback.format_exc()
                return False, f"send_exc={repr(send_exc)}; dm_exc={repr(dm_exc)}; tb={tb}"
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"unexpected: {repr(e)}; tb={tb}"
    return False, "unknown_error"


async def _post_notification_fallback(bot_client: discord.Client, owner_int: int | str, server: str | None, alarm_name: str, reason: str):
    """Attempt to post a notification to the configured NOTIFICATION_CHANNEL when DM fails.

    This imports the bot module at runtime to read NOTIFICATION_CHANNEL. It will silently
    ignore failures (best-effort fallback).
    """
    try:
        try:
            from bot import NOTIFICATION_CHANNEL
        except Exception:
            NOTIFICATION_CHANNEL = None

        if not NOTIFICATION_CHANNEL:
            return False

        chan = bot_client.get_channel(NOTIFICATION_CHANNEL)
        if chan is None:
            try:
                chan = await bot_client.fetch_channel(NOTIFICATION_CHANNEL)
            except Exception:
                chan = None

        if not chan:
            return False

        owner_mention = f"<@{owner_int}>" if owner_int else "(owner)"
        server_str = server or alarm_name
        msg = f"[ALERT] Could not DM owner {owner_mention} for alarm **{alarm_name}** on {server_str}: {reason}"
        try:
            await chan.send(msg)
            return True
        except Exception:
            return False
    except Exception:
        return False


class VoiceAlertManager:
    """
    Monitors smart alarms and sends voice notifications when they trigger.
    """

    def __init__(self, voice_channel_id: int):
        self.voice_channel_id = voice_channel_id
        self.alarms: dict = self._load_alarms()
        self.alarm_states: dict = {}  # entity_id -> last_known_state
        self._voice_client: Optional[discord.VoiceClient] = None

    def _load_alarms(self) -> dict:
        """Load alarm registry from alarms.json"""
        try:
            if ALARMS_FILE.exists():
                return json.loads(ALARMS_FILE.read_text())
        except Exception as e:
            log.warning(f"Could not load alarms.json: {e}")
        return {}

    def add_alarm(self, name: str, entity_id: int):
        """Register a new alarm to monitor"""
        self.alarms[name] = entity_id
        try:
            ALARMS_FILE.write_text(json.dumps(self.alarms, indent=2))
        except Exception as e:
            log.error(f"Could not save alarm: {e}")

    async def start_monitoring(self, socket, bot: discord.Client, monitored_server: str | None = None):
        """
        Main loop - checks alarm states every 2 seconds and announces triggers.
        """
        log.info(f"Voice alert monitoring started for {len(self.alarms)} alarms")

        while True:
            try:
                # Reload alarms each loop to pick up newly paired alarms written by pairing listeners
                try:
                    self.alarms = self._load_alarms() or {}
                except Exception:
                    # if reload fails, fall back to existing in-memory list
                    pass

                if not self.alarms:
                    await asyncio.sleep(10)
                    continue

                # Debug: log number of alarms loaded
                log.info(f"Loaded {len(self.alarms)} alarm(s) from alarms.json")

                # alarms.json schema backwards-compatible: value may be int (entity_id)
                # or a dict: {"entity_id": 12345, "server": "ip:port", "owner": "discord_id"}
                for alarm_name, alarm_val in self.alarms.items():
                    try:
                        # Normalize alarm entry
                        if isinstance(alarm_val, dict):
                            entity_id = alarm_val.get("entity_id") or alarm_val.get("entityId")
                            owner_id = alarm_val.get("owner")
                            server_key = alarm_val.get("server")
                        else:
                            entity_id = alarm_val
                            owner_id = None
                            server_key = None

                        # If this monitor is tied to a specific server, skip alarms for other servers
                        if monitored_server and server_key and server_key != monitored_server:
                            continue

                        if entity_id is None:
                            log.debug(f"Skipping alarm {alarm_name} with missing entity id")
                            continue

                        # Get current alarm state
                        entity = None
                        # Try several possible rustplus socket API names for fetching entity state
                        tried = []
                        for meth in ("get_entity_info", "get_entity", "get_entity_by_id", "get_entity_state", "get_entity_value"):
                            fn = getattr(socket, meth, None)
                            if callable(fn):
                                try:
                                    tried.append(meth)
                                    res = fn(int(entity_id))
                                    # If the method returned an awaitable, await it; otherwise use directly
                                    if inspect.isawaitable(res):
                                        try:
                                            entity = await res
                                        except Exception as e:
                                            log.debug(f"Awaiting {meth} raised for {entity_id}: {e}")
                                            entity = None
                                    else:
                                        entity = res
                                    break
                                except Exception as e:
                                    log.debug(f"Entity lookup {meth} failed for {entity_id}: {e}")

                        if entity is None:
                            # maybe socket exposes a mapping
                            try:
                                if hasattr(socket, 'entities'):
                                    entmap = getattr(socket, 'entities')
                                    entity = entmap.get(int(entity_id)) if isinstance(entmap, dict) else None
                            except Exception:
                                entity = None

                        # Determine boolean state from returned entity or value
                        current_state = False
                        if entity is None:
                            log.info(f"Alarm {alarm_name}: could not retrieve entity {entity_id} (tried: {tried})")
                            # skip to next alarm
                            self.alarm_states[str(entity_id)] = False
                            continue

                        # entity may be a primitive (bool/int) or object/dict
                        if isinstance(entity, (bool, int)):
                            current_state = bool(entity)
                        else:
                            # object or dict
                            if isinstance(entity, dict):
                                # common keys
                                if 'value' in entity:
                                    current_state = bool(entity.get('value'))
                                elif 'state' in entity:
                                    current_state = bool(entity.get('state'))
                                elif 'val' in entity:
                                    current_state = bool(entity.get('val'))
                            else:
                                # object with attributes
                                try:
                                    if hasattr(entity, 'value'):
                                        current_state = bool(getattr(entity, 'value'))
                                    elif hasattr(entity, 'state'):
                                        current_state = bool(getattr(entity, 'state'))
                                    elif hasattr(entity, 'val'):
                                        current_state = bool(getattr(entity, 'val'))
                                except Exception:
                                    current_state = False

                        last_state = self.alarm_states.get(str(entity_id), False)
                        log.info(f"Alarm {alarm_name} ({entity_id}) state: {current_state} (last: {last_state})")

                        # Alarm triggered (False -> True transition)
                        if current_state and not last_state:
                            log.info(f"🚨 Alarm triggered: {alarm_name} on {server_key}")

                            # Send DM to owner if known
                            if owner_id:
                                try:
                                    dm_text = f"You're being raided on {server_key or alarm_name}!"
                                    ok, msg = await _send_dm(bot, owner_id, dm_text)
                                    if ok:
                                        log.info(f"Sent raid DM to {owner_id}")
                                    else:
                                        log.warning(f"Could not send DM to {owner_id}: {msg}")
                                        # fallback: post to notification channel so owner sees it
                                        try:
                                            owner_int = None
                                            try:
                                                owner_int = int(owner_id)
                                            except Exception:
                                                owner_int = owner_id
                                            await _post_notification_fallback(bot, owner_int, server_key, alarm_name, msg)
                                        except Exception:
                                            pass
                                except Exception as e:
                                    log.warning(f"Could not send DM to {owner_id}: {e}")

                            # Voice announcement
                            try:
                                await self._announce(bot, alarm_name)
                            except Exception as e:
                                log.warning(f"Voice announce failed: {e}")

                        # store last_state keyed by entity id
                        self.alarm_states[str(entity_id)] = bool(current_state)

                    except Exception as e:
                        log.warning(f"Could not check alarm {alarm_name}: {e}")

            except Exception as e:
                log.error(f"Monitoring loop error: {e}")

            await asyncio.sleep(2)  # Check every 2 seconds

    async def _announce(self, bot: discord.Client, alarm_name: str):
        """Join voice channel and announce alarm trigger"""
        # Voice channel must be configured
        if not self.voice_channel_id:
            raise RuntimeError("Voice channel ID not configured for VoiceAlertManager")

        try:
            channel = bot.get_channel(self.voice_channel_id)
            # If channel not in cache, try fetching it from API
            try:
                if not channel:
                    channel = await bot.fetch_channel(self.voice_channel_id)
            except Exception as e:
                log.error(f"Voice channel {self.voice_channel_id} not found via cache or fetch: {e}")
                raise RuntimeError(f"Voice channel {self.voice_channel_id} not found")

            # Generate TTS audio - use fixed urgent message
            message = "You're being raided"
            tts = gTTS(text=message, lang='en', slow=False)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                temp_file = fp.name
                tts.save(temp_file)

            # Join voice channel if not already connected
            if self._voice_client is None or not self._voice_client.is_connected():
                self._voice_client = await channel.connect()
                log.info(f"Joined voice channel: {channel.name}")

            # Play announcement
            audio_source = discord.FFmpegPCMAudio(temp_file)
            self._voice_client.play(audio_source)

            # Wait for playback to finish
            while self._voice_client.is_playing():
                await asyncio.sleep(0.1)

            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)

            # Leave after 2 seconds
            await asyncio.sleep(2)
            if self._voice_client and self._voice_client.is_connected():
                await self._voice_client.disconnect()
                self._voice_client = None

        except Exception as e:
            log.error(f"Voice announcement error: {e}")


# Command handlers for bot integration
async def cmd_alarm_add(args: str, manager) -> str:
    """!alarm add <name> <entity_id>"""
    parts = args.split()
    if len(parts) != 2:
        return "Usage: `!alarm add <name> <entity_id>`\nExample: `!alarm add raid_tc 123456789`"

    name, entity_id = parts[0], parts[1]
    try:
        entity_id = int(entity_id)
        manager.add_alarm(name, entity_id)
        return f"Alarm **{name}** (ID: {entity_id}) added to monitoring."
    except ValueError:
        return "Entity ID must be a number."


async def cmd_alarm_list(manager=None) -> str:
    """!alarm list

    manager: optional VoiceAlertManager instance. When omitted, read directly from alarms.json.
    """
    alarms = None
    if manager is not None and hasattr(manager, 'alarms'):
        alarms = manager.alarms
    else:
        # Load from file fallback
        try:
            if ALARMS_FILE.exists():
                alarms = json.loads(ALARMS_FILE.read_text())
        except Exception as e:
            log.warning(f"Could not read alarms.json: {e}")

    if not alarms:
        return "No alarms configured. Use `!alarm add <name> <entity_id>` to add one."

    lines = []
    for name, val in (alarms.items() if isinstance(alarms, dict) else []):
        try:
            if isinstance(val, dict):
                eid = val.get("entity_id") or val.get("entityId") or "<unknown>"
                server = val.get("server")
                owner = val.get("owner")
                meta = []
                if server:
                    meta.append(f"Server: `{server}`")
                if owner:
                    meta.append(f"Owner: `{owner}`")
                meta_str = " — " + " | ".join(meta) if meta else ""
                lines.append(f"> **{name}** - Entity ID: `{eid}`{meta_str}")
            else:
                lines.append(f"> **{name}** - Entity ID: `{val}`")
        except Exception:
            lines.append(f"> **{name}** - (invalid entry) `{val}`")

    return "**Monitored Alarms:**\n" + "\n".join(lines)


# New helper: register alarm into alarms.json from pairing listeners
def register_alarm(name: str, entity_id, server: str = None, owner: str = None) -> bool:
    """Register an alarm in alarms.json storing entity, server and owner.

    The JSON schema becomes:
      { "alarm_name": {"entity_id": 123, "server": "ip:port", "owner": "discord_id"}, ... }

    Backwards compatibility: if alarms.json contains simple values, they are preserved.
    Returns True if the alarm was added or updated, False on error.
    """
    try:
        ea = {}
        if ALARMS_FILE.exists():
            try:
                ea = json.loads(ALARMS_FILE.read_text())
            except Exception:
                ea = {}

        # coerce entity_id to int when possible
        try:
            entity_id_int = int(entity_id)
        except Exception:
            entity_id_int = entity_id

        entry = {"entity_id": entity_id_int}
        if server:
            entry["server"] = server
        if owner:
            entry["owner"] = str(owner)

        ea[name] = entry
        ALARMS_FILE.write_text(json.dumps(ea, indent=2))
        log.info(f"Saved alarm pairing: {name} -> {entry}")
        return True
    except Exception as e:
        log.error(f"Could not save alarm pairing: {e}")
        return False


# Test helper: trigger an alarm by name (sends DM and does voice announce)
async def cmd_alarm_trigger(identifier: str, bot_client: discord.Client) -> str:
    """Trigger alarm actions for a given alarm name OR numeric entity id (for testing).

    identifier: alarm name (string key in alarms.json) OR numeric entity id (digits).
    Looks up alarms.json, sends DM to owner (if present), and runs the voice announcement.
    """
    try:
        if not ALARMS_FILE.exists():
            return "No alarms configured."
        alarms = json.loads(ALARMS_FILE.read_text())

        entry = alarms.get(identifier)
        alarm_name = identifier

        # If direct name lookup failed and identifier looks like a number, search by entity_id
        if entry is None and identifier.isdigit():
            target = int(identifier)
            for k, v in alarms.items():
                try:
                    if isinstance(v, dict):
                        vid = v.get("entity_id") or v.get("entityId")
                    else:
                        vid = v
                    if vid is not None and int(vid) == target:
                        entry = v
                        alarm_name = k
                        break
                except Exception:
                    continue

        if entry is None:
            return f"Alarm '{identifier}' not found."

        # Normalize
        if isinstance(entry, dict):
            eid = entry.get("entity_id") or entry.get("entityId")
            owner = entry.get("owner")
            server = entry.get("server")
        else:
            eid = entry
            owner = None
            server = None

        # Try to DM (non-fatal) then always attempt voice announce; return combined result
        dm_ok = None
        dm_msg = "not_attempted"
        if owner:
            dm_ok, dm_msg = await _send_dm(bot_client, owner, f"[TEST] You're being raided on {server or alarm_name}!")
            if not dm_ok:
                try:
                    owner_int = None
                    try:
                        owner_int = int(owner)
                    except Exception:
                        owner_int = owner
                    await _post_notification_fallback(bot_client, owner_int, server, alarm_name, dm_msg)
                except Exception:
                    pass

        # Announce in voice if available
        voice_ok = None
        voice_msg = "not_attempted"
        try:
            if not bot_client:
                voice_ok = False
                voice_msg = "Bot client not available for voice announce"
            else:
                try:
                    from bot import voice_alert_manager
                    vam = voice_alert_manager
                except Exception:
                    vam = None

                if vam is None:
                    voice_ok = False
                    voice_msg = "VoiceAlertManager not configured"
                else:
                    try:
                        await vam._announce(bot_client, alarm_name)
                        voice_ok = True
                        voice_msg = "ok"
                    except RuntimeError as e:
                        voice_ok = False
                        voice_msg = f"not_configured: {e}"
                    except Exception as e:
                        voice_ok = False
                        voice_msg = f"announce_failed: {e}"
        except Exception as e:
            voice_ok = False
            voice_msg = f"announce_exception: {e}"

        # Build combined message
        parts = []
        if owner:
            parts.append(f"DM: {'ok' if dm_ok else 'failed'} ({dm_msg})")
        else:
            parts.append("DM: not configured")
        parts.append(f"Voice: {'ok' if voice_ok else 'failed'} ({voice_msg})")
        return "; ".join(parts)

    except Exception as e:
        return f"Error triggering alarm: {e}"


def get_alarm_owner_info(identifier: str) -> str:
    """Return a short summary of the alarm entry for debugging owner values.

    identifier: alarm name or numeric entity id.
    """
    try:
        if not ALARMS_FILE.exists():
            return "No alarms configured."
        alarms = json.loads(ALARMS_FILE.read_text())

        entry = alarms.get(identifier)
        alarm_name = identifier

        if entry is None and identifier.isdigit():
            target = int(identifier)
            for k, v in alarms.items():
                try:
                    if isinstance(v, dict):
                        vid = v.get("entity_id") or v.get("entityId")
                    else:
                        vid = v
                    if vid is not None and int(vid) == target:
                        entry = v
                        alarm_name = k
                        break
                except Exception:
                    continue

        if entry is None:
            return f"Alarm '{identifier}' not found."

        if isinstance(entry, dict):
            eid = entry.get("entity_id") or entry.get("entityId")
            owner = entry.get("owner")
            server = entry.get("server")
        else:
            eid = entry
            owner = None
            server = None

        return (
            f"Alarm: {alarm_name}\n"
            f"  entity_id: {eid}\n"
            f"  server: {server}\n"
            f"  owner (repr): {repr(owner)}\n"
            f"  owner type: {type(owner).__name__}\n"
        )
    except Exception as e:
        return f"Error reading alarms.json: {e}"


def set_alarm_owner(identifier: str, owner_id) -> str:
    """Set/replace the owner for an alarm entry (writes alarms.json).

    identifier may be alarm name or entity id. owner_id should be a numeric id or string.
    Returns a status string.
    """
    try:
        if not ALARMS_FILE.exists():
            return "No alarms configured."
        data = json.loads(ALARMS_FILE.read_text())

        entry = data.get(identifier)
        alarm_name = identifier
        if entry is None and identifier.isdigit():
            target = int(identifier)
            for k, v in data.items():
                try:
                    vid = v.get('entity_id') if isinstance(v, dict) else v
                    if vid is not None and int(vid) == target:
                        entry = v
                        alarm_name = k
                        break
                except Exception:
                    continue

        if entry is None:
            return f"Alarm '{identifier}' not found."

        # ensure dict
        if not isinstance(entry, dict):
            entry = {"entity_id": entry}

        entry['owner'] = str(owner_id)
        data[alarm_name] = entry
        ALARMS_FILE.write_text(json.dumps(data, indent=2))
        return f"Owner for alarm '{alarm_name}' set to {owner_id}"
    except Exception as e:
        return f"Could not set owner: {e}"


def get_voice_and_notification_diag(bot_client: discord.Client) -> str:
    """Return diagnostic info about voice and notification channels and bot visibility."""
    try:
        out = []
        # notification channel
        try:
            from bot import NOTIFICATION_CHANNEL, VOICE_CHANNEL_ID
        except Exception:
            NOTIFICATION_CHANNEL = None
            VOICE_CHANNEL_ID = None

        out.append(f"NOTIFICATION_CHANNEL configured: {bool(NOTIFICATION_CHANNEL)}")
        if NOTIFICATION_CHANNEL:
            ch = bot_client.get_channel(NOTIFICATION_CHANNEL)
            out.append(f"  get_channel -> {repr(ch)}")
            # cannot await fetch here; return note
            out.append(f"  (will attempt fetch at runtime if needed)")

        out.append(f"VOICE_CHANNEL_ID configured: {bool(VOICE_CHANNEL_ID)}")
        if VOICE_CHANNEL_ID:
            chv = bot_client.get_channel(VOICE_CHANNEL_ID)
            out.append(f"  get_channel -> {repr(chv)}")
            try:
                # try to inspect permissions if channel is a VoiceChannel
                if chv and hasattr(chv, 'guild'):
                    perms = chv.permissions_for(bot_client.user)
                    out.append(f"  bot perms in channel -> connect={getattr(perms, 'connect', None)}, speak={getattr(perms, 'speak', None)}")
            except Exception as e:
                out.append(f"  could not inspect perms: {e}")

        return "\n".join(out)
    except Exception as e:
        return f"Diag error: {e}"

