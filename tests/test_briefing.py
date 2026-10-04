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
