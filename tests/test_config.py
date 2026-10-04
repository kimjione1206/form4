from form4 import config


def test_thresholds_match_spec():
    assert config.WINDOW_DAYS == 60
    assert config.MIN_PERSON_USD == 10_000
    assert config.MIN_PEOPLE == 3
    assert config.REQS_PER_SEC < 10
    assert "추천" in config.FORBIDDEN_WORDS
    assert {"손절", "고점", "경고"} <= set(config.FORBIDDEN_WORDS)
    assert "form4@jmheo.com" in config.USER_AGENT
