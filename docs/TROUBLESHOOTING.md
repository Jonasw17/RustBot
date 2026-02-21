# Troubleshooting Guide

Complete guide to solving common issues with the Rust+ Discord Bot.

## Table of Contents
1. [Installation Issues](#installation-issues)
2. [Registration Problems](#registration-problems)
3. [Connection Errors](#connection-errors)
4. [Command Issues](#command-issues)
5. [Smart Device Problems](#smart-device-problems)
6. [Error Messages Explained](#error-messages-explained)
7. [Performance Issues](#performance-issues)

---

## Installation Issues

### Python Not Found
**Symptom:** `python: command not found`

**Solution:**
```bash
# Check Python installation
python --version  # or python3 --version

# Install Python 3.8+ if missing
# Windows: Download from python.org
# Linux: sudo apt install python3 python3-pip
# Mac: brew install python3
```

### Pip Install Fails
**Symptom:** `pip install -r requirements.txt` fails

**Solutions:**
1. **Permission denied:**
   ```bash
   # Linux/Mac
   pip install --user -r requirements.txt
   
   # Or use sudo (not recommended)
   sudo pip install -r requirements.txt
   ```

2. **Module not found:**
   ```bash
   # Make sure pip is up to date
   python -m pip install --upgrade pip
   
   # Try python3 specifically
   python3 -m pip install -r requirements.txt
   ```

3. **Compiler errors (Windows):**
   - Install Microsoft C++ Build Tools
   - Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

### Discord.py Won't Install
**Solution:**
```bash
# Make sure you have correct version
pip install "discord.py>=2.3.0"

# If voice support errors:
pip install PyNaCl
```

---

## Registration Problems

### FCM Registration Fails

**Symptom:** `pair.bat` or `pair.sh` fails to create config file

**Solutions:**

1. **Node.js not installed:**
   ```bash
   # Check installation
   node --version
   
   # Install if needed
   # Windows: Download from nodejs.org
   # Linux: sudo apt install nodejs npm
   # Mac: brew install node
   ```

2. **npm package not found:**
   ```bash
   # Reinstall the package
   npm install -g @liamcottle/rustplus.js
   
   # Or run without global install
   npx @liamcottle/rustplus.js fcm-register
   ```

3. **Chrome doesn't open:**
   - Make sure Chrome/Chromium is installed
   - Try running as administrator (Windows)
   - Check firewall settings

4. **Steam login fails:**
   - Clear browser cookies
   - Try in incognito/private mode
   - Disable browser extensions
   - Make sure Steam is not blocking logins

### Bot Doesn't Accept Config File

**Symptom:** "Could not find Steam ID in the config file"

**Solutions:**
1. **Wrong file uploaded:**
   - Make sure it's `rustplus.config.json`
   - Not `rustplus.config.json.txt`
   - Check file contents with text editor

2. **Corrupted file:**
   - Re-run FCM registration
   - Don't edit the JSON manually
   - Make sure file encoding is UTF-8

3. **Old format:**
   - Delete old config file
   - Run registration again
   - Use latest version of rustplus.js package

### "User not registered" Error

**Solutions:**
```
# Check registration status
!whoami

# If not registered:
# 1. DM the bot (not server channel)
# 2. Send: !register
# 3. Attach rustplus.config.json
```

---

## Connection Errors

### "Could not reach Rust+ server"

**Possible Causes & Solutions:**

1. **Server doesn't have Rust+ enabled:**
   - Not all servers support Rust+
   - Check server description/rules
   - Try official or popular modded servers

2. **App Port blocked:**
   ```
   # Check firewall rules
   # Windows: Allow python.exe through firewall
   # Linux: sudo ufw allow out to any port 28082
   ```

3. **Not paired in-game:**
   ```
   # Re-pair the server:
   # 1. Join server in-game
   # 2. Press ESC
   # 3. Rust+ menu
   # 4. Pair Server
   ```

4. **Server offline:**
   ```
   # Check server status in game browser
   # Try different server
   ```

5. **Player token expired:**
   ```
   # Remove and re-pair server:
   !removeserver <server>
   # Then pair again in-game
   ```

### Connection Timeout

**Symptom:** Commands hang or timeout after 10 seconds

**Solutions:**
1. **Network issues:**
   - Check your internet connection
   - Try ping test: `ping <server_ip>`
   - Check if server is DDoS protected

2. **Server lag:**
   - High population servers may be slow
   - Try during off-peak hours
   - Use `!switch` to reconnect

3. **Bot overloaded:**
   - Restart the bot
   - Check system resources
   - Consider dedicated hosting

### FCM Listener Crashed Error

**Error Message:**
```
[ERROR] ServerManager: FCM listener crashed for <user>: 'fcm_credentials'
```

**Explanation:**
This is a **harmless startup timing issue**. The FCM listener tries to access credentials before they're fully loaded during bot startup.

**What Happens:**
1. Error is logged
2. Listener immediately restarts
3. Everything works normally

**Action Required:** None! You can safely ignore this error.

**If concerned:** Check that server pairing still works:
```
# In-game: ESC → Rust+ → Pair Server
# Bot should detect it automatically
```

---

## Command Issues

### Commands Not Working

**Symptom:** Bot doesn't respond to commands

**Checklist:**
1. **Bot online?**
   - Check bot status in Discord
   - Look for green dot next to name

2. **Right channel?**
   - Commands only work in configured channels
   - Check `.env` for COMMAND_CHANNEL_ID
   - Or use DMs

3. **Correct prefix?**
   - Default is `!`
   - Check for typos: `!status` not `! status`

4. **Permissions?**
   - Bot needs Read/Send Messages permission
   - Bot needs Embed Links for rich responses

### "Invalid ID" or "Invalid index" Errors

**For server/switch selection:**
```
# Use 1-based index (not 0-based)
!switch 1  # First server
!switch 2  # Second server

# Or use name
!switch rustoria
```

### Commands Timeout

**Symptom:** "[!] Command timed out"

**Solutions:**
1. **Check connection:** `!servers`
2. **Reconnect:** `!switch <server>`
3. **Restart bot** if persistent
4. **Check server status** - may be offline

---

## Smart Device Problems

### Can't Add Smart Switch

**Symptom:** "Failed to add switch" or invalid entity ID

**Solutions:**
1. **Wrong entity ID:**
   - Get ID from Rust+ app when pairing
   - Entity IDs are numbers (e.g., 12345678)
   - Don't use device name as ID

2. **Not connected to server:**
   ```
   # Check connection first
   !status
   
   # If not connected
   !switch <server>
   ```

3. **Syntax error:**
   ```
   # Correct format:
   !addswitch name 12345678
   
   # Examples:
   !addswitch maingate 12345678
   !addswitch garage 87654321
   ```

### Switch Control Not Working

**Symptom:** "Error toggling switch" or "Entity not found"

**Solutions:**
1. **Device unpaired:**
   - Device was destroyed or moved
   - Remove and re-add: `!removeswitch <name>`

2. **Wrong server:**
   ```
   # Check active server
   !status
   
   # Switch devices are per-server
   # Add same device on each server separately
   ```

3. **Permission issue:**
   - You must own the device
   - Or have building privilege
   - Device must be paired to your account

---

## Error Messages Explained

### [ERROR] FCM listener crashed: 'fcm_credentials'
**Meaning:** Harmless startup timing issue
**Action:** None - ignore this error

### [!] Command timed out
**Meaning:** Server didn't respond within 10 seconds
**Action:** Check connection, try again

### [!] Command failed: Connection issue
**Meaning:** Lost connection to Rust+ server
**Action:** Use `!switch <server>` to reconnect

### [X] No servers paired
**Meaning:** You haven't paired any servers yet
**Action:** Join server in-game and pair it

### [X] Not registered
**Meaning:** Your Discord account isn't registered
**Action:** DM bot with `!register` + config file

### "User not registered"
**Meaning:** Same as above
**Action:** Complete registration process

### "No server connected"
**Meaning:** Not connected to any server
**Action:** `!switch <server>` or pair new server

### "Could not reach Rust+ server"
**Meaning:** Can't establish connection
**Action:** See [Connection Errors](#connection-errors) section

### UTF-8 encoding error
**Meaning:** Emoji characters in old version
**Action:** Download emoji-free version of files

---

## Performance Issues

### Bot Running Slow

**Symptoms:**
- Commands take long to respond
- Map images slow to generate
- Frequent timeouts

**Solutions:**
1. **System resources:**
   ```bash
   # Check CPU/RAM usage
   # Windows: Task Manager
   # Linux: htop or top
   ```

2. **Optimize bot:**
   - Reduce status update frequency
   - Disable chat relay if not needed
   - Limit number of paired servers

3. **Network issues:**
   - Check bandwidth usage
   - Ping test to server
   - Consider hosting closer to servers

### High Memory Usage

**Solutions:**
1. **Restart bot periodically:**
   ```bash
   # Add to cron (Linux) or Task Scheduler (Windows)
   # Restart once per day
   ```

2. **Check for memory leaks:**
   - Update to latest version
   - Report issue on GitHub

3. **Reduce cache:**
   ```bash
   # Delete cache files
   rm event_timestamps.json
   # They will regenerate
   ```

### Bot Crashes

**Check logs for errors:**
```bash
# Run with logging
python bot.py 2>&1 | tee bot.log

# Check for errors
grep ERROR bot.log
```

**Common causes:**
1. **Out of memory** - Reduce features or upgrade hardware
2. **Network issues** - Check connection stability
3. **API rate limits** - Add delays between commands
4. **Corrupted data files** - Delete and regenerate

---

## Getting More Help

### Enable Debug Logging

Edit `bot.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

### Collect Diagnostic Info

```bash
# Python version
python --version

# Bot version
grep "Version" bot.py

# Installed packages
pip freeze | grep -E "discord|rustplus"

# System info
# Linux: uname -a
# Windows: systeminfo
```

### Report Issues

When reporting bugs, include:
1. Error message (full text)
2. Steps to reproduce
3. Python version
4. Operating system
5. Bot version
6. Relevant logs

### Community Resources

- GitHub Issues: Report bugs and request features
- Discord Server: [Your server invite]
- Documentation: Check `docs/` folder

---

## Quick Reference

### Restart Bot
```bash
# Stop bot (Ctrl+C)
# Start again
python bot.py
```

### Clear Data
```bash
# Backup first!
cp users.json users.json.bak

# Clear specific data
rm timers.json          # Clear timers
rm switches.json        # Clear smart devices
rm event_timestamps.json  # Clear event cache
```

### Reset User
```
# In Discord
!unregister

# Then re-register
!register
```

### Test Connection
```
!status    # Full server check
!time      # Quick API test
!servers   # List paired servers
```

---

## Still Having Issues?

If you've tried everything in this guide and still have problems:

1. **Check bot logs carefully**
2. **Try with a fresh install**
3. **Test with different server**
4. **Report detailed bug report**
5. **Ask in community Discord**

Remember to include:
- Exact error messages
- What you've already tried
- Your system details
- Bot and Python versions
