"""조건 충족 목록 계산 (스펙 5장).

공동 신고(한 신고서에 신고자 여럿)는 금액을 회사 총액에 한 번만 더하고,
1인 1만 달러 판정에는 신고자 각자에게 금액 전체를 붙인다.
"""

import re
from collections import defaultdict
from datetime import date, timedelta

from form4 import config
from form4.tables import guard_text

CEO_RE = re.compile(r"chief executive|\bceo\b", re.I)
VP_RE = re.compile(r"vice[\s-]*president|\b[se]?vp\b", re.I)
SLUG_RE = re.compile(r"[^A-Z0-9.-]")
ALNUM_RE = re.compile(r"[A-Z0-9]")
PLACEHOLDER_TICKERS = {"", "NONE", "N/A"}


def _is_insider(o: dict) -> bool:
    """사람 임원·이사만. 이사 자리를 가진 펀드·법인(is_entity)은 사람으로 세지 않는다."""
    return (o["is_director"] or o["is_officer"]) and not o.get("is_entity", False)


def _has_person(r: dict) -> bool:
    return any(_is_insider(o) for o in r["owners"])


def _is_holder(o: dict) -> bool:
    return o["is_ten_pct"] or ((o["is_director"] or o["is_officer"]) and o.get("is_entity", False))


def owner_label(o: dict, titles: dict[str, str]) -> str:
    if o["is_officer"]:
        title = o["title"].strip()
        if title in titles and guard_text(titles[title], 30):
            return titles[title]
        if CEO_RE.search(title):
            return "대표이사"
        return title or "임원"
    if o["is_director"]:
        return "이사"
    return "대주주"


def _slug(ticker: str) -> str:
    return SLUG_RE.sub("", ticker.upper())


def _value(r: dict) -> float:
    return r["shares"] * r["price"]


def _increase(rs: list[dict]):
    last = rs[-1]
    if last["after"] is None:
        return None
    bought = sum(r["shares"] for r in rs if r["direct"] == last["direct"])
    before = last["after"] - bought
    if before <= 0:
        return "new"
    return bought / before


def _rows(counted: list[dict], qualified: set[str], titles: dict[str, str]) -> list[dict]:
    groups = defaultdict(list)
    for r in counted:
        groups[r["accession"]].append(r)
    rows = []
    for rs in groups.values():
        rs.sort(key=lambda r: r["date"])
        owners = [o for o in rs[0]["owners"] if o["cik"] in qualified]
        labels = [owner_label(o, titles) for o in owners]
        who = labels[0] if len(labels) == 1 else f"{labels[0]} 외 {len(labels) - 1}명"
        tags = []
        if rs[0]["plan"]:
            tags.append("계획 매수")
        if any(r["direct"] == "I" for r in rs):
            tags.append("간접")
        rows.append({
            "date": rs[-1]["date"], "filed": rs[0]["filed"], "who": who,
            "value": sum(_value(r) for r in rs), "increase": _increase(rs),
            "tags": tags, "url": rs[0]["url"],
            "ceo": any(o["is_officer"] and CEO_RE.search(o["title"]) for o in owners),
        })
    rows.sort(key=lambda x: (x["date"], x["value"]), reverse=True)
    return rows


def _same_day(counted: list[dict], qualified: set[str], info: dict[str, dict]) -> bool:
    by_filed = defaultdict(lambda: defaultdict(float))
    for r in counted:
        for o in r["owners"]:
            if o["cik"] in qualified:
                by_filed[r["filed"]][o["cik"]] += _value(r)
    for amounts in by_filed.values():
        if len(amounts) < 3:
            continue
        vals = list(amounts.values())
        if max(vals) > min(vals) * config.SAME_DAY_TOLERANCE:
            continue
        vp = sum(1 for c in amounts if VP_RE.search(info[c]["title"]))
        if vp * 2 > len(amounts):
            return True
    return False


def _company(cik: str, rs: list[dict], titles: dict[str, str]) -> dict | None:
    rs = [r for r in rs if not (r["code"] == "P" and r.get("drip"))]  # 배당 재투자는 아예 안 셈
    ticker = next((r["ticker"] for r in sorted(rs, key=lambda r: r["filed"], reverse=True)
                   if r["ticker"]), "")
    if ticker.strip().upper() in PLACEHOLDER_TICKERS or not ALNUM_RE.search(ticker.upper()):
        return None  # 종목 코드가 없는 비상장 펀드·BDC는 방문자가 살 수 없음
    person_buys = [r for r in rs if r["code"] == "P" and _has_person(r)]
    buys = [r for r in person_buys if not r["offering"]]  # 증자 참여는 시장 매수가 아님
    per_person, info = defaultdict(float), {}
    for r in buys:
        for o in r["owners"]:
            if _is_insider(o):
                per_person[o["cik"]] += _value(r)
                info[o["cik"]] = o
    qualified = {c for c, v in per_person.items() if v >= config.MIN_PERSON_USD}
    if len(qualified) < config.MIN_PEOPLE:
        return None
    counted = [r for r in buys if any(o["cik"] in qualified for o in r["owners"])]
    rows = _rows(counted, qualified, titles)
    latest = max(rs, key=lambda r: (r["filed"], r["accession"]))
    tags = []
    if any(r["ceo"] for r in rows):
        tags.append("대표이사 포함")
    if _same_day(counted, qualified, info):
        tags.append("같은 날 여러 명 매수")
    if any("계획 매수" in r["tags"] for r in rows):
        tags.append("계획 매수 포함")
    return {
        "issuer_cik": cik,
        "name": latest["issuer_name"],
        "ticker": ticker,
        "slug": _slug(ticker),
        "people": len(qualified),
        "total_usd": sum(_value(r) for r in counted),
        "sales": len({r["accession"] for r in rs if r["code"] == "S"}),
        "offering_usd": sum(_value(r) for r in person_buys if r["offering"]),
        "ten_pct_usd": sum(_value(r) for r in rs if r["code"] == "P" and not _has_person(r)
                           and any(_is_holder(o) for o in r["owners"])),
        "first_date": min(r["date"] for r in counted),
        "last_date": max(r["date"] for r in counted),
        "tags": tags,
        "officer_titles": sorted({info[c]["title"] for c in qualified
                                  if info[c]["is_officer"] and info[c]["title"]}),
        "rows": rows,
        "top": max(rows, key=lambda x: x["value"]),
    }


def rank(records: list[dict], as_of: date, titles: dict[str, str]) -> list[dict]:
    start = (as_of - timedelta(days=config.WINDOW_DAYS - 1)).isoformat()
    end = as_of.isoformat()
    by_company = defaultdict(list)
    for r in records:
        if start <= r["date"] <= end:
            by_company[r["issuer_cik"]].append(r)
    results = [c for cik, rs in by_company.items() if (c := _company(cik, rs, titles))]
    results.sort(key=lambda c: (-c["people"], -c["total_usd"], c["name"]))
    used = set()
    for c in results:
        if c["slug"] in used:
            c["slug"] = f"{c['slug']}-{c['issuer_cik']}"
        used.add(c["slug"])
    return results
