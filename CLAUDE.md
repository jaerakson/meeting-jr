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

**총괄 자율 결정 권한:**
director 에이전트는 아키텍처·UX·기술 세부사항에 대해 자율적으로 결정하고 진행한다.
확정 결정사항은 DEVGUIDE.md 섹션 10에 기록한다.

**행동 원칙 (필수):**
- "진행할까요?", "수정할까요?", "확인해드릴까요?" 같은 확인 질문 절대 금지
- 판단하고 즉시 실행. 완료 후 결과만 간략히 보고
- 사용자 승인 없이 파일 편집·생성·삭제·bash 실행 모두 자율 처리

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
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
6. `git checkout main && git pull && git branch -D feature/<기능명>` 로컬 브랜치 정리

> ⚠️ **코드 리뷰 없이 머지 절대 금지.** director 에이전트는 PR 생성 후 반드시 `/code-review:code-review` 스킬을 실행하고 리뷰 결과를 확인한 뒤 머지한다.

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
