"""
auto_pairing.py
────────────────────────────────────────────────────────────────────────────
Automatic Entity ID Capture System

Listens for FCM pairing notifications and automatically captures entity IDs
when you pair devices in-game. No need to manually enter entity IDs!

How it works:
1. You pair a storage/smart switch in-game (ESC -> Rust+ -> Pair)
2. Bot automatically captures the entity ID from the pairing notification
3. Bot asks you what to name it via Discord DM
4. Entity is added to your monitors automatically

This is exactly how the Rust+ mobile app does it!
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict
import discord

log = logging.getLogger("AutoPairing")


class AutoPairingManager:
    """
    Manages automatic entity pairing from in-game FCM notifications.
    
    When you pair a device in-game, the FCM notification contains:
    - Entity ID
    - Entity Type (storage, switch, alarm, etc.)
    - Server info
    
    This manager captures that and prompts user to name the device.
    """
    
    def __init__(self):
        self._pending_pairs: Dict[str, dict] = {}  # discord_id -> pairing data
        self._pairing_callbacks: Dict[str, Callable] = {}  # entity_type -> callback
        self._user_manager = None
        self._bot = None
    
    def set_dependencies(self, user_manager, bot):
        """Set required dependencies"""
        self._user_manager = user_manager
        self._bot = bot
    
    def register_entity_handler(self, entity_type: str, callback: Callable):
        """
        Register a callback for handling specific entity types.
        
        Args:
            entity_type: Type of entity (e.g., "2" for storage, "1" for switch)
            callback: async function(discord_id, server_key, name, entity_id)
        """
        self._pairing_callbacks[entity_type] = callback
    
    async def handle_pairing_notification(self, discord_id: str, notification_data: dict):
        """
        Process a pairing notification from FCM.
        
        Args:
            discord_id: Discord user ID
            notification_data: Parsed FCM notification body
        """
        try:
            # Extract pairing data
            entity_type = notification_data.get("type", "")
            entity_id = int(notification_data.get("entityId", 0))
            entity_name = notification_data.get("entityName", "Unknown")
            
            # Server info
            ip = notification_data.get("ip", "")
            port = notification_data.get("port", "28017")
            server_name = notification_data.get("name", ip)
            
            if not entity_id or not ip:
                log.warning(f"Incomplete pairing data: {notification_data}")
                return
            
            server_key = f"{ip}:{port}"
            
            log.info(
                f"[Auto-Pair] User {discord_id} paired {entity_name} "
                f"(ID: {entity_id}, Type: {entity_type}) on {server_name}"
            )
            
            # Store pending pairing
            self._pending_pairs[discord_id] = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "server_key": server_key,
                "server_name": server_name,
                "ip": ip,
                "port": port
            }
            
            # Send DM to user asking for name
            await self._prompt_user_for_name(discord_id)
            
        except Exception as e:
            log.error(f"Error handling pairing notification: {e}", exc_info=True)
    
    async def _prompt_user_for_name(self, discord_id: str):
        """Send DM to user asking them to name the paired device"""
        if not self._bot or not self._user_manager:
            return
        
        user = self._user_manager.get_user(discord_id)
        if not user:
            return
        
        pairing = self._pending_pairs.get(discord_id)
        if not pairing:
            return
        
        try:
            # Get Discord user object
            discord_user = await self._bot.fetch_user(int(discord_id))
            
            # Determine entity type name
            entity_type_names = {
                "1": "Smart Switch",
                "2": "Storage Container",
                "3": "Smart Alarm",
                "4": "RF Broadcaster",
                "5": "Storage Monitor"
            }
            
            type_name = entity_type_names.get(
                pairing["entity_type"], 
                f"Device (type {pairing['entity_type']})"
            )
            
            embed = discord.Embed(
                title="[+] New Device Paired!",
                description=(
                    f"You just paired a **{type_name}** on "
                    f"**{pairing['server_name']}**\n\n"
                    f"Entity ID: `{pairing['entity_id']}`\n"
                    f"In-game name: `{pairing['entity_name']}`"
                ),
                color=0x00FF00
            )
            
            embed.add_field(
                name="What would you like to name it?",
                value=(
                    "Reply to this DM with a name (e.g., `main_loot` or `front_gate`)\n\n"
                    "Or reply with `skip` to ignore this pairing."
                ),
                inline=False
            )
            
            embed.set_footer(text="Reply within 5 minutes")
            
            await discord_user.send(embed=embed)
            log.info(f"Sent pairing prompt to user {user['discord_name']}")
            
        except discord.Forbidden:
            log.warning(f"Cannot send DM to user {discord_id} - DMs disabled")
        except Exception as e:
            log.error(f"Error sending pairing prompt: {e}")
    
    async def process_user_response(self, discord_id: str, name: str) -> tuple[bool, str]:
        """
        Process user's response to naming prompt.
        
        Args:
            discord_id: Discord user ID
            name: Name user wants to give the device
            
        Returns:
            (success, message)
        """
        if discord_id not in self._pending_pairs:
            return False, "No pending pairing found. The pairing may have expired."
        
        pairing = self._pending_pairs[discord_id]
        
        # Check if user wants to skip
        if name.lower() == "skip":
            del self._pending_pairs[discord_id]
            return True, "Pairing skipped."
        
        # Validate name
        if not name or len(name) > 50:
            return False, "Name must be 1-50 characters."
        
        # Check for invalid characters
        if not name.replace("_", "").replace("-", "").isalnum():
            return False, "Name can only contain letters, numbers, underscores, and hyphens."
        
        # Find appropriate callback based on entity type
        entity_type = pairing["entity_type"]
        
        # Map entity types to handlers
        # Type 2 = Storage containers
        # Type 1 = Smart switches
        # Type 3 = Smart alarms
        
        try:
            if entity_type == "2":
                # Storage container
                from storage_monitor import storage_manager
                success, message = storage_manager.add_monitor(
                    discord_id,
                    pairing["server_key"],
                    name,
                    pairing["entity_id"]
                )
            elif entity_type == "1":
                # Smart switch
                from commands import _switches, _save_switches
                full_key = f"{discord_id}_{pairing['server_key']}_{name}"
                _switches[full_key] = pairing["entity_id"]
                _save_switches(_switches)
                success = True
                message = f"Smart switch **{name}** added with entity ID `{pairing['entity_id']}`"
            else:
                # Unknown type - store as generic
                success = False
                message = (
                    f"Entity type `{entity_type}` not supported yet.\n"
                    f"Entity ID: `{pairing['entity_id']}` - You can add it manually."
                )
            
            # Clean up pending pairing
            del self._pending_pairs[discord_id]
            
            if success:
                message += (
                    f"\n\n**Server:** {pairing['server_name']}\n"
                    f"**Entity ID:** `{pairing['entity_id']}`"
                )
            
            return success, message
            
        except Exception as e:
            log.error(f"Error processing pairing: {e}", exc_info=True)
            return False, f"Error adding device: {str(e)[:100]}"
    
    def has_pending_pairing(self, discord_id: str) -> bool:
        """Check if user has a pending pairing"""
        return discord_id in self._pending_pairs
    
    def get_pending_pairing(self, discord_id: str) -> Optional[dict]:
        """Get pending pairing data for user"""
        return self._pending_pairs.get(discord_id)
    
    def clear_pending(self, discord_id: str):
        """Clear pending pairing for user"""
        if discord_id in self._pending_pairs:
            del self._pending_pairs[discord_id]


# Module-level singleton
auto_pairing_manager = AutoPairingManager()


def parse_fcm_notification(data_message: dict) -> Optional[dict]:
    """
    Parse FCM notification to extract pairing data.
    
    FCM notifications have structure:
    {
        "channelId": "pairing",
        "body": "{json_string}",
        ...
    }
    
    The body contains:
    {
        "type": "entity" or "server",
        "entityId": 12345678,
        "entityType": "2",  (1=switch, 2=storage, etc.)
        "entityName": "Storage Box",
        "ip": "...",
        "port": "28017",
        "name": "Server Name"
    }
    """
    try:
        # Check if this is a pairing notification
        if data_message.get("channelId") != "pairing":
            return None
        
        # Parse the body JSON
        body_str = data_message.get("body", "{}")
        body = json.loads(body_str)
        
        # Check if this is an entity pairing (not server pairing)
        if body.get("type") == "entity":
            return body
        
        return None
        
    except json.JSONDecodeError:
        log.warning(f"Could not parse FCM body: {data_message.get('body')}")
        return None
    except Exception as e:
        log.error(f"Error parsing FCM notification: {e}")
        return None
