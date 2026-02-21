"""
status_embed.py
────────────────────────────────────────────────────────────────────────────
Server status embed builder - shared between bot.py and commands.py

FIXED VERSION:
- Removed all emoji characters (prevents encoding errors)
- Clarified time calculation logic
- Added proper comments
"""

import asyncio
import logging
import time
import discord
from rustplus import RustError

log = logging.getLogger("StatusEmbed")


def _parse_time_to_float(t) -> float:
    """
    Safely parse time value from Rust+ API that could be:
    - A float (19.35)
    - A string with colon ("19:21")
    - A string number ("19.35")

    Returns float or 0.0 on error.
    """
    try:
        # If it's already a number type
        if isinstance(t, (int, float)):
            return float(t)

        # If it's a string
        if isinstance(t, str):
            # Handle "HH:MM" format
            if ":" in t:
                parts = t.split(":")
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 0
                return h + (m / 60.0)
            # Handle string number "19.35"
            else:
                return float(t)

        # Fallback: try to convert to float
        return float(t)
    except (ValueError, TypeError, AttributeError):
        return 0.0


def _fmt_time_val(t) -> str:
    """Format time as 12-hour format"""
    try:
        if isinstance(t, str) and ":" in t:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        h = int(float(t))
        m = int((float(t) - h) * 60)
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return str(t)


def _calculate_time_until_change(now_ig: float, sunrise: float, sunset: float) -> tuple[str, str]:
    """
    Calculate time until next day/night phase change.

    Rust time mechanics:
    - 24-hour in-game cycle = 60 real minutes
    - 1 in-game hour = 2.5 real minutes

    Args:
        now_ig: Current in-game time (0-24)
        sunrise: Sunrise time (e.g., 6.5 for 6:30 AM)
        sunset: Sunset time (e.g., 18.5 for 6:30 PM)

    Returns:
        (phase_indicator, time_message)
        Example: ("[Day]", "Night in 15m")
    """
    is_day = sunrise <= now_ig < sunset

    if is_day:
        # Currently day - calculate hours until sunset
        diff_h = (sunset - now_ig) % 24
        real_mins = int(diff_h * 2.5)
        return "[Day]", f"Night in {real_mins}m"
    else:
        # Currently night - calculate hours until sunrise
        # The modulo handles wrapping: (6.5 - 23.0) % 24 = 7.5
        diff_h = (sunrise - now_ig) % 24
        real_mins = int(diff_h * 2.5)
        return "[Night]", f"Day in {real_mins}m"


def _build_minimal_embed(server: dict, status: str) -> discord.Embed:
    """Build a minimal embed when full info is unavailable"""
    embed = discord.Embed(
        title=f"[!] {server.get('name', server['ip'])}",
        description=status,
        color=0xFFA500,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="Connect",
        value=f"`connect {server['ip']}:{server.get('port', '28017')}`"
    )
    return embed


async def build_server_status_embed(server: dict, socket, user_info: dict = None) -> discord.Embed:
    """Build a rich server status embed with live data"""
    try:
        info = await asyncio.wait_for(socket.get_info(), timeout=10.0)
        time_obj = await asyncio.wait_for(socket.get_time(), timeout=10.0)

        if isinstance(info, RustError) or isinstance(time_obj, RustError):
            raise Exception("Failed to fetch server info - Maybe it got wiped!")

        # Calculate wipe age
        wipe_ts = getattr(info, "wipe_time", 0) or 0
        now_ts = int(time.time())
        wipe_days = (now_ts - wipe_ts) / 86400 if wipe_ts else 0

        # Format player count
        players = f"{info.players}/{info.max_players}"
        if info.queued_players:
            players += f" ({info.queued_players} queued)"

        # Calculate day/night timing
        now_ig = _parse_time_to_float(time_obj.time)
        sunset = _parse_time_to_float(time_obj.sunset)
        sunrise = _parse_time_to_float(time_obj.sunrise)

        phase_indicator, next_change = _calculate_time_until_change(now_ig, sunrise, sunset)

        # Build embed
        embed = discord.Embed(
            title=f"[ONLINE] {server.get('name', server['ip'])}",
            color=0xCE422B,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Players", value=players, inline=True)
        embed.add_field(name="Time", value=f"{phase_indicator} {_fmt_time_val(time_obj.time)}", inline=True)
        embed.add_field(name="Next Phase", value=next_change, inline=True)

        embed.add_field(name="Since Wipe", value=f"{wipe_days:.1f} days", inline=True)
        embed.add_field(name="Map", value=f"{info.map} ({info.size})", inline=True)
        embed.add_field(name="Seed", value=f"`{info.seed}`", inline=True)

        embed.add_field(
            name="Connect",
            value=f"`connect {server['ip']}:{server.get('port', '28017')}`",
            inline=False
        )

        # Add user info if provided
        if user_info:
            embed.set_footer(text=f"Connected by {user_info.get('discord_name', 'User')} | Updates every 45s")
        else:
            embed.set_footer(text="Updates every 45s")

        return embed

    except asyncio.TimeoutError:
        log.warning(f"Server status timeout for {server.get('name', server['ip'])}")
        return _build_minimal_embed(server, "[!] Connection timeout")
    except Exception as e:
        log.error(f"Error building status embed: {e}")
        return _build_minimal_embed(server, f"[!] Error: {str(e)[:50]}")