from datetime import date

from form4.rank import owner_label, rank
from helpers import director, entity_director, fund, make_rec, officer

AS_OF = date(2026, 10, 2)
TITLES = {"Chief Financial Officer": "재무이사(CFO)"}


def buys(n, value_each=20_000.0, issuer="900", **kw):
    return [make_rec(f"{issuer}-{i}", issuer=issuer, owners=[director(str(i))],
                     shares=value_each / 20, price=20.0, **kw) for i in range(n)]


def test_needs_three_people():
    assert rank(buys(2), AS_OF, TITLES) == []
    assert rank(buys(3), AS_OF, TITLES)[0]["people"] == 3


def test_person_below_10k_not_counted():
    recs = buys(2) + [make_rec("small", owners=[director("99")], shares=100, price=99.0)]
    assert rank(recs, AS_OF, TITLES) == []  # 9,900달러는 세지 않음


def test_ten_pct_owner_excluded_but_reported():
    recs = buys(3) + [make_rec("F", owners=[fund("50")], shares=1000, price=100.0)]
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["people"] == 3 and c["total_usd"] == 60_000.0
    assert c["ten_pct_usd"] == 100_000.0


def test_outside_window_ignored():
    recs = buys(2) + [make_rec("old", owners=[director("77")], date="2026-08-03",
                               shares=1000, price=20.0)]
    assert rank(recs, AS_OF, TITLES) == []


def test_sort_by_people_then_total():
    a = buys(3, value_each=50_000, issuer="A")
    b = buys(4, value_each=11_000, issuer="B")
    c = buys(3, value_each=90_000, issuer="C")
    assert [r["issuer_cik"] for r in rank(a + b + c, AS_OF, TITLES)] == ["B", "C", "A"]


def test_sales_count_and_tags():
    recs = buys(2) + [
        make_rec("ceo", owners=[officer("5", "Chief Executive Officer")], plan=True,
                 direct="I", offering=True, shares=1000, price=20.0),
        make_rec("s1", code="S", owners=[director("0")]),
    ]
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["sales"] == 1
    assert c["tags"] == ["대표이사 포함", "계획 매수 포함", "증자 참여 포함"]
    row = [r for r in c["rows"] if r["ceo"]][0]
    assert row["who"] == "대표이사" and row["tags"] == ["계획 매수", "간접", "증자 참여"]


def test_same_day_batch_tag():
    owners = [officer(str(i), "Senior Vice President") for i in range(3)]
    recs = [make_rec(f"v{i}", owners=[o], filed="2026-10-01", shares=1000, price=20.0 + i)
            for i, o in enumerate(owners)]
    assert "같은 날 여러 명 매수" in rank(recs, AS_OF, TITLES)[0]["tags"]
    spread = [make_rec(f"w{i}", owners=[o], filed="2026-10-01", shares=1000, price=20.0 * (i + 1))
              for i, o in enumerate(owners)]
    assert "같은 날 여러 명 매수" not in rank(spread, AS_OF, TITLES)[0]["tags"]


def test_same_day_batch_tag_svp_evp_abbreviations():
    titles = ["SVP Sales", "EVP Operations", "SVP Finance"]
    recs = [make_rec(f"a{i}", owners=[officer(str(i), t)], filed="2026-10-01",
                     shares=1000, price=20.0 + i) for i, t in enumerate(titles)]
    assert "같은 날 여러 명 매수" in rank(recs, AS_OF, TITLES)[0]["tags"]


def test_increase_and_rows():
    recs = buys(2) + [make_rec("x", owners=[officer("8", "Chief Financial Officer")],
                               shares=1000, price=20.0, after=6000.0),
                      make_rec("y", owners=[director("9")], shares=1000, price=20.0, after=1000.0)]
    c = rank(recs, AS_OF, TITLES)[0]
    inc = {r["who"]: r["increase"] for r in c["rows"]}
    assert abs(inc["재무이사(CFO)"] - 0.2) < 1e-9
    director_incs = [r["increase"] for r in c["rows"] if r["who"] == "이사"]
    assert "new" in director_incs
    assert 0.25 in director_incs
    assert c["top"]["value"] == max(r["value"] for r in c["rows"])
    assert c["officer_titles"] == ["Chief Financial Officer"]


def test_joint_filing_counted_once_in_total():
    joint = make_rec("J", owners=[director("1"), director("2"), director("3")],
                     shares=1000, price=20.0)
    c = rank([joint], AS_OF, TITLES)[0]
    assert c["people"] == 3 and c["total_usd"] == 20_000.0
    assert c["rows"][0]["who"] == "이사 외 2명"


def test_owner_label():
    assert owner_label(officer("1", "Chief Financial Officer"), TITLES) == "재무이사(CFO)"
    assert owner_label(officer("1", "CEO & Founder"), TITLES) == "대표이사"
    assert owner_label(officer("1", "SVP Sales"), TITLES) == "SVP Sales"
    assert owner_label(officer("1", ""), TITLES) == "임원"
    assert owner_label(director("1"), TITLES) == "이사"


def test_slug_placeholder_tickers_use_cik():
    recs = (buys(3, issuer="11", ticker="NONE") + buys(3, issuer="22", ticker="NONE")
            + buys(3, issuer="33", ticker="..") + buys(3, issuer="44", ticker="N/A"))
    slugs = {c["issuer_cik"]: c["slug"] for c in rank(recs, AS_OF, TITLES)}
    assert slugs == {"11": "cik11", "22": "cik22", "33": "cik33", "44": "cik44"}


def test_slug_same_ticker_later_gets_cik_suffix():
    recs = buys(3, issuer="11", ticker="ABC") + buys(4, issuer="22", ticker="ABC")
    assert [c["slug"] for c in rank(recs, AS_OF, TITLES)] == ["ABC", "ABC-11"]


def test_entity_directors_are_not_people():
    joint = make_rec("E", owners=[entity_director("1"), entity_director("2"), entity_director("3")],
                     shares=1000, price=20.0)
    assert rank([joint], AS_OF, TITLES) == []


def test_entity_director_not_third_person_but_reported():
    ent = make_rec("E", owners=[entity_director("50")], shares=1000, price=100.0)
    assert rank(buys(2) + [ent], AS_OF, TITLES) == []
    c = rank(buys(3) + [ent], AS_OF, TITLES)[0]
    assert c["people"] == 3 and c["total_usd"] == 60_000.0
    assert c["ten_pct_usd"] == 100_000.0


def test_owner_label_ignores_title_translation_failing_guard():
    titles = {"Chief Growth Officer": "최고성장책임자"}  # 금지어 '성장'
    assert owner_label(officer("1", "Chief Growth Officer"), titles) == "Chief Growth Officer"


def test_dividend_reinvestment_ignored():
    assert rank(buys(3, drip=True), AS_OF, TITLES) == []
    recs = buys(3) + [make_rec("D", owners=[director("0")], drip=True, shares=1000, price=20.0)]
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["total_usd"] == 60_000.0 and len(c["rows"]) == 3
    fund_drip = make_rec("FD", owners=[fund("50")], drip=True, shares=1000, price=100.0)
    assert rank(buys(3) + [fund_drip], AS_OF, TITLES)[0]["ten_pct_usd"] == 0.0
