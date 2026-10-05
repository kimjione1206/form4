"""어제 목록과 비교해 '오늘의 정리'를 만든다."""

from datetime import date, timedelta


def snapshot(results: list[dict]) -> list[dict]:
    return [{"issuer_cik": c["issuer_cik"], "name": c["name"], "ticker": c["ticker"]}
            for c in results]


def briefing(results: list[dict], prev: list[dict] | None, total: str = "total_usd") -> dict:
    """total: 최대 금액을 고를 칸(매도 목록은 sell_total_usd)."""
    top = max(results, key=lambda c: c[total], default=None)
    if prev is None:
        return {"count": len(results), "new": [], "dropped": [], "top": top}
    prev_ciks = {p["issuer_cik"] for p in prev}
    now_ciks = {c["issuer_cik"] for c in results}
    return {
        "count": len(results),
        "new": [c for c in results if c["issuer_cik"] not in prev_ciks],
        "dropped": [p for p in prev if p["issuer_cik"] not in now_ciks],
        "top": top,
    }


def recent(results: list[dict], as_of: date, days: int = 7, limit: int = 3,
           last: str = "last_date", people: str = "people") -> list[dict]:
    """최근 7일(기준일 포함) 안에 거래가 있었던 곳. 최근 거래일 순, 같으면 사람 많은 순.
    last·people: 매도 목록은 sell_last_date·sell_people."""
    start = (as_of - timedelta(days=days - 1)).isoformat()
    hits = [c for c in results if c[last] and c[last] >= start]
    hits.sort(key=lambda c: (c[last], c[people]), reverse=True)
    return hits[:limit]
