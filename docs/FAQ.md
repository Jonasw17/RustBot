# Frequently Asked Questions (FAQ)

## General Questions

### Q: What is this bot?
A: A Discord bot that connects to Rust servers via the Rust+ Companion API, allowing you to monitor servers, control smart devices, and manage your team from Discord.

### Q: Do I need to be a server admin?
A: No! Any player can use this bot. You just need to pair your own Rust+ account with the bot.

### Q: Can multiple people use the same bot?
A: Yes! The bot supports multiple users. Each person registers their own credentials and manages their own servers independently.

## Setup & Registration

### Q: How do I register with the bot?
A: Follow these steps:
1. Run `pair.bat` (Windows) or `pair.sh` (Linux/Mac)
2. Sign in with Steam when prompted
3. Find `rustplus.config.json` on your Desktop
4. DM the bot with `!register` and attach the file

### Q: Where do I find my FCM credentials?
A: After running the pairing script, look for `rustplus.config.json` on your Desktop. This file contains your FCM credentials.

### Q: Do I need Node.js?
A: Yes, but only for the initial FCM registration (running `pair.bat`). The bot itself runs on Python.

### Q: Can I use this bot without pairing?
A: No. You must pair your Rust+ account first to use any server-related commands.

## Server Management

### Q: How do I add a server?
A: Simply join the server in-game and press ESC → Rust+ → Pair Server. The bot detects it automatically!

### Q: How many servers can I pair?
A: As many as you want! There's no limit.

### Q: How do I switch between servers?
A: Use `!switch <name>` or `!switch <number>`. Example: `!switch rustoria` or `!switch 2`

### Q: How do I remove a server?
A: Use `!removeserver <name>` or `!removeserver <number>`. Example: `!removeserver 1` or `!removeserver rustoria`

### Q: Can I pair multiple servers at once?
A: Each server must be paired individually by joining in-game and using the Rust+ menu.

## Errors & Troubleshooting

### Q: I see "FCM listener crashed: 'fcm_credentials'" error. Is this bad?
A: **No**, this is harmless! It's a startup timing issue. The listener immediately restarts and works fine. You can safely ignore this error.

**Technical explanation:** During bot startup, the FCM listener tries to access user credentials before they're fully loaded. The error handler catches this and restarts the listener successfully.

### Q: "Not registered" error - what does it mean?
A: Your Discord account isn't registered with the bot yet. Follow the registration steps in the setup guide.

### Q: "No server connected" - how do I fix?
A: You need to pair a server first:
1. Join any Rust server in-game
2. Press ESC → Rust+ → Pair Server
3. Bot will auto-connect

### Q: Connection timeout errors?
A: Check these:
- Is Rust+ enabled on the server?
- Is the App Port blocked by firewall?
- Did you pair the server in-game recently?
- Try: `!switch <server>` to reconnect

### Q: UTF-8 encoding errors?
A: You're using an old version with emoji characters. Download the fixed version without emojis.

## Team Features

### Q: Can I make myself team leader?
A: **No** - this is a Rust+ API limitation, not a bot limitation. Only the current team leader can transfer leadership to another member.

**Workaround:** Have your current team leader:
1. Register with the bot
2. Run `!leader <your_name>`

### Q: Why can't I see team member locations?
A: The Rust+ API only provides approximate grid positions, not exact coordinates. Use the `!team` command to see who's online/offline and alive/dead.

### Q: Can I kick team members via the bot?
A: No, the Rust+ API doesn't support team management actions like kicking or inviting.

## Smart Devices

### Q: How do I control smart switches?
A: First register the switch:
```
!addswitch maingate 12345678
```
Then control it:
```
!sson maingate
!ssoff maingate
```

### Q: Where do I get the entity ID?
A: Pair the device in the Rust+ mobile app or game. The entity ID is shown when you pair it.

### Q: Can I control turrets?
A: Currently only smart switches are supported. Turrets require different API calls.

### Q: Do smart devices work across servers?
A: Each server has its own devices. Register devices separately for each server.

## Time & Events

### Q: Why does the time countdown seem wrong?
A: Make sure you're using the fixed version! The countdown is calculated based on:
- 1 in-game hour = 2.5 real minutes
- 24 in-game hours = 60 real minutes

### Q: How accurate are event timers?
A: Oil Rig crate timers are approximate, based on when the bot first detected the crate. They unlock 15 minutes after being triggered.

### Q: Can the bot alert me when events spawn?
A: Not automatically. You can set up timers (`!timer add 2h Cargo Ship`) to remind you to check.

## Commands

### Q: Can I use commands in-game?
A: Yes! Team chat messages starting with `!` are processed as commands. Example: type `!time` in team chat.

### Q: Do commands work in DMs?
A: Most commands work in DMs. Registration commands (like `!register`) MUST be used in DMs for security.

### Q: Can I customize the command prefix?
A: The prefix is hardcoded as `!`. To change it, edit `COMMAND_PREFIX` in `bot.py`.

### Q: Are there admin-only commands?
A: Currently only `!users` is admin-restricted. Most commands are per-user and don't need admin permissions.

## Data & Privacy

### Q: What data does the bot store?
A: The bot stores:
- Your Discord ID and username
- Your Steam ID
- Your FCM credentials (encrypted by Rust+)
- Your paired servers and player tokens
- Your registered smart devices

### Q: Is my data secure?
A: Your credentials are stored locally in `users.json`. Keep this file private and never share it. The bot doesn't send your data anywhere except to Rust servers you've paired.

### Q: Can other users see my servers?
A: No. Each user's servers are private to them. The bot keeps all user data separate.

### Q: How do I delete my data?
A: Use `!unregister` to remove all your credentials from the bot.

## Performance

### Q: Why is the bot slow sometimes?
A: The Rust+ API can be slow, especially for:
- Map generation (large images)
- First connection to a server
- Servers with high population

### Q: Can the bot crash my game?
A: No, the bot only uses the official Rust+ API. It can't affect your game.

### Q: Does the bot use a lot of bandwidth?
A: No, the bot uses minimal bandwidth. Most commands are small API requests.

## Advanced Usage

### Q: Can I run multiple bots?
A: Yes, but you need separate Discord bots and separate config files for each instance.

### Q: Can I host the bot 24/7?
A: Yes! See the README for instructions on running as a service (Linux) or scheduled task (Windows).

### Q: Can I build an executable?
A: Yes, use `build.bat` (Windows) or `build.sh` (Linux) to create a standalone executable.

### Q: Can I contribute to the bot?
A: Yes! Fork the repository, make improvements, and submit pull requests.

## Known Limitations

### Q: What can't the bot do?
A: The bot is limited by the Rust+ API:
- Can't send team invites or kick members
- Can't transfer leadership unless you ARE the leader
- Can't see exact player coordinates (only grid positions)
- Can't control turrets or other non-switch devices (yet)
- Can't access server console or admin functions

### Q: Why doesn't X feature work?
A: If a feature doesn't work:
1. Check if Rust+ supports it (many things aren't in the API)
2. Verify you're using the latest bot version
3. Check your credentials and server pairing
4. Report bugs via GitHub Issues

## Getting Help

### Q: Where can I report bugs?
A: Report bugs via GitHub Issues on the repository.

### Q: How do I request features?
A: Feature requests are welcome! Submit them via GitHub Issues with the "enhancement" label.

### Q: Is there a Discord server for support?
A: [Add your Discord server link here if you have one]

### Q: The bot isn't responding - what do I do?
A: Check:
1. Is the bot online in Discord?
2. Are you using commands in the right channel?
3. Check bot logs for errors
4. Restart the bot

## Tips & Tricks

### Q: Any tips for using the bot effectively?
A: Yes!
- Set up timers for regular tasks (furnace checks, raid defense)
- Use `!status` for quick server overview
- Register smart switches with descriptive names
- Use `!clear` to keep command channel clean
- Set up chat relay for seamless communication
- Check `!events` regularly during peak hours

### Q: Can I automate tasks?
A: The bot itself doesn't support automation, but you can:
- Use timers for reminders
- Set up external scripts to send Discord messages
- Use scheduled tasks to run specific commands

### Q: What's the most useful command?
A: Different users prefer different commands:
- **PvP players**: `!events`, `!team`, `!online`
- **Farmers**: `!time`, `!timers`, smart switches
- **Base builders**: `!upkeep`, `!decay`, `!map`
- **All players**: `!status`, `!wipe`
