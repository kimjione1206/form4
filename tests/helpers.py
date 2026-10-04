"""테스트용 가짜 Form 4 XML과 거래 줄을 만드는 도우미 (실제 SEC 스키마 X0609 모양)."""


def form4_xml(issuer_cik="1000697", ticker="WAT", owners=None, txs=None, plan=False,
              footnotes=None, doc_type="4", deriv_txs=None):
    owners = owners or [{"cik": "111", "director": True}]
    txs = txs or [{"code": "P", "date": "2026-09-30", "shares": 100, "price": 50, "after": 1000}]
    owner_xml = ""
    for o in owners:
        rel = ""
        if o.get("director"):
            rel += "<isDirector>1</isDirector>"
        if o.get("officer"):
            rel += f"<isOfficer>true</isOfficer><officerTitle>{o.get('title', '')}</officerTitle>"
        if o.get("ten_pct"):
            rel += "<isTenPercentOwner>1</isTenPercentOwner>"
        owner_xml += (
            f"<reportingOwner><reportingOwnerId><rptOwnerCik>{int(o['cik']):010d}</rptOwnerCik>"
            f"<rptOwnerName>{o.get('name', 'SECRET NAME')}</rptOwnerName></reportingOwnerId>"
            f"<reportingOwnerRelationship>{rel}</reportingOwnerRelationship></reportingOwner>"
        )
    tx_xml = ""
    for t in txs:
        fn = "".join(f'<footnoteId id="{f}"/>' for f in t.get("footnotes", []))
        price_fn = "".join(f'<footnoteId id="{f}"/>' for f in t.get("price_footnotes", []))
        after_fn = "".join(f'<footnoteId id="{f}"/>' for f in t.get("after_footnotes", []))
        title_fn = "".join(f'<footnoteId id="{f}"/>' for f in t.get("title_footnotes", []))
        after = (
            f"<postTransactionAmounts><sharesOwnedFollowingTransaction><value>{t['after']}</value>"
            f"{after_fn}</sharesOwnedFollowingTransaction></postTransactionAmounts>"
            if t.get("after") is not None else ""
        )
        tx_xml += (
            f"<nonDerivativeTransaction><securityTitle><value>Common Stock</value>{title_fn}</securityTitle>"
            f"<transactionDate><value>{t['date']}</value></transactionDate>"
            f"<transactionCoding><transactionFormType>4</transactionFormType>"
            f"<transactionCode>{t['code']}</transactionCode></transactionCoding>"
            f"<transactionAmounts><transactionShares><value>{t['shares']}</value>{fn}</transactionShares>"
            f"<transactionPricePerShare><value>{t['price']}</value>{price_fn}</transactionPricePerShare>"
            f"<transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>"
            f"</transactionAmounts>{after}"
            f"<ownershipNature><directOrIndirectOwnership><value>{t.get('direct', 'D')}</value>"
            f"</directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction>"
        )
    deriv_xml = "".join(
        f"<derivativeTransaction><securityTitle><value>Stock Option</value></securityTitle>"
        f"<transactionDate><value>{t['date']}</value></transactionDate>"
        f"<transactionCoding><transactionFormType>4</transactionFormType>"
        f"<transactionCode>{t['code']}</transactionCode></transactionCoding></derivativeTransaction>"
        for t in (deriv_txs or []))
    notes = "".join(f'<footnote id="{k}">{v}</footnote>' for k, v in (footnotes or {}).items())
    return (
        '<?xml version="1.0"?><ownershipDocument><schemaVersion>X0609</schemaVersion>'
        f"<documentType>{doc_type}</documentType>"
        f"<issuer><issuerCik>{int(issuer_cik):010d}</issuerCik><issuerName>EXAMPLE CORP</issuerName>"
        f"<issuerTradingSymbol>{ticker}</issuerTradingSymbol></issuer>"
        f"{owner_xml}<aff10b5One>{1 if plan else 0}</aff10b5One>"
        f"<nonDerivativeTable>{tx_xml}</nonDerivativeTable>"
        f"<derivativeTable>{deriv_xml}</derivativeTable>"
        f"<footnotes>{notes}</footnotes></ownershipDocument>"
    )


def submission(xml):
    return f"<SEC-DOCUMENT>\n<DOCUMENT>\n<TYPE>4\n<TEXT>\n<XML>\n{xml}\n</XML>\n</TEXT>\n</DOCUMENT>\n"


def make_rec(accession="A1", issuer="900", owners=None, code="P", date="2026-09-30",
             shares=1000.0, price=20.0, after=5000.0, filed=None, form="4", plan=False,
             direct="D", offering=False, drip=False, ticker="EXM", name="EXAMPLE CORP",
             exercise=False):
    owners = owners or [{"cik": "1", "is_director": True, "is_officer": False,
                         "is_ten_pct": False, "title": ""}]
    return {
        "accession": accession, "form": form, "filed": filed or date,
        "issuer_cik": issuer, "issuer_name": name, "ticker": ticker,
        "owners": owners, "plan": plan, "url": f"https://www.sec.gov/{accession}",
        "code": code, "date": date, "shares": shares, "price": price,
        "after": after, "direct": direct, "offering": offering, "drip": drip,
        "exercise": exercise,
    }


def director(cik):
    return {"cik": cik, "is_director": True, "is_officer": False, "is_ten_pct": False, "title": ""}


def entity_director(cik):
    return {"cik": cik, "is_director": True, "is_officer": False, "is_ten_pct": False, "title": "",
            "is_entity": True}


def officer(cik, title):
    return {"cik": cik, "is_director": False, "is_officer": True, "is_ten_pct": False, "title": title}


def fund(cik):
    return {"cik": cik, "is_director": False, "is_officer": False, "is_ten_pct": True, "title": ""}
