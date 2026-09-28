"""
config.py - loads the settings used by adurite_watch.py and roplace_watch.py.

Each setting comes from an environment variable if it's set (this is how
GitHub Actions passes in your secrets), otherwise from settings.py (for
running on your own computer).

    NTFY_TOPIC    -> NTFY_TOPIC
    WANTED_JSON   -> WANTED   (a JSON list, e.g. ["punk face", "lipstick"])
    IGNORED_JSON  -> IGNORED  (a JSON list)
    MAX_RATE      -> MAX_RATE (a number)
    STATE_DIR     -> folder for seen.json / roplace_seen.json
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    import settings as _local
except ImportError:
    _local = None

ON_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


class ConfigError(Exception):
    pass


def _env(name):
    # GitHub turns a missing secret into an empty string, so treat "" as unset.
    value = os.environ.get(name, "").strip()
    return value or None


def _json_list(env_name, local_name):
    raw = _env(env_name)
    if raw is None:
        return list(getattr(_local, local_name, []))
    try:
        value = json.loads(raw)
    except ValueError as e:
        raise ConfigError(f"{env_name} is not valid JSON ({e}). Example: [\"punk face\", \"lipstick\"]")
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{env_name} must be a JSON list of strings, e.g. [\"punk face\", \"lipstick\"]")
    return value


def _load():
    topic = _env("NTFY_TOPIC") or getattr(_local, "NTFY_TOPIC", None)
    if not topic:
        raise ConfigError("No ntfy topic: set the NTFY_TOPIC secret, or NTFY_TOPIC in settings.py.")

    raw_rate = _env("MAX_RATE")
    if raw_rate is None:
        max_rate = getattr(_local, "MAX_RATE", 6)
    else:
        try:
            max_rate = float(raw_rate)
        except ValueError:
            raise ConfigError(f"MAX_RATE must be a number like 6 or 5.5, not {raw_rate!r}")

    return (
        topic,
        _json_list("WANTED_JSON", "WANTED"),
        _json_list("IGNORED_JSON", "IGNORED"),
        max_rate,
    )


try:
    NTFY_TOPIC, WANTED, IGNORED, MAX_RATE = _load()
except ConfigError as e:
    print(f"Settings problem: {e}")
    sys.exit(3)

POLL_SECONDS = getattr(_local, "POLL_SECONDS", 30)
STATE_DIR = _env("STATE_DIR") or HERE


def describe():
    """One line summarising the settings, safe to print in public GitHub logs."""
    if ON_GITHUB:
        # Actions logs on a public repo are public: don't reveal the topic or lists.
        return f"MAX_RATE = {MAX_RATE}, WANTED = {len(WANTED)} words, IGNORED = {len(IGNORED)} words (from secrets)"
    return f"MAX_RATE = {MAX_RATE}, WANTED = {WANTED or 'anything'}, IGNORED = {IGNORED or 'nothing'}, topic = {NTFY_TOPIC}"
