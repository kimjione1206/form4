import httpx
import pytest

from form4.fx import current_rate


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_reads_rate():
    c = client(lambda r: httpx.Response(200, json={"date": "2026-10-02", "rates": {"KRW": 1348.28}}))
    assert current_rate(c, None) == {"rate": 1348.28, "date": "2026-10-02"}


def test_falls_back_on_error():
    c = client(lambda r: httpx.Response(500))
    assert current_rate(c, {"rate": 1300.0, "date": "2026-10-01"}) == {"rate": 1300.0, "date": "2026-10-01"}


def test_raises_without_fallback():
    with pytest.raises(httpx.HTTPError):
        current_rate(client(lambda r: httpx.Response(500)), None)
