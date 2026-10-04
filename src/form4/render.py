"""정적 HTML 생성. 목록·상세 페이지는 금지어 검사를 통과해야 쓴다."""

import json
import re
import shutil
from datetime import date
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from form4 import config
from form4.briefing import recent
from form4.tables import company_line, korean_name

TAG_RE = re.compile(r"<[^>]+>")
SENTENCE_GAP_RE = re.compile(r"(?<=\.) ")


def fmt_usd(v: float) -> str:
    if round(v / 1e3) >= 1000:
        return f"${v / 1e6:.1f}M"
    if v >= 1e4:
        return f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


def fmt_krw_short(usd: float, rate: float) -> str:
    won = usd * rate
    if round(won / 1e8) >= 10000:
        jo = won / 1e12
        s = f"{jo:.0f}" if jo >= 10 else f"{jo:.1f}".rstrip("0").rstrip(".")
        return f"{s}조"
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


def fmt_price(v: float) -> str:
    """주당 가격. 100달러 이상은 소수점 없이, 1달러 미만은 소수 넷째 자리까지."""
    if v >= 100:
        return f"${v:,.0f}"
    if v >= 1:
        return f"${v:.2f}"
    return f"${v:.4f}"


def fmt_shares(v: float) -> str:
    return f"{v:,.0f}주"


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
    if c["avg_price"]:
        segs.append((f"임원·이사가 산 평균 가격은 주당 약 {fmt_price(c['avg_price'])}예요. ", False))
    if c["top_person"]:
        tp = c["top_person"]
        segs.append((f"가장 많이 산 1명({tp['label']})이 전체 매수 금액의 약 {tp['share']}%를 차지해요. ", False))
    return segs + _sale_segments(c, rate)


def _sale_segments(c: dict, rate: float) -> list[tuple[str, bool]]:
    if c["sale_people"]:
        text = f"같은 기간 임원·이사 {c['sale_people']}명이 {fmt_krw(c['sale_usd'], rate)}어치를 장내 매도했어요."
        if c["sale_usd"] > 0:
            text += " " + _planned_sale_sentence(c)
        return [(text, False)]
    return [("같은 기간 장내 매도 신고는 없어요.", False)]


def _planned_sale_sentence(c: dict) -> str:
    """매도 금액 중 미리 정한 계획(10b5-1) 매도의 비율. 저장된 매도 줄의 계획 표시·금액만 쓴다."""
    planned = sum(r["value"] for r in c["sale_rows"] if "계획 매도" in r["tags"])
    share = planned / c["sale_usd"] * 100
    if share == 0:
        return "미리 정한 계획(10b5-1) 매도 표시는 없어요."
    part = "1% 미만은" if share < 1 else f"약 {round(share)}%는"
    return f"매도 금액 중 {part} 미리 정한 계획(10b5-1)에 따른 매도예요."


def company_description(c: dict, k: str, rate: float) -> str:
    """회사 페이지 검색·공유 미리보기 설명(자르기 전)."""
    buy = f"{fmt_krw_short(c['total_usd'], rate)} 원" if c["total_usd"] > 0 else "없음"
    sale = f"{fmt_krw_short(c['sale_usd'], rate)} 원" if c["sale_usd"] > 0 else "없음"
    return (f"{k or c['name']}({c['ticker']}) 임원·이사 거래, SEC 공시 기준 최근 {config.WINDOW_DAYS}일: "
            f"매수 {c['people']}명·{buy}, 매도 {c['sale_people']}명·{sale}. 매일 아침 한국어로 정리 · 무료 · 광고 없음")


def page_description(text: str, limit: int = 150) -> str:
    """검색·공유 미리보기 설명. 길면 문장 단위로 자르고, 첫 문장부터 길면 글자로 자른다."""
    if len(text) <= limit:
        return text
    out = ""
    for sentence in SENTENCE_GAP_RE.split(text):
        joined = f"{out} {sentence}" if out else sentence
        if len(joined) > limit:
            break
        out = joined
    return out or text[:limit - 1] + "…"


def find_forbidden(html: str) -> list[str]:
    text = TAG_RE.sub(" ", html)
    return [w for w in config.FORBIDDEN_WORDS if w in text]


def _env() -> Environment:
    env = Environment(loader=PackageLoader("form4", "templates"), autoescape=select_autoescape())
    env.filters.update(usd=fmt_usd, krw=fmt_krw, krw_short=fmt_krw_short,
                       increase=fmt_increase, decrease=fmt_decrease, md=fmt_md,
                       price=fmt_price, shares=fmt_shares)
    env.globals["site"] = config.SITE_URL
    env.globals["naver_verification"] = config.NAVER_SITE_VERIFICATION
    return env


def search_index(profiles: list[dict], knames: dict) -> list[dict]:
    return sorted(({"t": c["ticker"], "n": c["name"], "k": knames[c["issuer_cik"]], "s": c["slug"],
                    "q": c["qualified"]} for c in profiles),
                  key=lambda e: (e["t"], e["s"]))


def sitemap(profiles: list[dict], as_of: str) -> str:
    paths = ["/", "/criteria/", "/privacy/"] + [f"/c/{c['slug']}/" for c in profiles]
    urls = "".join(f"<url><loc>{config.SITE_URL}{p}</loc><lastmod>{as_of}</lastmod></url>\n" for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


def render_site(profiles: list[dict], brief: dict, meta: dict, companies: dict, out_dir: Path,
                names: dict | None = None, industries: dict | None = None) -> None:
    """profiles: 회사 페이지를 만들 모든 회사. 그중 qualified 인 것이 첫 화면 목록(순서 그대로).
    names: 종목 코드 → 한국어 회사 이름 표(data/korean_names.json).
    industries: SEC 영어 업종 → 한국어 업종 표(data/industries.json)."""
    env = _env()
    results = [c for c in profiles if c["qualified"]]
    lines = {c["issuer_cik"]: company_line(c["issuer_cik"], companies, industries) for c in profiles}
    knames = {c["issuer_cik"]: korean_name(c["ticker"], names or {}) for c in profiles}
    new_ciks = {c["issuer_cik"] for c in brief["new"]}
    recent_buys = [] if brief["new"] else recent(results, date.fromisoformat(meta["as_of"]))
    checked = {"index.html": env.get_template("index.html").render(
        meta=meta, path="/", brief=brief, results=results, lines=lines, knames=knames, new_ciks=new_ciks,
        recent=recent_buys)}
    for c in profiles:
        summary = summary_segments(c, meta["fx_rate"])
        checked[f"c/{c['slug']}/index.html"] = env.get_template("company.html").render(
            meta=meta, path=f"/c/{c['slug']}/", c=c, k=knames[c["issuer_cik"]], line=lines[c["issuer_cik"]],
            summary=summary,
            description=page_description(company_description(c, knames[c["issuer_cik"]], meta["fx_rate"])))
    for name, html in checked.items():
        bad = find_forbidden(html)
        if bad:
            raise ValueError(f"{name}: 금지어 {bad}")
    pages = dict(checked)
    pages["criteria/index.html"] = env.get_template("criteria.html").render(meta=meta, path="/criteria/", cfg=config)
    pages["privacy/index.html"] = env.get_template("privacy.html").render(meta=meta, path="/privacy/")
    pages["404.html"] = env.get_template("404.html").render(meta=meta)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for name, html in pages.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
    (out_dir / "search.json").write_text(
        json.dumps(search_index(profiles, knames), ensure_ascii=False, separators=(",", ":")))
    (out_dir / "sitemap.xml").write_text(sitemap(profiles, meta["as_of"]))
    (out_dir / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    static = files("form4") / "static"
    for name in ("style.css", "typing.js", "search.js", "share.js", "sort.js"):
        (out_dir / name).write_text((static / name).read_text())
    (out_dir / "og.png").write_bytes((static / "og.png").read_bytes())
