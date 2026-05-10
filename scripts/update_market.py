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
    ("^BVSP",  "Ibovespa",            "🇧🇷"),
    ("SPY",    "S&P 500 (SPY)",        "🇺🇸"),
    ("QQQ",    "Nasdaq 100 (QQQ)",     "🇺🇸"),
    ("QMOM",   "Quant Momentum (QMOM)","📐"),
    ("MTUM",   "Momentum Factor (MTUM)","⚡"),
    ("QUAL",   "Quality Factor (QUAL)","🔬"),
]

ARROW = {"up": "▲", "down": "▼", "flat": "─"}


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


def fetch_row(ticker: str, label: str, flag: str) -> str:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info

        price: float | None = getattr(info, "last_price", None)
        prev_close: float | None = getattr(info, "previous_close", None)

        day_pct: float | None = ((price - prev_close) / prev_close * 100) if price and prev_close else None

        # YTD: approximate from 52w low/high range midpoint isn't reliable,
        # so we pull the first trading day of the year explicitly.
        hist = t.history(period="ytd", auto_adjust=True)
        if not hist.empty and price:
            ytd_start = hist["Close"].iloc[0]
            ytd_pct = (price - ytd_start) / ytd_start * 100
        else:
            ytd_pct = None

        return (
            f"| {flag} **{label}** "
            f"| {fmt_price(price, ticker)} "
            f"| {fmt_pct(day_pct)} "
            f"| {fmt_pct(ytd_pct)} "
            f"| {datetime.now(timezone.utc).strftime('%Y-%m-%d')} |"
        )
    except Exception as e:
        return f"| {flag} **{label}** | — | — | — | error: {e} |"


def build_table() -> str:
    header = (
        "| Asset | Price | Day % | YTD % | Updated |\n"
        "|---|---|---|---|---|\n"
    )
    rows = "\n".join(fetch_row(ticker, label, flag) for ticker, label, flag in TICKERS)
    return header + rows


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
