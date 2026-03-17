# config.py
# Central configuration for all monitored APIs and system thresholds

APIS = [
    {
        "name": "CBS Statistics NL",
        "url": "https://opendata.cbs.nl/ODataApi/odata/83765NED",
        "description": "Statistics Netherlands — Government data feed"
    },
    {
        "name": "RIVM Public Health",
        "url": "https://data.rivm.nl/data/",
        "description": "Dutch Public Health Institute — Epidemiology & disease data"
    },
    {
        "name": "HAPI FHIR Server",
        "url": "https://hapi.fhir.org/baseR4/metadata",
        "description": "HL7 FHIR R4 — Healthcare interoperability standard"
    }
]

# Response time threshold in milliseconds — above this = SLOW
SLOW_THRESHOLD_MS = 2000

# HTTP request timeout in seconds
TIMEOUT_SECONDS = 10

# How often the background monitor runs (seconds)
CHECK_INTERVAL_SECONDS = 30

# How many times to retry a failed request before marking DOWN
RETRY_ATTEMPTS = 2

# Seconds to wait between retries
RETRY_DELAY_SECONDS = 2

# How many historical check results to keep per API
HISTORY_SIZE = 10

# How many log entries to keep in memory
MAX_LOG_ENTRIES = 200
