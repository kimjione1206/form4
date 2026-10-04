from datetime import date

from form4.index import parse_master_index

SAMPLE = """Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    Oct 2, 2026

CIK|Company Name|Form Type|Date Filed|File Name
--------------------------------------------------------------------------------
1000275|ROYAL BANK OF CANADA|424B2|20261002|edgar/data/1000275/0000950103-26-014973.txt
1000697|WATERS CORP /DE/|4|20261002|edgar/data/1000697/0001000697-26-000136.txt
1867980|REPORTING PERSON|4|20261002|edgar/data/1867980/0001000697-26-000136.txt
1001085|BROOKFIELD Corp /ON/|4/A|20261002|edgar/data/1001085/0001193125-26-412127.txt
"""


def test_keeps_only_form4_and_dedupes_by_accession():
    refs = parse_master_index(SAMPLE)
    assert [r.accession for r in refs] == ["0001000697-26-000136", "0001193125-26-412127"]
    assert refs[0].form == "4" and refs[1].form == "4/A"
    assert refs[0].filed == date(2026, 10, 2)
    assert refs[0].url == "https://www.sec.gov/Archives/edgar/data/1000697/0001000697-26-000136.txt"


def test_header_line_is_ignored():
    assert parse_master_index("CIK|Company Name|Form Type|Date Filed|File Name\n") == []
