"""
run_all.py - runs adurite_watch.py and roplace_watch.py side by side, each in
its own process, with every line labelled [Adurite] or [RoPlace].

    python run_all.py          check both sites every POLL_SECONDS (local use)
    python run_all.py --once   check both sites once and exit (GitHub Actions)

Add --only Adurite or --only RoPlace to check just that site.

If a site blocks us (403 / Cloudflare page), that site is reported and not
tried again while this is running; the other site keeps going.
Ctrl + C stops both. Settings are in settings.py (or GitHub secrets).
"""

import os
import subprocess
import sys
import threading
import time

from config import ON_GITHUB, POLL_SECONDS

SCRIPTS = [
    ("Adurite", "adurite_watch.py"),
    ("RoPlace", "roplace_watch.py"),
]

EXIT_REASONS = {
    0: "checked OK",
    1: "fetch failed (will try again next round)",
    2: "BLOCKED (403 / Cloudflare page); not retrying",
    3: "settings problem; fix settings and restart",
}

HERE = os.path.dirname(os.path.abspath(__file__))

print_lock = threading.Lock()


def say(label, line):
    with print_lock:
        print(f"[{label}] {line}", flush=True)


def pump_output(label, proc):
    """Prints each line the script writes, prefixed with its label."""
    for raw in proc.stdout:
        say(label, raw.rstrip("\r\n"))


def run_round(labels, env):
    """Runs the given scripts at the same time. Returns {label: exit code}."""
    procs = {}
    readers = []
    for label, script in SCRIPTS:
        if label not in labels:
            continue
        proc = subprocess.Popen(
            [sys.executable, "-u", os.path.join(HERE, script)],
            cwd=HERE,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        reader = threading.Thread(target=pump_output, args=(label, proc), daemon=True)
        reader.start()
        procs[label] = proc
        readers.append(reader)
    try:
        codes = {label: proc.wait() for label, proc in procs.items()}
    except KeyboardInterrupt:
        # Ctrl + C reaches the child scripts too; give them a moment to exit
        # on their own, then force any stragglers.
        for proc in procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
        raise
    for reader in readers:
        reader.join(timeout=2)
    return codes


def main():
    args = sys.argv[1:]
    once = "--once" in args
    labels = [label for label, _ in SCRIPTS]
    if "--only" in args:
        i = args.index("--only")
        wanted = args[i + 1].lower() if i + 1 < len(args) else ""
        labels = [label for label in labels if label.lower() == wanted]
        if not labels:
            print(f"--only must be followed by one of: {', '.join(label for label, _ in SCRIPTS)}")
            return 3

    # Item names can contain emoji; make sure they don't crash the output.
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    active = list(labels)
    serious_problem = False

    try:
        while active:
            codes = run_round(active, env)
            for label, code in codes.items():
                reason = EXIT_REASONS.get(code, f"crashed (exit code {code})")
                say("run_all", f"{label}: {reason}")
                if code == 2 and ON_GITHUB:
                    print(f"::warning::{label} blocked the request (403 / Cloudflare). The other site was still checked.")
                if code in (2, 3):
                    active.remove(label)
                if code not in (0, 1, 2):
                    serious_problem = True
            if once:
                break
            if not active:
                say("run_all", "no sites left to check; stopping.")
                break
            if len(active) < len(labels):
                say("run_all", f"still checking: {', '.join(active)}")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        say("run_all", "Ctrl + C received, stopped.")
        return 0

    # A block or a failed fetch isn't the job's fault; a settings problem or a
    # crash is something you need to fix, so fail the run for those.
    return 1 if serious_problem else 0


if __name__ == "__main__":
    sys.exit(main())
