"""Form 4 신고서 XML → 거래 줄(P·S만). 신고자 이름은 저장하지 않는다."""

import re
import xml.etree.ElementTree as ET
from datetime import date

OFFERING_RE = re.compile(
    r"public offering|private placement|underwritten|registered direct|\bIPO\b|\boffering\b", re.I
)
# 신고자 이름에 이 단어가 있으면 사람이 아닌 법인(펀드·회사)으로 본다. 이름 자체는 저장하지 않는다.
ENTITY_RE = re.compile(
    r"(?<![A-Z0-9])(?:LLC|L\.L\.C\.|LP|L\.P\.|FUNDS?|PARTNERS|PARTNERSHIP|TRUST|HOLDINGS|CAPITAL"
    r"|INC\.?|CORP|CORPORATION|LTD|LIMITED|MANAGEMENT|GROUP|VENTURES|ADVISORS|ADVISERS"
    r"|ASSOCIATES|LLLP|PLC|AG|SA|GMBH)(?![A-Z0-9])", re.I
)


def extract_xml(submission_text: str) -> str:
    start = submission_text.find("<XML>")
    end = submission_text.find("</XML>", start)
    if start < 0 or end < 0:
        raise ValueError("신고서에 <XML> 블록이 없음")
    return submission_text[start + len("<XML>"):end].strip()


def filing_url(issuer_cik: str, accession: str) -> str:
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(issuer_cik)}/"
        f"{accession.replace('-', '')}/{accession}-index.htm"
    )


def _t(el, path: str) -> str:
    if el is None:
        return ""
    found = el.find(path)
    return (found.text or "").strip() if found is not None else ""


def _b(el, path: str) -> bool:
    return _t(el, path).lower() in ("1", "true")


def _f(el, path: str) -> float | None:
    try:
        return float(_t(el, path))
    except ValueError:
        return None


def _cik(text: str) -> str:
    return str(int(text)) if text.isdigit() else text


def parse_form4(xml_text: str, accession: str, filed: date) -> list[dict]:
    root = ET.fromstring(xml_text)
    issuer = root.find("issuer")
    issuer_cik = _cik(_t(issuer, "issuerCik"))
    owners = []
    for ro in root.findall("reportingOwner"):
        rel = ro.find("reportingOwnerRelationship")
        owners.append({
            "cik": _cik(_t(ro, "reportingOwnerId/rptOwnerCik")),
            "is_director": _b(rel, "isDirector"),
            "is_officer": _b(rel, "isOfficer"),
            "is_ten_pct": _b(rel, "isTenPercentOwner"),
            "title": _t(rel, "officerTitle"),
            "is_entity": bool(ENTITY_RE.search(_t(ro, "reportingOwnerId/rptOwnerName"))),
        })
    notes = {fn.get("id"): (fn.text or "") for fn in root.findall("footnotes/footnote")}
    base = {
        "accession": accession,
        "form": _t(root, "documentType") or "4",
        "filed": filed.isoformat(),
        "issuer_cik": issuer_cik,
        "issuer_name": _t(issuer, "issuerName"),
        "ticker": _t(issuer, "issuerTradingSymbol").upper(),
        "owners": owners,
        "plan": _b(root, "aff10b5One"),
        "url": filing_url(issuer_cik, accession),
    }
    records = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _t(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        ids = {f.get("id") for f in tx.iter("footnoteId")}
        records.append({
            **base,
            "code": code,
            "date": _t(tx, "transactionDate/value")[:10],
            "shares": _f(tx, "transactionAmounts/transactionShares/value") or 0.0,
            "price": _f(tx, "transactionAmounts/transactionPricePerShare/value") or 0.0,
            "after": _f(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
            "direct": _t(tx, "ownershipNature/directOrIndirectOwnership/value") or "D",
            "offering": any(OFFERING_RE.search(notes.get(i, "")) for i in ids),
        })
    return records
