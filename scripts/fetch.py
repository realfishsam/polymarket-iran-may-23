"""
Iran multi-market fetcher — literally fetch_starship_data.py looped over a
hand-picked list of high-volume markets.

Same call shape that produced the Starship hero chart:
  poly.fetch_order_book(condition_id, params={"since": ms, "outcome": "yes"})

For each market:
  - fetch_market(slug) → grab conditionId
  - pull ±N hours of book snapshots, paced at 85 req/min
  - stream each snapshot to book_history_{slug}.ndjson (live progress)
  - write book_history_{slug}.json at the end (for the renderer)

Run:
  PMXT_API_KEY='pmxt_...' python3 fetch_iran_books.py
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pmxt

# Per-call hard timeout for fetch_order_book — prevents the run from hanging
# indefinitely on a single non-responsive API call.
CALL_TIMEOUT_SEC = 15
_executor = ThreadPoolExecutor(max_workers=1)


def call_with_timeout(fn, *args, **kwargs):
    fut = _executor.submit(fn, *args, **kwargs)
    return fut.result(timeout=CALL_TIMEOUT_SEC)

# ----------------------------------------------------------------------------
# CONFIG — hand-picked subset, highest volume + most narratively useful
# ----------------------------------------------------------------------------

SLUGS = [
    # Ceasefire term structure — these are THE news-reactive markets
    # for the May 23 Trump 60-day ceasefire announcement
    "will-the-iran-ceasefire-continue-through-may-24-733",       # today's deadline
    "will-the-iran-ceasefire-continue-through-may-27-496",       # +3d
    "will-the-iran-ceasefire-continue-through-may-31-654-633",   # +1w
    "will-the-iran-ceasefire-continue-through-june-30-529-427",  # +1mo
    "will-the-iran-ceasefire-continue-through-december-31-395-943",  # +6mo
    # Peace-deal term structure — same story, longer horizon
    "us-x-iran-permanent-peace-deal-by-may-31-2026-333-871-241-192-799-449-125",  # $47M
    "us-x-iran-permanent-peace-deal-by-june-30-2026-837-641-896-877-363-892-537",
    # One regime-fall as a "didn't move" counterpoint
    "will-the-iranian-regime-fall-by-june-30",
]

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_HOURS    = 36    # last 36h — covers the May 23 ceasefire announcement
EVERY_SECONDS   = 180   # snapshot every 3 min (≈ 720 per market, ~8 min each)
RATE_PER_MIN    = 85    # safely under 100/min cap
RETRIES         = 1

# ----------------------------------------------------------------------------

key = os.environ.get("PMXT_API_KEY")
if not key:
    sys.exit("ERROR: set PMXT_API_KEY env var first.")
poly = pmxt.Polymarket(pmxt_api_key=key)

INTERVAL = 60.0 / RATE_PER_MIN
_last = [0.0]
def paced(fn, *a, **kw):
    s = (_last[0] + INTERVAL) - time.time()
    if s > 0: time.sleep(s)
    _last[0] = time.time()
    return fn(*a, **kw)


def lookup(slug):
    """Same as fetch_starship_data.py — multiple call-shape attempts."""
    for fn in [
        lambda: poly.fetch_market(slug=slug),
        lambda: poly.fetch_market(params={"slug": slug}),
        lambda: poly.fetch_market(slug),
    ]:
        try:
            return paced(fn)
        except Exception:
            continue
    raise RuntimeError(f"fetch_market failed for {slug!r}")


def fetch_book(cond, ts):
    requested_ms = int(ts.timestamp() * 1000)
    params = {"since": requested_ms, "outcome": "yes"}
    for attempt in range(RETRIES + 1):
        try:
            # Pace + timeout. paced() runs the call inside a worker thread so
            # we can enforce a hard timeout if the API hangs.
            sleep_for = (_last[0] + INTERVAL) - time.time()
            if sleep_for > 0: time.sleep(sleep_for)
            _last[0] = time.time()
            book = call_with_timeout(poly.fetch_order_book, cond, params=params)
            # Prod OrderBook has `.timestamp` (ms) but not always `.dt`. Defensive.
            dt = getattr(book, "dt", None)
            ts_ms = getattr(book, "timestamp", None)
            snapshot_dt = str(dt) if dt else (str(ts_ms) if ts_ms else None)
            return {
                "requested_ms": requested_ms,
                "requested_iso": ts.isoformat(),
                "snapshot_dt": snapshot_dt,
                "snapshot_ts_ms": ts_ms,
                "bids": [[lv.price, lv.size] for lv in book.bids],
                "asks": [[lv.price, lv.size] for lv in book.asks],
            }
        except Exception as e:
            if attempt < RETRIES:
                time.sleep(2.0)
                continue
            return {
                "requested_ms": requested_ms,
                "requested_iso": ts.isoformat(),
                "snapshot_dt": None,
                "bids": [], "asks": [],
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }


def run_market(slug):
    print(f"\n=== {slug} ===")
    try:
        m = lookup(slug)
    except Exception as e:
        print(f"  lookup failed: {e}")
        return
    cond = m.contract_address
    print(f"  title:    {m.title}")
    print(f"  cond_id:  {cond}")
    print(f"  volume:   ${m.volume:,.0f}")
    print(f"  status:   {m.status}")

    end   = datetime.now(tz=timezone.utc)
    start = end - timedelta(hours=WINDOW_HOURS)
    timestamps = []
    t = start
    while t <= end:
        timestamps.append(t)
        t += timedelta(seconds=EVERY_SECONDS)
    print(f"  pulling {len(timestamps)} snapshots from {start.isoformat()} → {end.isoformat()}")

    ndjson_path = OUTPUT_DIR / f"book_history_{slug}.ndjson"
    json_path   = OUTPUT_DIR / f"book_history_{slug}.json"

    # Resume: load any snapshots already on disk and skip past their indices.
    snaps = []
    completed_indices = set()
    if ndjson_path.exists():
        with open(ndjson_path) as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("_type") == "snapshot":
                    snaps.append(r)
                    completed_indices.add(r["i"])
        if snaps:
            print(f"  resuming — {len(snaps)} snapshots already on disk")

    if not snaps:
        with open(ndjson_path, "w") as fh:
            fh.write(json.dumps({"_type": "header", "slug": slug, "condition_id": cond,
                                 "title": m.title, "volume": m.volume,
                                 "started_at": datetime.now(tz=timezone.utc).isoformat()}) + "\n")

    t0 = time.time()
    n_ok = sum(1 for s in snaps if s.get("bids") or s.get("asks"))
    for i, ts in enumerate(timestamps):
        if i in completed_indices:
            continue
        s = fetch_book(cond, ts)
        snaps.append(s)
        with open(ndjson_path, "a") as fh:
            fh.write(json.dumps({"_type": "snapshot", "i": i, **s}) + "\n"); fh.flush()
        if s.get("bids") or s.get("asks"):
            n_ok += 1
        if (i + 1) % 20 == 0 or (i + 1) == len(timestamps):
            print(f"    {i+1:>4}/{len(timestamps)}  ok={n_ok:>3}  "
                  f"{time.time() - t0:5.1f}s elapsed")

    unique_dts = len({s["snapshot_dt"] for s in snaps if s.get("snapshot_dt")})
    payload = {
        "meta": {
            "slug": slug, "condition_id": cond, "title": m.title,
            "volume": m.volume, "status": m.status,
            "window_hours": WINDOW_HOURS, "every_seconds": EVERY_SECONDS,
            "n_snapshots": len(snaps), "n_with_data": n_ok, "unique_dts": unique_dts,
        },
        "snapshots": snaps,
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"  done in {(time.time() - t0)/60:.1f} min — {n_ok}/{len(snaps)} OK, {unique_dts} unique dts")


def main():
    print(f"Fetching {len(SLUGS)} markets, {WINDOW_HOURS}h windows, "
          f"every {EVERY_SECONDS}s, at {RATE_PER_MIN} req/min")
    print(f"Estimated: ~{len(SLUGS) * (WINDOW_HOURS * 3600 / EVERY_SECONDS) / RATE_PER_MIN:.0f} min total")

    t0 = time.time()
    for slug in SLUGS:
        run_market(slug)
    print(f"\nAll done in {(time.time() - t0)/60:.1f} min")


if __name__ == "__main__":
    main()
