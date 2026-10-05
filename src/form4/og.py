"""공유 카드(og 이미지) 1200×630 PNG. 글자는 정해진 규칙으로만 만든다(평가하는 말·신호 색·화살표 없음)."""

from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from form4 import config
from form4.render import find_forbidden, fmt_krw_short

W, H, PAD = 1200, 630, 80
TEXT_W = W - 2 * PAD
BG, ACCENT, ICON, WHITE, DIM = "#111827", "#6B8AF0", "#1F3A8A", "#FFFFFF", "#A9B4C6"
TITLE_SIZES = (72, 64, 56, 48)  # 한 줄에 들어가는 가장 큰 크기, 안 되면 56·48에서 두 줄
FOOTER = f"무료 · 광고 없음 · 투자 권유 아님 · {config.SITE_URL.removeprefix('https://')}"
DEFAULT_LINES = [config.SITE_TAGLINE, "매일 아침 한국어로 정리"]


@lru_cache
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Form4CardSans-Bold.ttf" if bold else "Form4CardSans-Regular.ttf"
    with as_file(files("form4") / "fonts" / name) as path:
        return ImageFont.truetype(str(path), size)


def counts_line(meta: dict, buy_n: int, sell_n: int) -> str:
    return f"{meta['as_of_label']} 기준 · 매수 목록 {buy_n}곳 · 매도 목록 {sell_n}곳"


def company_lines(c: dict, rate: float, as_of: str) -> list[str]:
    def part(label: str, people: int, usd: float, none: str) -> str:
        if not people:
            return none
        return f"{label} {people}명" + (f" · {fmt_krw_short(usd, rate)} 원" if usd > 0 else "")
    return [part("임원·이사 장내 매수", c["people"], c["total_usd"], "장내 매수 없음"),
            part("장내 매도", c["sale_people"], c["sale_usd"], "장내 매도 없음"),
            f"최근 {config.WINDOW_DAYS}일 · {as_of} 기준"]


def card_title(c: dict, k: str) -> str:
    """한국어 이름이 있고 카드 글꼴(한글 완성형 2,350자)로 다 그려지면 한국어, 아니면 영어 이름."""
    drawable = all(not "가" <= ch <= "힣" or len(ch.encode("euc-kr")) == 2 for ch in k)
    return k if k and drawable else c["name"]


def _ellipsize(text: str, f, width: int) -> str:
    if f.getlength(text) <= width:
        return text
    while text and f.getlength(text.rstrip() + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(text: str, f, width: int) -> list[str]:
    """띄어쓰기에서 줄을 바꾸고, 한 단어가 폭보다 길면 글자에서 바꾼다."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if f.getlength(trial) <= width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = word
        while f.getlength(cur) > width:
            i = next(i for i in range(len(cur), 0, -1) if f.getlength(cur[:i]) <= width or i == 1)
            lines.append(cur[:i])
            cur = cur[i:]
    return lines + [cur]


def fit_title(text: str, width: int) -> tuple[int, list[str]]:
    for size in TITLE_SIZES:
        if font(size, True).getlength(text) <= width:
            return size, [text]
    for size in TITLE_SIZES[2:]:
        lines = _wrap(text, font(size, True), width)
        if len(lines) <= 2:
            return size, lines
    f = font(TITLE_SIZES[-1], True)
    lines = _wrap(text, f, width)
    return TITLE_SIZES[-1], [lines[0], _ellipsize(" ".join(lines[1:]), f, width)]


@lru_cache
def _base() -> Image.Image:
    """모든 카드에 같은 부분: 바탕·왼쪽 위 F4 표시와 사이트 이름·강조 선·바닥 줄."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((PAD, 56, PAD + 52, 108), radius=10, fill=ICON)
    d.text((PAD + 26, 82), "F4", font=font(28, True), fill=WHITE, anchor="mm")
    d.text((PAD + 72, 82), config.SITE_NAME, font=font(28), fill=WHITE, anchor="lm")
    d.rectangle((PAD, 150, PAD + 96, 155), fill=ACCENT)
    d.text((PAD, H - 56), FOOTER, font=font(24), fill=DIM, anchor="ls")
    return im


def draw_card(title: str, lines: list[str], path: Path, ticker: str = "") -> None:
    bad = find_forbidden(" ".join([title, ticker, *lines]))
    if bad:
        raise ValueError(f"{path.name}: 금지어 {bad}")
    im = _base().copy()
    d = ImageDraw.Draw(im)
    size, title_lines = fit_title(title, TEXT_W)
    y = 184
    for s in title_lines:
        d.text((PAD, y), s, font=font(size, True), fill=WHITE, anchor="la")
        y += round(size * 1.25)
    if ticker:
        d.text((PAD, y), ticker, font=font(34, True), fill=DIM, anchor="la")
        y += 52
    y += 16
    for s in lines:
        d.text((PAD, y), s, font=font(32), fill=WHITE, anchor="la")
        y += 48
    path.parent.mkdir(parents=True, exist_ok=True)
    # 64색 팔레트: 글자 가장자리는 그대로이고 파일은 약 1/3(카드 약 700장이 매일 바뀜), 빠른 방식(FASTOCTREE)
    im.quantize(64, method=Image.Quantize.FASTOCTREE).save(path)


def write_cards(out_dir: Path, meta: dict, results: list[dict], sells: list[dict], knames: dict) -> None:
    """기본 카드 /og.png, 첫 화면 /og/home.png, 매도 목록 /og/sell.png, 두 목록에 있는 회사 /og/c/<slug>.png."""
    counts = counts_line(meta, len(results), len(sells))
    draw_card(config.SITE_NAME, DEFAULT_LINES, out_dir / "og.png")
    draw_card(config.SITE_NAME, [counts], out_dir / "og" / "home.png")
    draw_card("임원 매도 목록", [counts], out_dir / "og" / "sell.png")
    for c in {c["slug"]: c for c in results + sells}.values():
        draw_card(card_title(c, knames.get(c["issuer_cik"], "")),
                  company_lines(c, meta["fx_rate"], meta["as_of"]),
                  out_dir / "og" / "c" / f"{c['slug']}.png", ticker=c["ticker"])
