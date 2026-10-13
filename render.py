import os
import time, json, urllib.request, datetime, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pytz

B = "https://public-as.datapacket.com"
TZ = pytz.timezone("Australia/Sydney")
OUT = os.environ.get("CHART_OUT", "/data/tarkov_au_isp_latency.png")

# Best healthy (lowest non-lost) probe per ISP -> DataPacket Sydney DC (Tarkov host)
# Overridable via env:  ISPS_LOW="Telstra=210.57.5.137,Optus=211.29.152.162"
#                       ISPS_HIGH="iPrimus (Vocus)=203.134.85.40"
def _parse_isps(env, default):
    raw = os.environ.get(env, "").strip()
    if not raw:
        return default
    out = []
    for pair in raw.split(","):
        if not pair.strip():
            continue
        if "=" in pair:
            name, ip = pair.split("=", 1)
        elif ":" in pair:
            name, ip = pair.split(":", 1)
        else:
            raise ValueError(f"bad ISPS entry {pair!r} (want Name=IP)")
        out.append((name.strip(), ip.strip()))
    return out

LOW  = _parse_isps("ISPS_LOW", [("Telstra","210.57.5.137"),("Optus","211.29.152.162"),
                                ("Aussie Broadband","159.196.255.0"),("TPG Telecom","203.12.160.141"),
                                ("Vodafone AU","101.119.57.83")])
HIGH = _parse_isps("ISPS_HIGH", [("iPrimus (Vocus)","203.134.85.40")])
_PALETTE = ["#4cc2ff","#ff7a45","#39d98a","#c58bff","#ff5d8f","#ffd24a","#7ee0e6","#f6a9c0"]
COLORS = {name: _PALETTE[i % len(_PALETTE)] for i, (name, _) in enumerate(LOW + HIGH)}

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())

def _fetch(ip, start, end):
    d = _get(f"{B}/v1/agr/198/{ip}/{start}/{end}?slave=SYD")["data"]
    pts = sorted(((int(k), v) for k, v in d.items()), key=lambda x: x[0])
    dates = [datetime.datetime.fromtimestamp(t, TZ) for t, _ in pts]
    avg = [v["avg"] for _, v in pts]
    win = 5
    sm = [statistics.median(avg[max(0, j - win // 2): j + win // 2 + 1]) for j in range(len(avg))]
    return dates, sm, avg

def _style(ax):
    ax.set_facecolor("#12151c")
    ax.grid(True, color="#2a2f3a", lw=0.6, alpha=0.6)
    ax.tick_params(colors="#c3c9d4", labelsize=9)
    for s in ax.spines.values():
        s.set_color("#3a4150")
    ax.yaxis.label.set_color("#c3c9d4")
    ax.yaxis.label.set_fontsize(11)

def _plot(ax, items, title, start, end, cache):
    ys = []
    for name, ip in items:
        dates, sm, avg = cache[ip]
        c = COLORS[name]
        ax.plot(dates, avg, color=c, lw=0.5, alpha=0.18)
        ax.plot(dates, sm, color=c, lw=1.9, alpha=0.95, label=name)
        ys += sm
    _style(ax)
    ax.set_title(title, color="#e6e9ef", fontsize=11, fontweight="bold", loc="left", pad=8)
    lo, hi = min(ys), max(ys)
    pad = max((hi - lo) * 0.22, 0.6)
    ax.set_ylim(lo - pad, hi + pad)

def build(hours=24):
    now = int(time.time())
    end = now
    start = now - hours * 3600
    cache = {ip: _fetch(ip, start, end) for _, ip in LOW + HIGH}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.4), dpi=150, sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.6], "hspace": 0.12})
    fig.patch.set_facecolor("#12151c")
    _plot(ax1, HIGH, "Higher route", start, end, cache)
    _plot(ax2, LOW, "Low-latency routes", start, end, cache)
    fig.suptitle(os.environ.get("CHART_TITLE",
                 "ISP latency \u2192 DataPacket Sydney DC   \u00b7   Escape from Tarkov (best-in route)"),
                 color="#e6e9ef", fontsize=15, fontweight="bold", x=0.5, y=0.985)
    for ax in (ax1, ax2):
        ax.set_ylabel("Latency (ms)")
        leg = ax.legend(loc="upper right", frameon=True, fontsize=9)
        leg.get_frame().set_facecolor("#1a1f29")
        leg.get_frame().set_edgecolor("#3a4150")
        for t in leg.get_texts():
            t.set_color("#e6e9ef")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TZ))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=3, tz=TZ))
    plt.setp(ax2.get_xticklabels(), rotation=0)

    readings = [(name, round(cache[ip][2][-1], 2)) for name, ip in LOW + HIGH]
    txt = "   ".join(f"{n}  {v:.0f} ms" for n, v in readings)
    gen = time.strftime("%d/%m %H:%M", time.localtime(now))
    fig.text(0.02, 0.028, txt, ha="left", color="#aeb6c4", fontsize=9.5, family="monospace")
    fig.text(0.98, 0.028, f"Last {hours} h \u00b7 AEST \u00b7 updated {gen}",
             ha="right", color="#8a93a5", fontsize=8.5)
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    plt.savefig(OUT, facecolor=fig.get_facecolor())
    plt.close(fig)
    return {"png": OUT, "readings": readings, "generated": gen, "window_hours": hours}

if __name__ == "__main__":
    print(json.dumps(build()))
