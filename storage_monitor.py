"""
storage_monitor.py
────────────────────────────────────────────────────────────────────────────
Storage Monitor System - Track storage containers in Rust+

Features:
- Add storage monitors with custom names
- View current storage contents
- Auto-notification when storage changes
- Per-user, per-server storage tracking
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
import discord
from rustplus import RustError

log = logging.getLogger("StorageMonitor")

STORAGE_FILE = Path("storage_monitors.json")


class StorageMonitorManager:
    """
    Manages storage monitors for multiple users across servers.
    
    Storage format:
    {
      "discord_id_ip:port_name": {
        "entity_id": 12345,
        "name": "main_loot",
        "last_items": [...],
        "discord_id": "123456789",
        "server_key": "ip:port"
      }
    }
    """
    
    def __init__(self):
        self._monitors: Dict = self._load()
        self._notify_callback: Optional[callable] = None
    
    def set_notify_callback(self, callback):
        """Set callback for storage change notifications"""
        self._notify_callback = callback
    
    def _load(self) -> dict:
        try:
            if STORAGE_FILE.exists():
                return json.loads(STORAGE_FILE.read_text())
        except Exception as e:
            log.warning(f"Could not load storage monitors: {e}")
        return {}
    
    def _save(self):
        try:
            STORAGE_FILE.write_text(json.dumps(self._monitors, indent=2))
        except Exception as e:
            log.error(f"Could not save storage monitors: {e}")
    
    def add_monitor(self, discord_id: str, server_key: str, name: str, 
                   entity_id: int) -> tuple[bool, str]:
        """
        Add a storage monitor.
        
        Args:
            discord_id: Discord user ID
            server_key: Server identifier (ip:port)
            name: Custom name for this storage
            entity_id: Rust+ entity ID
            
        Returns:
            (success, message)
        """
        full_key = f"{discord_id}_{server_key}_{name}"
        
        if full_key in self._monitors:
            return False, f"Storage monitor `{name}` already exists. Use a different name."
        
        self._monitors[full_key] = {
            "entity_id": entity_id,
            "name": name,
            "last_items": [],
            "discord_id": discord_id,
            "server_key": server_key
        }
        self._save()
        
        log.info(f"Added storage monitor: {name} (entity {entity_id}) for user {discord_id}")
        return True, f"Storage monitor **{name}** added with entity ID `{entity_id}`"
    
    def remove_monitor(self, discord_id: str, server_key: str, 
                      name: str) -> tuple[bool, str]:
        """Remove a storage monitor"""
        full_key = f"{discord_id}_{server_key}_{name}"
        
        if full_key not in self._monitors:
            return False, f"Storage monitor `{name}` not found."
        
        del self._monitors[full_key]
        self._save()
        
        log.info(f"Removed storage monitor: {name} for user {discord_id}")
        return True, f"Storage monitor **{name}** removed"
    
    def get_monitors_for_user(self, discord_id: str, 
                             server_key: str = None) -> List[dict]:
        """Get all storage monitors for a user (optionally filtered by server)"""
        monitors = []
        
        for full_key, data in self._monitors.items():
            if not full_key.startswith(f"{discord_id}_"):
                continue
            
            if server_key and data["server_key"] != server_key:
                continue
            
            monitors.append(data)
        
        return monitors
    
    async def check_storage(self, socket, discord_id: str, server_key: str, 
                          name: str) -> tuple[bool, str | dict]:
        """
        Check current contents of a storage monitor.
        
        Returns:
            (success, data)
            data is either error message (str) or storage info (dict)
        """
        full_key = f"{discord_id}_{server_key}_{name}"
        
        if full_key not in self._monitors:
            return False, f"Storage monitor `{name}` not found."
        
        monitor = self._monitors[full_key]
        entity_id = monitor["entity_id"]
        
        try:
            # Get storage contents from Rust+ API
            result = await socket.get_entity_info(entity_id)
            
            if isinstance(result, RustError):
                return False, f"Error reading storage: {result.reason}"
            
            # Extract item data
            items = []
            if hasattr(result, 'items') and result.items:
                for item in result.items:
                    items.append({
                        "name": getattr(item, 'name', 'Unknown'),
                        "quantity": getattr(item, 'quantity', 0),
                        "item_id": getattr(item, 'item_id', 0)
                    })
            
            # Update last known state
            monitor["last_items"] = items
            self._save()
            
            return True, {
                "name": name,
                "entity_id": entity_id,
                "items": items,
                "capacity": getattr(result, 'capacity', 0) if hasattr(result, 'capacity') else len(items)
            }
            
        except Exception as e:
            log.error(f"Error checking storage {name}: {e}")
            return False, f"Error: {str(e)[:100]}"
    
    async def check_all_for_user(self, socket, discord_id: str, 
                                server_key: str) -> List[dict]:
        """Check all storage monitors for a user on current server"""
        monitors = self.get_monitors_for_user(discord_id, server_key)
        results = []
        
        for monitor in monitors:
            success, data = await self.check_storage(
                socket, discord_id, server_key, monitor["name"]
            )
            
            if success and isinstance(data, dict):
                results.append(data)
        
        return results


# Module-level singleton
storage_manager = StorageMonitorManager()


def format_storage_embed(storage_data: dict, user_name: str = None) -> discord.Embed:
    """Format storage data as Discord embed"""
    name = storage_data["name"]
    items = storage_data["items"]
    entity_id = storage_data["entity_id"]
    
    embed = discord.Embed(
        title=f"Storage: {name}",
        color=0xCE422B,
        timestamp=discord.utils.utcnow()
    )
    
    if not items:
        embed.description = "Storage is empty"
    else:
        # Group items by name and sum quantities
        item_summary = {}
        for item in items:
            item_name = item["name"]
            qty = item["quantity"]
            
            if item_name in item_summary:
                item_summary[item_name] += qty
            else:
                item_summary[item_name] = qty
        
        # Format item list
        lines = []
        for item_name, qty in sorted(item_summary.items()):
            lines.append(f"**{qty}x** {item_name}")
        
        embed.description = "\n".join(lines)
    
    embed.add_field(
        name="Info",
        value=f"Entity ID: `{entity_id}`\nItems: {len(items)}",
        inline=False
    )
    
    if user_name:
        embed.set_footer(text=f"Monitored by {user_name}")
    
    return embed
