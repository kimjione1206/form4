# 공유 카드용 글꼴

공유 카드(og 이미지)를 그릴 때만 쓰는 글꼴이에요. 웹 페이지 글꼴은 그대로 구글 폰트에서 불러와요.

- 원본: IBM Plex Sans KR Regular·Bold (SIL Open Font License 1.1, `OFL.txt`)
  - 받은 곳: https://github.com/google/fonts/tree/main/ofl/ibmplexsanskr (google/fonts 9710da1)
  - 원본 SHA-256: Regular `53750379270312368cf7641901f43a98dd892e3d9d5798cf25cdc245c85c71c0`,
    Bold `9d82a8be5330f6d7b53121262867b402baca672eb69b852928f06d185d357f7d`
- 줄인 방법(약 2.8MB → 약 0.4MB씩): 한글은 KS X 1001 완성형 2,350자만, 그 밖에는 영문·숫자·라틴-1·자주 쓰는
  문장 부호만 남기고 힌팅을 뺐어요. 원본 이름의 'Plex'는 OFL 예약 이름이라 줄인 글꼴의 이름을
  `Form4 Card Sans`로 바꿨어요.
  ```
  pyftsubset IBMPlexSansKR-Regular.ttf --text-file=ks.txt \
    --unicodes="U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-203A,U+2190-2193,U+2212,U+20A9,U+FF5E" \
    --no-hinting --layout-features='kern'
  # ks.txt = 가~힣 중 EUC-KR 2바이트로 적히는 2,350자. 그다음 name 표의 이름(1·3·4·6·16번)을 바꿈
  ```
- 이 2,350자에 없는 한글이 한국어 회사 이름에 있으면 카드에는 영어 이름을 써요(`og.py`).
