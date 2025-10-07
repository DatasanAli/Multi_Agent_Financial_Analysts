# collect_raw_data.py
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from resolver import resolve_ticker_to_cik
from sec_financials import pull_sec_financials
from price_trend import pull_price_trend_yf
from finnhub_news import pull_finnhub_news


def collect_raw_data(ticker: str) -> Dict[str, Any]:
    """
    Unified fetch hub.
    NOTE: Return shape is preserved EXACTLY for downstream compatibility.
      {
        "meta":   <resolver dict>,
        "sec":    <sec_financials dict>,
        "prices": <price_trend dict>,
        "news":   <finnhub_news dict>
      }
    """
    resolved = resolve_ticker_to_cik(ticker)
    cik = resolved["cik"]
    sec = pull_sec_financials(cik)
    prices = pull_price_trend_yf(ticker)
    news = pull_finnhub_news(ticker)
    return {"meta": resolved, "sec": sec, "prices": prices, "news": news}


# -----------------------------
# Persistence (optional helpers)
# -----------------------------
def persist_raw_json(
    ticker: str,
    data: Dict[str, Any],
    out_dir: str = "reports",
    filename: Optional[str] = None,
    with_timestamp: bool = True,
) -> str:
    """
    Save the raw data to JSON for later reuse (persist).
    Does NOT modify the return shape of collect_raw_data.
    Returns the file path written.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") if with_timestamp else ""
    base = filename or (f"{ticker}_raw{('_' + stamp) if stamp else ''}.json")
    path = str(Path(out_dir) / base)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_raw_json(path: str) -> Dict[str, Any]:
    """Convenience loader for persisted runs."""
    with open(path, "r") as f:
        return json.load(f)


# -----------------------------
# Example CLI usage 
# -----------------------------
if __name__ == "__main__":
    # Usage:
    #   TEST_TICKER=MSFT python collect_raw_data.py
    #   (writes reports/MSFT_raw_YYYYMMDD-HHMMSS.json)
    ticker = os.getenv("TEST_TICKER", "AAPL").strip() or "AAPL"
    data = collect_raw_data(ticker)
    out_path = persist_raw_json(ticker, data, out_dir="reports")
    print(f"Collected and saved raw data for {ticker} → {out_path}")
