"""회사 한 줄 소개·직함 번역·한국어 회사 이름·한국어 업종 표. AI(Claude 루틴)가 채우고, 여기서 검사한다."""

import json
import re
from pathlib import Path

from form4 import config
from form4.sec import submissions_url

DIGIT_RE = re.compile(r"\d")
TICKER_RE = re.compile(r"[A-Z0-9.\-]{1,10}")  # 할 일에 올릴 수 있는 깨끗한 종목 코드
MAX_NAME_TODO = 300  # 한국어 이름 할 일은 금액 큰 회사부터 이만큼만


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def guard_text(s: str, max_len: int = 40) -> bool:
    return (bool(s) and len(s) <= max_len and not DIGIT_RE.search(s)
            and not any(w in s for w in config.FORBIDDEN_WORDS))


def check_tables(companies: dict, titles: dict, names: dict, industries: dict | None = None) -> list[str]:
    errors = []
    for cik, c in companies.items():
        s = c.get("summary")
        if s is not None and not guard_text(s):
            errors.append(f"회사 {cik}: {s!r}")
    for en, ko in titles.items():
        if not guard_text(ko, 30):
            errors.append(f"직함 {en!r}: {ko!r}")
    for ticker, ko in names.items():
        if ko != "" and not guard_text(ko, 20):  # 빈 문자열 = 루틴이 건너뛴 회사 기록
            errors.append(f"한국어 이름 {ticker!r}: {ko!r}")
    for en, ko in (industries or {}).items():
        if not guard_text(ko, 30):
            errors.append(f"업종 {en!r}: {ko!r}")
    return errors


def company_line(cik: str, companies: dict, industries: dict | None = None) -> str:
    """회사 소개 → 한국어 업종(data/industries.json) → SEC 영어 업종 → 빈칸 순."""
    c = companies.get(cik, {})
    s = c.get("summary")
    if s and guard_text(s):
        return s
    sic = c.get("sic_description") or ""
    ko = (industries or {}).get(sic, "")
    return ko if guard_text(ko, 30) else sic


def korean_name(ticker: str, names: dict) -> str:
    """종목 코드로 찾은 한국어 회사 이름(예: 엔비디아). 검사를 못 넘으면 없는 것으로 친다."""
    k = names.get(ticker, "")
    return k if guard_text(k, 20) else ""


def ensure_company_info(results: list[dict], companies: dict, client) -> None:
    for c in results:
        cik = c["issuer_cik"]
        if cik in companies:
            continue
        text = client.get_text(submissions_url(cik))
        data = json.loads(text) if text else {}
        companies[cik] = {"name": c["name"], "sic_description": data.get("sicDescription") or "",
                          "summary": None}


def build_todo(results: list[dict], companies: dict, titles: dict, profiles: list[dict],
               names: dict, industries: dict | None = None) -> dict:
    """회사 소개는 조건 충족 목록(results)만, 직함 번역·한국어 이름은 페이지가 있는 모든 회사(profiles)에서.
    한국어 이름은 표에 아직 없는(빈 문자열로 건너뛴 것도 제외) 깨끗한 종목 코드만.
    업종은 companies.json 의 영어 업종 중 한국어 업종 표에 아직 없는 것."""
    todo_companies = [
        {"cik": c["issuer_cik"], "name": companies[c["issuer_cik"]]["name"],
         "sic_description": companies[c["issuer_cik"]]["sic_description"]}
        for c in results
        if companies.get(c["issuer_cik"], {}).get("summary") is None
    ]
    todo_titles = sorted({t for c in profiles for t in c["officer_titles"] if t not in titles})
    todo_names, seen = [], set()
    for c in sorted(profiles, key=lambda c: -(c["total_usd"] + c["sale_usd"])):
        t = c["ticker"]
        if (t not in seen and t not in names and TICKER_RE.fullmatch(t)
                and t not in config.PLACEHOLDER_TICKERS):
            seen.add(t)
            todo_names.append({"t": t, "n": c["name"]})
    todo_industries = sorted({c["sic_description"] for c in companies.values()
                              if c.get("sic_description") and c["sic_description"] not in (industries or {})})
    return {"companies": todo_companies, "titles": todo_titles, "names": todo_names[:MAX_NAME_TODO],
            "industries": todo_industries}
