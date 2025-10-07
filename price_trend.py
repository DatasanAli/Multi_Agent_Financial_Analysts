# price_trend.py

import yfinance as yf
import math
import statistics
from typing import Dict

def pull_price_trend_yf(symbol: str, days: int = 60) -> Dict[str, any]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")
        if hist.empty:
            return {"error": "No price data returned"}
        closes_series = hist["Close"].dropna()
        closes = [(idx.strftime("%Y-%m-%d"), float(val)) for idx, val in closes_series.items()]
        latest_close = closes[-1][1]
        oldest_close = closes[0][1]
        pct_change = (latest_close / oldest_close - 1.0) if oldest_close else None

        sma20 = float(closes_series.tail(20).mean()) if len(closes_series) >= 20 else None
        sma50 = float(closes_series.tail(50).mean()) if len(closes_series) >= 50 else None

        vals = list(closes_series.values)
        logrets = [math.log(vals[i] / vals[i-1]) for i in range(1, len(vals)) if vals[i-1] and vals[i]]
        vol = statistics.pstdev(logrets) * math.sqrt(252) if logrets else None

        return {
            "latest_close": latest_close,
            "oldest_close": oldest_close,
            "pct_change": pct_change,
            "sma20": sma20,
            "sma50": sma50,
            "annualized_vol": vol,
            "sample": closes[-5:]
        }
    except Exception as e:
        return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    data = pull_price_trend_yf("AAPL")
    for k, v in data.items():
        print(f"{k:20}: {v}")
