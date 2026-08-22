---
name: meeting-jr-dev
description: Meeting Junior 회의록 자동화 앱 개발 오케스트레이터. "개발 시작", "만들어줘", "구현해줘", "개발해줘", "이어서 개발", "다시 실행", "재개", "수정해줘", "프론트만 다시" 등 코드 작업 요청 시 반드시 이 스킬을 사용한다. DEVGUIDE.md를 기준 문서로 삼아 product-manager, director, backend-dev, frontend-dev, ai-engineer, qa-engineer 에이전트 팀을 구성하여 전체 앱을 개발한다.
---

# Meeting Junior 개발 오케스트레이터

## 실행 모드: 에이전트 팀

```
product-manager (기획)
director (총괄+아키텍트)
  ├── backend-dev
  ├── frontend-dev
  ├── ai-engineer
  └── qa-engineer
```

## Phase 0: 컨텍스트 확인

시작 전 기존 작업 상태를 확인한다:
- `app/`, `static/` (또는 `frontend/`) 존재 여부 확인
- **존재 + 부분 수정 요청** → 해당 에이전트만 재호출
- **존재 + 새 지시** → 기존 코드 기반으로 이어서 개발
- **없음** → 신규 개발 시작

## Phase 1: 팀 구성

```
TeamCreate(
  team_name: "meeting-jr-dev-team",
  members: [director, backend-dev, frontend-dev, ai-engineer, qa-engineer]
)
```

`director`에게 지시:
1. `DEVGUIDE.md` 읽기 (최신 요구사항 + 기술 스택 확인)
2. 프로젝트 디렉토리 구조 생성
3. 기본 설정 파일 생성 (requirements.txt, .env.example)

## Phase 2: 병렬 개발

`director`가 동시에 위임:
- `backend-dev` → FastAPI 백엔드 (app/main.py + API 엔드포인트)
- `ai-engineer` → 오디오 파이프라인 + Claude 요약 + Notion 연동

`qa-engineer`는 각 파일 완성 직후 점진적 검증 시작.

## Phase 3: 프론트엔드 개발

백엔드 API 스펙 확정 후:
- `frontend-dev` → 웹 UI (DEVGUIDE.md 섹션 5 기준, 기술 스택은 DEVGUIDE.md 따름)

## Phase 4: 통합 QA

`qa-engineer` 전체 통합 검증:
- API 응답 shape ↔ 프론트 파싱 일치
- 오디오 파이프라인 출력 형식 검증
- UI 상태 전환 검증

## Phase 5: 완료 보고

`director`가 사용자에게:
- 생성된 파일 목록
- 실행 방법
- 환경 설정 안내 (`.env` 작성 방법, HF_TOKEN 발급 등)

## 데이터 전달

| 단계 | 방식 |
|------|------|
| 작업 할당 | TaskCreate + SendMessage |
| 중간 산출물 | 파일 기반 (app/, static/, frontend/) |
| 진행 상황 | SendMessage |
| 최종 보고 | director → 사용자 |

## 에러 핸들링

- 에이전트 실패: 1회 재시도 후 `director`가 사용자에게 보고
- M1 MPS 오류: `ai-engineer`가 CPU 폴백으로 처리
- 기술 스택 결정 필요: `director`가 사용자에게 확인 요청

## 테스트 시나리오

**정상 흐름:**
1. 사용자: "개발 시작해"
2. 팀 구성 → DEVGUIDE.md 확인 → 초기화 → 병렬 개발 → QA → 완료 보고

**부분 재실행:**
1. 사용자: "프론트엔드만 다시 만들어줘"
2. Phase 0에서 기존 코드 확인 → frontend-dev만 재호출
