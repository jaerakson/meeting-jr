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

## 에러 핸들링

- 에이전트 실패: 1회 재시도 후 director가 팀리드에게 보고
- M1 MPS 오류: ai-engineer가 CPU 폴백
- 기술/아키텍처 결정: director 자율 결정 (사용자에게 질문 금지)
