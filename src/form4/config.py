"""사이트 전체가 쓰는 기준값. 숫자를 바꿀 때는 이 파일만 고친다."""

USER_AGENT = "form4.jmheo.com form4@jmheo.com"
REQS_PER_SEC = 8

WINDOW_DAYS = 60
MIN_PERSON_USD = 10_000
MIN_PEOPLE = 3
SAME_DAY_TOLERANCE = 1.2
MAX_FAIL_RATIO = 0.05
MAX_DAILY_DAYS = 5  # daily 한 번에 따라잡는 최대 영업일 수

FORBIDDEN_WORDS = ("주목", "급등", "신호", "기회", "유망", "추천", "성장", "손절", "고점", "경고")

REPO_URL = "https://github.com/kimjione1206/form4"
