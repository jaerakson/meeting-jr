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
| PATCH | `/api/jobs/{job_id}/transcript` | 편집된 transcript를 재요약 없이 저장한다 (segments·화자 이름도 함께 갱신). |
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
| POST | `/api/jobs/{job_id}/rename-speakers` | 화자 이름 매핑을 적용하고 transcript를 재렌더한다 (요약은 하지 않는다). |
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
| identity-mapped 판별 | speaker_map 키 중 `SPEAKER_\d+` 패턴에 매칭되지 않는 실명 키가 하나라도 있으면 identity-mapped 회의로 판별. 부분 apply-match 후 혼합 상태(`{"SPEAKER_00":"김과장","엄마":"엄마"}`)도 identity-mapped로 올바르게 처리. participation API의 `_is_identity_mapped` 지역 변수로 판별하며, **용도는 경로 선택(diar vs transcript segments)뿐**이다. **apply_match는 이 판별을 쓰지 않는다** — `get_segments(job_id)`가 반환하는 segment label 집합에 `matches`의 키가 있는지로만 검증한다(PR B) |
| 기존 불일치 데이터 처리 | **[PR B로 폐기]** 아래 '화자 매핑 라벨 모델 (PR B)' 항목으로 대체됨. 이하 서술은 이력. DB 마이그레이션 없이 조회 시점 reconciliation. participation API의 `_resolve_speaker_display`가 diarization↔transcript 구간 overlap 면적 방식으로 런타임에 display_name 결정 |
| apply-match 충돌 해소 | **[PR B로 폐기]** '충돌' 개념 자체가 소멸(speaker_map은 label 키). 이하 서술은 이력. **"충돌"의 정의**: 서로 다른 diar 라벨이 같은 `current_name`으로 수렴하는 경우 (예: SPEAKER_00·SPEAKER_01 모두 "김팀장"으로 해석). **충돌 없는 경우**: 기존 원자적 정규식 치환(`replace_map` + `re.sub` 콜백). **충돌 시**: diarization 타임스탬프 기반 라인별 치환 — 각 transcript 라인의 `[MM:SS]`를 diar 세그먼트 구간과 **overlap 면적**(=`min(seg_e, line_end) − max(seg_s, line_start)`)으로 대조하여 가장 큰 overlap을 가진 라벨로 치환. 어떤 세그먼트에도 속하지 않는 라인은 치환하지 않고 원래 이름 유지. **speakers 확정 규칙**: 치환에 실제 반영된 라벨만(`applied_labels`) speakers에 확정하고, 세그먼트가 비었거나 overlap이 없어 한 줄도 치환되지 않은 라벨은 `skipped`로 보고한다. **한계: diarization이 DB·파일 모두에 없으면**(ClovaNote/txt 업로드 등) 같은 토큰을 공유하는 라벨을 구분할 수 없어 **첫 라벨만 적용되고 나머지는 `skipped`로 보고**된다 |
| apply-match 응답 스펙 | 전체 성공: `200 {"ok": true}`. 부분 적용(일부 라벨 건너뜀): `200 {"ok": true, "skipped": ["SPEAKER_XX"], "warning": "일부 화자를 매칭할 수 없습니다"}`. 전체 실패(모든 라벨 건너뜀): `422 {"detail": "매칭할 수 있는 화자가 없습니다. 예전 방식으로 저장된 회의일 수 있습니다.", "skipped": [...]}` (`JSONResponse` 직접 반환, **이 경로에서는 `update_job_result`를 호출하지 않는다** — 재렌더가 우연히 같은 문자열을 내는 것에 기대지 않기 위함). **`skipped` 사유는 두 가지**: ①라벨 검증 실패(`matches` 키가 segment label 집합에 없음) ②`new_name`이 빈/공백뿐(매핑을 건드리지 않고 거부 — 쓰면 관문이 키를 제외해 기존 이름이 지워진다). 프론트(`MainArea.handleApplyMatch`)는 `data.skipped` 유무로 부분 적용 안내를 표시한다 |
| participation 중복 방지 | **[PR B로 폐기]** 라벨별 독립 조회로 중복이 구조적으로 불가능해짐. 이하 서술은 이력. `_resolve_speaker_display` 결과가 이미 다른 라벨에 할당된 `display_name`과 겹치면 raw 라벨(`SPEAKER_XX`)로 폴백한다. `seen_display_names: set`으로 루프 내 중복 감지. diar 라벨이 transcript 화자 수보다 많은 과분할 상황에서 동일 이름 행 중복을 방지한다 |
| trim 3겹 방어 | speaker_map 값의 공백 오염을 백엔드 3겹 + 프론트에서 방어. **백엔드 ①쓰기 직전**: `apply_match`/`rename_speakers`가 값을 `.strip()`. **②관문**: `update_job_result`가 저장 시 trim + 빈 값 제외(호출부 전부가 통과하므로 새 쓰기 경로가 생겨도 구멍이 없다). **③렌더**: `render`의 `display = (speaker_map.get(label) or "").strip() or label`(레거시 행 방어, 빈 값이면 라벨 유지). **관문 하나로 합치면 안 되는 이유**: `render()`가 `update_job_result`보다 **먼저** 호출되므로, 관문에만 맡기면 `" 박과장 "`이 transcript에 `[00:00]  박과장 : …`로 그대로 렌더된다. ①과 ②는 중복이 아니라 순서가 다른 방어다. **프론트**: `TranscriptEditor.handleSubmit`에서 `names[s]?.trim() \|\| s` — serialize의 `names[l.speaker]?.trim() \|\| l.speaker`와 연산 순서를 일치시켜 공백 전용 입력이 빈 문자열로 평가된 뒤 폴백한다 |
| transcript segments (PR A) | `transcript_segments TEXT` (JSON `[{start,end,label,text,raw?}]`) 신설. 문자열 `transcript`는 파생값으로 유지하며 **바이트 동일**. 일괄 마이그레이션 없이 `get_segments()`의 lazy 파싱 + 조회 시 백필. 백필 전 `render(parsed) == transcript`를 검증해 **불일치 시 DB에 쓰지 않는다**(조용한 오염 차단). 생산자 2곳(`merge_and_save` 3-tuple, `_parse_txt_transcript` 호출부)이 기록하며 `update_job_result` 단일 호출에 transcript와 동승시켜 drift를 차단한다 |
| transcript 파서 계약 | 2단 매칭: `^\[(\d+):(\d{2})\]\s(.+?):\s(.*)$`(우선) → 실패 시 `^\[(\d+):(\d{2})\]\s(.+?):$`(빈 발언). **분은 `\d+` 무제한**(100분 초과 회의 대응, 기존 finalize의 `\d{2}` 불일치 해소). 라벨은 `.+?`이며 **`\S+` 금지**(공백 포함 실명 "김 팀장" 대응). 라벨 앞뒤 공백은 strip(내부 공백 보존), strip 후 빈 문자열이면 passthrough. 매칭 실패 줄은 폐기하지 않고 `label=None` 통과 라인으로 보존하며 **speaker_map이 무엇이든 치환하지 않는다**(본문 오염 차단) |
| `raw` 필드 규칙 | 정규 렌더가 원본 줄과 바이트 동일하지 않을 때만 저장. `render` 시 `display = (speaker_map.get(label) or "").strip() or label`을 구해 **`display == label`이면 `raw` 출력**(왕복 보존), **`display != label`이면 정규형 렌더**(치환 우선). `raw`를 무조건 출력하면 라벨 치환이 조용히 무력화되므로 이 규칙이 필수다. **빈/공백뿐인 매핑 값은 매핑이 없는 것으로 취급**해 `display == label`로 수렴시킨다(PR B) — 프론트 `SpeakerMapper.tsx:42` 초기값이 `''`라 실제로 도달하는 입력이고, 그대로 치환하면 화자 이름이 지워진다 |
| **[한계]** `[HH:MM:SS]` 형식 | **구조화하지 않고 passthrough한다.** 구조화하면 치환 시 `[01:02:03]` → `[62:03]`으로 사용자 화면의 타임스탬프 표기가 바뀌기 때문. 현행 `finalize`의 `\d{2}:\d{2}`도 이 형식을 잡지 못하므로 passthrough가 기존 동작과 일치한다. **결과적으로 이 형식의 줄은 PR B 이후에도 라벨 기반 치환 대상이 아니다** (사용자가 업로드한 표준 txt에서만 발생) |
| **[한계]** 오디오 파이프라인 e2e | 실제 오디오 파이프라인(FFmpeg/PyAnnote/MLX-Whisper)은 이 리포에 mock 패턴이 없어 **end-to-end 테스트가 없다.** 다만 `job_queue.start_worker`가 segments를 DB까지 쓰는 **배선 구간은 `test_audio_pipeline_wiring_persists_segments_to_db`가 덮는다** — `process_audio`를 monkeypatch로 대체해 실제 워커를 태우고 `transcript_segments` 도달과 `render(segments) == transcript`를 단언하며, 배선 라인 제거 시 이 테스트만 실패하는 것을 mutation test로 확인했다. 파이프라인 내부(오디오 디코딩·화자분리·STT 정확도) 변경 시에는 수동 확인이 필요하다 |
| 화자 매핑 라벨 모델 (PR B) | apply-match·participation·rename-speakers가 **표시 이름을 `speaker_map.get(label, label)` 하나로만** 결정한다. apply-match = 라벨 검증(`get_segments`의 label 집합) → speaker_map 갱신 → `render()` 재렌더. 텍스트 매칭·overlap 휴리스틱(`_resolve_speaker_display`/`replace_map`/`collision_groups`/`seen_display_names`) 전부 삭제. `new_name`이 빈/공백뿐이면 매핑을 건드리지 않고 `skipped` — 그대로 쓰면 `update_job_result` 관문이 키를 제외해 **기존 이름이 지워진다**. rename-speakers도 재렌더를 붙여 transcript↔speakers desync를 없앴고(기존 speakers를 베이스로 body 키만 덮어쓰는 **merge-safe 병합** — 전체 교체면 body에 빠진 라벨의 이름이 본문에서 사라진다), 정규화된 map으로 렌더·프로필 저장을 한다. **순차 `.replace()`는 `app/main.py`(`finalize_job`·`regenerate_summary`)뿐 아니라 `app/summarizer.py::_replace_speakers`에도 사본이 있었고 둘 다 제거했다** — summarizer 쪽은 줄 앵커조차 없는 전체 문자열 `.replace()`라 본문 텍스트까지 오염시켰고, 이미 `render()`로 렌더된 스크립트 위에 **중복 치환**이 걸려 요약이 발언자를 오귀속했다. `grep`은 `app/` 전체에 걸 것(main.py만 보면 놓친다). **[한계] 레거시 행(speaker_map 키가 실명)에서는 음성 프로필 재매칭이 동작하지 않고 `422 + skipped`로 명시 거부된다.** **원인**: `matches` 키는 항상 `SPEAKER_XX`(diarization 라벨)인데 레거시 행의 segment label은 실명이라 라벨 공간이 어긋난다. 조용히 틀리는 대신 거부를 택했다(폐기된 매칭 방식의 재유입 차단). **PR C가 근본 원인(finalize의 identity 재키잉)을 제거하므로 레거시 행은 더 이상 생기지 않는다 — 모집단이 고정된다.** **영향 범위**: **[정정] 실측 10건 중 6건이다**(아래 '레거시 행에서 음성 프로필 추출 불가' 행 참조). '1건'은 레거시를 *speaker_map 키가 실명인 행*으로 잘못 정의했을 때의 숫자이고, 그 정의는 같은 PR 에서 정정됐다. **[부작용, 의도됨]** participation에서 레거시 행은 `_is_identity_mapped` 경로 선택에 따라 diar를 조회하지 않고 transcript(segments) 경로를 타므로, diar 정밀 시간 대신 추정 시간을 쓰게 되어 `total_seconds`·`percentage` 숫자가 달라지고 transcript에 없는 과분할 diar 라벨은 항목 자체가 사라진다(전/후 실측값은 대응표 참조). **`_is_identity_mapped` 존치 이유**: 설계문서를 문자 그대로 적용해 이 판별까지 지우면 레거시 행에서 사용자가 설정한 이름이 전부 사라진다(`speaker_map.get(label, label)`의 label이 diar 라벨이 되어버림). 이 함수가 하던 일이 둘(경로 선택 + 이름 해석 휴리스틱)이었으므로 **해석 휴리스틱만 삭제하고 경로 선택 용도로만 남겼다.** |
| 폐기된 매칭 방식 제거 완료 (PR B·C) | 폐기된 매칭 방식은 총 **5벌**이었고 PR B가 4벌을 제거했다(`apply_match` 3a~3e / `_resolve_speaker_display` / `finalize_job`·`regenerate_summary`의 순차 `.replace()` / `summarizer._replace_speakers`). **남은 1벌이던 `save_speaker_profile`(main.py)의 diar↔transcript overlap 휴리스틱은 PR C에서 제거했다 — 이로써 5벌 전부 소멸했고 `backend/app` 전수 grep이 0이다.** PR B 범위 밖이라 손대지 않았고 **PR C에서 라벨 모델로 전환한다.** **[일관성 문제]** 같은 레거시 행(speaker_map 키가 실명)에 대해 `apply_match`는 `422 + skipped`로 명시 거부하는데 `save_speaker_profile`은 조용히 옛 휴리스틱을 돌려 **성공한다** — 사용자에게 같은 데이터가 한 화면에서는 거부되고 다른 화면에서는 처리되는 것처럼 보인다 |
| `finalize_job`의 segments 동승 갱신 | `finalize_job`은 편집된 transcript를 저장할 때 `parse(transcript)` 결과를 `transcript_segments`에 **함께** 쓴다(같은 `update_job_result` 호출). **왜 필요한가**: PR A 시점에는 소비자가 없어 낡은 segments가 남아도 무해했지만, **PR B가 apply-match·rename-speakers에 재렌더를 붙이면서 데이터 손실 경로로 승격됐다** — finalize로 편집 → 낡은 segments 잔존 → 이후 rename → 낡은 segments로 렌더 → **사용자 편집이 통째로 사라진다.** `transcript`만 갱신하도록 되돌리지 말 것. 이 경로는 `rename-speakers`의 부분 map 이름 소실과 같은 부류다 |
| 프론트 공유 파서 모듈 (PR C) | `frontend/lib/transcript.ts` 신설 — `backend/app/transcript.py`의 `parse`/`render` 계약을 그대로 포팅(교차 검증: 동일 입력에 대해 Python·TS 양쪽 산출물이 바이트 단위로 동일함을 확인). 프론트에 흩어져 있던 파서 4개·시리얼라이저 2개를 이 모듈로 수렴시킨다. `TranscriptEditor.tsx`(라벨 파싱에 `\S+` 사용)도 **이 PR 에서 전환 완료**했다 — finalize 계약 변경과 함께 처리했고, 공백 포함 실명("김 팀장")을 놓치던 `\S+` 결함도 이때 해소됐다. **프론트 중복 파서는 전수 0건이다.** |
| `Transcript.tsx` 화자 재지정 UX 변경 (PR C) | 화자 이름 편집 UI를 라벨 기반으로 재설계하며 **"이 항목만 이름 변경" 버튼을 제거**하고 **"이 줄을 다른 화자로 재지정"**(그 줄의 label을 이미 존재하는 다른 라벨로 교체)으로 대체했다. **기존 기능 삭제가 아니라 라벨 모델에서 의미가 성립하지 않아 재해석한 것이다** — "같은 라벨의 한 줄만 다른 표시 이름"은 "라벨이 화자의 정체성"이라는 전제 자체와 모순된다(그 전제가 무너지면 화자 매핑 리팩터링 전체가 다시 원점이다). "전체 변경"은 `speaker_map[label]=newName` 갱신으로 유지된다. UI는 select가 아니라 **존재하는 다른 라벨들을 버튼으로 나열**하는 방식(화자가 보통 2~4명이라 select보다 가벼움) |
| **[한계]** 레거시 행에서 음성 프로필 추출 불가 (PR C) | `save_speaker_profile`이 라벨 모델로 전환되면서 **레거시 행(speaker_map 키가 실명이라 diar 라벨과 다리가 없는 행)에서는 음성 프로필을 추출할 수 없고 422로 거부된다.** **기능 손실이다** — 이전에는 transcript 구간과 diar 세그먼트의 overlap 휴리스틱으로 추론해 성공했다. `apply_match`가 같은 행을 422로 거부하는 것과 **동작을 일치시킨 결과**이며(한 화면에서 거부된 데이터가 다른 화면에서 처리되던 불일치 해소), 조용히 틀린 화자의 목소리를 프로필로 저장하는 것보다 낫다는 판단이다. **대상**: 실측 기준 저장된 회의 10건 중 6건. **[정정] '키가 실명인 행'이라는 위 정의는 틀렸다** — 키가 실명인 행은 `60b7b738` **1건뿐**이고, 나머지 5건은 **키가 전부 `SPEAKER_XX` 인데 본문 라벨만 실명**인 행이다. 따라서 **`SPEAKER_\d+` 정규식으로 레거시를 판별하면 복구 대상 2건(`92c731af`·`2e3a65c4`)을 '정상'으로 분류해 조용히 방치한다.** **올바른 판별 기준은 '모든 segment 라벨이 diar 라벨 공간 안에 있는가'** (diar 가 없으면 `SPEAKER_XX` 형태를 공간으로 본다) — 이것이 apply-match 가 실제로 요구하는 성질이다. **[정정] 실측 판정: 자동복구 3 / 병합복구 2 / 건너뜀 1 / 조치불필요 4** (기존 3/3/0 은 틀렸다). 건너뛴 `60b7b738` 의 실패 조건은 **③(키 ⊆ diar 키)** 이다 — map 에 `아빠`·`손주환`·`손재락` 키가 있으나 diar 키는 `SPEAKER_00~03` 뿐이라 되돌릴 라벨이 데이터에 없다. **표시 이름으로 호출된 경우**는 `{값: 키}` 역맵으로 라벨을 되찾되, **값이 중복이면 역맵에서 제외**한다(어느 라벨인지 데이터로 결정 불가 — 추측하지 않는다) |
| `finalize_job` identity 재키잉 삭제 (PR C) | finalize의 "speaker_map이 identity면 transcript에서 이름을 파싱해 `{실명: 실명}`으로 재키잉" 분기를 삭제했다. **되살리지 말 것.** **무엇을 막고 있었나**: 사용자가 이름 input이 아니라 **본문에서 직접** 화자명을 고쳐 speaker_map은 identity인데 transcript 라벨만 실명이 되는 입력 — 그대로 저장하면 키(SPEAKER_XX) ≠ 라벨(실명)인 레거시 행이 된다(실제 사용자 데이터 `60b7b738`이 그 흔적). **왜 이제 필요 없나**: `TranscriptEditor`가 이름을 본문에 굽지 않고 라벨 그대로 보내고 이름은 speaker_map이 나르므로(PR C 계약) 그 입력 자체가 생기지 않는다. 이름을 채우면 `all(k == v)`가 False라 분기가 발동하지 않았고, 이름이 비면 재키잉해도 같은 값이 나오는 무동작이었다 — **즉 이 분기는 본문 직접 편집이라는 단 하나의 입력에서만 일했다.** **순서 주의**: 프론트 계약 변경(라벨 왕복)보다 먼저 지우면 오히려 레거시 행이 새로 생긴다 |
| 레거시 화자 라벨 복구 마이그레이션 (PR C) | `scripts/migrate_legacy_speaker_map.py`. **기본 dry-run, `--write` 로만 기록, 자동 실행 경로 없음**(앱에서 호출하지 않는다). 커넥션을 `mode=ro` URI 로 열어 dry-run 의 읽기 전용을 **코드로 강제**한다. 바꾸는 것은 `transcript_segments` 의 `label` 뿐 — `transcript` 문자열·`speaker_map`·`diarization` 은 한 글자도 바꾸지 않는다. **핵심 안전장치**: 재키잉 후 `render(new_segments, speaker_map)` 가 현재 `transcript` 와 **바이트 동일**하지 않으면 그 행을 쓰지 않는다(표시 이름은 map 이 나르므로 **화면이 한 글자도 안 바뀌는 것이 정상**이다). 행별 사전조건 ②값집합==라벨집합 ③키 ⊆ diar 키 ④매핑 실패 라벨 0건 — **하나라도 불성립이면 행 전체를 건너뛴다(부분 복구 금지).** **[정정] ①(값 유일)은 건너뜀 조건이 아니다** — 값이 중복이면 건너뛰지 않고 **병합 경로**로 분기해 대표 라벨을 고른 뒤 ②③④를 동일하게 적용한다. ①을 건너뜀 조건으로 적으면 실제 복구 대상 2건(`6c5acaa2`·`5938f69c`)이 스펙상 제외돼 버린다. 멱등(2회차는 전부 조치불필요). |
| 마이그레이션의 중복 이름 병합 — **폐기 휴리스틱과 다르다** (PR C) | 한 사람이 diar 에서 과분할돼 사용자가 여러 라벨에 **같은 이름**을 준 경우(실측 `6c5acaa2` 의 `이삼희`, `5938f69c` 의 `대표님` 3벌). 대표 라벨 = **diar 총 발화 길이(`sum(end-start)`) 최대인 키**, 동률 시 키 문자열 정렬(결정적). **이것을 PR B 에서 지운 overlap 휴리스틱과 혼동하지 말 것** — 지운 것은 *어느 줄이 누구 발화인지* 추측이었고, 이건 *사용자가 이미 선언한 이름 하나*가 실려 있던 여러 클러스터 중 대표를 고르는 규칙이다. **줄 배정은 추측하지 않는다**: 줄의 라벨은 역맵으로만 결정되며, 결정되지 않는 줄이 하나라도 있으면 그 행 전체를 건너뛴다. |
| 병합 복구 시 **비대표 키를 speaker_map 에 남긴다** (PR C) | 대표 라벨을 고른 뒤에도 동명의 비대표 키(`SPEAKER_02` 등)를 **지우지 않는다.** **지우면 안 되는 이유**: `participation` 의 diar 경로(main.py:2268~)는 **`diar_data` 키를 순회**하며 `display = (speaker_map.get(label) or "").strip() or label` 로 이름을 찾으므로, 키를 지우면 그 클러스터가 참여도 화면에 **raw `SPEAKER_XX` 로 표시된다**(실측: `6c5acaa2` 66초/5%, `5938f69c` 145초/3%). **이 스크립트는 '화면은 한 글자도 안 바뀐다'를 약속하고 실행되므로 소수 구간이라도 받아들일 수 없다.** 남겨도 안전한 이유: transcript 라벨은 대표 라벨로 통일되어 **본문 렌더에 비대표 키가 등장하지 않고**, 표시 이름 중복은 PR B 가 이미 허용하기로 결정한 상태이며, apply-match 는 키가 diar 라벨이므로 중복 값이 있어도 동작한다. **결과적으로 `--write` 는 `transcript_segments` 만 기록하고 `speakers` 는 건드리지 않는다** — transcript 도 speakers 도 안 쓰는 것이 화면 불변 약속의 가장 강한 보장이다. |
| **[한계]** 병합 복구된 행은 프로필 추출이 계속 422 (PR C) | `save_speaker_profile` 의 역맵은 **값이 중복이면 제외**한다(어느 라벨인지 데이터로 결정 불가 — 추측하지 않는다). 병합 복구된 행은 표시 이름이 중복인 상태 그대로이므로 **그 이름으로는 음성 프로필 추출이 계속 422 다.** **마이그레이션이 복구했다고 모든 기능이 되는 것은 아니다** — 복구가 보장하는 것은 apply-match 의 라벨 공간 정합뿐이다. PR B 의 '추측하지 않고 명시 거부' 원칙 그대로이므로 **역맵에 추측을 집어넣어 '고치려' 하지 말 것.** |
| **[한계]** 표시 이름이 중복인 회의는 '회의록 수정'에서 **줄을 추가할 수 없다** (PR C) | `patch_transcript` 는 편집된 본문의 라벨을 (a)이미 라벨 공간 안 → (b)같은 `start` 의 편집 이전 세그먼트 표시 이름과 일치 → (c)값이 유일한 역맵 순으로 되돌리고, **미해소가 하나라도 있으면 422 로 거부하고 부분 저장하지 않는다.** 표시 이름이 중복인 회의(실측 `5938f69c` 의 `대표님` 3벌, `6c5acaa2` 의 `이삼희`)에서 **새 줄을 추가하면** (b)는 새 `start` 라 대조할 옛 세그먼트가 없고 (c)는 중복이라 역맵에서 제외되므로 **422 가 된다.** **기존 줄의 텍스트 편집·삭제는 정상 동작한다(200)** — 새 줄 추가만 막힌다. **의도된 동작이다**: 허용하려면 '중복 이름은 그 이름을 가진 라벨 중 하나로 배정'이 필요한데 그건 명백한 추측이고, 조용히 틀린 화자를 붙이는 것보다 거부가 낫다(`save_speaker_profile` 422 와 같은 판단). **마이그레이션으로 병합 복구된 행은 표시 이름 중복이 그대로 남으므로 이 제약도 그대로 유지된다.** |
| **[확정]** 프론트 전송용 페이로드와 화면용 렌더가 분리됐다 (`8c47a56`) | **과거 근본 원인**(front-c3 전수조사 시점): `Transcript.tsx` 의 `onTranscriptChange` 가 항상 `render(segments, speakerMap)`(**이름 적용판**)을 콜백으로 내보내, 편집 세션 중 화자 이름을 한 번이라도 바꾸면 그 시점부터 `saveEdit` 조차 이름이 구워진 문자열을 만들었다(`MainArea` 의 `handleSaveTranscript`/`handleResummarize` 두 결함의 공통 근원). **`8c47a56`(fix(PR C): Transcript.tsx 전송 payload/화면 렌더 계약 분리 [근원])에서 해소됐다.** 현재 계약: `onTranscriptChange` 를 호출하는 3곳(`saveEdit` L186·`saveSpeakerAll` L196·`reassignLine` L208) **전부** `render(seg, {})` 로 **라벨만** 렌더해 `transcript` 로 내보내고, 이름은 `speakerMap` 이 별도 필드로 나른다. **이 분리를 되돌리지 말 것** — 셋 중 하나라도 `render(seg, speakerMap)` 으로 바뀌면 근본 원인이 재유입된다. **다만 서버측 `restore_segment_labels` 방어는 프론트를 고쳐도 계속 필요하다** — 구버전 번들·다른 클라이언트·직접 API 호출에 무방비이므로, 프론트 수정은 서버 방어의 *대체*가 아니라 *추가 방어*다. **참고**: `TranscriptEditor` 는 `render(segments, {})` 로 **빈 map 을 넘겨 `display == label` 을 강제**하므로 애초에 이 부류가 아니었다(같은 `render` 호출이라도 인자로 안전/위험이 갈린다). |
| **[프로세스]** `patch_transcript` 수정은 `08de49a`(docs 커밋) 안에 있다 | 공유 워킹트리에서 `git add -A` 로 커밋해 **backend 의 `main.py` 수정 92줄이 director 의 docs 커밋에 함께 들어갔고**, qa 의 테스트 520줄은 `e327150` 에 들어갔다. **커밋 메시지만 보면 이 PR 의 핵심 코드 수정을 놓친다.** 내용은 정상이며 squash 머지라 최종 이력에는 영향이 없다. 원인은 커밋 후 `git show --stat` 을 실행하고도 **파일 목록을 확인하지 않은 것**. 공유 워킹트리에서는 **경로를 명시해 add 할 것.** |
| **[검증 기법]** 집계 건수는 판별력이 없다 (PR C) | 이번 작업에서 **'집계 건수는 정확한데 행 구성이 틀린' 오구현이 두 번** 나왔다: ①첫 판정 기준이 깨진 행 `60b7b738` 을 정상으로 위장(집계는 3/2/1/4 로 일치) ②다음 정의는 `5ab8e338` 과 `60b7b738` 의 판정이 **서로 뒤바뀌었는데** 건수만 우연히 같았다. **우연이 두 번 겹쳤다는 것은 이 데이터에서 집계 숫자에 판별력이 거의 없다는 뜻이다.** → 검증은 **행 구성(ID→판정 매핑)으로** 한다. 테스트도 픽스처 행의 ID 집합으로 단언하고, **뒤바뀜이 잡히도록 서로 다른 판정 유형을 같은 테스트에 함께 넣는다.** 집계만 비교하는 단언은 위 두 오구현을 모두 통과시킨다. |
| **[함정]** `transcript_segments` 는 대부분 NULL 이다 — 이 컬럼을 읽는 **모든** 코드에 해당 | 실측(2026-08-31, 회의 10건): **NULL 인 행이 9/10.** PR A 의 lazy backfill 은 `get_segments()` 로 **조회될 때만** 채우므로, 조회된 적 없는 행은 계속 NULL 이다. **`transcript_segments` 컬럼만 읽고 라벨 공간을 판단하면 9/10 을 잘못 읽는다.** 세그먼트가 필요하면 `get_segments()` 를 쓰거나, **읽기 전용이어야 하는 문맥에서는 `parse(transcript)` 로 직접 파싱한다** — `get_segments()` 는 백필로 DB 에 쓰므로 dry-run·읽기 전용 보장을 깬다(마이그레이션 스크립트가 `parse` 를 직접 쓰는 이유). |
| **[판정 순서가 계약이다]** (PR C) | 마이그레이션은 **①~④ 사전조건보다 먼저** '이 행이 이미 라벨 공간과 정합한가'를 판정하고, 정합하면 **조치불필요**로 분류하고 조건 검사를 하지 않는다. 순서가 뒤바뀌면 정상 행(`5ab8e338`: segment 라벨 4개인데 `speaker_map` 은 `SPEAKER_00` 하나 — 매핑 안 된 diar 라벨이 본문에 남은 정상 상태)이 사전조건 ②를 못 지나 **'건너뜀'으로 잘못 보고된다.** **결과가 그럴듯해서 눈으로는 걸러지지 않는다.** |
| **[확정 계약]** `job.transcript` 컬럼은 항상 라벨이다 (PR C) | **저장되는 `transcript` 는 라벨(`SPEAKER_XX`) 그대로이고, 이름은 `job.speakers` 가 나르며, 표시는 소비 시점에 `render(segments, speakers)` 로 만든다.** 이름을 컬럼에 굽는 쓰기 경로는 더 이상 없다 — `finalize`·`patch_transcript` 는 받은 문자열을 그대로 저장하고, `apply_match`·`rename_speakers` 는 `render(segments, {})` 로 저장한다(이 둘이 마지막 두 지점이었다). **본문을 밖으로 내보내는 소비 지점은 전부 `display_transcript(job)` 공용 헬퍼를 쓴다** — ZIP 내보내기·`/ask` 프롬프트·후속조치 대조·`regenerate`. 새 소비 지점이 생기면 사본을 만들지 말고 이 헬퍼를 호출할 것. **예외는 검색 스니펫 하나뿐이다**(아래 한계 ④). |
| **[한계 ①]** 하위호환 PATCH 경로는 불변식 밖이다 (PR C) | `PATCH /api/jobs/{id}/transcript` 에 `speaker_map` 이 **없으면**(구버전 번들·직접 API 호출) 받은 문자열을 **그대로** `transcript` 에 저장하고 `speakers` 는 갱신하지 않는다. 그 문자열에는 이름이 구워져 있을 수 있으므로 **그 경로로 들어온 행은 "컬럼은 항상 라벨" 불변식 밖이다.** `restore_segment_labels` 가 segments 라벨은 되돌리므로 `transcript_segments` 는 정합하다. 서버측 방어는 프론트를 고쳐도 계속 필요하다 — 프론트 수정은 방어의 *대체*가 아니라 *추가*다. |
| **[한계 ②+⑤]** DB 안에 transcript 두 세대가 공존한다 (PR C) | **이번 수정 이후의 신규 쓰기만** `transcript` 컬럼이 라벨이다. 기존 행은 `apply-match`·`rename-speakers` 이력 때문에 **이름이 구워진 채**로 남아 있고 **마이그레이션하지 않았다.** — **표시 경로**(화면·다운로드·복사·공유·ZIP)는 `speaker_map` 미스로 `display == label` 에 수렴해 **두 세대 모두 맞게 나온다**(degrade gracefully). — **검색·`/ask`·후속조치 대조는 세대에 따라 동작이 다르다**: 구세대 행은 본문에 이름이 있어 그대로 걸리고, 신세대 행은 렌더를 거쳐야 이름이 나온다. **'모집단이 고정된다'고 쓰지 말 것** — 두 세대가 공존하며 경로별로 다르게 동작한다. |
| **[한계 ③]** 검색어에 `SPEAKER` 가 들어가면 라벨 키에 매칭된다 (PR C) | 화자 이름 검색을 위해 `speakers LIKE ?` 를 조건에 넣었으므로, 검색어가 `SPEAKER` 를 포함하면 `speakers` 컬럼의 **라벨 키**에 매칭돼 대부분의 행이 걸리고 스니펫은 빈 문자열이 된다. **의도된 트레이드오프다** — 막으려고 검색 조건을 특수화하는 쪽이 더 큰 부채다. |
| **[한계 ④]** 검색 스니펫은 `parse()` 로 렌더한다 — `get_segments()` 금지 (PR C) | `search_jobs` 의 스니펫은 `_rendered_transcript(row)` 가 `parse(transcript)` 로 직접 파싱해 렌더한다. **`get_segments()` 로 바꾸지 말 것** — 그 함수는 조회 시 DB 백필 쓰기를 하고 `transcript_segments` 는 대부분 NULL(10건 중 9건)이라 **검색 한 번에 페이지 전체가 써진다.** 검색은 읽기 전용 조회 경로다. **반대로 쓰기 경로(`display_transcript`)는 `get_segments()` 를 쓴다** — 한쪽으로 통일하려다 반대편을 깨지 말 것. |
| **[한계 ⑥]** 빈 `speaker_map` 은 "이름 없음"이 아니라 "갱신 안 함"이다 (PR C) | `finalize`·`patch_transcript` 는 빈 맵(`{}`)을 **키 부재와 같게** 취급한다. 근거: 모든 화자 이름을 지우는 UI 동작이 존재하지 않는다(`TranscriptEditor` 는 항상 identity 폴백을 채운다). 빈 맵을 그대로 쓰면 `update_job_result` 가 `speakers` 를 `{}` 로 덮어써 **회의의 화자 이름이 영구 소실된다**(실제 발생). 방어는 **요청 경계(body 를 받는 두 엔드포인트)** 에서 한다 — 관문(`update_job_result`)에서 막으면 빈 맵을 정말 쓰려는 미래 경로까지 조용히 막힌다. **"빈 맵이면 지우는 게 자연스럽다"고 되돌리지 말 것.** 참고: 이름이 아직 없는 신규 회의는 `effective` 가 **정상적으로** 빈 맵이며, 라벨 공간은 diar 라벨로 성립한다 — 빈 맵을 무조건 이상 상황으로 오해하지 말 것. |
| **[원칙]** 방어 코드는 조용히 버리지 않는다 (PR C) | **입력을 거부할 때 조용히 버리지 않는다. 해소 불가능한 입력은 422 로 거부하고 이유를 담는다.** 조용히 버리는 방어는 방어가 아니라 **새로운 무음 실패**다. 근거: 이번 라운드 결함 3건이 전부 같은 형태였다 — 빈 `speaker_map` 이 speakers 를 **조용히 덮어썼고**, `patch_transcript` 의 라벨 공간 필터가 실명 키를 **조용히 버렸고**, 프론트 `res.ok` 미검사가 **조용히 실패했다**. `restore_segment_labels` 의 (d)(미해소 하나라도 있으면 422·부분 저장 없음)와 같은 계약이다. |
| **[구현]** `patch_transcript` 의 키 번역 (PR C) | body 의 `speaker_map` 키를 **그대로 라벨 공간으로 인정하지 않는다**(신뢰할 수 없는 입력). ①키가 라벨 공간(`diar 라벨 ∪ 편집 이전 세그먼트 라벨 ∪ 기존 speakers 키`) 안이면 그대로 → ②아니면 기존 `speakers` 의 **역맵(값이 유일할 때만)** 으로 표시 이름→라벨 번역 → ③둘 다 실패하면 **422**. 번역은 추측이 아니라 `restore_segment_labels` (c)와 **같은 규칙**이며, 그 규칙은 `unique_display_inverse()` 로 공용화했다(사본 금지). 번역 항목은 직접 키 **뒤에** 얹는다 — 구세대 payload 에는 옛 매핑과 새 이름이 함께 실려 오므로 사용자가 방금 지정한 이름이 이겨야 한다. |
