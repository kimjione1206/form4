# 운영 설정 순서 (운영자 + Claude)

비밀값(토큰)은 운영자가 직접 입력해요. Claude는 화면 안내와 확인만 해요.

## 1. GitHub 공개 저장소
- `gh repo create kimjione1206/form4 --public --source . --push` (Claude가 운영자 확인 후 실행)

## 2. Cloudflare
1. 대시보드 → 오른쪽 위 프로필 → API 토큰 → 토큰 만들기 → "Cloudflare Workers 편집" 템플릿 → 계정: 운영자 계정, 영역: jmheo.com → 만들기 → 토큰 복사
2. 터미널에서 운영자가 직접:
   ```bash
   gh secret set CLOUDFLARE_API_TOKEN -R kimjione1206/form4
   ```
   (붙여 넣고 Enter)
3. 계정 ID(대시보드 Workers 화면 오른쪽에 있음)도 같은 방법으로:
   ```bash
   gh secret set CLOUDFLARE_ACCOUNT_ID -R kimjione1206/form4
   ```

## 3. 메일 전달 form4@jmheo.com
대시보드 → jmheo.com → 이메일 → 이메일 라우팅 → 시작 → 사용자 지정 주소 `form4` → 대상 운영자 메일 → 받은 확인 메일 승인 → DNS 레코드 자동 추가 승인

## 4. 처음 60일 채우기
GitHub → Actions → backfill → Run workflow 를 두 번(각각 약 1~2시간):
- 1회차: start = 60일 전, end = 31일 전
- 2회차: start = 30일 전, end 비움
- 1회차 실행이 끝난(초록) 것을 확인한 뒤 2회차를 실행하고, 매일 06:07 자동 실행 시각과 겹치지 않게 해요. (같은 대기열에 둘이 들어가면 하나가 취소될 수 있어요.)
(Claude가 `gh workflow run backfill -f start=... -f end=...` 로 대신 실행 가능)

## 5. Claude 루틴
1. https://claude.ai/code/routines → 새 루틴 → 이름 `form4 관리`
2. 지시문: `ops/routine-prompt.md` 의 본문 붙여 넣기, 모델: Sonnet
3. 저장소: kimjione1206/form4
4. 환경: 편집 → 네트워크 접근 "사용자 지정" → 허용 도메인 `sec.gov`, `www.sec.gov`, `data.sec.gov` 추가, "기본 목록 함께 포함" 체크
5. 트리거: 예약 매일 06:37 + API 추가 → 저장 후 URL 복사, 토큰 생성 → 복사
6. 운영자가 직접:
   ```bash
   gh secret set ROUTINE_FIRE_URL -R kimjione1206/form4
   ```
   ```bash
   gh secret set ROUTINE_TOKEN -R kimjione1206/form4
   ```
7. 커넥터는 모두 빼기(이 루틴은 GitHub만 쓴다)

## 6. 공개 전
- 금감원 1332: "광고·후원·회원 없이 무료로 미국 SEC 공시를 정해진 기준으로 정리해 보여 주는 사이트가 유사투자자문업 신고 대상인지" 문의
