"""
timers.py
────────────────────────────────────────────────────────────────────────────
Persistent custom timer system.
  !rust timer add 15m TC is running low
  !rust timer add 2h30m Raid window ends
  !rust timers           (list all)
  !rust timer remove 2

Timers fire a Discord notification when they expire.
Persisted to timers.json so they survive restarts.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional
import re

import discord

log = logging.getLogger("Timers")
_TIMERS_FILE = Path("timers.json")


def parse_duration(s: str) -> Optional[int]:
    """Parse '2h15m30s', '15m', '90s', '1h' etc. Returns seconds or None."""
    s = s.strip().lower()
    pattern = r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?"
    m = re.fullmatch(pattern, s)
    if not m or not any(m.groups()):
        return None
    d, h, mn, sc = (int(x or 0) for x in m.groups())
    total = d * 86400 + h * 3600 + mn * 60 + sc
    return total if total > 0 else None


def fmt_duration(seconds: int) -> str:
    parts = []
    if seconds >= 3600:
        parts.append(f"{seconds // 3600}h")
        seconds %= 3600
    if seconds >= 60:
        parts.append(f"{seconds // 60}m")
        seconds %= 60
    if seconds:
        parts.append(f"{seconds}s")
    return "".join(parts) or "0s"


class TimerManager:
    def __init__(self):
        self._timers: dict = {}   # id -> {label, expires_at, text}
        self._next_id: int = 1
        self._notify_cb: Optional[Callable] = None
        self._load()

    def set_notify_callback(self, cb: Callable):
        """Callback receives (label, text) when a timer fires."""
        self._notify_cb = cb

    def _load(self):
        try:
            if _TIMERS_FILE.exists():
                data = json.loads(_TIMERS_FILE.read_text())
                self._timers  = {int(k): v for k, v in data.get("timers", {}).items()}
                self._next_id = data.get("next_id", 1)
                # Remove already-expired timers
                now = time.time()
                self._timers = {k: v for k, v in self._timers.items()
                                if v["expires_at"] > now}
        except Exception as e:
            log.warning(f"Could not load timers: {e}")

    def _save(self):
        try:
            _TIMERS_FILE.write_text(json.dumps({
                "timers":  self._timers,
                "next_id": self._next_id,
            }, indent=2))
        except Exception as e:
            log.warning(f"Could not save timers: {e}")

    def add(self, duration_str: str, text: str) -> tuple[bool, str]:
        """Add a timer. Returns (success, message)."""
        secs = parse_duration(duration_str)
        if secs is None:
            return False, f"Invalid duration `{duration_str}`. Use format like `15m`, `2h30m`, `1h15m30s`."
        timer_id = self._next_id
        self._next_id += 1
        self._timers[timer_id] = {
            "label":      fmt_duration(secs),
            "expires_at": time.time() + secs,
            "text":       text or f"Timer #{timer_id}",
        }
        self._save()
        return True, f"Timer **#{timer_id}** set for **{fmt_duration(secs)}** — _{text or 'no label'}_"

    def remove(self, id_str: str) -> tuple[bool, str]:
        try:
            timer_id = int(id_str)
        except ValueError:
            return False, f"Invalid ID `{id_str}` — use a number."
        if timer_id not in self._timers:
            return False, f"No timer with ID `{timer_id}`."
        t = self._timers.pop(timer_id)
        self._save()
        return True, f"Removed timer **#{timer_id}** — _{t['text']}_"

    def list_timers(self) -> str:
        if not self._timers:
            return "No active timers."
        now = time.time()
        lines = []
        for tid, t in sorted(self._timers.items()):
            remaining = max(0, int(t["expires_at"] - now))
            lines.append(f"> **#{tid}** `{fmt_duration(remaining)}` remaining — _{t['text']}_")
        return "**Active Timers:**\n" + "\n".join(lines)

    async def run_loop(self):
        """Background loop — checks timers every second and fires callbacks."""
        log.info("Timer loop started")
        while True:
            now = time.time()
            fired = [tid for tid, t in list(self._timers.items())
                     if t["expires_at"] <= now]
            for tid in fired:
                t = self._timers.pop(tid)
                self._save()
                log.info(f"Timer #{tid} fired: {t['text']}")
                if self._notify_cb:
                    try:
                        await self._notify_cb(t["label"], t["text"])
                    except Exception as e:
                        log.error(f"Timer notify error: {e}")
            await asyncio.sleep(1)


# Module-level singleton
timer_manager = TimerManager()