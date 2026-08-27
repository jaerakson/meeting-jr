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

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/record` | webm 녹음 파일 업로드, job_id 반환 |
| GET | `/api/progress/{job_id}` | SSE 진행률 스트림 |
| GET | `/api/jobs` | 전체 Job 목록 |
| GET | `/api/jobs/{job_id}` | Job 상세 (transcript, summary 포함) |
| POST | `/api/jobs/{job_id}/finalize` | 편집된 transcript + speaker_map → Claude 요약 |
| POST | `/api/jobs/{job_id}/retry` | 실패 재시도 |
| DELETE | `/api/jobs/{job_id}` | 회의 삭제 |
| PATCH | `/api/jobs/{job_id}/title` | 제목 편집 |
| PATCH | `/api/jobs/{job_id}/summary` | 요약 내용 저장 |
| PATCH | `/api/jobs/{job_id}/transcript` | 트랜스크립트 수정 저장 |
| GET | `/api/jobs/{job_id}/download` | 마크다운 다운로드 |
| GET | `/api/jobs/{job_id}/audio` | 녹음 오디오 서빙 |
| GET | `/api/speakers` | 저장된 화자 이름 목록 |
| POST | `/api/jobs/{job_id}/export-notion` | Notion 등록 (mode: new\|update) |
| GET | `/api/meetings` | 회의 목록 검색+페이지네이션 (?q=&page=&limit=) |
| GET | `/api/settings` | 설정 키 등록 여부 조회 |
| PATCH | `/api/settings` | 설정값 저장 (암호화) |
| GET | `/api/settings/default-title` | 기본 회의 제목 조회 |
| GET | `/api/settings/claude-status` | Claude CLI 인증 상태 확인 |
| POST | `/api/settings/claude-logout` | Claude CLI 로그아웃 |
| POST | `/api/upload` | 파일 업로드 (오디오/txt), job_id 반환 |
| PATCH | `/api/jobs/{job_id}/action-items` | 액션 아이템 수정 |
| GET | `/api/action-items` | 통합 액션아이템 조회 (assignee/done 필터, 페이지네이션) |
| POST | `/api/jobs/{job_id}/share` | 공유 토큰 생성 |
| GET | `/api/shared/{token}` | 읽기 전용 공유 페이지 데이터 |
| DELETE | `/api/jobs/{job_id}/share` | 공유 토큰 폐기 |
| POST | `/api/jobs/{job_id}/ask` | AI 추가 질의 (claude -p) |
| POST | `/api/insights` | 크로스 회의 인사이트 (keyword/날짜 필터 → claude -p) |
| GET | `/api/jobs/{job_id}/participation` | 화자 발언 참여도 집계 |
| GET | `/api/jobs/{job_id}/related` | 관련 회의 조회 (키워드 매칭) |
| GET | `/api/jobs/{job_id}/followup` | 후속조치 대조 결과 조회 |
| PATCH | `/api/jobs/{job_id}/followup` | 후속조치 사용자 확정/수정 |
| POST | `/api/jobs/{job_id}/followup/generate` | 후속조치 대조 (재)생성 |
| POST | `/api/series` | 회의 시리즈 생성 |
| GET | `/api/series` | 시리즈 목록 |
| GET | `/api/series/{id}` | 시리즈 상세 + 연결 회의 |
| PATCH | `/api/series/{id}` | 시리즈 수정 |
| DELETE | `/api/series/{id}` | 시리즈 삭제 |
| PATCH | `/api/jobs/{job_id}/series` | 회의에 시리즈 할당/해제 |
| GET | `/api/export` | 전체 회의 ZIP 내보내기 |
| GET | `/api/categories` | 카테고리 목록 |
| POST | `/api/categories` | 카테고리 생성 |
| PATCH | `/api/categories/{id}` | 카테고리 수정 |
| DELETE | `/api/categories/{id}` | 카테고리 삭제 |
| PATCH | `/api/jobs/{job_id}/category` | 회의 카테고리 변경 |

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
