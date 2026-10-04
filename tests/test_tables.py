import json

from form4.tables import (build_todo, check_tables, company_line, ensure_company_info,
                          guard_text)


def test_guard_text():
    assert guard_text("반도체 장비를 만드는 회사")
    assert not guard_text("")
    assert not guard_text("2024년 설립된 회사")       # 숫자
    assert not guard_text("빠르게 성장하는 회사")       # 금지어
    assert not guard_text("가" * 41)


def test_check_tables_reports_bad_entries():
    companies = {"1": {"summary": "유망한 회사"}, "2": {"summary": None}, "3": {"summary": "은행"}}
    titles = {"SVP": "선임 부사장", "X": "제3 부사장"}
    errors = check_tables(companies, titles)
    assert len(errors) == 2 and "1" in errors[0] and "X" in errors[1]


def test_company_line_falls_back_to_sic():
    companies = {"1": {"summary": "은행", "sic_description": "National Commercial Banks"},
                 "2": {"summary": None, "sic_description": "Retail"},
                 "3": {"summary": "추천 종목", "sic_description": "Oil"}}
    assert company_line("1", companies) == "은행"
    assert company_line("2", companies) == "Retail"
    assert company_line("3", companies) == "Oil"
    assert company_line("9", companies) == ""


class FakeSec:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get_text(self, url):
        self.calls.append(url)
        return self.pages.get(url)


def test_ensure_company_info_fetches_missing_only():
    url = "https://data.sec.gov/submissions/CIK0000000002.json"
    sec = FakeSec({url: json.dumps({"sicDescription": "Retail"})})
    companies = {"1": {"name": "A", "sic_description": "x", "summary": "은행"}}
    results = [{"issuer_cik": "1", "name": "A"}, {"issuer_cik": "2", "name": "B"}]
    ensure_company_info(results, companies, sec)
    assert sec.calls == [url]
    assert companies["2"] == {"name": "B", "sic_description": "Retail", "summary": None}


def test_build_todo():
    companies = {"1": {"name": "A", "sic_description": "x", "summary": None},
                 "2": {"name": "B", "sic_description": "y", "summary": "은행"}}
    results = [{"issuer_cik": "1", "officer_titles": ["SVP Sales", "CFO"]},
               {"issuer_cik": "2", "officer_titles": []}]
    todo = build_todo(results, companies, {"CFO": "재무이사(CFO)"}, results)
    assert todo == {"companies": [{"cik": "1", "name": "A", "sic_description": "x"}],
                    "titles": ["SVP Sales"]}


def test_build_todo_titles_from_all_profiles_companies_from_list_only():
    companies = {"1": {"name": "A", "sic_description": "x", "summary": None}}
    results = [{"issuer_cik": "1", "officer_titles": ["CFO"]}]
    profiles = results + [{"issuer_cik": "9", "officer_titles": ["Chief Legal Officer", "CFO"]}]
    todo = build_todo(results, companies, {}, profiles)
    assert todo == {"companies": [{"cik": "1", "name": "A", "sic_description": "x"}],
                    "titles": ["CFO", "Chief Legal Officer"]}


def test_null_industry_name_stored_as_empty():
    url = "https://data.sec.gov/submissions/CIK0000000002.json"
    companies = {}
    ensure_company_info([{"issuer_cik": "2", "name": "B"}], companies,
                        FakeSec({url: json.dumps({"sicDescription": None})}))
    assert companies["2"]["sic_description"] == ""
    assert company_line("2", companies) == ""
    assert company_line("3", {"3": {"summary": None, "sic_description": None}}) == ""
