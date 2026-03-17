# app.py
# Flask application — serves the dashboard UI and JSON API endpoints.
# Monitoring runs in a background daemon thread; Flask only reads shared state.

from flask import Flask, jsonify, render_template

import monitor
from logger import get_recent_logs, log_info

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    """Render the main monitoring dashboard."""
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# JSON API endpoints (consumed by the dashboard via fetch())
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    """
    Returns the latest check result for every monitored API.
    Shape: [ { api_name, status, response_time_ms, http_code, timestamp, error }, ... ]
    """
    return jsonify(monitor.get_latest_results())


@app.route("/api/alerts")
def api_alerts():
    """
    Returns all currently active alerts.
    Shape: [ { api_name, alert_type, timestamp, detail, response_time_ms }, ... ]
    """
    return jsonify(monitor.get_active_alerts())


@app.route("/api/logs")
def api_logs():
    """
    Returns the 50 most recent log entries from the in-memory buffer.
    Shape: [ { timestamp, api_name, status, response_time_ms, http_code, message }, ... ]
    """
    return jsonify(get_recent_logs(limit=50))


@app.route("/api/history/<api_name>")
def api_history(api_name: str):
    """
    Returns historical check results for a single API (last HISTORY_SIZE checks).
    Shape: [ result_dict, ... ]
    """
    return jsonify(monitor.get_history(api_name))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_info("Integration Monitor starting up …")

    # Run the first check immediately so the dashboard isn't empty on first load
    monitor.run_checks()

    # Start the background polling thread
    monitor.start_background_monitor()

    log_info("Flask server starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
