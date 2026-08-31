# Meeting Assistant - 개발 가이드 (v2 — 브라우저 직접 녹음)

> 이 문서는 개발 시작 전 Claude Code가 읽는 기준 문서입니다.

---

## 1. 프로젝트 개요

M1 Mac 로컬 환경에서 **브라우저로 직접 녹음**하면
화자 분리(PyAnnote) + STT(MLX-Whisper) + 텍스트·참석자 편집 + Claude 요약을 거쳐
마크다운 회의록을 자동 생성하는 웹 애플리케이션.

### 핵심 플로우 (업로드 없음, 브라우저 직접 녹음)
```
[브라우저 녹음 시작] → [녹음 중 실시간 타이머]
        ↓
[녹음 중지] → [음성 다운로드 가능] + [백엔드로 오디오 전송]
        ↓
[STT + 화자 분리] → 텍스트 스크립트 생성
        ↓
[텍스트·참석자 직접 편집 UI] → [텍스트 다운로드 가능]
        ↓
[회의록 생성] → Claude 요약 → 마크다운 회의록
        ↓
[Notion 등록] (선택)
```

---

## 2. 기술 스택

| 역할 | 기술 |
|------|------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| 오디오 변환 | ffmpeg-python |
| 화자 분리 | pyannote.audio (MPS 가속) |
| STT | mlx-whisper (language="ko") |
| 회의록 생성 | Claude Code CLI (`claude -p` subprocess) |
| Notion 연동 | notion-client (선택) |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS |
| 브라우저 녹음 | MediaRecorder API (webm/opus) |
| 실시간 진행률 | Server-Sent Events (SSE) |
| Job 영속성 | SQLite (`backend/meetings.db`) |
| 동시 처리 | asyncio Queue (최대 1개) |

---

## 3. 디렉토리 구조

```
meeting-jr/
├── backend/
│   ├── input/           # 녹음된 오디오 저장
│   ├── output/          # 생성된 마크다운 저장
│   ├── meetings.db      # SQLite
│   ├── speakers.json    # 화자 이름 기억
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── job_queue.py
│   │   ├── audio_processor.py
│   │   ├── summarizer.py
│   │   ├── notion_sync.py
│   │   └── settings_manager.py  # 설정값 암호화 저장/조회
│   ├── tests/
│   │   ├── test_search_jobs.py
│   │   └── test_meetings_endpoint.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # ?job=<id> 파라미터 처리
│   │   ├── globals.css
│   │   └── meetings/
│   │       └── page.tsx          # /meetings 회의 목록 페이지
│   ├── components/
│   │   ├── RecordingZone.tsx     # 핵심: 녹음 UI
│   │   ├── Sidebar.tsx           # 전체 목록 보기 링크 포함
│   │   ├── AudioPlayer.tsx
│   │   ├── TranscriptEditor.tsx  # 핵심: 텍스트+참석자 편집
│   │   ├── SummaryPanel.tsx
│   │   ├── SpeakerMapper.tsx
│   │   ├── ProgressCard.tsx
│   │   ├── MeetingCard.tsx       # 회의 목록 카드 컴포넌트
│   │   ├── Pagination.tsx        # 페이지 번호 네비게이션
│   │   └── SettingsModal.tsx     # 설정 모달 (API 키, 기본 제목)
│   ├── next.config.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docs/
│   └── superpowers/
│       ├── plans/                # 구현 계획 문서
│       └── specs/                # 설계 문서
├── DEVGUIDE.md
└── CLAUDE.md
```

---

## 4. 처리 파이프라인

```
[브라우저: MediaRecorder API로 녹음]
  → 녹음 중 실시간 타이머 표시
  → 녹음 완료 시 webm Blob 생성
        ↓
[다운로드 옵션 즉시 제공]
  → 음성 파일 다운로드 버튼 (webm)
        ↓
[POST /api/record  — webm Blob 전송]
  → backend input/ 저장
  → job_id 반환
  → asyncio Queue에 추가
        ↓
[FFmpeg: webm → 16kHz 모노 WAV]
        ↓
[PyAnnote: 화자 분리] (MPS 가속, CPU 폴백)
        ↓
[MLX-Whisper: STT, language="ko"]
        ↓
[화자-텍스트 매핑 → input/{job_id}.txt]
  형식: [MM:SS] SPEAKER_00: 텍스트
        ↓
[SSE: stage="awaiting_edit" 전송]
        ↓
[프론트: TranscriptEditor 표시]
  → 텍스트 자유 편집 (textarea)
  → 참석자 이름 편집 (SPEAKER_00 → 실제 이름)
  → 텍스트 파일 다운로드 버튼 (.txt)
        ↓
[POST /api/jobs/{job_id}/finalize]
  → 편집된 transcript + speaker_map 전송
  → Claude CLI로 회의록 생성
        ↓
[결과 화면: 오디오 플레이어 + 편집된 스크립트 + 요약 패널]
```

---

## 5. UI 디자인 명세

### 5-1. 전체 레이아웃

```
┌────────────────────┬──────────────────────────────────────────────────────┐
│  회의 목록   240px  │                     메인 영역                        │
│────────────────────│  [회의 제목 인라인 편집]            [Notion 내보내기] │
│  [● 새 회의 녹음]   │──────────────────────────────────────────────────────│
│                    │                                                      │
│  [완료] 팀 주간회의 │  ← 상태에 따라 조건부 렌더링                          │
│  2026-08-22  45분  │                                                      │
│                    │  [녹음 화면 / 처리중 / 편집 / 완료결과]               │
│  [완료] 기획 회의   │                                                      │
│  2026-08-20  30분  │                                                      │
│  [실패] ... [재시도]│                                                      │
└────────────────────┴──────────────────────────────────────────────────────┘
```

### 5-2. 컬러 시스템

| 항목 | 값 |
|------|-----|
| 페이지 배경 | #F8F9FA |
| 카드 배경 | #FFFFFF |
| 액센트 (파란) | #2563EB |
| 녹음 버튼 | #EF4444 (빨강) |
| 화자 1 버블 | #EBF4FF / #1D4ED8 |
| 화자 2 버블 | #F0FDF4 / #166534 |
| 화자 3 버블 | #FFF7ED / #9A3412 |
| 화자 4 버블 | #FAF5FF / #6B21A8 |
| 사이드바 배경 | #1E293B |
| 사이드바 텍스트 | #F1F5F9 |

### 5-3. 상태별 화면

**녹음 화면 (초기 / 새 회의)**
```
┌────────────────────────────────────────────────────┐
│                                                    │
│              ● 00:00:00                            │
│                                                    │
│         [ ● 녹음 시작 ]                            │
│                                                    │
│    녹음 후 자동으로 텍스트로 변환됩니다             │
│                                                    │
└────────────────────────────────────────────────────┘
```

**녹음 중 화면**
```
┌────────────────────────────────────────────────────┐
│                                                    │
│           ● 00:02:34  (깜빡이는 빨간 점)           │
│         ━━━━━━━━━━━━━━━━━━━ (음파 시각화)          │
│                                                    │
│         [ ■ 녹음 중지 ]                            │
│                                                    │
└────────────────────────────────────────────────────┘
```

**녹음 완료 직후 (STT 처리 전)**
```
┌────────────────────────────────────────────────────┐
│  녹음 완료  00:02:34                               │
│  [ ↓ 음성 다운로드 (.webm) ]                       │
│                                                    │
│  처리 중...                                        │
│  [완료] FFmpeg 변환    100%                        │
│  [진행] 화자 분리       67%  ████████░░           │
│  [대기] STT 변환       대기                        │
└────────────────────────────────────────────────────┘
```

**텍스트·참석자 편집 화면 (STT 완료 후)**
```
┌────────────────────────────────────────────────────┐
│  참석자                          [ ↓ 텍스트 다운로드 ]│
│  SPEAKER_00  [ 김팀장________ ]                    │
│  SPEAKER_01  [ 손재락________ ]                    │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ [00:00] SPEAKER_00: 안녕하세요, 회의 시작할게요 │  │
│  │ [00:15] SPEAKER_01: 네, 준비됐습니다          │  │
│  │  ... (자유 편집 가능한 textarea)              │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│              [ 회의록 생성 ]                       │
└────────────────────────────────────────────────────┘
```

**완료 결과 화면**
- 오디오 플레이어 (녹음본 재생)
- 좌: 확정된 스크립트 (읽기 전용, 타임스탬프 클릭 시 오디오 이동)
- 우: 요약 패널 (TL;DR / 주요 논의 / 결정 사항 / 액션 아이템)
  - 우상단 [편집] / [↓ 다운로드] 버튼

### 5-4. 사이드바

```
[● 새 회의 녹음]  ← 빨간 녹음 버튼
─────────────────
[완료] 팀 주간회의 / 2026-08-22 / 45분
[처리중] 기획 회의 (파란 스피너)
[실패] ... [재시도]   ← 우클릭 → 삭제
```

### 5-5. UX 기능

| 기능 | 구현 |
|------|------|
| 브라우저 녹음 | MediaRecorder API (webm/opus) |
| 실시간 타이머 | setInterval 1초 |
| 음파 시각화 | Web Audio API AnalyserNode (선택, 간단히) |
| 음성 다운로드 | Blob URL → `<a download>` |
| 텍스트 다운로드 | 편집된 스크립트 → .txt Blob 다운로드 |
| 텍스트 자유 편집 | textarea (전체 스크립트 편집) |
| 참석자 이름 편집 | SPEAKER_XX → 실제 이름 input |
| 처리 완료 알림 | Browser Notification API |
| 회의 제목 편집 | 메인 헤더 클릭 → 인라인 편집 |
| 요약 편집+저장 | SummaryPanel 편집 토글 + PATCH /api/jobs/{id}/summary |
| 회의 삭제 | 사이드바 우클릭 → 삭제 |
| 실패 재시도 | [재시도] 버튼 |

---

## 6. API 엔드포인트

<!-- API_TABLE:BEGIN -->
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/record` | 브라우저에서 녹음된 webm Blob을 받아 처리 큐에 등록한다. |
| POST | `/api/upload` | 오디오 또는 텍스트 파일을 업로드하여 처리 큐에 등록한다. |
| GET | `/api/progress/{job_id}` | SSE 진행률 스트림 |
| GET | `/api/jobs` | 전체 Job 목록 |
| GET | `/api/jobs/{job_id}` | Job 상세 (transcript, summary 포함) |
| POST | `/api/jobs/{job_id}/finalize` | 편집된 transcript와 speaker_map을 받아 Claude 요약을 시작한다. |
| POST | `/api/jobs/{job_id}/regenerate` | done 상태 회의의 요약을 다른 카테고리로 재생성한다. |
| POST | `/api/jobs/{job_id}/retry` | 실패 재시도 |
| DELETE | `/api/jobs/{job_id}` | 회의 삭제 |
| PATCH | `/api/jobs/{job_id}/title` | 제목 편집 |
| PATCH | `/api/jobs/{job_id}/bookmark` | 북마크 토글 |
| PATCH | `/api/jobs/{job_id}/memo` | 회의 메모 저장 |
| PATCH | `/api/jobs/{job_id}/tags` | 태그 저장 |
| PATCH | `/api/jobs/{job_id}/transcript` | 트랜스크립트 수정 저장 |
| PATCH | `/api/jobs/{job_id}/summary` | 요약 내용 저장 |
| POST | `/api/insights` | 크로스 회의 인사이트 (keyword/날짜 필터 → claude -p) |
| POST | `/api/jobs/{job_id}/ask` | AI 추가 질의 (claude -p) |
| POST | `/api/jobs/{job_id}/share` | 공유 토큰 생성 |
| GET | `/api/shared/{token}` | 읽기 전용 공유 페이지 데이터 |
| DELETE | `/api/jobs/{job_id}/share` | 공유 토큰 폐기 |
| GET | `/api/action-items` | 전체 회의의 액션 아이템 통합 조회. |
| PATCH | `/api/jobs/{job_id}/action-items` | 액션 아이템 수정 |
| GET | `/api/jobs/{job_id}/download` | 마크다운 다운로드 |
| GET | `/api/jobs/{job_id}/audio` | 녹음 오디오 서빙 |
| GET | `/api/stats` | done 상태 회의의 통계를 반환한다. |
| GET | `/api/stats/monthly` | 최근 6개월 월별 회의 횟수 + 총 시간(분)을 반환한다. |
| GET | `/api/speakers` | 저장된 화자 이름 목록 |
| POST | `/api/speakers` | 화자 이름을 speakers.json에 등록한다. |
| DELETE | `/api/speakers/{name}` | 저장된 화자 이름 삭제 |
| POST | `/api/jobs/{job_id}/export-notion` | Notion 등록 (mode: new\|update) |
| GET | `/api/settings/claude-status` | Claude CLI 인증 상태를 반환한다. |
| POST | `/api/settings/claude-logout` | Claude CLI 로그아웃을 실행한다. |
| GET | `/api/settings/default-title` | 기본 회의 제목을 반환한다. 미설정 시 빈 문자열. |
| GET | `/api/settings/claude-model` | 현재 설정된 Claude 모델 반환. 미설정 시 기본값. |
| GET | `/api/settings/claude-prompt` | 현재 설정된 프롬프트 반환. 미설정 시 빈 문자열. default도 함께 반환. |
| GET | `/api/settings` | 각 설정 키의 설정 여부만 반환 (값 자체는 노출 안 함). |
| PATCH | `/api/settings` | 설정값을 암호화하여 DB에 저장. 빈 문자열이면 해당 키 삭제. |
| GET | `/api/settings/backup` | speakers.json + settings + categories를 JSON으로 내보낸다. |
| POST | `/api/settings/restore` | 백업 JSON 파일에서 설정을 복원한다. |
| GET | `/api/meetings` | 제목+요약+스크립트 검색 + 카테고리/날짜/태그 필터 + 페이지네이션. |
| GET | `/api/tags` | 전체 사용된 태그 목록 반환. |
| GET | `/api/categories` | 카테고리 목록 반환 (sort_order 오름차순). |
| POST | `/api/categories` | 사용자 카테고리 생성. |
| PATCH | `/api/categories/{cat_id}` | 카테고리 이름/아이콘/설명/프롬프트 수정. |
| DELETE | `/api/categories/{cat_id}` | 카테고리 삭제. is_builtin=1이면 거부. |
| POST | `/api/categories/{cat_id}/reset` | 내장 카테고리 프롬프트를 DEFAULT로 복원. |
| POST | `/api/jobs/{job_id}/notes` | 녹음 중 메모/북마크 일괄 저장. |
| GET | `/api/jobs/{job_id}/notes` | 해당 job의 노트 목록. |
| DELETE | `/api/jobs/{job_id}/notes/{note_id}` | 개별 노트 삭제. |
| GET | `/api/jobs/{job_id}/related` | 현재 회의와 키워드가 겹치는 다른 회의를 최대 5개 반환한다. |
| GET | `/api/export` | 모든 회의를 ZIP으로 내보낸다. |
| POST | `/api/jobs/{job_id}/rematch` | 완료된 회의의 화자를 voice profile과 재매칭. |
| POST | `/api/jobs/{job_id}/apply-match` | 매칭된 화자명을 transcript와 speakers에 적용. |
| GET | `/api/voice-profiles` | 목소리 프로필 목록 (embedding 제외). |
| POST | `/api/voice-profiles` | 새 목소리 프로필 생성 (오디오 → embedding 추출). |
| GET | `/api/voice-profiles/threshold` | 매칭 임계값 조회. |
| PUT | `/api/voice-profiles/threshold` | 매칭 임계값 설정. |
| DELETE | `/api/voice-profiles/{profile_id}` | 프로필 삭제. |
| POST | `/api/voice-profiles/{profile_id}/add-sample` | 기존 프로필에 샘플 추가 (누적 평균). |
| POST | `/api/jobs/{job_id}/rename-speakers` | 화자 이름 매핑을 적용한다 (요약 없이 speaker_map만 저장). |
| POST | `/api/series` | 시리즈 생성. |
| GET | `/api/series` | 시리즈 목록. |
| GET | `/api/series/{series_id}` | 시리즈 상세 + 연결 회의 목록. |
| PATCH | `/api/series/{series_id}` | 시리즈 수정. |
| DELETE | `/api/series/{series_id}` | 시리즈 삭제. |
| PATCH | `/api/jobs/{job_id}/series` | 회의에 시리즈 할당/해제. done 상태에서 할당 시 후속조치 자동 생성. |
| GET | `/api/jobs/{job_id}/followup` | 후속조치 조회. |
| PATCH | `/api/jobs/{job_id}/followup` | 후속조치 사용자 확정 (user_status, confirmed). |
| POST | `/api/jobs/{job_id}/followup/generate` | 후속조치 대조를 (재)생성한다. claude -p 사용. |
| GET | `/api/jobs/{job_id}/participation` | 화자별 발언 시간·비율·턴수 분석. |
| POST | `/api/jobs/{job_id}/save-speaker-profile` | 완료된 회의의 화자를 프로필로 저장. |
| GET | `/api/settings/denoise` | 노이즈 제거 설정 조회 |
| PUT | `/api/settings/denoise` | 노이즈 제거 설정 변경 |
| PATCH | `/api/jobs/{job_id}/rating` | 별점(1~5) 저장. |
| GET | `/api/stats/ratings` | 카테고리별 평균 평점. |
<!-- API_TABLE:END -->

### SSE 이벤트 형식
```json
{"stage": "converting|diarizing|transcribing|awaiting_edit|summarizing|done|error", "progress": 0~100, "message": "..."}
```
`awaiting_edit` 단계에서 transcript, speakers, suggested_names 추가 포함:
```json
{"stage": "awaiting_edit", "progress": 100, "message": "텍스트를 확인하고 편집해주세요.", "transcript": "...", "speakers": ["SPEAKER_00"], "suggested_names": {}}
```

---

## 7. 회의록 마크다운 형식 (Claude 출력)

```markdown
# [회의 주제]

- 일시: YYYY-MM-DD
- 참석자: 김팀장, 손재락, ...
- 회의 목적: ...

## 핵심 요약 (TL;DR)
...

## 주요 논의 및 안건
- 안건 1: ...

## 주요 결정 사항
- 결정 1

## 액션 아이템 (To-Do)
- [ ] @담당자 - 내용 (기한: MM/DD)

## 이슈 및 리스크
- 이슈 1
```

---

## 8. 환경 변수

`.env` 파일 (서버 시작 전 필요):
```env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxx
PORT=8000
MAX_UPLOAD_MB=500
```

앱 실행 후 설정 모달에서 저장 (DB 암호화 저장):
```
NOTION_API_KEY=secret_xxxxxxxx      # 선택
NOTION_DATABASE_ID=xxxxxxxx         # 선택
DEFAULT_MEETING_TITLE=팀 주간회의   # 선택, 미설정 시 '회의록'
```

---

## 9. 실행 방법

```bash
# 백엔드
cd backend
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000

# 프론트엔드
cd frontend
npm run dev   # http://localhost:3000
```

---

## 10. 확정 결정사항

| 항목 | 결정 |
|------|------|
| 입력 방식 | 브라우저 MediaRecorder API 직접 녹음 (파일 업로드 없음) |
| 오디오 포맷 | webm/opus (브라우저 기본) → FFmpeg로 WAV 변환 |
| 텍스트 편집 | STT 완료 후 textarea 자유 편집 |
| 참석자 편집 | SPEAKER_XX → 실제 이름 input |
| 다운로드 | 음성(.webm), 텍스트(.txt) 모두 브라우저에서 직접 |
| Claude 요약 | `claude -p` CLI subprocess |
| Job 영속성 | SQLite |
| 동시 처리 | asyncio Queue 최대 1개 |
| ANTHROPIC_API_KEY | 사용 안 함 |
| 설정 저장 | DB settings 테이블 암호화 저장 (Fernet), SECRET_KEY는 .env |
| 회의 목록 페이지 | `/meetings` 라우트, 12개/페이지, 제목+요약 LIKE 검색 |
| 기본 회의 제목 | 설정 모달에서 입력, 미설정 시 '회의록' |
| Notion 제목 형식 | `[회의날짜 HH:MM] 회의제목` + 페이지 상단에 업로드 일시 기록 |
| 에이전트 팀 | product-manager → director → backend/frontend/ai-engineer → qa |
| 파일 업로드 | 오디오(webm/mp3/m4a/wav) + ClovaNote txt 지원 |
| txt 파싱 | 표준(`[MM:SS] SPEAKER:`) + ClovaNote(`참석자 N MM:SS`) 자동 감지 |
| 액션아이템 대시보드 | 전체 회의 통합 조회, assignee/done 필터, 페이지네이션 |
| 공유 링크 | 토큰 기반 읽기 전용 공유, 토큰 폐기 가능 |
| AI 추가 질의 | done 상태 회의에 대해 claude -p로 후속 질문 |
| 크로스 회의 인사이트 | 복수 회의 요약을 context로 묶어 claude -p 질의 |
| 발언 참여도 분석 | diarization 우선, transcript 폴백, 수평 BarChart 시각화 |
| 회의 시리즈 | 카테고리(유형)와 별도로 반복 회의 인스턴스를 묶는 구조 |
| 후속조치 자동 대조 | 시리즈 직전 회의 미완료 액션아이템을 claude -p로 대조, AI 추정 + 사용자 확정 이원화 |
| 후속조치 격리 | 대조 실패가 요약 파이프라인에 영향 없음 (try-except 격리, SSE 흐름 불변) |
| 음성 프로필 | PyAnnote 임베딩 기반 화자 자동 인식, 프로필 CRUD |
| PDF 출력 | 라이트 모드 강제, 트랜스크립트 제외 요약만 |
| 화자 이름 클릭 점프 | Transcript 화자 이름 클릭 → 첫 발언으로 시킹+스크롤, 반복 클릭 시 다음 발언 순환. ParticipationChart 범례 클릭 → 항상 첫 발언 고정 |
| identity-mapped 판별 | speaker_map 키 중 `SPEAKER_\d+` 패턴에 매칭되지 않는 실명 키가 하나라도 있으면 identity-mapped 회의로 판별. 부분 apply-match 후 혼합 상태(`{"SPEAKER_00":"김과장","엄마":"엄마"}`)도 identity-mapped로 올바르게 처리. participation API의 `_is_identity_mapped` 지역 변수로 판별하고, apply_match는 `raw_label not in speakers`로 라벨 단위 판별 |
| 기존 불일치 데이터 처리 | DB 마이그레이션 없이 조회 시점 reconciliation. participation API의 `_resolve_speaker_display`가 diarization↔transcript 구간 overlap 면적 방식으로 런타임에 display_name 결정 |
| apply-match 충돌 해소 | **"충돌"의 정의**: 서로 다른 diar 라벨이 같은 `current_name`으로 수렴하는 경우 (예: SPEAKER_00·SPEAKER_01 모두 "김팀장"으로 해석). **충돌 없는 경우**: 기존 원자적 정규식 치환(`replace_map` + `re.sub` 콜백). **충돌 시**: diarization 타임스탬프 기반 라인별 치환 — 각 transcript 라인의 `[MM:SS]`를 diar 세그먼트 구간과 **overlap 면적**(=`min(seg_e, line_end) − max(seg_s, line_start)`)으로 대조하여 가장 큰 overlap을 가진 라벨로 치환. 어떤 세그먼트에도 속하지 않는 라인은 치환하지 않고 원래 이름 유지. **speakers 확정 규칙**: 치환에 실제 반영된 라벨만(`applied_labels`) speakers에 확정하고, 세그먼트가 비었거나 overlap이 없어 한 줄도 치환되지 않은 라벨은 `skipped`로 보고한다. **한계: diarization이 DB·파일 모두에 없으면**(ClovaNote/txt 업로드 등) 같은 토큰을 공유하는 라벨을 구분할 수 없어 **첫 라벨만 적용되고 나머지는 `skipped`로 보고**된다 |
| apply-match 응답 스펙 | 전체 성공: `200 {"ok": true}`. 부분 적용(일부 라벨 건너뜀): `200 {"ok": true, "skipped": ["SPEAKER_XX"], "warning": "일부 화자를 매칭할 수 없습니다"}`. 전체 실패(모든 라벨 건너뜀): `422 {"detail": "매칭할 수 있는 화자가 없습니다", "skipped": [...]}` (`JSONResponse` 직접 반환). 프론트(`MainArea.handleApplyMatch`)는 `data.skipped` 유무로 부분 적용 안내를 표시한다 |
| participation 중복 방지 | `_resolve_speaker_display` 결과가 이미 다른 라벨에 할당된 `display_name`과 겹치면 raw 라벨(`SPEAKER_XX`)로 폴백한다. `seen_display_names: set`으로 루프 내 중복 감지. diar 라벨이 transcript 화자 수보다 많은 과분할 상황에서 동일 이름 행 중복을 방지한다 |
| trim 이중 방어 | speaker_map 값의 공백 오염을 백엔드·프론트 양쪽에서 방어. **백엔드**: `label_to_current` 구성 시 `.strip()`. **프론트**: `TranscriptEditor.handleSubmit`에서 `names[s]?.trim() \|\| s` — serialize의 `names[l.speaker]?.trim() \|\| l.speaker`와 연산 순서를 일치시켜 공백 전용 입력이 빈 문자열로 평가된 뒤 폴백한다 |
| transcript segments (PR A) | `transcript_segments TEXT` (JSON `[{start,end,label,text,raw?}]`) 신설. 문자열 `transcript`는 파생값으로 유지하며 **바이트 동일**. 일괄 마이그레이션 없이 `get_segments()`의 lazy 파싱 + 조회 시 백필. 백필 전 `render(parsed) == transcript`를 검증해 **불일치 시 DB에 쓰지 않는다**(조용한 오염 차단). 생산자 2곳(`merge_and_save` 3-tuple, `_parse_txt_transcript` 호출부)이 기록하며 `update_job_result` 단일 호출에 transcript와 동승시켜 drift를 차단한다 |
| transcript 파서 계약 | 2단 매칭: `^\[(\d+):(\d{2})\]\s(.+?):\s(.*)$`(우선) → 실패 시 `^\[(\d+):(\d{2})\]\s(.+?):$`(빈 발언). **분은 `\d+` 무제한**(100분 초과 회의 대응, 기존 finalize의 `\d{2}` 불일치 해소). 라벨은 `.+?`이며 **`\S+` 금지**(공백 포함 실명 "김 팀장" 대응). 라벨 앞뒤 공백은 strip(내부 공백 보존), strip 후 빈 문자열이면 passthrough. 매칭 실패 줄은 폐기하지 않고 `label=None` 통과 라인으로 보존하며 **speaker_map이 무엇이든 치환하지 않는다**(본문 오염 차단) |
| `raw` 필드 규칙 | 정규 렌더가 원본 줄과 바이트 동일하지 않을 때만 저장. `render` 시 `display = speaker_map.get(label, label)`을 구해 **`display == label`이면 `raw` 출력**(왕복 보존), **`display != label`이면 정규형 렌더**(치환 우선). `raw`를 무조건 출력하면 라벨 치환이 조용히 무력화되므로 이 규칙이 필수다 |
| **[한계]** `[HH:MM:SS]` 형식 | **구조화하지 않고 passthrough한다.** 구조화하면 치환 시 `[01:02:03]` → `[62:03]`으로 사용자 화면의 타임스탬프 표기가 바뀌기 때문. 현행 `finalize`의 `\d{2}:\d{2}`도 이 형식을 잡지 못하므로 passthrough가 기존 동작과 일치한다. **결과적으로 이 형식의 줄은 PR B 이후에도 라벨 기반 치환 대상이 아니다** (사용자가 업로드한 표준 txt에서만 발생) |
| **[한계]** 오디오 경로 배선 테스트 | `job_queue.start_worker`가 segments를 실제 DB까지 쓰는 경로에 **자동 회귀 테스트가 없다.** 이 리포에 오디오 파이프라인(FFmpeg/PyAnnote/MLX-Whisper) mock 패턴이 없어 유닛테스트로 커버하지 못했다. `merge_and_save` 출력 포맷과 txt 업로드 경로는 테스트로 커버되지만, **오디오 경로의 배선이 끊겨도 전체 테스트가 통과한다.** 이 구간 변경 시 수동 확인이 필요하다 |
