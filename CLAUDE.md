# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트

M1 Mac 로컬 환경의 회의록 자동화 웹앱. 음성 파일 → 화자 분리(PyAnnote) + STT(MLX-Whisper) → Claude 요약 → Notion 등록.
설계 기준 문서: `DEVGUIDE.md`

---

## 하네스: meeting-jr

**목표:** DEVGUIDE.md 기반으로 에이전트 팀이 Meeting Junior 앱을 완성한다.

**트리거:** 개발, 구현, 수정, 기능 추가 등 코드 작업 요청 시 `meeting-jr-dev` 스킬을 사용하라. 단순 질문은 직접 응답 가능.

**팀 운영:**
- meeting-jr-dev 스킬 호출 시 반드시 TeamCreate로 팀 구성 (별도 창 표시)
- 팀리드가 상황 판단하여 적절한 에이전트를 먼저 소환 (기획→PM, 버그→director, 기능→director)
- teammate는 다른 teammate 소환 불가 (시스템 제약) → 팀리드만 소환 가능
- director가 팀원 요청 → 팀리드가 소환 → director가 SendMessage로 팀원 간 코디네이션
- 공통: 오케스트레이터가 직접 코드를 수정하지 않는다. 개발자 에이전트 → qa-engineer → 코드 리뷰 절차는 항상 유지. 개발자 에이전트가 QA나 코드 리뷰를 대신하지 않는다.

**총괄 자율 결정 권한:**
director 에이전트는 아키텍처·UX·기술 세부사항에 대해 자율적으로 결정하고 진행한다.
확정 결정사항은 DEVGUIDE.md 섹션 10에 기록한다.

**행동 원칙 (필수):**
- "진행할까요?", "수정할까요?", "확인해드릴까요?" 같은 확인 질문 절대 금지
- 판단하고 즉시 실행. 완료 후 결과만 간략히 보고
- 사용자 승인 없이 파일 편집·생성·삭제·bash 실행 모두 자율 처리

**에이전트 모델 배정:**
| 에이전트 | 모델 | 사유 |
|---------|------|------|
| director | opus | 아키텍처·설계 판단이 전체에 파급된다. 판단 오류가 실제로 발생한 이력 있음 |
| product-manager | opus | 기획 품질이 이후 작업 전체를 좌우. 호출 빈도 낮아 비용 부담 적음 |
| backend-dev | opus | 데이터 정합성 로직에서 미묘한 버그가 반복 발생한 영역 |
| ai-engineer | opus | 오디오 파이프라인·라이브러리 호환 패치가 까다로움 |
| frontend-dev | sonnet | 명세 기반 UI 구현. 판단 여지가 적다 |
| qa-engineer | sonnet | director 명세를 받아 테스트 작성. 판단 여지가 적다 |

> 모델은 별칭(`opus`/`sonnet`/`haiku`)으로 지정한다. 버전을 박으면 낡는다
> (실제로 여섯 개 전부 `claude-opus-4-6`에 고정돼 있었다).

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-08-29 | 에이전트 모델 역할별 차등 + 별칭 전환 | 전체 에이전트 | 전부 구형 opus 고정 상태였음. 판단 역할은 opus, 명세 기반 구현은 sonnet |
| 2026-08-27 | 하네스 팀 구조·프로세스 전면 재정비 | 전체 | TDD, 보고 체계, 소환 규칙, 팀리드 역할 명확화 |
| 2026-08-23 | product-manager 에이전트 추가 | 하네스 팀 | 기획/명세 역할 분리 |
| 2026-08-22 | DEVGUIDE.md 아키텍처/UX/기술 세부사항 보완 | DEVGUIDE.md | SQLite, Queue, Anthropic SDK, UX 기능 확정 |
| 2026-08-22 | 초기 구성 | 전체 | - |

---

## 브랜치 전략

- `main` — 항상 배포 가능한 상태 유지. 직접 커밋 금지.
- `feature/<기능명>` — 새 기능 개발 브랜치 (예: `feature/pdf-export`)
- `fix/<버그명>` — 버그 수정 브랜치 (예: `fix/sse-disconnect`)

**개발 플로우:**
1. `git checkout -b feature/<기능명>` 으로 브랜치 생성
2. 기능 구현 + 테스트 완료
3. `git push origin feature/<기능명>` 후 PR 생성
4. **[필수] `/code-review:code-review` 스킬로 코드 리뷰** ← 반드시 실행, 생략 불가
5. 리뷰 통과 후 `gh pr merge --squash --delete-branch` 로 머지
6. 로컬 브랜치 전체 정리 (main 제외 모든 브랜치 삭제):
```bash
git checkout main && git pull
git branch | grep -v '^\* main' | xargs git branch -D
git remote prune origin
```
> ⚠️ **`feature/<기능명>` 브랜치만 삭제하지 말 것.** 작업 중 생성된 임시 브랜치(pr-check, test 등)도 함께 삭제한다.

> ⚠️ **코드 리뷰 없이 머지 절대 금지.** director가 PR 생성 후 팀리드에게 보고하고, 팀리드가 `/code-review:code-review` 스킬을 실행한다.

**코드 리뷰 전 PR 생성 명령어:**
```bash
gh pr create --base main --title "<제목>" --body "<설명>"
```

---

## 개발 명령어

```bash
# 서버 실행
cd backend && /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000

# 프론트엔드
cd frontend && npm run dev

# 테스트
cd backend && /opt/homebrew/bin/python3.11 -m pytest tests/ -v

# 의존성 설치
pip install -r requirements.txt
```
