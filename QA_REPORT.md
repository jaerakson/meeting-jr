# QA 보고서 - Meeting Junior (이력 문서)

> ⚠️ **이 문서는 2026-08-22 v1 완성 시점의 스냅샷이며 현행 상태가 아니다.**
> 이후 세션 28~55에서 기능이 대폭 추가돼(엔드포인트 12개 → 75개) 아래 내용 대부분이 낡았다.
> 현행 정보는 다음을 참조할 것:
> - **API 목록**: `DEVGUIDE.md` 섹션 6
> - **확정 결정사항·알려진 한계**: `DEVGUIDE.md` 섹션 10
> - **진행 이력·현재 상태**: `PROGRESS.md` (최신순)
> - **테스트 현황**: `cd backend && python3.11 -m pytest tests/ -q` 로 직접 확인 (2026-08-29 기준 215개)
> - **업무 처리 방식**: `docs/ai_analysis/20260829_업무_처리_방식.md`
>
> 이 문서는 초기 구현 시점의 검증 기록으로만 남긴다.

생성일: 2026-08-22

## 파일 완성도

### 백엔드 (backend/)
| 파일 | 상태 | 비고 |
|------|------|------|
| app/main.py | OK | 12개 엔드포인트 모두 구현 |
| app/database.py | OK | meetings 테이블 스키마 완전, CRUD 완비 |
| app/job_queue.py | OK | asyncio Queue 기반 단일 순차 처리 |
| app/audio_processor.py | OK | FFmpeg + PyAnnote(MPS/CPU 폴백) + MLX-Whisper(ko) |
| app/summarizer.py | OK | claude CLI subprocess 방식 (anthropic SDK 미사용) |
| app/notion_sync.py | OK | notion-client AsyncClient, 100블록 분할 처리 |
| requirements.txt | OK | anthropic 패키지 미포함 (의도적) |
| .env.example | OK | HF_TOKEN, NOTION_API_KEY, NOTION_DATABASE_ID, MAX_UPLOAD_MB |

### 프론트엔드 (frontend/)
| 파일 | 상태 | 비고 |
|------|------|------|
| next.config.ts | OK | /api/** -> localhost:8000 프록시 (rewrites) |
| types/index.ts | OK | Job, ProgressEvent 인터페이스 |
| app/page.tsx | OK | /api/jobs 3초 폴링, Sidebar+MainArea 렌더링 |
| components/Sidebar.tsx | OK | 우클릭 삭제, 재시도 버튼, 상태 아이콘(스피너/초록/빨강) |
| components/MainArea.tsx | OK | 제목 인라인 편집, Notion 내보내기, 조건부 렌더링 |
| components/AudioPlayer.tsx | OK | 재생/일시정지, 시크바, CustomEvent 기반 외부 시크 |
| components/Transcript.tsx | OK | [MM:SS] SPEAKER_XX 파싱, 화자별 색상, 타임스탬프 클릭 |
| components/SummaryPanel.tsx | OK | 탭 UI, 편집 토글, 마크다운 다운로드 |
| components/SpeakerMapper.tsx | OK | /api/speakers 로드, rename-speakers 호출 |
| components/ProgressCard.tsx | OK | SSE 연결, 4단계 진행 표시, Browser Notification |
| components/UploadZone.tsx | OK | 드래그앤드롭, 파일 검증(확장자+크기) |

## API 정합성

### 엔드포인트 매핑 (프론트 -> 백엔드)
| 프론트엔드 호출 | 백엔드 라우트 | 일치 |
|----------------|-------------|------|
| POST /api/upload (FormData) | @app.post("/api/upload") | OK |
| GET /api/jobs | @app.get("/api/jobs") | OK |
| GET /api/jobs/{id} | @app.get("/api/jobs/{job_id}") | OK |
| DELETE /api/jobs/{id} | @app.delete("/api/jobs/{job_id}") | OK |
| POST /api/jobs/{id}/retry | @app.post("/api/jobs/{job_id}/retry") | OK |
| PATCH /api/jobs/{id}/title (JSON) | @app.patch("/api/jobs/{job_id}/title") | OK |
| POST /api/jobs/{id}/rename-speakers (JSON) | @app.post("/api/jobs/{job_id}/rename-speakers") | OK |
| POST /api/jobs/{id}/export-notion | @app.post("/api/jobs/{job_id}/export-notion") | OK |
| GET /api/jobs/{id}/download | @app.get("/api/jobs/{job_id}/download") | OK |
| GET /api/jobs/{id}/audio | @app.get("/api/jobs/{job_id}/audio") | OK |
| GET /api/progress/{id} (SSE) | @app.get("/api/progress/{job_id}") | OK |
| GET /api/speakers | @app.get("/api/speakers") | OK |

### 요청/응답 정합성
- upload: FormData `file` -> `{job_id, filename}` OK
- rename-speakers: `{speaker_map: Record}` -> `{status, job_id}` OK
- title: `{title: string}` -> `{status, job_id, title}` OK
- SSE: `{stage, progress, message, speakers?, suggested_names?}` OK
- Job 타입: `speakers: Record<string, string>` (DB dict 반환과 일치) OK

## 수정 사항

검증 시점에 이미 다른 에이전트에 의해 수정 완료된 항목:
1. `GET /api/jobs/{job_id}/audio` 엔드포인트 추가 (AudioPlayer에서 사용)
2. `notion_sync.py`의 `export_to_notion(title, summary_md)` 파라미터 순서 수정
3. `types/index.ts`의 `speakers` 타입을 `Record<string, string>`으로 변경

QA 검증 시 추가 수정 필요 사항: 없음

## 보안 검증
- backend/app/*.py 에 하드코딩된 토큰/키: **없음** (모두 os.getenv 사용)
- backend/.env 가 .gitignore에 포함: **OK**
- .env.example에 실제 값 노출: **없음** (placeholder만 포함)

## 알려진 제한사항

1. **PyAnnote 첫 실행**: speaker-diarization-3.1 모델 약 1GB 다운로드 필요
2. **Claude CLI 필요**: summarizer.py가 `claude -p` CLI를 사용하므로, Claude Code CLI가 시스템에 설치되어 있어야 함
3. **Notion 연동 선택적**: NOTION_API_KEY/NOTION_DATABASE_ID 미설정 시 내보내기 버튼에서 에러 표시
4. **summarizer.py 이중 저장**: main.py의 `run_summary`와 `summarizer.py`가 각각 output 파일을 저장 (동일 경로이므로 기능상 문제없음)
5. **SummaryPanel 편집**: 편집 모드에서 저장 시 실제 API 호출 없이 UI만 토글 (read-only 요약)
6. **동시 처리**: asyncio Queue 최대 1개 순차 처리 (동시 업로드 시 대기열 순서대로 처리)

## 실행 방법

### 사전 조건
- Python 3.10+, Node.js 18+
- FFmpeg 설치: `brew install ffmpeg`
- Claude Code CLI 설치
- HuggingFace 토큰 발급 (PyAnnote 모델 접근용)

### 설치 및 실행
```bash
# 1. 백엔드 환경 설정
cd backend
cp .env.example .env
# .env 파일에서 HF_TOKEN을 실제 토큰으로 변경

# 2. 백엔드 의존성 설치
pip install -r requirements.txt

# 3. 프론트엔드 의존성 설치
cd ../frontend
npm install

# 4. 백엔드 서버 실행 (터미널 1)
cd ../backend
python -m uvicorn app.main:app --reload --port 8000

# 5. 프론트엔드 서버 실행 (터미널 2)
cd ../frontend
npm run dev

# 6. 브라우저에서 접속
# http://localhost:3000
```

## 완성도 평가
9/10

감점 사유: SummaryPanel 편집 기능이 UI만 토글하고 실제 저장 API가 없음 (minor, 요약은 Claude가 생성하므로 수동 편집 필요성 낮음)
