# monitor.py
# Core monitoring engine.
# Runs health checks against all configured APIs, classifies their status,
# manages per-API history, and builds the active alert list.

import time
import threading
from collections import deque, defaultdict
from datetime import datetime

import requests

import config
from logger import log_check, log_alert, log_info, log_error

# ---------------------------------------------------------------------------
# Shared state (thread-safe via a lock)
# ---------------------------------------------------------------------------
_lock = threading.Lock()

# Latest check result per API  →  { api_name: result_dict }
_latest: dict[str, dict] = {}

# Last HISTORY_SIZE results per API  →  { api_name: deque[result_dict] }
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=config.HISTORY_SIZE))

# Active alerts  →  list of alert dicts
_alerts: list[dict] = []

# Track which APIs already have an active alert (to avoid duplicates)
_alerted: set[str] = set()


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------

def _classify(response_time_ms: float, http_code: int) -> str:
    """Return OK, SLOW, or DOWN based on response time and HTTP status code."""
    if http_code != 200:
        return "DOWN"
    if response_time_ms > config.SLOW_THRESHOLD_MS:
        return "SLOW"
    return "OK"


# ---------------------------------------------------------------------------
# Single API health check (with retry logic)
# ---------------------------------------------------------------------------

def _check_api(api: dict) -> dict:
    """
    Perform a health check on one API entry.
    Retries up to RETRY_ATTEMPTS times before marking as DOWN.
    Returns a result dict.
    """
    name = api["name"]
    url = api["url"]
    last_error = ""

    for attempt in range(1, config.RETRY_ATTEMPTS + 2):  # +2 → initial try + retries
        try:
            start = time.monotonic()
            response = requests.get(url, timeout=config.TIMEOUT_SECONDS)
            elapsed_ms = (time.monotonic() - start) * 1000

            status = _classify(elapsed_ms, response.status_code)

            result = {
                "api_name": name,
                "url": url,
                "status": status,
                "response_time_ms": round(elapsed_ms, 1),
                "http_code": response.status_code,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": None,
                "attempt": attempt
            }

            log_check(name, status, elapsed_ms, response.status_code,
                      f"attempt {attempt}" if attempt > 1 else "")
            return result

        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        except requests.exceptions.ConnectionError:
            last_error = "Connection error"
        except requests.exceptions.RequestException as exc:
            last_error = str(exc)

        # Wait before retrying (skip delay after last attempt)
        if attempt <= config.RETRY_ATTEMPTS:
            log_info(f"[{name}] attempt {attempt} failed ({last_error}) — retrying in {config.RETRY_DELAY_SECONDS}s")
            time.sleep(config.RETRY_DELAY_SECONDS)

    # All attempts exhausted → mark DOWN
    result = {
        "api_name": name,
        "url": url,
        "status": "DOWN",
        "response_time_ms": None,
        "http_code": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": last_error,
        "attempt": attempt
    }
    log_check(name, "DOWN", None, None, last_error)
    return result


# ---------------------------------------------------------------------------
# Alert management
# ---------------------------------------------------------------------------

def _handle_alerts(result: dict) -> None:
    """
    Raise an alert when an API becomes SLOW or DOWN.
    Resolve it automatically when it returns to OK.
    """
    name = result["api_name"]
    status = result["status"]

    with _lock:
        if status in ("DOWN", "SLOW") and name not in _alerted:
            alert = {
                "api_name": name,
                "alert_type": status,
                "timestamp": result["timestamp"],
                "detail": (
                    f"HTTP {result['http_code']}" if result["http_code"]
                    else result.get("error", "No response")
                ),
                "response_time_ms": result["response_time_ms"]
            }
            _alerts.append(alert)
            _alerted.add(name)
            log_alert(name, status, alert["detail"])

        elif status == "OK" and name in _alerted:
            # Remove resolved alerts for this API
            _alerts[:] = [a for a in _alerts if a["api_name"] != name]
            _alerted.discard(name)
            log_info(f"[{name}] recovered — alert cleared")


# ---------------------------------------------------------------------------
# Full monitoring cycle (all APIs)
# ---------------------------------------------------------------------------

def run_checks() -> None:
    """Check all configured APIs and update shared state."""
    log_info("--- Monitor cycle started ---")

    for api in config.APIS:
        result = _check_api(api)
        _handle_alerts(result)

        with _lock:
            _latest[api["name"]] = result
            _history[api["name"]].appendleft(result)

    log_info("--- Monitor cycle complete ---")


# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

def _scheduler() -> None:
    """Run health checks on a fixed interval in a background thread."""
    while True:
        try:
            run_checks()
        except Exception as exc:
            log_error(f"Unexpected error in monitor cycle: {exc}")
        time.sleep(config.CHECK_INTERVAL_SECONDS)


def start_background_monitor() -> None:
    """Launch the monitoring scheduler as a daemon thread."""
    thread = threading.Thread(target=_scheduler, name="monitor-scheduler", daemon=True)
    thread.start()
    log_info(f"Background monitor started — checking every {config.CHECK_INTERVAL_SECONDS}s")


# ---------------------------------------------------------------------------
# Public accessors (used by Flask routes)
# ---------------------------------------------------------------------------

def get_latest_results() -> list[dict]:
    """Return the most recent check result for every configured API."""
    with _lock:
        return [_latest.get(api["name"], _placeholder(api)) for api in config.APIS]


def get_history(api_name: str) -> list[dict]:
    """Return the last HISTORY_SIZE results for a specific API."""
    with _lock:
        return list(_history.get(api_name, []))


def get_active_alerts() -> list[dict]:
    """Return all currently active alerts."""
    with _lock:
        return list(_alerts)


def _placeholder(api: dict) -> dict:
    """Return an empty result for an API that hasn't been checked yet."""
    return {
        "api_name": api["name"],
        "url": api["url"],
        "status": "PENDING",
        "response_time_ms": None,
        "http_code": None,
        "timestamp": None,
        "error": None
    }
