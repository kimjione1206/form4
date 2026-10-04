import json
import re

import pytest

from form4.render import (find_forbidden, fmt_decrease, fmt_increase, fmt_krw, fmt_krw_short,
                          fmt_usd, page_description, render_site, summary_segments)

META = {"as_of_label": "10/2", "as_of": "2026-10-02", "updated": "10/04 06:07", "fx_rate": 1400.0,
        "fx_date": "2026-10-02", "new_filings": 1502, "beacon_token": ""}


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
    assert sold.endswith("를 늘린 거예요. 같은 기간 임원·이사 2명이 약 2,800만 원어치를 장내 매도했어요. "
                         "미리 정한 계획(10b5-1) 매도 표시는 없어요.")


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
            ".search button", ".explain summary", ".copy", ".note-links a"} <= covered
    assert ".replay[hidden] { display: none; }" in css


def test_open_to_search_and_operator_trading_policy(tmp_path):
    # 정식 개설(2026-10-04): 검색 차단 해제 + 운영자 매매 원칙을 모든 페이지 바닥글과 기준 페이지에 밝힌다
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    policy = "운영자는 목록·검색 결과의 종목을 따로 사고팔지 않아요"
    for f in ["index.html", "c/EXM/index.html", "criteria/index.html", "404.html"]:
        html = (tmp_path / f).read_text()
        assert 'name="robots"' not in html
        assert policy in html

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
    sells = detail[detail.index("<h2>매도 기록"):detail.index("용어 풀이")]
    assert "매도는 세금 납부·생활 자금·미리 정한 계획 등 여러 이유로 일어나며, 주가 하락을 뜻하지 않아요." in sells
    assert re.search(r'<div class="[^"]*\bthead\b[^"]*">.*<span class="[^"]*\bd-only\b[^"]*">신고일</span>.*보유↓', sells, re.S)
    assert "9/25" in sells and "$20K" in sells and "−8%" in sells
    assert '<span class="chip m-only">옵션 행사 후 매도</span>' in sells
    assert re.search(r'<a class="small m-only" href="https://www.sec.gov/sell1"[^>]*>신고 9/26 · 원문 ↗</a>', sells)
    assert re.search(r'<a class="src d-only" href="https://www.sec.gov/sell1"', sells)
    assert "계획 매도 · 옵션 행사 후 매도" in sells
    assert "장내 매도 신고는 없어요" not in sells
    assert detail.index("<h2>매수 기록") < detail.index("<h2>매도 기록") < detail.index("용어 풀이")


def test_detail_without_sales(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    sells = detail[detail.index("<h2>매도 기록"):detail.index("용어 풀이")]
    assert "같은 기간 임원·이사의 장내 매도 신고는 없어요." in sells and "trow" not in sells
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", detail))
    assert "같은 기간 매도 0명 없음" in text


def test_glossary_explains_sell_terms(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    text = re.sub(r"<[^>]+>", "", (tmp_path / "c" / "EXM" / "index.html").read_text())
    assert "계획 매도 몇 달 전에 미리 정해 둔 계획(10b5-1)대로 판 것" in text
    assert "옵션 행사 후 매도 스톡옵션으로 받은 주식을 같은 날 바로 판 것" in text
    assert "보유↑ 이 신고서 명의(본인 또는 가족·신탁) 기준으로, 거래 전 갖고 있던 주식 대비 늘어난 비율" in text
    assert "보유↓ 이 신고서 명의(본인 또는 가족·신탁) 기준으로, 거래 전 갖고 있던 주식 대비 줄어든 비율" in text
    assert ("계획 표시 없음 신고서에 계획(10b5-1) 매도 표시가 없다는 뜻이에요. "
            "계획이 아니라고 단정할 수는 없어요.") in text
    assert "간접 본인 이름이 아닌 가족·신탁 명의로 사고판 것" in text


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


NOT_LISTED = ("이 회사는 매수 조건 목록(최근 60일 동안 임원·이사 3명 이상이 각각 1만 달러 이상 장내 매수)에는 없어요. "
              "아래에서 이 회사 임원·이사의 매수·매도 기록을 그대로 볼 수 있어요.")


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
    # 매수가 없고 매도만 있는 회사는 있는 것(매도 기록)을 먼저 보여 준다
    assert page.index("<h2>매도 기록") < page.index("<h2>매수 기록") < page.index("용어 풀이")
    buys = page[page.index("<h2>매수 기록"):page.index("용어 풀이")]
    assert "trow" not in buys and "장내 매수 신고는 없어요" in buys
    assert "$20K" in page[page.index("<h2>매도 기록"):page.index("<h2>매수 기록")]
    two_html = (tmp_path / "c" / "TWO" / "index.html").read_text()  # 매수가 있으면 매수 기록이 먼저
    assert two_html.index("<h2>매수 기록") < two_html.index("<h2>매도 기록")
    assert "거래 기록" not in page and "조건 충족 목록에는 없는 회사예요" not in page


def test_forbidden_word_checked_on_pages_outside_the_list(tmp_path):
    bad = result(issuer_cik="901", name="ROCKET 급등 CORP", slug="RKT", qualified=False)
    with pytest.raises(ValueError, match="금지어"):
        render_site([result(), bad], {"count": 1, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)


def test_search_index_and_forms(tmp_path):
    ps = [result(ticker="ZZZ", slug="ZZZ"),
          result(issuer_cik="901", name="Apple Inc.", ticker="AAPL", slug="AAPL", qualified=False)]
    render_site(ps, {"count": 1, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    assert json.loads((tmp_path / "search.json").read_text()) == [
        {"t": "AAPL", "n": "Apple Inc.", "k": "", "s": "AAPL", "q": False},
        {"t": "ZZZ", "n": "EXAMPLE CORP", "k": "", "s": "ZZZ", "q": True}]
    assert (tmp_path / "search.js").exists()
    for f in ["index.html", "404.html", "c/AAPL/index.html", "c/ZZZ/index.html"]:
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
    assert "/search.json" in js and ("찾는 회사가 이 사이트에 없어요. 최근 60일 안에 임원·이사 거래 신고가 있는 회사만 "
                                     "있어서, 거래가 없었거나 이름이 다를 수 있어요. 미국 종목 코드(예: AAPL)로도 "
                                     "찾아보세요.") in js
    assert "공시가 없어요" not in js  # 신고가 없다고 단정하지 않는다
    assert "indexOf(q) === 0" in js  # 종목 코드 앞부분으로도 찾는다(GOOG → GOOGL)


def test_company_page_search_box_near_top(tmp_path):
    listed = result()
    outside = result(issuer_cik="901", name="TWO CO", ticker="TWO", slug="TWO", qualified=False)
    render_site([listed, outside], {"count": 1, "new": [], "dropped": [], "top": listed}, META, {}, tmp_path)
    for slug in ["EXM", "TWO"]:
        page = (tmp_path / "c" / slug / "index.html").read_text()
        assert len(re.findall(r'<form role="search"', page)) == 1
        form_at = page.index('<form role="search"')
        assert page.index("</header>") < form_at < page.index('<section class="tiles')
        if slug == "TWO":
            assert page.index('class="note band-note"') < form_at
        assert 'id="q-c"' in page and 'class="c-search' in page
        assert '<script src="/search.js" defer></script>' in page
    home = (tmp_path / "index.html").read_text()
    assert 'id="q-c"' not in home and 'class="c-search' not in home


def test_home_explanations(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    home = (tmp_path / "index.html").read_text()
    text = plain(home)
    assert "(합법)" not in home
    assert ('<p class="intro">임원의 자기 회사 주식 거래는 합법이에요. 사고팔면 이틀 안에 미국 증권거래위원회(SEC)에 '
            '공개 신고해야 하고, 그 신고를 정리해요.</p>') in home
    css = (tmp_path / "style.css").read_text()
    assert ".band .intro { margin: 6px 0 0; font-size: 15px;" in css  # 본문과 같은 크기(작은 글씨 아님)
    assert ".band .sub, .band .intro" not in css
    assert "새로 = 오늘 목록에 처음 오른 회사 · 빠짐 = 기간(60일)이 지나 목록에서 빠진 회사" in text
    assert "조건 충족 = 최근 60일 임원·이사 3명 이상이 각자 1만 달러 이상 장내 매수" in text
    details = re.search(r"<details[^>]*>\s*<summary[^>]*>매도는 왜 일어나요\?</summary>(.*?)</details>", home, re.S)
    assert details and ("임원은 월급·보너스를 회사 주식으로 받는 경우가 많아요. 그래서 세금 납부, 생활 자금, 분산 투자를 위해 "
                        "팔기도 하고, 몇 달 전에 미리 정해 둔 계획(10b5-1)대로 자동으로 팔기도 해요. 매도가 많다고 주가 "
                        "하락을 뜻하지 않아요. 반대로 매수는 이유가 비교적 단순해서 이 사이트는 매수를 중심으로 정리해요.") \
        in plain(details.group(1))
    assert home.index('class="notice"') < home.index("<details")


def test_krw_jo_unit():
    assert fmt_krw_short(1_304_600_000_000, 1) == "1.3조"   # 13046억
    assert fmt_krw_short(999_950_000_000, 1) == "1조"       # 9999.5억 → 반올림하면 1조
    assert fmt_krw_short(2_000_000_000_000, 1) == "2조"
    assert fmt_krw_short(13_046_000_000_000, 1) == "13조"
    assert fmt_krw_short(999_900_000_000, 1) == "9999억"
    assert fmt_krw(1_304_600_000_000, 1) == "약 1.3조 원"
    assert fmt_krw_short(2_400_000, 1400) == "34억" and fmt_krw_short(71_425, 1400) == "1억"


NVDA = dict(issuer_cik="1045810", name="NVIDIA CORP", ticker="NVDA", slug="NVDA")


def test_korean_name_shown_first(tmp_path):
    c = result(**NVDA)
    other = result(issuer_cik="901", name="OTHER CO", ticker="OTH", slug="OTH")
    names = {"NVDA": "엔비디아", "OTH": "추천 회사"}  # 금지어가 든 이름은 쓰지 않는다
    render_site([c, other], {"count": 2, "new": [], "dropped": [], "top": c}, META, {}, tmp_path, names)
    detail = (tmp_path / "c" / "NVDA" / "index.html").read_text()
    assert "<title>엔비디아(NVDA) 임원 매수·매도 기록 · 미국 임원 매수 정리</title>" in detail
    h1 = re.search(r"<h1>(.*?)</h1>", detail, re.S).group(1)
    assert h1.startswith("엔비디아 <span") and plain(h1).split() == ["엔비디아", "NVIDIA", "CORP", "·", "NVDA"]
    home = (tmp_path / "index.html").read_text()
    rows = re.findall(r'<a class="[^"]*\bitem\b[^"]*".*?</a>', home, re.S)
    name0 = re.search(r'<span class="name">(.*?)</span>\s*<span class="small dim">', rows[0], re.S).group(1)
    assert name0.startswith("엔비디아 <span") and "NVIDIA CORP" in name0
    name1 = re.search(r'<span class="name">(.*?)</span>\s*<span class="small dim">', rows[1], re.S).group(1)
    assert name1.startswith("OTHER CO <span") and "추천" not in home
    other_page = (tmp_path / "c" / "OTH" / "index.html").read_text()
    assert "<title>OTHER CO(OTH) 임원 매수·매도 기록 · 미국 임원 매수 정리</title>" in other_page
    assert "<h1>OTHER CO <span" in other_page
    index = {e["t"]: e for e in json.loads((tmp_path / "search.json").read_text())}
    assert index["NVDA"]["k"] == "엔비디아" and index["OTH"]["k"] == ""
    js = (tmp_path / "search.js").read_text()
    assert '(e.k || "")' in js  # 예전 search.json(k 없음)이 캐시돼 있어도 검색이 깨지지 않게


SITE = "https://form4.jmheo.com"


def head_meta(html):
    head = html[:html.index("</head>")]
    props = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)">', head))
    canonical = re.search(r'<link rel="canonical" href="([^"]+)">', head)
    title = re.search(r"<title>(.*?)</title>", head).group(1)
    return title, props, canonical.group(1) if canonical else None


def test_share_meta_tags(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    default = "미국 상장사 임원의 자기 회사 주식 거래(합법·공개 신고)를 매일 아침 한국어로 정리해요. 무료, 광고 없음, 투자 권유 아님."
    title, props, canonical = head_meta((tmp_path / "index.html").read_text())
    assert title == "미국 임원 매수 정리 · 내부자 거래 공시(Form 4) 한국어 정리"
    assert canonical == SITE + "/"
    assert props["description"] == default and props["og:description"] == default
    assert props["og:title"] == title and props["og:url"] == SITE + "/"
    assert props["og:type"] == "website" and props["og:site_name"] == "미국 임원 매수 정리"
    assert props["og:image"] == SITE + "/og.png" and props["og:locale"] == "ko_KR"
    assert props["twitter:card"] == "summary_large_image"

    title, props, canonical = head_meta((tmp_path / "c" / "EXM" / "index.html").read_text())
    summary = "".join(t for t, _ in summary_segments(c, META["fx_rate"]))
    assert canonical == SITE + "/c/EXM/" and props["og:url"] == canonical
    assert props["description"] == summary and props["og:description"] == summary
    assert props["og:title"] == title == "EXAMPLE CORP(EXM) 임원 매수·매도 기록 · 미국 임원 매수 정리"

    for f, path in [("criteria/index.html", "/criteria/"), ("privacy/index.html", "/privacy/")]:
        title, props, canonical = head_meta((tmp_path / f).read_text())
        assert canonical == SITE + path and props["og:url"] == canonical
        assert props["description"] and props["description"] != default and props["og:title"] == title
    _, props, _ = head_meta((tmp_path / "404.html").read_text())
    assert props["description"] and props["description"] != default


def test_page_description_cuts_at_sentence():
    short = "첫 문장이에요. 둘째 문장이에요."
    assert page_description(short) == short
    long = "가" * 100 + "요. " + "나" * 60 + "요. 끝이에요."
    assert page_description(long) == "가" * 100 + "요."
    no_stop = "다" * 200
    cut = page_description(no_stop)
    assert len(cut) <= 150 and cut.endswith("…")


def test_company_page_copy_link_button(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    band = detail[detail.index('<header class="band">'):detail.index("</header>")]
    assert re.search(r'<button type="button" class="copy" data-copy-link hidden>링크 복사</button>', band)
    assert '<script src="/share.js" defer></script>' in detail
    for f in ["index.html", "criteria/index.html", "privacy/index.html", "404.html"]:
        assert "share.js" not in (tmp_path / f).read_text()
    js = (tmp_path / "share.js").read_text()
    assert "navigator.clipboard" in js and "location.href" in js and "복사했어요" in js and "2000" in js
    assert ".catch(" in js and "복사하지 못했어요" in js


def test_og_image_copied(tmp_path):
    render_site([], {"count": 0, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    png = (tmp_path / "og.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(png[16:20], "big") == 1200 and int.from_bytes(png[20:24], "big") == 630


def test_sitemap_and_robots(tmp_path):
    listed = result()
    outside = result(issuer_cik="901", name="TWO CO", ticker="TWO", slug="TWO", qualified=False)
    render_site([listed, outside], {"count": 1, "new": [], "dropped": [], "top": listed}, META, {}, tmp_path)
    xml = (tmp_path / "sitemap.xml").read_text()
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in xml
    locs = re.findall(r"<url><loc>([^<]+)</loc><lastmod>2026-10-02</lastmod></url>", xml)
    assert locs == [SITE + "/", SITE + "/criteria/", SITE + "/privacy/", SITE + "/c/EXM/", SITE + "/c/TWO/"]
    assert xml.count("<url>") == 5
    assert (tmp_path / "robots.txt").read_text() == (
        "User-agent: *\nAllow: /\nSitemap: https://form4.jmheo.com/sitemap.xml\n")


def test_privacy_page_and_footer_link(tmp_path):
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    text = plain((tmp_path / "privacy" / "index.html").read_text())
    for s in ["개인정보 안내", "이 사이트는 이름·이메일 등 개인정보를 모으지 않아요",
              "회원가입·댓글·구독 없음", "검색어는 브라우저 안에서만 처리",
              "쿠키를 쓰지 않는 Cloudflare Web Analytics", "페이지별 방문 수", "(켜져 있을 때)",
              "글꼴은 구글 폰트(Google Fonts)에서 불러와요. 이때 브라우저가 구글 서버에 접속해요.",
              "form4@jmheo.com"]:
        assert s in text, s
    for f in ["index.html", "c/EXM/index.html", "criteria/index.html", "privacy/index.html", "404.html"]:
        foot = re.search(r'<footer class="foot">.*?</footer>', (tmp_path / f).read_text(), re.S).group(0)
        assert '<a href="/privacy/">개인정보 안내</a> · <a href="/criteria/#about">만든 사람·기준</a>' in foot, f


BEACON = '<script defer src="https://static.cloudflareinsights.com/beacon.min.js"'


def test_beacon_only_with_token(tmp_path):
    c = result()
    brief = {"count": 1, "new": [], "dropped": [], "top": c}
    render_site([c], brief, META, {}, tmp_path)
    for f in ["index.html", "c/EXM/index.html", "privacy/index.html"]:
        assert "cloudflareinsights" not in (tmp_path / f).read_text()
    render_site([c], brief, {**META, "beacon_token": "abc123"}, {}, tmp_path)
    tag = BEACON + """ data-cf-beacon='{"token": "abc123"}'></script>"""
    for f in ["index.html", "c/EXM/index.html", "criteria/index.html", "privacy/index.html", "404.html"]:
        assert tag in (tmp_path / f).read_text(), f


def test_home_brief_uses_korean_names(tmp_path):
    nv = result(**NVDA, total_usd=9_000_000.0)
    other = result(issuer_cik="901", name="OTHER CO", ticker="OTH", slug="OTH")
    render_site([nv, other], {"count": 2, "new": [nv, other], "dropped": [], "top": nv}, META, {}, tmp_path,
                {"NVDA": "엔비디아"})
    home = (tmp_path / "index.html").read_text()
    tiles = home[home.index('<div class="tiles">'):home.index("새로 = 오늘")]
    assert tiles.count('<span class="small">엔비디아</span>') == 2  # 새로 첫 회사 + 최대 금액
    assert "NVIDIA CORP" not in tiles
    text = plain(home)
    assert "엔비디아 — 임원·이사 5명 장내 매수" in text and "OTHER CO — 임원·이사 5명 장내 매수" in text


PRICE_NOTE = ("신고서의 주당 가격이 비정상적으로 큰 신고 2건은 원문 오류로 보고 계산에서 뺐어요. "
              "원문을 확인해 주세요.")


def test_price_error_note_only_when_present(tmp_path):
    filings = [{"filed": "2026-09-22", "url": "https://www.sec.gov/e2"},
               {"filed": "2026-09-02", "url": "https://www.sec.gov/e1"}]
    for count, shown in [(0, False), (2, True)]:
        c = result(price_error_count=count, price_error_filings=filings[:count])
        render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
        detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
        assert (PRICE_NOTE in plain(detail)) is shown
    note = re.search(r'<div class="note">.*?</div>', detail, re.S).group(0)
    links = re.findall(r'<a href="([^"]+)" target="_blank" rel="noopener">([^<]+)</a>', note)
    assert links == [("https://www.sec.gov/e2", "신고 9/22 · 원문 ↗"), ("https://www.sec.gov/e1", "신고 9/2 · 원문 ↗")]
    assert 'class="note-links"' in note


def test_home_dropped_tile_uses_korean_name(tmp_path):
    c = result()
    dropped = [{"issuer_cik": "1045810", "name": "NVIDIA CORP", "ticker": "NVDA"}]
    nv = result(**NVDA, qualified=False)
    render_site([c, nv], {"count": 1, "new": [], "dropped": dropped, "top": c}, META, {}, tmp_path,
                {"NVDA": "엔비디아"})
    home = (tmp_path / "index.html").read_text()
    tile = re.search(r'빠짐</span>.*?<span class="small">([^<]*)</span>', home, re.S).group(1)
    assert tile == "엔비디아"
    gone = [{"issuer_cik": "555", "name": "GONE CO", "ticker": "GON"}]  # 페이지가 없어진 회사는 영어 이름 그대로
    render_site([c], {"count": 1, "new": [], "dropped": gone, "top": c}, META, {}, tmp_path, {"GON": "곤"})
    home = (tmp_path / "index.html").read_text()
    assert re.search(r'빠짐</span>.*?<span class="small">([^<]*)</span>', home, re.S).group(1) == "GONE CO"


def test_naver_site_verification_meta_on_home(tmp_path):
    from form4 import config
    c = result()
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    tag = f'<meta name="naver-site-verification" content="{config.NAVER_SITE_VERIFICATION}">'
    assert tag in (tmp_path / "index.html").read_text()


def test_summary_full_text_in_html_and_typing_never_collapses(tmp_path):
    c = result(sale_people=2, sale_usd=20_000.0, sale_rows=[SELL])
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    box = re.search(r"<p class=\"summary\" data-typing>(.*?)</p>", detail, re.S).group(1)
    full = "".join(t for t, _ in summary_segments(c, META["fx_rate"]))
    assert re.sub(r"<[^>]+>", "", box) == full  # JS 가 없어도 문장 전체가 보인다
    js = (tmp_path / "typing.js").read_text()
    assert "minHeight" in js and "offsetHeight" in js  # 지우기 전에 높이를 고정해 상자가 접히지 않게
    assert "1200" in js  # 길이와 상관없이 약 1.2초 안에 끝
    assert "prefers-reduced-motion" in js and "data-replay" in js


UNPLANNED = {"date": "2026-09-24", "filed": "2026-09-25", "who": "이사", "value": 980_000.0,
             "decrease": 0.02, "tags": ["간접"], "url": "https://www.sec.gov/sell2"}


def test_sale_rows_without_plan_tag_say_so(tmp_path):
    c = result(sale_people=2, sale_usd=1_000_000.0, sale_rows=[SELL, UNPLANNED])
    render_site([c], {"count": 1, "new": [], "dropped": [], "top": c}, META, {}, tmp_path)
    detail = (tmp_path / "c" / "EXM" / "index.html").read_text()
    sells = detail[detail.index("<h2>매도 기록"):detail.index("용어 풀이")]
    rows = re.findall(r'<div class="trow">.*?</div>', sells, re.S)
    assert len(rows) == 2
    assert "계획 표시 없음" not in rows[0]  # 계획 매도 줄
    assert '<span class="small d-only">간접 · <span class="dim">계획 표시 없음</span></span>' in rows[1]
    assert re.search(r'<span class="chip m-only">간접</span><span class="small dim m-only">계획 표시 없음</span>'
                     r'<a class="small m-only"', rows[1])
    buys = detail[detail.index("<h2>매수 기록"):detail.index("<h2>매도 기록")]
    assert "계획 표시 없음" not in buys  # 매수 줄은 그대로


def test_summary_planned_sale_share():
    def text(rows, sale_usd):
        return "".join(t for t, _ in summary_segments(
            result(sale_people=len(rows), sale_usd=sale_usd, sale_rows=rows), 1400))
    plan = lambda v: {**SELL, "value": v}
    other = lambda v: {**UNPLANNED, "value": v}
    assert text([plan(30_000.0), other(970_000.0)], 1_000_000.0).endswith(
        "장내 매도했어요. 매도 금액 중 약 3%는 미리 정한 계획(10b5-1)에 따른 매도예요.")
    assert text([plan(5_000.0), other(995_000.0)], 1_000_000.0).endswith(
        "매도 금액 중 1% 미만은 미리 정한 계획(10b5-1)에 따른 매도예요.")
    assert text([plan(20_000.0)], 20_000.0).endswith("매도 금액 중 약 100%는 미리 정한 계획(10b5-1)에 따른 매도예요.")
    assert text([other(20_000.0)], 20_000.0).endswith("장내 매도했어요. 미리 정한 계획(10b5-1) 매도 표시는 없어요.")
    assert text([], 0.0).endswith("같은 기간 장내 매도 신고는 없어요.")


def test_criteria_window_reason_and_about(tmp_path):
    render_site([], {"count": 0, "new": [], "dropped": [], "top": None}, META, {}, tmp_path)
    page = (tmp_path / "criteria" / "index.html").read_text()
    text = plain(page)
    assert "3. 최근 60일(거래한 날짜 기준, 달력 날짜) 동안 1인 합계 10,000달러 미만은 세지 않습니다." in text
    assert "(거래일 기준)" not in text
    assert ("왜 이 기준인가요? 한 사람의 매수는 개인 사정일 수 있어서, 같은 회사에서 여러 임원·이사가 비슷한 시기에 "
            "시장에서 산 경우만 모았어요. 1만 달러 미만의 소액은 뺐어요. 이 기준은 주가를 예측하지 않아요.") in text
    about = re.search(r'<section class="card" id="about">(.*?)</section>', page, re.S).group(1)
    assert plain(about).strip() == (
        "만든 사람 개인이 만들어 운영해요. 광고·후원·유료 기능이 없고, 운영자는 이 사이트로 수익을 받지 않아요. "
        "운영자는 목록·검색 결과의 종목을 따로 사고팔지 않아요. 문의: form4@jmheo.com")
    assert "자기 돈" not in page
