import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.analyze import calculate
from scripts.fetch_opendart import business_year, parse_xbrl_annual


class RatioTests(unittest.TestCase):
    def test_annual_ratios_use_average_balances(self):
        base = {"report_code": "11011", "report_name": "사업보고서", "period_order": 4, "period_months": 12}
        first = {**base, "year": 2021, "revenue": 100.0, "cost_of_sales": 60.0, "gross_profit": 40.0,
                 "operating_income": 10.0, "net_income": 8.0, "current_assets": 50.0, "current_liabilities": 25.0,
                 "total_assets": 100.0, "total_liabilities": 40.0, "total_equity": 60.0,
                 "cash_and_cash_equivalents": 10.0, "accounts_receivable": 20.0, "inventory": 15.0,
                 "short_term_borrowings": 5.0, "long_term_borrowings": 15.0, "operating_cash_flow": 12.0,
                 "capex_ppe": -4.0, "capex_intangibles": -1.0}
        second = {**first, "year": 2022, "revenue": 120.0, "net_income": 12.0, "total_assets": 140.0,
                  "total_equity": 80.0, "accounts_receivable": 24.0, "inventory": 18.0}
        result = calculate([first, second])[1]
        self.assertAlmostEqual(result["revenue_growth_pct"], 20.0)
        self.assertAlmostEqual(result["roa_pct"], 10.0)
        self.assertAlmostEqual(result["free_cash_flow"], 7.0)

    def test_business_year_uses_report_title(self):
        filing = {"report_nm": "[기재정정]사업보고서 (2013.12)", "rcept_dt": "20150330"}
        self.assertEqual(business_year(filing), 2013)

    def test_legacy_xbrl_parser_extracts_required_accounts(self):
        fields = {
            "revenue": {"statement": "IS", "names": ["매출액"], "ids": ["ifrs-full_Revenue"]},
            "operating_income": {"statement": "IS", "names": ["영업이익"], "ids": ["dart_OperatingIncomeLoss"]},
            "net_income": {"statement": "IS", "names": ["당기순이익"], "ids": ["ifrs-full_ProfitLoss"]},
            "current_assets": {"statement": "BS", "names": ["유동자산"], "ids": ["ifrs-full_CurrentAssets"]},
            "total_assets": {"statement": "BS", "names": ["자산총계"], "ids": ["ifrs-full_Assets"]},
            "current_liabilities": {"statement": "BS", "names": ["유동부채"], "ids": ["ifrs-full_CurrentLiabilities"]},
            "total_liabilities": {"statement": "BS", "names": ["부채총계"], "ids": ["ifrs-full_Liabilities"]},
            "total_equity": {"statement": "BS", "names": ["자본총계"], "ids": ["ifrs-full_Equity"]},
            "operating_cash_flow": {"statement": "CF", "names": ["영업활동현금흐름"], "ids": ["ifrs-full_CashFlowsFromUsedInOperatingActivities"]},
        }
        duration = '<xbrli:context id="D"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2013-01-01</xbrli:startDate><xbrli:endDate>2013-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
        instant = '<xbrli:context id="I"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2013-12-31</xbrli:instant></xbrli:period></xbrli:context>'
        facts = ''.join(f'<ifrs:{name} contextRef="{context}">100</ifrs:{name}>' for name, context in [
            ("Revenue", "D"), ("OperatingIncomeLoss", "D"), ("ProfitLoss", "D"),
            ("CurrentAssets", "I"), ("Assets", "I"), ("CurrentLiabilities", "I"),
            ("Liabilities", "I"), ("Equity", "I"), ("CashFlowsFromUsedInOperatingActivities", "D")])
        xml = f'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ifrs="urn:ifrs">{duration}{instant}{facts}</xbrli:xbrl>'
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "sample.zip"
            with ZipFile(archive, "w") as zipped:
                zipped.writestr("instance.xbrl", xml)
            row, warnings = parse_xbrl_annual(archive, 2013, fields)
        self.assertEqual(warnings, [])
        self.assertEqual(row["revenue"], 100)


if __name__ == "__main__":
    unittest.main()
