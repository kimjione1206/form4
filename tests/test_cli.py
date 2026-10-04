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
