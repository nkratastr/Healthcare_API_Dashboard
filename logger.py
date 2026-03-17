# logger.py
# Dual-channel logging system:
#   1. Rotating file logger  → logs/monitor.log  (persistent, human-readable)
#   2. In-memory ring buffer → recent log entries served to the dashboard UI

import logging
import os
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import MAX_LOG_ENTRIES

# ---------------------------------------------------------------------------
# File logger setup
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")

os.makedirs(LOG_DIR, exist_ok=True)

# Rotating handler: max 2 MB per file, keep last 5 files
_file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=2 * 1024 * 1024,  # 2 MB
    backupCount=5,
    encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)

# Console handler (useful during development)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
)

# Root logger used throughout the application
logger = logging.getLogger("integration_monitor")
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ---------------------------------------------------------------------------
# In-memory ring buffer — newest entries first for the dashboard
# ---------------------------------------------------------------------------
_memory_buffer: deque = deque(maxlen=MAX_LOG_ENTRIES)


def _build_entry(api_name: str, status: str, response_time_ms: float | None,
                 http_code: int | None, message: str) -> dict:
    """Build a structured log entry dict."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "api_name": api_name,
        "status": status,           # OK | SLOW | DOWN
        "response_time_ms": round(response_time_ms, 1) if response_time_ms is not None else None,
        "http_code": http_code,
        "message": message
    }


def log_check(api_name: str, status: str, response_time_ms: float | None,
              http_code: int | None, message: str = "") -> None:
    """
    Record a single health-check result.
    Writes to the file logger and pushes to the in-memory buffer.
    """
    entry = _build_entry(api_name, status, response_time_ms, http_code, message)

    # Human-readable line for the file / console
    rt_str = f"{entry['response_time_ms']} ms" if entry["response_time_ms"] is not None else "N/A"
    code_str = str(http_code) if http_code else "N/A"
    line = (
        f"[{api_name}] status={status} | "
        f"response_time={rt_str} | http_code={code_str}"
        + (f" | {message}" if message else "")
    )

    if status == "DOWN":
        logger.error(line)
    elif status == "SLOW":
        logger.warning(line)
    else:
        logger.info(line)

    # Push to in-memory buffer (newest first)
    _memory_buffer.appendleft(entry)


def log_alert(api_name: str, alert_type: str, detail: str) -> None:
    """Log an alert event (DOWN or SLOW threshold crossed)."""
    logger.warning(f"ALERT | [{api_name}] {alert_type} — {detail}")


def log_info(message: str) -> None:
    """General informational log (system startup, scheduler ticks, etc.)."""
    logger.info(message)


def log_error(message: str) -> None:
    """General error log (unexpected exceptions, config problems, etc.)."""
    logger.error(message)


def get_recent_logs(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` log entries from the in-memory buffer."""
    return list(_memory_buffer)[:limit]
