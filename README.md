# 빵마스터 · Bread Master

베이커리 신입 근무자를 위한 상품 학습 및 POS 탐색 연습 웹 앱.
현재는 **로컬 개발용 데모**입니다. 모든 상품명·가격·카테고리는 예시이며, 상품 이미지는 예시 일러스트입니다. 실제 POS 및 결제 시스템과 연결하지 않습니다.

## 구성

- `frontend/`: React + TypeScript + Vite + Tailwind CSS
- `backend/app/main.py`: 상품 조회, 문제 출제, 서버 채점 API
- `backend/app/learning.py`: 단계별 출제·점수·상황별 피드백
- `frontend/src/features/learning/`: 단계 선택·라운드·점수 화면
- `backend/app/db.py`: SQLite 연결, 테이블 생성, 예시 데이터
- `backend/tests/`: 필터·채점·중복 답안·유효성 검증
- `.vscode/`: Python 환경, 추천 확장, 실행 작업

현재 상품 도감(검색·카테고리·상세)과 네 단계 학습을 제공합니다.

1. 카테고리: 일러스트를 보고 카테고리 선택
2. 상품명: 일러스트를 보고 유사 이름 그룹의 2~3개 보기에서 선택
3. 배달: 주문 이름만 보고 4개의 일러스트 중 선택 (보기에는 이름 숨김)
4. POS: 일러스트를 보고 카테고리·페이지를 탐색해 상품 등록

각 단계는 독립적으로 선택하며 라운드당 중복 없는 5문제, 정답당 20점, 100점 만점입니다.
서버가 점수와 상황별 피드백을 반환합니다. 라운드 점수는 화면에 합산하며 새로고침·단계 변경 시 초기화됩니다.
오답이면 정답을 표시하고, 최종 결과에는 점수·정답률·헷갈린 상품을 보여줍니다.
유사 이름 그룹은 `products.name_group`에 지정합니다. 실제 데이터 도입 시 직접 검수해야 합니다.
기존 SQLite 데이터는 삭제하지 않고 필요한 컬럼을 추가합니다.

## 실행

Node.js 22.12 이상 또는 24 LTS 권장. Python은 현재 설치된 3.9에서 검증했으며 신규 환경은 3.12 이상 권장.

터미널 1:

```sh
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

터미널 2:

```sh
cd frontend
npm ci
npm run dev
```

웹: http://localhost:5173 · API 문서: http://127.0.0.1:8000/docs
프론트엔드의 `/api` 요청은 Vite가 백엔드로 전달합니다.
SQLite는 `backend/bread.db`에 생성되며 Git에서 제외됩니다.

## VS Code

`bread-master.code-workspace`를 열고 추천 확장을 설치합니다.
`터미널 → 작업 실행`에서 `Bread Master: API`와 `Bread Master: Web`을 각각 실행할 수 있습니다.

## 검증

```sh
cd frontend
npm run build
npm run lint
```

```sh
cd backend
./.venv/bin/python -m pytest -q
```

## Figma

[상품 도감 및 POS 디자인](https://www.figma.com/design/HYUdIHeWPNGj0WaK8CMZr0)
Codex의 Figma MCP 계정 연결을 확인했습니다. VS Code용 `.vscode/mcp.json`도 추가했습니다. VS Code에서 이 파일의 Start를 눌러 별도 Figma OAuth 로그인을 완료해야 합니다. Codex 앱의 연결과 VS Code의 로그인은 별개입니다.

## 다음 단계

1. 계정 정책 확정 및 로그인·관리자 권한 구현
2. 상품 관리와 실제 사진 업로드
3. 사용자별 오답 노트와 학습 통계
4. 배포 및 데이터 백업

답안은 서버에서 채점하고 DB에 저장하지만 현재 사용자별로 분리하지 않습니다.
인증 전에는 실제 사용자·개인정보를 수집하거나 공개 서비스로 배포하지 않습니다.
