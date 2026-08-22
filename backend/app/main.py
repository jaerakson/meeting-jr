"""
FastAPI 진입점 및 모든 API 엔드포인트.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import asyncio
import json
import os
import uuid

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .database import (
    init_db,
    create_job,
    get_job,
    get_all_jobs,
    update_job_status,
    update_job_result,
    update_job_title,
    update_job_notion,
    delete_job,
)
from .job_queue import job_queue, start_worker, progress_store, update_progress
from .settings_manager import get_settings_status, get_setting, set_setting, SETTING_KEYS

load_dotenv()

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SPEAKERS_FILE = BASE_DIR / "speakers.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".webm", ".mp4", ".ogg"}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    asyncio.create_task(start_worker())
    yield
    # Shutdown (nothing to clean up)


# ---------------------------------------------------------------------------
# FastAPI 앱
# ---------------------------------------------------------------------------

app = FastAPI(title="Meeting Junior API", lifespan=lifespan)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 1) POST /api/record  — webm Blob 전송
# ---------------------------------------------------------------------------

@app.post("/api/record")
async def record_audio(audio: UploadFile = File(...)):
    """브라우저에서 녹음된 webm Blob을 받아 처리 큐에 등록한다."""
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    total_size = 0

    job_id = str(uuid.uuid4())
    # MIME 타입으로 확장자 결정 (iOS Safari는 audio/mp4 사용)
    content_type = audio.content_type or ""
    if "mp4" in content_type:
        ext = ".mp4"
    elif "ogg" in content_type:
        ext = ".ogg"
    else:
        ext = ".webm"
    filename = f"{job_id}{ext}"
    save_path = INPUT_DIR / filename

    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await audio.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > max_bytes:
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail=f"파일 크기가 {MAX_UPLOAD_MB}MB를 초과합니다.",
                )
            await f.write(chunk)

    if total_size == 0:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="오디오 데이터가 없습니다.")

    _custom = get_setting("DEFAULT_MEETING_TITLE")
    title = _custom if _custom else "회의록"
    create_job(job_id, filename, title=title)
    await job_queue.put(job_id)

    return {"job_id": job_id, "filename": filename}


# ---------------------------------------------------------------------------
# 2) GET /api/progress/{job_id}  — SSE
# ---------------------------------------------------------------------------

@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    async def event_generator():
        while True:
            data = progress_store.get(job_id)
            if data:
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                stage = data.get("stage", "")
                if stage in ("done", "error", "awaiting_edit"):
                    break
            else:
                current_job = get_job(job_id)
                if current_job:
                    status = current_job["status"]
                    if status in ("done", "error", "awaiting_edit"):
                        fallback = {
                            "stage": status,
                            "progress": 100 if status == "done" else 0,
                            "message": current_job.get("error_msg", ""),
                        }
                        yield f"data: {json.dumps(fallback, ensure_ascii=False)}\n\n"
                        break
                yield f"data: {json.dumps({'stage': 'pending', 'progress': 0, 'message': '대기 중...'}, ensure_ascii=False)}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 3) GET /api/jobs
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
async def list_jobs():
    return get_all_jobs()


# ---------------------------------------------------------------------------
# 4) GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


# ---------------------------------------------------------------------------
# 5) POST /api/jobs/{job_id}/finalize  — 편집된 transcript + speaker_map 전송
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/finalize")
async def finalize_job(job_id: str, body: dict):
    """편집된 transcript와 speaker_map을 받아 Claude 요약을 시작한다."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    transcript: str = body.get("transcript", "").strip()
    speaker_map: dict = body.get("speaker_map", {})

    if not transcript:
        raise HTTPException(status_code=422, detail="transcript가 비어 있습니다.")

    # DB에 저장
    update_job_result(job_id, transcript=transcript, speakers=speaker_map)

    # speakers.json 업데이트 (이름 기억)
    if speaker_map:
        _save_speakers(speaker_map)

    # speaker_map 적용 후 스크립트 파일 저장
    final_transcript = transcript
    for speaker_id, name in speaker_map.items():
        if name.strip():
            final_transcript = final_transcript.replace(speaker_id, name)

    script_path = INPUT_DIR / f"{job_id}.txt"
    script_path.write_text(final_transcript, encoding="utf-8")

    # 상태를 summarizing으로 변경 (progress_store 초기화로 SSE 재연결 준비)
    update_job_status(job_id, "summarizing")
    progress_store.pop(job_id, None)

    # 백그라운드 요약 실행
    asyncio.create_task(run_summary(job_id, str(script_path), speaker_map))

    return {"status": "summarizing", "job_id": job_id}


async def run_summary(job_id: str, script_path: str, speaker_map: dict):
    """백그라운드에서 Claude 요약을 실행한다."""
    try:
        update_progress(job_id, {
            "stage": "summarizing",
            "progress": 0,
            "message": "회의록 생성 중...",
        })

        from .summarizer import generate_summary

        summary = await generate_summary(
            script_path,
            speaker_map,
            job_id,
            lambda jid, data: update_progress(jid, data),
        )

        output_path = OUTPUT_DIR / f"{job_id}_요약.md"
        output_path.write_text(summary, encoding="utf-8")

        update_job_result(job_id, summary=summary, status="done")
        update_progress(job_id, {
            "stage": "done",
            "progress": 100,
            "message": "완료",
        })

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        update_job_status(job_id, "error", error_msg)
        update_progress(job_id, {
            "stage": "error",
            "progress": 0,
            "message": error_msg,
        })


# ---------------------------------------------------------------------------
# 6) POST /api/jobs/{job_id}/retry
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "error":
        raise HTTPException(status_code=422, detail="error 상태의 Job만 재시도할 수 있습니다.")

    update_job_status(job_id, "pending")
    progress_store.pop(job_id, None)

    await job_queue.put(job_id)
    return {"status": "pending", "job_id": job_id}


# ---------------------------------------------------------------------------
# 7) DELETE /api/jobs/{job_id}
# ---------------------------------------------------------------------------

@app.delete("/api/jobs/{job_id}")
async def delete_job_endpoint(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    delete_job(job_id)

    for directory in (INPUT_DIR, OUTPUT_DIR):
        for f in directory.glob(f"{job_id}*"):
            f.unlink(missing_ok=True)

    progress_store.pop(job_id, None)

    return {"status": "deleted", "job_id": job_id}


# ---------------------------------------------------------------------------
# 8) PATCH /api/jobs/{job_id}/title
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/title")
async def patch_title(job_id: str, body: dict):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="제목이 비어 있습니다.")

    update_job_title(job_id, title)
    return {"status": "updated", "job_id": job_id, "title": title}


# ---------------------------------------------------------------------------
# 9-a) PATCH /api/jobs/{job_id}/transcript  — 재요약 없이 transcript만 저장
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/transcript")
async def patch_transcript(job_id: str, body: dict):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    transcript = body.get("transcript", "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcript가 비어 있습니다.")

    update_job_result(job_id, transcript=transcript)

    script_path = OUTPUT_DIR / f"{job_id}_스크립트.txt"
    script_path.write_text(transcript, encoding="utf-8")

    return {"status": "updated", "job_id": job_id}


# ---------------------------------------------------------------------------
# 9-b) PATCH /api/jobs/{job_id}/summary
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/summary")
async def patch_summary(job_id: str, body: dict):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    summary = body.get("summary", "").strip()
    if not summary:
        raise HTTPException(status_code=422, detail="요약 내용이 비어 있습니다.")

    update_job_result(job_id, summary=summary)

    output_path = OUTPUT_DIR / f"{job_id}_요약.md"
    output_path.write_text(summary, encoding="utf-8")

    return {"status": "updated", "job_id": job_id}


# ---------------------------------------------------------------------------
# 10) GET /api/jobs/{job_id}/download
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/download")
async def download_summary(job_id: str):
    summary_path = OUTPUT_DIR / f"{job_id}_요약.md"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="요약 파일을 찾을 수 없습니다.")

    job = get_job(job_id)
    download_name = f"{job['title']}_요약.md" if job else f"{job_id}_요약.md"

    return FileResponse(
        path=str(summary_path),
        media_type="text/markdown; charset=utf-8",
        filename=download_name,
    )


# ---------------------------------------------------------------------------
# 11) GET /api/jobs/{job_id}/audio — 오디오 파일 서빙
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/audio")
async def get_audio(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    audio_files = [f for f in INPUT_DIR.glob(f"{job_id}.*")
                   if f.suffix.lower() in AUDIO_EXTENSIONS]
    if not audio_files:
        raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다.")

    audio_path = audio_files[0]
    media_types = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
    }
    media_type = media_types.get(audio_path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        path=str(audio_path),
        media_type=media_type,
        filename=audio_path.name,
    )


# ---------------------------------------------------------------------------
# 12) GET /api/speakers
# ---------------------------------------------------------------------------

@app.get("/api/speakers")
async def get_speakers():
    if SPEAKERS_FILE.exists():
        try:
            data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


# ---------------------------------------------------------------------------
# 13) POST /api/jobs/{job_id}/export-notion
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/export-notion")
async def export_notion(job_id: str, body: dict = {}):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if not job.get("summary"):
        raise HTTPException(status_code=422, detail="요약이 아직 생성되지 않았습니다.")

    try:
        from .notion_sync import export_to_notion, update_notion_page

        mode = body.get("mode", "update")  # "update" | "new"
        existing_page_id = job.get("notion_page_id")

        # 회의 날짜 (created_at → KST)
        _KST = ZoneInfo("Asia/Seoul")
        try:
            created_dt = datetime.fromisoformat(job["created_at"])
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            meeting_ts = created_dt.astimezone(_KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            meeting_ts = str(job.get("created_at", ""))[:16]

        import re as _re
        base_title = job.get("title") or "제목 없음"
        # 구 자동생성 형식 "회의 YYYY-MM-DD HH:MM" → "회의록" 으로 정규화
        if _re.match(r"^회의\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", base_title):
            base_title = "회의록"
        notion_title = f"[{meeting_ts}] {base_title}"

        # 업로드 일시 (내보내기 실행 시점, KST)
        upload_ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
        summary_with_meta = f"📤 업로드 일시: {upload_ts}\n\n" + (job["summary"] or "")

        if existing_page_id and mode == "update":
            result = await update_notion_page(existing_page_id, notion_title, summary_with_meta)
        else:
            result = await export_to_notion(notion_title, summary_with_meta)
            update_job_notion(job_id, result["url"], result["page_id"])

        return {"status": "exported", "job_id": job_id, **result}
    except ImportError:
        raise HTTPException(status_code=501, detail="Notion 모듈이 구현되지 않았습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion 내보내기 실패: {e}")


# ---------------------------------------------------------------------------
# 13-b) GET /api/settings/claude-status
# ---------------------------------------------------------------------------

@app.get("/api/settings/claude-status")
async def claude_status():
    """Claude CLI 인증 상태를 반환한다."""
    import shutil
    import subprocess

    claude_path = shutil.which("claude")
    if not claude_path:
        return {"installed": False, "logged_in": False}

    try:
        result = subprocess.run(
            [claude_path, "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "installed": True,
                "logged_in": data.get("loggedIn", False),
                "email": data.get("email"),
                "auth_method": data.get("authMethod"),
                "subscription_type": data.get("subscriptionType"),
            }
        return {"installed": True, "logged_in": False}
    except Exception:
        return {"installed": True, "logged_in": False}


# ---------------------------------------------------------------------------
# 13-c) POST /api/settings/claude-logout
# ---------------------------------------------------------------------------

@app.post("/api/settings/claude-logout")
async def claude_logout():
    """Claude CLI 로그아웃을 실행한다."""
    import shutil
    import subprocess

    claude_path = shutil.which("claude")
    if not claude_path:
        raise HTTPException(status_code=404, detail="Claude CLI가 설치되어 있지 않습니다.")

    try:
        result = subprocess.run(
            [claude_path, "auth", "logout"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"status": "logged_out"}
        raise HTTPException(status_code=500, detail="로그아웃 실패: " + result.stderr)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그아웃 오류: {e}")


# ---------------------------------------------------------------------------
# 14) GET /api/settings
# ---------------------------------------------------------------------------

@app.get("/api/settings/default-title")
async def get_default_title():
    """기본 회의 제목을 반환한다. 미설정 시 빈 문자열."""
    return {"value": get_setting("DEFAULT_MEETING_TITLE") or ""}


@app.get("/api/settings")
async def get_settings():
    """각 설정 키의 설정 여부만 반환 (값 자체는 노출 안 함)."""
    return get_settings_status()


# ---------------------------------------------------------------------------
# 15) PATCH /api/settings
# ---------------------------------------------------------------------------

@app.patch("/api/settings")
async def patch_settings(body: dict):
    """설정값을 암호화하여 DB에 저장. 빈 문자열이면 해당 키 삭제."""
    for key in SETTING_KEYS:
        if key in body:
            set_setting(key, body[key])
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 16) GET /api/meetings  — 검색 + 페이지네이션
# ---------------------------------------------------------------------------

@app.get("/api/meetings")
async def list_meetings(q: str = "", page: int = 1, limit: int = 12):
    """제목+요약 검색 + 페이지네이션. 기존 /api/jobs 와 독립적으로 동작."""
    from .database import search_jobs
    return search_jobs(q=q, page=page, limit=limit)


# ---------------------------------------------------------------------------
# 헬퍼: speakers.json 저장
# ---------------------------------------------------------------------------

def _save_speakers(speaker_map: dict) -> None:
    """speaker_map의 이름들을 speakers.json에 병합 저장한다."""
    existing: dict = {}
    if SPEAKERS_FILE.exists():
        try:
            existing = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            existing = {}

    existing.update(speaker_map)
    SPEAKERS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
