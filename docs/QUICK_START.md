# Quick Start Guide - Rust+ Companion Bot

## For Users (First Time Setup)

### Step 1: Get Your FCM Credentials (One Time Only)

**Windows:**
```bash
# Just double-click this file
pair.bat
```

**Linux/Mac:**
```bash
npm install -g @liamcottle/rustplus.js
npx @liamcottle/rustplus.js fcm-register
```

This creates `rustplus.config.json` on your Desktop.

### Step 2: Register with Bot

1. DM the bot: `!register`
2. Attach the `rustplus.config.json` file
3. Wait for confirmation

### Step 3: Pair a Server

1. Join any Rust server in-game
2. Press **ESC**
3. Click **Rust+**
4. Click **Pair Server**
5. Bot auto-connects!

## For Bot Admins (Setup)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` File
```env
DISCORD_TOKEN=your_bot_token_here
COMMAND_CHANNEL_ID=123456789
NOTIFICATION_CHANNEL_ID=123456789
CHAT_RELAY_CHANNEL_ID=123456789
```

### 3. Run Bot
```bash
python bot.py
```

## Testing New Features

### Test Server Pairing Fix
1. Register a new user
2. Pair a server in-game (ESC > Rust+ > Pair Server)
3. Check bot logs for: `[Pairing] Server paired by...`
4. Verify connection: `!servers`

### Test Raid Alarm
1. Enable: `!raidalarm on`
2. Have someone raid you (or shoot rockets near you)
3. Check for DM notification
4. Verify cooldown: `!raidalarm status`

### Test Grid Coordinates
1. Be online in-game
2. Run: `!team`
3. Should see: `> PlayerName - Online @ K15`
4. Die and check: `!alive` (shows death location)

### Test Uptime Fix
1. Run: `!uptime`
2. Should show:
   - Bot uptime
   - Server uptime (time since wipe)

## Common Commands Quick Reference

```bash
# Setup
!register              # Register your account (DM)
!servers               # List paired servers
!switch <server>       # Change active server

# Server Info
!status               # Full server status
!uptime               # Bot + server uptime
!time                 # Day/night cycle

# Team (with grid coords!)
!team                 # All members + locations
!online               # Online members @ grid
!alive                # Shows death locations

# Raid Alarm
!raidalarm on         # Enable alerts
!raidalarm status     # Check status

# Timers
!timer add 15m Boom   # Set 15min timer
!timers               # List all timers
```


## File Checklist

Make sure you have these files:
- [ ] bot.py
- [ ] commands.py
- [ ] server_manager_multiuser.py
- [ ] multi_user_auth.py
- [ ] raid_alarm.py (NEW)
- [ ] grid_coordinates.py (NEW)
- [ ] status_embed.py
- [ ] timers.py
- [ ] rust_info_db.py
- [ ] chat_relay.py
- [ ] requirements.txt
- [ ] pair.bat (Windows only)
- [ ] .env (you create this)

## Troubleshooting Quick Fixes

**Bot won't start:**
```bash
pip install -r requirements.txt --upgrade
```

**Pairing not working:**
```bash
# Re-run FCM registration
npx @liamcottle/rustplus.js fcm-register
# Send new config to bot
!register
```

**Raid alarm not working:**
```bash
pip install PyNaCl
# Then enable
!raidalarm on
```

**Grid coords wrong:**
- Normal! They're approximate based on Rust+ API data
- More accurate when you're online
- Death locations are last known position

## Need More Help?

See the full README.md for:
- Detailed troubleshooting
- Architecture explanation
- Performance tuning
- Security notes
