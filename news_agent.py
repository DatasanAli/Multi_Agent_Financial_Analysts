# news_agent.py

import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env file")

# ---- Prompt + LLM setup ------------------------------------------------------

# The JSON contract we want back from the model.
NEWS_ANALYSIS_JSON_SCHEMA = {
    "relevant_articles": [
        {
            "headline": "string",
            "source": "string",
            "date": "YYYY-MM-DD (or raw ISO)",
            "why_relevant": "string"
        }
    ],
    "themes": [
        {
            "name": "string",
            "article_count": "int",
            "snippets": ["string"]
        }
    ],
    "sentiment": "one of: positive | negative | mixed | neutral",
    "risks": ["string"],
    "opportunities": ["string"],
    "pro_summary": "1–3 sentences, for analysts",
    "plain_summary": "1–3 sentences, for regular readers"
}

SYSTEM_INSTRUCTIONS = (
    "You are a senior financial news analyst. "
    "Analyze only the provided articles. "
    "Be precise, evidence-based, and concise. "
    "ALWAYS return valid JSON ONLY that matches the provided schema. "
    "If information is missing, use empty lists/strings."
)

HUMAN_TASK = (
    "You are given a list of news articles an upstream API tagged for a target company.\n"
    "Tasks:\n"
    "1) Identify which articles are actually about the target company (from the text).\n"
    "2) Group them into themes (e.g., leadership, litigation, product, AI, macro, supply chain, guidance, etc.).\n"
    "3) Assess overall sentiment (positive/negative/mixed/neutral) with brief rationale implied by content.\n"
    "4) Highlight key risks and opportunities.\n"
    "5) Provide two summaries: (a) pro_summary for analysts, (b) plain_summary for regular readers.\n\n"
    "Return JSON ONLY using this schema:\n"
    "{json_schema}\n\n"
    "Articles:\n{articles}\n"
    "{target_hint}"
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_INSTRUCTIONS),
        ("human", HUMAN_TASK),
    ]
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
to_text = StrOutputParser()

chain = prompt | llm | to_text  # Produces a JSON string (we'll parse it below)


# ---- Public function ---------------------------------------------------------

def analyze_news(news_sample: List[Dict[str, Any]], target_company_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze a batch of news items related to a company (ticker-agnostic).

    Returns a dict with:
      - raw_articles: filtered input items with headline/summary/source/date
      - analysis_json: parsed JSON (relevant_articles, themes, sentiment, risks, opportunities, pro_summary, plain_summary)
      - raw_model_text: the raw JSON text returned by the model (for debugging)
    """
    # Filter out items with no summary (keeps behavior similar to your original)
    items = [
        {
            "headline": n.get("headline", ""),
            "summary": n.get("summary", ""),
            "source": n.get("source", ""),
            "date": n.get("datetime_iso", "") or n.get("date", ""),
        }
        for n in news_sample
        if n.get("summary")
    ]

    if not items:
        empty = {
            "relevant_articles": [],
            "themes": [],
            "sentiment": "neutral",
            "risks": [],
            "opportunities": [],
            "pro_summary": "",
            "plain_summary": ""
        }
        return {"raw_articles": [], "analysis_json": empty, "raw_model_text": json.dumps(empty)}

    # Prepare inputs to the chain
    articles_json = json.dumps(items, indent=2, ensure_ascii=False)
    target_hint = f"Target company hint (optional): {target_company_hint}" if target_company_hint else ""

    # Run the chain
    raw_text = chain.invoke(
        {
            "json_schema": json.dumps(NEWS_ANALYSIS_JSON_SCHEMA, indent=2),
            "articles": articles_json,
            "target_hint": target_hint,
        }
    )

    # Best-effort JSON parse with graceful fallback
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # If the model emits extra text, try trimming to the first/last braces
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(raw_text[start : end + 1])
            except Exception:
                parsed = _empty_payload()
        else:
            parsed = _empty_payload()

    # Ensure required keys exist
    for k in NEWS_ANALYSIS_JSON_SCHEMA.keys():
        parsed.setdefault(k, [] if isinstance(NEWS_ANALYSIS_JSON_SCHEMA[k], list) else "")

    return {
        "raw_articles": items,
        "analysis_json": parsed,
        "raw_model_text": raw_text,
    }


def _empty_payload() -> Dict[str, Any]:
    return {
        "relevant_articles": [],
        "themes": [],
        "sentiment": "neutral",
        "risks": [],
        "opportunities": [],
        "pro_summary": "",
        "plain_summary": "",
    }


# ---- Example usage -----------------------------------------------------------

def _get_news_sample(news: Dict[str, Any]):
    """Safely extract a list of news items from different possible shapes."""
    if isinstance(news, dict):
        if "sample" in news and isinstance(news["sample"], list):
            return news["sample"]
        if "results" in news and isinstance(news["results"], list):
            return news["results"]
    return []

if __name__ == "__main__":
    from collect_raw_data import collect_raw_data

    TICKER = os.getenv("TEST_TICKER", "AAPL").strip() or "AAPL"

    data = collect_raw_data(TICKER)
    meta = data.get("meta", {}) or {}
    news = data.get("news", {}) or {}

    news_sample = _get_news_sample(news)
    company_hint = meta.get("company_name") or TICKER

    result = analyze_news(news_sample, target_company_hint=company_hint)

    print("\n=== News Analysis (JSON) ===\n")
    print(json.dumps(result["analysis_json"], indent=2))
