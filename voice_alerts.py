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
from gtts import gTTS
import tempfile

log = logging.getLogger("VoiceAlerts")

ALARMS_FILE = Path("alarms.json")


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

    async def start_monitoring(self, socket, bot: discord.Client):
        """
        Main loop - checks alarm states every 2 seconds and announces triggers.
        """
        log.info(f"Voice alert monitoring started for {len(self.alarms)} alarms")

        while True:
            try:
                if not self.alarms:
                    await asyncio.sleep(10)
                    continue

                for alarm_name, entity_id in self.alarms.items():
                    try:
                        # Get current alarm state
                        entity = await socket.get_entity_info(entity_id)

                        if hasattr(entity, 'value'):
                            current_state = entity.value
                            last_state = self.alarm_states.get(entity_id, False)

                            # Alarm triggered (False -> True transition)
                            if current_state and not last_state:
                                log.info(f"🚨 Alarm triggered: {alarm_name}")
                                await self._announce(bot, alarm_name)

                            self.alarm_states[entity_id] = current_state

                    except Exception as e:
                        log.warning(f"Could not check alarm {alarm_name}: {e}")

            except Exception as e:
                log.error(f"Monitoring loop error: {e}")

            await asyncio.sleep(2)  # Check every 2 seconds

    async def _announce(self, bot: discord.Client, alarm_name: str):
        """Join voice channel and announce alarm trigger"""
        try:
            channel = bot.get_channel(self.voice_channel_id)
            if not channel:
                log.error(f"Voice channel {self.voice_channel_id} not found")
                return

            # Generate TTS audio
            message = f"Raid alarm triggered: {alarm_name}"
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


async def cmd_alarm_list(manager) -> str:
    """!alarm list"""
    if not manager.alarms:
        return "No alarms configured. Use `!alarm add <name> <entity_id>` to add one."

    lines = [f"> **{name}** - Entity ID: `{eid}`" for name, eid in manager.alarms.items()]
    return "**Monitored Alarms:**\n" + "\n".join(lines)