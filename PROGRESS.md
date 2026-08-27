## 2026-08-27 (작업 PC: 로컬) — 세션 50 (PR #68~#70: 녹음 파형 + 오디오 시킹 수정)
- 브랜치: main (PR #68 9533352, #69 2a2b183, #70 3dfcbfa)
- 완료:
  - **PR #68 - 녹음 시 음성 파형 미표시 수정:**
    - 원인: drawWave()를 setIsRecording(true) 직후 동기 호출 → canvas 미마운트 상태에서 canvasRef=null
    - 수정: useEffect로 isRecording/isPaused 상태 변화 후 canvas 확인 뒤 drawWave() 호출
  - **PR #69 - WebM remux (duration/Cues 추가):**
    - MediaRecorder WebM 파일에 duration=N/A → ffmpeg -c copy remux로 메타데이터 추가
    - _remux_webm_if_needed() 유틸: ffprobe 확인 → 필요 시 remux → 원본 교체
    - POST /api/record 저장 후 + GET /api/jobs/{id}/audio 서빙 시 적용
  - **PR #70 - HTTP Range 요청 지원:**
    - Starlette FileResponse가 Range 미지원 → seekable={0,0} → 시킹 불가
    - StreamingResponse로 206 Partial Content + Content-Range 구현
    - Accept-Ranges: bytes 헤더 추가
  - Playwright 검증: seekable={0, 49.473}, currentTime=37 시킹 정상 동작 확인
  - 3건 코드리뷰 모두 통과
- 현재 상태: 안정 — 녹음 파형 + 오디오 시킹 완전 해결
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/RecordingZone.tsx, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (3dfcbfa)

---

## 2026-08-27 (작업 PC: 로컬) — 세션 49 (PR #63~#67: diarization DB + SummaryPanel + 프로필 추출 + 음성 매칭 UX)
- 브랜치: main (PR #63 0daed85, #64 937b501, #65 2d88f25, #66 bd33196, #67 8b62f3c, hotfix fb5ef77)
- 완료:
  - **PR #63 - Diarization DB 통합:**
    - meetings.diarization TEXT 컬럼 추가, DB 우선 조회 + lazy migration
  - **PR #64 - SummaryPanel 높이 붕괴 수정:**
    - md:h-auto → md:h-full, SummaryPanel flex-1 min-h-0, 하단 섹션 max-h-[35%] 래퍼
  - **PR #65 - Identity-mapped speakers 프로필 추출 수정:**
    - speakers {아빠: 아빠} 형태에서 SPEAKER_XX 매핑 소실 → transcript 타임스탬프 교차 비교 폴백
  - **PR #66 - 타임스탬프 매칭 개선:**
    - ±2초 포인트 매칭 → 구간 overlap 면적 매칭 (실제 데이터로 아빠 프로필 추출 성공 확인)
  - **PR #67 - 음성 매칭 UX 개선 + 기존 녹음 재매칭:**
    - TranscriptEditor: 자동 채우기 제거 → 제안 칩 `👤 이름 85% [적용]` + 되돌리기
    - POST /api/jobs/{id}/rematch: done 상태 회의에서 voice profile 재매칭
    - POST /api/jobs/{id}/apply-match: 매칭 결과를 transcript/speakers에 반영
    - MainArea: "🎤 음성 매칭" 버튼 + 결과 모달 + 전체 적용
    - _extract_and_match_speakers() 공통 함수 추출 (job_queue 인라인 → 재사용)
    - 코드리뷰 수정: handleApplyMatch null 필터링 + res.ok 검증
  - **Hotfix fb5ef77 - rematch 모달 키 불일치 수정:**
    - 모달이 speakers 키(아빠) 대신 rematchResult 키(SPEAKER_XX)로 순회하도록 수정
    - Playwright 검증: SPEAKER_00 → 아빠 (100%) 매칭 + 전체 적용 성공 확인
  - 전체 105개 테스트 통과, 5건 코드리뷰 통과
- 현재 상태: 안정
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/database.py, job_queue.py, main.py, tests/test_speaker_profile.py, test_rematch_api.py, frontend/components/MainArea.tsx, SummaryPanel.tsx, TranscriptEditor.tsx
- 푸시 여부: origin/main 푸시 완료 (fb5ef77)

---

## 2026-08-27 (작업 PC: 로컬) — 세션 49 이전 기록 (diarization DB 통합 PR #63 + SummaryPanel 수정 PR #64)
- 브랜치: main (PR #63 squash 머지 0daed85, PR #64 squash 머지 937b501)
- 완료:
  - **PR #63 - Diarization DB 통합:**
    - meetings.diarization TEXT 컬럼 추가 (마이그레이션)
    - get_job_diarization() 경량 조회 헬퍼
    - job_queue: process_audio 결과의 diarization을 DB에 저장
    - save_speaker_profile: DB 우선 → 파일 폴백(lazy migration) → WAV 재실행 3단계 로직
    - 테스트 2개 추가 (DB-only, lazy migration), 전체 95개 통과
  - **PR #64 - SummaryPanel 높이 붕괴 버그 수정:**
    - 원인: md:h-auto가 flex stretch 무효화 → SummaryPanel 2px 붕괴 → overflow-hidden 클리핑
    - 수정: md:h-full + SummaryPanel flex-1 min-h-0 + 하단 섹션 max-h-[35%] 래퍼
    - Playwright 검증: 385px 높이 + 탭/편집 버튼 동작 확인
  - 두 PR 모두 코드리뷰 통과 (80점 이상 이슈 없음)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/database.py, backend/app/job_queue.py, backend/app/main.py, backend/tests/test_speaker_profile.py, frontend/components/MainArea.tsx, frontend/components/SummaryPanel.tsx
- 푸시 여부: origin/main 푸시 완료 (0daed85)

## 2026-08-27 (작업 PC: 로컬) — 세션 48 (프로필 추출 버그 수정 PR #62)
- 브랜치: main (PR #62 squash 머지, d065e3e)
- 완료:
  - Backend: save_speaker_profile에서 매핑된 화자 이름(김팀장 등)으로 diarization 역조회 로직 추가
  - Frontend: TranscriptEditor에서 suggestedNames를 names 초기값으로 사전 입력 (빈 문자열 대신)
  - TDD: qa-engineer 테스트 먼저 작성 → backend-dev/frontend-dev 구현 → qa 재검증 (93/93 통과)
  - 코드리뷰: /code-review 스킬 실행, 80점 이상 이슈 없음 → 통과
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/main.py, backend/tests/test_speaker_profile.py, frontend/components/TranscriptEditor.tsx, frontend/__tests__/TranscriptEditor.test.tsx
- 푸시 여부: origin/main 푸시 완료 (d065e3e)

## 2026-08-27 (작업 PC: 로컬) — 세션 47 (하네스 최종 프로세스 정립)
- 브랜치: main (1c97a50)
- 완료:
  - 하네스 팀 구조·프로세스 최종 정립 (8개 파일 수정)
  - 프로세스 A(새 기능): PM brainstorming → 사용자 승인 → director → TDD → 개발 → QA → 코드리뷰 → 머지
  - 프로세스 B(버그): director 분석 → TDD → 개발 → QA → 코드리뷰 → 머지
  - TDD 도입: qa-engineer가 구현 전 테스트 먼저 작성
  - 팀리드 상황 판단: 기획→PM, 버그→director, 기능→director
  - 시스템 제약 반영: teammate 소환 불가 → 팀리드만 소환, director는 SendMessage 코디네이션
  - 보고 체계: 팀원→director→팀리드→사용자 (기획안만 사용자 승인)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: .claude/skills/meeting-jr-dev/SKILL.md, .claude/agents/*.md, CLAUDE.md
- 푸시 여부: origin/main 푸시 완료 (1c97a50)

## 2026-08-27 (작업 PC: 로컬) — 세션 46 (speaker_map 이름 파싱 + 하네스 재정비 PR #61)
- 브랜치: main (PR #61 squash 머지, 10279a0)
- 완료:
  - Backend: finalize 시 identity-mapped speaker_map 감지 → transcript에서 실제 이름 파싱 (이름 자체를 키로 사용)
  - Frontend: 드롭다운에서 key===value일 때 중복 표시 방지
  - 코드리뷰: sorted keys vs appearance order 매핑 버그 발견 → 수정 후 재리뷰 통과
  - 하네스 전면 재정비: 팀 구조(director 최상위), Phase 0~5 재구성, brainstorming/worktree 추가
  - teammate 소환 제약 발견: flat 구조 → 팀리드만 소환 가능, 스킬/에이전트 문서 반영
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/main.py, frontend/components/SettingsModal.tsx, .claude/skills, .claude/agents
- 푸시 여부: origin/main 푸시 완료 (72f0220)

## 2026-08-27 (작업 PC: 로컬) — 세션 45 (오디오 시크바 + duration 수정 PR #60)
- 브랜치: main (PR #60 squash 머지, 7d5c365)
- 완료:
  - AudioPlayer: webm duration Infinity 문제 해결 (durationchange + seek-to-end 워크어라운드 + fallbackDuration 3단계 폴백)
  - 시크바 클릭/드래그 탐색 활성화 (duration 정상화로 disabled 해제)
  - MainArea: job.duration_sec를 fallbackDuration prop으로 전달
  - TranscriptEditor: onDurationChange 핸들러 추가
  - preload="metadata" → "auto" 변경
  - 하네스 스킬 호출 시 무조건 TeamCreate 규칙 추가 (별도 창 표시)
  - 절차: frontend-dev → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/AudioPlayer.tsx, MainArea.tsx, TranscriptEditor.tsx
- 푸시 여부: origin/main 푸시 완료 (dc53501)

## 2026-08-26 (작업 PC: 로컬) — 세션 44 (diarization 재실행 프로필 추출 PR #59)
- 브랜치: main (PR #59 squash 머지, bfab3b6)
- 완료:
  - _diarization.json 없지만 _16k.wav 있는 기존 회의에서 프로필 추출 시 diarization 자동 재실행
  - audio_processor.py: run_diarization_and_save() 함수 추가 (pyannote 독립 실행 + JSON 저장)
  - main.py: save-speaker-profile 엔드포인트에서 wav 있으면 재실행 분기 추가
  - 절차: ai-engineer → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- E2E 테스트 완료: 주일 예배 → 목사님(SPEAKER_00) 프로필 추출 성공 (pyannote/embedding 모델 수락 필요 — gated repo)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/audio_processor.py, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (bfab3b6)

## 2026-08-26 (작업 PC: 로컬) — 세션 43 (프로필 추출 화자 이름 매칭 PR #58)
- 브랜치: main (PR #58 squash 머지, 396e471)
- 완료:
  - 설정 > 목소리 프로필 > 기존 회의에서 추출 화자 드롭다운에 실제 이름 표시
  - 이름 있으면 "목사님 (SPEAKER_00)" 형식, 없으면 기존대로 SPEAKER_XX
  - 화자 선택 시 프로필 이름 자동 입력 (extractSpeakerMap 상태 추가)
  - 절차: frontend-dev → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/SettingsModal.tsx
- 푸시 여부: origin/main 푸시 완료 (396e471)

## 2026-08-26 (작업 PC: 로컬) — 세션 42 (설정 모달 사이드바 이동 버그 수정 PR #57)
- 브랜치: main (PR #57 squash 머지, d0cfc34)
- 완료:
  - 설정 화면이 열려있을 때 사이드바에서 회의록 클릭 시 설정을 닫고 해당 회의록으로 이동하도록 수정
  - SettingsModal에 isDirtyRef prop 추가 (API 키 입력 중, 카테고리 편집 중일 때 dirty 판단)
  - dirty 상태에서 이동 시 "변경사항을 저장하지 않고 이동하시겠습니까?" confirm 대화상자 표시
  - 새 녹음 버튼에도 동일한 dirty check 적용
  - TypeScript 타입 체크 통과, 백엔드 테스트 90건 전체 pass
  - 코드리뷰: 이슈 없음 (통과)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/app/page.tsx, frontend/components/SettingsModal.tsx
- 푸시 여부: origin/main 푸시 완료 (d0cfc34)

## 2026-08-26 (작업 PC: 로컬) — 세션 41 (목소리 프로필 추출 버그 수정 PR #56)
- 브랜치: main (PR #56 squash 머지, adde99f)
- 완료:
  - 설정 > 목소리 프로필 > "기존 회의에서 추출" 버튼 무반응 버그 수정
  - 프론트엔드: fetch 응답 상태(res.ok) 체크 추가, 에러 시 alert 표시, extracting 로딩 상태 추가
  - 백엔드: txt 업로드 회의에서 프로필 추출 시도 시 사용자 친화적 에러 메시지 반환
  - QA 검증 15/15 PASS, 백엔드 테스트 90건 전체 pass
- 다음 할 일: 다음 기능 기획
- 관련 파일: frontend/components/SettingsModal.tsx, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (adde99f)

## 2026-08-26 (작업 PC: 로컬) — 세션 40 (PDF 다크모드 + 트랜스크립트 제거 PR #55)
- 브랜치: main (PR #55 squash 머지, 3260bdd)
- 완료:
  - 다크모드에서 PDF 저장 시 흰 배경에 흰 글자 출력 문제 수정
    - html/body에 color-scheme: light 강제, .dark 클래스 무력화
    - 모든 텍스트 요소에 !important로 명시적 라이트 색상 지정
    - Tailwind className → inline style로 컨테이너 색상 고정
  - PDF에서 대화 스크립트(트랜스크립트) 섹션 완전 제거, 요약만 포함
  - 미사용 parseTranscript 함수 제거
  - 코드리뷰: 이슈 없음 (통과)
  - 백엔드 테스트 90건 전체 pass
- 다음 할 일: 다음 기능 기획
- 관련 파일: frontend/app/print/[id]/page.tsx
- 푸시 여부: origin/main 푸시 완료 (3260bdd)

## 2026-08-26 (작업 PC: 로컬) — 세션 39 (ClovaNote txt 형식 파싱 수정 PR #54)
- 브랜치: main (PR #54 squash 머지, e1a8393)
- 완료:
  - 백엔드: `_parse_txt_transcript()` 함수 추가 — ClovaNote 내보내기 형식 자동 감지 및 표준 형식 변환
  - ClovaNote 형식: `참석자 N MM:SS\n텍스트` → `[MM:SS] SPEAKER_XX: 텍스트` 변환
  - 멀티라인 발화 텍스트를 단일 줄로 병합
  - 헤더 영역(제목/날짜/이름) 자동 건너뛰기 (false positive 방지: `\d{2}:\d{2}` 엄격 매칭)
  - suggested_names에 원본 화자 이름 매핑 (TranscriptEditor에서 자동 표시)
  - 테스트 4건 추가 (ClovaNote 업로드 통합, 표준/ClovaNote/미인식 형식 단위 테스트, 전체 90 pass)
- E2E 테스트 완료: 실제 ClovaNote 파일(회의록.txt, 참석자 5명/91발화) 브라우저 업로드 → 화자 자동 파싱 → TranscriptEditor 렌더링 → 문서 생성(Claude 요약) → done 전환 모두 정상
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/main.py, backend/tests/test_upload.py
- 푸시 여부: origin/main 푸시 완료 (e1a8393)

## 2026-08-26 (작업 PC: 로컬) — 세션 38 (txt 업로드 speakers 타입 불일치 수정 PR #53)
- 브랜치: main (PR #53 squash 머지, f33d5cc)
- 완료:
  - 백엔드: txt 업로드 시 speakers를 빈 딕셔너리({}) → 화자 파싱 배열([])로 변경
  - 백엔드: `\w+` regex로 `[MM:SS] SPEAKER_XX:` 패턴 자동 파싱, suggested_names/suggested_speakers 필드 추가
  - 프론트: ProgressCard.tsx에 Array.isArray 방어 코드 추가 (딕셔너리→배열 변환)
  - 중복 import re 제거 (모듈 최상단에 이미 존재)
  - 코드리뷰: regex `[^:]+` 과도한 패턴 → `\w+`로 제한 (비화자 텍스트 캡처 방지)
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/main.py, frontend/components/ProgressCard.tsx
- 푸시 여부: origin/main 푸시 완료 (f33d5cc)

## 2026-08-26 (작업 PC: 로컬) — 세션 37 (녹음 중 메모 + 북마크 PR #52)
- 브랜치: main (PR #52 squash 머지, 6a12472)
- 완료:
  - 기능 B (트랜스크립트 전문 검색): PR #51로 이미 머지됨 확인, 스킵
  - 기능 A (녹음 중 메모 + 북마크):
    - recording_notes 테이블 신규 (database.py)
    - POST/GET/DELETE /api/jobs/{job_id}/notes API 3개
    - RecordingZone: 녹음 중 메모 입력 + 북마크(깃발) 버튼, notesRef로 stale closure 방지
    - MainArea: done 상태에서 녹음 중 메모 표시 + 타임스탬프 클릭 시 오디오 이동
    - RecordingNote 인터페이스 (types/index.ts)
    - test_recording_notes.py 5건 추가 (전체 86 pass)
  - 코드리뷰: stale closure bug 발견 → notesRef 사용으로 수정 후 머지
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/{database,main}.py, frontend/components/{RecordingZone,MainArea}.tsx, frontend/types/index.ts, backend/tests/test_recording_notes.py
- 푸시 여부: origin/main 푸시 완료 (6a12472)

## 2026-08-26 (작업 PC: 로컬) — 세션 35 (타임스탬프→오디오 이동 + 카테고리 프롬프트 템플릿 PR #50)
- 브랜치: main (PR #50 squash 머지, 2f1980a)
- 완료:
  - 타임스탬프 클릭→오디오 이동: AudioPlayer forwardRef+useImperativeHandle seekTo, MainArea audioPlayerRef, SummaryPanel parseInlineTimestamps
  - 카테고리별 요약 프롬프트 템플릿: DB prompt_template 컬럼, CRUD API, SettingsModal textarea UI
  - 코드리뷰 2건 수정: create_category prompt_template 누락 + 액션 아이템 타임스탬프 파싱
- 다음 할 일: 3번(트랜스크립트 전문 검색) 또는 4번(녹음 중 북마크) 기획
- 관련 파일: backend/app/{database,main,summarizer}.py, frontend/components/{AudioPlayer,MainArea,SummaryPanel,SettingsModal}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (2f1980a)

## 2026-08-26 (작업 PC: 로컬) — 세션 34 (노이즈 제거 + 요약 별점 PR #49)
- 브랜치: main (PR #49 squash 머지, 36bc929)
- 완료:
  - 오디오 노이즈 제거: FFmpeg afftdn/highpass/lowpass 필터 조건부 적용 (설정 ON/OFF)
  - GET/PUT /api/settings/denoise 엔드포인트
  - SettingsModal 일반 탭 노이즈 제거 토글 스위치
  - 요약 품질 별점: jobs 테이블 rating 컬럼 추가
  - PATCH /api/jobs/{id}/rating, GET /api/stats/ratings API
  - SummaryPanel ★★★★★ 별점 UI + 저장 확인 메시지
  - MeetingCard 카드 하단 별점 표시
  - 코드리뷰: 80점 이상 이슈 없음 → 통과
- 테스트 완료:
  - 별점 클릭 → PATCH 저장 → "피드백 감사합니다" 표시 → /meetings 카드 별 표시 ✓
  - 노이즈 제거 토글 ON → API {"enabled": true} 저장 확인 ✓
- 다음 할 일: 다음 기능 기획 (product-manager에게 요청)
- 관련 파일: backend/app/{audio_processor,database,main}.py, frontend/components/{SettingsModal,SummaryPanel,MeetingCard,MainArea}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (36bc929)

## 2026-08-26 (작업 PC: 로컬) — 세션 33 (목소리 프로필 자동 매칭 PR #48)
- 브랜치: main (PR #48 squash 머지, 632daa3)
- 완료:
  - 백엔드: voice_profiles 테이블, embedding CRUD, Voice Profile API 7개
  - 백엔드: PyAnnote embedding 추출 함수 (extract_speaker_embedding, extract_embeddings_from_diarization)
  - 백엔드: match_speaker_to_profiles() 코사인 유사도 매칭 (임계값 0.75)
  - 백엔드: job_queue.py awaiting_edit 전 자동 매칭 + suggested_speakers SSE 전달
  - 백엔드: GET/PUT /api/voice-profiles/threshold 엔드포인트
  - 프론트: SettingsModal 화자 탭 → 목소리 프로필 관리 (목록, 직접 녹음, 기존 회의 추출, 임계값 슬라이더)
  - 프론트: TranscriptEditor 자동 매칭 결과 표시 (이름 + 신뢰도 배지)
  - 프론트: SpeakerMapper "이 목소리를 프로필로 저장" 체크박스 추가
  - 코드리뷰 3건 발견 → 수정 완료:
    1. confidence * 100 이중변환 제거 (TranscriptEditor.tsx)
    2. suggested_speakers SSE → DB 저장 + ProgressCard/MainArea 전달 연결
    3. rename-speakers 엔드포인트 추가 (main.py)
- 다음 할 일: 실제 서버 실행 후 end-to-end 테스트 (목소리 프로필 등록 → 녹음 → 자동매칭 확인)
- 관련 파일: backend/app/{database,audio_processor,job_queue,main}.py, frontend/components/{SettingsModal,TranscriptEditor,SpeakerMapper,ProgressCard,MainArea}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (632daa3)

## 2026-08-26 (작업 PC: 로컬) — 세션 31 (설정 UX 개선 PR #47)
- 브랜치: main (PR #47 squash 머지, 458f214)
- 완료:
  - 설정 패널: 모달 → 메인 영역 페이지 방식으로 변환 (← 돌아가기)
  - Claude 탭 제거, 카테고리별 모델 선택 드롭다운 추가 (Opus/Sonnet/Haiku)
  - categories 테이블 model 컬럼 추가, CRUD/backup/restore 반영
  - 기본 회의 제목 설정 항목 제거
  - "새 회의 녹음" → "새 녹음" 용어 수정
  - 다크모드 텍스트 색상 버그 수정
  - 코드리뷰: backup/restore model 누락 + 저장버튼 비활성화 2건 발견→수정
- QA: 8/8 통과 (블로커 없음). 경미한 이슈: 복원 배너 다크모드 미적용 (후속 처리)
- 현재 상태: main 최신 (458f214)
- 다음 할 일: 없음
- 관련 PR: #47
- 푸시 여부: origin/main 푸시 완료

## 2026-08-26 (작업 PC: 로컬) — 세션 30 (기능 2개 완료)
- 브랜치: main (PR #43, #45 squash 머지)
- 완료:
  - 선택 모드 일괄 북마크: ★ 버튼, Promise.all 병렬 API 호출, QA 통과 (PR #43)
  - 회의 제목 인라인 편집: Sidebar 더블클릭→input, ref guard로 이중호출 방지, MainArea 편집, Esc 취소 시 PATCH 방지 (PR #45)
  - 날짜 범위 필터: 이미 구현 완료 확인 (추가 작업 불필요)
- 코드리뷰: PR #45에서 버그 3개 발견 → 수정 후 재푸시 → 재리뷰 통과
- QA: PR #43 QA 통과 (북마크 토글, 선택모드 해제 확인)
- 현재 상태: main 최신 (9d37a0b)
- 다음 할 일: 없음
- 관련 PR: #43 (머지), #44 (close, #45로 대체), #45 (머지)
- 푸시 여부: origin/main 푸시 완료
- 추가: QA가 발견한 Sidebar 더블클릭 2회차 버그 (span 단일클릭 버블링) → PR #46 코드리뷰 통과 → 머지 (c2fb016)

## 2026-08-26 (작업 PC: 로컬) — 세션 29 (기능 2개 + 기존 확인)
- 브랜치: main (PR #41 squash 머지, PR #42 close)
- 완료:
  - 월별 통계 차트: recharts BarChart, GET /api/stats/monthly, MonthlyChart 컴포넌트 (PR #41)
  - 다중 선택 삭제: 체크박스, 선택 모드, 일괄 삭제 (PR #41에 포함)
  - 인쇄/PDF: 이미 /print/[id] 페이지로 구현 완료 확인 (추가 작업 불필요)
- QA: PR #41에 bulk-select 중복 포함 발견 → PR #42 close 처리
- 현재 상태: main 최신 (8029a61)
- 다음 할 일: 없음
- 관련 PR: #41 (머지), #42 (close)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-26 (작업 PC: 로컬) — 세션 28 (기능 4개 완료)
- 브랜치: main (PR #37~#40 squash 머지)
- 완료: backend-dev + frontend-dev × 2 + qa-engineer 병렬 구현
  - 전체 텍스트 검색 개선: summary/transcript LIKE 검색 + snippet 추출 (PR #37)
  - 녹음 일시정지/재개: MediaRecorder pause/resume, ⏸/▶ 버튼, QA 통과 (PR #38)
  - 카테고리 뱃지: MeetingCard에 카테고리 색상 뱃지 5종 (PR #39)
  - 검색 결과 snippet 표시: 검색어 주변 텍스트 MeetingCard에 표시 (PR #40)
- 현재 상태: main 최신 (1e23a43)
- 다음 할 일: 없음
- 관련 PR: #37, #38, #39, #40
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 27 (사이드바 + 카드 기능)
- 브랜치: main (직접 커밋 + PR #36)
- 완료:
  - /meetings 카드 북마크 토글 버튼 추가 (313bec6)
  - /meetings 카드 삭제 버튼 추가 + confirm 다이얼로그 (6a969ee)
  - 사이드바 접기/펼치기: w-0↔w-60 transition, «/» 버튼, [ 단축키, localStorage (PR #36)
- 현재 상태: main 최신 (75960af)
- 다음 할 일: 없음
- 관련 PR: #36
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 26 (다크모드 버그 수정)
- 브랜치: main (PR #34 squash 머지)
- 완료: 다크모드 전체 영역 적용 버그 수정
  - 기존: 상단 바만 다크모드 적용됨
  - 수정: Sidebar, MainArea, SummaryPanel 등 12개 컴포넌트 dark: 클래스 일괄 보완 (PR #34)
  - 잔여 이슈 추가 수정: MeetingCard 상태 뱃지, SummaryPanel 리스트, SettingsModal 버튼, TranscriptEditor 화자 색상 (PR #35)
  - 확인: 코드 리뷰 이슈 0건 (클린 패스)
- 현재 상태: main 최신 (add523f)
- 다음 할 일: 사이드바 접기/펼치기 기능 (product-manager 기획 대기 중)
- 관련 PR: #34, #35
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 25 (신규 기능 3개 완료)
- 브랜치: main (PR #31~#33 squash 머지)
- 완료: director 직접 구현 (3가지 기능)
  - 설정 백업/복원: GET /api/settings/backup, POST /api/settings/restore, SettingsModal 내보내기/가져오기 UI (PR #31)
  - Claude 프롬프트 미리보기: 카테고리 편집/생성 시 미리보기 버튼, 샘플 대화 삽입 프롬프트 모달 (PR #32)
  - Notion 연동 상태 표시: MeetingCard Notion 배지, MainArea 상태 배지 (등록됨/미등록) (PR #33)
- 코드 리뷰: PR #31에서 민감 키 평문 노출 이슈 발견 → 수정 후 머지, PR #32/#33 클린 패스
- 현재 상태: main 최신
- 다음 할 일: 없음
- 관련 PR: #31, #32, #33
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 24 (신규 기능 3개 완료)
- 브랜치: main (PR #27~#29 squash 머지)
- 완료: director + frontend-dev 팀 구현 (3가지 기능)
  - 검색 결과 하이라이트: /meetings 검색어 일치 텍스트 노란색 형광 강조, XSS 안전 (PR #27)
  - 공유 링크 URL 라우팅: /meetings/[id] 직접 접근, 링크 복사 버튼 (PR #28)
  - Sidebar URL 동기화: 클릭 시 history.pushState, popstate 뒤로 가기 지원 (PR #30)
  - 키보드 단축키 도움말: ? 키로 단축키 목록 모달, useKeyboardShortcuts 훅 확장 (PR #29)
- 현재 상태: main 최신 (21c6603)
- 다음 할 일: 없음
- 관련 PR: #27, #28, #29, #30
- 푸시 여부: origin/main 푸시 완료

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


