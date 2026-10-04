"""회사 한 줄 소개·직함 번역 표. AI(Claude 루틴)가 채우고, 여기서 검사한다."""

import json
import re
from pathlib import Path

from form4 import config
from form4.sec import submissions_url

DIGIT_RE = re.compile(r"\d")


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def guard_text(s: str, max_len: int = 40) -> bool:
    return (bool(s) and len(s) <= max_len and not DIGIT_RE.search(s)
            and not any(w in s for w in config.FORBIDDEN_WORDS))


def check_tables(companies: dict, titles: dict) -> list[str]:
    errors = []
    for cik, c in companies.items():
        s = c.get("summary")
        if s is not None and not guard_text(s):
            errors.append(f"회사 {cik}: {s!r}")
    for en, ko in titles.items():
        if not guard_text(ko, 30):
            errors.append(f"직함 {en!r}: {ko!r}")
    return errors


def company_line(cik: str, companies: dict) -> str:
    c = companies.get(cik, {})
    s = c.get("summary")
    if s and guard_text(s):
        return s
    return c.get("sic_description") or ""


def ensure_company_info(results: list[dict], companies: dict, client) -> None:
    for c in results:
        cik = c["issuer_cik"]
        if cik in companies:
            continue
        text = client.get_text(submissions_url(cik))
        data = json.loads(text) if text else {}
        companies[cik] = {"name": c["name"], "sic_description": data.get("sicDescription") or "",
                          "summary": None}


def build_todo(results: list[dict], companies: dict, titles: dict) -> dict:
    todo_companies = [
        {"cik": c["issuer_cik"], "name": companies[c["issuer_cik"]]["name"],
         "sic_description": companies[c["issuer_cik"]]["sic_description"]}
        for c in results
        if companies.get(c["issuer_cik"], {}).get("summary") is None
    ]
    todo_titles = sorted({t for c in results for t in c["officer_titles"] if t not in titles})
    return {"companies": todo_companies, "titles": todo_titles}
