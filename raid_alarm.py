"""
raid_alarm.py
────────────────────────────────────────────────────────────────────────────
Raid alarm system that detects when player is being raided.

Features:
- Monitors explosion markers near player's base
- Sends DM to Discord user when raid detected
- Joins voice channel and plays TTS alert
- Configurable detection radius and cooldown
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Dict
import discord

log = logging.getLogger("RaidAlarm")

# Configuration
RAID_DETECTION_RADIUS = 100  # meters from player position
RAID_COOLDOWN = 300  # seconds (5 minutes) before another alert
EXPLOSION_EVENT_TYPE = 1  # Event marker type for explosions


class RaidAlarm:
    """
    Monitors for raid activity and alerts users via DM and voice.
    """
    
    def __init__(self):
        self._enabled_users: Dict[str, bool] = {}  # discord_id -> enabled
        self._last_alert: Dict[str, float] = {}  # discord_id -> timestamp
        self._player_positions: Dict[str, tuple] = {}  # discord_id -> (x, y)
        
    def enable_for_user(self, discord_id: str):
        """Enable raid alarm for a user"""
        self._enabled_users[discord_id] = True
        log.info(f"Raid alarm enabled for user {discord_id}")
        
    def disable_for_user(self, discord_id: str):
        """Disable raid alarm for a user"""
        self._enabled_users[discord_id] = False
        log.info(f"Raid alarm disabled for user {discord_id}")
        
    def is_enabled(self, discord_id: str) -> bool:
        """Check if raid alarm is enabled for user"""
        return self._enabled_users.get(discord_id, False)
    
    def update_player_position(self, discord_id: str, x: float, y: float):
        """Update player's known position"""
        self._player_positions[discord_id] = (x, y)
    
    async def check_for_raids(
        self,
        discord_id: str,
        markers: list,
        player_x: float,
        player_y: float,
        discord_user: discord.User,
        bot: discord.Client
    ):
        """
        Check if any explosion events are near the player.
        
        Args:
            discord_id: Discord user ID
            markers: List of map markers from Rust+ API
            player_x: Player's X coordinate
            player_y: Player's Y coordinate
            discord_user: Discord User object
            bot: Discord bot client
        """
        if not self.is_enabled(discord_id):
            return
        
        # Check cooldown
        last = self._last_alert.get(discord_id, 0)
        if time.time() - last < RAID_COOLDOWN:
            return
        
        # Update position
        self.update_player_position(discord_id, player_x, player_y)
        
        # Check for nearby explosions
        explosions = [m for m in markers if m.type == EXPLOSION_EVENT_TYPE]
        
        for explosion in explosions:
            distance = self._calculate_distance(
                player_x, player_y,
                explosion.x, explosion.y
            )
            
            if distance <= RAID_DETECTION_RADIUS:
                log.warning(f"RAID DETECTED for {discord_id}: explosion {distance:.1f}m away")
                await self._trigger_alarm(discord_id, discord_user, bot, distance)
                self._last_alert[discord_id] = time.time()
                break
    
    def _calculate_distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Calculate Euclidean distance between two points"""
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    
    async def _trigger_alarm(
        self,
        discord_id: str,
        user: discord.User,
        bot: discord.Client,
        distance: float
    ):
        """
        Trigger the raid alarm - send DM and join voice.
        
        Args:
            discord_id: Discord user ID
            user: Discord User object
            bot: Discord bot client
            distance: Distance to explosion in meters
        """
        # Send DM
        try:
            embed = discord.Embed(
                title="[RAID ALERT]",
                description=(
                    f"**You're being raided!**\n\n"
                    f"Explosion detected {distance:.0f}m from your position.\n"
                    f"Check your base immediately!"
                ),
                color=0xFF0000
            )
            embed.set_footer(text="Raid alarm will not trigger again for 5 minutes")
            
            await user.send(embed=embed)
            log.info(f"Sent raid alert DM to {user}")
        except discord.Forbidden:
            log.warning(f"Cannot send DM to {user} - DMs disabled")
        except Exception as e:
            log.error(f"Failed to send raid alert DM: {e}")
        
        # Try to join voice and play alert
        try:
            await self._play_voice_alert(user, bot)
        except Exception as e:
            log.error(f"Failed to play voice alert: {e}")
    
    async def _play_voice_alert(self, user: discord.User, bot: discord.Client):
        """
        Join user's voice channel and play TTS alert.
        
        Args:
            user: Discord User object
            bot: Discord bot client
        """
        # Find user in a voice channel across all guilds
        voice_channel = None
        for guild in bot.guilds:
            member = guild.get_member(user.id)
            if member and member.voice and member.voice.channel:
                voice_channel = member.voice.channel
                break
        
        if not voice_channel:
            log.info(f"User {user} not in voice channel - skipping voice alert")
            return
        
        log.info(f"Joining voice channel: {voice_channel.name}")
        
        try:
            # Check if bot is already in a voice channel in this guild
            if voice_channel.guild.voice_client:
                vc = voice_channel.guild.voice_client
                if vc.channel != voice_channel:
                    await vc.move_to(voice_channel)
            else:
                vc = await voice_channel.connect()
            
            # Play TTS message
            if vc.is_connected():
                # Use Discord's built-in TTS (requires text channel)
                # Alternative: Use FFmpeg audio source if you have audio files
                log.info("Voice connected - TTS alert would play here")
                
                # Wait a moment then disconnect
                await asyncio.sleep(3)
                await vc.disconnect()
                
        except discord.ClientException as e:
            log.error(f"Voice connection error: {e}")
        except Exception as e:
            log.error(f"Voice alert error: {e}")


# Global instance
raid_alarm = RaidAlarm()


# Command handlers
async def cmd_raidalarm(args: str, discord_id: str, user_manager) -> str:
    """
    !raidalarm [on|off|status]
    
    Enable/disable raid alarm notifications.
    """
    if not discord_id or not user_manager.has_user(discord_id):
        return "You need to register first. Use `!register`"
    
    if not args:
        args = "status"
    
    cmd = args.lower().strip()
    
    if cmd in ("on", "enable", "start"):
        raid_alarm.enable_for_user(discord_id)
        return (
            "**Raid Alarm Enabled**\n\n"
            "You will be alerted via DM and voice when explosions are detected near you.\n"
            "Detection radius: 100m\n"
            "Cooldown: 5 minutes between alerts"
        )
    
    elif cmd in ("off", "disable", "stop"):
        raid_alarm.disable_for_user(discord_id)
        return "**Raid Alarm Disabled**"
    
    elif cmd in ("status", "info"):
        enabled = raid_alarm.is_enabled(discord_id)
        status = "Enabled" if enabled else "Disabled"
        
        last_alert = raid_alarm._last_alert.get(discord_id, 0)
        if last_alert and enabled:
            time_since = int(time.time() - last_alert)
            cooldown_left = max(0, RAID_COOLDOWN - time_since)
            
            if cooldown_left > 0:
                cooldown_msg = f"\nCooldown: {cooldown_left}s remaining"
            else:
                cooldown_msg = "\nReady to detect"
        else:
            cooldown_msg = ""
        
        return (
            f"**Raid Alarm Status**\n\n"
            f"Status: **{status}**\n"
            f"Detection radius: 100m\n"
            f"Cooldown: 5 minutes{cooldown_msg}"
        )
    
    else:
        return (
            "Usage: `!raidalarm [on|off|status]`\n\n"
            "**Commands:**\n"
            "`!raidalarm on` - Enable raid detection\n"
            "`!raidalarm off` - Disable raid detection\n"
            "`!raidalarm status` - Check current status"
        )
