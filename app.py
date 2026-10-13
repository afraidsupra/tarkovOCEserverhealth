#!/usr/bin/env python
"""Tarkov OCE server health — ISP latency refresher.

Modes:
  app.py          loop: refresh every REFRESH_INTERVAL seconds (default 1800)
  app.py --once   single refresh (for cron/systemd)
  app.py --health healthcheck (exits 0 if last run succeeded)
"""
import json
import os
import signal
import sys
import time

from webhook import STATE_PATH, run_once

INTERVAL = max(60, int(os.environ.get("REFRESH_INTERVAL", "1800")))


def healthy():
    try:
        with open(STATE_PATH) as f:
            st = json.load(f)
        return bool(st.get("message_id")) and \
            (time.time() - int(st.get("updated", 0))) < INTERVAL * 2
    except Exception:
        return False


def main():
    if "--once" in sys.argv:
        ok = run_once(verbose=True)
        sys.exit(0 if ok else 1)

    if "--health" in sys.argv:
        sys.exit(0 if healthy() else 1)

    stop = {"flag": False}

    def _sig(signum, frame):
        stop["flag"] = True
        print(f"[info] got signal {signum}, shutting down", file=sys.stderr)

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    print(f"[info] tarkov-latency loop starting: every {INTERVAL}s "
          f"(state: {STATE_PATH})")
    while not stop["flag"]:
        t0 = time.time()
        try:
            run_once(verbose=False)
        except Exception as e:
            print(f"[error] refresh failed: {e}", file=sys.stderr)
        # sleep in small steps so SIGTERM is responsive
        slept = 0.0
        while slept < INTERVAL and not stop["flag"]:
            time.sleep(1)
            slept += 1
    print("[info] loop stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
