# Study Guide — Integration Monitoring & Alert System
### Prepared for Interview on Integration Specialist Role

---

## 1. What Is This Project?

This project simulates a **hospital integration monitoring system**.

In a real hospital, many systems talk to each other:
- The Electronic Health Record (EHR) sends patient data
- Lab systems return test results
- Government health APIs provide public health data

If any of these connections fail, patient care is at risk. An **Integration Specialist** monitors these connections and responds to failures. This project demonstrates exactly that.

---

## 2. What Problem Does It Solve?

| Problem | Solution in This Project |
|---------|--------------------------|
| How do you know if an external API is down? | Automated health checks every 30 seconds |
| How do you detect slow responses before they become failures? | SLOW status when response > 2000ms |
| How do you keep a record of what happened? | Rotating log file + in-memory buffer |
| How do you get notified of problems? | Alert banner on dashboard |
| How do you share status with the team? | Public dashboard via browser |

---

## 3. The Three APIs — Why These?

### CBS Statistics NL
- **What:** Dutch national statistics bureau
- **Why it fits:** Hospitals consume government population and health statistics for reporting
- **Endpoint:** `https://opendata.cbs.nl/ODataApi/odata/83765NED`

### RIVM Public Health
- **What:** Dutch National Institute for Public Health
- **Why it fits:** Hospitals monitor RIVM data for outbreak alerts, vaccination rates, epidemiology
- **Endpoint:** `https://data.rivm.nl/data/`

### HAPI FHIR Server
- **What:** A public HL7 FHIR R4 test server
- **Why it fits:** **FHIR (Fast Healthcare Interoperability Resources)** is the global standard for exchanging clinical data between hospital systems (EHR, lab, pharmacy). Every modern hospital integration uses FHIR.
- **Endpoint:** `https://hapi.fhir.org/baseR4/metadata`
- **Key point:** Knowing FHIR exists and why it matters shows healthcare IT domain knowledge

---

## 4. Architecture — How the Pieces Fit

```
┌─────────────────────────────────────────────┐
│               EXTERNAL APIs                  │
│   CBS Statistics  |  RIVM  |  HAPI FHIR     │
└──────────────────────┬──────────────────────┘
                       │ HTTP GET (every 30s)
┌──────────────────────▼──────────────────────┐
│              BACKEND (Python)                │
│                                              │
│  config.py   → settings & API list          │
│  monitor.py  → checks, retry, alerts        │
│  logger.py   → file log + memory buffer     │
│  app.py      → Flask web server             │
└──────────────────────┬──────────────────────┘
                       │ JSON responses
┌──────────────────────▼──────────────────────┐
│              FRONTEND (Browser)              │
│  dashboard.html + style.css + script.js     │
│  Auto-refreshes every 30 seconds            │
└─────────────────────────────────────────────┘
```

---

## 5. File by File — What Each Does

### `config.py`
- The **single source of truth** for all settings
- Change the check interval, slow threshold, or add a new API here
- Why important: Clean separation of config from logic — easy to maintain

### `monitor.py`
The heart of the project. Does 4 things:
1. **Health check** — sends HTTP GET to each API, measures time
2. **Retry logic** — if it fails, tries again up to 2 times before marking DOWN
3. **Status classification** — OK / SLOW / DOWN
4. **Alert management** — raises alert on problem, clears it on recovery

### `logger.py`
Two outputs at the same time:
1. **File** (`logs/monitor.log`) — permanent record, rotates at 2MB
2. **Memory** — last 200 entries, served to the dashboard instantly

Why two channels? The file is for audit/history. Memory is for real-time display.

### `app.py`
- Flask web server
- On startup: runs first check immediately, then starts background thread
- Exposes 4 JSON endpoints the dashboard reads from

### `dashboard.html` + `script.js`
- No framework — plain HTML and JavaScript
- Every 30 seconds, `fetch()` calls the Flask API
- Renders: status cards, alert banner, log table, sparkline history

---

## 6. Status Classification Logic

```
HTTP GET request
      │
      ├── Error / Timeout ──► retry (up to 2×) ──► DOWN
      │
      └── Response received
                │
                ├── HTTP code ≠ 200 ──────────────► DOWN
                │
                └── HTTP 200
                          │
                          ├── response > 2000ms ──► SLOW
                          │
                          └── response ≤ 2000ms ──► OK
```

---

## 7. Key Concepts to Know for the Interview

### What is an API health check?
A simple HTTP request sent periodically to verify a system is reachable and responding correctly. The response time and status code tell you whether the system is healthy.

### What is a retry mechanism?
When a request fails, instead of immediately marking the system as down, you try again. This avoids false alarms from temporary network blips. In this project: 2 retries with a 2-second delay.

### What is HL7 FHIR?
**HL7 FHIR** (Fast Healthcare Interoperability Resources) is the international standard for healthcare data exchange. It defines how patient records, lab results, medications, and appointments are structured and shared between hospital systems. It is REST-based (uses HTTP), which makes it similar to standard web APIs.

### What is a rotating log file?
A log file that automatically creates a new file when it reaches a size limit (here: 2MB), keeping the last 5 files. This prevents disk space from filling up while keeping enough history to investigate incidents.

### What is a daemon thread?
A background thread that runs independently of the main program. In this project, the monitoring loop runs in a daemon thread so Flask can serve web requests at the same time without blocking.

### What is thread safety?
When multiple threads access shared data, conflicts can occur. This project uses a `threading.Lock()` to ensure only one thread reads or writes the shared state at a time.

---

## 8. Potential Interview Questions

**Q: Why did you choose these three APIs?**
> CBS and RIVM are realistic sources a Dutch hospital would integrate with for government reporting and public health monitoring. HAPI FHIR represents the clinical integration layer — hospitals use FHIR to connect EHR systems, lab systems, and pharmacy systems. Together they simulate a complete hospital integration landscape.

**Q: How does the retry mechanism work?**
> When a request fails (timeout or connection error), the system waits 2 seconds and retries. It retries up to 2 times. Only after all attempts are exhausted does it mark the API as DOWN. This avoids false alerts from brief network interruptions.

**Q: How would you add a new API to monitor?**
> Just add one entry to the `APIS` list in `config.py`. No other code changes needed.

**Q: How does the alert system work?**
> When an API transitions to SLOW or DOWN, an alert is created and stored. The dashboard reads this and displays a banner. When the API recovers to OK, the alert is automatically cleared. A set called `_alerted` tracks which APIs have active alerts to prevent duplicate alerts.

**Q: What is the difference between the file log and the in-memory log?**
> The file log is permanent — it survives restarts and is used for auditing and post-incident analysis. The in-memory buffer (a Python `deque`) holds the last 200 entries and is served to the dashboard for real-time display. It is faster to read but lost on restart.

**Q: How would you scale this for production?**
> Replace the in-memory state with a database (PostgreSQL or Redis), add authentication to the dashboard, use a proper task scheduler (Celery), deploy behind a production WSGI server (Gunicorn), and containerise with Docker. You could also add email or Slack alerting.

---

## 9. Technical Terms to Use in the Interview

| Term | Meaning in context |
|------|--------------------|
| **Health check** | Periodic request to verify a system is up |
| **Endpoint** | A specific URL that an API exposes |
| **Response time / latency** | How long an API takes to reply |
| **HTTP 200** | Standard success response code |
| **Timeout** | Request abandoned after waiting too long |
| **Retry logic** | Attempt the request again before giving up |
| **Alert** | Notification that something is wrong |
| **Observability** | Ability to understand system state from its outputs |
| **FHIR** | Healthcare data exchange standard |
| **Integration** | Connecting two or more systems to exchange data |
| **Incident** | A period when a system is degraded or unavailable |
| **Uptime** | Percentage of time a system is available |

---

## 10. One-Line Project Summary (for introduction)

> *"I built an integration monitoring dashboard that simulates a hospital IT environment. It continuously checks three healthcare-relevant APIs — CBS, RIVM, and a FHIR server — classifies their health status, triggers alerts on degradation, and displays everything in a live color-coded dashboard with full logging."*
