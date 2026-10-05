import json

from form4.tables import (build_todo, check_tables, company_line, ensure_company_info,
                          guard_text, korean_name)


def test_guard_text():
    assert guard_text("반도체 장비를 만드는 회사")
    assert not guard_text("")
    assert not guard_text("2024년 설립된 회사")       # 숫자
    assert not guard_text("빠르게 성장하는 회사")       # 금지어
    assert not guard_text("가" * 41)


def test_check_tables_reports_bad_entries():
    companies = {"1": {"summary": "유망한 회사"}, "2": {"summary": None}, "3": {"summary": "은행"}}
    titles = {"SVP": "선임 부사장", "X": "제3 부사장"}
    errors = check_tables(companies, titles, {})
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
    results = [{**p("A", "A", 1.0, 0.0), "issuer_cik": "1", "officer_titles": ["SVP Sales", "CFO"]},
               {**p("B", "B", 1.0, 0.0), "issuer_cik": "2", "officer_titles": []}]
    todo = build_todo(results, companies, {"CFO": "재무이사(CFO)"}, results, {})
    assert todo["companies"] == [{"cik": "1", "name": "A", "sic_description": "x"}]
    assert todo["titles"] == ["SVP Sales"]


def test_build_todo_titles_from_all_profiles_companies_from_list_only():
    companies = {"1": {"name": "A", "sic_description": "x", "summary": None}}
    results = [{**p("A", "A", 1.0, 0.0), "issuer_cik": "1", "officer_titles": ["CFO"]}]
    profiles = results + [{**p("Z", "Z", 1.0, 0.0), "issuer_cik": "9",
                           "officer_titles": ["Chief Legal Officer", "CFO"]}]
    todo = build_todo(results, companies, {}, profiles, {})
    assert todo["companies"] == [{"cik": "1", "name": "A", "sic_description": "x"}]
    assert todo["titles"] == ["CFO", "Chief Legal Officer"]


def test_null_industry_name_stored_as_empty():
    url = "https://data.sec.gov/submissions/CIK0000000002.json"
    companies = {}
    ensure_company_info([{"issuer_cik": "2", "name": "B"}], companies,
                        FakeSec({url: json.dumps({"sicDescription": None})}))
    assert companies["2"]["sic_description"] == ""
    assert company_line("2", companies) == ""
    assert company_line("3", {"3": {"summary": None, "sic_description": None}}) == ""


def test_korean_name_guarded():
    names = {"NVDA": "엔비디아", "BAD": "추천 회사", "NUM": "쓰리엠3", "LONG": "가" * 21, "OK20": "가" * 20,
             "SKIP": ""}
    assert korean_name("NVDA", names) == "엔비디아"
    assert korean_name("OK20", names) == "가" * 20
    for t in ["BAD", "NUM", "LONG", "NONE", "SKIP"]:
        assert korean_name(t, names) == ""


def test_check_tables_validates_korean_names():
    errors = check_tables({}, {}, {"NVDA": "엔비디아", "X": "유망 회사", "Y": "가" * 21, "SKIP": ""})
    assert len(errors) == 2 and "X" in errors[0] and "Y" in errors[1]  # 빈 문자열 = 건너뛴 회사 기록


def p(ticker, name, buy, sale):
    return {"issuer_cik": ticker, "ticker": ticker, "name": name, "total_usd": buy, "sale_usd": sale,
            "officer_titles": []}


def test_build_todo_names_largest_first_without_korean_name():
    profiles = [p("SMALL", "Small Co", 100.0, 0.0), p("NVDA", "NVIDIA CORP", 1e9, 0.0),
                p("SELL", "Seller Co", 0.0, 5e6), p("BUY", "Buyer Co", 3e6, 1e6),
                p("BAD", "Bad Co", 9e9, 0.0)]
    todo = build_todo([], {}, {}, profiles, {"NVDA": "엔비디아"})
    assert todo["names"] == [{"t": "BAD", "n": "Bad Co"}, {"t": "SELL", "n": "Seller Co"},
                             {"t": "BUY", "n": "Buyer Co"}, {"t": "SMALL", "n": "Small Co"}]
    # 이미 표에 있는 종목은 값이 빈 문자열(건너뛴 회사)이어도 다시 올리지 않는다
    todo = build_todo([], {}, {}, profiles, {"NVDA": "엔비디아", "BAD": "", "SELL": "추천 회사"})
    assert [e["t"] for e in todo["names"]] == ["BUY", "SMALL"]


def test_build_todo_names_only_clean_ticker_codes():
    messy = ["NYSE: VTEX", "GEF, GEF-B", "(SIRI)", "N/A", "NONE", "TOOLONGTICKER", "brk.b"]
    profiles = [p(t, f"Co {t}", 1e6, 0.0) for t in messy] + [p("BRK.B", "Berkshire", 1.0, 0.0),
                                                            p("GEF-B", "Greif", 1.0, 0.0)]
    assert [e["t"] for e in build_todo([], {}, {}, profiles, {})["names"]] == ["BRK.B", "GEF-B"]


def test_build_todo_names_capped_at_300():
    profiles = [p(f"T{i:03d}", f"Co {i}", float(i), 0.0) for i in range(350)]
    names = build_todo([], {}, {}, profiles, {})["names"]
    assert len(names) == 300 and names[0]["t"] == "T349" and names[-1]["t"] == "T050"


def test_build_todo_companies_capped_at_100_in_list_order():
    results = [{"issuer_cik": str(i)} for i in range(150)]
    companies = {str(i): {"name": f"Co {i}", "sic_description": "", "summary": None} for i in range(150)}
    companies["0"]["summary"] = "지역 은행"  # 소개가 있는 회사는 할 일에서 빠짐
    todo = build_todo(results, companies, {}, [], {})["companies"]
    assert len(todo) == 100 and todo[0]["cik"] == "1" and todo[-1]["cik"] == "100"


def test_company_line_uses_korean_industry_before_english():
    companies = {"1": {"summary": "지역 은행", "sic_description": "State Commercial Banks"},
                 "2": {"summary": None, "sic_description": "State Commercial Banks"},
                 "3": {"summary": None, "sic_description": "Pharmaceutical Preparations"},
                 "4": {"summary": None, "sic_description": "Retail"}}
    industries = {"State Commercial Banks": "은행", "Pharmaceutical Preparations": "유망 의약품",
                  "Retail": "가" * 31}
    assert company_line("1", companies, industries) == "지역 은행"  # 소개가 먼저
    assert company_line("2", companies, industries) == "은행"
    assert company_line("3", companies, industries) == "Pharmaceutical Preparations"  # 금지어 → 영어
    assert company_line("4", companies, industries) == "Retail"  # 30자 넘음 → 영어
    assert company_line("9", companies, industries) == ""


def test_check_tables_validates_industries():
    errors = check_tables({}, {}, {}, {"State Commercial Banks": "은행", "X": "추천 업종", "Y": "업종3"})
    assert len(errors) == 2 and "X" in errors[0] and "Y" in errors[1]


def test_build_todo_industries_not_yet_translated():
    companies = {"1": {"name": "A", "sic_description": "State Commercial Banks", "summary": "은행"},
                 "2": {"name": "B", "sic_description": "Retail", "summary": None},
                 "3": {"name": "C", "sic_description": "Retail", "summary": None},
                 "4": {"name": "D", "sic_description": "", "summary": None},
                 "5": {"name": "E", "sic_description": "Air Transport", "summary": None}}
    todo = build_todo([], companies, {}, [], {}, {"State Commercial Banks": "은행"})
    assert todo["industries"] == ["Air Transport", "Retail"]
    assert set(todo) == {"companies", "titles", "names", "industries"}
