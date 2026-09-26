"""정규화 재무자료에서 주요 재무비율과 대시보드 JSON을 생성한다."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def num(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def divide(numerator: float | None, denominator: float | None, scale: float = 100) -> float | None:
    return None if numerator is None or denominator in (None, 0) else numerator / denominator * scale


def avg(current: float | None, previous: float | None) -> float | None:
    return None if current is None or previous is None else (current + previous) / 2


def add(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def load_rows() -> list[dict]:
    with (ROOT / "data" / "financial_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            rows.append({
                key: int(value) if key in {"year", "period_order", "period_months"}
                else value if key in {"report_code", "report_name"}
                else num(value)
                for key, value in raw.items()
            })
    return sorted(rows, key=lambda row: (row["year"], row["period_order"]))


def calculate(rows: list[dict]) -> list[dict]:
    prior_by_code: dict[str, dict] = {}
    ratios = []
    for row in rows:
        prior = prior_by_code.get(row["report_code"])
        annual_factor = 12 / row["period_months"]
        average_assets = avg(row.get("total_assets"), prior.get("total_assets") if prior else None)
        average_equity = avg(row.get("total_equity"), prior.get("total_equity") if prior else None)
        average_receivables = avg(row.get("accounts_receivable"), prior.get("accounts_receivable") if prior else None)
        average_inventory = avg(row.get("inventory"), prior.get("inventory") if prior else None)
        total_debt = add(row.get("short_term_borrowings"), row.get("long_term_borrowings"))
        capex = add(row.get("capex_ppe"), row.get("capex_intangibles"))
        if capex is not None:
            capex = abs(capex)
        free_cash_flow = row.get("operating_cash_flow") - capex if row.get("operating_cash_flow") is not None and capex is not None else None
        ratios.append({
            "year": row["year"], "report_code": row["report_code"], "report_name": row["report_name"],
            "period_order": row["period_order"], "period_months": row["period_months"],
            "revenue_growth_pct": divide(row["revenue"] - prior["revenue"], prior["revenue"]) if prior else None,
            "gross_margin_pct": divide(row.get("gross_profit"), row["revenue"]),
            "operating_margin_pct": divide(row["operating_income"], row["revenue"]),
            "net_margin_pct": divide(row["net_income"], row["revenue"]),
            "current_ratio_pct": divide(row["current_assets"], row["current_liabilities"]),
            "quick_ratio_pct": divide(add(row.get("cash_and_cash_equivalents"), row.get("accounts_receivable")), row["current_liabilities"]),
            "debt_ratio_pct": divide(row["total_liabilities"], row["total_assets"]),
            "debt_to_equity_pct": divide(row["total_liabilities"], row["total_equity"]),
            "equity_ratio_pct": divide(row["total_equity"], row["total_assets"]),
            "borrowings": total_debt,
            "net_debt": total_debt - row["cash_and_cash_equivalents"] if total_debt is not None and row.get("cash_and_cash_equivalents") is not None else None,
            "roa_pct": divide(row["net_income"] * annual_factor, average_assets),
            "roe_pct": divide(row["net_income"] * annual_factor, average_equity),
            "asset_turnover_x": divide(row["revenue"] * annual_factor, average_assets, 1),
            "inventory_turnover_x": divide(row.get("cost_of_sales") * annual_factor if row.get("cost_of_sales") is not None else None, average_inventory, 1),
            "dso_days": divide(average_receivables, row["revenue"] * annual_factor, 365),
            "cfo_margin_pct": divide(row["operating_cash_flow"], row["revenue"]),
            "cfo_conversion_pct": divide(row["operating_cash_flow"], row["net_income"]),
            "capex": capex,
            "free_cash_flow": free_cash_flow,
            "fcf_margin_pct": divide(free_cash_flow, row["revenue"]),
        })
        prior_by_code[row["report_code"]] = row
    return ratios


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = load_rows()
    if not rows:
        raise RuntimeError("분석할 데이터가 없습니다.")
    ratios = calculate(rows)
    write_csv(ROOT / "data" / "ratios.csv", ratios)
    accounts = json.loads((ROOT / "config" / "accounts.json").read_text(encoding="utf-8"))
    disclosures_path = ROOT / "reports" / "opendart_disclosures.json"
    disclosures = json.loads(disclosures_path.read_text(encoding="utf-8")) if disclosures_path.exists() else {"filings": []}
    latest_filing = disclosures.get("filings", [])[-1] if disclosures.get("filings") else None
    dashboard = {
        "schema_version": 1,
        "company": "LG전자",
        "stock_code": "066570",
        "corp_code": "00401731",
        "basis": "연결 기준 · 금액 단위 원 · 분기/반기 손익 및 현금흐름은 누적 기준",
        "updated_at": latest_filing.get("rcept_dt") if latest_filing else f"{rows[-1]['year']}-12-31",
        "source": {
            "provider": "OpenDART 단일회사 전체 재무제표 API",
            "rss_url": "https://dart.fss.or.kr/api/companyRSS.xml?crpCd=00401731",
            "report_url": "https://dart.fss.or.kr/dsab002/main.do?autoSearch=true&textCrpCik=00401731"
        },
        "account_labels": {key: value["label"] for key, value in accounts.items()},
        "financials": rows,
        "ratios": ratios,
        "annual_financials": [row for row in rows if row["report_code"] == "11011"],
        "annual_ratios": [row for row in ratios if row["report_code"] == "11011"],
        "filings": disclosures.get("filings", []),
    }
    (ROOT / "data" / "dashboard.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"분석 완료: {len(rows)}개 기간, 연간 {len(dashboard['annual_financials'])}개")


if __name__ == "__main__":
    main()
