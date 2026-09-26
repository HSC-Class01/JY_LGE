# LG전자 OpenDART 재무 분석 에이전트

[![🔗 대시보드 바로가기](https://img.shields.io/badge/%F0%9F%94%97-%EB%8C%80%EC%8B%9C%EB%B3%B4%EB%93%9C%20%EB%B0%94%EB%A1%9C%EA%B0%80%EA%B8%B0-a50034?style=for-the-badge)](https://hsc-class01.github.io/JY_LGE/)

LG전자(종목코드 `066570`, DART 고유번호 `00401731`)의 2010년 이후 정기공시와 연결 재무제표를 수집하고, 주요 재무비율을 계산해 대시보드로 보여주는 프로젝트입니다.

## 제공 기능

- 2010년 이후 사업보고서 목록·원문 ZIP·XBRL 원본을 누적 보관
- OpenDART 전체계정 API가 제공하는 연결 재무수치를 분기·반기·연간으로 정규화
- 2010~2014년은 사업보고서 XBRL 원본에서 연간 계정을 보완 추출하고, 매핑 불가 항목은 경고 파일에 명시
- 수익성, 성장성, 안정성, 활동성, 현금흐름 지표 21개 계산
- 매월 1일 09:00 KST 자동 갱신 및 GitHub Pages 재배포
- GitHub Pages에서 바로 열리는 반응형 재무 대시보드 제공

## 처음 설정하기

1. [OpenDART](https://opendart.fss.or.kr/)에서 40자리 API 인증키를 발급합니다.
2. ZIP을 풀고 PowerShell에서 `./install_github_workflow.ps1`을 실행합니다. 배포 ZIP에는 숨김 폴더가 없으므로 이 스크립트가 `github-workflows`의 파일을 GitHub 표준 위치인 `.github/workflows`로 복사합니다.
3. 준비된 저장소 [`HSC-Class01/JY_LGE`](https://github.com/HSC-Class01/JY_LGE)에 이 폴더의 내용을 업로드합니다. GitHub CLI를 사용한다면 `./publish_to_github.ps1`로 푸시와 About 링크 설정을 한 번에 할 수 있습니다.
4. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 이름을 `DART_API_KEY`로 지정하고 인증키를 입력합니다.
5. **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 선택합니다.
6. **Actions → Update OpenDART data and deploy dashboard → Run workflow**를 한 번 실행합니다.

상세한 키 입력 방법은 `API_KEY_SETUP.txt`에 있습니다. 인증키는 저장소 파일이나 ZIP에 포함하지 마세요.

## GitHub 링크 설정

- README 최상단 배지는 GitHub Pages 대시보드로 연결됩니다.
- 저장소 오른쪽 **About → ⚙ → Website**에 대시보드 주소를 입력합니다.
- 대시보드 주소: `https://hsc-class01.github.io/JY_LGE/`
- `publish_to_github.ps1`을 이용하면 `gh repo edit --homepage`가 이 설정을 자동 적용합니다.
- GitHub 저장소: `https://github.com/HSC-Class01/JY_LGE`

## 로컬 실행

```powershell
Copy-Item env.example.txt .env
# .env의 DART_API_KEY= 뒤에 키 입력
python scripts/fetch_opendart.py --start-year 2010
python scripts/analyze.py
python scripts/build_site.py
python -m unittest discover -s tests -v
python -m http.server 8000 -d dist
```

브라우저에서 `http://localhost:8000`을 엽니다.

## 주요 파일

- `config/accounts.json`: 수집할 계정명과 XBRL 계정 ID
- `data/financial_summary.csv`: 정규화 재무수치
- `data/ratios.csv`: 계산된 재무비율
- `data/dashboard.json`: 웹 대시보드 분석용 통합 데이터
- `data/raw/`: OpenDART 전체 재무제표 API 응답
- `data/xbrl/`: 사업보고서 XBRL 원본 ZIP
- `reports/source/`: DART 사업보고서 원문 ZIP
- `github-workflows/update-and-deploy.yml`: 숨김 파일 없는 ZIP용 Actions 템플릿

## 데이터 해석 주의

OpenDART의 전체계정 데이터는 IFRS XBRL 제출 자료를 기반으로 하므로 오래된 연도는 일부 계정이 없거나 명칭이 다를 수 있습니다. 누락·매핑 경고는 `data/fetch_warnings.json`에 남습니다. 분기·반기 손익과 현금흐름은 누적 수치일 수 있으므로 같은 보고서 유형의 전년 동기끼리 비교하세요. 본 프로젝트는 정보 제공용이며 투자 권유가 아닙니다.
