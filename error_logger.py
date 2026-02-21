"""
error_logger.py
────────────────────────────────────────────────────────────────────────────
Centralized error and warning logging system with 72-hour retention.

Features:
- Captures ERROR and WARNING level logs from all modules
- Automatically removes entries older than 72 hours
- Rotates log files to prevent disk space issues
- Thread-safe file operations
"""

import logging
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler


class TimeFilteredRotatingHandler(RotatingFileHandler):
    """
    Custom handler that only keeps log entries from the past 72 hours.
    Cleans up old entries on each rotation.
    """

    MAX_AGE_SECONDS = 72 * 3600  # 72 hours

    def __init__(self, filename, maxBytes=10*1024*1024, backupCount=3):
        """
        Args:
            filename: Path to log file
            maxBytes: Max file size before rotation (default 10MB)
            backupCount: Number of backup files to keep (default 3)
        """
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount)

    def emit(self, record):
        """Write log entry and clean old entries if needed"""
        super().emit(record)

        # Clean old entries after every 100 log writes
        if not hasattr(self, '_emit_count'):
            self._emit_count = 0

        self._emit_count += 1
        if self._emit_count >= 100:
            self._emit_count = 0
            self._clean_old_entries()

    def _clean_old_entries(self):
        """Remove log entries older than 72 hours"""
        try:
            log_file = Path(self.baseFilename)
            if not log_file.exists():
                return

            cutoff_time = time.time() - self.MAX_AGE_SECONDS

            # Read all lines
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Filter lines by timestamp
            filtered_lines = []
            for line in lines:
                # Extract timestamp from log line (format: "YYYY-MM-DD HH:MM:SS")
                try:
                    timestamp_str = line[:19]  # First 19 chars are timestamp
                    log_time = time.mktime(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))

                    if log_time >= cutoff_time:
                        filtered_lines.append(line)
                except (ValueError, IndexError):
                    # Keep lines without valid timestamp (header lines, stack traces, etc)
                    filtered_lines.append(line)

            # Write back filtered lines
            if len(filtered_lines) < len(lines):
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(filtered_lines)

        except Exception as e:
            # Don't crash the logger if cleanup fails
            print(f"Warning: Could not clean old log entries: {e}")


def setup_error_logging(log_file: str = "errors.log", level=logging.WARNING):
    """
    Set up centralized error/warning logging for the entire application.

    Args:
        log_file: Path to the log file (default: "errors.log")
        level: Minimum log level (default: WARNING - captures WARNING and ERROR)

    Returns:
        The configured file handler

    Example:
        # In your main bot.py, add this after imports:
        from error_logger import setup_error_logging

        # Set up error logging
        setup_error_logging()

        # Now all errors/warnings will be logged to errors.log
    """

    # Create the handler with time-based filtering
    handler = TimeFilteredRotatingHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB per file
        backupCount=3                # Keep 3 backup files
    )

    # Set format - detailed for debugging
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Set level to WARNING (captures WARNING and ERROR)
    handler.setLevel(level)

    # Add to root logger (catches all loggers in the app)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    logging.info(f"Error logging initialized: {log_file} (72-hour retention)")

    return handler


def get_recent_errors(log_file: str = "errors.log", hours: int = 72) -> list[str]:
    """
    Read all errors/warnings from the past N hours.

    Args:
        log_file: Path to log file
        hours: Number of hours to look back (default: 72)

    Returns:
        List of log lines from the specified time period
    """
    log_path = Path(log_file)

    if not log_path.exists():
        return []

    cutoff_time = time.time() - (hours * 3600)
    recent_logs = []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    # Extract timestamp
                    timestamp_str = line[:19]
                    log_time = time.mktime(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))

                    if log_time >= cutoff_time:
                        recent_logs.append(line.rstrip())
                except (ValueError, IndexError):
                    # Include lines without timestamps (stack traces, etc)
                    if recent_logs:  # Only if we're already collecting recent logs
                        recent_logs.append(line.rstrip())

    except Exception as e:
        logging.error(f"Could not read error log: {e}")
        return []

    return recent_logs


def clear_old_logs(log_file: str = "errors.log", hours: int = 72):
    """
    Manually trigger cleanup of logs older than specified hours.

    This is called automatically, but can be invoked manually if needed.
    """
    handler = TimeFilteredRotatingHandler(log_file)
    handler._clean_old_entries()
    logging.info(f"Cleaned logs older than {hours} hours from {log_file}")


if __name__ == "__main__":
    # Example usage
    setup_error_logging("test_errors.log")

    # Generate some test logs
    log = logging.getLogger("TestModule")
    log.warning("This is a warning message")
    log.error("This is an error message")
    log.info("This info message won't be logged to errors.log")

    print("\nRecent errors:")
    for line in get_recent_errors("test_errors.log"):
        print(line)