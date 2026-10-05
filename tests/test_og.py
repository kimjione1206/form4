import struct

from form4 import config, og
from form4.render import find_forbidden
from test_render import META, result


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_counts_and_company_lines():
    assert og.counts_line(META, 12, 610) == "10/2 기준 · 매수 목록 12곳 · 매도 목록 610곳"
    assert og.company_lines(result(), 1400.0, "2026-10-02") == [
        "임원·이사 장내 매수 5명 · 34억 원", "장내 매도 없음", "최근 60일 · 2026-10-02 기준"]
    sold = result(people=0, total_usd=0.0, sale_people=4, sale_usd=2_000_000.0)
    assert og.company_lines(sold, 1400.0, "2026-10-02")[:2] == ["장내 매수 없음", "장내 매도 4명 · 28억 원"]
    no_price = result(sale_people=2, sale_usd=0.0)
    assert og.company_lines(no_price, 1400.0, "2026-10-02")[1] == "장내 매도 2명"


def test_card_text_is_neutral():
    texts = [og.FOOTER, og.counts_line(META, 1, 2), *og.company_lines(result(), 1400.0, "2026-10-02"),
             og.DEFAULT_LINES[0], og.DEFAULT_LINES[1]]
    assert not find_forbidden(" ".join(texts))
    assert og.FOOTER == "무료 · 광고 없음 · 투자 권유 아님 · form4.jmheo.com"
    assert og.DEFAULT_LINES == [config.SITE_TAGLINE, "매일 아침 한국어로 정리"]


def test_card_title_prefers_korean_name_the_font_can_draw():
    c = result(name="EXAMPLE CORP")
    assert og.card_title(c, "예시") == "예시"
    assert og.card_title(c, "") == "EXAMPLE CORP"
    assert og.card_title(c, "똠양") == "EXAMPLE CORP"  # '똠'은 카드 글꼴(완성형 2,350자)에 없음


def test_fit_title_shrinks_then_wraps_to_two_lines():
    size, lines = og.fit_title("애플", og.TEXT_W)
    assert size == og.TITLE_SIZES[0] and lines == ["애플"]
    long_en = "INTERNATIONAL FLAVORS & FRAGRANCES HOLDINGS ACQUISITION CORPORATION OF NORTH AMERICA INCORPORATED"
    size, lines = og.fit_title(long_en, og.TEXT_W)
    assert len(lines) == 2 and lines[1].endswith("…")
    assert all(og.font(size, bold=True).getlength(s) <= og.TEXT_W for s in lines)
    nospace = "가" * 60
    size, lines = og.fit_title(nospace, og.TEXT_W)
    assert len(lines) == 2 and all(og.font(size, bold=True).getlength(s) <= og.TEXT_W for s in lines)


def test_write_cards(tmp_path):
    buy = result()
    sell = result(issuer_cik="901", name="SELL CO", ticker="SLL", slug="SLL", qualified=False, sell_qualified=True)
    og.write_cards(tmp_path, META, [buy], [sell], {"900": "예시", "901": ""})
    for p in ["og.png", "og/home.png", "og/sell.png", "og/c/EXM.png", "og/c/SLL.png"]:
        assert png_size(tmp_path / p) == (1200, 630), p
    assert sorted(p.name for p in (tmp_path / "og" / "c").iterdir()) == ["EXM.png", "SLL.png"]


def test_card_rejects_forbidden_words(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="금지어"):
        og.draw_card("ROCKET 급등 CORP", ["x"], tmp_path / "x.png")
