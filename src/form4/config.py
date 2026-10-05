"""사이트 전체가 쓰는 기준값. 숫자를 바꿀 때는 이 파일만 고친다."""

USER_AGENT = "form4.jmheo.com form4@jmheo.com"
REQS_PER_SEC = 8

WINDOW_DAYS = 60
MIN_PERSON_USD = 10_000
MIN_PEOPLE = 3
SAME_DAY_TOLERANCE = 1.2
BULK_MIN_PEOPLE = 10  # 같은 거래일에 이만큼 이상이 사면 '하루 N명 일괄 매수' 꼬리표
MAX_FAIL_RATIO = 0.05
MAX_DAILY_DAYS = 5  # daily 한 번에 따라잡는 최대 영업일 수
MAX_PRICE_PER_SHARE = 20_000  # 주당 가격이 이보다 크면 신고서 원문 오류로 보고 계산에서 뺀다
PRICE_CHECK_EXEMPT = {"BRK.A"}  # 실제로 주당 2만 달러가 넘는 종목
PLACEHOLDER_TICKERS = {"", "NONE", "N/A"}  # 종목 코드 칸에 코드 대신 적힌 값

FORBIDDEN_WORDS = ("주목", "급등", "신호", "기회", "유망", "추천", "성장", "손절", "고점", "경고")

# 사이트 이름: 바꿀 때는 이 두 줄만 고친다(페이지·공유 카드가 모두 여기서 가져감)
SITE_NAME = "미국 임원 거래 정리"
SITE_TAGLINE = "내부자 거래 공시(Form 4) 한국어 정리"

# 기준 페이지 '기준 개정 이력'(최근 것이 위)
CRITERIA_HISTORY = [
    ("2026-10-05", "매도 목록 추가(매수와 같은 기준) · '하루 N명 일괄 매수/매도' 꼬리표 · "
                   "'같은 날 여러 명 매수'를 접수일이 아닌 거래일 기준으로"),
    ("2026-10-04", "사이트 개설 · 배당 재투자·증자 참여·종목 코드 없는 회사 제외 · "
                   "주당 2만 달러 초과 가격은 원문 오류로 제외(BRK.A 예외)"),
]

REPO_URL = "https://github.com/kimjione1206/form4"
SITE_URL = "https://form4.jmheo.com"

# 네이버 서치어드바이저 소유 확인(공개 값, 페이지 소스에 그대로 보임)
NAVER_SITE_VERIFICATION = "76ff0971f874a151b2def597c7325102fc0b6f7d"
