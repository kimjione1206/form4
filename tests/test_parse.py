from datetime import date

import pytest

from form4.parse import extract_xml, filing_url, parse_form4
from helpers import form4_xml, submission

FILED = date(2026, 10, 2)


def test_extract_xml_from_submission():
    xml = form4_xml()
    assert extract_xml(submission(xml)) == xml


def test_extract_xml_missing_block():
    with pytest.raises(ValueError):
        extract_xml("<SEC-DOCUMENT>no xml</SEC-DOCUMENT>")


def test_keeps_only_p_and_s_lines():
    xml = form4_xml(txs=[
        {"code": "P", "date": "2026-09-30", "shares": 100, "price": 50, "after": 1000},
        {"code": "A", "date": "2026-09-30", "shares": 10, "price": 0, "after": 1010},
        {"code": "S", "date": "2026-09-30", "shares": 5, "price": 51, "after": 1005},
    ])
    recs = parse_form4(xml, "0001-26-1", FILED)
    assert [r["code"] for r in recs] == ["P", "S"]


def test_record_fields():
    xml = form4_xml(issuer_cik="1000697", ticker="wat",
                    owners=[{"cik": "1867980", "officer": True, "title": "Chief Executive Officer"}],
                    txs=[{"code": "P", "date": "2026-09-30", "shares": 100, "price": 42.5,
                          "after": 1100, "direct": "I"}],
                    plan=True)
    r = parse_form4(xml, "0001000697-26-000136", FILED)[0]
    assert r["issuer_cik"] == "1000697" and r["ticker"] == "WAT"
    assert r["owners"] == [{"cik": "1867980", "is_director": False, "is_officer": True,
                            "is_ten_pct": False, "title": "Chief Executive Officer",
                            "is_entity": False}]
    assert r["plan"] is True and r["direct"] == "I"
    assert (r["shares"], r["price"], r["after"]) == (100.0, 42.5, 1100.0)
    assert r["date"] == "2026-09-30" and r["filed"] == "2026-10-02" and r["form"] == "4"
    assert r["url"] == filing_url("1000697", "0001000697-26-000136")
    assert "SECRET" not in str(r)  # 이름은 저장하지 않는다


def test_filing_url_shape():
    assert filing_url("1000697", "0001000697-26-000136") == (
        "https://www.sec.gov/Archives/edgar/data/1000697/000100069726000136/"
        "0001000697-26-000136-index.htm"
    )


def test_joint_filers_listed_on_each_line():
    xml = form4_xml(owners=[{"cik": "1", "director": True}, {"cik": "2", "ten_pct": True}])
    r = parse_form4(xml, "a", FILED)[0]
    assert [o["cik"] for o in r["owners"]] == ["1", "2"]
    assert r["owners"][1]["is_ten_pct"] is True


def test_offering_footnote_detected_only_when_referenced():
    xml = form4_xml(
        txs=[{"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 2, "footnotes": ["F1"]},
             {"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 3}],
        footnotes={"F1": "Shares purchased in the issuer's underwritten public offering."},
    )
    recs = parse_form4(xml, "a", FILED)
    assert [r["offering"] for r in recs] == [True, False]


def test_amendment_form_and_missing_after():
    xml = form4_xml(doc_type="4/A",
                    txs=[{"code": "P", "date": "2026-09-30-05:00", "shares": 1, "price": 1, "after": None}])
    r = parse_form4(xml, "a", FILED)[0]
    assert r["form"] == "4/A" and r["after"] is None and r["date"] == "2026-09-30"


def test_entity_owner_flagged_without_storing_name():
    xml = form4_xml(owners=[{"cik": "1", "director": True, "name": "ABC CAPITAL PARTNERS LP"},
                            {"cik": "2", "director": True}])
    r = parse_form4(xml, "a", FILED)[0]
    assert [o["is_entity"] for o in r["owners"]] == [True, False]
    assert "ABC" not in str(r) and "SECRET" not in str(r)


def test_entity_words_are_word_bounded():
    def flagged(name):
        xml = form4_xml(owners=[{"cik": "1", "director": True, "name": name}])
        return parse_form4(xml, "a", FILED)[0]["owners"][0]["is_entity"]
    assert flagged("Acme Holdings, L.L.C.") and flagged("Foo Fund I, L.P.") and flagged("BAR INC.")
    assert not flagged("SAGE JOHN") and not flagged("TRUSTY ANN")


def test_offering_word_alone_detected():
    xml = form4_xml(txs=[{"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 2,
                          "footnotes": ["F1"]}],
                    footnotes={"F1": "Shares purchased in the Offering."})
    assert parse_form4(xml, "a", FILED)[0]["offering"] is True


def test_dividend_reinvestment_footnote_marked_drip():
    xml = form4_xml(
        txs=[{"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 2, "footnotes": ["F1"]},
             {"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 3, "footnotes": ["F2"]}],
        footnotes={"F1": "Represents shares of common stock acquired through the reinvestment of "
                         "dividends received on restricted stock",
                   "F2": "Weighted average price"},
    )
    assert [r["drip"] for r in parse_form4(xml, "a", FILED)] == [True, False]


def test_footnote_text_read_past_inner_elements():
    xml = form4_xml(txs=[{"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 2,
                          "footnotes": ["F1"]}],
                    footnotes={"F1": "Price note.<b>x</b> Purchased in the Offering; dividend reinvestment."})
    r = parse_form4(xml, "a", FILED)[0]
    assert r["offering"] is True and r["drip"] is True


def test_only_transaction_footnotes_mark_drip_and_offering():
    notes = {"F1": "Includes 120 shares acquired under the Issuer's Dividend Reinvestment Plan.",
             "F2": "Includes shares purchased in the IPO."}
    tx = {"code": "P", "date": "2026-09-30", "shares": 1, "price": 1, "after": 2}
    on_holdings = form4_xml(txs=[{**tx, "after_footnotes": ["F1", "F2"]}], footnotes=notes)
    r = parse_form4(on_holdings, "a", FILED)[0]
    assert r["drip"] is False and r["offering"] is False
    on_price = form4_xml(txs=[{**tx, "price_footnotes": ["F1", "F2"]}], footnotes=notes)
    r = parse_form4(on_price, "a", FILED)[0]
    assert r["drip"] is True and r["offering"] is True


def test_offering_footnote_on_security_title_counts():
    # 실제 사례(EDAP): "공모로 산 주식"이라는 각주가 증권 종류 칸에 붙어 있다
    tx = {"code": "P", "date": "2026-08-14", "shares": 1, "price": 1, "after": 2, "title_footnotes": ["F2"]}
    xml = form4_xml(txs=[tx], footnotes={"F2": "ordinary shares purchased in connection with an underwritten public offering"})
    assert parse_form4(xml, "a", FILED)[0]["offering"] is True


def test_exercise_marks_lines_with_option_exercise_same_day():
    sale = {"code": "S", "date": "2026-09-30", "shares": 10, "price": 5, "after": 90}
    exercise_same_day = {"code": "M", "date": "2026-09-30", "shares": 10, "price": 1, "after": 100}
    in_table = form4_xml(txs=[exercise_same_day, sale])
    assert [r["exercise"] for r in parse_form4(in_table, "a", FILED)] == [True]
    deriv = form4_xml(txs=[sale], deriv_txs=[{"code": "M", "date": "2026-09-30-04:00"}])
    assert parse_form4(deriv, "a", FILED)[0]["exercise"] is True
    other_day = form4_xml(txs=[sale], deriv_txs=[{"code": "M", "date": "2026-09-29"}])
    assert parse_form4(other_day, "a", FILED)[0]["exercise"] is False
    no_m = form4_xml(txs=[sale], deriv_txs=[{"code": "A", "date": "2026-09-30"}])
    assert parse_form4(no_m, "a", FILED)[0]["exercise"] is False
    buy = form4_xml()
    assert parse_form4(buy, "a", FILED)[0]["exercise"] is False
