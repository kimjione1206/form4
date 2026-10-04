"""어제 목록과 비교해 '오늘의 정리'를 만든다."""

from datetime import date, timedelta


def snapshot(results: list[dict]) -> list[dict]:
    return [{"issuer_cik": c["issuer_cik"], "name": c["name"], "ticker": c["ticker"]}
            for c in results]


def briefing(results: list[dict], prev: list[dict] | None) -> dict:
    top = max(results, key=lambda c: c["total_usd"], default=None)
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


def recent(results: list[dict], as_of: date, days: int = 7, limit: int = 3) -> list[dict]:
    """최근 7일(기준일 포함) 안에 매수가 있었던 곳. 최근 거래일 순, 같으면 사람 많은 순."""
    start = (as_of - timedelta(days=days - 1)).isoformat()
    hits = [c for c in results if c["last_date"] and c["last_date"] >= start]
    hits.sort(key=lambda c: (c["last_date"], c["people"]), reverse=True)
    return hits[:limit]
