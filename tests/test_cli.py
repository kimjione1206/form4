import json
from datetime import date, datetime, timezone

import httpx
import pytest

from form4 import cli
from form4.sec import SecError, index_url
from helpers import form4_xml, submission

NOW = datetime(2026, 10, 3, 21, 7, tzinfo=timezone.utc)  # 한국 10/4 06:07


def test_latest_complete_date_is_previous_us_day():
    assert cli.latest_complete_date(NOW) == date(2026, 10, 2)


def test_business_days_skip_weekend():
    assert cli.business_days(date(2026, 10, 2), date(2026, 10, 5)) == [date(2026, 10, 2), date(2026, 10, 5)]


class FakeSec:
    def __init__(self, pages):
        self.pages = pages

    def get_text(self, url):
        return self.pages.get(url)


def site_pages(day=date(2026, 10, 2), bad=0, n=3):
    lines = ["CIK|Company Name|Form Type|Date Filed|File Name"]
    pages = {}
    for i in range(n):
        acc = f"0000000900-26-{i:06d}"
        path = f"edgar/data/900/{acc}.txt"
        lines.append(f"900|EXAMPLE CORP|4|{day:%Y%m%d}|{path}")
        xml = form4_xml(issuer_cik="900", ticker="EXM",
                        owners=[{"cik": str(10 + i), "director": True}],
                        txs=[{"code": "P", "date": "2026-09-30", "shares": 1000, "price": 20, "after": 2000}])
        pages["https://www.sec.gov/Archives/" + path] = submission(xml) if i >= bad else "broken"
    pages[index_url(day)] = "\n".join(lines)
    pages["https://data.sec.gov/submissions/CIK0000000900.json"] = json.dumps({"sicDescription": "Retail"})
    return pages


def fx():
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"date": "2026-10-02", "rates": {"KRW": 1400.0}})))


def seed(data):
    data.mkdir()
    (data / "state.json").write_text('{"last_date": null, "fx": null}')
    (data / "titles.json").write_text("{}")
    (data / "companies.json").write_text("{}")


def test_daily_end_to_end(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages()), fx(), data, dist, log=lambda m: None)
    home = (dist / "index.html").read_text()
    assert "EXAMPLE CORP" in home and "조건 충족 1곳" in home
    assert (dist / "c" / "EXM" / "index.html").exists()
    state = json.loads((data / "state.json").read_text())
    assert state["last_date"] == "2026-10-02" and state["fx"]["rate"] == 1400.0
    assert json.loads((data / "todo.json").read_text())["companies"][0]["cik"] == "900"
    assert json.loads((data / "companies.json").read_text())["900"]["sic_description"] == "Retail"
    assert len((data / "transactions.jsonl").read_text().splitlines()) == 3


def test_too_many_failures_abort(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    with pytest.raises(RuntimeError, match="실패"):
        cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages(bad=1)), fx(), data, dist,
                log=lambda m: None)
    assert not dist.exists()


def test_holiday_index_missing(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    cli.run([date(2026, 11, 26)], date(2026, 11, 26), NOW, FakeSec({}), fx(), data, dist, log=lambda m: None)
    assert "새로 들어온 신고가 없어요" in (dist / "index.html").read_text()
    assert "(미국 주말·휴일)" in (dist / "index.html").read_text()


def test_us_federal_holidays_2026():
    h = cli.us_federal_holidays(2026)
    assert {date(2026, 7, 3), date(2026, 11, 26), date(2026, 12, 25)} <= h
    assert date(2026, 7, 4) not in h  # 토요일 → 금요일에 쉼
    assert len(h) == 11


def test_new_year_on_saturday_observed_previous_december():
    assert date(2021, 12, 31) in cli.us_federal_holidays(2021)
    assert date(2021, 12, 31) not in cli.us_federal_holidays(2022)


def test_collect_holiday_without_index_continues():
    assert cli.collect([date(2026, 11, 26)], FakeSec({}), log=lambda m: None) == ([], [], 0)


class RecordingSec(FakeSec):
    def __init__(self, pages):
        super().__init__(pages)
        self.calls = []

    def get_text(self, url):
        self.calls.append(url)
        return super().get_text(url)


def test_collect_skips_holiday_without_requesting_index():
    sec = RecordingSec({})  # SEC는 없는 색인에 404가 아니라 403을 준다 → 휴일은 아예 요청하지 않는다
    assert cli.collect([date(2026, 9, 7)], sec, log=lambda m: None) == ([], [], 0)
    assert sec.calls == []


def test_collect_weekday_without_index_raises():
    with pytest.raises(RuntimeError, match="일일 색인 없음"):
        cli.collect([date(2026, 10, 2)], FakeSec({}), log=lambda m: None)


def test_check_tables_exit_code(tmp_path, monkeypatch):
    data = tmp_path / "data"
    seed(data)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check-tables"]) == 0
    (data / "titles.json").write_text('{"X": "추천 부사장"}')
    assert cli.main(["check-tables"]) == 1
    (data / "titles.json").write_text("{}")
    (data / "korean_names.json").write_text('{"NVDA": "엔비디아"}')
    assert cli.main(["check-tables"]) == 0
    (data / "korean_names.json").write_text('{"NVDA": "엔비디아 3"}')
    assert cli.main(["check-tables"]) == 1


class FlakySec(FakeSec):
    def __init__(self, pages, fail_url):
        super().__init__(pages)
        self.fail_url = fail_url

    def get_text(self, url):
        if url == self.fail_url:
            raise SecError(f"503 {url}")
        return super().get_text(url)


def test_one_filing_download_error_is_skipped(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    sec = FlakySec(site_pages(n=21), "https://www.sec.gov/Archives/edgar/data/900/0000000900-26-000020.txt")
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, sec, fx(), data, dist, log=lambda m: None)
    assert "0000000900-26-000020" in (data / "skipped.log").read_text()
    assert (dist / "index.html").exists()


def test_last_date_follows_collected_dates_not_as_of(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    sec = FakeSec(site_pages(day=date(2026, 9, 1), n=0))
    cli.run([date(2026, 9, 1)], date(2026, 10, 2), NOW, sec, fx(), data, dist, log=lambda m: None)
    assert json.loads((data / "state.json").read_text())["last_date"] == "2026-09-01"


def test_daily_dates_caps_catch_up_to_oldest_five():
    dates, as_of = cli.daily_dates(date(2026, 9, 18), date(2026, 10, 2))  # 영업일 10일 밀림
    assert dates == [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23),
                     date(2026, 9, 24), date(2026, 9, 25)]
    assert as_of == date(2026, 9, 25)


def test_daily_dates_without_last_date():
    assert cli.daily_dates(None, date(2026, 10, 2)) == ([date(2026, 10, 2)], date(2026, 10, 2))


def test_pages_for_companies_outside_the_list_without_extra_sec_requests(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    pages = site_pages()
    day, acc = date(2026, 10, 2), "0000000901-26-000001"
    path = f"edgar/data/901/{acc}.txt"
    pages[index_url(day)] += f"\n901|ONE BUYER CO|4|{day:%Y%m%d}|{path}"
    pages["https://www.sec.gov/Archives/" + path] = submission(form4_xml(
        issuer_cik="901", ticker="ONE", owners=[{"cik": "77", "director": True}],
        txs=[{"code": "P", "date": "2026-09-30", "shares": 100, "price": 20, "after": 500}]))
    sec = RecordingSec(pages)
    cli.run([day], day, NOW, sec, fx(), data, dist, log=lambda m: None)
    assert "조건 충족 1곳" in (dist / "index.html").read_text()
    assert "이 회사는 매수 조건 목록(" in (dist / "c" / "ONE" / "index.html").read_text()
    assert [e["t"] for e in json.loads((dist / "search.json").read_text())] == ["EXM", "ONE"]
    assert not any("CIK0000000901" in u for u in sec.calls)  # 목록 밖 회사는 SEC 회사 정보를 받지 않음
    assert "901" not in json.loads((data / "companies.json").read_text())
    assert [p["ticker"] for p in json.loads((data / "ranking_prev.json").read_text())] == ["EXM"]


def test_daily_uses_korean_names_beacon_token_and_as_of(tmp_path, monkeypatch):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    (data / "korean_names.json").write_text('{"EXM": "예시전자"}')
    monkeypatch.setenv("FORM4_BEACON_TOKEN", "tok123")
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages()), fx(), data, dist, log=lambda m: None)
    detail = (dist / "c" / "EXM" / "index.html").read_text()
    assert "<title>예시전자(EXM) 임원 매수·매도 기록" in detail
    assert """data-cf-beacon='{"token": "tok123"}'""" in detail
    assert "<lastmod>2026-10-02</lastmod>" in (dist / "sitemap.xml").read_text()
    assert json.loads((data / "todo.json").read_text())["names"] == []
    assert json.loads((data / "korean_names.json").read_text()) == {"EXM": "예시전자"}  # 읽기만 한다


def test_daily_without_beacon_token(tmp_path, monkeypatch):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    monkeypatch.delenv("FORM4_BEACON_TOKEN", raising=False)
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages()), fx(), data, dist, log=lambda m: None)
    assert "cloudflareinsights" not in (dist / "index.html").read_text()
    assert json.loads((data / "todo.json").read_text())["names"] == [{"t": "EXM", "n": "EXAMPLE CORP"}]


def test_check_tables_checks_industries(tmp_path, monkeypatch):
    data = tmp_path / "data"
    seed(data)
    monkeypatch.chdir(tmp_path)
    (data / "industries.json").write_text('{"Retail": "소매"}')
    assert cli.main(["check-tables"]) == 0
    (data / "industries.json").write_text('{"Retail": "소매 3"}')
    assert cli.main(["check-tables"]) == 1


def test_daily_uses_industries_table(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages()), fx(), data, dist, log=lambda m: None)
    assert json.loads((data / "todo.json").read_text())["industries"] == ["Retail"]
    (data / "industries.json").write_text('{"Retail": "소매업"}')
    cli.run([date(2026, 10, 2)], date(2026, 10, 2), NOW, FakeSec(site_pages()), fx(), data, dist, log=lambda m: None)
    assert "소매업" in (dist / "index.html").read_text()
    assert json.loads((data / "todo.json").read_text())["industries"] == []
    assert json.loads((data / "industries.json").read_text()) == {"Retail": "소매업"}  # 읽기만 한다


def test_daily_sell_list_info_todo_and_prev_snapshot(tmp_path):
    data, dist = tmp_path / "data", tmp_path / "dist"
    seed(data)
    pages = site_pages()
    day = date(2026, 10, 2)
    for i in range(3):  # 902 회사: 이사 3명이 각자 2만 달러 장내 매도 → 매도 목록에만 오른다
        acc, path = f"0000000902-26-{i:06d}", f"edgar/data/902/0000000902-26-{i:06d}.txt"
        pages[index_url(day)] += f"\n902|SELLER CO|4|{day:%Y%m%d}|{path}"
        pages["https://www.sec.gov/Archives/" + path] = submission(form4_xml(
            issuer_cik="902", ticker="SEL", owners=[{"cik": str(80 + i), "director": True}],
            txs=[{"code": "S", "date": "2026-09-30", "shares": 1000, "price": 20, "after": 500}]))
    pages["https://data.sec.gov/submissions/CIK0000000902.json"] = json.dumps({"sicDescription": "Banks"})
    cli.run([day], day, NOW, FakeSec(pages), fx(), data, dist, log=lambda m: None)
    assert json.loads((data / "companies.json").read_text())["902"]["sic_description"] == "Banks"
    assert [c["cik"] for c in json.loads((data / "todo.json").read_text())["companies"]] == ["900", "902"]
    assert [p["ticker"] for p in json.loads((data / "ranking_prev_sell.json").read_text())] == ["SEL"]
    assert [p["ticker"] for p in json.loads((data / "ranking_prev.json").read_text())] == ["EXM"]
    sell = (dist / "sell" / "index.html").read_text()
    assert 'href="/c/SEL/"' in sell and "매수 목록 (1곳)" in sell and "매도 목록 (1곳)" in sell
    assert "+0" in sell  # 처음 실행(이전 목록 없음)에는 '새로' 없음
    assert "매도 목록 (1곳)" in (dist / "index.html").read_text()
    (data / "ranking_prev_sell.json").write_text("[]")
    cli.run([day], day, NOW, FakeSec(pages), fx(), data, dist, log=lambda m: None)
    assert "EXAMPLE CORP — 임원·이사 3명 장내 매도 (거래 9/30~9/30)" in (dist / "sell" / "index.html").read_text()
