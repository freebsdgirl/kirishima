import os

ROLLING_BUFFER_DB               = "./shared/db/brain/rolling_buffer.db"

DEFAULT_MEMORY_PRIORITY         = 0.5

# Threshold for triggering message summarization when the channel is active
SUMMARIZE_THRESHOLD_ACTIVE      = 40

# Number of messages to process in a single summarization batch
SUMMARIZE_CHUNK_SIZE            = 20

# Defines the time threshold (in minutes) to determine channel inactivity
IDLE_THRESHOLD_MINUTES          = 5

# Defines the minimum number of messages required to consider a channel as active
DENSITY_THRESHOLD_LINES         = 10

# Defines the time window in minutes to evaluate message density for channel activity determination
DENSITY_THRESHOLD_MINUTES       = 20 

# guardrails against a conversation being marked inactive too soon
LAST_SUMMARY_TIMESTAMP_FILE     = "/tmp/last_summary_run.txt"
MIN_SUMMARY_INTERVAL_SECONDS    = 300  # 5 minutes




# Configure the proxy URL from environment variables.
PROXY_HOST                              = os.getenv("PROXY_HOST", "proxy")
PROXY_PORT                              = os.getenv("PROXY_PORT", "4205")
PROXY_URL                               = os.getenv("PROXY_URL", f"http://{PROXY_HOST}:{PROXY_PORT}")

# database for mode status
STATUS_DB                               = "./shared/db/brain/status.db"
