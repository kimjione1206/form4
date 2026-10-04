from datetime import date

import httpx
import pytest

from form4.sec import SecClient, SecError, index_url, submissions_url


def test_index_url_uses_quarter():
    assert index_url(date(2026, 10, 2)) == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.20261002.idx"
    )
    assert "/QTR1/" in index_url(date(2026, 3, 31))


def test_submissions_url_pads_cik():
    assert submissions_url("1000697") == "https://data.sec.gov/submissions/CIK0001000697.json"


def _client(handler, sleeps):
    t = [0.0]
    return SecClient(
        transport=httpx.MockTransport(handler),
        sleep=lambda s: sleeps.append(s),
        clock=lambda: t[0],
        max_retries=3,
    )


def test_sends_user_agent_and_returns_text():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, text="hello")

    assert _client(handler, []).get_text("https://www.sec.gov/x") == "hello"
    assert seen["ua"] == "form4.jmheo.com form4@jmheo.com"


def test_404_returns_none():
    assert _client(lambda r: httpx.Response(404), []).get_text("https://www.sec.gov/x") is None


def test_retries_on_429_then_succeeds():
    codes = iter([429, 403, 200])
    sleeps = []
    c = _client(lambda r: httpx.Response(next(codes), text="ok"), sleeps)
    assert c.get_text("https://www.sec.gov/x") == "ok"
    assert 1 in sleeps and 2 in sleeps  # 2**0, 2**1 초 대기


def test_gives_up_after_max_retries():
    with pytest.raises(SecError):
        _client(lambda r: httpx.Response(403), []).get_text("https://www.sec.gov/x")


def test_spaces_requests_by_rate():
    sleeps = []
    c = _client(lambda r: httpx.Response(200, text="ok"), sleeps)
    c.get_text("https://www.sec.gov/a")
    c.get_text("https://www.sec.gov/b")
    assert sleeps and abs(sleeps[0] - 1 / 8) < 1e-9
