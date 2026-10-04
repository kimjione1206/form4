"""정적 HTML 생성. 목록·상세 페이지는 금지어 검사를 통과해야 쓴다."""

import json
import re
import shutil
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from form4 import config
from form4.tables import company_line

TAG_RE = re.compile(r"<[^>]+>")


def fmt_usd(v: float) -> str:
    if round(v / 1e3) >= 1000:
        return f"${v / 1e6:.1f}M"
    if v >= 1e4:
        return f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


def fmt_krw_short(usd: float, rate: float) -> str:
    won = usd * rate
    if round(won / 1e4) >= 10000:
        eok = won / 1e8
        s = f"{eok:.0f}" if eok >= 10 else f"{eok:.1f}".rstrip("0").rstrip(".")
        return f"{s}억"
    return f"{won / 1e4:,.0f}만"


def fmt_krw(usd: float, rate: float) -> str:
    return f"약 {fmt_krw_short(usd, rate)} 원"


def fmt_increase(x) -> str:
    if x is None:
        return "-"
    if x == "new":
        return "신규 보유"
    return f"+{x * 100:.0f}%"


def fmt_decrease(x) -> str:
    if not x:
        return "-"
    if x < 0.01:
        return "\u22121% 미만"
    if x < 1:
        return f"\u2212{min(x * 100, 99):.0f}%"  # 다 판 게 아니면 반올림으로 −100%가 되지 않게
    return "\u2212100%"


def fmt_md(iso: str) -> str:
    _, m, d = iso.split("-")
    return f"{int(m)}/{int(d)}"


def summary_segments(c: dict, rate: float) -> list[tuple[str, bool]]:
    top = c["top"]
    if top is None:
        return [(f"최근 {config.WINDOW_DAYS}일 동안 임원·이사의 장내 매수 신고는 없어요. ", False),
                *_sale_segments(c, rate)]
    segs = [
        (f"최근 {config.WINDOW_DAYS}일 동안 임원·이사 {c['people']}명이 시장에서 직접 "
         f"{fmt_krw(c['total_usd'], rate)}({fmt_usd(c['total_usd'])})어치를 샀어요. 가장 큰 매수는 ",
         False),
        (f"{top['who']}의 {fmt_krw(top['value'], rate)}", True),
    ]
    inc = top["increase"]
    if isinstance(inc, float):
        segs += [("으로, 기존 보유 주식의 ", False), (fmt_increase(inc), True), ("를 늘린 거예요. ", False)]
    elif inc == "new":
        segs.append(("으로, 새로 보유를 시작한 거예요. ", False))
    else:
        segs.append(("이에요. ", False))
    return segs + _sale_segments(c, rate)


def _sale_segments(c: dict, rate: float) -> list[tuple[str, bool]]:
    if c["sale_people"]:
        return [(f"같은 기간 임원·이사 {c['sale_people']}명이 {fmt_krw(c['sale_usd'], rate)}어치를 "
                 "장내 매도했어요.", False)]
    return [("같은 기간 장내 매도 신고는 없어요.", False)]


def find_forbidden(html: str) -> list[str]:
    text = TAG_RE.sub(" ", html)
    return [w for w in config.FORBIDDEN_WORDS if w in text]


def _env() -> Environment:
    env = Environment(loader=PackageLoader("form4", "templates"), autoescape=select_autoescape())
    env.filters.update(usd=fmt_usd, krw=fmt_krw, krw_short=fmt_krw_short,
                       increase=fmt_increase, decrease=fmt_decrease, md=fmt_md)
    return env


def search_index(profiles: list[dict]) -> list[dict]:
    return sorted(({"t": c["ticker"], "n": c["name"], "s": c["slug"], "q": c["qualified"]} for c in profiles),
                  key=lambda e: (e["t"], e["s"]))


def render_site(profiles: list[dict], brief: dict, meta: dict, companies: dict, out_dir: Path) -> None:
    """profiles: 회사 페이지를 만들 모든 회사. 그중 qualified 인 것이 첫 화면 목록(순서 그대로)."""
    env = _env()
    results = [c for c in profiles if c["qualified"]]
    lines = {c["issuer_cik"]: company_line(c["issuer_cik"], companies) for c in profiles}
    new_ciks = {c["issuer_cik"] for c in brief["new"]}
    checked = {"index.html": env.get_template("index.html").render(
        meta=meta, brief=brief, results=results, lines=lines, new_ciks=new_ciks)}
    for c in profiles:
        checked[f"c/{c['slug']}/index.html"] = env.get_template("company.html").render(
            meta=meta, c=c, line=lines[c["issuer_cik"]],
            summary=summary_segments(c, meta["fx_rate"]))
    for name, html in checked.items():
        bad = find_forbidden(html)
        if bad:
            raise ValueError(f"{name}: 금지어 {bad}")
    pages = dict(checked)
    pages["criteria/index.html"] = env.get_template("criteria.html").render(meta=meta, cfg=config)
    pages["404.html"] = env.get_template("404.html").render(meta=meta)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for name, html in pages.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
    (out_dir / "search.json").write_text(
        json.dumps(search_index(profiles), ensure_ascii=False, separators=(",", ":")))
    static = files("form4") / "static"
    for name in ("style.css", "typing.js", "search.js"):
        (out_dir / name).write_text((static / name).read_text())
