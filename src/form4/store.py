"""거래 줄을 data/transactions.jsonl 에 보관한다 (최근 60일)."""

import json
from datetime import date, timedelta
from pathlib import Path

SALE_KEYS = ("accession", "form", "filed", "issuer_cik", "issuer_name", "ticker",
             "owners", "url", "code", "date")


def owners_key(r: dict) -> tuple:
    return tuple(sorted(o["cik"] for o in r["owners"]))


def has_insider(r: dict) -> bool:
    return any(o["is_director"] or o["is_officer"] for o in r["owners"])


def _collapse_sales(records: list[dict]) -> list[dict]:
    """매도(S)는 신고서당 한 줄로 줄이고, 임원·이사가 낀 것만 남긴다."""
    out, sales = [], {}
    for r in records:
        if r["code"] != "S":
            out.append(r)
            continue
        if not has_insider(r):
            continue
        prev = sales.get(r["accession"])
        if prev is None or r["date"] > prev["date"]:
            sales[r["accession"]] = {k: r[k] for k in SALE_KEYS}
    return out + list(sales.values())


def merge(existing: list[dict], new: list[dict]) -> list[dict]:
    new = _collapse_sales(new)
    new_accessions = {r["accession"] for r in new}
    kept = [r for r in existing if r["accession"] not in new_accessions]
    rows = kept + new
    # 같은 (회사, 신고자, 거래일)의 정정 신고는 가장 최근 것(접수일, 접수번호) 하나만 남긴다.
    latest = {}
    for r in rows:
        if r["form"] == "4/A":
            key = (r["issuer_cik"], owners_key(r), r["date"])
            latest[key] = max(latest.get(key, ("", "")), (r["filed"], r["accession"]))
    return [r for r in rows
            if (key := (r["issuer_cik"], owners_key(r), r["date"])) not in latest
            or (r["form"] == "4/A" and r["accession"] == latest[key][1])]


def prune(records: list[dict], as_of: date, days: int) -> list[dict]:
    cutoff = (as_of - timedelta(days=days - 1)).isoformat()
    return [r for r in records if r["date"] >= cutoff]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda r: (r["date"], r["accession"], r["code"]))
    path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
                            for r in ordered))
