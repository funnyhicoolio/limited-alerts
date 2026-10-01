# limited-alerts

Watches the Adurite and RoPlace Roblox limited markets and sends a phone
notification through [ntfy](https://ntfy.sh) when a new listing matches your
watchlist and its rate (price in dollars per 1,000 RAP) is at or below `MAX_RATE`.

## On GitHub Actions

`.github/workflows/check.yml` runs both sites every 5 minutes, and you can run
it by hand from **Actions → Check markets → Run workflow**. Tick **Send test
alert** there to just send one test notification (no sites checked, seen
listings untouched). Seen listings are
saved on the `state` branch so each listing only alerts once. The very first
run records what's already listed without alerting.

Settings come from repository secrets (**Settings → Secrets and variables →
Actions → New repository secret**):

| Secret         | Example                                  |
| -------------- | ---------------------------------------- |
| `NTFY_TOPIC`   | `my-long-random-topic-name`              |
| `WANTED_JSON`  | `["punk face", "lipstick"]` (or `[]` for any item) |
| `IGNORED_JSON` | `["bandana"]` (or `[]`)                  |
| `MAX_RATE`     | `6`                                      |
| `RATE_OVERRIDES_JSON` | `{"dominus": 4}` (or `{}`) |

`RATE_OVERRIDES_JSON` gives some items their own max rate: an item whose name
(or Adurite alias) contains a keyword alerts only at that rate or lower, even
if it isn't in `WANTED` and even if `MAX_RATE` is higher. `IGNORED` still wins.

If a site returns 403 or a Cloudflare page, the run says which one and still
checks the other. Blocks are not retried.

## On your own computer

```
pip install -r requirements.txt
copy settings.example.py settings.py     # then edit settings.py
python run_all.py                        # checks both sites every POLL_SECONDS
```

`python adurite_watch.py` or `python roplace_watch.py` checks one site once.
