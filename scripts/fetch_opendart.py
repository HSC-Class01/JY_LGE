"""LG전자의 2010년 이후 정기공시와 OpenDART 재무 데이터를 증분 수집한다."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://opendart.fss.or.kr/api"
COMPANY = {"name": "LG전자", "corp_code": "00401731", "stock_code": "066570"}
REPORTS = {"11013": ("1분기보고서", 1), "11012": ("반기보고서", 2), "11014": ("3분기보고서", 3), "11011": ("사업보고서", 4)}
REQUIRED = {"revenue", "operating_income", "net_income", "current_assets", "total_assets", "current_liabilities", "total_liabilities", "total_equity", "operating_cash_flow"}


def compact(value: str) -> str:
    return re.sub(r"[\s·ㆍ]", "", value or "").replace("(손실)", "")


def load_local_key() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_json(endpoint: str, params: dict[str, str], retries: int = 3) -> dict:
    url = f"{API}/{endpoint}?{urlencode(params)}"
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "LGE-DART-Agent/1.0"})
            with urlopen(req, timeout=60) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == retries - 1:
                raise RuntimeError(f"OpenDART 요청 실패: {endpoint}: {error}") from error
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def amount(item: dict) -> int | None:
    key = "thstrm_amount" if item.get("sj_div") == "BS" else "thstrm_add_amount"
    raw = item.get(key) or item.get("thstrm_amount")
    if not raw or raw.strip() in {"-", ""}:
        return None
    try:
        return int(raw.replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def score_candidate(item: dict, spec: dict) -> tuple[int, int, int]:
    exact_id = int(item.get("account_id") in spec.get("ids", []))
    exact_name = int(compact(item.get("account_nm", "")) in {compact(x) for x in spec.get("names", [])})
    statement = int(item.get("sj_div") == spec.get("statement"))
    return exact_id, exact_name, statement


def normalise(year: int, report_code: str, items: list[dict], accounts: dict) -> tuple[dict, list[str]]:
    report_name, period_order = REPORTS[report_code]
    row = {
        "year": year,
        "report_code": report_code,
        "report_name": report_name,
        "period_order": period_order,
        "period_months": period_order * 3,
        **{field: None for field in accounts},
    }
    for field, spec in accounts.items():
        candidates = [item for item in items if score_candidate(item, spec)[:2] != (0, 0)]
        candidates.sort(key=lambda item: score_candidate(item, spec), reverse=True)
        if candidates:
            row[field] = amount(candidates[0])
    missing = sorted(field for field in REQUIRED if row[field] is None)
    return row, missing


def list_filings(key: str, start_year: int) -> list[dict]:
    page, results = 1, []
    while True:
        data = request_json("list.json", {
            "crtfc_key": key,
            "corp_code": COMPANY["corp_code"],
            "bgn_de": f"{start_year}0101",
            "end_de": date.today().strftime("%Y%m%d"),
            "pblntf_ty": "A",
            "page_no": str(page),
            "page_count": "100",
        })
        if data.get("status") == "013":
            return results
        if data.get("status") != "000":
            raise RuntimeError(f"공시 목록 오류 {data.get('status')}: {data.get('message')}")
        results.extend(data.get("list", []))
        if page >= int(data.get("total_page", 1)):
            return results
        page += 1


def business_year(filing: dict) -> int:
    match = re.search(r"\((20\d{2})[.년]", filing.get("report_nm", ""))
    if match:
        return int(match.group(1))
    return int(filing.get("rcept_dt", "0000")[:4]) - 1


def download_archives(key: str, filings: list[dict]) -> list[str]:
    target = ROOT / "reports" / "source"
    target.mkdir(parents=True, exist_ok=True)
    warnings = []
    for filing in filings:
        receipt = filing["rcept_no"]
        archive = target / f"{receipt}.zip"
        if archive.exists():
            continue
        url = f"{API}/document.xml?{urlencode({'crtfc_key': key, 'rcept_no': receipt})}"
        try:
            with urlopen(Request(url, headers={"User-Agent": "LGE-DART-Agent/1.0"}), timeout=120) as response:
                payload = response.read()
            if payload[:2] == b"PK":
                archive.write_bytes(payload)
            else:
                warnings.append(f"{receipt}: 사업보고서 원문 ZIP 없음")
        except (HTTPError, URLError, TimeoutError) as error:
            warnings.append(f"{receipt}: 사업보고서 원문 ZIP 다운로드 실패({error})")
    return warnings


def download_xbrl_archives(key: str, filings: list[dict]) -> list[str]:
    """2010~2014를 포함한 장기 원본 보존용 XBRL ZIP을 가능한 범위에서 받는다."""
    target = ROOT / "data" / "xbrl"
    target.mkdir(parents=True, exist_ok=True)
    warnings = []
    for filing in filings:
        receipt = filing["rcept_no"]
        archive = target / f"{receipt}.zip"
        if archive.exists():
            continue
        url = f"{API}/fnlttXbrl.xml?{urlencode({'crtfc_key': key, 'rcept_no': receipt})}"
        try:
            with urlopen(Request(url, headers={"User-Agent": "LGE-DART-Agent/1.0"}), timeout=120) as response:
                payload = response.read()
            if payload[:2] == b"PK":
                archive.write_bytes(payload)
            else:
                warnings.append(f"{receipt}: XBRL 원본 없음")
        except (HTTPError, URLError, TimeoutError) as error:
            warnings.append(f"{receipt}: XBRL 다운로드 실패({error})")
    return warnings


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def parse_xbrl_annual(archive: Path, year: int, accounts: dict) -> tuple[dict | None, list[str]]:
    """오래된 XBRL에서 연결 연간 값을 추출한다. 찾지 못한 값은 경고로 남긴다."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            candidates = [name for name in zipped.namelist() if name.lower().endswith((".xbrl", ".xml"))]
            instance = next((name for name in candidates if "instance" in name.lower()), candidates[0] if candidates else None)
            if not instance:
                return None, [f"{year}: XBRL 인스턴스 없음"]
            root = ET.fromstring(zipped.read(instance))
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as error:
        return None, [f"{year}: XBRL 파싱 실패({error})"]

    contexts: dict[str, tuple[str | None, str | None, bool]] = {}
    for node in root.iter():
        if local_name(node.tag) != "context":
            continue
        cid = node.attrib.get("id", "")
        start = end = None
        dimensional = False
        for child in node.iter():
            name = local_name(child.tag)
            if name == "startDate":
                start = child.text
            elif name in {"endDate", "instant"}:
                end = child.text
            elif name in {"segment", "scenario", "explicitMember", "typedMember"}:
                dimensional = True
        contexts[cid] = (start, end, dimensional)

    row = {"year": year, "report_code": "11011", "report_name": "사업보고서", "period_order": 4,
           "period_months": 12, **{field: None for field in accounts}}
    aliases = {
        field: {compact(name) for name in spec.get("names", [])}
        | {compact(value.split("_")[-1]) for value in spec.get("ids", [])}
        for field, spec in accounts.items()
    }
    ranked: dict[str, tuple[int, int]] = {}
    for fact in root.iter():
        context_id = fact.attrib.get("contextRef")
        if not context_id or context_id not in contexts or fact.text is None:
            continue
        start, end, dimensional = contexts[context_id]
        if not end or not end.startswith(str(year)):
            continue
        concept = compact(local_name(fact.tag))
        try:
            value = int(round(float(fact.text.replace(",", "").strip())))
        except ValueError:
            continue
        for field, names in aliases.items():
            if concept not in names:
                continue
            is_balance = accounts[field].get("statement") == "BS"
            annual_duration = bool(start and start.startswith(str(year)))
            score = (0 if dimensional else 4) + (2 if is_balance and start is None else 0) + (2 if not is_balance and annual_duration else 0)
            if score > ranked.get(field, (-1, 0))[0]:
                ranked[field] = (score, value)
                row[field] = value
    missing = sorted(field for field in REQUIRED if row[field] is None)
    if missing:
        return None, [f"{year}: XBRL 필수 계정 누락({', '.join(missing)})"]
    return row, []


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", help="OpenDART 인증키. 생략하면 DART_API_KEY 환경변수를 사용합니다.")
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--skip-report-archives", action="store_true")
    args = parser.parse_args()
    if args.start_year < 2010:
        raise SystemExit("시작연도는 2010년 이후여야 합니다.")
    load_local_key()
    key = args.api_key or os.environ.get("DART_API_KEY")
    if not key:
        raise SystemExit("DART_API_KEY가 없습니다. API_KEY_SETUP.txt를 참고하세요.")

    accounts = json.loads((ROOT / "config" / "accounts.json").read_text(encoding="utf-8"))
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows, warnings = [], []
    for year in range(args.start_year, date.today().year + 1):
        for report_code, (report_name, _) in REPORTS.items():
            response = request_json("fnlttSinglAcntAll.json", {
                "crtfc_key": key,
                "corp_code": COMPANY["corp_code"],
                "bsns_year": str(year),
                "reprt_code": report_code,
                "fs_div": "CFS",
            })
            if response.get("status") == "013":
                continue
            if response.get("status") != "000":
                warnings.append(f"{year} {report_name}: {response.get('status')} {response.get('message')}")
                continue
            (raw_dir / f"lge_{year}_{report_code}.json").write_text(
                json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            row, missing = normalise(year, report_code, response.get("list", []), accounts)
            if missing:
                warnings.append(f"{year} {report_name}: 필수 계정 누락({', '.join(missing)}) — 기간 제외")
                continue
            rows.append(row)

    filings = list_filings(key, args.start_year)
    annual = [item for item in filings if "사업보고서" in item.get("report_nm", "")]
    annual.sort(key=lambda item: item.get("rcept_dt", ""))
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "opendart_disclosures.json").write_text(json.dumps({
        "company": COMPANY,
        "source_rss": "https://dart.fss.or.kr/api/companyRSS.xml?crpCd=00401731",
        "filings": annual,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.skip_report_archives:
        warnings.extend(download_archives(key, annual))
        warnings.extend(download_xbrl_archives(key, annual))
    legacy_by_year = {}
    for filing in annual:
        filing_year = business_year(filing)
        if filing_year < args.start_year or filing_year >= 2015:
            continue
        legacy_by_year[filing_year] = ROOT / "data" / "xbrl" / f"{filing['rcept_no']}.zip"
    existing_years = {row["year"] for row in rows if row["report_code"] == "11011"}
    for year, archive in sorted(legacy_by_year.items()):
        if year in existing_years or not archive.exists():
            continue
        legacy_row, legacy_warnings = parse_xbrl_annual(archive, year, accounts)
        warnings.extend(legacy_warnings)
        if legacy_row:
            rows.append(legacy_row)
    if not rows:
        raise RuntimeError("수집된 완전한 연결 재무제표가 없습니다. API 키와 공시 여부를 확인하세요.")
    rows.sort(key=lambda row: (row["year"], row["period_order"]))
    fields = ["year", "report_code", "report_name", "period_order", "period_months", *accounts]
    write_csv(ROOT / "data" / "financial_summary.csv", rows, fields)
    (ROOT / "data" / "fetch_warnings.json").write_text(
        json.dumps(warnings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"수집 완료: 재무기간 {len(rows)}개, 사업보고서 {len(annual)}건, 경고 {len(warnings)}건")


if __name__ == "__main__":
    main()
