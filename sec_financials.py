# sec_financials.py

import requests
import datetime as dt
from typing import Optional, Dict, Any, List

SEC_BASE = "https://data.sec.gov"
HEADERS_SEC = {"User-Agent": "Your Name your@email.com", "Accept-Encoding": "gzip, deflate"}

def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[WARN] GET {url} failed: {e}")
        return None

def latest_annual_value(values: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    annuals = [v for v in values if v.get("fp") == "FY" or v.get("form") in {"10-K", "20-F"}]
    if not annuals:
        annuals = values[:]
    def parse_date(x):
        try:
            return dt.datetime.fromisoformat(x.get("end"))
        except:
            return dt.datetime.min
    annuals.sort(key=lambda v: (parse_date(v), int(v.get("fy", 0))), reverse=True)
    return annuals[0] if annuals else None

def get_us_gaap(facts: Dict[str, Any], tag: str) -> Optional[float]:
    try:
        tag_data = facts["facts"]["us-gaap"][tag]
        units = tag_data.get("units", {})
        usd_values = None
        for unit_key in ["USD", "USD/shares", "pure"]:
            if unit_key in units:
                usd_values = units[unit_key]
                break
        if not usd_values and units:
            usd_values = list(units.values())[0]
        latest = latest_annual_value(usd_values)
        return float(latest.get("val")) if latest else None
    except Exception:
        return None

def pull_sec_financials(cik: str) -> Dict[str, Any]:
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    data = fetch_json(url, headers=HEADERS_SEC)
    if not data:
        return {}

    g = lambda tag: get_us_gaap(data, tag)

    revenue = g("RevenueFromContractWithCustomerExcludingAssessedTax") or g("SalesRevenueNet") or g("Revenues")
    gross_profit = g("GrossProfit")
    operating_income = g("OperatingIncomeLoss") or g("OperatingIncome")
    net_income = g("NetIncomeLoss") or g("ProfitLoss")
    current_assets = g("AssetsCurrent")
    current_liabilities = g("LiabilitiesCurrent")
    equity = g("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest") or g("StockholdersEquity")
    cash = g("CashAndCashEquivalentsAtCarryingValue") or g("CashCashEquivalentsAndShortTermInvestments")

    lt_debt = g("LongTermDebtNoncurrent") or g("LongTermDebt")
    current_portion_lt_debt = g("LongTermDebtCurrent")
    st_borrow = g("ShortTermBorrowings")
    commercial_paper = g("CommercialPaper")
    total_debt = sum([v for v in [lt_debt, current_portion_lt_debt, st_borrow, commercial_paper] if v is not None])

    gross_margin = (gross_profit / revenue) if revenue and gross_profit is not None else None
    operating_margin = (operating_income / revenue) if revenue and operating_income is not None else None
    current_ratio = (current_assets / current_liabilities) if current_assets and current_liabilities else None
    debt_to_equity = (total_debt / equity) if equity and total_debt is not None else None

    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "net_income": net_income,
        "cash": cash,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "equity": equity,
        "total_debt": total_debt if total_debt != 0 else None,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "current_ratio": current_ratio,
        "debt_to_equity": debt_to_equity,
    }

# Example usage
if __name__ == "__main__":
    cik = "0000320193"  # AAPL
    sec = pull_sec_financials(cik)
    for k, v in sec.items():
        print(f"{k:20}: {v}")
