# Rust+ Companion Discord Bot

A powerful multi-user Discord bot for managing Rust servers via the Rust+ Companion API. Monitor server status, team members, in-game events, and control smart devices—all from Discord!

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [User Registration](#user-registration)
- [Command Reference](#command-reference)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)
- [Security](#security)
- [Support](#support)
- [Credits](#credits)
- [Version History](#version-history)
- 

## Features

### Multi-User Support
- Multiple Discord users can register their own Rust+ credentials
- Each user maintains their own paired servers
- Automatic server pairing via FCM notifications
- Per-user connection management

### Server Monitoring
- Real-time server status (players, time, map info)
- Live day/night cycle tracking with accurate countdown
- Wipe date tracking
- Automatic status updates every 45 seconds

### Team Management
- View online/offline team members
- Check alive/dead status
- Team leadership transfer
- Team chat relay to Discord

### In-Game Events
- Patrol Helicopter tracking
- Cargo Ship notifications
- Chinook CH-47 detection
- Locked crate timers (Oil Rigs)
- Event duration tracking

### Smart Device Control
- Register and control smart switches
- Toggle switches on/off from Discord
- Multi-server device management
- Easy device naming system

### Utilities
- Custom timers with notifications
- Map image generation
- Server information lookup
- Rust crafting/research/recycle info (!DISCLAIMER: This data may not reflect the latest few game changes, use with caution, and report any inaccuracies)
- CCTV codes database

## Quick Start
This is needed to get the bot up and running yourself. 
If you know someone who has already set up the bot and just want to add your credentials, you can skip to the [User Registration](#user-registration) section below.

### Prerequisites
- Python 3.8 or higher
- Discord bot token
- Node.js (for FCM registration)

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd rust-bot
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js package for FCM (one-time)**
   ```bash
   npm install -g @liamcottle/rustplus.js
   ```

4. **Configure the bot**
   
   Create a `.env` file:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   COMMAND_CHANNEL_ID=1234567890
   NOTIFICATION_CHANNEL_ID=1234567890
   CHAT_RELAY_CHANNEL_ID=1234567890
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

## User Registration

### Prerequisites
1. Make sure you have your Rust+ app set up so you can pair servers in-game.
2. Make sure you have [node.js](https://nodejs.org/dist/v24.13.1/node-v24.13.1-x64.msi) installed to run the FCM credential generation script. This is a one-time setup process to get your FCM credentials, which are required for the bot to connect to Rust servers on your behalf. Click the link, install node.js, and then run the pairing script as described below.
3. Download the [pairing script](https://github.com/Jonasw17/RustBot/blob/main/pair.bat) from [GitHub Repo](https://github.com/Jonasw17/RustBot) and run it to generate your FCM credentials. This will create a `rustplus.config.json` file on your Desktop, which contains the necessary credentials for the bot to connect to Rust servers using your account.


### Step 1: Generate FCM Credentials

#### **On Windows:**
```bash
pair.bat
```

#### **On Linux/Mac:**
_I haven't personally tested the Linux/Mac pairing script, but if it's set up similarly to the Windows version, you should be able to run it with. Worst case scenario run it on a Windows machine to generate the `rustplus.config.json` file and then transfer that file to your Linux/Mac machine._
```bash
chmod +x pair.sh
./pair.sh
```

This will:
- Open Chrome for Steam login
- Generate `rustplus.config.json` on your Desktop
- Contains your FCM credentials

### Step 2: Register with Bot

1. **DM the bot** (not in a server channel)
2. Send the command: `!register`
3. **Attach** your `rustplus.config.json` file
4. Bot confirms registration with your Steam ID ([steamid64](https://steamid.io/)) 

### Step 3: Pair Servers

1. Join any Rust server in-game
2. Press **ESC** → **Rust+** → **Pair Server**
3. Bot automatically detects and connects!

## Command Reference

### User Management
| Command | Description |
|---------|-------------|
| `!register` | Register your Rust+ account (DM only) |
| `!whoami` | Check your registration status |
| `!unregister` | Remove your credentials from bot |

### Server Management
| Command | Description |
|---------|-------------|
| `!servers` | List all your paired servers |
| `!switch <name/number>` | Switch to a different server |
| `!removeserver <name/number>` | Remove a server from your list |

### Server Information
| Command | Description |
|---------|-------------|
| `!status` | Detailed server status embed |
| `!players` or `!pop` | Current player count |
| `!time` | In-game time with day/night countdown |
| `!map` | Generate map image with markers |
| `!wipe` | Last wipe date and time elapsed |
| `!uptime` | Bot and server uptime |

### Team Commands
| Command | Description |
|---------|-------------|
| `!team` | List all team members |
| `!online` | Show online members |
| `!offline` | Show offline members |
| `!alive [name]` | Check alive/dead status |
| `!leader [name]` | Transfer team leadership* |

*Note: Team leadership can only be transferred by the current team leader

### Event Tracking
| Command | Description |
|---------|-------------|
| `!events` | Show all active events |
| `!heli` | Patrol Helicopter location |
| `!cargo` | Cargo Ship location |
| `!chinook` | Chinook location |
| `!large` | Large Oil Rig crate timer |
| `!small` | Small Oil Rig crate timer |

### Smart Devices
| Command | Description |
|---------|-------------|
| `!smartitems` | List registered devices |
| `!addswitch <name> <entity_id>` | Register smart switch |
| `!removeswitch <name>` | Unregister device |
| `!sson <name>` | Turn switch ON |
| `!ssoff <name>` | Turn switch OFF |
| `!switches` | List all your switches |

### Timers
| Command | Description |
|---------|-------------|
| `!timer add <time> <label>` | Create timer |
| `!timer remove <id>` | Delete timer |
| `!timers` | List active timers |

**Timer Examples:**
- `!timer add 15m Furnace check`
- `!timer add 2h30m Raid defense`
- `!timer add 1h Base upkeep`

### Game Information
| Command | Description |
|---------|-------------|
| `!craft <item>` | Crafting recipe |
| `!recycle <item>` | Recycling output |
| `!research <item>` | Research cost |
| `!decay <item>` | Decay time |
| `!upkeep <item>` | Upkeep cost |
| `!cctv <monument>` | CCTV codes |
| `!vehicles` | Vehicle costs |
| `!carmodules` | Car module costs |
| `!price <item>` | Item price/cost |

### Utilities
| Command | Description |
|---------|-------------|
| `!clear [amount]` | Delete messages (requires permissions) |
| `!help` | Show command list |

## Configuration

### Discord Setup

1. **Create Discord Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create New Application
   - Go to Bot → Add Bot
   - Copy token to `.env` file

2. **Set Bot Permissions**
   Required permissions:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Manage Messages (for `!clear`)

3. **Enable Intents**
   Bot → Privileged Gateway Intents:
   - ✓ Message Content Intent
   - ✓ Server Members Intent (optional)

4. **Invite Bot**
   OAuth2 → URL Generator:
   - Scopes: `bot`
   - Permissions: (use permission calculator)
   - Copy URL and invite to your server

### Channel Configuration

Set these in your `.env` file:

- **COMMAND_CHANNEL_ID**: Where users run commands
- **NOTIFICATION_CHANNEL_ID**: Where bot posts status/events
- **CHAT_RELAY_CHANNEL_ID**: Two-way chat relay with in-game

**How to get Channel IDs:**
1. Enable Developer Mode (Settings → Advanced → Developer Mode)
2. Right-click channel → Copy ID

## Architecture

### Multi-User System
```
User A → Steam ID A → Server X (Token A)
                   → Server Y (Token A)

User B → Steam ID B → Server X (Token B)
                   → Server Z (Token B)
```

Each user has:
- Their own Steam ID
- Their own FCM credentials
- Their own player tokens per server
- Independent server connections

### File Structure
```
rust-bot/
├── bot.py                          # Main bot entry point
├── commands.py                     # Command handlers
├── status_embed.py                 # Server status embeds
├── timers.py                       # Timer system
├── multi_user_auth.py              # User registration
├── server_manager_multiuser.py     # Multi-user server management
├── chat_relay.py                   # In-game chat relay
├── rust_client.py                  # Rust+ API wrapper
├── requirements.txt                # Python dependencies
├── pair.bat / pair.sh              # FCM registration scripts
└── .env                            # Configuration (not tracked)
```

### Data Files (Auto-generated)
- `users.json` - User credentials and paired servers
- `timers.json` - Active timers
- `switches.json` - Registered smart devices
- `event_timestamps.json` - Event tracking cache

## Troubleshooting

### "FCM listener crashed" Error
**Issue:** Error shows `'fcm_credentials'` key missing
**Cause:** User data structure issue during FCM listener startup
**Impact:** None - listener restarts immediately and works fine
**Fix:** This is already handled in the code and can be ignored

### Cannot Promote Self to Leader
**Question:** Can I make myself team leader?
**Answer:** No - Rust+ API only allows the **current team leader** to transfer leadership to another member. This is a Rust+ limitation, not a bot limitation.

**Workaround:** Have your current team leader use the bot:
1. Leader registers with bot
2. Leader runs `!leader <your_name>`

### Connection Issues
```
Error: Could not reach Rust+ server
```
**Solutions:**
1. Verify server has Rust+ enabled
2. Check App Port is not blocked by firewall (might be irrelevant)
3. Ensure you've paired the server in-game
4. Try reconnecting: `!switch <server>`

### Encoding Errors
```
SyntaxError: (unicode error) 'utf-8' codec can't decode
```
**Solution:** Make sure you're using the emoji-free version of all Python files (the `_fixed.py` versions from the deployment package)

### "Not registered" Error
**Cause:** Your Discord account isn't registered with the bot
**Solution:** Follow the User Registration steps above

## Advanced Usage

### Running as Background Service

**Linux (systemd):**
Create `/etc/systemd/system/rust-bot.service`:
```ini
[Unit]
Description=Rust+ Discord Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/rust-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable rust-bot
sudo systemctl start rust-bot
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: At system startup
4. Action: Start a program
5. Program: `python.exe`
6. Arguments: `C:\path\to\rust-bot\bot.py`
7. Start in: `C:\path\to\rust-bot`

### Building Executable

**Windows:**
```bash
build.bat
```

**Linux:**
I've read that for Raspberry Pi's it might be better to run python directly instead of building an executable, but if you want to build it anyway for linux pcs:
```bash
chmod +x build.sh
./build.sh
```

Creates standalone executable in `dist/` folder.

## Security

### Protecting Credentials
- Never share `rustplus.config.json`
- Add `.env` to `.gitignore`
- Use environment variables for production
- Keep `users.json` private (contains tokens)

### Discord Permissions
Only grant bot permissions it needs:
- Avoid Administrator permission
- Limit to specific channels with roles
- Use channel permissions for commands


## Support

- Report bugs via GitHub Issues
- Feature requests welcome
- Check documentation folder for detailed guides

## Credits

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Uses [rustplus.py](https://github.com/olijeffers0n/rustplus) API wrapper
- FCM registration via [@liamcottle/rustplus.js](https://github.com/liamcottle/rustplus.js)

## Version History

See `CHANGELOG.md` for version history and updates.
