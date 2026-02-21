"""
death_tracker.py
────────────────────────────────────────────────────────────────────────────
Death Location Tracker - Monitor team deaths and report grid positions

Features:
- Track when teammates die
- Report grid location (e.g., "K15")
- Persistent death history
- Auto-notification to Discord
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict
import discord

log = logging.getLogger("DeathTracker")

DEATHS_FILE = Path("death_history.json")


def coords_to_grid(x: float, y: float, map_size: int) -> str:
    """
    Convert Rust map coordinates to grid reference (e.g., "K15").
    
    Rust maps use:
    - Origin (0, 0) at bottom-left
    - Map size determines scale
    - Standard sizes: 3000, 4000, 4500, 5000, 6000
    
    Grid system:
    - Letters: A-Z (left to right)
    - Numbers: 0-25+ (bottom to top)
    """
    # Normalize coordinates to 0-1 range
    norm_x = (x + (map_size / 2)) / map_size
    norm_y = (y + (map_size / 2)) / map_size
    
    # Clamp to valid range
    norm_x = max(0, min(1, norm_x))
    norm_y = max(0, min(1, norm_y))
    
    # Convert to grid
    # 26 letters across (A-Z)
    grid_size = 26
    
    col = int(norm_x * grid_size)
    row = int(norm_y * grid_size)
    
    # Clamp to valid grid
    col = min(col, grid_size - 1)
    row = min(row, grid_size - 1)
    
    # Convert column to letter (A=0, B=1, etc.)
    letter = chr(ord('A') + col)
    
    return f"{letter}{row}"


class DeathTracker:
    """
    Tracks team member deaths and their locations.
    
    History format:
    {
      "discord_id_server_key": [
        {
          "player_name": "PlayerName",
          "steam_id": 76561198...,
          "timestamp": 1234567890,
          "x": 100.5,
          "y": 200.3,
          "grid": "K15",
          "map_size": 4000
        }
      ]
    }
    """
    
    def __init__(self):
        self._history: Dict = self._load()
        self._last_alive_state: Dict = {}  # Track who was alive last check
        self._notify_callback: Optional[callable] = None
    
    def set_notify_callback(self, callback):
        """Set callback for death notifications"""
        self._notify_callback = callback
    
    def _load(self) -> dict:
        try:
            if DEATHS_FILE.exists():
                data = json.loads(DEATHS_FILE.read_text())
                # Clean old entries (keep last 7 days)
                cutoff = time.time() - (7 * 86400)
                for key in list(data.keys()):
                    data[key] = [d for d in data[key] if d.get("timestamp", 0) >= cutoff]
                return data
        except Exception as e:
            log.warning(f"Could not load death history: {e}")
        return {}
    
    def _save(self):
        try:
            DEATHS_FILE.write_text(json.dumps(self._history, indent=2))
        except Exception as e:
            log.error(f"Could not save death history: {e}")
    
    async def check_team_deaths(self, socket, discord_id: str, server_key: str,
                               map_size: int = 4000):
        """
        Check for new deaths in team.
        
        Args:
            socket: Active RustSocket
            discord_id: Discord user ID
            server_key: Server identifier (ip:port)
            map_size: Current map size for grid calculation
        """
        try:
            team = await socket.get_team_info()
            
            if isinstance(team, Exception):
                return
            
            history_key = f"{discord_id}_{server_key}"
            
            # Initialize tracking for this user/server if needed
            if history_key not in self._last_alive_state:
                self._last_alive_state[history_key] = {}
            
            if history_key not in self._history:
                self._history[history_key] = []
            
            current_state = self._last_alive_state[history_key]
            
            # Check each team member
            for member in team.members:
                steam_id = str(member.steam_id)
                is_alive = member.is_alive
                
                # First time seeing this player or they were alive before
                if steam_id not in current_state:
                    current_state[steam_id] = {
                        "name": member.name,
                        "alive": is_alive,
                        "x": member.x,
                        "y": member.y
                    }
                    continue
                
                # Check if player just died
                was_alive = current_state[steam_id]["alive"]
                
                if was_alive and not is_alive:
                    # Player died - record it
                    grid = coords_to_grid(member.x, member.y, map_size)
                    
                    death_record = {
                        "player_name": member.name,
                        "steam_id": member.steam_id,
                        "timestamp": int(time.time()),
                        "x": round(member.x, 1),
                        "y": round(member.y, 1),
                        "grid": grid,
                        "map_size": map_size
                    }
                    
                    self._history[history_key].append(death_record)
                    self._save()
                    
                    log.info(f"Death recorded: {member.name} at {grid}")
                    
                    # Notify if callback is set
                    if self._notify_callback:
                        await self._notify_callback(death_record, server_key)
                
                # Update state
                current_state[steam_id] = {
                    "name": member.name,
                    "alive": is_alive,
                    "x": member.x,
                    "y": member.y
                }
            
        except Exception as e:
            log.error(f"Error checking team deaths: {e}")
    
    def get_recent_deaths(self, discord_id: str, server_key: str, 
                         count: int = 10) -> List[dict]:
        """Get recent deaths for a user/server"""
        history_key = f"{discord_id}_{server_key}"
        
        if history_key not in self._history:
            return []
        
        # Return most recent deaths
        deaths = self._history[history_key]
        return sorted(deaths, key=lambda d: d["timestamp"], reverse=True)[:count]
    
    def clear_history(self, discord_id: str, server_key: str) -> tuple[bool, str]:
        """Clear death history for a user/server"""
        history_key = f"{discord_id}_{server_key}"
        
        if history_key not in self._history:
            return False, "No death history found."
        
        count = len(self._history[history_key])
        del self._history[history_key]
        self._save()
        
        return True, f"Cleared {count} death record(s)."


# Module-level singleton
death_tracker = DeathTracker()


def format_death_embed(death_record: dict, server_name: str = None) -> discord.Embed:
    """Format death record as Discord embed"""
    embed = discord.Embed(
        title=f"[X] {death_record['player_name']} died",
        description=f"**Location:** Grid **{death_record['grid']}**",
        color=0xFF0000,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="Coordinates",
        value=f"X: `{death_record['x']}`\nY: `{death_record['y']}`",
        inline=True
    )
    
    embed.add_field(
        name="Map Info",
        value=f"Size: {death_record['map_size']}",
        inline=True
    )
    
    if server_name:
        embed.set_footer(text=f"Server: {server_name}")
    
    return embed


def format_death_history_embed(deaths: List[dict], 
                               server_name: str = None) -> discord.Embed:
    """Format death history as Discord embed"""
    if not deaths:
        return discord.Embed(
            title="Death History",
            description="No deaths recorded yet.",
            color=0xCE422B
        )
    
    embed = discord.Embed(
        title=f"Recent Deaths ({len(deaths)})",
        color=0xCE422B,
        timestamp=discord.utils.utcnow()
    )
    
    lines = []
    for death in deaths[:10]:  # Show last 10
        # Format timestamp
        time_ago = int(time.time() - death["timestamp"])
        if time_ago < 60:
            time_str = f"{time_ago}s ago"
        elif time_ago < 3600:
            time_str = f"{time_ago // 60}m ago"
        else:
            time_str = f"{time_ago // 3600}h ago"
        
        lines.append(
            f"**{death['player_name']}** died at **{death['grid']}** - {time_str}"
        )
    
    embed.description = "\n".join(lines)
    
    if server_name:
        embed.set_footer(text=f"Server: {server_name}")
    
    return embed
