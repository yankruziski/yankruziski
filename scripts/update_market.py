#!/usr/bin/env python3
"""Generates terminal.svg and updates README.md Market Pulse section."""

import re
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

# ── config ────────────────────────────────────────────────────────────────────

TICKERS = [
    ("^BVSP", "Ibovespa",        "IBOV"),
    ("SPY",   "S&P 500",         "SPY"),
    ("QQQ",   "Nasdaq 100",      "QQQ"),
    ("QMOM",  "Quant Momentum",  "QMOM"),
    ("MTUM",  "Momentum Factor", "MTUM"),
    ("QUAL",  "Quality Factor",  "QUAL"),
]

NOW_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
TODAY   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ── SVG palette (Bloomberg-inspired: dark navy + amber) ──────────────────────

P = {
    "bg":     "#060B14",
    "accent": "#E87800",
    "text":   "#C8D8E8",
    "dim":    "#2E3F52",
    "dim2":   "#607888",
    "up":     "#00C878",
    "down":   "#FF3C3C",
    "flat":   "#8A9AAA",
}
FONT = "Courier New, Courier, monospace"

# ── helpers ───────────────────────────────────────────────────────────────────

def color_pct(val: float | None, invert: bool = False) -> str:
    if val is None:
        return P["flat"]
    pos = val > 0.05
    neg = val < -0.05
    if invert:
        pos, neg = neg, pos
    return P["up"] if pos else (P["down"] if neg else P["flat"])


def fmt_pct(val: float | None) -> str:
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def fmt_price(val: float | None, ticker: str) -> str:
    if val is None:
        return "—"
    return f"{val:,.0f}" if ticker == "^BVSP" else f"{val:,.2f}"


def vix_label(level: float | None) -> str:
    if level is None:
        return "—"
    if level < 15:  return "CALM"
    if level < 20:  return "NORMAL"
    if level < 30:  return "ELEVATED"
    if level < 40:  return "FEAR"
    return "PANIC"


def sparkline(prices: list[float], x0: float, y0: float, w: float, h: float, color: str) -> str:
    if len(prices) < 2:
        return ""
    lo, hi = min(prices), max(prices)
    span = hi - lo or 1.0
    n = len(prices)
    pts = " ".join(
        f"{x0 + i / (n - 1) * w:.1f},{y0 + h - (p - lo) / span * h:.1f}"
        for i, p in enumerate(prices)
    )
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )

# ── data fetching ─────────────────────────────────────────────────────────────

def fetch_vix() -> dict:
    try:
        t = yf.Ticker("^VIX")
        info = t.fast_info
        price: float | None    = getattr(info, "last_price", None)
        prev: float | None     = getattr(info, "previous_close", None)
        day_pct: float | None  = ((price - prev) / prev * 100) if price and prev else None
        hist = t.history(period="3mo", auto_adjust=True)
        return {
            "price": price, "day_pct": day_pct,
            "label": vix_label(price),
            "history": hist["Close"].tolist() if not hist.empty else [],
        }
    except Exception as e:
        print(f"VIX fetch error: {e}")
        return {"price": None, "day_pct": None, "label": "—", "history": []}


def fetch_asset(ticker: str, label: str, short: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price: float | None      = getattr(info, "last_price", None)
        prev_close: float | None = getattr(info, "previous_close", None)
        day_pct: float | None    = ((price - prev_close) / prev_close * 100) if price and prev_close else None

        hist_ytd = t.history(period="ytd", auto_adjust=True)
        ytd_pct: float | None = None
        if not hist_ytd.empty and price:
            ytd_pct = (price - hist_ytd["Close"].iloc[0]) / hist_ytd["Close"].iloc[0] * 100

        hist = t.history(period="3mo", auto_adjust=True)
        return {
            "ticker": ticker, "label": label, "short": short,
            "price": price, "day_pct": day_pct, "ytd_pct": ytd_pct,
            "history": hist["Close"].tolist() if not hist.empty else [],
        }
    except Exception as e:
        print(f"{ticker} fetch error: {e}")
        return {
            "ticker": ticker, "label": label, "short": short,
            "price": None, "day_pct": None, "ytd_pct": None, "history": [],
        }

# ── SVG generation ────────────────────────────────────────────────────────────

def build_svg(vix: dict, assets: list[dict]) -> str:
    W   = 880
    PAD = 16

    # Bloomberg-authentic layout heights
    SB  = 18   # status bar (solid amber, top)
    TB  = 20   # subtitle bar (dark)
    CH  = 22   # column header band
    RH  = 32   # data row
    IL  = 18   # info line (bottom)

    n_rows = 1 + len(assets)
    H = SB + TB + CH + n_rows * RH + IL

    # Bloomberg-inspired palette
    BP = {
        "bg":       "#040810",
        "bar":      "#D87000",
        "bar_text": "#030608",
        "amber":    "#E8A000",
        "amber2":   "#FFA020",
        "white":    "#D8E8F0",
        "dim":      "#2A3A4A",
        "dim2":     "#506070",
        "up":       "#00C878",
        "down":     "#FF3C3C",
        "flat":     "#7A8A9A",
    }

    # Column x-positions
    C_TICK  = PAD
    C_NAME  = PAD + 56
    C_LAST  = 340
    C_DAY   = 420
    C_YTD   = 500
    C_CHART = 516
    C_CHART_W = W - C_CHART - PAD

    def t(x, y, text, anchor="start", size=10, fill=None, bold=False) -> str:
        fw = 'font-weight="bold"' if bold else ""
        fc = fill or BP["white"]
        return (
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-family="{FONT}" font-size="{size}" fill="{fc}" {fw}>{escape(str(text))}</text>'
        )

    def hline(y, color=None, dash=False, w=0.5, x1=0, x2=None) -> str:
        c  = color or BP["dim"]
        da = 'stroke-dasharray="4,4"' if dash else ""
        x2 = x2 or W
        return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{c}" stroke-width="{w}" {da}/>'

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BP["bg"]}"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="none" stroke="{BP["amber"]}" stroke-width="0.7" opacity="0.5"/>',
    ]

    # ── solid amber status bar (Bloomberg session bar) ──
    parts += [
        f'<rect x="0" y="0" width="{W}" height="{SB}" fill="{BP["bar"]}"/>',
        t(PAD, SB - 4, "BLOOMBERG", size=9, fill=BP["bar_text"], bold=True),
        t(PAD + 72, SB - 4, "QUANT MARKET MONITOR", size=9, fill=BP["bar_text"]),
        t(W // 2, SB - 4, "EQUITY  &  VOLATILITY  DASHBOARD", anchor="middle", size=9, fill=BP["bar_text"]),
        t(W - PAD, SB - 4, NOW_UTC, anchor="end", size=9, fill=BP["bar_text"]),
    ]

    # ── subtitle bar ──
    sub_y = SB + TB - 5
    parts += [
        hline(SB + TB, BP["amber"], w=0.8),
        t(PAD, sub_y, "YAN KRUZISKI  ·  VP OF INTELI RESEARCH  ·  SÃO PAULO, BR", size=9, fill=BP["dim2"]),
        t(W - PAD, sub_y, "PAGE 1/1", anchor="end", size=9, fill=BP["dim2"]),
    ]

    # ── column header band ──
    chy = SB + TB + CH - 6
    parts += [
        f'<rect x="0" y="{SB + TB}" width="{W}" height="{CH}" fill="{BP["amber"]}" opacity="0.14"/>',
        t(C_TICK,                     chy, "TICKER",      size=9, fill=BP["amber2"], bold=True),
        t(C_NAME,                     chy, "DESCRIPTION", size=9, fill=BP["amber2"], bold=True),
        t(C_LAST,                     chy, "LAST",        anchor="end", size=9, fill=BP["amber2"], bold=True),
        t(C_DAY,                      chy, "%CHG",        anchor="end", size=9, fill=BP["amber2"], bold=True),
        t(C_YTD,                      chy, "YTD%",        anchor="end", size=9, fill=BP["amber2"], bold=True),
        t(C_CHART + C_CHART_W // 2,   chy, "3-MONTH",     anchor="middle", size=9, fill=BP["amber2"], bold=True),
        hline(SB + TB + CH, BP["amber"], w=0.9),
    ]

    # ── VIX row (amber-tinted highlight) ──
    vr_y  = SB + TB + CH
    vr_ty = vr_y + RH // 2 + 4
    dc    = color_pct(vix["day_pct"], invert=True)

    parts += [
        f'<rect x="0" y="{vr_y}" width="{W}" height="{RH}" fill="{BP["amber"]}" opacity="0.09"/>',
        t(C_TICK,  vr_ty, "^VIX",                    size=10, fill=BP["amber2"],  bold=True),
        t(C_NAME,  vr_ty, "CBOE VOLATILITY INDEX",   size=10, fill=BP["amber"],   bold=True),
        t(C_LAST,  vr_ty, f'{vix["price"]:.2f}' if vix["price"] is not None else "—",
          anchor="end", size=11, fill=BP["white"], bold=True),
        t(C_DAY,   vr_ty, fmt_pct(vix["day_pct"]),  anchor="end", size=11, fill=dc, bold=True),
        t(C_YTD,   vr_ty, vix["label"],              anchor="end", size=10, fill=dc, bold=True),
    ]
    if vix["history"]:
        parts.append(sparkline(vix["history"], C_CHART, vr_y + 5, C_CHART_W, RH - 10, dc))
    parts.append(hline(vr_y + RH, BP["amber"], w=0.5))

    # ── asset rows ──
    for i, asset in enumerate(assets):
        ry  = vr_y + RH + i * RH
        ty  = ry + RH // 2 + 4
        dc  = color_pct(asset["day_pct"])
        yc  = color_pct(asset["ytd_pct"])

        if i % 2 == 0:
            parts.append(
                f'<rect x="0" y="{ry}" width="{W}" height="{RH}" fill="#FFFFFF" opacity="0.02"/>'
            )

        parts += [
            t(C_TICK,  ty, asset["short"],                      size=10, fill=BP["amber2"],  bold=True),
            t(C_NAME,  ty, asset["label"].upper(),              size=10, fill=BP["amber"]),
            t(C_LAST,  ty, fmt_price(asset["price"], asset["ticker"]),
              anchor="end", size=11, fill=BP["white"], bold=True),
            t(C_DAY,   ty, fmt_pct(asset["day_pct"]),          anchor="end", size=11, fill=dc),
            t(C_YTD,   ty, fmt_pct(asset["ytd_pct"]),          anchor="end", size=11, fill=yc),
        ]
        if asset["history"]:
            parts.append(sparkline(asset["history"], C_CHART, ry + 5, C_CHART_W, RH - 10, dc))
        parts.append(hline(ry + RH, BP["dim"], w=0.3, x1=PAD, x2=W - PAD))

    # ── info line ──
    fy = SB + TB + CH + n_rows * RH
    parts += [
        hline(fy, BP["amber"], w=0.4),
        t(PAD, fy + IL - 5,
          "SRC: YAHOO FINANCE  ·  AUTO-UPDATE 22:00 UTC WEEKDAYS  ·  GITHUB.COM/YANKRUZISKI",
          size=8, fill=BP["dim2"]),
        t(W - PAD, fy + IL - 5, TODAY, anchor="end", size=8, fill=BP["dim2"]),
    ]

    parts.append("</svg>")
    return "\n".join(parts)

# ── README update ─────────────────────────────────────────────────────────────

def update_readme() -> None:
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_block = (
        "<!-- MARKET_START -->\n"
        '<div align="center">\n\n'
        '<img src="terminal.svg" alt="Market Terminal" width="880"/>\n\n'
        "</div>\n"
        "<!-- MARKET_END -->"
    )
    updated = re.sub(
        r"<!-- MARKET_START -->.*?<!-- MARKET_END -->",
        new_block,
        content,
        flags=re.DOTALL,
    )

    marker = "<!-- MARKET_START -->"
    if marker not in content:
        print("Warning: MARKET_START marker not found in README.md")
        sys.exit(1)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)
    print("README.md updated.")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching data...")
    vix    = fetch_vix()
    assets = [fetch_asset(t, l, s) for t, l, s in TICKERS]

    print("Generating terminal.svg...")
    svg = build_svg(vix, assets)
    with open("terminal.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("terminal.svg written.")

    import xml.dom.minidom
    xml.dom.minidom.parseString(svg)
    print("terminal.svg XML validated.")

    update_readme()
