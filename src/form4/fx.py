"""달러→원 환율 (유럽중앙은행 기준, Frankfurter 무료 API). 실패하면 전날 값."""

import httpx

FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=KRW"


def current_rate(client: httpx.Client, fallback: dict | None) -> dict:
    try:
        r = client.get(FX_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
        return {"rate": float(data["rates"]["KRW"]), "date": data["date"]}
    except (httpx.HTTPError, KeyError, ValueError):
        if fallback:
            return fallback
        raise
