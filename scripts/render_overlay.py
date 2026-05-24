"""Term-structure overlay — all ceasefire markets on one axis.
Annotates the 14:18 UTC informed-trade move and the 21:50 UTC Trump post."""

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DIR = Path("data/raw")

MARKETS = [
    ("book_history_will-the-iran-ceasefire-continue-through-may-24-733.ndjson",
     "Ceasefire through May 24", "#7ee787"),
    ("book_history_will-the-iran-ceasefire-continue-through-may-27-496.ndjson",
     "Ceasefire through May 27", "#79c0ff"),
    ("book_history_will-the-iran-ceasefire-continue-through-may-31-654-633.ndjson",
     "Ceasefire through May 31", "#ff7a59"),
]


def load_mids(path):
    if not path.exists():
        return [], []
    seen = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("_type") != "snapshot": continue
            dt = r.get("snapshot_dt")
            if dt in seen or not r.get("bids") or not r.get("asks"):
                continue
            bb = max(b[0] for b in r["bids"])
            ba = min(a[0] for a in r["asks"])
            if bb >= ba: continue
            mid = (bb + ba) / 2
            ts = datetime.fromtimestamp(r["requested_ms"] / 1000, tz=timezone.utc)
            seen[dt] = (ts, mid)
    rows = sorted(seen.values())
    return [r[0] for r in rows], [r[1] for r in rows]


plt.rcParams.update({"font.family": "DejaVu Sans"})
fig, ax = plt.subplots(figsize=(13, 7), dpi=160)
fig.patch.set_facecolor("#0e1117")
ax.set_facecolor("#0e1117")

for fname, label, color in MARKETS:
    times, mids = load_mids(DIR / fname)
    if not times: continue
    ax.plot(times, mids, color=color, linewidth=2.2, marker="o",
            markersize=2.5, alpha=0.95, label=f"{label}  ({mids[0]*100:.0f}¢ → {mids[-1]*100:.0f}¢)")

# Annotation markers
FIRST_INFORMED = datetime(2026, 5, 23, 14, 18, 0, tzinfo=timezone.utc)
TRUMP_POST     = datetime(2026, 5, 23, 21, 50, 0, tzinfo=timezone.utc)

ax.axvline(FIRST_INFORMED, color="#ffd866", linestyle="--", linewidth=1.4, alpha=0.85)
ax.annotate("14:18 UTC\nfirst pre-news move\n(+7¢ on May-24 market)",
            xy=(FIRST_INFORMED, 0.55),
            xytext=(8, 0), textcoords="offset points",
            color="#ffd866", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0e1117",
                      edgecolor="#ffd866", linewidth=0.8, alpha=0.92))

ax.axvline(TRUMP_POST, color="#ff7a59", linestyle="--", linewidth=1.4, alpha=0.85)
ax.annotate("21:50 UTC\nTrump Truth Social\n\"largely negotiated\"",
            xy=(TRUMP_POST, 0.45),
            xytext=(8, 0), textcoords="offset points",
            color="#ff7a59", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0e1117",
                      edgecolor="#ff7a59", linewidth=0.8, alpha=0.92))

ax.set_xlabel("UTC time (May 23–24, 2026)", color="#ddd", fontsize=11)
ax.set_ylabel("YES probability (mid)", color="#ddd", fontsize=11)
ax.set_ylim(0.40, 1.02)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
ax.tick_params(colors="#bbb")
for s in ax.spines.values(): s.set_color("#444")
ax.grid(True, alpha=0.12, color="#888")
ax.legend(loc="lower right", facecolor="#1a1f29", edgecolor="#444",
          labelcolor="#ddd", fontsize=10)

fig.text(0.06, 0.955, "Iran ceasefire — term structure response to Trump's May 23 post",
         color="#f0f0f0", fontsize=15, fontweight="bold")
fig.text(0.06, 0.925,
         "Same news, three durations. Longer-dated markets had more room to re-rate.",
         color="#9aa0a6", fontsize=10)

ax.text(0.5, 0.5, "pmxt.dev", transform=ax.transAxes,
        fontsize=64, fontweight="bold", color="#ffffff", alpha=0.06,
        ha="center", va="center", zorder=10)
fig.text(0.97, 0.025, "PMXT.dev", color="#ffffff", fontsize=12,
         fontweight="bold", ha="right", va="bottom")

plt.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.10)
out = Path("charts") / "overlay_ceasefire_term_structure.png"
fig.savefig(out, facecolor=fig.get_facecolor())
print(f"Saved {out.name}")
