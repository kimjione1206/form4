"""SEC에 예의 바르게 요청하는 도구: 자기소개 꼬리표, 속도 제한, 재시도."""

import time
from datetime import date

import httpx

from form4 import config


class SecError(RuntimeError):
    pass


def index_url(d: date) -> str:
    quarter = (d.month - 1) // 3 + 1
    return (
        f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{quarter}/"
        f"master.{d:%Y%m%d}.idx"
    )


def submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"


class SecClient:
    def __init__(self, transport=None, rate=config.REQS_PER_SEC, sleep=time.sleep,
                 clock=time.monotonic, max_retries=5):
        self._http = httpx.Client(
            headers={"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            timeout=30,
            transport=transport,
            follow_redirects=True,
        )
        self._gap = 1.0 / rate
        self._sleep = sleep
        self._clock = clock
        self._last = None
        self._max_retries = max_retries

    def _wait_turn(self):
        if self._last is not None:
            delay = self._gap - (self._clock() - self._last)
            if delay > 0:
                self._sleep(delay)
        self._last = self._clock()

    def get_text(self, url: str) -> str | None:
        status = None
        for attempt in range(self._max_retries + 1):
            self._wait_turn()
            try:
                r = self._http.get(url)
                status = r.status_code
            except httpx.TransportError as e:
                status = f"network {e!r}"
                r = None
            if r is not None and r.status_code == 200:
                return r.text
            if r is not None and r.status_code == 404:
                return None
            retryable = r is None or r.status_code in (403, 429) or r.status_code >= 500
            if not retryable or attempt == self._max_retries:
                break
            self._sleep(2 ** attempt)
        raise SecError(f"{status} {url}")
