"""사이트 전체가 쓰는 기준값. 숫자를 바꿀 때는 이 파일만 고친다."""

USER_AGENT = "form4.jmheo.com form4@jmheo.com"
REQS_PER_SEC = 8

WINDOW_DAYS = 60
MIN_PERSON_USD = 10_000
MIN_PEOPLE = 3
SAME_DAY_TOLERANCE = 1.2
MAX_FAIL_RATIO = 0.05
MAX_DAILY_DAYS = 5  # daily 한 번에 따라잡는 최대 영업일 수
MAX_PRICE_PER_SHARE = 20_000  # 주당 가격이 이보다 크면 신고서 원문 오류로 보고 계산에서 뺀다
PRICE_CHECK_EXEMPT = {"BRK.A"}  # 실제로 주당 2만 달러가 넘는 종목
PLACEHOLDER_TICKERS = {"", "NONE", "N/A"}  # 종목 코드 칸에 코드 대신 적힌 값

FORBIDDEN_WORDS = ("주목", "급등", "신호", "기회", "유망", "추천", "성장", "손절", "고점", "경고")

REPO_URL = "https://github.com/kimjione1206/form4"
SITE_URL = "https://form4.jmheo.com"

# 네이버 서치어드바이저 소유 확인(공개 값, 페이지 소스에 그대로 보임)
NAVER_SITE_VERIFICATION = "76ff0971f874a151b2def597c7325102fc0b6f7d"
