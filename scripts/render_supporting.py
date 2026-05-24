"""Five supporting charts for the Iran ceasefire post.
All use the same dark/pmxt.dev styling.

  1. extras_timeline_with_news.png         — overlay + news annotations
  2. extras_cumulative_price_discovery.png — % of move priced in over time
  3. extras_regime_fall_counter.png        — ceasefire vs regime-fall (control)
  4. extras_imbalance_with_baseline.png    — bid/ask imbalance vs baseline band
  5. extras_spread_and_depth.png           — 2-panel microstructure response
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

DIR = Path("data/raw")

# ---- styling primitives ---------------------------------------------------

DARK_BG    = "#0e1117"
PANEL_BG   = "#1a1f29"
TEXT_LIGHT = "#ddd"
TEXT_MID   = "#9aa0a6"
SPINE_DARK = "#444"
GREEN_HI   = "#7ee787"
BLUE_HI    = "#79c0ff"
ORANGE_HI  = "#ff7a59"
YELLOW_HI  = "#ffd866"


def style_axes(ax):
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors="#bbb")
    for s in ax.spines.values():
        s.set_color(SPINE_DARK)
    ax.grid(True, alpha=0.12, color="#888")


def brand(fig, ax, title, subtitle):
    fig.patch.set_facecolor(DARK_BG)
    fig.text(0.06, 0.955, title, color="#f0f0f0", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.925, subtitle, color=TEXT_MID, fontsize=10)
    ax.text(0.5, 0.5, "pmxt.dev", transform=ax.transAxes,
            fontsize=64, fontweight="bold", color="#ffffff", alpha=0.06,
            ha="center", va="center", zorder=10)
    fig.text(0.97, 0.025, "PMXT.dev", color="#ffffff", fontsize=12,
             fontweight="bold", ha="right", va="bottom")


def note_bbox(border):
    return dict(boxstyle="round,pad=0.35", facecolor=DARK_BG,
                edgecolor=border, linewidth=0.8, alpha=0.92)


# ---- data loader ----------------------------------------------------------

def load_snapshots(path):
    seen = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("_type") != "snapshot":
                continue
            dt = r.get("snapshot_dt")
            if dt in seen or not r.get("bids") or not r.get("asks"):
                continue
            bb = max(b[0] for b in r["bids"])
            ba = min(a[0] for a in r["asks"])
            if bb >= ba:
                continue
            ts = datetime.fromtimestamp(r["requested_ms"] / 1000, tz=timezone.utc)
            seen[dt] = {
                "ts": ts, "bb": bb, "ba": ba, "mid": (bb + ba) / 2,
                "spread": ba - bb,
                "bid_dep": sum(b[1] for b in r["bids"]),
                "ask_dep": sum(a[1] for a in r["asks"]),
            }
    rows = sorted(seen.values(), key=lambda r: r["ts"])
    return rows


# ---- canonical events for annotations -------------------------------------

EVENTS = [
    (datetime(2026, 5, 23, 13, 33, tzinfo=timezone.utc),
     "CENTCOM tweets blockade milestone", "#888"),
    (datetime(2026, 5, 23, 14, 23, tzinfo=timezone.utc),
     "Rubio: \"good news in the next few hours\"", "#79c0ff"),
    (datetime(2026, 5, 23, 14, 55, tzinfo=timezone.utc),
     "Pakistan ISPR statement", "#79c0ff"),
    (datetime(2026, 5, 23, 15, 29, tzinfo=timezone.utc),
     "Axios EXCLUSIVE: \"50/50\"", "#79c0ff"),
    (datetime(2026, 5, 23, 17, 30, tzinfo=timezone.utc),
     "Washington Times: draft within 24h", "#79c0ff"),
    (datetime(2026, 5, 23, 18, 14, tzinfo=timezone.utc),
     "Axios: gaps focused on 'wording'", "#79c0ff"),
    (datetime(2026, 5, 23, 21, 50, tzinfo=timezone.utc),
     "TRUMP TRUTH SOCIAL: \"largely negotiated\"", ORANGE_HI),
]
FIRST_MOVE = datetime(2026, 5, 23, 14, 18, tzinfo=timezone.utc)


# ---- 1. timeline + news annotations ---------------------------------------

def chart_timeline_with_news(rows_24, rows_27, rows_31):
    fig, ax = plt.subplots(figsize=(14, 8), dpi=160)

    for rows, label, color in [
        (rows_24, "May 24", GREEN_HI),
        (rows_27, "May 27", BLUE_HI),
        (rows_31, "May 31", ORANGE_HI),
    ]:
        if not rows:
            continue
        ax.plot([r["ts"] for r in rows], [r["mid"] for r in rows],
                color=color, linewidth=2.0, alpha=0.95,
                label=f"Ceasefire through {label}")

    # First-move marker — gold, prominent
    ax.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--",
               linewidth=1.8, alpha=0.95)
    ax.annotate("14:18 UTC\nfirst pre-news move",
                xy=(FIRST_MOVE, 0.55), xytext=(8, 0), textcoords="offset points",
                color=YELLOW_HI, fontsize=11, fontweight="bold",
                bbox=note_bbox(YELLOW_HI))

    # News events — thin vertical lines only, no inline labels.
    # Labels go in a clean legend-style box in the corner so nothing overlaps.
    for ts, label, color in EVENTS:
        ax.axvline(ts, color=color, linestyle=":", linewidth=1.0, alpha=0.5)
    # Final Trump-post line gets its own bigger marker
    ax.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
               linewidth=1.8, alpha=0.95)
    ax.annotate("21:50 UTC\nTrump Truth Social",
                xy=(EVENTS[-1][0], 0.55), xytext=(8, 0),
                textcoords="offset points",
                color=ORANGE_HI, fontsize=11, fontweight="bold",
                bbox=note_bbox(ORANGE_HI))

    # News legend in the upper-left
    news_text = "Public Iran news (May 23 UTC):\n"
    for ts, label, _ in EVENTS:
        news_text += f"  {ts.strftime('%H:%M')}  {label}\n"
    ax.text(0.01, 0.98, news_text.strip(),
            transform=ax.transAxes,
            color=TEXT_LIGHT, fontsize=8.5, family="monospace",
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=PANEL_BG,
                      edgecolor=SPINE_DARK, alpha=0.92))

    style_axes(ax)
    ax.set_xlabel("UTC time (May 23–24, 2026)", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylabel("YES probability (mid)", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylim(0.40, 1.02)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend(loc="lower right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
              labelcolor=TEXT_LIGHT, fontsize=10)

    brand(fig, ax,
          "The market moved before every public Iran headline",
          "Polymarket ceasefire markets vs. timestamped news, May 23–24, 2026")
    plt.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.08)
    out = Path("charts") / "extras_timeline_with_news.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}")


# ---- 2. cumulative price discovery ----------------------------------------

def chart_cumulative_discovery(rows_24):
    if len(rows_24) < 10:
        print("  skipping cumulative — not enough data")
        return
    start_mid = rows_24[0]["mid"]
    end_mid   = rows_24[-1]["mid"]
    total_move = end_mid - start_mid
    if abs(total_move) < 0.01:
        print("  skipping cumulative — no total move")
        return
    pct = [(r["ts"], (r["mid"] - start_mid) / total_move * 100) for r in rows_24]

    fig, ax = plt.subplots(figsize=(13, 7), dpi=160)
    times_p = [p[0] for p in pct]
    vals_p  = [p[1] for p in pct]
    # Fill positive in green above 0, negative in red below — makes the
    # asymmetry obvious at a glance
    ax.fill_between(times_p, vals_p, 0, where=[v >= 0 for v in vals_p],
                    interpolate=True, color=GREEN_HI, alpha=0.25)
    ax.fill_between(times_p, vals_p, 0, where=[v < 0 for v in vals_p],
                    interpolate=True, color=ORANGE_HI, alpha=0.30)
    ax.plot(times_p, vals_p, color=GREEN_HI, linewidth=2.4, alpha=0.95,
            label="% of total May 23–24 move priced in")
    ax.axhline(100, color=YELLOW_HI, linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axhline(0,   color=TEXT_MID,  linestyle="-", linewidth=1.0, alpha=0.7)

    # Trump-post marker + the "85% done" annotation
    ax.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
               linewidth=1.6, alpha=0.95)
    # Find pct value at Trump post time
    trump_pct = None
    for ts, p in pct:
        if ts >= EVENTS[-1][0]:
            trump_pct = p
            break
    if trump_pct is not None:
        ax.scatter([EVENTS[-1][0]], [trump_pct], s=80, color=ORANGE_HI,
                   edgecolor="#1a1f29", linewidth=1.5, zorder=6)
        ax.annotate(f"By Trump's post, the market was\n"
                    f"already {trump_pct:.0f}% of the way to final price",
                    xy=(EVENTS[-1][0], trump_pct),
                    xytext=(-260, -10), textcoords="offset points",
                    color=ORANGE_HI, fontsize=11, fontweight="bold",
                    bbox=note_bbox(ORANGE_HI),
                    arrowprops=dict(arrowstyle="->", color=ORANGE_HI, lw=1.2, alpha=0.85))

    ax.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--", linewidth=1.4, alpha=0.85)
    ax.annotate("14:18 UTC\nfirst pre-news move",
                xy=(FIRST_MOVE, 10), xytext=(8, 0),
                textcoords="offset points",
                color=YELLOW_HI, fontsize=10, fontweight="bold",
                bbox=note_bbox(YELLOW_HI))

    style_axes(ax)
    ax.set_xlabel("UTC time", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylabel("% of total move priced in", color=TEXT_LIGHT, fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    # Auto-fit y-axis with a small margin
    v_min, v_max = min(vals_p), max(vals_p)
    pad = (v_max - v_min) * 0.08
    ax.set_ylim(v_min - pad, v_max + pad)
    ax.legend(loc="lower right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
              labelcolor=TEXT_LIGHT, fontsize=10)
    brand(fig, ax,
          "By the time the news hit, the market was already done",
          "Cumulative price discovery — Iran ceasefire (May 24 market)")
    plt.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.10)
    out = Path("charts") / "extras_cumulative_price_discovery.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}")


# ---- 3. regime-fall counter-evidence --------------------------------------

def chart_regime_fall_counter(rows_24, rows_regime):
    if not rows_regime:
        print("  skipping regime-fall — no data")
        return
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), dpi=160, sharex=True)

    ax1.plot([r["ts"] for r in rows_24], [r["mid"] for r in rows_24],
             color=GREEN_HI, linewidth=2.0, alpha=0.95,
             label="Iran ceasefire through May 24 — REACTED")
    ax1.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--",
                linewidth=1.4, alpha=0.85)
    ax1.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
                linewidth=1.4, alpha=0.85)
    ax1.set_ylabel("YES (ceasefire)", color=TEXT_LIGHT, fontsize=10)
    ax1.set_ylim(0.65, 1.02)
    ax1.legend(loc="lower right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
               labelcolor=TEXT_LIGHT, fontsize=10)
    style_axes(ax1)

    ax2.plot([r["ts"] for r in rows_regime], [r["mid"] for r in rows_regime],
             color=ORANGE_HI, linewidth=2.0, alpha=0.95,
             label="Will the Iranian regime fall by June 30? — UNAFFECTED")
    ax2.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--",
                linewidth=1.4, alpha=0.85)
    ax2.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
                linewidth=1.4, alpha=0.85)
    ax2.set_ylabel("YES (regime fall)", color=TEXT_LIGHT, fontsize=10)
    ax2.set_ylim(0, max(0.06, max(r["mid"] for r in rows_regime) * 1.2))
    ax2.set_xlabel("UTC time (May 23–24, 2026)", color=TEXT_LIGHT, fontsize=11)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax2.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
               labelcolor=TEXT_LIGHT, fontsize=10)
    style_axes(ax2)

    brand(fig, ax1,
          "Specificity check: only the ceasefire markets reacted",
          "The 14:18 informed move was about ceasefire, not general Iran sentiment")
    plt.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.08, hspace=0.05)
    out = Path("charts") / "extras_regime_fall_counter.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}")


# ---- 4. imbalance with baseline band --------------------------------------

def chart_imbalance(rows):
    if len(rows) < 50:
        print("  skipping imbalance — not enough data")
        return
    imbs = [(r["ts"], (r["bid_dep"] - r["ask_dep"]) / (r["bid_dep"] + r["ask_dep"]))
            for r in rows]
    baseline_end = datetime(2026, 5, 23, 13, 0, tzinfo=timezone.utc)
    baseline = [v for ts, v in imbs if ts < baseline_end]
    if len(baseline) < 5:
        print("  skipping imbalance — no baseline data")
        return
    b_mean = statistics.mean(baseline)
    b_std  = statistics.stdev(baseline)

    fig, ax = plt.subplots(figsize=(13, 7), dpi=160)
    ts_all = [t for t, _ in imbs]
    v_all  = [v for _, v in imbs]

    # Baseline band — clearer with brighter shade
    ax.axhspan(b_mean - b_std, b_mean + b_std, color=BLUE_HI,
               alpha=0.18, label=f"Normal range (baseline ±1σ, pre-13:00 UTC)")
    ax.axhline(b_mean, color=BLUE_HI, linestyle="-", linewidth=1.0, alpha=0.5)

    # Highlight the pre-news breakout window (14:00–17:00 UTC) in yellow
    breakout_start = datetime(2026, 5, 23, 14, 0, tzinfo=timezone.utc)
    breakout_end   = datetime(2026, 5, 23, 17, 0, tzinfo=timezone.utc)
    ax.axvspan(breakout_start, breakout_end, color=YELLOW_HI, alpha=0.10,
               label="Pre-news breakout window")

    # Raw signal — light, in the background
    ax.plot(ts_all, v_all, color=GREEN_HI, linewidth=0.8, alpha=0.25,
            label="Raw imbalance")
    # 15-snapshot rolling mean (~45 min smoothing at 3-min cadence)
    win = 15
    smoothed = np.convolve(v_all, np.ones(win) / win, mode="same")
    # Edge correction (convolve "same" mode has bias at endpoints)
    for i in range(win // 2):
        smoothed[i] = np.mean(v_all[:i + win // 2 + 1])
        smoothed[-(i + 1)] = np.mean(v_all[-(i + win // 2 + 1):])
    ax.plot(ts_all, smoothed, color=GREEN_HI, linewidth=2.4, alpha=0.95,
            label=f"Imbalance ({win}-snapshot rolling avg)")

    ax.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--",
               linewidth=1.6, alpha=0.95)
    ax.annotate("14:18 UTC\nfirst pre-news\nprice move",
                xy=(FIRST_MOVE, 0.45), xytext=(8, 0),
                textcoords="offset points",
                color=YELLOW_HI, fontsize=10, fontweight="bold",
                bbox=note_bbox(YELLOW_HI))
    ax.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
               linewidth=1.6, alpha=0.95)
    ax.annotate("21:50 UTC\nTrump post",
                xy=(EVENTS[-1][0], 0.45), xytext=(8, 0),
                textcoords="offset points",
                color=ORANGE_HI, fontsize=10, fontweight="bold",
                bbox=note_bbox(ORANGE_HI))

    style_axes(ax)
    ax.set_xlabel("UTC time", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylabel("Order book imbalance  (bid − ask) / (bid + ask)",
                  color=TEXT_LIGHT, fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
              labelcolor=TEXT_LIGHT, fontsize=9)
    brand(fig, ax,
          "Order book imbalance vs. pre-news baseline",
          "Positive = bid-side heavier. Baseline band from 06:00–13:00 UTC May 23.")
    plt.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.10)
    out = Path("charts") / "extras_imbalance_with_baseline.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}")


# ---- 5. spread + depth panel ---------------------------------------------

def chart_spread_depth(rows):
    """Single panel — total depth (bids vs asks) over time.
    Spread chart dropped (too sparse to read at log scale)."""
    if len(rows) < 50:
        print("  skipping spread/depth — not enough data")
        return
    fig, ax = plt.subplots(figsize=(13, 7), dpi=160)
    ts_all = [r["ts"] for r in rows]
    bid_raw = np.array([r["bid_dep"] for r in rows])
    ask_raw = np.array([r["ask_dep"] for r in rows])
    win = 15
    def smooth(v):
        s = np.convolve(v, np.ones(win) / win, mode="same")
        for i in range(win // 2):
            s[i] = np.mean(v[:i + win // 2 + 1])
            s[-(i + 1)] = np.mean(v[-(i + win // 2 + 1):])
        return s
    bid_sm = smooth(bid_raw)
    ask_sm = smooth(ask_raw)

    # Raw signals very faint in the background
    ax.plot(ts_all, bid_raw, color=GREEN_HI,  linewidth=0.6, alpha=0.20)
    ax.plot(ts_all, ask_raw, color=ORANGE_HI, linewidth=0.6, alpha=0.20)
    # Smoothed signals with light fills
    ax.fill_between(ts_all, bid_sm, color=GREEN_HI,  alpha=0.25)
    ax.fill_between(ts_all, ask_sm, color=ORANGE_HI, alpha=0.25)
    ax.plot(ts_all, bid_sm, color=GREEN_HI,  linewidth=2.4, alpha=0.95,
            label=f"Bid depth ({win}-snap rolling avg)")
    ax.plot(ts_all, ask_sm, color=ORANGE_HI, linewidth=2.4, alpha=0.95,
            label=f"Ask depth ({win}-snap rolling avg)")

    ax.axvline(FIRST_MOVE, color=YELLOW_HI, linestyle="--",
               linewidth=1.6, alpha=0.95)
    ax.annotate("14:18 UTC\nfirst pre-news\nprice move",
                xy=(FIRST_MOVE, max(r["bid_dep"] for r in rows) * 0.85),
                xytext=(8, 0), textcoords="offset points",
                color=YELLOW_HI, fontsize=10, fontweight="bold",
                bbox=note_bbox(YELLOW_HI))
    ax.axvline(EVENTS[-1][0], color=ORANGE_HI, linestyle="--",
               linewidth=1.6, alpha=0.95)
    ax.annotate("21:50 UTC\nTrump post",
                xy=(EVENTS[-1][0], max(r["bid_dep"] for r in rows) * 0.85),
                xytext=(8, 0), textcoords="offset points",
                color=ORANGE_HI, fontsize=10, fontweight="bold",
                bbox=note_bbox(ORANGE_HI))

    style_axes(ax)
    ax.set_xlabel("UTC time", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylabel("Total resting depth (contracts)", color=TEXT_LIGHT, fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=SPINE_DARK,
              labelcolor=TEXT_LIGHT, fontsize=10)
    brand(fig, ax,
          "Order book depth around the news",
          "Bid-side vs ask-side total resting liquidity — Iran ceasefire May 24")
    plt.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.10)
    out = Path("charts") / "extras_spread_and_depth.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → {out.name}")


# ---- main -----------------------------------------------------------------

def main():
    print("Loading data...")
    rows_24 = load_snapshots(DIR / "book_history_will-the-iran-ceasefire-continue-through-may-24-733.ndjson")
    rows_27 = load_snapshots(DIR / "book_history_will-the-iran-ceasefire-continue-through-may-27-496.ndjson")
    rows_31_path = DIR / "book_history_will-the-iran-ceasefire-continue-through-may-31-654-633.ndjson"
    rows_31 = load_snapshots(rows_31_path) if rows_31_path.exists() else []
    rows_regime_path = DIR / "book_history_will-the-iranian-regime-fall-by-june-30.ndjson"
    rows_regime = load_snapshots(rows_regime_path) if rows_regime_path.exists() else []

    print(f"  may-24: {len(rows_24)} snapshots")
    print(f"  may-27: {len(rows_27)} snapshots")
    print(f"  may-31: {len(rows_31)} snapshots")
    print(f"  regime: {len(rows_regime)} snapshots")
    print()

    print("Rendering...")
    chart_timeline_with_news(rows_24, rows_27, rows_31)
    chart_cumulative_discovery(rows_24)
    # chart_regime_fall_counter — skipped; regime-fall data too sparse on May 23
    chart_imbalance(rows_24)
    chart_spread_depth(rows_24)


if __name__ == "__main__":
    main()
