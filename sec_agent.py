# sec_agent.py

import os
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from collect_raw_data import collect_raw_data

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env file")

# ---------------------
# LLM + Prompt Setup
# ---------------------

SEC_JSON_SCHEMA = {
    "analyst_summary": "2 short paragraphs for a CFA audience.",
    "plain_summary": "2–4 sentences for non-technical readers.",
    "profitability": [
        "Short bullet(s) on gross/operating margin quality and trends if implied."
    ],
    "liquidity": [
        "Short bullet(s) on current ratio and near-term cash coverage."
    ],
    "solvency": [
        "Short bullet(s) on leverage (debt/equity) and balance-sheet risk."
    ],
    "red_flags": [
        "Specific risks (e.g., high leverage, weak liquidity, margin compression)."
    ],
    "green_flags": [
        "Specific strengths (e.g., robust margins, strong cash, improving leverage)."
    ],
    "verdict": "One of: strong | stable | watch | fragile"
}

SYSTEM_MSG = (
    "You are a CFA financial analyst. Be precise, conservative, and evidence-based. "
    "ONLY use the provided numeric fields. If something is not present, do not invent it."
)

HUMAN_TASK = (
    "You are reviewing structured SEC 10-K/annual data for a company. Using ONLY the fields provided,\n"
    "evaluate financial health from a CFA perspective.\n\n"
    "Required focal points:\n"
    "• Profitability: gross_margin, operating_margin\n"
    "• Liquidity: current_ratio\n"
    "• Solvency: debt_to_equity (and cash context if provided)\n"
    "• Call out risks and strengths explicitly\n"
    "• Provide two summaries: (a) analyst_summary (pro audience), (b) plain_summary (general audience)\n"
    "• Give a one-word verdict: strong | stable | watch | fragile\n\n"
    "Return VALID JSON ONLY using this schema:\n{json_schema}\n\n"
    "Here is the structured data:\n{sec_json}\n"
    "{ticker_hint}"
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        ("human", HUMAN_TASK),
    ]
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.25)
to_text = StrOutputParser()
chain = prompt | llm | to_text


# ---------------------
# Public API
# ---------------------

def analyze_sec_financials(sec_data: Dict[str, Any], ticker_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Use LLM (via LangChain) to analyze SEC financial data from a CFA perspective.
    Returns:
      {
        "metrics": <sec_data>,
        "analysis_json": { ...see SEC_JSON_SCHEMA... },
        "raw_model_text": "<raw json text>"
      }
    """
    required_fields = [
        "revenue", "gross_profit", "operating_income", "net_income",
        "cash", "current_assets", "current_liabilities", "equity",
        "total_debt", "gross_margin", "operating_margin",
        "current_ratio", "debt_to_equity"
    ]
    missing = [k for k in required_fields if k not in sec_data or sec_data[k] is None]
    if missing:
        return {"error": f"Missing required SEC fields: {missing}"}

    # Prepare inputs
    sec_json = json.dumps(sec_data, indent=2, ensure_ascii=False)
    ticker_hint_str = f"Target company: {ticker_hint}" if ticker_hint else ""

    # Run the prompt chain
    raw_text = chain.invoke(
        {
            "json_schema": json.dumps(SEC_JSON_SCHEMA, indent=2),
            "sec_json": sec_json,
            "ticker_hint": ticker_hint_str
        }
    )

    # Robust JSON parse with brace-snipping fallback
    parsed = _safe_parse_json(raw_text, fallback=_empty_payload())

    # Ensure expected keys exist
    for k, template in SEC_JSON_SCHEMA.items():
        if k not in parsed:
            parsed[k] = [] if isinstance(template, list) else ""

    return {
        "metrics": sec_data,
        "analysis_json": parsed,
        "raw_model_text": raw_text
    }


# ---------------------
# Helpers
# ---------------------

def _safe_parse_json(txt: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
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
        "analyst_summary": "",
        "plain_summary": "",
        "profitability": [],
        "liquidity": [],
        "solvency": [],
        "red_flags": [],
        "green_flags": [],
        "verdict": ""
    }


# ---------------------
# Example usage
# ---------------------

if __name__ == "__main__":
    TICKER = os.getenv("TEST_TICKER", "AAPL").strip() or "AAPL"

    data = collect_raw_data(TICKER)
    meta = data.get("meta", {}) or {}
    sec_data = data.get("sec", {}) or {}

    company_hint = meta.get("company_name") or TICKER

    sec_result = analyze_sec_financials(sec_data, ticker_hint=company_hint)

    if "error" in sec_result:
        print("[SEC] Error:", sec_result["error"])
    else:
        print("\n=== SEC Financial Health Report (JSON) ===\n")
        print(json.dumps(sec_result["analysis_json"], indent=2))
