# Meeting Junior

> 음성 녹음 → 화자 분리 → STT → AI 요약 → Notion 자동 등록까지 한 번에 처리하는 회의록 자동화 웹앱

M1 Mac 로컬에서 실행하며, 브라우저에서 직접 녹음하거나 외부 기기(모바일 포함)에서 Cloudflare Tunnel을 통해 접속해 사용할 수 있습니다.

---

## 주요 기능

- **브라우저 녹음** — 별도 앱 없이 웹에서 바로 마이크 녹음 (PC/모바일 모두 지원)
- **화자 분리** — PyAnnote로 SPEAKER_00, SPEAKER_01 등 자동 분리
- **STT** — MLX-Whisper로 전체 대화 텍스트 변환
- **트랜스크립트 편집** — 화자 이름 지정, 발화 텍스트 수정 후 요약 진행
- **AI 요약** — Claude CLI로 핵심 요약 / 주요 논의 / 결정 사항 / 액션 아이템 생성
- **Notion 내보내기** — 요약 결과를 Notion 데이터베이스에 자동 등록
- **외부 접속** — Cloudflare Tunnel로 외부 기기에서 접속 가능

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 15 App Router, Tailwind CSS |
| 백엔드 | Python 3.11, FastAPI, SQLite |
| 화자 분리 | PyAnnote Audio |
| STT | MLX-Whisper (Apple Silicon 최적화) |
| AI 요약 | Claude CLI (`claude -p`) |
| 녹음 | MediaRecorder API (webm/mp4 자동 감지) |

---

## 시스템 요구사항

- **Apple Silicon Mac** (M1/M2/M3) — MLX-Whisper, PyAnnote 최적화 환경
- Python 3.11
- Node.js 18+
- FFmpeg (`brew install ffmpeg`)
- Claude CLI 설치 및 로그인 (`claude` 명령어 사용 가능)
- Hugging Face 계정 및 토큰 (PyAnnote 모델 접근용)

---

## 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/meeting-jr.git
cd meeting-jr
```

### 2. 백엔드 설정

```bash
cd backend
pip3.11 install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 편집 → HF_TOKEN 입력
```

### 3. 프론트엔드 설정

```bash
cd frontend
npm install
```

### 4. 서버 실행

```bash
# 터미널 1: 백엔드
cd backend
python3.11 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 터미널 2: 프론트엔드
cd frontend
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

---

## 환경변수

`backend/.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
# Hugging Face 토큰 (PyAnnote 모델 접근용, 필수)
# https://huggingface.co/settings/tokens 에서 발급
HF_TOKEN=hf_your_token_here

# Notion API 연동 (선택)
NOTION_API_KEY=
NOTION_DATABASE_ID=

# 파일 업로드 제한 (MB)
MAX_UPLOAD_MB=500

# CORS 허용 출처 (외부 접속 시 프론트엔드 주소 추가)
ALLOWED_ORIGINS=http://localhost:3000
```

`frontend/.env.local` (외부 접속 시에만 필요):

```env
# 백엔드 주소 (기본값: http://localhost:8000)
BACKEND_URL=http://localhost:8000
```

---

## 외부 기기에서 접속 (Cloudflare Tunnel)

로컬 서버를 외부에 노출해 스마트폰 등에서 접속할 수 있습니다.

```bash
# cloudflared 설치
brew install cloudflared

# 터미널에서 실행 (프론트엔드가 3000 포트에 실행 중이어야 함)
cloudflared tunnel --url http://localhost:3000
```

출력된 `https://xxx.trycloudflare.com` URL을 모바일 브라우저에서 열면 됩니다.

> **참고:** Quick Tunnel URL은 재시작마다 변경됩니다. 고정 URL이 필요하면 Cloudflare 계정 기반 Named Tunnel을 설정하세요.

---

## 프로젝트 구조

```
meeting-jr/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 엔드포인트
│   │   ├── audio_processor.py  # PyAnnote + MLX-Whisper 파이프라인
│   │   ├── summarizer.py    # Claude CLI 요약
│   │   ├── notion_sync.py   # Notion 연동
│   │   ├── job_queue.py     # 비동기 처리 큐
│   │   └── database.py      # SQLite CRUD
│   ├── input/               # 업로드된 오디오 (gitignore)
│   ├── output/              # 처리 결과 (gitignore)
│   ├── requirements.txt
│   └── .env                 # 환경변수 (gitignore)
│
├── frontend/
│   ├── app/
│   │   └── page.tsx         # 메인 페이지
│   ├── components/
│   │   ├── Sidebar.tsx      # 회의 목록 사이드바
│   │   ├── MainArea.tsx     # 메인 콘텐츠 영역
│   │   ├── RecordingZone.tsx   # 녹음 UI
│   │   ├── ProgressCard.tsx    # 처리 진행률 (SSE)
│   │   ├── TranscriptEditor.tsx  # 화자/텍스트 편집
│   │   ├── AudioPlayer.tsx  # 오디오 재생
│   │   ├── Transcript.tsx   # 대화 스크립트
│   │   └── SummaryPanel.tsx # 요약 패널
│   ├── next.config.ts       # API 프록시 설정
│   └── .env.local           # 환경변수 (gitignore)
│
└── README.md
```

---

## 처리 흐름

```
[브라우저 녹음]
      ↓ webm / mp4 업로드
[FastAPI /api/record]
      ↓ 큐 등록
[FFmpeg 변환] → [PyAnnote 화자 분리] → [MLX-Whisper STT]
      ↓ SSE로 실시간 진행률 전송
[트랜스크립트 편집 UI] ← 사용자가 화자 이름 지정, 텍스트 수정
      ↓ /api/jobs/{id}/finalize
[Claude CLI 요약]
      ↓
[결과 표시 + Notion 내보내기]
```

---

## PyAnnote 모델 사용 동의

처음 실행 시 Hugging Face에서 아래 모델에 대한 사용 동의가 필요합니다:

- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

각 모델 페이지에서 "Agree and access repository" 클릭 후 HF_TOKEN을 발급받아 `.env`에 입력하세요.

---

## 라이선스

MIT
