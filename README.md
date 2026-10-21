# AI 주식 도우미



초보 투자자가 주가 데이터와 추세를 이해하도록 돕는 교육용 프로젝트입니다.



\## 1. 중요 안내



`data/stock\_prices.csv`의 주가 숫자는 실제 시장 가격이 아닌 \*\*교육용 시뮬레이션 데이터\*\*입니다.   
실제 투자 판단이나 실제 종목 가격으로 사용하지 마세요.



\## 2. Python 환경 확인



PowerShell에서 Python 버전을 확인합니다.



```powershell

python --version

```



Python 3.10 이상을 권장합니다.



\## 3. 가상환경 및 패키지 설치



프로젝트 폴더에서 실행합니다.



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

python -m pip install -r requirements.txt

```



가상환경 활성화가 차단되면 가상환경의 Python을 직접 사용할 수 있습니다.



```powershell

.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt

```



\## 4. 서버 실행



프로젝트 폴더에서 실행합니다.



```powershell

python -m uvicorn app.main:app --reload

```



서버가 실행 중인 터미널은 닫지 마세요.



\## 5. 브라우저에서 확인



\- 메인 화면: http://127.0.0.1:8000/

\- API 문서: http://127.0.0.1:8000/docs

\- 서버 상태: http://127.0.0.1:8000/api/health

\- 데이터 요약: http://127.0.0.1:8000/api/data/summary

\- 샘플 데이터: http://127.0.0.1:8000/api/data



\## 6. 현재 구현된 기능



\- 주가 데이터 조회 및 추가

\- 데이터 수정 및 삭제

\- 데이터 요약 및 서버 상태 확인

\- 주가 그래프와 기간별 추세 분석

\- 테스트 환경 및 실제용 백엔드 주소 설정

\- 연결 점검과 오류 안내

\- 브라우저 수준의 자동 점검 및 사용자 체크리스트



\## 7. API 목록



\- `GET /api/data` — 데이터 조회

\- `POST /api/data` — 데이터 추가

\- `PUT /api/data/{item\_id}` — 데이터 수정

\- `DELETE /api/data/{item\_id}` — 데이터 삭제

\- `GET /api/data/summary` — 데이터 요약

\- `GET /api/health` — 서버 상태 확인



\## 8. 현재 한계와 향후 작업



\- 데이터 추가·수정·삭제 결과는 현재 서버 메모리에 저장되며, 서버 재시작 시 초기화됩니다.

\- Firestore, OpenAI 채팅 API, 실시간 주가 API는 아직 실제 연동이 완료되지 않았습니다.

\- 패키지가 `requirements.txt`에 등록되어 있어도 해당 기능의 연동이 완료된 것은 아닙니다.

\- 브라우저는 Python 설치 여부, 운영체제 설정 및 로컬 패키지를 직접 확인하거나 변경할 수 없습니다.  
관련 항목은 사용자 체크리스트로 안내합니다.

\- 실제 서비스 배포 전에는 CORS 허용 출처와 인증·권한 등 보안 설정을 점검해야 합니다.



\## 9. 보안 주의사항



\- 실제 API 키는 `.env` 또는 배포 플랫폼의 환경변수로 관리합니다.

\- `.env.example`에는 실제 비밀값을 입력하지 않습니다.

\- Firebase 서비스 계정 키 파일을 Git 저장소나 프런트엔드에 올리지 않습니다.

\- 실제 서비스에 연결하기 전에는 데이터 출처와 정확성을 확인합니다.

