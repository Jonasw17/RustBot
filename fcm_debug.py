"""
fcm_debug.py
------------------------------------------------------------
Run this script, then pair a server in-game (ESC > Rust+ > Pair Server).
It will print the EXACT raw data the FCM listener receives so you can
confirm pairing notifications are arriving and inspect their structure.

Usage:
    python fcm_debug.py
"""

import json
import logging
from rustplus import FCMListener

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("FCMDebug")

CONFIG_FILE = "rustplus.config.json"

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        fcm_creds = json.load(f)
except FileNotFoundError:
    print("[ERROR] {} not found.".format(CONFIG_FILE))
    print("Run pair.bat (Windows) or the FCM register command first.")
    raise SystemExit(1)
except Exception as e:
    print("[ERROR] Could not read {}: {}".format(CONFIG_FILE, e))
    raise SystemExit(1)


class DebugListener(FCMListener):
    def on_notification(self, obj, notification, data_message):
        print("\n" + "=" * 60)
        print("FCM NOTIFICATION RECEIVED")
        print("=" * 60)
        print("obj type    :", type(obj).__name__)
        print("obj         :", obj)
        print("---")
        print("notification:", notification)
        print("---")
        print("data_message:", data_message)
        print("=" * 60 + "\n")


print("Listening for FCM notifications...")
print("Go in-game: ESC > Rust+ > Pair Server")
print("Press Ctrl+C to stop.\n")

DebugListener(fcm_creds).start()
