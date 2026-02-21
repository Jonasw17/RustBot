# Quick Start Guide - New Features

## Storage Monitor

### Setup (2 minutes)

1. **In Rust+ mobile app:**
   - Find your storage container
   - Tap to pair it
   - Note the Entity ID (e.g., 87654321)

2. **In Discord:**
   ```
   !addSM loot_room 87654321
   ```

3. **Check contents anytime:**
   ```
   !viewSM loot_room
   ```

### All Commands

```
!addSM <n> <id>     - Add storage monitor
!viewSM [name]       - View contents
!deleteSM <n>       - Remove monitor
!storages            - List all monitors
```

## Death Tracker

### Setup (automatic)

No setup needed! The bot automatically tracks deaths.

### Usage

**View death history:**
```
!deaths
```

**Clear old deaths:**
```
!cleardeaths
```

### What You Get

When a teammate dies, you'll see:
- Player name
- Grid location (e.g., K15)
- Exact coordinates
- Server name

## Examples

### Example 1: Monitor Main Loot Room

```
You: !addSM main_loot 12345678
Bot: Storage monitor **main_loot** added with entity ID `12345678`

You: !viewSM main_loot
Bot: [Shows embed with all items and quantities]
```

### Example 2: Check Death Location

```
[Teammate dies in-game]

Bot: [Automatic notification]
     [X] PlayerName died
     Location: Grid K15
     Coordinates: X: 123.4, Y: 567.8

You: !deaths
Bot: Recent Deaths (5)
     PlayerName died at K15 - 2m ago
     OtherPlayer died at H22 - 10m ago
     ...
```

## Tips

### Storage Monitors

- Use descriptive names: `main_loot`, `sulfur_box`, `raid_gear`
- You can have unlimited monitors per server
- Each user has their own monitors
- Monitors persist across bot restarts

### Death Tracking

- Grid system: A-Z (columns), 0-25 (rows)
- History kept for 7 days
- Automatic cleanup of old entries
- Works for all team members

## Troubleshooting

### Storage Not Found
- Verify entity ID from Rust+ app
- Make sure storage still exists in-game
- Check you're on the right server (!servers)

### No Deaths Showing
- Bot needs to be running when death occurs
- Player must be in your Rust+ team
- Wait 10 seconds after bot starts

## Need Help?

1. Check `STORAGE_DEATH_FEATURES.md` for full documentation
2. Use `!help` to see all commands
3. Use `!whoami` to verify registration
4. Use `!servers` to check connection

## File Checklist

Make sure you have these files:
- [X] storage_monitor.py (new)
- [X] death_tracker.py (new)
- [X] bot.py (updated)
- [X] commands.py (updated)
- [X] .gitignore (updated)

All other files remain unchanged.
