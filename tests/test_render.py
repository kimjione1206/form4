import json
import re

import pytest

from form4.render import (find_forbidden, fmt_decrease, fmt_increase, fmt_krw, fmt_krw_short,
                          fmt_usd, render_site, summary_segments)

META = {"as_of_label": "10/2", "updated": "10/04 06:07", "fx_rate": 1400.0,
        "fx_date": "2026-10-02", "new_filings": 1502}


def result(**kw):
    row = {"date": "2026-09-29", "filed": "2026-10-01", "who": "대표이사(CEO)", "value": 1_500_000.0,
           "increase": 0.18, "tags": ["계획 매수"], "url": "https://www.sec.gov/x", "ceo": True}
    c = {"issuer_cik": "900", "name": "EXAMPLE CORP", "ticker": "EXM", "slug": "EXM", "qualified": True,
         "people": 5, "total_usd": 2_400_000.0, "ten_pct_usd": 5_000_000.0,
         "sale_people": 0, "sale_usd": 0.0, "sale_rows": [],
         "offering_usd": 0.0,
         "first_date": "2026-09-12", "last_date": "2026-09-29", "tags": ["대표이사 포함"],
         "officer_titles": [], "rows": [row], "top": row}
    c.update(kw)
    return c


def test_formatters():
    assert fmt_usd(2_400_000) == "$2.4M" and fmt_usd(310_000) == "$310K" and fmt_usd(9_500) == "$9,500"
    assert fmt_krw(2_400_000, 1400) == "약 34억 원"
    assert fmt_krw(310_000, 1400) == "약 4.3억 원"
    assert fmt_krw(5_000, 1400) == "약 700만 원"
    assert fmt_krw_short(2_400_000, 1400) == "34억"
    assert fmt_increase(0.18) == "+18%" and fmt_increase("new") == "신규 보유" and fmt_increase(None) == "-"
    assert fmt_decrease(0.08) == "\u22128%" and fmt_decrease(0.084) == "−8%" and fmt_decrease(1.0) == "−100%"
    assert fmt_decrease(0.004) == "−1% 미만" and fmt_decrease(None) == "-"
    assert fmt_decrease(0.995) == "−99%" and fmt_decrease(0.9999) == "−99%" and fmt_decrease(0.994) == "−99%"
    assert fmt_decrease(1.2) == "−100%" and fmt_decrease(0.0) == "-"


def test_formatters_round_up_to_next_unit():
    assert fmt_usd(999_950) == "$1.0M" and fmt_usd(1_000_000) == "$1.0M"
    assert fmt_krw_short(71_425, 1400) == "1억"  # 99,995,000원


def test_briefing_lists_at_most_three_new(tmp_path):
    news = [result(issuer_cik=str(i), name=f"CO{i}", slug=f"S{i}") for i in range(5)]
    brief = {"count": 5, "new": news, "dropped": [], "top": news[0]}
    render_site(news, brief, META, {}, tmp_path)
    home = (tmp_path / "index.html").read_text()
    assert "CO2 — 임원" in home and "CO3 — 임원" not in home
    assert "외 2곳" in home


def test_summary_segments_text():
    text = "".join(t for t, _ in summary_segments(result(), 1400))
    assert text == ("최근 60일 동안 임원·이사 5명이 시장에서 직접 약 34억 원($2.4M)어치를 샀어요. "
                    "가장 큰 매수는 대표이사(CEO)의 약 21억 원으로, 기존 보유 주식의 +18%를 늘린 거예요. "
                    "같은 기간 장내 매도 신고는 없어요.")
    sold = "".join(t for t, _ in summary_segments(result(sale_people=2, sale_usd=20_000.0), 1400))
    assert sold.endswith("를 늘린 거예요. 같은 기간 임원·이사 2명이 약 2,800만 원어치를 장내 매도했어요.")


def test_render_site_writes_pages(tmp_path):
    c = result()
    brief = {"count": 1, "new": [c], "dropped": [], "top": c}
    companies = {"900": {"name": "EXAMPLE CORP", "sic_description": "Retail", "summary": "반도체 장비를 만드는 회사"}}
    render_site([c], brief, META, companies, tmp_path)
    home = (tmp_path / "index.html").read_text()
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    assert "특정 종목의 매수·매도를 권하지 않아요" in home
    assert "반도체 장비를 만드는 회사" in home and "매도 0명 · <b" in home
    assert "새로 · 거래 9/29" in home
    assert "data-typing" in detail and "+18%" in detail and "대주주(펀드)" in detail
    for f in ["criteria/index.html", "404.html", "style.css", "typing.js"]:
        assert (tmp_path / f).exists()


def test_offering_note_only_when_present(tmp_path):
    note = "공모·사모 등 증자에 참여해 받은 매수"
    for offering_usd, shown in [(0.0, False), (250_000.0, True)]:
        c = result(offering_usd=offering_usd)
        render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
        detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
        assert (note in detail) is shown
    assert ("참고 · 같은 기간 임원·이사가 공모·사모 등 증자에 참여해 받은 매수 $250K는 시장에서 직접 산 게 "
            "아니라서 위 인원·금액에 넣지 않았어요.") in re.sub(r"<[^>]+>", "", detail)
    assert "증자 참여</b>" not in detail


def test_criteria_lists_exclusions(tmp_path):
    render_site([], {"count": 0, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    page = (tmp_path / "criteria" / "index.html").read_text()
    assert ("다음은 시장에서 직접 산 매수가 아니라서 세지 않아요: 각주에 배당 재투자로 적힌 매수, "
            "공모·사모 등 증자 참여(상세 페이지에 참고로 표시), 종목 코드가 없는 비상장 회사.") in page
    assert "증자 참여 포함" not in page


def test_render_rejects_forbidden_words(tmp_path):
    c = result(name="ROCKET 급등 CORP")
    with pytest.raises(ValueError, match="금지어"):
        render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)


def test_find_forbidden_ignores_markup():
    assert find_forbidden('<p class="추천">x</p>') == []
    assert find_forbidden("<p>추천 종목</p>") == ["추천"]


def test_empty_day(tmp_path):
    render_site([], {"count": 0, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    assert "조건에 맞는 회사가 없어요" in (tmp_path / "index.html").read_text()


def test_touch_targets_44px(tmp_path):
    render_site([], {"count": 0, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    css = (tmp_path / "style.css").read_text()
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    covered = {s.strip() for sel, body in rules if "min-height: 44px" in body for s in sel.split(",")}
    assert {".replay", ".who a", ".back", ".notice a", ".foot a", ".band-side a", ".src",
            ".search button", ".explain summary"} <= covered
    assert ".replay[hidden] { display: none; }" in css


def test_pages_ask_search_engines_not_to_index(tmp_path):
    # 금감원 확인 전까지 검색 노출 막기. 정식 개설 때 base.html 의 robots 줄을 지우고 이 테스트도 지운다.
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    for f in ["index.html", "c/EXM/index.html", "criteria/index.html", "404.html"]:
        assert '<meta name="robots" content="noindex, nofollow">' in (tmp_path / f).read_text()


def test_desktop_layout(tmp_path):
    a = result()
    b = result(issuer_cik="901", name="SECOND CO", slug="SEC2", last_date="2026-08-27")
    render_site([a, b], {"count": 2, "new": [], "dropped": [], "top": a}, META, {}, tmp_path)
    css = (tmp_path / "style.css").read_text()
    assert "@media (min-width: 1024px)" in css
    desktop = css[css.index("@media (min-width: 1024px)"):]
    # 머리띠 안 검색 결과는 겹쳐 떠서 머리띠 오른쪽 정보를 밀어내지 않는다 (휴대폰은 그대로)
    assert re.search(r"\.band-search \.search-out \{[^}]*position: absolute[^}]*z-index", desktop)
    assert "position: absolute" not in css[:css.index("@media (min-width: 1024px)")]
    home = (tmp_path / "index.html").read_text()
    assert re.search(r'<div class="[^"]*\blist-cols\b[^"]*">.*<span class="[^"]*\br\b[^"]*">최근 거래</span>', home, re.S)
    rows = re.findall(r'<a class="[^"]*\bitem\b[^"]*".*?</a>', home, re.S)
    assert len(rows) == 2
    assert re.search(r'<span class="[^"]*\bcol-last\b[^"]*">9/29</span>', rows[0])
    assert re.search(r'<span class="[^"]*\bcol-last\b[^"]*">8/27</span>', rows[1])
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    assert re.search(r'<div class="[^"]*\bthead\b[^"]*">.*<span class="[^"]*\bd-only\b[^"]*">신고일</span>', detail, re.S)


SELL = {"date": "2026-09-25", "filed": "2026-09-26", "who": "재무이사(CFO)", "value": 20_000.0,
        "decrease": 0.08, "tags": ["계획 매도", "옵션 행사 후 매도"], "url": "https://www.sec.gov/sell1"}


def test_home_shows_sale_people_and_amount(tmp_path):
    a = result(sale_people=2, sale_usd=20_000.0, sale_rows=[SELL])
    b = result(issuer_cik="901", name="SECOND CO", slug="SEC2")
    render_site([a, b], {"count": 2, "new": [], "dropped": [], "top": a}, META, {}, tmp_path)
    home = (tmp_path / "index.html").read_text()
    rows = re.findall(r'<a class="[^"]*\bitem\b[^"]*".*?</a>', home, re.S)
    assert "대표이사 포함 · 매도 2명 · 약 2,800만 원" in rows[0]
    assert "대표이사 포함 · 매도 0명<" in rows[1] and "매도 0명 ·" not in rows[1]
    cell = re.search(r'<span class="[^"]*\bcol-sale\b[^"]*">(.*?)</span>\s*</a>', rows[0], re.S).group(1)
    assert "2명" in cell and "2,800만" in cell
    cell = re.search(r'<span class="[^"]*\bcol-sale\b[^"]*">(.*?)</span>\s*</a>', rows[1], re.S).group(1)
    assert "0명" in cell and "만" not in cell
    assert "건</span>" not in home


def test_detail_sell_tile_and_table(tmp_path):
    c = result(sale_people=2, sale_usd=20_000.0, sale_rows=[SELL])
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", detail))
    assert "같은 기간 매도 2명 약 2,800만 원" in text
    assert "같은 기간 임원·이사 2명이 약 2,800만 원어치를 장내 매도했어요." in text
    sells = detail[detail.index("매도 기록"):detail.index("용어 풀이")]
    assert "매도는 세금 납부·생활 자금·미리 정한 계획 등 여러 이유로 일어나며, 주가 하락을 뜻하지 않아요." in sells
    assert re.search(r'<div class="[^"]*\bthead\b[^"]*">.*<span class="[^"]*\bd-only\b[^"]*">신고일</span>.*보유↓', sells, re.S)
    assert "9/25" in sells and "$20K" in sells and "−8%" in sells
    assert '<span class="chip m-only">옵션 행사 후 매도</span>' in sells
    assert re.search(r'<a class="small m-only" href="https://www.sec.gov/sell1"[^>]*>신고 9/26 · 원문 ↗</a>', sells)
    assert re.search(r'<a class="src d-only" href="https://www.sec.gov/sell1"', sells)
    assert "계획 매도 · 옵션 행사 후 매도" in sells
    assert "장내 매도 신고는 없어요" not in sells
    assert detail.index("거래 기록") < detail.index("매도 기록") < detail.index("용어 풀이")


def test_detail_without_sales(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    sells = detail[detail.index("매도 기록"):detail.index("용어 풀이")]
    assert "같은 기간 임원·이사의 장내 매도 신고는 없어요." in sells and "trow" not in sells
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", detail))
    assert "같은 기간 매도 0명 없음" in text


def test_glossary_explains_sell_terms(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    text = re.sub(r"<[^>]+>", "", (tmp_path / "c" / "EXM" / "index.html").read_text())
    assert "계획 매도 몇 달 전에 미리 정해 둔 계획(10b5-1)대로 판 것" in text
    assert "옵션 행사 후 매도 스톡옵션으로 받은 주식을 같은 날 바로 판 것" in text
    assert "보유↓ 원래 갖고 있던 주식 대비 이번에 줄어든 비율" in text
    assert "간접 본인 이름이 아닌 가족·신탁 명의로 사고판 것" in text


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


NOT_LISTED = "조건 충족 목록에는 없는 회사예요 (기준: 최근 60일 임원·이사 3명 이상이 각각 1만 달러 이상 장내 매수)."


def test_pages_for_companies_outside_the_list(tmp_path):
    listed = result()
    two = result(issuer_cik="901", name="TWO BUYERS CO", ticker="TWO", slug="TWO", qualified=False, people=2,
                 total_usd=30_000.0, tags=[])
    seller = result(issuer_cik="902", name="SELLER CO", ticker="SEL", slug="SEL", qualified=False, people=0,
                    total_usd=0.0, rows=[], top=None, tags=[], first_date=None, last_date=None,
                    sale_people=2, sale_usd=20_000.0, sale_rows=[SELL])
    render_site([listed, two, seller], {"count": 1, "new": [], "dropped": [], "top": listed}, META, {}, tmp_path)
    home = (tmp_path / "index.html").read_text()
    assert "조건 충족 1곳" in home and "TWO BUYERS CO" not in home and "SELLER CO" not in home
    assert NOT_LISTED not in plain((tmp_path / "c" / "EXM" / "index.html").read_text())
    two_page = plain((tmp_path / "c" / "TWO" / "index.html").read_text())
    assert NOT_LISTED in two_page and "임원·이사 2명이 시장에서 직접" in two_page
    page = (tmp_path / "c" / "SEL" / "index.html").read_text()
    text = plain(page)
    assert NOT_LISTED in text
    assert ("최근 60일 동안 임원·이사의 장내 매수 신고는 없어요. "
            "같은 기간 임원·이사 2명이 약 2,800만 원어치를 장내 매도했어요.") in text
    assert "장내 매수 0명" in text
    buys = page[page.index("거래 기록"):page.index("매도 기록")]
    assert "trow" not in buys and "장내 매수 신고는 없어요" in buys
    assert "$20K" in page[page.index("매도 기록"):]


def test_forbidden_word_checked_on_pages_outside_the_list(tmp_path):
    bad = result(issuer_cik="901", name="ROCKET 급등 CORP", slug="RKT", qualified=False)
    with pytest.raises(ValueError, match="금지어"):
        render_site([result(), bad], {"count": 1, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)


def test_search_index_and_forms(tmp_path):
    ps = [result(ticker="ZZZ", slug="ZZZ"),
          result(issuer_cik="901", name="Apple Inc.", ticker="AAPL", slug="AAPL", qualified=False)]
    render_site(ps, {"count": 1, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    assert json.loads((tmp_path / "search.json").read_text()) == [
        {"t": "AAPL", "n": "Apple Inc.", "s": "AAPL", "q": False},
        {"t": "ZZZ", "n": "EXAMPLE CORP", "s": "ZZZ", "q": True}]
    assert (tmp_path / "search.js").exists()
    for f in ["index.html", "404.html"]:
        page = (tmp_path / f).read_text()
        forms = re.findall(r'<form role="search"[^>]*>.*?</form>', page, re.S)
        assert forms, f
        for form in forms:
            assert 'action="#"' in form and "name=" not in form  # 검색어가 주소에 실려 서버로 가지 않게
            label = re.search(r'<label for="([^"]+)"', form).group(1)
            assert f'<input id="{label}"' in form
            assert 'placeholder="종목 코드 또는 회사 이름 (예: AAPL)"' in form and ">찾기</button>" in form
        assert "검색어는 이 브라우저 안에서만 처리돼요." in page
        assert '<script src="/search.js" defer></script>' in page
    text = plain((tmp_path / "404.html").read_text())
    assert "없는 페이지예요" in text
    assert "이 주소의 회사 페이지가 없어요. 최근 60일 동안 임원 거래 공시가 없거나 주소가 달라요." in text
    js = (tmp_path / "search.js").read_text()
    assert "/search.json" in js and "최근 60일 동안 이 종목의 임원·이사 매수·매도 공시가 없어요." in js


def test_home_explanations(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    home = (tmp_path / "index.html").read_text()
    text = plain(home)
    assert "(합법)" not in home and "공개 신고해야 해요(신고 의무가 있는 공개 정보예요)." in text
    assert "새로 = 오늘 목록에 처음 오른 회사 · 빠짐 = 기간(60일)이 지나 목록에서 빠진 회사" in text
    assert "조건 충족 = 최근 60일 임원·이사 3명 이상이 각자 1만 달러 이상 장내 매수" in text
    details = re.search(r"<details[^>]*>\s*<summary[^>]*>매도는 왜 일어나요\?</summary>(.*?)</details>", home, re.S)
    assert details and ("임원은 월급·보너스를 회사 주식으로 받는 경우가 많아요. 그래서 세금 납부, 생활 자금, 분산 투자를 위해 "
                        "팔기도 하고, 몇 달 전에 미리 정해 둔 계획(10b5-1)대로 자동으로 팔기도 해요. 매도가 많다고 주가 "
                        "하락을 뜻하지 않아요. 반대로 매수는 이유가 비교적 단순해서 이 사이트는 매수를 중심으로 정리해요.") \
        in plain(details.group(1))
    assert home.index('class="notice"') < home.index("<details")
