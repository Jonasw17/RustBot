# Storage Monitor & Death Tracker Features

This update adds two major features to your Rust+ Discord bot:

## Storage Monitor System

Track your storage containers remotely and view their contents from Discord.

### Commands

- `!addSM <name> <entity_id>` - Add a storage monitor
- `!viewSM [name]` - View storage contents (all storages if no name given)
- `!deleteSM <name>` - Remove a storage monitor
- `!storages` - List all storage monitors for current server

### How to Use

1. **Pair your storage in Rust+**
   - Open Rust+ mobile app
   - Go to your storage container
   - Pair it (get the entity ID)

2. **Add to bot**
   ```
   !addSM main_loot 12345678
   ```

3. **View contents**
   ```
   !viewSM main_loot
   ```

### Features

- Per-user, per-server tracking
- View all items and quantities
- Rich Discord embeds with item counts
- Persistent storage across bot restarts

## Death Tracker System

Automatically tracks when teammates die and reports their grid location.

### Commands

- `!deaths` - View recent death history
- `!cleardeaths` - Clear death history for current server

### How It Works

The bot automatically monitors your team status every 10 seconds. When a teammate dies:

1. **Death is recorded** with:
   - Player name
   - Grid location (e.g., "K15")
   - Exact coordinates
   - Timestamp

2. **Discord notification** is sent with:
   - Player name
   - Grid reference
   - Map coordinates
   - Server name

### Grid System

The bot converts Rust coordinates to grid references:
- Letters A-Z (left to right)
- Numbers 0-25 (bottom to top)
- Example: "K15" means column K, row 15

### Data Retention

- Death history kept for 7 days
- Automatic cleanup of old entries
- Per-user, per-server tracking

## Installation

### New Files

Add these new files to your bot directory:
- `storage_monitor.py` - Storage monitoring system
- `death_tracker.py` - Death tracking system

### Updated Files

Replace these files with updated versions:
- `bot.py` - Integrated new features
- `commands.py` - Added new commands
- `.gitignore` - Added new data files

### No New Dependencies

Both features use existing dependencies from `requirements.txt`. No additional packages needed.

## Technical Details

### Storage Monitoring

- Uses Rust+ `get_entity_info()` API
- Stores monitor configs in `storage_monitors.json`
- Tracks last known state for each storage
- Format: `discord_id_server_key_name` for unique identification

### Death Tracking

- Monitors team status every 10 seconds
- Compares alive/dead state between checks
- Calculates grid position from map coordinates
- Stores history in `death_history.json`
- Automatic cleanup of entries older than 7 days

### Grid Calculation Algorithm

```python
def coords_to_grid(x: float, y: float, map_size: int) -> str:
    # Normalize coordinates to 0-1 range
    norm_x = (x + (map_size / 2)) / map_size
    norm_y = (y + (map_size / 2)) / map_size
    
    # Convert to 26x26 grid
    col = int(norm_x * 26)
    row = int(norm_y * 26)
    
    # Convert to letter-number format
    letter = chr(ord('A') + col)
    return f"{letter}{row}"
```

## Examples

### Storage Monitor Example

```
> !addSM sulfur_box 87654321
Storage monitor **sulfur_box** added with entity ID `87654321`

Check it with: !viewSM sulfur_box

> !viewSM sulfur_box
[Embed showing:]
Storage: sulfur_box
- 5000x Sulfur Ore
- 2000x Metal Fragments
- 500x High Quality Metal
Entity ID: 87654321
Items: 3
```

### Death Tracker Example

```
[Automatic notification when teammate dies:]

[X] PlayerName died
Location: Grid K15

Coordinates:
X: 123.4
Y: 567.8

Map Info:
Size: 4000

Server: Rustopia Main

---

> !deaths
Recent Deaths (3)

PlayerName died at K15 - 5m ago
OtherPlayer died at H22 - 15m ago
TeamMate died at N8 - 1h ago
```

## Configuration

No additional configuration needed. The features work automatically once files are added.

### Data Files Created

- `storage_monitors.json` - Storage monitor configurations
- `death_history.json` - Death tracking history

Both files are automatically created and managed by the bot.

## Troubleshooting

### Storage Monitor Issues

**"Entity ID not found"**
- Make sure you paired the storage in Rust+ app first
- Verify the entity ID is correct (numbers only)
- Check that you're connected to the correct server

**"Storage appears empty"**
- Storage might actually be empty
- Entity ID might be incorrect
- Storage might have been destroyed/despawned

### Death Tracker Issues

**"No deaths recorded"**
- System needs ~10 seconds to start tracking
- Deaths only tracked while bot is running
- Make sure team members are in your Rust+ team

**"Wrong grid location"**
- Grid calculation based on map size
- Verify map size in server info (!status)
- Grid system uses standard 26x26 layout

## Performance

- **Storage checks**: On-demand only (when you run commands)
- **Death tracking**: Checks every 10 seconds per connected user
- **Memory usage**: Minimal (JSON-based storage)
- **Network usage**: Low (only checks active connections)

## Privacy & Security

- All data stored locally in JSON files
- Per-user tracking (users only see their own data)
- No data shared between users
- Data files included in .gitignore

## Future Enhancements

Possible future additions:
- Storage change notifications (alert when items added/removed)
- Death heatmaps (visualize where deaths occur)
- Storage capacity warnings
- Death statistics (most dangerous areas, etc.)

## Support

If you encounter issues:

1. Check bot logs for error messages
2. Verify Rust+ connection is active
3. Ensure entity IDs are correct
4. Confirm user is registered (!whoami)

## Credits

Built for multi-user Rust+ Discord bot architecture.
Compatible with Windows and Linux (Raspberry Pi).
