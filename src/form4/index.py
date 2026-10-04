"""SEC 일일 색인(master.YYYYMMDD.idx)에서 양식 4 신고서 목록을 뽑는다.

같은 신고서가 회사 CIK와 신고자 CIK 아래 두 번 나오므로 접수번호로 중복을 지운다.
"""

from dataclasses import dataclass
from datetime import date, datetime

FORMS = {"4", "4/A"}


@dataclass(frozen=True)
class FilingRef:
    accession: str
    form: str
    filed: date
    path: str

    @property
    def url(self) -> str:
        return "https://www.sec.gov/Archives/" + self.path


def parse_master_index(text: str) -> list[FilingRef]:
    refs, seen = [], set()
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or parts[2] not in FORMS:
            continue
        path = parts[4].strip()
        accession = path.rsplit("/", 1)[-1].removesuffix(".txt")
        if accession in seen:
            continue
        seen.add(accession)
        filed = datetime.strptime(parts[3], "%Y%m%d").date()
        refs.append(FilingRef(accession, parts[2], filed, path))
    return refs
