from form4.briefing import briefing, snapshot


def co(cik, total):
    return {"issuer_cik": cik, "name": f"CO{cik}", "ticker": f"T{cik}", "total_usd": total}


def test_new_dropped_top():
    prev = snapshot([co("1", 10), co("2", 20)])
    b = briefing([co("2", 20), co("3", 99)], prev)
    assert [c["issuer_cik"] for c in b["new"]] == ["3"]
    assert [c["issuer_cik"] for c in b["dropped"]] == ["1"]
    assert b["top"]["issuer_cik"] == "3" and b["count"] == 2


def test_first_run_has_no_new_or_dropped():
    b = briefing([co("1", 5)], None)
    assert b["new"] == [] and b["dropped"] == [] and b["top"]["issuer_cik"] == "1"


def test_empty_results():
    assert briefing([], []) == {"count": 0, "new": [], "dropped": [], "top": None}


def test_recent_within_seven_days_newest_first_then_people():
    from datetime import date
    from form4.briefing import recent

    def c(cik, last, people):
        return {"issuer_cik": cik, "last_date": last, "people": people}
    rs = [c("old", "2026-09-25", 9), c("a", "2026-09-26", 3), c("b", "2026-10-01", 3),
          c("c", "2026-10-01", 5), c("d", "2026-09-30", 4), c("none", None, 3)]
    assert [x["issuer_cik"] for x in recent(rs, date(2026, 10, 2))] == ["c", "b", "d"]
    assert [x["issuer_cik"] for x in recent(rs[:2], date(2026, 10, 2))] == ["a"]  # 9/26 = 기준일 − 6일
    assert recent([c("old", "2026-09-25", 9)], date(2026, 10, 2)) == []


def test_briefing_and_recent_for_sell_list():
    from datetime import date
    from form4.briefing import recent

    def s(cik, total, last, people):
        return {"issuer_cik": cik, "name": f"CO{cik}", "ticker": f"T{cik}", "total_usd": 0.0,
                "sell_total_usd": total, "sell_last_date": last, "sell_people": people, "last_date": None,
                "people": 0}
    rs = [s("1", 10, "2026-09-30", 3), s("2", 99, "2026-10-01", 3), s("3", 50, "2026-10-01", 5)]
    b = briefing(rs, snapshot(rs[:1]), total="sell_total_usd")
    assert b["top"]["issuer_cik"] == "2" and [c["issuer_cik"] for c in b["new"]] == ["2", "3"]
    hits = recent(rs, date(2026, 10, 2), last="sell_last_date", people="sell_people")
    assert [c["issuer_cik"] for c in hits] == ["3", "2", "1"]
