"""Render Starship-style heatmaps for every Iran market that has data on disk.
Reads from book_history_{slug}.ndjson (in-progress) or .json (complete)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

DIR = Path("data/raw")


def load_snapshots(path):
    snaps = []
    header = None
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("_type") == "header":
                header = r
            elif r.get("_type") == "snapshot":
                snaps.append(r)
    return header, snaps


def normalize_to_yes(bids, asks):
    """outcome='yes' on prod returns the YES book directly — no flipping needed.
    (The Starship flip workaround was for an old merged-book bug.)"""
    if not bids and not asks: return [], [], None, None
    return (list(bids), list(asks),
            (max(b[0] for b in bids) if bids else None),
            (min(a[0] for a in asks) if asks else None))


def depth_cmap(name, kind):
    """Color encodes depth: faint dark at low depth → bright saturated at high depth.
    'green' for bids, 'red' for asks. Background-transparent at zero."""
    if kind == "bid":
        # transparent → dim green → bright green
        return LinearSegmentedColormap(name, {
            "red":   [(0.0, 0.10, 0.10), (0.5, 0.15, 0.15), (1.0, 0.60, 0.60)],
            "green": [(0.0, 0.15, 0.15), (0.5, 0.55, 0.55), (1.0, 1.00, 1.00)],
            "blue":  [(0.0, 0.10, 0.10), (0.5, 0.20, 0.20), (1.0, 0.55, 0.55)],
            "alpha": [(0.0, 0.00, 0.00), (0.15, 0.55, 0.55), (1.0, 1.00, 1.00)],
        })
    else:
        # transparent → dim red → bright red-orange
        return LinearSegmentedColormap(name, {
            "red":   [(0.0, 0.30, 0.30), (0.5, 0.70, 0.70), (1.0, 1.00, 1.00)],
            "green": [(0.0, 0.10, 0.10), (0.5, 0.20, 0.20), (1.0, 0.55, 0.55)],
            "blue":  [(0.0, 0.10, 0.10), (0.5, 0.15, 0.15), (1.0, 0.40, 0.40)],
            "alpha": [(0.0, 0.00, 0.00), (0.15, 0.55, 0.55), (1.0, 1.00, 1.00)],
        })


BID_RGB = (0.49, 0.91, 0.53)   # for the legend swatch
ASK_RGB = (1.00, 0.48, 0.35)


def render(ndjson_path):
    header, snaps = load_snapshots(ndjson_path)
    slug = header["slug"]
    title = header["title"]
    cond_id = header["condition_id"]
    volume = header.get("volume", 0)

    # Collect unique normalized snapshots
    seen = {}
    for s in snaps:
        dt = s.get("snapshot_dt")
        if not dt or dt in seen:
            continue
        yb, ya, bb, ba = normalize_to_yes(s.get("bids", []), s.get("asks", []))
        if not yb and not ya:
            continue
        # Use the requested timestamp (ms → datetime) as the chart x-coord since
        # snapshot_dt may be a numeric ms string on prod
        ts = datetime.fromtimestamp(s["requested_ms"] / 1000, tz=timezone.utc)
        seen[dt] = {"ts": ts, "yes_bids": yb, "yes_asks": ya, "bb": bb, "ba": ba}

    rows = sorted(seen.values(), key=lambda r: r["ts"])
    if not rows:
        print(f"  no data yet for {slug}")
        return None

    # Build the depth grid on the FULL [0, 1] probability range — same physics
    # as the Starship chart, so sigma=4 produces equivalent blur. Then we
    # zoom the y-axis at display time to focus on the active region.
    mids = [(r["bb"] + r["ba"]) / 2 for r in rows if r["bb"] is not None and r["ba"] is not None]
    spreads = [(r["ba"] - r["bb"]) for r in rows if r["bb"] is not None and r["ba"] is not None]
    if not mids:
        return None
    typical_spread = float(np.median(spreads)) if spreads else 0.01

    # Grid spans the full probability range so the smoothing physics matches
    # Starship's chart exactly (220 bins over [0, 1], sigma=4 ≈ 1.8c blur)
    grid_min, grid_max = 0.0, 1.0
    n_price = 220
    n_time = len(rows)
    bid_grid = np.zeros((n_price, n_time))
    ask_grid = np.zeros((n_price, n_time))

    def to_idx(p):
        return int((p - grid_min) / (grid_max - grid_min) * (n_price - 1))

    # Display y-axis zoom: span the full trajectory of mid + margin, so the
    # whole arc is visible (e.g. 78¢→97¢ pre+post-news). Not just the median.
    mid_lo = float(np.min(mids))
    mid_hi = float(np.max(mids))
    margin = max(typical_spread * 6, 0.03)
    price_min = max(0.0, mid_lo - margin)
    price_max = min(1.02, mid_hi + margin)

    for j, r in enumerate(rows):
        for p, sz in r["yes_bids"]:
            if grid_min <= p <= grid_max:
                bid_grid[to_idx(p), j] += sz
        for p, sz in r["yes_asks"]:
            if grid_min <= p <= grid_max:
                ask_grid[to_idx(p), j] += sz

    bid_grid = np.log1p(bid_grid)
    ask_grid = np.log1p(ask_grid)
    from scipy.ndimage import gaussian_filter
    bid_grid = gaussian_filter(bid_grid, sigma=(3, 1.2))
    ask_grid = gaussian_filter(ask_grid, sigma=(3, 1.2))
    m = max(bid_grid.max(), ask_grid.max(), 1e-9)
    bid_grid /= m; ask_grid /= m

    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=160)
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    times = [r["ts"] for r in rows]
    # extent matches the GRID range so smoothing is positioned correctly;
    # display zoom is applied separately via set_ylim
    extent = [mdates.date2num(times[0]), mdates.date2num(times[-1]), grid_min, grid_max]
    ax.imshow(bid_grid, aspect="auto", origin="lower", extent=extent,
              cmap=depth_cmap("b", "bid"), interpolation="bilinear", vmin=0, vmax=1)
    ax.imshow(ask_grid, aspect="auto", origin="lower", extent=extent,
              cmap=depth_cmap("a", "ask"), interpolation="bilinear", vmin=0, vmax=1)
    ax.set_ylim(price_min, price_max)

    if mids:
        mid_ts = [r["ts"] for r in rows if r["bb"] is not None and r["ba"] is not None]
        ax.plot(mid_ts, mids, color="#7ee787", linewidth=2.0,
                marker="o", markersize=4, alpha=0.95)

    ax.set_xlabel("UTC time", color="#ddd", fontsize=10)
    ax.set_ylabel("YES probability", color="#ddd", fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.tick_params(colors="#bbb")
    for s in ax.spines.values(): s.set_color("#444")

    handles = [
        Patch(facecolor=BID_RGB, edgecolor="none", label="Bids (buy YES) — depth"),
        Patch(facecolor=ASK_RGB, edgecolor="none", label="Asks (sell YES) — depth"),
        Line2D([0],[0], color="#7ee787", linewidth=2, marker="o", markersize=4,
               label="Mid (YES)"),
    ]
    ax.legend(handles=handles, loc="upper left", facecolor="#1a1f29",
              edgecolor="#444", labelcolor="#ddd", fontsize=9)

    fig.text(0.06, 0.955, title[:90], color="#f0f0f0", fontsize=14, fontweight="bold")
    fig.text(0.06, 0.925,
             f"{slug}  ·  vol ${volume:,.0f}  ·  {len(rows)} unique book moments",
             color="#9aa0a6", fontsize=10)
    ax.text(0.5, 0.5, "pmxt.dev", transform=ax.transAxes,
            fontsize=64, fontweight="bold", color="#ffffff", alpha=0.07,
            ha="center", va="center", zorder=10)
    fig.text(0.97, 0.025, "PMXT.dev", color="#ffffff", fontsize=12,
             fontweight="bold", ha="right", va="bottom")

    plt.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.08)
    out = Path("charts") / f"heatmap_{slug}.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}  ({len(rows)} unique snapshots, price {price_min:.2f}-{price_max:.2f})")
    return out


def main():
    ndjson_files = sorted(DIR.glob("book_history_*.ndjson"))
    print(f"Found {len(ndjson_files)} NDJSON files\n")
    for p in ndjson_files:
        try:
            render(p)
        except Exception as e:
            print(f"  ERROR rendering {p.name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
