# Automatic Entity ID Capture - No Manual IDs Needed!

## The Problem (Old Way)

Before, you had to:
1. Pair device in-game
2. Find the entity ID somehow
3. Manually type `!addSM name 12345678`

**The entity ID was hidden!** The Rust+ app doesn't show it anymore, and it's not in combat log.

## The Solution (New Way)

The bot now works **exactly like the Rust+ mobile app**!

### How It Works

1. **Pair device in-game** (ESC -> Rust+ -> Pair)
   - Storage box, smart switch, etc.

2. **Bot automatically detects it!**
   - Captures the entity ID from the pairing notification

3. **Bot sends you a DM:**
   ```
   [+] New Device Paired!
   You just paired a Storage Container on Rustopia Main
   
   Entity ID: 87654321
   In-game name: Storage Box
   
   What would you like to name it?
   Reply with a name (e.g., main_loot or front_gate)
   Or reply with skip to ignore this pairing.
   ```

4. **You reply in DM:**
   ```
   main_loot
   ```

5. **Bot confirms:**
   ```
   [OK] Device Added!
   Storage monitor main_loot added with entity ID 87654321
   
   Server: Rustopia Main
   Entity ID: 87654321
   ```

6. **Done!** Now use:
   ```
   !viewSM main_loot
   ```

## No More Manual Entity IDs!

You **never** have to type entity IDs anymore. The bot captures them automatically, just like the official Rust+ app does.

## Step-by-Step Example

### Pairing a Storage Box

**In Rust (game):**
```
1. Press ESC
2. Click "Rust+"
3. Click "Pair to Server"
4. Walk to your storage box
5. Press E to pair
6. Confirm pairing
```

**In Discord (automatically):**
```
Bot DMs you:
┌────────────────────────────────────
│ [+] New Device Paired!
│ 
│ You just paired a Storage Container
│ on Rustopia Main
│ 
│ Entity ID: 87654321
│ In-game name: Storage Box
│ 
│ What would you like to name it?
│ Reply with a name or skip
└────────────────────────────────────

You reply: sulfur_room

Bot responds:
┌────────────────────────────────────
│ [OK] Device Added!
│ 
│ Storage monitor sulfur_room added
│ Entity ID: 87654321
│ Server: Rustopia Main
└────────────────────────────────────
```

**Now check it anytime:**
```
!viewSM sulfur_room
```

## Supported Devices

The auto-pairing system works for:

- **Storage Containers** → Becomes storage monitor
- **Smart Switches** → Becomes controllable switch
- **Smart Alarms** → (Future support)
- **Tool Cupboards** → (Already handled by server pairing)

## Benefits

### 1. No Hidden Entity IDs
- Bot captures them automatically
- You never need to find them manually

### 2. Just Like Rust+ App
- Same pairing process
- Automatic detection
- Name things your way

### 3. Multi-Server Support
- Pair devices on any server
- Bot tracks which server each device is on
- Switch servers with `!change <server>`

### 4. No Mistakes
- No typing wrong entity IDs
- No confusion about which device is which
- Bot confirms everything

## How to Enable DMs

**Important:** The bot needs to send you DMs for this to work.

### Enable DMs from Server Members

1. Right-click your server icon
2. Click "Privacy Settings"
3. Enable "Direct Messages"

Or:

1. User Settings → Privacy & Safety
2. Enable "Allow direct messages from server members"

### If DMs Are Disabled

The bot will log the pairing but can't prompt you. You'll need to add devices manually:

```
!addSM name 12345678
```

But you still won't know the entity ID! **So enable DMs!**

## Multiple Devices

You can pair as many as you want:

**Pair in game:**
- Storage box 1
- Storage box 2  
- Front gate smart switch
- Back door smart switch

**Name them in DM:**
```
Bot: New Device Paired! (Storage)
You: loot_room_1

Bot: New Device Paired! (Storage)
You: loot_room_2

Bot: New Device Paired! (Switch)
You: front_gate

Bot: New Device Paired! (Switch)
You: back_door
```

**Use them:**
```
!viewSM loot_room_1
!viewSM loot_room_2
!sson front_gate
!ssoff back_door
```

## Naming Tips

### Good Names
- `main_loot` ✓
- `sulfur_room` ✓
- `front_gate` ✓
- `tc_upstairs` ✓
- `raid_defense_1` ✓

### Bad Names
- `my box` ✗ (no spaces)
- `loot@base` ✗ (no special characters)
- `a` ✗ (too short, not descriptive)

### Rules
- Letters, numbers, underscores, hyphens only
- 1-50 characters
- No spaces
- Make it descriptive!

## Skipping Devices

If you paired something by accident:

**Bot DM:**
```
New Device Paired! (Smart Switch)
...
```

**You reply:**
```
skip
```

**Bot confirms:**
```
Pairing skipped.
```

The device won't be added to your monitors.

## Troubleshooting

### Bot Didn't Send Me a DM

**Check:**
1. Did you enable DMs from server members?
2. Did you pair the device after the bot started?
3. Is your Discord ID registered? (`!whoami`)

**If still not working:**
- Check bot logs for errors
- Make sure FCM listener is running
- Restart bot and try again

### I Named It Wrong

**Fix it:**
```
!deleteSM wrong_name
```

Then pair the device again in-game and name it correctly.


### Pairing Timeout

You have **5 minutes** to reply to the naming prompt.

After 5 minutes, the pairing expires and you'll need to:
1. Delete the device in Rust+ app
2. Pair it again in-game
3. Name it when bot DMs you

## Technical Details

### How It Works

1. **FCM Listener** monitors pairing notifications
2. **Notification contains:**
   - Entity ID
   - Entity type (storage, switch, alarm)
   - Entity name
   - Server info
3. **Bot captures data** and stores temporarily
4. **Bot sends DM** with prompt
5. **User replies** with name
6. **Bot adds device** with captured entity ID

### Entity Types

- Type 1 = Smart Switch
- Type 2 = Storage Container
- Type 3 = Smart Alarm
- Type 4 = RF Broadcaster
- Type 5 = Storage Monitor

The bot automatically adds devices to the right system based on type.

### Data Flow

```
In-Game Pairing
      ↓
FCM Notification → Bot Listener
      ↓
Parse Entity Data (ID, Type, Name)
      ↓
Store Temporarily (5 min)
      ↓
Send DM to User
      ↓
User Replies with Name ← (You are here!)
      ↓
Add to Storage/Switch Manager
      ↓
Confirm to User
      ↓
Ready to Use! (!viewSM, !sson, etc.)
```

## Examples

### Example 1: First Time Setup

```
[You just installed the bot]

You: !register
Bot: Upload your rustplus.config.json
[You upload file]
Bot: Registration successful!

[In Rust, you pair your base server]
Bot: Server paired! Auto-connected.

[In Rust, you pair a storage box]
Bot DM: New Device Paired! Storage Container
         What would you like to name it?
You DM: main_loot
Bot DM: Device added!

[In Discord channel]
You: !viewSM main_loot
Bot: [Shows all items in your storage]
```

### Example 2: Adding Multiple Storages

```
[You pair 3 boxes in game]

Bot DM: New Device Paired! (Storage)
You: sulfur
Bot: Device added!

Bot DM: New Device Paired! (Storage)
You: metal
Bot: Device added!

Bot DM: New Device Paired! (Storage)
You: components
Bot: Device added!

[In Discord channel]
You: !viewSM
Bot: [Shows all 3 storages with contents]
```

### Example 3: Smart Switches + Storage

```
[You pair a switch]
Bot DM: New Device Paired! (Smart Switch)
You: front_door
Bot: Device added!

[You pair storage]
Bot DM: New Device Paired! (Storage)
You: loot_behind_door
Bot: Device added!

You: !sson front_door
Bot: Smart switch front_door turned ON

You: !viewSM loot_behind_door
Bot: [Shows storage contents]
```

## Summary

- Pair in-game
- Bot DMs you immediately
- Reply with name
- Done! ✓

**Zero manual entity IDs needed!**

## Commands Reference

After auto-pairing:

```
!storages         - List all storage monitors
!viewSM [name]    - View storage contents
!deleteSM <n>    - Remove storage monitor

!switches         - List all smart switches
!sson <n>        - Turn switch on
!ssoff <n>       - Turn switch off

!servers          - List paired servers
!status           - Current server status
```

The bot handles everything automatically!
