# resolver.py

import requests
import json
from typing import Optional, Dict

SEC_TICKER_CIK = "https://www.sec.gov/files/company_tickers.json"
HEADERS_SEC = {"User-Agent": "Your Name your@email.com", "Accept-Encoding": "gzip, deflate"}

def resolve_ticker_to_cik(ticker: str) -> Optional[Dict[str, str]]:
    """
    Given a stock ticker (like AAPL), return CIK and metadata.
    """
    try:
        r = requests.get(SEC_TICKER_CIK, headers=HEADERS_SEC)
        r.raise_for_status()
        data = r.json()
        for entry in data.values():
            if entry['ticker'].upper() == ticker.upper():
                cik_str = str(entry['cik_str']).zfill(10)
                return {
                    "ticker": ticker.upper(),
                    "cik": cik_str,
                    "title": entry.get("title", "Unknown"),
                }
    except Exception as e:
        print(f"[Resolver] Error fetching CIK for {ticker}: {e}")
        return None
