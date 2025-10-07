# finnhub_news.py

import os
import requests
import datetime as dt
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

FINNHUB_BASE = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()

def fetch_json(url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[WARN] GET {url} failed: {e}")
        return None

def pull_finnhub_news(symbol: str, days: int = 30) -> Dict[str, Any]:
    if not FINNHUB_API_KEY:
        return {"error": "Missing FINNHUB_API_KEY"}
    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=days)
    url = f"{FINNHUB_BASE}/company-news"
    params = {"symbol": symbol, "from": str(from_date), "to": str(to_date), "token": FINNHUB_API_KEY}
    data = fetch_json(url, params=params)
    if not data or isinstance(data, dict) and data.get("error"):
        return {"error": data.get("error") if isinstance(data, dict) else "Failed to get news"}
    items = sorted(data, key=lambda x: x.get("datetime", 0), reverse=True)[:20]
    for it in items:
        try:
            ts = it.get("datetime", 0)
            it["datetime_iso"] = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    return {"count": len(data), "sample": items}

# Example usage
if __name__ == "__main__":
    news = pull_finnhub_news("AAPL", days=30)
    if "error" in news:
        print("Error:", news["error"])
    else:
        print(f"Articles: {news['count']}")
        for i, n in enumerate(news["sample"], 1):
            print(f"{i}. {n['datetime_iso']} | {n['source']}: {n['headline']}")
            summary = (n.get("summary") or "").strip()
            if summary:
                truncated = summary[:200] + ("…" if len(summary) > 200 else "")
                print(f"    Summary: {truncated}")
            else:
                print("    Summary: [No summary provided]")
