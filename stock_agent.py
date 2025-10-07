# stock_agent.py
#
# Quant-style stock analysis + a plain-English summary (for a general audience).
# Input: dict from price_trend.pull_price_trend_yf(symbol, days)
# Output: { analysis_technical, summary_plain, metrics{..., derived_signals} }

import os
import json
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv

# LangChain
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from price_trend import pull_price_trend_yf

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env file")


# -------------------------
# Derived signal helpers
# -------------------------
def _derive_signals(price_data: Dict[str, Any]) -> Dict[str, Any]:
    latest = price_data.get("latest_close")
    sma20 = price_data.get("sma20")
    sma50 = price_data.get("sma50")
    pct_change = price_data.get("pct_change")
    vol = price_data.get("annualized_vol")

    trend = "Up" if (pct_change or 0) > 0.05 else ("Down" if (pct_change or 0) < -0.05 else "Flat")
    above_20 = (latest is not None and sma20 is not None and latest > sma20)
    above_50 = (latest is not None and sma50 is not None and latest > sma50)

    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            crossover = "Bullish (20D above 50D)"
        elif sma20 < sma50:
            crossover = "Bearish (20D below 50D)"
        else:
            crossover = "Neutral (20D ~ 50D)"
    else:
        crossover = None

    if vol is not None:
        if vol < 0.20:
            vol_label = "Low"
        elif vol < 0.35:
            vol_label = "Moderate"
        else:
            vol_label = "High"
    else:
        vol_label = None

    days = price_data.get("days") or (len(price_data.get("sample", [])) or None)

    return {
        "trend_label": trend,
        "above_sma20": above_20,
        "above_sma50": above_50,
        "crossover": crossover,
        "volatility_label": vol_label,
        "days_window": days,
    }


# -------------------------
# LLM prompt + schema
# -------------------------
JSON_CONTRACT = {
    "analysis_technical": "6-8 sentences for finance readers; discuss pct_change, SMAs (20D/50D), crossover, volatility label, and flags.",
    "summary_plain": "3-5 short sentences for non-experts, no jargon.",
    "flags": {
        "positives": ["bullet list of positives"],
        "red_flags": ["bullet list of risks"]
    }
}

SYSTEM_MSG = (
    "You are a disciplined, evidence-based quantitative equity analyst who communicates clearly "
    "to both experts and non-experts. Use ONLY the provided fields; do not invent numbers. "
    "Return VALID JSON ONLY that matches the given schema."
)

HUMAN_TASK = (
    "Given structured stock data and derived signals, produce:\n"
    "1) analysis_technical: 6-8 sentences for technical readers covering trend via pct_change, 20D/50D SMA posture, any bullish/bearish crossover, and annualized volatility implications.\n"
    "2) summary_plain: 3-5 short sentences for general audience (no jargon) explaining recent direction, position vs averages, and whether price swings are calm/moderate/large; end neutral.\n"
    "3) flags: positives[] and red_flags[] bullet points.\n\n"
    "Return JSON ONLY using this schema:\n{json_schema}\n\n"
    "DATA:\n{data_json}\n\n"
    "SIGNALS:\n{signals_json}\n"
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        ("human", HUMAN_TASK)
    ]
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.25)
to_text = StrOutputParser()
chain = prompt | llm | to_text


# -------------------------
# Public API
# -------------------------
def analyze_stock_price(price_data: Dict[str, Any], *, ticker_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    LLM-driven analysis that returns BOTH:
      - analysis_technical: concise note for finance/technical readers
      - summary_plain: plain-English 3–5 sentence recap for general audience
      - flags: positives/red_flags bullet points
      - metrics: original metrics plus derived_signals
    """
    if not price_data or "error" in price_data:
        return {"error": price_data.get("error", "No price data provided")}

    # Precompute signals and compact recent series
    signals = _derive_signals(price_data)
    recent: List[Tuple[str, float]] = price_data.get("sample", [])
    recent_compact = [{"date": d, "close": c} for d, c in recent]

    data_payload = {
        "ticker_hint": ticker_hint or "",
        "latest_close": price_data.get("latest_close"),
        "oldest_close": price_data.get("oldest_close"),
        "pct_change": price_data.get("pct_change"),
        "sma20": price_data.get("sma20"),
        "sma50": price_data.get("sma50"),
        "annualized_vol": price_data.get("annualized_vol"),
        "window_days": price_data.get("days"),
        "recent_sample": recent_compact
    }

    raw = chain.invoke(
        {
            "json_schema": json.dumps(JSON_CONTRACT, indent=2),
            "data_json": json.dumps(data_payload, indent=2, ensure_ascii=False),
            "signals_json": json.dumps(signals, indent=2, ensure_ascii=False),
        }
    )

    parsed = _safe_json(raw, fallback=_empty_payload())

    # Ensure required top-level keys exist
    for k, v in JSON_CONTRACT.items():
        if k not in parsed:
            parsed[k] = [] if isinstance(v, list) else ({} if isinstance(v, dict) else "")

    return {
        "analysis_technical": parsed.get("analysis_technical", ""),
        "summary_plain": parsed.get("summary_plain", ""),
        "flags": parsed.get("flags", {"positives": [], "red_flags": []}),
        "metrics": {
            **price_data,
            "derived_signals": signals
        },
        "raw_model_text": raw
    }


# -------------------------
# Helpers
# -------------------------
def _safe_json(txt: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        start, end = txt.find("{"), txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(txt[start : end + 1])
            except Exception:
                return fallback
        return fallback


def _empty_payload() -> Dict[str, Any]:
    return {
        "analysis_technical": "",
        "summary_plain": "",
        "flags": {"positives": [], "red_flags": []}
    }


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    # Use collect_raw_data for consistency with other agents and to grab a nicer company hint.
    from collect_raw_data import collect_raw_data

    TICKER = os.getenv("TEST_TICKER", "AAPL").strip() or "AAPL"

    data = collect_raw_data(TICKER)
    meta = data.get("meta", {}) or {}
    prices = data.get("prices", {}) or {}

    company_hint = meta.get("company_name") or TICKER

    # Fallback path: if collect_raw_data ever changes, we can still fetch directly.
    if not prices:
        prices = pull_price_trend_yf(TICKER, days=60)

    if "error" in prices:
        print("Price fetch error:", prices.get("error"))
        raise SystemExit(1)

    result = analyze_stock_price(prices, ticker_hint=company_hint)

    print("\n=== Stock Price Analysis (Technical) ===\n")
    print(result["analysis_technical"])

    print("\n=== Plain-English Summary ===\n")
    print(result["summary_plain"])

    # Optional: flags
    print("\n--- Flags ---")
    flags = result.get("flags", {})
    print("Positives:", *flags.get("positives", []), sep="\n - ")
    print("Red Flags:", *flags.get("red_flags", []), sep="\n - ")

    print("\n--- Key Metrics ---")
    m = result["metrics"]
    print(f"Latest Close:   {m.get('latest_close')}")
    print(f"Oldest Close:   {m.get('oldest_close')}")
    print(f"60d % Change:   {round((m.get('pct_change') or 0)*100, 1)}%")
    print(f"SMA20 / SMA50:  {round(m.get('sma20') or 0, 2)} / {round(m.get('sma50') or 0, 2)}")
    print(f"Ann. Vol:       {round(m.get('annualized_vol') or 0, 3)}")

    ds = m.get("derived_signals", {})
    print("\n--- Derived Signals ---")
    print(f"Trend Label:        {ds.get('trend_label')}")
    print(f"Above SMA20/SMA50:  {ds.get('above_sma20')} / {ds.get('above_sma50')}")
    print(f"Crossover:          {ds.get('crossover')}")
    print(f"Volatility Label:   {ds.get('volatility_label')}")
    print(f"Days Window:        {ds.get('days_window')}")
