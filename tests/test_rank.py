from datetime import date

from form4 import store
from form4.rank import owner_label, profiles, rank
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


def test_sale_people_and_tags():
    recs = buys(2) + [
        make_rec("ceo", owners=[officer("5", "Chief Executive Officer")], plan=True,
                 direct="I", shares=1000, price=20.0),
        make_rec("s1", code="S", owners=[director("0")]),
    ]
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["sale_people"] == 1 and "sales" not in c
    assert c["tags"] == ["대표이사 포함", "계획 매수 포함"]
    row = [r for r in c["rows"] if r["ceo"]][0]
    assert row["who"] == "대표이사" and row["tags"] == ["계획 매수", "간접"]


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
    for t in ["See Remarks", " see remark ", "SEE REMARKS", "   "]:
        assert owner_label(officer("1", t), {"See Remarks": "비고 참조"}) == "임원"
    assert owner_label(officer("1", "See Remarks below"), TITLES) == "See Remarks below"


def test_officer_titles_include_sellers_and_skip_see_remarks():
    recs = buys(2) + [make_rec("r", owners=[officer("8", "See Remarks")], shares=1000, price=20.0)] + sold(
        "s", [officer("9", "Chief Legal Officer")], issuer="X", ticker="SEL")
    ps = {p["issuer_cik"]: p for p in profiles(recs, AS_OF, TITLES)}
    assert ps["900"]["officer_titles"] == []
    assert ps["X"]["officer_titles"] == ["Chief Legal Officer"]


def test_company_without_ticker_excluded():
    assert rank(buys(3, ticker=""), AS_OF, TITLES) == []
    assert rank(buys(3, ticker="NONE"), AS_OF, TITLES) == []
    assert rank(buys(3, ticker=" n/a "), AS_OF, TITLES) == []
    for ticker in ["-", "..", " . "]:
        assert rank(buys(3, ticker=ticker), AS_OF, TITLES) == []
    assert rank(buys(3, ticker="EXM"), AS_OF, TITLES)[0]["ticker"] == "EXM"


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


def test_offering_not_counted_but_reported():
    offer = make_rec("O", owners=[director("7")], offering=True, shares=1000, price=30.0)
    assert rank(buys(2) + [offer], AS_OF, TITLES) == []
    fund_offer = make_rec("FO", owners=[fund("50")], offering=True, shares=1000, price=100.0)
    c = rank(buys(3) + [offer, fund_offer], AS_OF, TITLES)[0]
    assert c["people"] == 3 and c["total_usd"] == 60_000.0 and len(c["rows"]) == 3
    assert c["offering_usd"] == 30_000.0 and c["ten_pct_usd"] == 100_000.0
    assert rank(buys(3), AS_OF, TITLES)[0]["offering_usd"] == 0.0


def sold(accession, owners, **kw):
    """저장될 때처럼 신고서당 한 줄로 줄인 매도."""
    return store.merge([], [make_rec(accession, code="S", owners=owners, **kw)])


def test_sale_people_and_usd_count_only_insider_individuals():
    recs = buys(3) + (
        sold("s1", [director("0"), entity_director("E")], shares=100, price=10.0)
        + sold("s2", [director("0")], shares=50, price=10.0)
        + sold("s3", [officer("8", "Chief Financial Officer")], shares=10, price=10.0)
        + sold("s4", [entity_director("E2")], shares=1000, price=10.0)
        + sold("s5", [director("9"), fund("F")], shares=20, price=10.0)
    ) + [{**make_rec("s6", code="S", owners=[fund("F2")], shares=1000, price=10.0),
          "value": 10_000.0}]  # 10% 대주주만 (저장 단계에서 빠지지만 혹시 들어와도 안 셈)
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["sale_people"] == 3  # 이사 0, CFO 8, 이사 9 — 법인·대주주는 빼고
    assert c["sale_usd"] == 1_800.0
    assert sorted(r["url"][-2:] for r in c["sale_rows"]) == ["s1", "s2", "s3", "s5"]
    assert c["people"] == 3 and c["total_usd"] == 60_000.0  # 매도는 조건·순서에 영향 없음


def test_sale_rows_decrease_tags_and_order():
    recs = buys(3) + (
        sold("a", [officer("8", "Chief Financial Officer"), director("2")], date="2026-09-20",
             shares=200, price=10.0, after=800.0, plan=True, exercise=True, direct="I")
        + sold("b", [director("0")], date="2026-09-25", shares=100, price=10.0, after=None)
        + sold("c", [director("1")], date="2026-09-25", shares=10, price=10.0, after=0.0)
    )
    rows = rank(recs, AS_OF, TITLES)[0]["sale_rows"]
    assert [r["url"][-1] for r in rows] == ["b", "c", "a"]
    a = rows[2]
    assert a["who"] == "재무이사(CFO) 외 1명" and a["value"] == 2_000.0
    assert abs(a["decrease"] - 0.2) < 1e-9
    assert a["tags"] == ["계획 매도", "옵션 행사 후 매도", "간접"]
    assert (a["date"], a["filed"]) == ("2026-09-20", "2026-09-20")
    assert rows[0]["decrease"] is None and rows[0]["tags"] == []
    assert rows[1]["decrease"] == 1.0  # 전부 팜
    zero = sold("z", [director("0")], shares=0.0, price=10.0, after=0.0)
    assert rank(buys(3) + zero, AS_OF, TITLES)[0]["sale_rows"][0]["decrease"] is None


def test_old_shape_sale_rows_count_as_zero_amount():
    old = {k: v for k, v in make_rec("old", code="S").items() if k in store.SALE_KEYS}
    c = rank(buys(3) + [old], AS_OF, TITLES)[0]
    assert c["sale_people"] == 1 and c["sale_usd"] == 0.0
    [row] = c["sale_rows"]
    assert row["value"] == 0.0 and row["decrease"] is None and row["tags"] == []


def test_no_sales():
    c = rank(buys(3), AS_OF, TITLES)[0]
    assert (c["sale_people"], c["sale_usd"], c["sale_rows"]) == (0, 0.0, [])


def test_profile_with_only_sells():
    recs = buys(3) + sold("s", [director("7")], issuer="X", ticker="SEL", shares=100, price=10.0)
    p = {c["issuer_cik"]: c for c in profiles(recs, AS_OF, TITLES)}["X"]
    assert p["qualified"] is False and p["slug"] == "SEL"
    assert (p["people"], p["total_usd"], p["rows"], p["top"]) == (0, 0.0, [], None)
    assert p["sale_people"] == 1 and p["sale_usd"] == 1_000.0 and len(p["sale_rows"]) == 1


def test_profile_two_small_buyers_shows_what_exists():
    recs = [make_rec("a", owners=[director("1")], shares=1000, price=20.0),
            make_rec("b", owners=[director("2")], shares=100, price=20.0)]  # 2,000달러도 셈
    [p] = profiles(recs, AS_OF, TITLES)
    assert p["qualified"] is False
    assert p["people"] == 2 and p["total_usd"] == 22_000.0 and len(p["rows"]) == 2
    assert p["top"]["value"] == 20_000.0 and p["tags"] == []


def test_profiles_skip_companies_without_insider_trades_or_ticker():
    recs = (buys(2, issuer="NT", ticker="")
            + [make_rec("F", issuer="FU", owners=[fund("50")]),
               make_rec("O", issuer="OF", owners=[director("1")], offering=True),
               make_rec("D", issuer="DR", owners=[director("1")], drip=True)]
            + sold("E", [entity_director("9")], issuer="EN"))
    assert profiles(recs, AS_OF, TITLES) == []


def test_qualified_flag_matches_rank():
    recs = (buys(3, issuer="A", ticker="AAA") + buys(4, value_each=11_000, issuer="B", ticker="BBB")
            + buys(2, issuer="C", ticker="CCC") + sold("s", [director("1")], issuer="D", ticker="DDD"))
    ps = profiles(recs, AS_OF, TITLES)
    assert [p["issuer_cik"] for p in ps if p["qualified"]] == [c["issuer_cik"] for c in rank(recs, AS_OF, TITLES)]
    assert {p["issuer_cik"]: p["qualified"] for p in ps} == {"A": True, "B": True, "C": False, "D": False}


def test_profile_slugs_unique_and_listed_slugs_unchanged():
    small = [make_rec(f"n{i}", issuer="33", ticker="ABC", owners=[director(str(i))], shares=100, price=20.0)
             for i in range(6)]  # 6명이지만 각자 2,000달러 → 목록 밖, 사람 수는 더 많음
    recs = buys(3, issuer="11", ticker="ABC") + buys(4, issuer="22", ticker="ABC") + small
    listed = {c["issuer_cik"]: c["slug"] for c in rank(buys(3, issuer="11", ticker="ABC")
                                                        + buys(4, issuer="22", ticker="ABC"), AS_OF, TITLES)}
    ps = profiles(recs, AS_OF, TITLES)
    slugs = {p["issuer_cik"]: p["slug"] for p in ps}
    assert {k: slugs[k] for k in listed} == listed == {"22": "ABC", "11": "ABC-11"}
    assert slugs["33"] == "ABC-33" and len(set(slugs.values())) == len(ps)
    assert {c["issuer_cik"]: c["slug"] for c in rank(recs, AS_OF, TITLES)} == listed


def test_absurd_buy_price_is_filing_error():
    slbt = make_rec("bad", owners=[director("88")], shares=4_400_000, price=2_272_653.0)  # SLBT 사례
    c = rank(buys(3) + [slbt], AS_OF, TITLES)[0]
    assert c["people"] == 3 and c["total_usd"] == 60_000.0 and len(c["rows"]) == 3
    assert c["price_error_count"] == 1
    assert rank(buys(2) + [slbt], AS_OF, TITLES) == []
    assert profiles(buys(3), AS_OF, TITLES)[0]["price_error_count"] == 0


def test_allowlisted_ticker_high_price_counted():
    recs = [make_rec(f"b{i}", owners=[director(str(i))], ticker="BRK.A", shares=1, price=700_000.0)
            for i in range(3)]
    c = rank(recs, AS_OF, TITLES)[0]
    assert c["total_usd"] == 2_100_000.0 and c["price_error_count"] == 0


def test_sale_with_price_error_flag():
    partial = store.merge([], [make_rec("s1", code="S", owners=[director("0")], shares=100, price=10.0),
                               make_rec("s1", code="S", owners=[director("0")], shares=9, price=60_000.0)])
    all_bad = store.merge([], [make_rec("s2", code="S", owners=[director("1")], shares=9, price=60_000.0)])
    c = profiles(buys(3) + partial + all_bad, AS_OF, TITLES)[0]
    assert c["sale_people"] == 1 and c["sale_usd"] == 1000.0 and len(c["sale_rows"]) == 1
    assert c["price_error_count"] == 2


def test_company_with_only_price_error_filings_keeps_page_with_note():
    slbt = make_rec("bad", issuer="77", owners=[director("88")], shares=4_400_000, price=2_272_653.0, ticker="SLBT")
    [c] = profiles([slbt], AS_OF, TITLES)
    assert c["ticker"] == "SLBT" and not c["qualified"] and c["people"] == 0 and c["total_usd"] == 0
    assert c["rows"] == [] and c["price_error_count"] == 1
