from datetime import date

from form4 import store
from helpers import director, fund, make_rec


def test_merge_replaces_same_accession():
    old = [make_rec("A1", shares=1)]
    merged = store.merge(old, [make_rec("A1", shares=2)])
    assert [r["shares"] for r in merged] == [2]


def test_amendment_replaces_original_same_owner_issuer_date():
    orig = make_rec("A1", date="2026-09-30", shares=100)
    other_day = make_rec("A0", date="2026-09-29", shares=50)
    amended = make_rec("A2", form="4/A", date="2026-09-30", shares=120)
    merged = store.merge([orig, other_day], [amended])
    assert sorted(r["accession"] for r in merged) == ["A0", "A2"]


def test_amendment_and_original_in_same_batch_keeps_only_amendment():
    orig = make_rec("A1", date="2026-09-30", shares=100)
    amended = make_rec("A2", form="4/A", date="2026-09-30", shares=120)
    merged = store.merge([], [orig, amended])
    assert [r["accession"] for r in merged] == ["A2"]


def test_original_arriving_after_stored_amendment_is_dropped():
    amended = make_rec("A2", form="4/A", date="2026-09-30", shares=120)
    orig = make_rec("A1", date="2026-09-30", shares=100)
    merged = store.merge([amended], [orig])
    assert [r["accession"] for r in merged] == ["A2"]


def test_newer_amendment_replaces_stored_amendment_keeping_all_its_lines():
    stored = make_rec("A2", form="4/A", date="2026-09-30", filed="2026-10-01", shares=120)
    line1 = make_rec("A3", form="4/A", date="2026-09-30", filed="2026-10-02", shares=130)
    line2 = make_rec("A3", form="4/A", date="2026-09-30", filed="2026-10-02", shares=10)
    merged = store.merge([stored], [line1, line2])
    assert [(r["accession"], r["shares"]) for r in merged] == [("A3", 130), ("A3", 10)]


def test_two_amendments_same_key_in_one_batch_keep_newer():
    newer = make_rec("A3", form="4/A", date="2026-09-30", filed="2026-10-02")
    older = make_rec("A2", form="4/A", date="2026-09-30", filed="2026-10-01")
    merged = store.merge([], [newer, older])
    assert [r["accession"] for r in merged] == ["A3"]


def test_sales_collapsed_to_one_per_filing_and_insider_only():
    s1 = make_rec("S1", code="S", date="2026-09-28")
    s2 = make_rec("S1", code="S", date="2026-09-29")
    fund_sale = make_rec("S2", code="S", owners=[fund("9")])
    merged = store.merge([], [s1, s2, fund_sale])
    assert len(merged) == 1
    assert merged[0]["accession"] == "S1" and merged[0]["date"] == "2026-09-29"


def test_collapsed_sale_keeps_sums_last_holding_and_flags():
    s1 = make_rec("S1", code="S", date="2026-09-29", shares=100, price=10.0, after=850.0,
                  direct="I", exercise=True, plan=True)
    s2 = make_rec("S1", code="S", date="2026-09-28", shares=50, price=12.0, after=900.0)
    s3 = make_rec("S1", code="S", date="2026-09-29", shares=30, price=10.0, after=820.0)
    [row] = store.merge([], [s1, s2, s3])
    assert row["shares"] == 180 and row["value"] == 1900.0
    assert row["after"] == 820.0 and row["direct"] == "D"  # 같은 날이면 뒤에 적힌 줄
    assert row["plan"] is True and row["exercise"] is True and row["date"] == "2026-09-29"
    assert "price" not in row


def test_old_shape_sale_rows_still_merge_and_save(tmp_path):
    old = {k: v for k, v in make_rec("S0", code="S").items() if k in store.SALE_KEYS}
    merged = store.merge([old], [make_rec("P1")])
    store.save(tmp_path / "t.jsonl", merged)
    assert sorted(r["accession"] for r in store.load(tmp_path / "t.jsonl")) == ["P1", "S0"]


def test_prune_keeps_window_by_trade_date():
    recs = [make_rec("A", date="2026-08-04"), make_rec("B", date="2026-08-05")]
    kept = store.prune(recs, date(2026, 10, 3), 60)
    assert [r["accession"] for r in kept] == ["B"]


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "t.jsonl"
    recs = [make_rec("B", date="2026-09-30"), make_rec("A", date="2026-09-29", owners=[director("7")])]
    store.save(p, recs)
    assert [r["accession"] for r in store.load(p)] == ["A", "B"]
    assert store.load(tmp_path / "none.jsonl") == []
