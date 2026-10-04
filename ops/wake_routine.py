"""daily 실패 시 Claude 루틴을 깨운다. 설정이 없으면 조용히 끝낸다."""

import json
import os
import sys
import urllib.request
from pathlib import Path


def build_body(run_url: str, log_path: Path) -> dict:
    tail = log_path.read_text()[-3000:] if log_path.exists() else "로그 없음"
    return {"text": f"daily 실패: {run_url}\n{tail}"}


def main() -> int:
    url, token = os.environ.get("ROUTINE_FIRE_URL"), os.environ.get("ROUTINE_TOKEN")
    if not url or not token:
        print("루틴 설정 없음, 건너뜀")
        return 0
    body = build_body(os.environ.get("RUN_URL", ""), Path(sys.argv[1]))
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.status, r.read().decode()[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
