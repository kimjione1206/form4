"""회사 한 줄 소개·직함 번역·한국어 회사 이름 표. AI(Claude 루틴)가 채우고, 여기서 검사한다."""

import json
import re
from pathlib import Path

from form4 import config
from form4.sec import submissions_url

DIGIT_RE = re.compile(r"\d")
MAX_NAME_TODO = 300  # 한국어 이름 할 일은 금액 큰 회사부터 이만큼만


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def guard_text(s: str, max_len: int = 40) -> bool:
    return (bool(s) and len(s) <= max_len and not DIGIT_RE.search(s)
            and not any(w in s for w in config.FORBIDDEN_WORDS))


def check_tables(companies: dict, titles: dict, names: dict) -> list[str]:
    errors = []
    for cik, c in companies.items():
        s = c.get("summary")
        if s is not None and not guard_text(s):
            errors.append(f"회사 {cik}: {s!r}")
    for en, ko in titles.items():
        if not guard_text(ko, 30):
            errors.append(f"직함 {en!r}: {ko!r}")
    for ticker, ko in names.items():
        if not guard_text(ko, 20):
            errors.append(f"한국어 이름 {ticker!r}: {ko!r}")
    return errors


def company_line(cik: str, companies: dict) -> str:
    c = companies.get(cik, {})
    s = c.get("summary")
    if s and guard_text(s):
        return s
    return c.get("sic_description") or ""


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
               names: dict) -> dict:
    """회사 소개는 조건 충족 목록(results)만, 직함 번역·한국어 이름은 페이지가 있는 모든 회사(profiles)에서."""
    todo_companies = [
        {"cik": c["issuer_cik"], "name": companies[c["issuer_cik"]]["name"],
         "sic_description": companies[c["issuer_cik"]]["sic_description"]}
        for c in results
        if companies.get(c["issuer_cik"], {}).get("summary") is None
    ]
    todo_titles = sorted({t for c in profiles for t in c["officer_titles"] if t not in titles})
    todo_names, seen = [], set()
    for c in sorted(profiles, key=lambda c: -(c["total_usd"] + c["sale_usd"])):
        if c["ticker"] not in seen and not korean_name(c["ticker"], names):
            seen.add(c["ticker"])
            todo_names.append({"t": c["ticker"], "n": c["name"]})
    return {"companies": todo_companies, "titles": todo_titles, "names": todo_names[:MAX_NAME_TODO]}
