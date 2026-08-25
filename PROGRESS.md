## 2026-08-25 (작업 PC: 로컬) — 세션 23 (신규 기능 3개 완료)
- 브랜치: main (PR #24~#26 squash 머지)
- 완료: product-manager 기획 → director 팀 구현 (3가지 기능)
  - 타임스탬프 클릭 → 오디오 점프: [MM:SS] 버튼 파란색 링크 스타일, CustomEvent audio-seek (PR #24)
  - 요약 재생성: POST /api/jobs/{id}/regenerate, SummaryPanel 재생성 버튼+카테고리 선택 모달 (PR #25)
  - 회의 태그: DB tags 컬럼, PATCH /api/jobs/{id}/tags, GET /api/tags, 태그 입력 UI, /meetings 필터, Sidebar 뱃지 (PR #26)
- 현재 상태: main 최신 (7a28dbb)
- 다음 할 일: 없음
- 관련 PR: #24, #25, #26
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 22 (신규 기능 4개 완료)
- 브랜치: main (PR #18~#23 squash 머지)
- 완료: product-manager + director 협의 후 4개 기능 개발
  - 북마크/즐겨찾기: DB bookmarked 컬럼, PATCH API, Sidebar 별표 토글, /meetings 필터 (PR #18, #22)
  - 회의 메모 필드: DB memo 컬럼, PATCH API, done 화면 textarea+저장 (PR #19, #22)
  - 다크모드 파형+Notification: AnalyserNode 캔버스 다크/라이트, done/error 브라우저 알림 (PR #20)
  - ZIP 전체 내보내기: GET /api/export StreamingResponse, /meetings 버튼 (PR #21, #23)
- 현재 상태: main 최신 (3651b4f), 서버 실행 중
- 다음 할 일: 없음
- 관련 PR: #18, #19, #20, #21, #22, #23
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 21 (서버 검증 + 버그 수정)
- 브랜치: main (직접 커밋 8c6f1be)
- 완료: 신규 기능 3개 서버 검증 + 버그 수정
  - fix: PR #16(연관 회의 API) 코드 누락 확인 → main.py에 직접 구현
    - _extract_keywords() 헬퍼: 불용어 제거, 빈도 기반 상위 N개
    - GET /api/jobs/{id}/related: 키워드 매칭 상위 5개 반환
  - 검증: 키보드 단축키 힌트 표시, 연관 회의 섹션 정상 렌더링 확인 (Playwright 스크린샷)
- 현재 상태: main 최신 (8c6f1be), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 20 (신규 기능 3개 완료)
- 브랜치: main (PR #13~#17 squash 머지)
- 완료: product-manager + director 협의 후 3개 기능 개발
  - 액션 아이템 체크리스트: DB action_items 컬럼, Claude 요약 파싱, PATCH API, 인터랙티브 UI (PR #13, #15)
  - 키보드 단축키: useKeyboardShortcuts 훅, Space/←→/Esc, input 포커스 시 비활성화 (PR #14)
  - 연관 회의 검색: 키워드 추출 API, done 화면 하단 관련 회의 섹션 UI (PR #16, #17)
- 현재 상태: main 최신 (a468deb), 서버 실행 중
- 다음 할 일: 없음 (신규 기획 기능 모두 완료)
- 관련 PR: #13, #14, #15, #16, #17
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 19 (A, C, G 완료)
- 브랜치: main (feature/multilang-stt → PR #12 → squash 머지)
- 완료: A, C, G 전체 완료
  - A. 자동 회의 제목 생성: run_summary 후 # 첫 줄 파싱 → update_job_title (PR #10)
  - C. 마크다운 내보내기: ↓ MD 버튼, Blob 방식, 제목+날짜+요약+스크립트 (PR #11)
  - G. 다국어 STT: DB language 컬럼, 드롭다운 UI (🇰🇷/🇺🇸/🇯🇵/🌐), Whisper 전달 (PR #12)
- 현재 상태: main 최신 (7774763), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음 (모든 계획 기능 완료)
- 관련 PR: #10, #11, #12
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 18
- 브랜치: main (feature/markdown-export → PR #11 → squash 머지)
- 완료: C. 마크다운 내보내기 (↓ MD 버튼, Blob 방식)
- 현재 상태: main 최신 (ceaba1f)
- 관련 PR: #11
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 17
- 브랜치: main (feature/auto-title → PR #10 → squash 머지)
- 완료: A. 자동 회의 제목 생성 (run_summary 요약 첫 # 줄 파싱)
- 현재 상태: main 최신 (4c4425e)
- 관련 PR: #10
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 16 (서버 검증 + 버그 수정)
- 브랜치: main (직접 커밋)
- 완료: 브라우저 실제 동작 검증 + 버그 수정
  - fix: 화자 탭 SPEAKER_00 등 내부 ID 표시 버그 → 실제 이름(값)으로 수정
    - 프론트: Object.keys() → Object.values() (중복 제거 포함)
    - 백엔드: DELETE /api/speakers/{name} — 값 기준 삭제로 변경
  - 검증: 메인/다크모드/통계카드/화자탭 모두 정상 확인 (Playwright 스크린샷)
- 현재 상태: main 최신 (05efd13), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음 (모든 계획 기능 완료 + 검증)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 15 (기능 b~f 완료)
- 브랜치: main (feature/mobile-responsive → PR #9 → squash 머지)
- 완료: 기능 b~f 전체 완료
  - b. 화자 프로필 관리: POST/DELETE /api/speakers + 설정 모달 '화자' 탭 (PR #7)
  - c. 통계 대시보드: GET /api/stats + /meetings 페이지 통계 카드 4개 (PR #8)
  - d. 실패 재시도: 이미 구현 확인 (추가 PR 불필요)
  - e. 다크 모드: useTheme 훅 + Tailwind class 전체 적용 (PR #6, 세션 12)
  - f. 모바일 최적화: Sidebar 삭제 버튼 모바일 상시표시, ProgressCard 패딩 (PR #9)
- 현재 상태: main 최신 (9b6dbbb), 브랜치 origin/main 만 남음
- 다음 할 일: 없음 (모든 계획 기능 완료)
- 관련 PR: #6, #7, #8, #9
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 14
- 브랜치: main (feature/stats-dashboard → PR #8 → squash 머지)
- 완료:
  - c. 통계 대시보드: GET /api/stats + /meetings 페이지 통계 카드 4개 (PR #8)
  - d. 실패 재시도: 이미 구현됨 확인 (backend POST /api/jobs/{id}/retry + MainArea 버튼, 별도 PR 불필요)
- 현재 상태: main 최신 (4d84a7c)
- 관련 커밋: PR #7, PR #8
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 13
- 브랜치: main (feature/speaker-profile → PR #7 → squash 머지)
- 완료: 화자 프로필 관리
  - 백엔드: POST /api/speakers, DELETE /api/speakers/{name}
  - 프론트: 설정 모달 '화자' 탭 (이름 추가/삭제, Enter 지원)
- 현재 상태: main 최신 (04bdded)
- 관련 커밋: PR #7
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 12
- 브랜치: main (feature/dark-mode → PR #6 → squash 머지)
- 완료: 다크 모드 지원 + git 브랜치 정리
  - `tailwind.config.ts`: `darkMode: 'class'` 추가
  - `frontend/hooks/useTheme.ts`: localStorage + 시스템 preference 감지, FOUC 방지, hydration 안전 (null 초기값)
  - `layout.tsx`: 인라인 스크립트 FOUC 방지, `suppressHydrationWarning`
  - `Sidebar.tsx`: 다크/라이트 토글 버튼 추가
  - `MainArea.tsx`, `AudioPlayer.tsx`: dark: Tailwind 클래스 전체 적용
- 브랜치 정리: stale 원격 브랜치 6개 pruned (clipboard-copy, pdf-export, playback-speed, sidebar-delete-button, summary-patch-test, dark-mode)
- 현재 상태: main 최신 (6fee23a), 브랜치 origin/main 만 남음
- 다음 할 일: 나머지 기능 (b. 화자 프로필 관리, c. 통계 대시보드, d. 실패 재시도, f. 모바일 최적화) 순차 개발
- 관련 커밋: PR #6
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 11
- 브랜치: main (feature/sidebar-delete-button → PR #3, feature/summary-patch-test → PR #4)
- 완료: 기능 a~f 검증 및 보강
  - a. Browser Notification: 이미 구현됨 (ProgressCard.tsx + MainArea.tsx)
  - b. 음파 시각화: 이미 구현됨 (RecordingZone.tsx AnalyserNode + canvas)
  - c. 음성 다운로드: 이미 구현됨 (MainArea.tsx `<a download>`)
  - d. 회의 삭제: 사이드바 hover 시 휴지통 삭제 버튼 추가 (PR #3)
  - e. 요약 편집+저장: 이미 구현됨 + 백엔드 테스트 3개 추가 (PR #4)
  - f. 재요약: 이미 구현됨 (카테고리 변경 모달 포함)
- 현재 상태: main 최신 (11c2f58)
- 다음 할 일: 새 기능 논의
- 관련 커밋: 80f5eed (PR #3), 11c2f58 (PR #4)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 10
- 브랜치: main (feature/playback-speed → PR #2 → squash 머지)
- 완료: 오디오 재생 속도 조절 버튼 (0.75x/1x/1.25x/1.5x/2x 순환)
- 현재 상태: main 최신 (83b711a), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - frontend/components/AudioPlayer.tsx: SPEEDS 배열, speed state, handleSpeedChange(), 속도 버튼 UI
- 관련 커밋: 83b711a (main, squash 머지), PR #2
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 9
- 브랜치: main (feature/pdf-export → PR #1 → squash 머지)
- 완료: PDF 내보내기 기능 + 브랜치 개발 워크플로우 확립
- 현재 상태: main 최신, 서버 실행 중
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - frontend/app/print/[id]/page.tsx: 인쇄 최적화 전용 페이지 (A4, 요약+스크립트)
  - frontend/components/MainArea.tsx: done 상태에 PDF 버튼 추가
- 코드 리뷰 이슈 수정:
  - 테이블 구분자 행(| --- |) 필터링 추가
  - window.print() 트리거에 job.status === 'done' 조건 추가
- 브랜치 전략 확립: feature/* → PR → /code-review → 머지
- 관련 커밋: a22ba66 (main, squash 머지), PR #1
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 8
- 브랜치: main
- 완료: 회의 목록 카테고리/날짜 필터 기능
- 현재 상태: 서버 실행 중, 테스트 59/59 PASS
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - backend/app/database.py: search_jobs()에 category_id, date_from, date_to 필터 추가 (SQLite DATE() 함수 사용)
  - backend/app/main.py: /api/meetings에 필터 쿼리 파라미터 추가
  - backend/tests/test_search_jobs.py: 카테고리 필터, 날짜 필터, 복합 필터 테스트 3개 추가
  - frontend/app/meetings/page.tsx: 카테고리 드롭다운 + 날짜 범위(from/to) 필터 UI, URL 쿼리 동기화, 필터 초기화 버튼
- 관련 커밋: 7cdd585
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 7
- 브랜치: main
- 완료: 파일 업로드 기능 E2E 테스트 완료
- 현재 상태: 전체 기능 정상, 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 새 기능 논의 or 배포
- E2E 테스트 결과:
  - txt 파일 업로드 → awaiting_edit 직진입 → TranscriptEditor 정상 렌더링 ✅
  - 화자 분리 (SPEAKER_00/01) + 타임스탬프 파싱 정상 ✅
  - 사이드바 "편집 대기 중" 뱃지 표시 ✅
  - 백엔드 테스트 56/56 PASS ✅
- 관련 커밋: 6e231ee (파일 업로드), ede4423 (PROGRESS 세션 6)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 6
- 브랜치: main
- 완료: 파일 업로드 기능 (오디오/txt) + 코드 리뷰 버그 3개 수정
- 현재 상태: 서버 미실행 (코드만 수정), 모든 테스트 통과 (56/56)
- 구현 내용:
  - backend/app/main.py: POST /api/upload 엔드포인트 (오디오→STT파이프라인, txt→awaiting_edit 직진입), limit 상한 100, SSE 연결 해제 감지
  - backend/app/summarizer.py: self-referential 화자 매핑 필터링 버그 수정
  - backend/tests/test_upload.py: 업로드 테스트 4개 (56개 전체 통과)
  - frontend/components/RecordingZone.tsx: 녹음/파일업로드 탭 UI, 드래그앤드롭 + 클릭 업로드
- 관련 커밋: 6e231ee, e699d80
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 5
- 브랜치: main
- 완료: 카테고리 시스템 E2E 테스트 + 버그 2개 수정
- 현재 상태: 서버 실행 중 (백엔드 8000, 프론트 3000), 모든 기능 정상
- 다음 할 일: 추가 테스트 또는 새 기능 논의
- 구현 내용:
  - Playwright로 UI E2E 검증 (RecordingZone 카테고리 드롭다운 5개, 설정 모달 3탭, 카테고리 인라인 편집)
  - `frontend/components/TranscriptEditor.tsx`: suggestedNames 버그 수정
    - 기존: speakers.json 이전 매핑이 이름 입력란에 자동 채워져 의도치 않게 적용됨
    - 수정: names 초기값 빈 문자열, suggestedNames는 placeholder 힌트로만 표시
  - `backend/app/notion_sync.py`: Notion 테이블 블록 구조 버그 수정
    - 기존: table_row children을 블록 최상위 children에 넣어 Notion API 422 오류
    - 수정: children을 table 오브젝트 내부로 이동 (`table.children`)
    - 영향: 설교요약 등 표가 포함된 카테고리 Notion 업데이트 정상 동작
  - `backend/tests/test_notion_sync.py`: 테이블 구조 변경에 맞게 테스트 수정
- 관련 커밋: be79908..2ff5450 (gitignore 포함)
- 푸시 여부: origin/main 푸시 완료 (https://github.com/jaerakson/meeting-jr)

## 2026-08-23 (작업 PC: 로컬) — 세션 4
- 브랜치: main
- 완료: 카테고리 시스템 전체 구현 (8개 Task, SDD 방식)
- 현재 상태: 서버 미실행 (코드만 수정), 모든 테스트 통과
- 다음 할 일: 서버 재시작 후 E2E 테스트
- 구현 내용:
  - `backend/app/categories.py`: 5개 기본 카테고리 (meeting/lecture/sermon/interview/brainstorm) + DEFAULT_PROMPTS
  - `backend/app/database.py`: categories 테이블 + seed, Job에 category_id 필드
  - `backend/app/main.py`: Category CRUD API (GET/POST/PATCH/DELETE/reset), record/finalize에 category_id 통합, run_summary 카테고리별 프롬프트 적용
  - `backend/app/notion_sync.py`: table/quote/numbered/bold 블록 지원, 카테고리 헤더 자동 삽입
  - `frontend/types/index.ts`: Category 인터페이스, Job에 category 필드 추가
  - `frontend/components/CategorySelect.tsx`: 카테고리 드롭다운 컴포넌트
  - `frontend/components/RecordingZone.tsx`: 카테고리 선택 + localStorage 저장
  - `frontend/components/TranscriptEditor.tsx`: 카테고리 선택 + finalize에 전달
  - `frontend/components/MainArea.tsx`: 카테고리 뱃지 + 재요약 카테고리 모달
  - `frontend/components/SettingsModal.tsx`: 일반/Claude/카테고리 3탭, 카테고리 CRUD UI
  - `backend/tests/`: 52개 전체 통과 (0.45s)
- QA 검증 결과:
  - 백엔드 테스트: 52/52 PASS
  - 프론트엔드 빌드: PASS (Next.js 15, static 5페이지)
  - 카테고리 API: 5개 카테고리, 전체 {script} 플레이스홀더 포함 확인
- 관련 커밋: 91c84ed..98e416c (Task 1~7)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬) — 세션 3
- 브랜치: main
- 완료: Claude 모델/프롬프트 설정 기능 구현 + 화자 매핑 버그 2개 수정
- 현재 상태: 서버 미실행 (코드만 수정), 기능 정상
- 다음 할 일: 서버 재시작 후 테스트
- 구현 내용:
  - `backend/app/settings_manager.py`: `CLAUDE_MODEL`, `CLAUDE_PROMPT` 키 추가
  - `backend/app/summarizer.py`: `DEFAULT_PROMPT` 상수 추가, `generate_summary(model, prompt_template)` 파라미터 추가
  - `backend/app/main.py`: `GET /api/settings/claude-model`, `GET /api/settings/claude-prompt` 엔드포인트 추가, `run_summary`에서 설정값 읽어 모델/프롬프트 전달
  - `backend/app/main.py`: `_save_speakers()` 수정 — key==value 무의미한 매핑(UNKNOWN→UNKNOWN 등) 저장 안 함
  - `frontend/components/SettingsModal.tsx`: Claude 모델 선택 드롭다운 + 프롬프트 textarea (10행, 초기화 버튼) 추가
  - `frontend/components/MainArea.tsx`: `handleAwaitingEdit` 수정 — transcript 없는 SSE fallback 시 editData 설정 안 함 (페이지 새로고침 시 빈 TranscriptEditor 방지)
  - `backend/speakers.json`: "UNKNOWN": "UNKNOWN" 오염 항목 제거
  - `backend/tests/test_model_prompt_setting.py`: 4개 테스트 추가
- 버그 수정 내역:
  1. 페이지 새로고침 시 awaiting_edit 상태에서 빈 TranscriptEditor 표시 → transcript 빈 경우 editData 미설정으로 수정
  2. speakers.json에 "UNKNOWN": "UNKNOWN" 같은 self-referential 항목 축적 → 필터링 추가
- 관련 커밋: 4118915.. (미커밋)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬) — 세션 2
- 브랜치: main
- 완료: Notion UX 개선 + 기본 회의 제목 설정 + 문서 전체 업데이트
- 현재 상태: 서버 실행 중 (백엔드 8000, 프론트 3000), 모든 기능 정상
- 다음 할 일: 테스트 후 추가 기능 논의
- 구현 내용:
  - `backend/app/main.py`: Notion 내보내기 제목에 `[회의날짜 HH:MM]` 접두 (created_at KST 변환)
  - `backend/app/main.py`: Notion 페이지 상단에 `📤 업로드 일시: YYYY-MM-DD HH:MM` 자동 삽입
  - `backend/app/main.py`: 녹음 시작 시 기본 제목 설정값 사용 (미설정 시 '회의록')
  - `backend/app/main.py`: `GET /api/settings/default-title` 엔드포인트 추가
  - `backend/app/settings_manager.py`: `DEFAULT_MEETING_TITLE` 키 추가
  - `frontend/components/MainArea.tsx`: Notion 버튼 로딩 피드백 (스피너 + 텍스트 변경 + disabled)
  - `frontend/components/SettingsModal.tsx`: 기본 회의 제목 입력 필드 추가 (하단 공통 저장 통합)
  - 문서: SKILL.md TeamCreate에 product-manager 추가, DEVGUIDE.md/README.md 전체 업데이트
- 관련 커밋: 980c6fb..4118915 (5개)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬)
- 브랜치: main
- 완료: 회의 목록 페이지 (/meetings) 전체 구현 + QA 완료
- 현재 상태: 실행 준비 완료 (6개 커밋, 모든 테스트 통과)
- 다음 할 일:
  1. 터미널1: cd backend && /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000
  2. 터미널2: cd frontend && npm run dev
  3. 브라우저: http://localhost:3000 → 사이드바 "전체 목록 보기" 클릭 → /meetings
- 구현 내용:
  - backend/app/database.py: search_jobs() 함수 추가
  - backend/app/main.py: GET /api/meetings?q=&page=&limit=12 엔드포인트
  - backend/tests/: pytest 8개 테스트 (search_jobs 5개 + endpoint 3개)
  - frontend/components/Pagination.tsx: 페이지 번호 + ellipsis 컴포넌트
  - frontend/components/MeetingCard.tsx: 카드 (제목/날짜/참석자/요약/액션수/뱃지)
  - frontend/app/meetings/page.tsx: 검색+그리드+페이지네이션 페이지
  - frontend/components/Sidebar.tsx: "전체 목록 보기" 링크 추가
  - frontend/app/page.tsx: ?job= 파라미터 자동 선택 처리
- 머지 후 개선 사항 (Minor, 기능 영향 없음):
  - test_search_jobs.py: 미사용 import tempfile 제거
  - /meetings 마운트 시 이중 fetch 최적화
  - Pagination aria-label 추가 (접근성)
  - limit 파라미터 상한 검증 추가
- 관련 커밋: c857701..5ffbf02 (6개)
- 푸시 여부: 미푸시 (git remote 미설정)


