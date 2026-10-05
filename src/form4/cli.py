"""명령: daily(매일), backfill(처음 60일 채우기), check-tables(AI 표 검사)."""

import argparse
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from form4 import config, store
from form4.briefing import briefing, snapshot
from form4.fx import current_rate
from form4.index import parse_master_index
from form4.parse import extract_xml, parse_form4
from form4.rank import profiles, sell_list
from form4.render import render_site
from form4.sec import SecClient, SecError, index_url
from form4.tables import (build_todo, check_tables, ensure_company_info, load_json,
                          save_json)

NEW_YORK = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")


def latest_complete_date(now_utc: datetime) -> date:
    """SEC 일일 색인은 미국 동부 22시 무렵 완성 → 지금 기준 '미국 어제'까지가 완전하다."""
    return now_utc.astimezone(NEW_YORK).date() - timedelta(days=1)


def business_days(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def daily_dates(last_date: date | None, as_of: date) -> tuple[list[date], date]:
    """밀린 날은 오래된 쪽부터 최대 MAX_DAILY_DAYS일만. 잘랐으면 기준일도 마지막 처리일로 당긴다."""
    start = last_date + timedelta(days=1) if last_date else as_of
    dates = business_days(start, as_of)
    if len(dates) > config.MAX_DAILY_DAYS:
        dates = dates[:config.MAX_DAILY_DAYS]
        as_of = dates[-1]
    return dates, as_of


def us_federal_holidays(year: int) -> set[date]:
    """그해 실제로 쉬는 미국 연방 공휴일. 날짜 고정 휴일이 토요일이면 금요일, 일요일이면 월요일에 쉰다."""
    def nth(month, weekday, n):
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))

    def observed(d):
        return d + timedelta(days={5: -1, 6: 1}.get(d.weekday(), 0))

    last_may = date(year, 5, 31)
    fixed = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4), date(year, 11, 11),
             date(year, 12, 25), date(year + 1, 1, 1)]
    days = {observed(d) for d in fixed} | {
        nth(1, 0, 3), nth(2, 0, 3), last_may - timedelta(days=last_may.weekday()),
        nth(9, 0, 1), nth(10, 0, 2), nth(11, 3, 4)}
    return {d for d in days if d.year == year}


def collect(dates, client, log):
    new, skipped, total = [], [], 0
    for d in dates:
        if d in us_federal_holidays(d.year):
            # SEC는 없는 색인에 404가 아니라 403을 주므로, 휴일은 요청하지 않고 건너뛴다
            log(f"{d}: 미국 휴일, 건너뜀")
            continue
        text = client.get_text(index_url(d))
        if text is None:
            raise RuntimeError(f"{d}: 일일 색인 없음(게시 지연?)")
        refs = parse_master_index(text)
        failed = 0
        for ref in refs:
            try:
                sub = client.get_text(ref.url)
                if sub is None:
                    raise ValueError("신고서 404")
                new.extend(parse_form4(extract_xml(sub), ref.accession, ref.filed))
            except (ValueError, ET.ParseError, SecError) as e:
                failed += 1
                skipped.append(f"{d} {ref.accession} {e}")
        total += len(refs)
        log(f"{d}: 신고서 {len(refs)}건, 건너뜀 {failed}건")
        if refs and failed / len(refs) > config.MAX_FAIL_RATIO:
            raise RuntimeError(f"{d}: 신고서 {len(refs)}건 중 {failed}건 실패")
    return new, skipped, total


def run(dates, as_of, now_utc, client, fx_client, data_dir: Path, dist_dir: Path, log=print):
    state = load_json(data_dir / "state.json", {"last_date": None, "fx": None})
    records = store.load(data_dir / "transactions.jsonl")
    new, skipped, total = collect(dates, client, log)
    records = store.prune(store.merge(records, new), as_of, config.WINDOW_DAYS)

    titles = load_json(data_dir / "titles.json", {})
    companies = load_json(data_dir / "companies.json", {})
    names = load_json(data_dir / "korean_names.json", {})
    industries = load_json(data_dir / "industries.json", {})
    all_profiles = profiles(records, as_of, titles)
    results = [c for c in all_profiles if c["qualified"]]  # 매수 조건 충족 목록
    sells = sell_list(all_profiles)  # 매도 조건 충족 목록
    listed = results + [c for c in sells if not c["qualified"]]  # 회사 정보·AI 할 일은 두 목록만(겹치지 않게)
    ensure_company_info(listed, companies, client)
    brief = briefing(results, load_json(data_dir / "ranking_prev.json", None))
    sell_brief = briefing(sells, load_json(data_dir / "ranking_prev_sell.json", None), total="sell_total_usd")
    fx = current_rate(fx_client, state.get("fx"))
    meta = {
        "as_of_label": f"{as_of.month}/{as_of.day}", "as_of": as_of.isoformat(),
        "updated": now_utc.astimezone(SEOUL).strftime("%m/%d %H:%M"),
        "fx_rate": fx["rate"], "fx_date": fx["date"], "new_filings": total,
        "beacon_token": os.environ.get("FORM4_BEACON_TOKEN", ""),  # 쿠키 없는 방문 통계(비우면 안 넣음)
    }
    render_site(all_profiles, brief, meta, companies, dist_dir, names, industries, sells, sell_brief)

    store.save(data_dir / "transactions.jsonl", records)
    save_json(data_dir / "companies.json", companies)
    save_json(data_dir / "todo.json", build_todo(listed, companies, titles, all_profiles, names,
                                                            industries))
    save_json(data_dir / "ranking_prev.json", snapshot(results))
    save_json(data_dir / "ranking_prev_sell.json", snapshot(sells))
    (data_dir / "skipped.log").write_text("".join(s + "\n" for s in skipped))
    last = max(filter(None, [state.get("last_date"), *(d.isoformat() for d in dates)]),
               default=as_of.isoformat())
    save_json(data_dir / "state.json", {"last_date": last, "fx": fx})
    log(f"완료: 기준 {as_of}, 조건 충족 {len(results)}곳, 매도 목록 {len(sells)}곳, 거래 줄 {len(records)}개")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="form4")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daily")
    bf = sub.add_parser("backfill")
    bf.add_argument("--start", type=date.fromisoformat)
    bf.add_argument("--end", type=date.fromisoformat)
    sub.add_parser("check-tables")
    args = parser.parse_args(argv)

    data_dir, dist_dir = Path("data"), Path("dist")
    if args.cmd == "check-tables":
        errors = check_tables(load_json(data_dir / "companies.json", {}),
                              load_json(data_dir / "titles.json", {}),
                              load_json(data_dir / "korean_names.json", {}),
                              load_json(data_dir / "industries.json", {}))
        for e in errors:
            print(e)
        return 1 if errors else 0

    now = datetime.now(timezone.utc)
    as_of = latest_complete_date(now)
    if args.cmd == "daily":
        last = load_json(data_dir / "state.json", {}).get("last_date")
        dates, as_of = daily_dates(date.fromisoformat(last) if last else None, as_of)
    else:
        start = args.start or as_of - timedelta(days=config.WINDOW_DAYS - 1)
        dates = business_days(start, args.end or as_of)
    with httpx.Client() as fx_client:
        run(dates, as_of, now, SecClient(), fx_client, data_dir, dist_dir)
    return 0
