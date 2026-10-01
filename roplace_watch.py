"""
roplace_watch.py - watches the RoPlace Roblox market and sends a phone
notification (via ntfy.sh) when a new listing matches your settings.

Each run checks the market once and exits. Settings come from environment
variables (GitHub secrets) or settings.py; see config.py.

Run it once with:   python roplace_watch.py
Keep it running:    python run_all.py   (checks both sites every POLL_SECONDS)

Exit codes: 0 = checked OK, 1 = fetch failed, 2 = blocked (403 / Cloudflare),
3 = settings problem.
"""

import json
import os
import sys

import requests

from config import IGNORED, MAX_RATE, NTFY_TOPIC, STATE_DIR, WANTED, describe, find_override

API_URL = "https://api.ro.place/graphql"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

SEEN_FILE = os.path.join(STATE_DIR, "roplace_seen.json")

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (roplace_watch script)",
}

TRIMMED_QUERY = (
    "query fetchExploreData { items { items { itemId name image rap value price "
    "optimizedPrice showFee sellerFee type purchaseToken sellerId } } }"
)

# Used only if the server rejects TRIMMED_QUERY. Paste the full query
# string here (between the quotes) if that ever happens.
FULL_QUERY = ""


class Blocked(Exception):
    """The server returned 403 or a Cloudflare page."""


def load_seen():
    """Returns (set of seen listing ids, whether roplace_seen.json already existed)."""
    if not os.path.exists(SEEN_FILE):
        return set(), False
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f)), True
    except (OSError, ValueError) as e:
        print(f"Could not read {SEEN_FILE} ({e}); starting fresh.")
        return set(), False


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen), f)
    except OSError as e:
        print(f"Could not save {SEEN_FILE}: {e}")


def post_query(query):
    """Returns the parsed JSON response. Raises Blocked on 403 / Cloudflare pages."""
    body = {"operationName": "fetchExploreData", "variables": {}, "query": query}
    response = requests.post(API_URL, json=body, headers=HEADERS, timeout=15)
    text = response.text[:2000].lower()
    if response.status_code == 403 or ("cloudflare" in text and "<html" in text):
        raise Blocked(f"HTTP {response.status_code}: {response.text[:300]!r}")
    if response.status_code >= 500:
        response.raise_for_status()
    return response.json()


def fetch_listings():
    """Returns a list of listing dicts, or None if the request failed."""
    try:
        data = post_query(TRIMMED_QUERY)
        if data.get("errors") or not data.get("data"):
            if not FULL_QUERY:
                print(f"Server rejected the trimmed query: {data.get('errors')}")
                print("Paste the full query into FULL_QUERY in roplace_watch.py.")
                return None
            print("Server rejected the trimmed query; retrying with FULL_QUERY.")
            data = post_query(FULL_QUERY)
        return list(data["data"]["items"]["items"])
    except Blocked:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"Failed to fetch listings: {e}")
        return None


def listing_key(listing):
    # purchaseToken is unique per listing and stayed the same between fetches.
    # itemId + sellerId + price is NOT unique (one seller can list several
    # copies at the same price), so it's only a fallback if the token is missing.
    token = listing.get("purchaseToken")
    if token:
        return str(token)
    return f"{listing.get('itemId')}-{listing.get('sellerId')}-{listing.get('price')}"


def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_listing(listing):
    """Returns (should_alert, reason, rate). rate is None if it couldn't be computed."""
    name = str(listing.get("name", "")).lower()
    ignored = [word for word in IGNORED if word.lower() in name]
    if ignored:
        return False, f"name matches IGNORED ({ignored[0]!r})", None
    # An override keyword alerts even if the item isn't in WANTED, and its
    # rate replaces MAX_RATE. The rate itself is never printed.
    override = find_override(name)
    if override is None and WANTED and not any(word.lower() in name for word in WANTED):
        return False, "name not in WANTED", None
    rap = to_number(listing.get("rap"))
    if not rap:
        return False, "RAP is 0 or missing", None
    price = to_number(listing.get("price"))
    if price is None:
        return False, "price is missing", None
    rate = price / (rap / 1000)
    if override is not None:
        if rate > override:
            return False, f"rate {rate:.2f} > override rate (RATE_OVERRIDES)", rate
        return True, f"rate {rate:.2f} <= override rate (RATE_OVERRIDES)", rate
    if rate > MAX_RATE:
        return False, f"rate {rate:.2f} > MAX_RATE {MAX_RATE}", rate
    return True, f"rate {rate:.2f} <= MAX_RATE {MAX_RATE}", rate


def notify(listing, rate):
    name = str(listing.get("name", "Unknown item"))
    body = (
        f"{name}\n"
        f"Price: ${listing.get('price')}\n"
        f"RAP: {listing.get('rap')}\n"
        f"Rate: {rate:.2f}"
    )
    # HTTP headers can't hold every character (e.g. emoji), so strip any
    # that don't fit. The full name is still in the message body.
    title = "[RoPlace] " + name.encode("latin-1", "ignore").decode("latin-1")
    headers = {"Title": title}
    # Tapping the alert opens this listing (skipped if there's no purchaseToken).
    token = str(listing.get("purchaseToken") or "").strip()
    if token:
        listing_url = f"https://ro.place/item/{token}"
        headers["Click"] = listing_url
        body += f"\n{listing_url}"
    try:
        r = requests.post(
            NTFY_URL,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        print(f"  -> Notified: {name} at ${listing.get('price')}")
    except requests.RequestException as e:
        print(f"  -> Failed to send notification for {name}: {e}")


def main():
    """Checks the market once. Returns the exit code."""
    seen, has_history = load_seen()
    print(f"Checking {API_URL}")
    print(describe())

    try:
        listings = fetch_listings()
    except Blocked as e:
        print(f"RoPlace blocked the request ({e}). Not retrying.")
        return 2
    if listings is None:
        return 1

    new_count = 0
    for listing in listings:
        listing_id = listing_key(listing)
        if listing_id in seen:
            continue
        seen.add(listing_id)
        new_count += 1
        # On the very first run we only record what's there.
        if not has_history:
            continue
        should_alert, reason, rate = check_listing(listing)
        name = listing.get("name", "Unknown item")
        price = listing.get("price")
        if should_alert:
            print(f"  ALERT {name} (${price}, RAP {listing.get('rap')}): {reason}")
            notify(listing, rate)
        else:
            print(f"  skip  {name} (${price}, RAP {listing.get('rap')}): {reason}")

    if not has_history:
        print(f"First run: recorded {len(listings)} existing listings (no alerts sent).")
    else:
        print(f"Checked {len(listings)} listings, {new_count} new")

    # Only rewrite the file when something changed, so git sees no change otherwise.
    if new_count or not has_history:
        save_seen(seen)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
