"""Analyze the May-24 ceasefire market for unusual / informed activity."""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data/raw/book_history_will-the-iran-ceasefire-continue-through-may-24-733.ndjson")

snaps = []
with open(DATA) as f:
    for line in f:
        r = json.loads(line)
        if r.get("_type") == "snapshot" and (r.get("bids") or r.get("asks")):
            snaps.append(r)

print(f"Loaded {len(snaps)} snapshots\n")

# Build metrics per snapshot
rows = []
seen_dt = set()
for s in snaps:
    dt = s.get("snapshot_dt")
    if dt in seen_dt: continue
    seen_dt.add(dt)
    bids = s["bids"]; asks = s["asks"]
    if not bids or not asks: continue
    bb = max(b[0] for b in bids); ba = min(a[0] for a in asks)
    if bb >= ba: continue
    mid = (bb + ba) / 2
    spread = ba - bb
    bid_depth_total = sum(b[1] for b in bids)
    ask_depth_total = sum(a[1] for a in asks)
    bid_topN = sum(b[1] for b in sorted(bids, key=lambda x: -x[0])[:5])
    ask_topN = sum(a[1] for a in sorted(asks, key=lambda x: x[0])[:5])
    rows.append({
        "ts": datetime.fromtimestamp(s["requested_ms"] / 1000, tz=timezone.utc),
        "mid": mid, "spread": spread,
        "best_bid": bb, "best_ask": ba,
        "bid_depth_total": bid_depth_total,
        "ask_depth_total": ask_depth_total,
        "bid_top5": bid_topN, "ask_top5": ask_topN,
        "imbalance": (bid_depth_total - ask_depth_total) / (bid_depth_total + ask_depth_total),
    })

rows.sort(key=lambda r: r["ts"])
print(f"Unique snapshots with both sides: {len(rows)}")
print(f"Time range: {rows[0]['ts']} → {rows[-1]['ts']}\n")

# 1. Mid-price moves: find biggest single-step jumps
print("=== Top 15 single-step mid-price moves ===")
moves = []
for i in range(1, len(rows)):
    dmid = rows[i]["mid"] - rows[i-1]["mid"]
    dt_min = (rows[i]["ts"] - rows[i-1]["ts"]).total_seconds() / 60
    moves.append((abs(dmid), dmid, dt_min, rows[i]["ts"], rows[i-1]["mid"], rows[i]["mid"]))
moves.sort(reverse=True)
for absm, dm, dt_min, ts, before, after in moves[:15]:
    print(f"  {ts.isoformat()[:19]}  Δmid {dm:+.4f} over {dt_min:.1f}min  ({before:.3f} → {after:.3f})")

# 2. Pre-news vs post-news comparison (cutoff = May 23 20:00 UTC, when chart shows sharp climb)
NEWS_TS = datetime(2026, 5, 23, 20, 0, 0, tzinfo=timezone.utc)
pre  = [r for r in rows if r["ts"] < NEWS_TS]
post = [r for r in rows if r["ts"] >= NEWS_TS]
print(f"\n=== Pre-news ({len(pre)} snaps before {NEWS_TS}) vs Post-news ({len(post)} snaps) ===")
def stats(label, key, rs):
    vals = [r[key] for r in rs]
    print(f"  {label}.{key}: mean={statistics.mean(vals):.4f}  median={statistics.median(vals):.4f}  "
          f"min={min(vals):.4f}  max={max(vals):.4f}  stdev={statistics.stdev(vals):.4f}")
for key in ["mid", "spread", "bid_depth_total", "ask_depth_total", "imbalance"]:
    stats("pre", key, pre)
    stats("post", key, post)
    print()

# 3. Hourly aggregates — find unusual hours
print("\n=== Hourly aggregates (UTC hour) ===")
print(f"{'hour':<22} {'n':>4} {'avg mid':>8} {'avg spread':>10} {'avg bidDepth':>12} {'avg askDepth':>12} {'imbal':>7}")
buckets = {}
for r in rows:
    key = r["ts"].strftime("%m-%d %H:00")
    buckets.setdefault(key, []).append(r)
for h in sorted(buckets.keys()):
    bs = buckets[h]
    print(f"  {h:<20} {len(bs):>4}  "
          f"{statistics.mean(r['mid'] for r in bs):>7.3f}  "
          f"{statistics.mean(r['spread'] for r in bs):>9.4f}  "
          f"{statistics.mean(r['bid_depth_total'] for r in bs):>11.0f}  "
          f"{statistics.mean(r['ask_depth_total'] for r in bs):>11.0f}  "
          f"{statistics.mean(r['imbalance'] for r in bs):>+6.3f}")

# 4. Identify spread spikes (potential market-maker withdrawal before news)
print("\n=== Spread spikes (top 10) ===")
spread_ranked = sorted(rows, key=lambda r: -r["spread"])
for r in spread_ranked[:10]:
    print(f"  {r['ts'].isoformat()[:19]}  spread={r['spread']:.4f}  mid={r['mid']:.3f}")
