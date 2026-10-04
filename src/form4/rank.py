"""조건 충족 목록 계산 (스펙 5장).

공동 신고(한 신고서에 신고자 여럿)는 금액을 회사 총액에 한 번만 더하고,
1인 1만 달러 판정에는 신고자 각자에게 금액 전체를 붙인다.
"""

import re
from collections import defaultdict
from datetime import date, timedelta

from form4 import config
from form4.store import bad_price
from form4.tables import guard_text

CEO_RE = re.compile(r"chief executive|\bceo\b", re.I)
VP_RE = re.compile(r"vice[\s-]*president|\b[se]?vp\b", re.I)
REMARKS_RE = re.compile(r"^\s*see\s+remarks?\s*$", re.I)  # 직함 칸에 "비고 참조"만 적은 신고
SLUG_RE = re.compile(r"[^A-Z0-9.-]")
ALNUM_RE = re.compile(r"[A-Z0-9]")


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
        if not title or REMARKS_RE.match(title):
            return "임원"
        if title in titles and guard_text(titles[title], 30):
            return titles[title]
        if CEO_RE.search(title):
            return "대표이사"
        return title
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
        tags = []
        if rs[0]["plan"]:
            tags.append("계획 매수")
        if any(r["direct"] == "I" for r in rs):
            tags.append("간접")
        rows.append({
            "date": rs[-1]["date"], "filed": rs[0]["filed"], "who": _who(owners, titles),
            "value": sum(_value(r) for r in rs), "increase": _increase(rs),
            "tags": tags, "url": rs[0]["url"],
            "ceo": any(o["is_officer"] and CEO_RE.search(o["title"]) for o in owners),
        })
    rows.sort(key=lambda x: (x["date"], x["value"]), reverse=True)
    return rows


def _who(owners: list[dict], titles: dict[str, str]) -> str:
    labels = [owner_label(o, titles) for o in owners]
    return labels[0] if len(labels) == 1 else f"{labels[0]} 외 {len(labels) - 1}명"


def _decrease(r: dict) -> float | None:
    shares, after = r.get("shares", 0.0), r.get("after")
    if after is None or after + shares <= 0:
        return None
    return shares / (after + shares)


def _sale_rows(sells: list[dict], titles: dict[str, str]) -> list[dict]:
    """매도는 저장할 때 이미 신고서당 한 줄. 예전 모양(금액 없음) 줄은 0으로 본다."""
    rows = []
    for r in sells:
        tags = []
        if r.get("plan"):
            tags.append("계획 매도")
        if r.get("exercise"):
            tags.append("옵션 행사 후 매도")
        if r.get("direct") == "I":
            tags.append("간접")
        rows.append({
            "date": r["date"], "filed": r["filed"],
            "who": _who([o for o in r["owners"] if _is_insider(o)], titles),
            "value": r.get("value", 0.0), "decrease": _decrease(r), "tags": tags, "url": r["url"],
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
    """임원·이사 개인의 장내 매수·매도가 하나라도 있고 종목 코드가 있는 회사. 조건 충족이면 qualified."""
    rs = [r for r in rs if not (r["code"] == "P" and r.get("drip"))]  # 배당 재투자는 아예 안 셈
    ticker = next((r["ticker"] for r in sorted(rs, key=lambda r: r["filed"], reverse=True)
                   if r["ticker"]), "")
    if ticker.strip().upper() in config.PLACEHOLDER_TICKERS or not ALNUM_RE.search(ticker.upper()):
        return None  # 종목 코드가 없는 비상장 펀드·BDC는 방문자가 살 수 없음
    latest = max(rs, key=lambda r: (r["filed"], r["accession"]))
    # 주당 가격이 비정상적으로 큰 매수 줄·매도 신고는 원문 오류로 보고 뺀다(매도는 저장할 때 이미 해당 줄을 뺐음)
    # 안내·원문 링크에는 임원·이사 개인이 낀 신고만(목록에 보이는 것과 건수가 같게)
    error_filings = {r["accession"]: {"filed": r["filed"], "url": r["url"]} for r in rs
                     if ((r["code"] == "P" and bad_price(r)) or (r["code"] == "S" and r.get("price_error")))
                     and _has_person(r)}
    rs = [r for r in rs if not ((r["code"] == "P" and bad_price(r))
                                or (r["code"] == "S" and r.get("price_error") and not r.get("shares")))]
    person_buys = [r for r in rs if r["code"] == "P" and _has_person(r)]
    buys = [r for r in person_buys if not r["offering"]]  # 증자 참여는 시장 매수가 아님
    sells = [r for r in rs if r["code"] == "S" and _has_person(r)]
    if not buys and not sells and not error_filings:
        return None
    per_person, info = defaultdict(float), {}
    for r in buys:
        for o in r["owners"]:
            if _is_insider(o):
                per_person[o["cik"]] += _value(r)
                info[o["cik"]] = o
    counted_people = {c for c, v in per_person.items() if v >= config.MIN_PERSON_USD}
    is_listed = len(counted_people) >= config.MIN_PEOPLE
    if not is_listed:
        counted_people = set(per_person)  # 목록 밖 회사는 기준 없이 있는 그대로 보여 준다
    counted = [r for r in buys if any(o["cik"] in counted_people for o in r["owners"])]
    rows = _rows(counted, counted_people, titles)
    tags = []
    if any(r["ceo"] for r in rows):
        tags.append("대표이사 포함")
    if _same_day(counted, counted_people, info):
        tags.append("같은 날 여러 명 매수")
    if any("계획 매수" in r["tags"] for r in rows):
        tags.append("계획 매수 포함")
    # 페이지에 직함이 보이는 사람(매수 표 + 매도 표) — 직함 번역 할 일에 쓴다
    shown = [info[c] for c in counted_people] + [o for r in sells for o in r["owners"] if _is_insider(o)]
    return {
        "issuer_cik": cik,
        "name": latest["issuer_name"],
        "ticker": ticker,
        "slug": _slug(ticker),
        "qualified": is_listed,
        "people": len(counted_people),
        "total_usd": sum(_value(r) for r in counted),
        "sale_people": len({o["cik"] for r in sells for o in r["owners"] if _is_insider(o)}),
        "sale_usd": sum(r.get("value", 0.0) for r in sells),
        "sale_rows": _sale_rows(sells, titles),
        "offering_usd": sum(_value(r) for r in person_buys if r["offering"]),
        "ten_pct_usd": sum(_value(r) for r in rs if r["code"] == "P" and not _has_person(r)
                           and any(_is_holder(o) for o in r["owners"])),
        "price_error_count": len(error_filings),
        "price_error_filings": sorted(error_filings.values(), key=lambda f: f["filed"], reverse=True),
        "first_date": min((r["date"] for r in counted), default=None),
        "last_date": max((r["date"] for r in counted), default=None),
        "tags": tags,
        "officer_titles": sorted({o["title"] for o in shown if o["is_officer"] and o["title"].strip()
                                  and not REMARKS_RE.match(o["title"])}),
        "rows": rows,
        "top": max(rows, key=lambda x: x["value"], default=None),
    }


def profiles(records: list[dict], as_of: date, titles: dict[str, str]) -> list[dict]:
    """임원·이사 거래가 있는 모든 회사. 조건 충족 회사가 먼저 와서 지금 목록의 주소(slug)가 그대로다."""
    start = (as_of - timedelta(days=config.WINDOW_DAYS - 1)).isoformat()
    end = as_of.isoformat()
    by_company = defaultdict(list)
    for r in records:
        if start <= r["date"] <= end:
            by_company[r["issuer_cik"]].append(r)
    results = [c for cik, rs in by_company.items() if (c := _company(cik, rs, titles))]
    results.sort(key=lambda c: (not c["qualified"], -c["people"], -c["total_usd"], c["name"]))
    used = set()
    for c in results:
        if c["slug"] in used:
            c["slug"] = f"{c['slug']}-{c['issuer_cik']}"
        used.add(c["slug"])
    return results


def rank(records: list[dict], as_of: date, titles: dict[str, str]) -> list[dict]:
    return [c for c in profiles(records, as_of, titles) if c["qualified"]]
