"""
pair.py — Run this ONCE to link your Steam account with Rust+
────────────────────────────────────────────────────────────────────────────
This creates rustplus.py.config.json which the bot uses to listen for
in-game pairing notifications.

Requirements:
  - Google Chrome must be installed
  - Node.js must be installed (for the @liamcottle/rustplus.js CLI)

Usage:
  python pair.py

What happens:
  1. Installs @liamcottle/rustplus.js if not already installed
  2. Opens a Chrome window to sign in with your Steam account
  3. Once signed in, saves rustplus.py.config.json
  4. You're done — the bot will now auto-detect new servers when you pair them
     in-game (ESC → Rust+ tab → Pair Server)
"""

import subprocess
import sys
import os
from pathlib import Path

FCM_CONFIG = Path("rustplus.py.config.json")


def main():
    print("=" * 60)
    print("  Rust+ Companion Bot — One-Time FCM Registration")
    print("=" * 60)
    print()

    # Check if already registered
    if FCM_CONFIG.exists():
        print(f"✅ {FCM_CONFIG} already exists.")
        print()
        answer = input("Re-register anyway? (y/N): ").strip().lower()
        if answer != "y":
            print("Nothing to do. You're already set up!")
            print()
            print("To pair a new server:")
            print("  1. Join any Rust server in-game")
            print("  2. Press ESC → Rust+ tab → Pair Server")
            print("  3. The bot will connect automatically!")
            return

    print("Prerequisites:")
    print("  ✓ Google Chrome must be installed")
    print("  ✓ Node.js must be installed (https://nodejs.org)")
    print()

    # Check Node.js is available
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"  Node.js: {result.stdout.strip()} ✅")
    except FileNotFoundError:
        print("  ❌ Node.js not found. Install it from https://nodejs.org and retry.")
        sys.exit(1)

    print()
    print("This will open a Chrome window.")
    print("Sign in with your Steam account when prompted.")
    print()
    input("Press ENTER to continue...")
    print()

    # Run the FCM registration CLI
    print("Running FCM registration...")
    print("-" * 60)

    try:
        subprocess.run(
            ["npx", "@liamcottle/rustplus.js", "fcm-register"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FCM registration failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ npx not found. Is Node.js properly installed?")
        sys.exit(1)

    print("-" * 60)
    print()

    # Verify the config was created
    if FCM_CONFIG.exists():
        print(f"✅ Success! {FCM_CONFIG} created.")
        print()
        print("You're all set up! Next steps:")
        print("  1. Start the bot:  python bot.py")
        print("  2. Join any Rust server in-game")
        print("  3. Press ESC → Rust+ tab → Pair Server")
        print("  4. The bot will automatically connect and notify Discord!")
        print()
        print("You only need to run this script once.")
        print("Your token works across all Rust servers.")
    else:
        print("⚠️  Config file not found after registration.")
        print("The CLI may have saved it to a different location.")
        print("Look for 'rustplus.py.config.json' and move it here.")


if __name__ == "__main__":
    main()