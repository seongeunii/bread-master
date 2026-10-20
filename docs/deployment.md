# 공개 데모 배포

이 저장소는 Render 무료 Docker 웹 서비스용 render.yaml과 Dockerfile을 제공합니다.
React를 빌드한 뒤 FastAPI가 화면과 /api를 함께 제공하므로 별도 프론트엔드 서버와 CORS 설정이 필요하지 않습니다.

## 사용자 계정 준비

1. https://dashboard.render.com/register 에서 GitHub로 가입합니다.
2. 약관 동의·이메일 인증은 계정 소유자가 직접 완료합니다.
3. GitHub 접근 권한을 선택할 수 있으면 bread-master 저장소만 연결합니다.
4. 아래 배포 링크를 열고 main 브랜치의 Blueprint를 적용합니다.

https://render.com/deploy?repo=https://github.com/seongeunii/bread-master&branch=main

서비스 설정에서 아래 값을 확인합니다.

| 설정 | 값 |
| --- | --- |
| 저장소 | seongeunii/bread-master |
| 브랜치 | main |
| Runtime | Docker |
| Plan | Free |
| Dockerfile | ./Dockerfile |
| Health Check | /api/v1/health |
| DB | /tmp/bread-master/demo.db |
| BREAD_DEMO | 1 |

render.yaml이 위 설정을 선언합니다. Free 외의 유료 플랜·유료 디스크·데이터베이스를 선택하지 않습니다.
서비스 이름 충돌 시 이름만 변경할 수 있습니다. 실제 공개 URL은 Render가 배포 완료 후 표시하는 주소이며, 미리 임의로 정하지 않습니다.

## 완료 확인

Render가 Live를 표시한 뒤 표시된 URL을 브라우저에서 엽니다.
- /api/v1/health가 status=ok, data=demo를 반환
- 상품 도감에 POS 카테고리가 표시
- 상품명 퀴즈 2단계의 양방향 연습 출제
- POS 여러 상품 등록·삭제·결제 채점
- 새 재고 연습에서 수정·등록·카테고리 저장

최종 URL을 채팅에 알려주면 외부 응답 검증과 README 데모 링크 반영을 이어서 진행할 수 있습니다.
배포 완료를 확인하기 전까지 README에 성공한 데모 주소를 표시하지 않습니다.

## 무료 데모의 한계

Render 무료 서비스는 비활성 상태에서 중지될 수 있어 첫 접속이 느릴 수 있습니다.
로컬 파일은 영구 저장소가 아니며 재배포·중지 등으로 사라질 수 있습니다.
따라서 회원 정보나 장기 학습 기록을 저장하는 정식 서비스 용도로 사용하지 않습니다.
참고: https://render.com/docs/free

서버 재시작 때 상품은 보관된 JSON으로 다시 등록합니다. 로컬 개발 DB는 Docker에 포함하지 않습니다.
데모 쓰기 API는 한 인스턴스 전체에 분당 300회 상한을 두며 초과 시 429를 반환합니다.
기록 수는 주기적으로 질문 2,000개 / 배달·POS 주문 500개 / 재고 세션 100개를 남기도록 정리합니다.
이 한도를 넘은 오래된 연습 링크는 없어질 수 있습니다. 개인 계정이나 개인정보를 수집하지 않습니다.
이 제한은 소규모 체험용이며 대규모 운영을 위한 트래픽 방어를 대체하지 않습니다.

## 배포 이미지 로컬 검증

Docker가 설치된 환경에서 프로젝트 루트 기준:

```sh
docker build -t bread-master-demo .
docker run --rm -p 8000:8000 bread-master-demo
```

http://127.0.0.1:8000 에서 프론트엔드와 API를 함께 확인합니다.
GitHub Actions도 같은 이미지의 빌드·초기 데이터·화면·상품명 출제를 검사합니다.

일반 로컬 개발은 기존 frontend Vite / backend uvicorn 방식을 그대로 사용합니다.
BREAD_DEMO=1은 별도 BREAD_DB_PATH가 있을 때만 시작하도록 제한합니다.
