import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("wake", Path("ops/wake_routine.py"))
wake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wake)


def test_body_has_run_url_and_log_tail(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("x" * 5000 + "마지막 오류")
    body = wake.build_body("https://github.com/run/1", log)
    assert body["text"].startswith("daily 실패: https://github.com/run/1\n")
    assert body["text"].endswith("마지막 오류") and len(body["text"]) < 3200


def test_missing_log(tmp_path):
    assert "로그 없음" in wake.build_body("u", tmp_path / "none.log")["text"]
