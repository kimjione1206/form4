"""거래 줄을 data/transactions.jsonl 에 보관한다 (최근 60일)."""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from form4 import config

SALE_KEYS = ("accession", "form", "filed", "issuer_cik", "issuer_name", "ticker",
             "owners", "url", "code", "date")


def owners_key(r: dict) -> tuple:
    return tuple(sorted(o["cik"] for o in r["owners"]))


def has_insider(r: dict) -> bool:
    return any(o["is_director"] or o["is_officer"] for o in r["owners"])


def bad_price(r: dict) -> bool:
    """주당 가격이 말이 안 되게 큰 줄(신고서 원문 오류). 실제로 비싼 종목은 예외."""
    return r["price"] > config.MAX_PRICE_PER_SHARE and r["ticker"].upper() not in config.PRICE_CHECK_EXEMPT


def _collapse_sales(records: list[dict]) -> list[dict]:
    """매도(S)는 신고서당 한 줄로 줄이고(수량·금액은 합계), 임원·이사가 낀 것만 남긴다."""
    out, sales = [], defaultdict(list)
    for r in records:
        if r["code"] != "S":
            out.append(r)
        elif has_insider(r):
            sales[r["accession"]].append(r)
    for lines in sales.values():
        last = max(enumerate(lines), key=lambda x: (x[1]["date"], x[0]))[1]  # 같은 날이면 뒤에 적힌 줄
        good = [r for r in lines if not bad_price(r)]
        out.append({
            **{k: last[k] for k in SALE_KEYS},
            "shares": sum(r["shares"] for r in good),
            "value": sum(r["shares"] * r["price"] for r in good),
            "after": last["after"], "direct": last["direct"],
            "plan": any(r["plan"] for r in lines),
            "exercise": any(r["exercise"] for r in lines),
            **({"price_error": True} if len(good) < len(lines) else {}),
        })
    return out


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
