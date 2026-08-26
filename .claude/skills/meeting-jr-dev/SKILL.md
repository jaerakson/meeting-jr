---
name: meeting-jr-dev
description: Meeting Junior 회의록 자동화 앱 개발 오케스트레이터. "개발 시작", "만들어줘", "구현해줘", "개발해줘", "이어서 개발", "다시 실행", "재개", "수정해줘", "프론트만 다시" 등 코드 작업 요청 시 반드시 이 스킬을 사용한다. DEVGUIDE.md를 기준 문서로 삼아 director, product-manager, backend-dev, frontend-dev, ai-engineer, qa-engineer 에이전트 팀을 구성하여 전체 앱을 개발한다.
---

# Meeting Junior 개발 오케스트레이터

## 실행 모드: 에이전트 팀

```
director (총괄+아키텍트)
  ├── product-manager (기획)
  ├── backend-dev (백엔드)
  ├── frontend-dev (프론트엔드)
  ├── ai-engineer (AI/오디오)
  └── qa-engineer (QA/테스트)
```

### 팀 운영 규칙

- **반드시 TeamCreate로 팀 구성** 후 진행 (별도 창 표시)
- 간단한 작업: director가 필요한 개발자 에이전트 + qa-engineer만 소환
- 복잡한 기능: director → product-manager 기획 지시 → 기획 결과 기반으로 개발자에게 분배
- **공통**: 오케스트레이터가 직접 코드 수정 금지. 개발자 에이전트 → qa-engineer → 코드 리뷰 절차는 항상 유지.

에이전트 역할:
- **director**: 원인 분석 → 작업 설계 → 팀원 소환/분배 → 결과 검수 → 팀리드에게 보고. 코드 직접 수정 금지.
- **product-manager**: `superpowers:brainstorming` 스킬로 아이디어 도출 → 기획/명세 작성 → director에게 전달. 새 기능·아키텍처 변경 시 반드시 소환.
- **backend-dev**: 백엔드 코드 수정
- **frontend-dev**: 프론트엔드 코드 수정
- **ai-engineer**: AI/오디오 파이프라인 수정
- **qa-engineer**: 테스트 작성 및 검증

### 팀원 소환 규칙 (필수)

> ⚠️ **teammate는 다른 teammate를 소환할 수 없다** (시스템 제약: 팀 구조가 flat).
> 팀원 소환은 **팀리드(오케스트레이터)만** 가능하다.

**운영 방식:**
1. 팀리드가 director를 소환 (`team_name` + `name` 필수 → 별도 창)
2. director가 분석 후 **팀리드에게 필요한 팀원 목록을 보고**
3. **팀리드가 직접** 개발자/qa-engineer를 소환 (`team_name` + `name` 필수)
4. 소환된 팀원에게 director가 SendMessage로 작업 지시

```
# 팀리드만 소환 가능 (별도 창 O)
Agent(
  description="Backend: 작업 설명",
  subagent_type="backend-dev",
  team_name="<현재 팀 이름>",
  name="backend-dev",
  prompt="구체적 작업 지시..."
)
```

## Phase 0: 브레인스토밍 (새 기능·아키텍처 변경 시)

새 기능 추가나 아키텍처 변경 요청 시:
1. **`superpowers:brainstorming` 스킬 실행** → 아이디어 도출
2. 도출된 방향을 director에게 전달

단순 버그 수정은 이 단계를 건너뛴다.

## Phase 1: 팀 구성 + Worktree

1. **`superpowers:using-git-worktrees` 스킬로 격리된 작업 공간 확보**
2. `TeamCreate(team_name="<작업명>")`으로 팀 생성
3. `Agent(subagent_type="director", team_name="<팀이름>", name="director")`로 director 소환
4. director에게 작업 내용 전달 (SendMessage)

director가 수행할 일:
1. 원인 분석 (Read/Grep/Glob — 직접 코드 수정 금지)
2. 필요한 팀원을 Agent tool로 소환 (`team_name` + `name` 필수)
3. 팀원에게 SendMessage로 구체적 작업 지시
4. 새 기능 시: product-manager 소환 → `superpowers:brainstorming`으로 기획 → 개발자에게 분배

## Phase 2: 개발

director가 팀원에게 위임:
- **버그 수정**: 해당 개발자 에이전트만 소환
- **새 기능**: product-manager(기획) → 개발자 분배 (필요 시 병렬)
- **백엔드+프론트 동시**: backend-dev, frontend-dev 병렬 소환

## Phase 3: QA 검증

개발 완료 후 director가 qa-engineer 소환:
- 수정된 코드 로직 검증
- `cd backend && /opt/homebrew/bin/python3.11 -m pytest tests/ -v` 실행
- 결과를 director에게 보고

## Phase 4: 코드 리뷰 (머지 전 필수)

> ⚠️ **머지 전 반드시 실행. 생략 절대 금지.**

director가 PR 생성 후 **팀리드(오케스트레이터)**에게 PR 번호 보고.
팀리드가 `/code-review:code-review` 스킬을 실행한다.

- 리뷰 결과에서 Critical/High 이슈 → director에게 수정 지시 → 재푸시 → 재리뷰
- 리뷰 통과 후에만 `gh pr merge --squash --delete-branch` 실행

**머지 후 브랜치 정리 (매번 실행):**
```bash
git checkout main && git pull
git branch | grep -v '^\* main' | xargs git branch -D
git remote prune origin
```

## Phase 5: 완료 보고

director가 **팀리드(오케스트레이터)**에게 보고:
- 수정된 파일 목록
- 테스트 결과
- PR 번호 / 머지 상태

팀리드가 사용자에게 최종 결과 전달.

## 보고 체계

```
사용자 ↔ 팀리드(오케스트레이터) ↔ director ↔ 팀원들
```

- 팀원 → director: 작업 완료 보고
- director → 팀리드: 전체 결과 보고
- 팀리드 → 사용자: 최종 전달
- director/팀원이 사용자에게 직접 소통하지 않음

## 에러 핸들링

- 에이전트 실패: 1회 재시도 후 director가 팀리드에게 보고
- M1 MPS 오류: ai-engineer가 CPU 폴백으로 처리
- 기술/아키텍처 결정: director가 자율 결정 후 진행 (사용자에게 질문 금지)
