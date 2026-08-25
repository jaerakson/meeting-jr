"""
FastAPI 진입점 및 모든 API 엔드포인트.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import asyncio
import io
import json
import os
import uuid
import zipfile

import re
from collections import Counter

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
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
    search_jobs,
    get_categories,
    get_category,
    create_category,
    update_category,
    delete_category,
    update_job_category,
    update_job_action_items,
    toggle_bookmark,
    update_job_memo,
    update_job_tags,
    get_all_tags,
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
TEXT_EXTENSIONS = {".txt"}
ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | TEXT_EXTENSIONS


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
async def record_audio(
    audio: UploadFile = File(...),
    category_id: str = Form("meeting"),
    language: str = Form("ko"),
):
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
    # category_id 유효성 확인, 없으면 "meeting" 폴백
    valid_cat = get_category(category_id) if category_id else None
    effective_category_id = category_id if valid_cat else "meeting"
    # language: "auto" → None (Whisper 자동 감지), 그 외는 그대로 전달
    lang = None if language == "auto" else language
    create_job(job_id, filename, title=title, category_id=effective_category_id, language=lang)
    await job_queue.put(job_id)

    return {"job_id": job_id, "filename": filename}


# ---------------------------------------------------------------------------
# 1-b) POST /api/upload  — 오디오/텍스트 파일 업로드
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    category_id: str = Form("meeting"),
    language: str = Form("ko"),
):
    """오디오 또는 텍스트 파일을 업로드하여 처리 큐에 등록한다."""
    original_filename = file.filename or "unknown"
    ext = Path(original_filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail="지원하지 않는 파일 형식입니다. 허용: mp3, m4a, wav, mp4, webm, ogg, txt",
        )

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    total_size = 0

    job_id = str(uuid.uuid4())
    filename = f"{job_id}{ext}"
    save_path = INPUT_DIR / filename

    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
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
        raise HTTPException(status_code=422, detail="파일이 비어 있습니다.")

    _custom = get_setting("DEFAULT_MEETING_TITLE")
    title = _custom if _custom else "회의록"
    valid_cat = get_category(category_id) if category_id else None
    effective_category_id = category_id if valid_cat else "meeting"

    lang = None if language == "auto" else language
    if ext in AUDIO_EXTENSIONS:
        create_job(job_id, filename, title=title, category_id=effective_category_id, language=lang)
        await job_queue.put(job_id)
    elif ext in TEXT_EXTENSIONS:
        transcript_content = save_path.read_text(encoding="utf-8")
        create_job(job_id, filename, title=title, category_id=effective_category_id, language=lang)
        update_job_result(job_id, transcript=transcript_content)
        update_job_status(job_id, "awaiting_edit")
        update_progress(job_id, {
            "stage": "awaiting_edit",
            "progress": 100,
            "message": "편집 대기 중",
            "transcript": transcript_content,
            "speakers": {},
        })

    return {"job_id": job_id, "filename": filename}


# ---------------------------------------------------------------------------
# 2) GET /api/progress/{job_id}  — SSE
# ---------------------------------------------------------------------------

@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str, request: Request):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
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
    body_category_id: str | None = body.get("category_id")

    if not transcript:
        raise HTTPException(status_code=422, detail="transcript가 비어 있습니다.")

    # category_id 결정: body → job → "meeting" 폴백
    category_id = body_category_id or job.get("category_id") or "meeting"
    if body_category_id:
        update_job_category(job_id, category_id)

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
    asyncio.create_task(run_summary(job_id, str(script_path), speaker_map, category_id=category_id))

    return {"status": "summarizing", "job_id": job_id}


async def run_summary(job_id: str, script_path: str, speaker_map: dict, category_id: str = "meeting"):
    """백그라운드에서 Claude 요약을 실행한다."""
    try:
        update_progress(job_id, {
            "stage": "summarizing",
            "progress": 0,
            "message": "회의록 생성 중...",
        })

        from .summarizer import generate_summary

        _model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"
        # 프롬프트 우선순위: 카테고리 prompt → CLAUDE_PROMPT 설정 → DEFAULT_PROMPT (None으로 위임)
        cat = get_category(category_id)
        if cat:
            _prompt = cat["prompt"]
        else:
            _prompt = get_setting("CLAUDE_PROMPT") or None

        summary = await generate_summary(
            script_path,
            speaker_map,
            job_id,
            lambda jid, data: update_progress(jid, data),
            model=_model,
            prompt_template=_prompt,
        )

        output_path = OUTPUT_DIR / f"{job_id}_요약.md"
        output_path.write_text(summary, encoding="utf-8")

        # 제목 자동 생성: 요약 첫 번째 # 제목 줄 파싱
        job = get_job(job_id)
        default_title = get_setting("DEFAULT_MEETING_TITLE") or "회의록"
        if job and job.get("title", "").strip() in ("회의록", default_title, ""):
            for line in summary.splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    auto_title = stripped[2:].strip().strip("[]")
                    if auto_title:
                        update_job_title(job_id, auto_title)
                    break

        # 액션 아이템 파싱
        action_items = []
        for line in summary.splitlines():
            m = re.match(r'^-\s*\[[ xX]\]\s*(?:@(\S+)\s*-?\s*)?(.+)$', line.strip())
            if m:
                done = '[x]' in line.lower()
                assignee = m.group(1) or ''
                text = m.group(2).strip()
                action_items.append({"text": text, "assignee": assignee, "done": done})
        if action_items:
            update_job_action_items(job_id, action_items)

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
# 5-b) POST /api/jobs/{job_id}/regenerate  — 요약 재생성 (동기)
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/regenerate")
async def regenerate_summary(job_id: str, body: dict = {}):
    """done 상태 회의의 요약을 다른 카테고리로 재생성한다."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=422, detail="done 상태의 Job만 재생성할 수 있습니다.")
    if not job.get("transcript"):
        raise HTTPException(status_code=422, detail="transcript가 없습니다.")

    category_id = body.get("category_id") or job.get("category_id") or "meeting"

    # category_id 갱신
    if category_id != job.get("category_id"):
        update_job_category(job_id, category_id)

    # speaker_map 적용 후 스크립트 준비
    speaker_map = job.get("speakers") or {}
    final_transcript = job["transcript"]
    for speaker_id, name in speaker_map.items():
        if name.strip():
            final_transcript = final_transcript.replace(speaker_id, name)

    script_path = INPUT_DIR / f"{job_id}.txt"
    script_path.write_text(final_transcript, encoding="utf-8")

    # 동기적으로 요약 실행 (요약은 보통 짧으므로)
    update_job_status(job_id, "summarizing")
    await run_summary(job_id, str(script_path), speaker_map, category_id=category_id)

    updated_job = get_job(job_id)
    return updated_job


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
# 8-b) PATCH /api/jobs/{job_id}/bookmark
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/bookmark")
async def toggle_job_bookmark(job_id: str):
    job = toggle_bookmark(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


# ---------------------------------------------------------------------------
# 8-c) PATCH /api/jobs/{job_id}/memo
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/memo")
async def update_memo(job_id: str, body: dict):
    memo = body.get("memo", "")
    job = update_job_memo(job_id, memo)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


# ---------------------------------------------------------------------------
# 8-d) PATCH /api/jobs/{job_id}/tags
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/tags")
async def patch_tags(job_id: str, body: dict):
    tags = body.get("tags")
    if tags is None or not isinstance(tags, list):
        raise HTTPException(status_code=422, detail="tags 리스트가 필요합니다.")
    job = update_job_tags(job_id, tags)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


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
# 9-c) PATCH /api/jobs/{job_id}/action-items
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/action-items")
async def patch_action_items(job_id: str, body: dict):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    action_items = body.get("action_items")
    if action_items is None or not isinstance(action_items, list):
        raise HTTPException(status_code=422, detail="action_items 리스트가 필요합니다.")

    update_job_action_items(job_id, action_items)
    return get_job(job_id)


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

@app.get("/api/stats")
async def get_stats():
    """done 상태 회의의 통계를 반환한다."""
    import sqlite3 as _sqlite3
    from .database import DB_PATH
    conn = _sqlite3.connect(str(DB_PATH))
    conn.row_factory = _sqlite3.Row

    _KST = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(_KST)
    # 이번 주 월요일 00:00 KST
    week_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_start.replace(day=week_start.day - week_start.weekday())
    week_start_utc = week_start.astimezone(timezone.utc).isoformat()

    total = conn.execute("SELECT COUNT(*) FROM meetings WHERE status='done'").fetchone()[0]
    this_week = conn.execute(
        "SELECT COUNT(*) FROM meetings WHERE status='done' AND created_at >= ?",
        (week_start_utc,)
    ).fetchone()[0]
    by_category_rows = conn.execute(
        "SELECT COALESCE(category_id,'meeting') as cat, COUNT(*) as cnt FROM meetings WHERE status='done' GROUP BY cat"
    ).fetchall()
    conn.close()

    by_category = [{"id": r["cat"], "count": r["cnt"]} for r in by_category_rows]
    return {"total": total, "this_week": this_week, "by_category": by_category}


@app.get("/api/speakers")
async def get_speakers():
    if SPEAKERS_FILE.exists():
        try:
            data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


@app.post("/api/speakers")
async def add_speaker(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name은 필수입니다.")
    data: dict = {}
    if SPEAKERS_FILE.exists():
        try:
            data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            data = {}
    # 이름을 key/value 모두로 저장 (식별자 = 표시명)
    data[name] = name
    SPEAKERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "name": name}


@app.delete("/api/speakers/{name}")
async def delete_speaker(name: str):
    if not SPEAKERS_FILE.exists():
        raise HTTPException(status_code=404, detail="화자가 없습니다.")
    try:
        data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        raise HTTPException(status_code=500, detail="speakers.json 읽기 실패")
    # 표시 이름(value)으로 매핑된 키를 모두 삭제
    keys_to_delete = [k for k, v in data.items() if v == name]
    if not keys_to_delete:
        raise HTTPException(status_code=404, detail="해당 화자를 찾을 수 없습니다.")
    for k in keys_to_delete:
        del data[k]
    SPEAKERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "name": name}


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

        # 카테고리 정보 조회
        job_cat_id = job.get("category_id") or "meeting"
        cat = get_category(job_cat_id)
        cat_icon = cat["icon"] if cat else "📋"
        cat_name = cat["name"] if cat else "회의록"

        # 업로드 일시 (내보내기 실행 시점, KST)
        upload_ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
        summary_md = job["summary"] or ""

        if existing_page_id and mode == "update":
            result = await update_notion_page(
                existing_page_id, notion_title, summary_md,
                upload_ts=upload_ts, category_icon=cat_icon, category_name=cat_name,
            )
        else:
            result = await export_to_notion(
                notion_title, summary_md,
                upload_ts=upload_ts, category_icon=cat_icon, category_name=cat_name,
            )
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


@app.get("/api/settings/claude-model")
async def get_claude_model():
    """현재 설정된 Claude 모델 반환. 미설정 시 기본값."""
    return {"value": get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"}


@app.get("/api/settings/claude-prompt")
async def get_claude_prompt():
    """현재 설정된 프롬프트 반환. 미설정 시 빈 문자열. default도 함께 반환."""
    from .summarizer import DEFAULT_PROMPT
    return {
        "value": get_setting("CLAUDE_PROMPT") or "",
        "default": DEFAULT_PROMPT,
    }


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
async def list_meetings(
    q: str = "",
    page: int = 1,
    limit: int = 12,
    category_id: str = "",
    date_from: str = "",
    date_to: str = "",
    tag: str = "",
):
    """제목+요약 검색 + 카테고리/날짜/태그 필터 + 페이지네이션."""
    limit = min(limit, 100)
    return search_jobs(q=q, page=page, limit=limit, category_id=category_id, date_from=date_from, date_to=date_to, tag=tag)


# ---------------------------------------------------------------------------
# Tags API
# ---------------------------------------------------------------------------

@app.get("/api/tags")
async def list_tags():
    """전체 사용된 태그 목록 반환."""
    return get_all_tags()


# ---------------------------------------------------------------------------
# Categories API
# ---------------------------------------------------------------------------

@app.get("/api/categories")
async def list_categories():
    """카테고리 목록 반환 (sort_order 오름차순)."""
    return get_categories()


@app.post("/api/categories")
async def create_category_endpoint(body: dict):
    """사용자 카테고리 생성."""
    name = (body.get("name") or "").strip()
    icon = (body.get("icon") or "📋").strip()
    description = (body.get("description") or "").strip()
    prompt = (body.get("prompt") or "").strip()

    if not name:
        raise HTTPException(status_code=422, detail="name이 비어 있습니다.")
    if "{script}" not in prompt:
        raise HTTPException(status_code=422, detail="prompt에 {script} 플레이스홀더가 필요합니다.")

    cat_id = str(uuid.uuid4())
    return create_category(cat_id, name, icon, description, prompt)


@app.patch("/api/categories/{cat_id}")
async def update_category_endpoint(cat_id: str, body: dict):
    """카테고리 이름/아이콘/설명/프롬프트 수정."""
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")

    kwargs = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "icon" in body:
        kwargs["icon"] = body["icon"]
    if "description" in body:
        kwargs["description"] = body["description"]
    if "prompt" in body:
        p = body["prompt"]
        if "{script}" not in p:
            raise HTTPException(status_code=422, detail="prompt에 {script} 플레이스홀더가 필요합니다.")
        kwargs["prompt"] = p

    return update_category(cat_id, **kwargs)


@app.delete("/api/categories/{cat_id}")
async def delete_category_endpoint(cat_id: str):
    """카테고리 삭제. is_builtin=1이면 거부."""
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    if cat.get("is_builtin"):
        raise HTTPException(status_code=422, detail="내장 카테고리는 삭제할 수 없습니다.")

    delete_category(cat_id)
    return {"status": "deleted", "id": cat_id}


@app.post("/api/categories/{cat_id}/reset")
async def reset_category_prompt(cat_id: str):
    """내장 카테고리 프롬프트를 DEFAULT로 복원."""
    from .categories import DEFAULT_PROMPTS
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    if not cat.get("is_builtin"):
        raise HTTPException(status_code=422, detail="사용자 카테고리는 초기화할 수 없습니다.")
    if cat_id not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=422, detail="해당 카테고리의 기본 프롬프트가 없습니다.")

    return update_category(cat_id, prompt=DEFAULT_PROMPTS[cat_id])


# ---------------------------------------------------------------------------
# 헬퍼: speakers.json 저장
# ---------------------------------------------------------------------------

def _extract_keywords(text: str, top_n: int = 8) -> list[str]:
    """불용어 제거 + 빈도 기반 상위 N개 키워드 추출."""
    STOPWORDS = {
        "의", "을", "를", "이", "가", "은", "는", "에", "에서", "와", "과", "로", "으로",
        "그", "저", "것", "수", "있", "하", "되", "이다", "합니다", "했습니다", "회의",
        "the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on", "at",
    }
    words = re.findall(r'[가-힣a-zA-Z]{2,}', text)
    filtered = [w for w in words if w not in STOPWORDS]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(top_n)]


@app.get("/api/jobs/{job_id}/related")
async def get_related_meetings(job_id: str):
    """현재 회의와 키워드가 겹치는 다른 회의를 최대 5개 반환한다."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    text = (job.get("summary") or "") + " " + (job.get("title") or "")
    keywords = _extract_keywords(text)

    if not keywords:
        return {"items": []}

    all_jobs = get_all_jobs()
    results = []
    for j in all_jobs:
        if j["id"] == job_id:
            continue
        search_text = (j.get("title") or "") + " " + (j.get("summary") or "")
        matched = [kw for kw in keywords if kw in search_text]
        if matched:
            results.append({
                "id": j["id"],
                "title": j.get("title"),
                "created_at": j.get("created_at"),
                "matched_keywords": matched[:3],
                "score": len(matched),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"items": results[:5]}


# ---------------------------------------------------------------------------
# ZIP 전체 내보내기
# ---------------------------------------------------------------------------

@app.get("/api/export")
async def export_all_meetings():
    """모든 회의를 ZIP으로 내보낸다."""
    jobs = get_all_jobs()
    if not jobs:
        raise HTTPException(status_code=404, detail="내보낼 회의가 없습니다.")

    def generate_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for job in jobs:
                job_id = job["id"]
                title = (job.get("title") or job_id)[:40]
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
                folder = f"{safe_title}/"

                if job.get("summary"):
                    date = job.get("created_at", "")[:10]
                    md = f"# {job.get('title', '')}\n\n날짜: {date}\n\n## 요약\n\n{job['summary']}"
                    if job.get("transcript"):
                        md += f"\n\n## 스크립트\n\n{job['transcript']}"
                    zf.writestr(folder + "summary.md", md.encode("utf-8"))

                if job.get("transcript"):
                    zf.writestr(folder + "transcript.txt", job["transcript"].encode("utf-8"))

                for ext in AUDIO_EXTENSIONS:
                    audio_path = INPUT_DIR / f"{job_id}{ext}"
                    if audio_path.exists():
                        zf.write(str(audio_path), folder + f"audio{ext}")
                        break

        buf.seek(0)
        yield buf.read()

    filename = f"meetings-export-{datetime.now().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        generate_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _save_speakers(speaker_map: dict) -> None:
    """speaker_map의 이름들을 speakers.json에 병합 저장한다.
    key == value인 항목(UNKNOWN → UNKNOWN 등)은 저장하지 않는다."""
    existing: dict = {}
    if SPEAKERS_FILE.exists():
        try:
            existing = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            existing = {}

    for speaker_id, name in speaker_map.items():
        if name and name.strip() and name.strip() != speaker_id:
            existing[speaker_id] = name.strip()

    SPEAKERS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
