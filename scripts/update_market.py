#!/usr/bin/env python3
"""Updates the Market Pulse section in README.md with live data from Yahoo Finance."""

import re
import sys
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

TICKERS = [
    ("^BVSP", "Ibovespa"),
    ("SPY",   "S&P 500 (SPY)"),
    ("QQQ",   "Nasdaq 100 (QQQ)"),
    ("QMOM",  "Quant Momentum (QMOM)"),
    ("MTUM",  "Momentum Factor (MTUM)"),
    ("QUAL",  "Quality Factor (QUAL)"),
]

ARROW = {"up": "▲", "down": "▼", "flat": "─"}

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def vix_sentiment(level: float) -> str:
    if level < 15:
        return "Calm"
    if level < 20:
        return "Normal"
    if level < 30:
        return "Elevated"
    if level < 40:
        return "Fear"
    return "Panic"


def fmt_pct(val: float | None) -> str:
    if val is None:
        return "—"
    arrow = ARROW["up"] if val > 0.05 else (ARROW["down"] if val < -0.05 else ARROW["flat"])
    sign = "+" if val > 0 else ""
    return f"{arrow} {sign}{val:.2f}%"


def fmt_price(val: float | None, ticker: str) -> str:
    if val is None:
        return "—"
    if ticker == "^BVSP":
        return f"{val:,.0f}"
    return f"${val:,.2f}"


def fetch_vix_row() -> str:
    try:
        t = yf.Ticker("^VIX")
        info = t.fast_info
        level: float | None = getattr(info, "last_price", None)
        prev: float | None = getattr(info, "previous_close", None)
        day_pct: float | None = ((level - prev) / prev * 100) if level and prev else None
        label = vix_sentiment(level) if level else "—"
        return (
            f"| **VIX — Fear Index** "
            f"| {f'{level:.2f}' if level else '—'} "
            f"| {fmt_pct(day_pct)} "
            f"| {label} "
            f"| {TODAY} |"
        )
    except Exception as e:
        return f"| **VIX — Fear Index** | — | — | — | error: {e} |"


def fetch_row(ticker: str, label: str) -> str:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price: float | None = getattr(info, "last_price", None)
        prev_close: float | None = getattr(info, "previous_close", None)
        day_pct: float | None = ((price - prev_close) / prev_close * 100) if price and prev_close else None

        hist = t.history(period="ytd", auto_adjust=True)
        if not hist.empty and price:
            ytd_pct: float | None = (price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100
        else:
            ytd_pct = None

        return (
            f"| **{label}** "
            f"| {fmt_price(price, ticker)} "
            f"| {fmt_pct(day_pct)} "
            f"| {fmt_pct(ytd_pct)} "
            f"| {TODAY} |"
        )
    except Exception as e:
        return f"| **{label}** | — | — | — | error: {e} |"


def build_table() -> str:
    vix_header = (
        "| Asset | Level | Day % | Sentiment | Updated |\n"
        "|---|---|---|---|---|\n"
    )
    market_header = (
        "\n| Asset | Price | Day % | YTD % | Updated |\n"
        "|---|---|---|---|---|\n"
    )
    vix = fetch_vix_row()
    rows = "\n".join(fetch_row(ticker, label) for ticker, label in TICKERS)
    return vix_header + vix + market_header + rows


def update_readme(table: str) -> None:
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_block = f"<!-- MARKET_START -->\n{table}\n<!-- MARKET_END -->"
    updated = re.sub(
        r"<!-- MARKET_START -->.*?<!-- MARKET_END -->",
        new_block,
        content,
        flags=re.DOTALL,
    )

    if updated == content:
        print("Warning: placeholder not found in README.md")
        sys.exit(1)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README.md updated successfully.")


if __name__ == "__main__":
    print("Fetching market data...")
    table = build_table()
    print(table)
    update_readme(table)
