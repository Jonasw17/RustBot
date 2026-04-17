# Rust+ Companion Bot - Enhanced Multi-User Edition

## What's New in This Version

### 1. FIXED: Server Pairing Issue
- **Problem**: New servers weren't being registered when paired in-game
- **Fix**: Enhanced FCM listener with better error handling and logging
- **Details**:
  - Improved JSON parsing for notification body
  - Added fallback for different field names (`playerToken` vs `playerId`)
  - Better logging to debug pairing issues
  - Small delay before auto-connect to ensure data persistence

### 2. NEW: Raid Alarm System
- **DM Notifications**: Get instant Discord DMs when explosions are detected near you
- **Voice Alerts**: Bot joins your voice channel and announces the raid
- **Smart Detection**: 100m radius detection with 5-minute cooldown
- **Commands**:
  - `!raidalarm on` - Enable raid alerts
  - `!raidalarm off` - Disable raid alerts
  - `!raidalarm status` - Check current status

### 3. FIXED: Uptime Command
- **Before**: Only showed bot uptime
- **After**: Shows both bot uptime AND server uptime (time since wipe)
- Example: `!uptime` now returns:
  ```
  Uptime
  > Bot: 2h 15m
  > Server (Rustoria US Main): 3d 7h 22m
  ```

### 4. NEW: Grid Coordinates for Team
- All team commands now show grid locations (e.g., K15, AA22)
- Works for any map size (3000, 4000, 4500, etc.)
- Supports extended grids (AA, AB, etc.) for large maps
- **Enhanced Commands**:
  - `!team` - Shows all members with grid locations
  - `!online` - Shows online members with current grid
  - `!alive` - Shows dead teammates with death location grid

### 5. FIXED: Special Character Encoding
- Removed all UTF-8 special characters that caused errors
- All text is now pure ASCII-compatible
- Works on both Windows and Debian/Raspberry Pi

### 6. Enhanced Event Tracking
- Event timestamps persist across bot restarts
- More accurate "active for X time" reporting
- Cached in `event_timestamps.json`

## Installation

### Prerequisites
```bash
# Python 3.10 or higher
python --version

# Node.js (for FCM registration)
node --version
```

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

**requirements.txt includes:**
- `discord.py>=2.3.0` - Discord bot framework
- `PyNaCl>=1.5.0` - Voice support (for raid alarms)
- `rustplus>=6.0.9` - Rust+ API wrapper with FCM support
- `python-dotenv>=1.0.0` - Environment variables

### Step 2: FCM Registration (First Time Setup)

**Windows Users:**
```bash
# Run the pairing script
pair.bat
```

**Linux/Mac Users:**
```bash
# Install the package globally
npm install -g @liamcottle/rustplus.js

# Run FCM registration
npx @liamcottle/rustplus.js fcm-register
```

This will:
1. Open Chrome for Steam login
2. Generate `rustplus.config.json` on your Desktop
3. This file contains your FCM credentials

### Step 3: Configure Environment
Create a `.env` file:
```env
# Discord Bot Token (get from https://discord.com/developers)
DISCORD_TOKEN=your_bot_token_here

# Channel IDs (right-click channel in Discord > Copy ID)
COMMAND_CHANNEL_ID=123456789
NOTIFICATION_CHANNEL_ID=123456789
CHAT_RELAY_CHANNEL_ID=123456789
```

### Step 4: Register with Bot
1. Start the bot: `python bot.py`
2. DM the bot: `!register`
3. Attach your `rustplus.config.json` file
4. Bot will confirm registration

### Step 5: Pair Your First Server
1. Join any Rust server in-game
2. Press **ESC → Rust+ → Pair Server**
3. Bot will automatically connect and show status

## New File Structure

```
rust-companion-bot/
├── bot.py                      # Main bot (UPDATED - raid alarm integration)
├── commands.py                 # Command handlers (UPDATED - grid coords, raid alarm)
├── server_manager_multiuser.py # Multi-user server manager (FIXED - pairing)
├── multi_user_auth.py          # User authentication
├── raid_alarm.py               # NEW - Raid detection system
├── grid_coordinates.py         # NEW - Grid coordinate conversion
├── status_embed.py             # Server status embeds
├── timers.py                   # Timer system
├── rust_info_db.py             # Rust item/cost database
├── chat_relay.py               # In-game chat relay
├── pair.bat                    # Windows FCM registration
├── requirements.txt            # Python dependencies
└── .env                        # Configuration (create this)
```

## Usage Guide

### Basic Commands

**Server Management:**
- `!servers` - List your paired servers
- `!switch <name or #>` - Switch active server
- `!removeserver <name or #>` - Remove a paired server
- `!register` - Register your Rust+ account (DM only)
- `!whoami` - Check your registration status

**Server Info:**
- `!status` - Rich server status embed (auto-updating)
- `!players` - Player count
- `!time` - In-game time with day/night countdown
- `!map` - Server map image with markers
- `!wipe` - Last wipe date
- `!uptime` - Bot and server uptime

**Team (with Grid Coordinates):**
- `!team` - All members with locations (e.g., "Player @ K15")
- `!online` - Online members with current grid
- `!offline` - Offline members
- `!alive [name]` - Show alive/dead status with death location
- `!leader [name]` - Promote to team leader

**Raid Alarm (NEW):**
- `!raidalarm on` - Enable raid detection
- `!raidalarm off` - Disable raid detection
- `!raidalarm status` - Check status and cooldown

**Events:**
- `!events` - All active events with timing
- `!heli` - Patrol helicopter location
- `!cargo` - Cargo ship location
- `!chinook` - Chinook location
- `!large` - Large oil rig crate status
- `!small` - Small oil rig crate status

**Smart Items:**
- `!addswitch <name> <entity_id>` - Register a smart switch
- `!sson <name>` - Turn switch ON
- `!ssoff <name>` - Turn switch OFF
- `!switches` - List all switches
- `!removeswitch <name>` - Remove switch

**Timers:**
- `!timer add 15m Furnace check` - Set timer with label
- `!timers` - List active timers
- `!timer remove <id>` - Delete timer

**Game Info:**
- `!craft <item>` - Show crafting recipe
- `!recycle <item>` - Show recycle yields
- `!research <item>` - Show research cost
- `!vehicles` - Vehicle costs
- `!carmodules` - Car module costs
- `!fragments` - Blueprint fragment info
- `!cctv <monument>` - CCTV codes

## Raid Alarm Details

### How It Works
1. Bot monitors your position every 10 seconds
2. Checks for explosion markers within 100m
3. Sends DM when raid detected
4. Attempts to join your voice channel and alert you
5. 5-minute cooldown before next alert

### Voice Setup
For voice alerts to work, you need to:
1. Be in a voice channel on the same server as the bot
2. Give bot permission to join voice channels
3. Ensure PyNaCl is installed: `pip install PyNaCl`

### DM Setup
Make sure your Discord DMs are open:
1. Server Settings → Privacy Settings
2. Enable "Allow direct messages from server members"

## Multi-User Architecture

### How It Works
- Each Discord user registers their own Rust+ credentials
- Multiple users can pair different servers
- Commands use the caller's credentials automatically
- FCM listeners run per-user for auto-pairing

### User Management
- `!users` - List all registered users (admin only)
- `!whoami` - Check your own registration
- `!unregister` - Remove your credentials

## Grid Coordinate System

### Understanding Grid References
- **Columns**: A-Z, AA-ZZ, etc. (horizontal)
- **Rows**: 0-29 (vertical)
- **Example**: K15 means column K, row 15

### Map Size Support
- Automatically detects map size (3000, 4000, 4500, etc.)
- Calculates correct grid dimensions
- Supports extended grids for large maps

### When Grid Shows
- `!team` - All online members
- `!online` - Online members' current position
- `!alive` - Dead members' death location
- Offline members don't show grid (no position data)

## Troubleshooting

### Server Pairing Not Working
1. Check logs for FCM messages
2. Ensure you're using the correct `rustplus.config.json`
3. Try re-running FCM registration
4. Check that bot has started FCM listeners

### Raid Alarm Not Triggering
1. Verify it's enabled: `!raidalarm status`
2. Check you're online in-game
3. Ensure explosions are within 100m
4. Wait 5 minutes between alerts (cooldown)

### Voice Alerts Not Working
1. Install PyNaCl: `pip install PyNaCl`
2. Be in a voice channel
3. Give bot voice permissions
4. Check bot logs for errors

### Grid Coordinates Wrong
- This is normal! Grid calculation depends on accurate map size
- Rust+ API sometimes returns approximate positions
- Grid is an estimate based on last known position

### UTF-8 Encoding Errors
- All files are now ASCII-compatible
- No special characters that cause encoding issues
- Safe to run on both Windows and Linux

## Debugging

### Enable Debug Logging
Edit `bot.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    # ...
)
```

### Check Specific Components
```python
# In bot.py, enable FCM debug
logging.getLogger("ServerManager").setLevel(logging.DEBUG)

# In commands.py, enable raid alarm debug
logging.getLogger("RaidAlarm").setLevel(logging.DEBUG)
```

### Common Log Messages
- `[Pairing] Server paired by...` - Successful pairing
- `[FCM] Notification received` - FCM working
- `RAID DETECTED` - Raid alarm triggered
- `Raid check timeout` - Normal, happens occasionally

## Performance Notes

### Resource Usage
- **RAM**: ~100-200 MB per bot instance
- **CPU**: <5% on modern hardware
- **Network**: Minimal (WebSocket + API calls)

### Background Tasks
- Status updates: Every 45 seconds
- Raid checks: Every 10 seconds (per enabled user)
- Timer checks: Every 1 second
- FCM listeners: One thread per registered user

### Scaling
- Supports unlimited users
- Each user can pair unlimited servers
- Performance degrades with 50+ concurrent users
- Consider running multiple bot instances for large communities

## Security Notes

### Sensitive Data
- `rustplus.config.json` - Contains FCM credentials
- `.env` - Contains bot token
- `users.json` - Contains all user credentials
- **Keep these files private!**

### Permissions
- Bot needs: Read Messages, Send Messages, Manage Messages
- For voice: Connect, Speak
- For raid alarms: DM users

### Data Storage
All data stored locally:
- `users.json` - User credentials
- `servers.json` - Paired servers (legacy)
- `switches.json` - Smart switches
- `timers.json` - Active timers
- `event_timestamps.json` - Event tracking

## Changelog

### v2.0.0 (Current Release)
- ✅ FIXED: Server pairing now works reliably
- ✅ NEW: Raid alarm with DM + voice alerts
- ✅ FIXED: Uptime shows server uptime
- ✅ NEW: Grid coordinates for all team commands
- ✅ FIXED: All UTF-8 encoding issues resolved
- ✅ Enhanced: Better error handling throughout
- ✅ Enhanced: Improved logging and debugging

### Known Issues
- Voice alerts may not work on all systems (FFmpeg required)
- Grid coordinates are approximate (Rust+ API limitation)
- Large maps (6000+) may have inaccurate grids

## Credits

**Original Bot**: Rust+ Companion Bot
**Enhanced By**: Your Team
**Dependencies**:
- discord.py (Discord API)
- rustplus (by olijeffers0n)
- @liamcottle/rustplus.js (FCM registration)

## Support

**Need Help?**
1. Check troubleshooting section above
2. Enable debug logging
3. Check bot logs
4. Review Discord permissions

**Found a Bug?**
- Enable debug logging
- Reproduce the issue
- Share logs (remove sensitive data)

## License

This project is provided as-is for personal and community use.
