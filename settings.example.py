"""
settings.example.py - copy this file to settings.py and fill in your own
values to run the scripts on your own computer. settings.py is in
.gitignore, so your values never get committed.

On GitHub Actions these come from repository secrets instead (see README.md).
"""

# Only notify for listings whose rate is this or lower.
# Rate = price in dollars per 1,000 RAP (e.g. $12 for a 2,000 RAP item = 6).
MAX_RATE = 6

# Only notify if the item name contains one of these words.
# Leave it empty like this:  WANTED = []  to get alerts for ANY item.
# Example:  WANTED = ["Dominus", "Valkyrie", "Sparkle Time"]
WANTED = []

# Never notify if the item name contains any of these words.
# This wins over WANTED: an item matching both is skipped.
# Example:  IGNORED = ["Cap", "Fedora"]
IGNORED = []

# Your ntfy topic name. Pick something long and hard to guess,
# because anyone who knows the name can read your alerts.
NTFY_TOPIC = "pick-a-long-random-topic-name"

# How many seconds run_all.py waits between checks (local use only).
POLL_SECONDS = 30
