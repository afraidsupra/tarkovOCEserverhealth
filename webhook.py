#!/usr/bin/env python
"""Discord webhook posting for the Tarkov Sydney ISP latency graph.

Strategy: DELETE the previous live message (if we have its id), then POST
exactly one fresh message with the new image. Rationale (learned the hard
way): a webhook PATCH edit STACKS a new image on top of the old one, and
sending `attachments: []` to clear them is rejected (HTTP 400). Delete+post
guarantees the channel always shows exactly one, latest-only graph.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from render import OUT, build  # noqa: F401 (re-export OUT for app)

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
STATE_PATH = os.path.join(os.environ.get("STATE_DIR", "/data"), "state.json")
USERNAME = os.environ.get("BOT_NAME", "Tarkov SYD latency")
HOURS = int(os.environ.get("HOURS", "24"))
USER_AGENT = "Mozilla/5.0 (compatible; TarkovLatencyBot/1.0)"


def _req(method, url, *, headers=None, data=None, files=None, timeout=60):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)
    if files is not None:
        boundary = "----tarkov" + str(int(time.time()))
        body = b""
        if data is not None:
            for k, v in data.items():
                body += (f"--{boundary}\r\n"
                         f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                         f"{v}\r\n").encode()
        for name, path, filename in files:
            with open(path, "rb") as f:
                content = f.read()
            body += (f"--{boundary}\r\n"
                     f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                     "Content-Type: image/png\r\n\r\n").encode()
            body += content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
    else:
        payload = json.dumps(data).encode() if data is not None else None
        headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and raw.strip()[:1] in b"{[" else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def _load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(d):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(d, f)
    except Exception as e:
        print(f"[warn] could not persist state: {e}", file=sys.stderr)


def content_line(info):
    rd = "  ".join(f"{n} {v:.0f}ms" for n, v in info["readings"])
    return (f"{rd}\n"
            f"Updated {info['generated']} AEST \u00b7 last {info['window_hours']}h \u00b7 "
            f"DataPacket Sydney DC \u00b7 best-in route")


def run_once(verbose=False):
    if os.environ.get("DRY_RUN") == "1":
        info = build(HOURS)
        if verbose:
            print(json.dumps({"mode": "dry_run", "png": OUT,
                              "readings": info["readings"], "generated": info["generated"]}))
        return True

    if not WEBHOOK:
        print("ERROR: DISCORD_WEBHOOK_URL is not set", file=sys.stderr)
        return False

    info = build(HOURS)
    text = content_line(info)
    old_id = _load_state().get("message_id")

    if old_id:
        dstatus, _ = _req("DELETE", f"{WEBHOOK}/messages/{old_id}")
        if dstatus not in (200, 204):
            print(f"[warn] delete of {old_id} -> {dstatus} (ignored)", file=sys.stderr)
            if verbose:
                print(f"[warn] delete of {old_id} -> {dstatus} (ignored)")

    status, body = _req("POST", f"{WEBHOOK}?wait=true",
                        data={"username": USERNAME, "content": text},
                        files=[("files[]", OUT, os.path.basename(OUT))])
    new_id = body.get("id") if isinstance(body, dict) else None
    if status in (200, 201) and new_id:
        _save_state({"message_id": new_id, "updated": int(time.time())})
        if verbose:
            print(json.dumps({"mode": "delete+post", "status": status,
                              "message_id": new_id, "readings": info["readings"],
                              "generated": info["generated"]}))
        return True

    status2, _ = _req("POST", WEBHOOK,
                      data={"username": USERNAME, "content": text},
                      files=[("files[]", OUT, os.path.basename(OUT))])
    if status2 == 204:
        if verbose:
            print(json.dumps({"mode": "post204", "status": 204,
                              "readings": info["readings"],
                              "generated": info["generated"]}))
        return True

    if verbose:
        print(json.dumps({"error": "all attempts failed", "new": status}))
    return False


if __name__ == "__main__":
    ok = run_once(verbose=True)
    sys.exit(0 if ok else 1)
