# API Documentation

Internal API documentation for developers working with the Rust+ Discord Bot codebase.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Discord                              │
│                     (User Interface)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                         bot.py                               │
│                   (Main Entry Point)                         │
│  - Event handlers                                            │
│  - Message routing                                           │
│  - Connection management                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      commands.py                             │
│                   (Command Router)                           │
│  - Parse commands                                            │
│  - Call appropriate handlers                                 │
│  - Format responses                                          │
└───┬─────────────────┬──────────────────┬─────────────────┬──┘
    │                 │                  │                 │
    ▼                 ▼                  ▼                 ▼
┌────────┐   ┌──────────────────┐  ┌──────────┐   ┌──────────┐
│Timers  │   │  Server Manager  │  │User Auth │   │ Status   │
│System  │   │  (Multi-User)    │  │ Manager  │   │ Embeds   │
└────────┘   └────────┬─────────┘  └──────────┘   └──────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   RustSocket    │
             │ (Rust+ API)     │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │  Rust Server    │
             │  (Game Server)  │
             └─────────────────┘
```

## Core Components

### bot.py
**Purpose:** Main entry point and Discord event handler

**Key Functions:**
- `on_ready()` - Bot initialization
- `on_message()` - Message event handler
- `execute_command_with_retry()` - Command execution with retry logic
- `check_connection_health()` - Connection monitoring
- `update_status_message()` - Status embed updates

**Key Variables:**
```python
DISCORD_TOKEN: str          # Bot token
COMMAND_CHANNEL_ID: int     # Channel for commands
NOTIFICATION_CHANNEL_ID: int # Channel for notifications
CHAT_RELAY_CHANNEL_ID: int  # Channel for chat relay
```

### commands.py
**Purpose:** Command parsing and routing

**Main Router:**
```python
async def handle_query(
    query: str,
    manager: MultiUserServerManager,
    user_manager: UserManager,
    ctx=None,
    discord_id: Optional[str] = None
) -> str | tuple
```

**Command Categories:**
1. **User Management** - Registration, whoami, unregister
2. **Server Management** - List, switch, remove servers
3. **Meta Commands** - Help, clear, timers
4. **Smart Devices** - Add, remove, control switches
5. **Live Commands** - Require active server connection

### server_manager_multiuser.py
**Purpose:** Multi-user server connection management

**Key Class:**
```python
class MultiUserServerManager:
    def __init__(self, user_manager: UserManager)
    
    # Connection Management
    async def connect_for_user(discord_id: str, ip: str, port: str)
    async def ensure_connected_for_user(discord_id: str)
    def get_socket_for_user(discord_id: str) -> Optional[RustSocket]
    
    # Server Management
    async def switch_server_for_user(discord_id: str, identifier: str)
    def list_servers_for_user(discord_id: str) -> list
    def get_active_server_for_user(discord_id: str) -> Optional[dict]
    
    # FCM Pairing
    async def start_fcm_listener_for_user(discord_id: str, callback)
    async def start_all_fcm_listeners(callback)
```

**Internal State:**
```python
_active_sockets: Dict[str, RustSocket]  # discord_id -> socket
_active_servers: Dict[str, dict]        # discord_id -> server_info
_chat_callbacks: list[Callable]
_registered_chat_keys: set
_fcm_listeners: Dict[str, Thread]       # discord_id -> listener_thread
```

### multi_user_auth.py
**Purpose:** User credential and server management

**Key Class:**
```python
class UserManager:
    def __init__(self)
    
    # User Management
    def add_user(discord_id: str, discord_name: str, 
                 steam_id: int, fcm_creds: dict) -> bool
    def get_user(discord_id: str) -> Optional[dict]
    def has_user(discord_id: str) -> bool
    def remove_user(discord_id: str) -> bool
    def list_users() -> list
    
    # Server Management
    def add_user_server(discord_id: str, ip: str, port: str, 
                       name: str, player_token: int)
    def get_user_servers(discord_id: str) -> list
    def remove_user_server(discord_id: str, identifier: str) 
        -> tuple[bool, str]
```

**Data Structure (users.json):**
```json
{
  "discord_user_id": {
    "discord_name": "Username#1234",
    "steam_id": 76561198...,
    "fcm_credentials": {
      "keys": {...},
      "fcm": {...},
      "gcm": {...}
    },
    "paired_servers": {
      "ip:port": {
        "name": "Server Name",
        "player_token": -123456789,
        "ip": "1.2.3.4",
        "port": "28017"
      }
    }
  }
}
```

### status_embed.py
**Purpose:** Generate rich Discord embeds for server status

**Key Functions:**
```python
def _parse_time_to_float(t) -> float
    """Convert time to float (0-24)"""

def _fmt_time_val(t) -> str
    """Format as 12-hour clock"""

def _calculate_time_until_change(now: float, sunrise: float, 
                                  sunset: float) -> tuple[str, str]
    """Calculate time until day/night change"""

async def build_server_status_embed(server: dict, socket, 
                                     user_info: dict) -> discord.Embed
    """Build full status embed"""
```

### timers.py
**Purpose:** Custom timer system with notifications

**Key Class:**
```python
class TimerManager:
    def add(duration_str: str, text: str) -> tuple[bool, str]
    def remove(id_str: str) -> tuple[bool, str]
    def list_timers() -> str
    async def run_loop()  # Background task
    def set_notify_callback(cb: Callable)
```

**Data Structure (timers.json):**
```json
{
  "timers": {
    "1": {
      "label": "15m",
      "expires_at": 1234567890.123,
      "text": "Furnace check"
    }
  },
  "next_id": 2
}
```

## Rust+ API Integration

### RustSocket Wrapper
The bot uses the `rustplus` Python library which wraps the Rust+ Companion API.

**Key Methods:**
```python
socket = RustSocket(server_details)
await socket.connect()

# Server Info
info = await socket.get_info()        # Server details
time = await socket.get_time()        # In-game time
team = await socket.get_team_info()   # Team members
markers = await socket.get_markers()  # Events

# Map
map_obj = await socket.get_map(
    add_icons=True,
    add_events=True,
    add_vending_machines=False
)

# Smart Devices
await socket.turn_on_smart_switch(entity_id)
await socket.turn_off_smart_switch(entity_id)

# Team
await socket.promote_to_team_leader(steam_id)
await socket.send_team_message(text)
```

### Server Details
```python
from rustplus import ServerDetails

server_details = ServerDetails(
    ip="1.2.3.4",
    port="28017",
    steam_id=76561198...,
    player_token=-123456789
)
```

### Chat Events
```python
from rustplus import ChatEvent, ChatEventPayload

@ChatEvent(server_details)
async def on_chat(event: ChatEventPayload):
    msg = event.message
    print(f"[{msg.name}] {msg.message}")
```

## Data Flow Examples

### User Registration Flow
```
1. User runs pair.bat/pair.sh
   └─> Generates rustplus.config.json

2. User DMs bot: !register + file
   └─> Bot reads attachment
       └─> Extracts Steam ID and FCM credentials
           └─> Stores in users.json

3. User pairs server in-game
   └─> FCM notification sent
       └─> Bot receives pairing data
           └─> Adds server to user's paired_servers
               └─> Auto-connects to server
```

### Command Execution Flow
```
1. User sends: !status

2. bot.py on_message()
   └─> Checks channel/permissions
       └─> Extracts command and args

3. commands.handle_query()
   └─> Routes to _cmd_status()
       └─> Calls manager.get_socket_for_user()
           └─> Gets RustSocket for user
               └─> Calls socket.get_info()
                   └─> Calls socket.get_time()
                       └─> Builds status embed
                           └─> Returns to bot
                               └─> Sends to Discord
```

### Server Switching Flow
```
1. User: !switch rustoria

2. cmd_change_server()
   └─> manager.switch_server_for_user()
       └─> Find server by name/index
           └─> Disconnect old socket (if exists)
               └─> connect_for_user()
                   └─> Create new ServerDetails
                       └─> Create new RustSocket
                           └─> await socket.connect()
                               └─> Register ChatEvent
                                   └─> Update active connection
```

## Time Calculation

### Rust Time Mechanics
- 24 in-game hours = 60 real minutes
- 1 in-game hour = 2.5 real minutes
- 1 in-game minute = 2.5 real seconds

### Calculation Function
```python
def _calculate_time_until_change(now_ig: float, sunrise: float, 
                                  sunset: float) -> tuple[str, str]:
    """
    Args:
        now_ig: Current in-game time (0-24)
        sunrise: Sunrise time (e.g., 6.5 = 6:30 AM)
        sunset: Sunset time (e.g., 18.5 = 6:30 PM)
    
    Returns:
        (phase_indicator, time_message)
    """
    is_day = sunrise <= now_ig < sunset
    
    if is_day:
        # Time until sunset
        diff_h = (sunset - now_ig) % 24
        real_mins = int(diff_h * 2.5)
        return "[Day]", f"Night in {real_mins}m"
    else:
        # Time until sunrise (handles midnight wrap)
        diff_h = (sunrise - now_ig) % 24
        real_mins = int(diff_h * 2.5)
        return "[Night]", f"Day in {real_mins}m"
```

## Error Handling

### Connection Retry Logic
```python
async def execute_command_with_retry(discord_id: str, query: str, 
                                     ctx, max_retries=2):
    for attempt in range(max_retries):
        try:
            response = await handle_query(...)
            _connection_health["last_successful_command"][discord_id] = time.time()
            return response
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await check_connection_health(discord_id)
                await asyncio.sleep(2)
            else:
                return "[!] Command timed out"
        except Exception as e:
            if attempt < max_retries - 1:
                await manager.ensure_connected_for_user(discord_id)
            else:
                return f"[!] Command failed: {e}"
```

### Health Monitoring
```python
_connection_health = {
    "last_successful_command": {},  # discord_id -> timestamp
    "reconnect_attempts": {},        # discord_id -> count
    "max_reconnect_attempts": 3
}

async def check_connection_health(discord_id: str) -> bool:
    try:
        info = await asyncio.wait_for(socket.get_info(), timeout=10.0)
        # Success - reset counters
        _connection_health["last_successful_command"][discord_id] = time.time()
        _connection_health["reconnect_attempts"][discord_id] = 0
        return True
    except:
        # Check if we should reconnect
        time_since_success = time.time() - last_success
        if time_since_success > 300:  # 5 minutes
            await manager.ensure_connected_for_user(discord_id)
```

## FCM Listener

### How It Works
1. User registers with FCM credentials
2. Bot starts background thread with FCMListener
3. When user pairs server in-game:
   - Rust+ sends push notification
   - FCM listener catches it
   - Extracts server info (IP, port, player_token)
   - Adds to user's paired servers
   - Auto-connects to server

### Implementation
```python
class UserPairingListener(FCMListener):
    def on_notification(self, obj, notification, data_message):
        data = data_message or {}
        
        if data.get("channelId") != "pairing":
            return  # Not a pairing notification
        
        body = json.loads(data.get("body", "{}"))
        
        if body.get("type") != "server":
            return  # Not a server pairing
        
        # Extract server details
        ip = body.get("ip")
        port = body.get("port", "28017")
        name = body.get("name", ip)
        player_token = int(body.get("playerToken"))
        
        # Add to user's account
        user_manager.add_user_server(
            discord_id, ip, port, name, player_token
        )
        
        # Auto-connect
        asyncio.run_coroutine_threadsafe(
            manager.connect_for_user(discord_id, ip, port),
            loop
        )
```

## Smart Device Management

### Registration
```python
# Data structure (switches.json)
{
  "discord_id_ip:port_name": entity_id,
  "12345_1.2.3.4:28017_maingate": 87654321
}
```

### Key Separation
- Each switch is keyed by: `{discord_id}_{server_key}_{name}`
- This ensures:
  - Switches are per-user
  - Switches are per-server
  - Names can overlap across users/servers

### Control Flow
```
1. User: !sson maingate

2. Look up: discord_id_server_key_maingate
   └─> Get entity_id

3. Get user's active socket

4. socket.turn_on_smart_switch(entity_id)
   └─> Rust+ API call
       └─> Device toggles in-game
```

## Background Tasks

### Status Update Loop
```python
async def server_status_loop():
    """Update status embeds every 45 seconds"""
    while not bot.is_closed():
        for discord_id in list(_status_messages.keys()):
            socket = manager.get_socket_for_user(discord_id)
            if socket:
                await update_status_message(discord_id)
        await asyncio.sleep(45)
```

### Timer Loop
```python
async def run_loop():
    """Check timers every second"""
    while True:
        now = time.time()
        fired = [tid for tid, t in self._timers.items()
                 if t["expires_at"] <= now]
        
        for tid in fired:
            t = self._timers.pop(tid)
            self._save()
            if self._notify_cb:
                await self._notify_cb(t["label"], t["text"])
        
        await asyncio.sleep(1)
```

## File Structure

### Configuration Files
- `.env` - Bot configuration (not tracked)
- `requirements.txt` - Python dependencies
- `rustplus.config.json` - FCM credentials (per-user)

### Data Files (Auto-generated)
- `users.json` - User accounts and paired servers
- `timers.json` - Active timers
- `switches.json` - Registered smart devices
- `event_timestamps.json` - Event tracking cache

### Code Files
- `bot.py` - Main entry point
- `commands.py` - Command routing
- `server_manager_multiuser.py` - Connection management
- `multi_user_auth.py` - User management
- `status_embed.py` - Discord embeds
- `timers.py` - Timer system
- `chat_relay.py` - Chat relay (optional)
- `rust_client.py` - API wrapper (legacy)

## Adding New Commands

### Step 1: Create Handler
```python
# In commands.py
async def cmd_new_feature(args: str, socket, server: dict) -> str:
    """Your new command"""
    if not args:
        return "Usage: !newfeature <args>"
    
    # Your logic here
    result = await socket.some_api_call()
    
    return f"Result: {result}"
```

### Step 2: Add to Router
```python
# In handle_query()
if cmd == "newfeature":
    return await cmd_new_feature(args, socket, active)
```

### Step 3: Update Help
```python
# In cmd_help()
"**New Category:**\n"
"`newfeature <args>` - Description\n\n"
```

## Testing

### Manual Testing Checklist
- [ ] User registration works
- [ ] Server pairing detected
- [ ] Commands execute without errors
- [ ] Time calculations correct
- [ ] Smart devices controllable
- [ ] Timers fire correctly
- [ ] Error handling works
- [ ] Multi-user isolation works

### Debug Mode
```python
# In bot.py
logging.basicConfig(level=logging.DEBUG)

# Verbose output
log.debug(f"Socket state: {socket}")
log.debug(f"User data: {user}")
```

## Performance Considerations

### Rate Limiting
- Rust+ API has rate limits
- Bot implements retry logic
- Avoid rapid successive calls

### Memory Management
- Clean up disconnected sockets
- Limit cache sizes
- Periodic restarts recommended

### Concurrency
- Use asyncio for I/O operations
- Don't block the event loop
- FCM listeners in separate threads

## Security Best Practices

1. **Never commit:**
   - `.env` files
   - `users.json`
   - `rustplus.config.json`

2. **Validate input:**
   - Sanitize user commands
   - Validate Discord IDs
   - Check entity IDs

3. **Limit permissions:**
   - Bot needs minimal Discord perms
   - Don't run as root/admin
   - Use environment variables

4. **Protect data:**
   - Encrypt sensitive files
   - Regular backups
   - Secure file permissions

## Contributing Guidelines

1. Follow existing code style
2. Add docstrings to functions
3. Handle errors gracefully
4. Test thoroughly
5. Update documentation
6. Submit PRs with clear descriptions

## API Reference Quick Links

- [discord.py docs](https://discordpy.readthedocs.io/)
- [rustplus.py GitHub](https://github.com/olijeffers0n/rustplus)
- [Rust+ API unofficial docs](https://github.com/liamcottle/rustplus.js)
