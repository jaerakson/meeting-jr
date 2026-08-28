---
name: meeting-jr-dev
description: Meeting Junior 회의록 자동화 앱 개발 오케스트레이터. "개발 시작", "만들어줘", "구현해줘", "개발해줘", "이어서 개발", "다시 실행", "재개", "수정해줘", "프론트만 다시" 등 코드 작업 요청 시 반드시 이 스킬을 사용한다. DEVGUIDE.md를 기준 문서로 삼아 director, product-manager, backend-dev, frontend-dev, ai-engineer, qa-engineer 에이전트 팀을 구성하여 전체 앱을 개발한다.
---

# Meeting Junior 개발 오케스트레이터

## 팀 구조

```
팀리드 (오케스트레이터) — 상황 판단 + 소환 + 코드리뷰 + 머지
  ├── director (분석 + 코디네이션 + 검수)
  ├── product-manager (brainstorming + 기획)
  ├── backend-dev (백엔드 수정)
  ├── frontend-dev (프론트엔드 수정)
  ├── ai-engineer (AI/오디오 파이프라인 수정)
  └── qa-engineer (TDD 테스트 작성 + 검증)
```

## 역할 정의

| 역할 | 담당 | 코드 수정 |
|------|------|----------|
| **팀리드** | 상황 판단, 에이전트 소환, 코드리뷰 스킬 실행, PR 머지 | ❌ |
| **director** | 코드 분석, 팀원 간 코디네이션(SendMessage), 결과 검수 | ❌ |
| **product-manager** | `superpowers:brainstorming` → 기획/명세 작성 | ❌ |
| **backend-dev** | 백엔드 코드 수정 | ✅ |
| **frontend-dev** | 프론트엔드 코드 수정 | ✅ |
| **ai-engineer** | AI/오디오 파이프라인 수정 | ✅ |
| **qa-engineer** | 테스트 케이스 작성(TDD) + 검증 | ✅ |

## 시스템 제약

- **teammate는 다른 teammate를 소환할 수 없다** (flat 구조)
- 소환은 **팀리드만** 가능 (`team_name` + `name` 필수 → 별도 창)
- teammate끼리는 **SendMessage로 직접 소통** 가능

## 팀리드 상황 판단 기준

| 사용자 요청 | 팀리드 판단 | 첫 소환 |
|------------|-----------|--------|
| "기획해" / "다음 기능 찾아" | 기획 필요 | → product-manager |
| "버그 고쳐" / "수정해" | 분석 필요 | → director |
| "기능 만들어" / "구현해" | 분석 + 기획 + 구현 | → director (필요 시 PM 요청) |

---

## 프로세스 A: 새 기능 개발

### Phase 1: 기획 (사용자 승인 필요)
```
1. 팀리드: TeamCreate + product-manager 소환
2. product-manager: superpowers:brainstorming → 기획안 작성
3. product-manager → 팀리드: 기획안 보고
4. 팀리드 → 사용자: 기획안 요약 전달
5. 사용자: 승인 / 수정 요청
```

### Phase 2: 분석 (승인 후 자동)
```
6. 팀리드: director 소환 → 기획안 전달
7. director: 코드 분석 → 수정 범위 확정
8. director → 팀리드: "qa-engineer + developer 필요" 요청
```

### Phase 3: TDD + 개발 (자동)
```
9.  팀리드: qa-engineer 소환
10. 팀리드: developer 소환
11. 팀리드 → director: "팀원 소환 완료, 알아서 진행해"
12. director ↔ qa-engineer: 테스트 케이스 작성 (구현 전)
13. director ↔ developer: "이 테스트 통과시켜"
14. director ↔ qa-engineer: 재검증
15. director: PR 생성 → 팀리드에게 보고
```

### Phase 4: 코드리뷰 + 머지 (팀리드)
```
16. 팀리드: /code-review:code-review 실행
17. 이슈 있으면 → director에게 수정 지시 → 재리뷰
18. 통과 → gh pr merge --squash --delete-branch
19. 브랜치 정리 + PROGRESS.md 업데이트
```

---

## 프로세스 B: 버그 수정

> 기획 단계 없이 바로 분석 → 개발

```
1. 팀리드: TeamCreate + director 소환
2. director: 분석 → "qa-engineer + developer 필요" 요청
3. 팀리드: qa-engineer + developer 소환
4. 팀리드 → director: "알아서 진행해"
5. director ↔ qa-engineer: 테스트 케이스 작성
6. director ↔ developer: 구현
7. director ↔ qa-engineer: 재검증
8. director: PR 생성 → 팀리드 보고
9. 팀리드: 코드리뷰 + 머지
```

---

## 소환 규칙

```python
# 올바른 소환 (별도 창 O)
Agent(
  description="Backend: 작업 설명",
  subagent_type="backend-dev",
  team_name="<현재 팀 이름>",
  name="backend-dev",
  prompt="구체적 작업 지시..."
)

# 잘못된 소환 (별도 창 X)
Agent(
  subagent_type="backend-dev",
  run_in_background=true,  # ← 별도 창 안 뜸
  prompt="..."
)
```

## 보고 체계

```
개발 중: developer → director → (자체 해결)
완료 시: director → 팀리드 → (코드리뷰/머지)
기획 승인: product-manager → 팀리드 → 사용자
최종 결과: 팀리드 → 사용자
```

## 코드리뷰 (머지 전 필수)

> ⚠️ 생략 절대 금지

팀리드가 `/code-review:code-review` 스킬 실행:
- Critical/High 이슈 → director에게 수정 지시 → 재리뷰
- 통과 → `gh pr merge --squash --delete-branch`

머지 후 브랜치 정리:
```bash
git checkout main && git pull
git branch | grep -v '^\* main' | xargs git branch -D
git remote prune origin
```

## 운영 규칙 (세션 52~55 실전에서 정착)

> 아래는 실제로 사고가 나서 만든 규칙이다. 배경은 `docs/ai_analysis/20260829_업무_처리_방식.md` 참조.

### 커밋 — 유실 방지
- **작업 단위마다 즉시 커밋한다.** 완성될 때까지 미루지 않는다.
- 사용자가 창을 닫거나 세션 한도에 걸려 팀이 죽은 사고가 2회 있었다. 미커밋 작업이 깨진 중간 상태로 남았다.
- 중단 시 팀리드가 WIP 커밋으로 먼저 보호한 뒤 새 팀을 구성한다.

### 코드 프리즈
- **director 가 PR 생성을 팀리드에게 보고하는 시점이 코드 프리즈다.**
- 이후 추가 푸시 금지. 리뷰 결과를 받고 나서 한 번에 수정한다.
- 리뷰 도중 커밋이 움직여 리뷰를 처음부터 다시 돌린 사고가 있었다(PR #78).

### 리뷰 강도 조절
- `/code-review:code-review` 는 한 라운드에 에이전트 13개를 쓴다(라운드당 70만~100만 토큰).
- **전체 프로토콜은 큰 기능 PR 에만 적용한다.**
- 작은 수정과 재리뷰는 **팀리드가 직접 diff 를 읽고 테스트를 돌려** 검증한다.
- 같은 부류 이슈가 3회 이상 반복되면 패치를 멈추고 **설계 안건으로 전환**한다.

### 테스트 — 통과해도 안 되는 것들
테스트 200개가 통과한 상태에서 리뷰가 확정 이슈 20건을 잡은 이력이 있다. 원인은 테스트가 "고친 경로"만 보고 실제 사용자 경로를 지나지 않은 것.

UI 가 개입하는 기능은 다음을 반드시 포함한다:
1. 프론트가 **실제로 보내는 payload 형태**로 API 를 호출하는 테스트
2. 사용자가 화면에서 밟는 **경로 전체**를 재현하는 테스트
3. 새 필드가 **NULL 인 기존 데이터**에서 정상 동작하는지

데이터 정합성 코드는 세 축을 점검한다:
- 여러 값이 **하나로 수렴**하는 경우
- **부분 적용**
- 데이터 소스가 **아예 없는** 경우

리뷰에서 나온 재현 케이스는 반드시 테스트로 고정한다.

### 실패 테스트를 만났을 때
**구현을 고쳐 통과시키기 전에 `git log` 로 테스트와 구현 중 어느 쪽이 나중에 바뀌었는지 확인한다.**
- 구현이 회귀 → 구현을 고친다
- 의도적 변경에 테스트가 안 따라옴 → 테스트를 고친다

낡은 테스트에 맞춰 구현을 되돌릴 뻔한 사고가 있었다(PR #67 이 의도적으로 없앤 UX 를 복구할 뻔함).

### 검증 — 팀리드
- 팀원 보고를 그대로 믿지 않고 **직접 diff 를 읽고 테스트를 실행한다.**
- 보고와 달리 구현이 깨져 있거나, 문서 반영 주장이 실제로는 누락된 경우를 이 과정에서 잡았다.
- **"이 상태는 발생하지 않는다"** 는 판단에는 그 상태를 만드는 코드 경로가 없다는 근거를 요구한다. 이 판단이 틀려서 회귀가 머지될 뻔했다.

### 문서
- **DEVGUIDE 섹션 6(API 목록)은 자동 생성이다.** `python3 scripts/gen_api_table.py --write` 를 실행한다. 손으로 고치지 않는다.
- 새 엔드포인트에는 docstring 을 붙인다(설명이 거기서 나온다).
- 확정 결정사항과 **알려진 한계**는 섹션 10에 기록한다. "되는 것"만 적으면 오해가 생긴다(문서-구현 불일치가 5회 연속 지적됨).
- 문서를 쓸 때 코드와 한 줄씩 대조한다.

### 팀 정리
- 작업 종료 즉시 팀원을 정리한다(TaskStop).

---

## 에러 핸들링

- 에이전트 실패: 1회 재시도 후 director가 팀리드에게 보고
- M1 MPS 오류: ai-engineer가 CPU 폴백
- 기술/아키텍처 결정: director 자율 결정 (사용자에게 질문 금지)
