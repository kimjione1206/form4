"""어제 목록과 비교해 '오늘의 정리'를 만든다."""


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
