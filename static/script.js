// script.js
// Dashboard client — polls the Flask JSON API endpoints and renders the UI.
// No framework dependencies; plain fetch() + DOM manipulation.

const REFRESH_INTERVAL_MS = 30_000;  // match server CHECK_INTERVAL_SECONDS

// Track which history tab is selected
let activeHistoryTab = null;


// ── Utility helpers ──────────────────────────────────────────────────────────

/** Map a status string to its CSS class name. */
function statusClass(status) {
  const s = (status || "pending").toLowerCase();
  return ["ok", "slow", "down"].includes(s) ? s : "pending";
}

/** Format a response time value for display. */
function formatRT(ms) {
  if (ms === null || ms === undefined) return '<span class="na">—</span>';
  const cls = ms > 2000 ? "slow" : "ok";
  return `<span class="${cls}-text">${ms} ms</span>`;
}

/** Format an HTTP status code for display. */
function formatCode(code) {
  if (!code) return '<span style="color:var(--text-muted)">—</span>';
  const cls = code === 200 ? "ok-text" : "down-text";
  return `<span class="${cls}">${code}</span>`;
}


// ── Status Cards ─────────────────────────────────────────────────────────────

/** Build one API status card element. */
function buildCard(api, history) {
  const sc    = statusClass(api.status);
  const rtNum = api.response_time_ms;

  // Response time display with colour
  let rtHtml = '<span class="metric-value na">N/A</span>';
  if (rtNum !== null && rtNum !== undefined) {
    const rtCls = rtNum > 2000 ? "slow" : "ok";
    rtHtml = `<span class="metric-value ${rtCls}">${rtNum}</span>
              <span style="color:var(--text-muted);font-size:12px">ms</span>`;
  }

  // HTTP code display
  const codeHtml = api.http_code
    ? `<span class="metric-value ${api.http_code === 200 ? "ok" : "down"}">${api.http_code}</span>`
    : `<span class="metric-value na">N/A</span>`;

  // Sparkline from history (last 10, newest first → reverse to show oldest→newest left→right)
  const bars = buildSparkline([...history].reverse());

  const card = document.createElement("div");
  card.className = `status-card ${sc}`;
  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-name">${api.api_name}</div>
        <div class="card-desc">${api.url}</div>
      </div>
      <span class="status-pill ${sc}">${(api.status || "PENDING").toUpperCase()}</span>
    </div>

    <div class="card-metrics">
      <div class="metric">
        <span class="metric-label">Response Time</span>
        <div style="display:flex;align-items:baseline;gap:4px">${rtHtml}</div>
      </div>
      <div class="metric">
        <span class="metric-label">HTTP Code</span>
        ${codeHtml}
      </div>
    </div>

    ${bars}

    <div class="card-timestamp">
      Last checked: ${api.timestamp || "—"}
      ${api.error ? `<br><span style="color:var(--down);font-size:11px">⚠ ${api.error}</span>` : ""}
    </div>
  `;
  return card;
}

/** Build a mini sparkline showing the last N check statuses. */
function buildSparkline(history) {
  if (!history || history.length === 0) return "";

  // Use response time to set bar height; DOWN = full red bar
  const maxRT = Math.max(...history.map(h => h.response_time_ms || 0), 500);

  const barsHtml = history.map(h => {
    const sc = statusClass(h.status);
    let heightPct = 30; // default for pending / null
    if (h.response_time_ms !== null && h.response_time_ms !== undefined) {
      heightPct = Math.max(15, Math.min(100, (h.response_time_ms / maxRT) * 100));
    }
    if (h.status === "DOWN") heightPct = 100;
    const title = `${h.timestamp} — ${h.status}${h.response_time_ms ? " (" + h.response_time_ms + " ms)" : ""}`;
    return `<div class="spark-bar ${sc}" style="height:${heightPct}%" title="${title}"></div>`;
  }).join("");

  return `
    <div>
      <span class="metric-label">Last ${history.length} checks</span>
      <div class="sparkline" style="margin-top:6px">${barsHtml}</div>
    </div>`;
}


// ── Alerts ───────────────────────────────────────────────────────────────────

function renderAlerts(alerts) {
  const section   = document.getElementById("alerts-section");
  const container = document.getElementById("alerts-container");
  container.innerHTML = "";

  if (!alerts || alerts.length === 0) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");

  alerts.forEach(a => {
    const isDown = a.alert_type === "DOWN";
    const div = document.createElement("div");
    div.className = `alert-card ${isDown ? "" : "slow"}`;
    div.innerHTML = `
      <span class="alert-badge ${isDown ? "" : "slow"}">${a.alert_type}</span>
      <div class="alert-info">
        <div class="alert-name">${a.api_name}</div>
        <div class="alert-detail">${a.detail}${a.response_time_ms ? " — " + a.response_time_ms + " ms" : ""}</div>
      </div>
      <span class="alert-time">${a.timestamp}</span>
    `;
    container.appendChild(div);
  });
}


// ── Logs Table ───────────────────────────────────────────────────────────────

function renderLogs(logs) {
  const tbody = document.getElementById("logs-body");
  const count = document.getElementById("log-count");
  count.textContent = logs.length;

  if (!logs || logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No logs yet</td></tr>`;
    return;
  }

  tbody.innerHTML = logs.map(l => {
    const sc = statusClass(l.status);
    return `
      <tr>
        <td style="color:var(--text-muted);white-space:nowrap;font-size:12px">${l.timestamp}</td>
        <td style="font-weight:600">${l.api_name}</td>
        <td><span class="${sc}-text">${l.status}</span></td>
        <td>${l.response_time_ms !== null && l.response_time_ms !== undefined ? l.response_time_ms : "—"}</td>
        <td>${l.http_code || "—"}</td>
        <td style="color:var(--text-muted);font-size:12px">${l.message || ""}</td>
      </tr>`;
  }).join("");
}


// ── History Tabs & Table ─────────────────────────────────────────────────────

function buildHistoryTabs(apiNames) {
  const container = document.getElementById("history-tabs");

  // Only rebuild tabs if the API names have changed
  const existing = [...container.querySelectorAll(".tab-btn")].map(b => b.dataset.api);
  if (JSON.stringify(existing) === JSON.stringify(apiNames)) return;

  container.innerHTML = "";
  apiNames.forEach((name, i) => {
    const btn = document.createElement("button");
    btn.className = "tab-btn" + (i === 0 ? " active" : "");
    btn.dataset.api = name;
    btn.textContent = name;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeHistoryTab = name;
      fetchHistory(name);
    });
    container.appendChild(btn);
  });

  // Auto-select first tab
  if (!activeHistoryTab && apiNames.length > 0) {
    activeHistoryTab = apiNames[0];
    fetchHistory(apiNames[0]);
  }
}

function renderHistory(history) {
  const tbody = document.getElementById("history-body");

  if (!history || history.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-row">No history yet</td></tr>`;
    return;
  }

  tbody.innerHTML = history.map(h => {
    const sc = statusClass(h.status);
    return `
      <tr>
        <td style="color:var(--text-muted);font-size:12px;white-space:nowrap">${h.timestamp || "—"}</td>
        <td><span class="${sc}-text">${h.status}</span></td>
        <td>${h.response_time_ms !== null && h.response_time_ms !== undefined ? h.response_time_ms + " ms" : "—"}</td>
        <td>${h.http_code || "—"}</td>
      </tr>`;
  }).join("");
}

async function fetchHistory(apiName) {
  try {
    const res  = await fetch(`/api/history/${encodeURIComponent(apiName)}`);
    const data = await res.json();
    renderHistory(data);
  } catch (e) {
    console.error("History fetch error:", e);
  }
}


// ── Main fetch & render cycle ────────────────────────────────────────────────

// Keep history data in memory so sparklines don't require separate round-trips
const historyCache = {};

async function fetchAll() {
  try {
    // Fetch status, alerts, and logs in parallel
    const [statusRes, alertsRes, logsRes] = await Promise.all([
      fetch("/api/status"),
      fetch("/api/alerts"),
      fetch("/api/logs")
    ]);

    const [statuses, alerts, logs] = await Promise.all([
      statusRes.json(),
      alertsRes.json(),
      logsRes.json()
    ]);

    // Build history tabs from the API names
    const apiNames = statuses.map(s => s.api_name);
    buildHistoryTabs(apiNames);

    // Fetch history for all APIs (for sparklines)
    await Promise.all(apiNames.map(async name => {
      try {
        const r = await fetch(`/api/history/${encodeURIComponent(name)}`);
        historyCache[name] = await r.json();
      } catch { historyCache[name] = []; }
    }));

    // Refresh active history tab
    if (activeHistoryTab) {
      renderHistory(historyCache[activeHistoryTab] || []);
    }

    // Render status cards
    const cardsEl = document.getElementById("status-cards");
    cardsEl.innerHTML = "";
    statuses.forEach(api => {
      const card = buildCard(api, historyCache[api.api_name] || []);
      cardsEl.appendChild(card);
    });

    renderAlerts(alerts);
    renderLogs(logs);

    // Update "last updated" timestamp
    document.getElementById("last-updated").textContent =
      "Updated: " + new Date().toLocaleTimeString();

  } catch (err) {
    console.error("Dashboard fetch error:", err);
    document.getElementById("last-updated").textContent = "⚠ Fetch error — retrying…";
  }
}


// ── Boot ─────────────────────────────────────────────────────────────────────
fetchAll();
setInterval(fetchAll, REFRESH_INTERVAL_MS);
