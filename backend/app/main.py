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
import subprocess
import tempfile
import uuid
import zipfile

import re
from collections import Counter

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

import numpy as np

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
    get_all_action_items,
    create_share_token,
    get_job_by_share_token,
    revoke_share_token,
    toggle_bookmark,
    update_job_memo,
    update_job_tags,
    get_all_tags,
    get_voice_profiles,
    get_voice_profile,
    get_all_voice_profiles_with_embeddings,
    create_voice_profile,
    update_voice_profile_embedding,
    delete_voice_profile,
    get_voice_profile_threshold,
    set_voice_profile_threshold,
    update_job_rating,
    save_recording_notes,
    get_recording_notes,
    delete_recording_note,
    create_series,
    get_all_series,
    get_series,
    get_series_meetings,
    update_series,
    delete_series,
    update_job_series,
    get_previous_series_meeting,
    update_job_followup,
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
# WebM remux 유틸
# ---------------------------------------------------------------------------

async def _remux_webm_if_needed(file_path: Path) -> None:
    """WebM 파일에 duration/seek cues가 없으면 ffmpeg remux로 추가한다."""
    if file_path.suffix.lower() != ".webm":
        return

    def _do_remux():
        # ffprobe로 duration 확인
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
                capture_output=True, text=True, timeout=10,
            )
            duration_str = probe.stdout.strip()
            # duration이 유효한 숫자면 remux 불필요
            if duration_str and duration_str != "N/A":
                try:
                    float(duration_str)
                    return  # 이미 seekable
                except ValueError:
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return  # ffprobe 없으면 스킵

        # ffmpeg -c copy remux
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".webm", dir=str(file_path.parent))
            os.close(tmp_fd)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(file_path), "-c", "copy", tmp_path],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and Path(tmp_path).stat().st_size > 0:
                Path(tmp_path).replace(file_path)
            else:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    await asyncio.to_thread(_do_remux)


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

    # WebM seekable remux
    await _remux_webm_if_needed(save_path)

    title = "회의록"
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

    title = "회의록"
    valid_cat = get_category(category_id) if category_id else None
    effective_category_id = category_id if valid_cat else "meeting"

    lang = None if language == "auto" else language
    if ext in AUDIO_EXTENSIONS:
        create_job(job_id, filename, title=title, category_id=effective_category_id, language=lang)
        await job_queue.put(job_id)
    elif ext in TEXT_EXTENSIONS:
        transcript_content = save_path.read_text(encoding="utf-8")
        # ClovaNote 형식 감지 및 변환
        transcript_content, found_speakers, suggested_names = _parse_txt_transcript(transcript_content)
        create_job(job_id, filename, title=title, category_id=effective_category_id, language=lang)
        update_job_result(job_id, transcript=transcript_content, speakers=suggested_names)
        update_job_status(job_id, "awaiting_edit")
        update_progress(job_id, {
            "stage": "awaiting_edit",
            "progress": 100,
            "message": "편집 대기 중",
            "transcript": transcript_content,
            "speakers": found_speakers,
            "suggested_names": suggested_names,
            "suggested_speakers": {},
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

    # speaker_map이 identity mapping이면 transcript에서 실제 이름 파싱
    # SPEAKER_XX 키와 발화순 이름의 매핑이 불확실하므로, 이름 자체를 키로 사용
    if speaker_map and all(k == v for k, v in speaker_map.items()):
        found_names = list(dict.fromkeys(
            m.strip() for m in re.findall(r'\[\d{2}:\d{2}\]\s*(.+?):', transcript)
        ))
        if found_names:
            speaker_map = {name: name for name in found_names}

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

        cat = get_category(category_id)
        _model = (cat.get("model") if cat else None) or get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"
        _prompt = cat["prompt"] if cat else (get_setting("CLAUDE_PROMPT") or None)
        _prompt_template = (cat.get("prompt_template") if cat else None) or None

        summary = await generate_summary(
            script_path,
            speaker_map,
            job_id,
            lambda jid, data: update_progress(jid, data),
            model=_model,
            prompt_template=_prompt,
            extra_instructions=_prompt_template,
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

# ---------------------------------------------------------------------------
# 크로스 회의 인사이트 API
# ---------------------------------------------------------------------------

@app.post("/api/insights")
async def get_insights(body: dict):
    question = body.get("question")
    if question is None or not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=422, detail="question이 필요합니다.")

    keyword = body.get("keyword", "")
    date_from = body.get("date_from", "")
    date_to = body.get("date_to", "")

    # done 상태 회의 필터링
    if keyword:
        result = search_jobs(q=keyword, date_from=date_from, date_to=date_to, limit=50)
        meetings = [m for m in result["items"] if m["status"] == "done"][:10]
    else:
        result = search_jobs(date_from=date_from, date_to=date_to, limit=50)
        meetings = [m for m in result["items"] if m["status"] == "done"][:10]

    if not meetings:
        raise HTTPException(status_code=404, detail="관련 회의를 찾을 수 없습니다.")

    # 회의 summaries 모아서 프롬프트 구성
    context_parts = []
    for m in meetings:
        context_parts.append(
            f"### {m['title']} ({m['created_at'][:10]})\n{m.get('summary', '') or ''}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = (
        f"다음은 여러 회의의 요약입니다:\n\n{context}\n\n"
        f"위 회의들을 종합하여 다음 질문에 답변해주세요:\n{question.strip()}"
    )

    model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt, "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Claude 질의 실패: {stderr.decode()}")

    return {
        "answer": stdout.decode().strip(),
        "meeting_count": len(meetings),
        "meetings": [
            {"id": m["id"], "title": m["title"], "created_at": m["created_at"]}
            for m in meetings
        ],
    }


# ---------------------------------------------------------------------------
# AI 추가 질의 API
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/ask")
async def ask_question(job_id: str, body: dict):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="완료된 회의만 질의할 수 있습니다.")

    question = body.get("question")
    if question is None or not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=422, detail="question이 필요합니다.")

    transcript = job.get("transcript", "")
    summary = job.get("summary", "")

    prompt = (
        f"다음은 회의 스크립트입니다:\n\n{transcript}\n\n"
        f"다음은 회의 요약입니다:\n\n{summary}\n\n"
        f"위 회의 내용을 바탕으로 다음 질문에 답변해주세요:\n{question.strip()}"
    )

    model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt, "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Claude 질의 실패: {stderr.decode()}")

    return {"answer": stdout.decode().strip()}


# ---------------------------------------------------------------------------
# 공유 링크 API
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/share")
async def share_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="완료된 회의만 공유할 수 있습니다.")
    token = create_share_token(job_id)
    return {"token": token, "url": f"/shared/{token}"}


@app.get("/api/shared/{token}")
async def get_shared(token: str):
    job = get_job_by_share_token(token)
    if not job:
        raise HTTPException(status_code=404, detail="공유 링크가 유효하지 않습니다.")
    return {
        "title": job.get("title"),
        "summary": job.get("summary"),
        "transcript": job.get("transcript"),
        "speakers": job.get("speakers", {}),
        "created_at": job.get("created_at"),
        "duration_sec": job.get("duration_sec"),
    }


@app.delete("/api/jobs/{job_id}/share")
async def revoke_share(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    revoke_share_token(job_id)
    return {"status": "revoked"}


@app.get("/api/action-items")
async def get_action_items(
    assignee: str = "",
    done: str | None = None,
    page: int = 1,
    limit: int = 20,
):
    """전체 회의의 액션 아이템 통합 조회."""
    return get_all_action_items(assignee=assignee, done=done, page=page, limit=limit)


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
async def get_audio(job_id: str, request: Request):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    audio_files = [f for f in INPUT_DIR.glob(f"{job_id}.*")
                   if f.suffix.lower() in AUDIO_EXTENSIONS]
    if not audio_files:
        raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다.")

    audio_path = audio_files[0]
    # 기존 녹음 파일도 서빙 시 remux (이미 처리된 파일은 건너뜀)
    await _remux_webm_if_needed(audio_path)
    media_types = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
    }
    media_type = media_types.get(audio_path.suffix.lower(), "application/octet-stream")

    file_size = audio_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Range: bytes=start-end
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(audio_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Disposition": f'inline; filename="{audio_path.name}"',
            },
        )

    # Range 없으면 전체 반환
    return FileResponse(
        path=str(audio_path),
        media_type=media_type,
        filename=audio_path.name,
        headers={"Accept-Ranges": "bytes"},
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


@app.get("/api/stats/monthly")
async def get_monthly_stats():
    """최근 6개월 월별 회의 횟수 + 총 시간(분)을 반환한다."""
    import sqlite3 as _sqlite3
    from .database import DB_PATH
    conn = _sqlite3.connect(str(DB_PATH))
    conn.row_factory = _sqlite3.Row

    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', created_at) AS month,
               COUNT(*) AS count,
               COALESCE(SUM(duration_sec), 0) AS total_seconds
        FROM meetings
        WHERE status = 'done'
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        """
    ).fetchall()
    conn.close()

    items = [
        {
            "month": r["month"],
            "count": r["count"],
            "total_minutes": round(r["total_seconds"] / 60),
        }
        for r in rows
    ]
    items.reverse()
    return items


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
# 15-b) GET /api/settings/backup  — 설정 백업
# ---------------------------------------------------------------------------

@app.get("/api/settings/backup")
async def backup_settings():
    """speakers.json + settings + categories를 JSON으로 내보낸다."""
    from .database import get_categories

    # speakers.json
    speakers_data: dict = {}
    if SPEAKERS_FILE.exists():
        try:
            speakers_data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            speakers_data = {}

    # settings (민감 키 제외, 비밀 키는 백업하지 않음)
    SECRET_KEYS = {"HF_TOKEN", "NOTION_API_KEY", "NOTION_DATABASE_ID"}
    settings_data: dict = {}
    for key in SETTING_KEYS:
        if key in SECRET_KEYS:
            continue
        val = get_setting(key)
        if val:
            settings_data[key] = val

    # categories (사용자 카테고리만 + 내장 카테고리 커스텀 prompt)
    categories_data = []
    for cat in get_categories():
        categories_data.append({
            "id": cat["id"],
            "name": cat["name"],
            "icon": cat["icon"],
            "description": cat["description"],
            "prompt": cat["prompt"],
            "is_builtin": cat["is_builtin"],
            "model": cat.get("model", "claude-sonnet-4-6"),
            "prompt_template": cat.get("prompt_template") or "",
        })

    backup = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "speakers": speakers_data,
        "settings": settings_data,
        "categories": categories_data,
    }

    filename = f"meeting-jr-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return StreamingResponse(
        iter([json.dumps(backup, ensure_ascii=False, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# 15-c) POST /api/settings/restore  — 설정 복원
# ---------------------------------------------------------------------------

@app.post("/api/settings/restore")
async def restore_settings(file: UploadFile = File(...)):
    """백업 JSON 파일에서 설정을 복원한다."""
    from .database import get_category, create_category, update_category

    content = await file.read()
    try:
        backup = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="유효하지 않은 JSON 파일입니다.")

    if not isinstance(backup, dict) or "version" not in backup:
        raise HTTPException(status_code=422, detail="Meeting Junior 백업 파일이 아닙니다.")

    restored = {"speakers": False, "settings": False, "categories": False}

    # speakers 복원
    if "speakers" in backup and isinstance(backup["speakers"], dict):
        existing: dict = {}
        if SPEAKERS_FILE.exists():
            try:
                existing = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                existing = {}
        existing.update(backup["speakers"])
        SPEAKERS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        restored["speakers"] = True

    # settings 복원
    if "settings" in backup and isinstance(backup["settings"], dict):
        for key in SETTING_KEYS:
            if key in backup["settings"]:
                set_setting(key, backup["settings"][key])
        restored["settings"] = True

    # categories 복원
    if "categories" in backup and isinstance(backup["categories"], list):
        for cat_data in backup["categories"]:
            cat_id = cat_data.get("id")
            if not cat_id:
                continue
            existing_cat = get_category(cat_id)
            if existing_cat:
                update_category(cat_id, prompt=cat_data.get("prompt", existing_cat["prompt"]), model=cat_data.get("model", "claude-sonnet-4-6"), prompt_template=cat_data.get("prompt_template", ""))
            elif not cat_data.get("is_builtin"):
                create_category(
                    cat_id,
                    cat_data.get("name", ""),
                    cat_data.get("icon", "📋"),
                    cat_data.get("description", ""),
                    cat_data.get("prompt", "{script}"),
                    model=cat_data.get("model", "claude-sonnet-4-6"),
                    prompt_template=cat_data.get("prompt_template", ""),
                )
        restored["categories"] = True

    return {"status": "restored", **restored}


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
    """제목+요약+스크립트 검색 + 카테고리/날짜/태그 필터 + 페이지네이션."""
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

    model = (body.get("model") or "claude-sonnet-4-6").strip()
    prompt_template = (body.get("prompt_template") or "").strip()
    cat_id = str(uuid.uuid4())
    return create_category(cat_id, name, icon, description, prompt, model=model, prompt_template=prompt_template)


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
    if "model" in body:
        kwargs["model"] = body["model"]
    if "prompt_template" in body:
        kwargs["prompt_template"] = body["prompt_template"]

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
# Recording Notes API
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/notes")
async def save_notes(job_id: str, body: dict):
    """녹음 중 메모/북마크 일괄 저장."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    notes = body.get("notes")
    if not isinstance(notes, list):
        raise HTTPException(status_code=422, detail="notes 리스트가 필요합니다.")
    return save_recording_notes(job_id, notes)


@app.get("/api/jobs/{job_id}/notes")
async def list_notes(job_id: str):
    """해당 job의 노트 목록."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return get_recording_notes(job_id)


@app.delete("/api/jobs/{job_id}/notes/{note_id}")
async def remove_note(job_id: str, note_id: str):
    """개별 노트 삭제."""
    if not delete_recording_note(job_id, note_id):
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"status": "deleted", "id": note_id}


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


def _parse_txt_transcript(raw: str) -> tuple[str, list[str], dict[str, str]]:
    """텍스트 파일의 transcript를 파싱하여 표준 형식으로 변환하고 화자 목록을 반환한다.

    지원 형식:
      1) 표준: [MM:SS] SPEAKER_XX: 텍스트
      2) ClovaNote: 참석자 N MM:SS\\n텍스트 (빈 줄로 구분)

    Returns:
        (변환된 transcript 문자열, 정렬된 화자 목록, suggested_names {SPEAKER_XX: 원본이름})
    """
    # 1) 표준 형식 검사
    standard_pattern = re.compile(r'\[[\d:]+\]\s+(\S+):\s')
    standard_speakers = sorted(set(standard_pattern.findall(raw)))
    if standard_speakers:
        return raw, standard_speakers, {}

    # 2) ClovaNote 형식 변환
    #    "참석자 N MM:SS" 또는 "화자이름 MM:SS" 패턴 (타임스탬프는 줄 끝)
    clova_header = re.compile(r'^(.+?)\s+(\d{2}:\d{2})\s*$')
    lines = raw.split('\n')
    segments: list[tuple[str, str, list[str]]] = []  # (speaker, timestamp, text_lines)
    current_speaker = None
    current_ts = None
    current_text: list[str] = []
    # 헤더 건너뛰기: ClovaNote 파일 상단의 제목/날짜/이름 등
    # 첫 번째 화자 헤더가 나올 때까지의 줄은 무시
    started = False

    for line in lines:
        m = clova_header.match(line)
        if m:
            # 이전 세그먼트 저장
            if current_speaker is not None and current_text:
                segments.append((current_speaker, current_ts, current_text))
            current_speaker = m.group(1).strip()
            current_ts = m.group(2)
            current_text = []
            started = True
        elif started:
            stripped = line.strip()
            if stripped:
                current_text.append(stripped)
            # 빈 줄은 무시 (세그먼트 구분자)

    # 마지막 세그먼트 저장
    if current_speaker is not None and current_text:
        segments.append((current_speaker, current_ts, current_text))

    if not segments:
        # 어떤 형식도 감지 못함 — 원본 그대로 반환
        return raw, [], {}

    # 화자 ID 매핑 (원본 이름 → SPEAKER_XX)
    unique_speakers = list(dict.fromkeys(s[0] for s in segments))
    speaker_id_map = {name: f"SPEAKER_{i:02d}" for i, name in enumerate(unique_speakers)}

    # 표준 형식으로 변환
    result_lines = []
    for speaker_name, ts, text_parts in segments:
        speaker_id = speaker_id_map[speaker_name]
        # MM:SS 형식 통일 (M:SS → 0M:SS)
        parts = ts.split(':')
        normalized_ts = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        combined_text = ' '.join(text_parts)
        result_lines.append(f"[{normalized_ts}] {speaker_id}: {combined_text}")

    converted = '\n'.join(result_lines)
    found_speakers = sorted(speaker_id_map.values())
    # suggested_names: SPEAKER_XX → 원본 이름 (TranscriptEditor에서 화자 이름 자동 입력)
    suggested_names = {sid: name for name, sid in speaker_id_map.items()}

    return converted, found_speakers, suggested_names


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


# ---------------------------------------------------------------------------
# Voice Profile 자동 매칭
# ---------------------------------------------------------------------------

async def match_speaker_to_profiles(speaker_embedding: np.ndarray) -> dict | None:
    """코사인 유사도로 화자 embedding과 프로필 매칭.

    Returns:
        {"profile_id": str, "name": str, "confidence": float} or None
    """
    threshold = get_voice_profile_threshold()
    profiles = get_all_voice_profiles_with_embeddings()
    if not profiles:
        return None

    best_match = None
    best_score = 0.0

    for profile in profiles:
        emb = np.frombuffer(profile["embedding"], dtype=np.float32)
        norm_a = np.linalg.norm(speaker_embedding)
        norm_b = np.linalg.norm(emb)
        if norm_a == 0 or norm_b == 0:
            continue
        score = float(np.dot(speaker_embedding, emb) / (norm_a * norm_b))
        if score > best_score:
            best_score = score
            best_match = profile

    if best_match and best_score >= threshold:
        return {
            "profile_id": best_match["id"],
            "name": best_match["name"],
            "confidence": round(best_score * 100, 1),
        }
    return None


async def _extract_and_match_speakers(
    job_id: str,
    *,
    wav_path: str | None = None,
    diar_segments: dict | None = None,
) -> dict | None:
    """각 화자별 embedding 추출 → match_speaker_to_profiles 호출.

    Returns:
        {"SPEAKER_00": {"name": ..., "confidence": ..., "profile_id": ...} or None, ...}
        diarization 없으면 None 반환.
    """
    from .audio_processor import extract_speaker_embedding
    from .database import get_job_diarization

    if diar_segments is None:
        diar_segments = get_job_diarization(job_id)
        if not diar_segments:
            diar_path = INPUT_DIR / f"{job_id}_diarization.json"
            if diar_path.exists():
                diar_segments = json.loads(diar_path.read_text(encoding="utf-8"))
                update_job_result(job_id, diarization=diar_segments)

    if not diar_segments:
        return None

    if wav_path is None:
        wav_path = str(INPUT_DIR / f"{job_id}_16k.wav")

    result: dict = {}
    for speaker_label, segs in diar_segments.items():
        sorted_segs = sorted(segs, key=lambda s: s["end"] - s["start"], reverse=True)
        selected = sorted_segs[:3]
        embeddings = []
        for seg in selected:
            try:
                emb = extract_speaker_embedding(wav_path, seg["start"], seg["end"])
                embeddings.append(emb)
            except Exception:
                continue
        if embeddings:
            avg_emb = np.mean(embeddings, axis=0).astype(np.float32)
            match_result = await match_speaker_to_profiles(avg_emb)
            result[speaker_label] = match_result
        else:
            result[speaker_label] = None

    return result


@app.post("/api/jobs/{job_id}/rematch")
async def rematch_speakers(job_id: str):
    """완료된 회의의 화자를 voice profile과 재매칭."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="완료된 회의만 재매칭할 수 있습니다.")

    result = await _extract_and_match_speakers(job_id)
    if result is None:
        raise HTTPException(status_code=422, detail="화자 분리 데이터가 없습니다.")

    return {"matches": result}


@app.post("/api/jobs/{job_id}/apply-match")
async def apply_match(job_id: str, body: dict):
    """매칭된 화자명을 transcript와 speakers에 적용."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="완료된 회의만 매칭 적용할 수 있습니다.")

    matches = body.get("matches", {})
    if not matches:
        return {"ok": True}

    transcript = job.get("transcript", "")
    for old_name, new_name in matches.items():
        transcript = transcript.replace(f"{old_name}:", f"{new_name}:")

    speakers = job.get("speakers") or {}
    if isinstance(speakers, str):
        speakers = json.loads(speakers)
    speakers.update(matches)

    update_job_result(job_id, transcript=transcript, speakers=speakers)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Voice Profiles API
# ---------------------------------------------------------------------------

@app.get("/api/voice-profiles")
async def list_voice_profiles():
    """목소리 프로필 목록 (embedding 제외)."""
    return get_voice_profiles()


@app.post("/api/voice-profiles")
async def create_voice_profile_endpoint(
    name: str = Form(...),
    audio: UploadFile = File(...),
):
    """새 목소리 프로필 생성 (오디오 → embedding 추출)."""
    import tempfile
    import subprocess

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=422, detail="오디오 데이터가 없습니다.")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(content)
        tmp_in_path = tmp_in.name

    wav_path = tmp_in_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, check=True,
        )
        from .audio_processor import extract_speaker_embedding
        embedding = await asyncio.to_thread(extract_speaker_embedding, wav_path)
        profile = create_voice_profile(name, embedding.tobytes(), len(embedding))
        return profile
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)
        Path(wav_path).unlink(missing_ok=True)


@app.get("/api/voice-profiles/threshold")
async def get_threshold():
    """매칭 임계값 조회."""
    return {"threshold": get_voice_profile_threshold()}


@app.put("/api/voice-profiles/threshold")
async def set_threshold(body: dict):
    """매칭 임계값 설정."""
    threshold = body.get("threshold")
    if threshold is None or not isinstance(threshold, (int, float)):
        raise HTTPException(status_code=422, detail="threshold (숫자)가 필요합니다.")
    if not (0.0 <= threshold <= 1.0):
        raise HTTPException(status_code=422, detail="threshold는 0~1 범위여야 합니다.")
    set_voice_profile_threshold(float(threshold))
    return {"threshold": float(threshold)}


@app.delete("/api/voice-profiles/{profile_id}")
async def delete_voice_profile_endpoint(profile_id: str):
    """프로필 삭제."""
    if not delete_voice_profile(profile_id):
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
    return {"status": "deleted", "id": profile_id}


@app.post("/api/voice-profiles/{profile_id}/add-sample")
async def add_sample_to_profile(
    profile_id: str,
    audio: UploadFile = File(...),
):
    """기존 프로필에 샘플 추가 (누적 평균)."""
    import tempfile
    import subprocess

    profile = get_voice_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=422, detail="오디오 데이터가 없습니다.")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(content)
        tmp_in_path = tmp_in.name

    wav_path = tmp_in_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, check=True,
        )
        from .audio_processor import extract_speaker_embedding
        new_emb = await asyncio.to_thread(extract_speaker_embedding, wav_path)

        existing_emb = np.frombuffer(profile["embedding"], dtype=np.float32)
        count = profile["sample_count"]
        averaged = (existing_emb * count + new_emb) / (count + 1)
        averaged = averaged.astype(np.float32)

        result = update_voice_profile_embedding(
            profile_id, averaged.tobytes(), count + 1
        )
        return result
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)
        Path(wav_path).unlink(missing_ok=True)


@app.post("/api/jobs/{job_id}/rename-speakers")
async def rename_speakers(job_id: str, body: dict):
    """화자 이름 매핑을 적용한다 (요약 없이 speaker_map만 저장).

    body: {speaker_map: {"SPEAKER_00": "김팀장", ...}}
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    speaker_map: dict = body.get("speaker_map", {})

    update_job_result(job_id, speakers=speaker_map)

    if speaker_map:
        _save_speakers(speaker_map)

    return {"ok": True}


# ---------------------------------------------------------------------------
# 회의 시리즈 CRUD
# ---------------------------------------------------------------------------

@app.post("/api/series")
async def create_series_endpoint(body: dict):
    """시리즈 생성."""
    name = body.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=422, detail="name이 필요합니다.")
    series_id = str(uuid.uuid4())[:8]
    description = body.get("description", "")
    return create_series(series_id, name.strip(), description)


@app.get("/api/series")
async def list_series():
    """시리즈 목록."""
    return {"items": get_all_series()}


@app.get("/api/series/{series_id}")
async def get_series_detail(series_id: str):
    """시리즈 상세 + 연결 회의 목록."""
    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="시리즈를 찾을 수 없습니다.")
    s["meetings"] = get_series_meetings(series_id)
    return s


@app.patch("/api/series/{series_id}")
async def update_series_endpoint(series_id: str, body: dict):
    """시리즈 수정."""
    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="시리즈를 찾을 수 없습니다.")
    return update_series(series_id, **body)


@app.delete("/api/series/{series_id}")
async def delete_series_endpoint(series_id: str):
    """시리즈 삭제."""
    if not delete_series(series_id):
        raise HTTPException(status_code=404, detail="시리즈를 찾을 수 없습니다.")
    return {"ok": True}


# ---------------------------------------------------------------------------
# 회의-시리즈 연결
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/series")
async def assign_series(job_id: str, body: dict):
    """회의에 시리즈 할당/해제. done 상태에서 할당 시 후속조치 자동 생성."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    series_id = body.get("series_id")
    update_job_series(job_id, series_id)

    # done 상태에서 시리즈 할당 시 후속조치 자동 생성 (실패 무시)
    if series_id and job.get("status") == "done":
        try:
            prev = get_previous_series_meeting(job_id, series_id)
            if prev and prev.get("action_items"):
                pending = [ai for ai in prev["action_items"] if not ai.get("done")]
                if pending:
                    _model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"
                    from .summarizer import generate_followup_comparison
                    result = await generate_followup_comparison(
                        pending, job.get("transcript", ""), job.get("summary", ""),
                        model=_model,
                    )
                    update_job_followup(job_id, result)
        except Exception:
            pass  # 자동 생성 실패해도 할당은 완료

    return get_job(job_id)


# ---------------------------------------------------------------------------
# 후속조치 (followup)
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/followup")
async def get_followup(job_id: str):
    """후속조치 조회."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    followup = job.get("followup_items")
    if not followup or not isinstance(followup, list) or len(followup) == 0:
        return {"source_job_id": None, "source_job_title": None, "items": []}

    source_job_id = None
    source_job_title = None
    series_id = job.get("series_id")
    if series_id:
        prev = get_previous_series_meeting(job_id, series_id)
        if prev:
            source_job_id = prev["id"]
            source_job_title = prev.get("title")

    return {"source_job_id": source_job_id, "source_job_title": source_job_title, "items": followup}


@app.patch("/api/jobs/{job_id}/followup")
async def patch_followup(job_id: str, body: dict):
    """후속조치 사용자 확정 (user_status, confirmed)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    updates = body.get("items", [])
    raw_followup = job.get("followup_items")

    # 저장된 followup_items에서 items 리스트 추출
    if isinstance(raw_followup, list):
        items = raw_followup
    elif isinstance(raw_followup, dict) and "items" in raw_followup:
        items = raw_followup["items"]
    else:
        items = []

    for upd in updates:
        idx = upd.get("index")
        if idx is not None and 0 <= idx < len(items):
            if "user_status" in upd:
                items[idx]["user_status"] = upd["user_status"]
            if "confirmed" in upd:
                items[idx]["confirmed"] = upd["confirmed"]

    # list 형태로 저장 (GET에서 source 정보는 동적으로 조합)
    update_job_followup(job_id, items)

    # 응답은 source 정보 포함
    source_job_id = None
    source_job_title = None
    series_id = job.get("series_id")
    if series_id:
        prev = get_previous_series_meeting(job_id, series_id)
        if prev:
            source_job_id = prev["id"]
            source_job_title = prev.get("title")

    return {
        "source_job_id": source_job_id,
        "source_job_title": source_job_title,
        "items": items,
    }


@app.post("/api/jobs/{job_id}/followup/generate")
async def generate_followup(job_id: str):
    """후속조치 대조를 (재)생성한다. claude -p 사용."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    series_id = job.get("series_id")
    if not series_id:
        return {"source_job_id": None, "source_job_title": None, "items": []}

    prev = get_previous_series_meeting(job_id, series_id)
    if not prev or not prev.get("action_items"):
        return {"source_job_id": None, "source_job_title": None, "items": []}

    pending_items = [ai for ai in prev["action_items"] if not ai.get("done")]
    if not pending_items:
        return {"source_job_id": prev["id"], "source_job_title": prev.get("title"), "items": []}

    # claude -p로 대조
    from .summarizer import generate_followup_comparison
    _model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"
    try:
        result = await generate_followup_comparison(
            pending_items, job.get("transcript", ""), job.get("summary", ""),
            model=_model,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"대조 분석 실패: {exc}")

    update_job_followup(job_id, result)
    return {
        "source_job_id": prev["id"],
        "source_job_title": prev.get("title"),
        "items": result,
    }


# ---------------------------------------------------------------------------
# 발언 참여도 분석
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/participation")
async def get_participation(job_id: str):
    """화자별 발언 시간·비율·턴수 분석.

    데이터 소스 우선순위:
      1. diarization DB 조회
      2. diarization 파일 폴백 ({job_id}_diarization.json) + lazy migration
      3. transcript [MM:SS] 화자명: 타임스탬프 폴백
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    speaker_map: dict = job.get("speakers") or {}
    result_speakers: list[dict] = []
    total_duration: float = 0.0

    # --- 1) diarization 기반 (DB → 파일 폴백 + lazy migration) ---
    from .database import get_job_diarization
    diar_data = get_job_diarization(job_id)
    if not diar_data:
        diar_path = INPUT_DIR / f"{job_id}_diarization.json"
        if diar_path.exists():
            diar_data = json.loads(diar_path.read_text(encoding="utf-8"))
            update_job_result(job_id, diarization=diar_data)

    use_diar = False
    if diar_data:
        for label, segments in diar_data.items():
            if not segments:
                # 빈 세그먼트라도 diarization이 존재한다고 간주
                result_speakers.append({
                    "label": label,
                    "display_name": speaker_map.get(label, label),
                    "total_seconds": 0,
                    "percentage": 0.0,
                    "turn_count": 0,
                    "avg_turn_seconds": 0.0,
                })
                use_diar = True
                continue
            total_sec = sum(
                max(seg.get("end", 0) - seg.get("start", 0), 0) for seg in segments
            )
            turn_count = len(segments)
            avg_turn = total_sec / turn_count if turn_count else 0.0
            result_speakers.append({
                "label": label,
                "display_name": speaker_map.get(label, label),
                "total_seconds": round(total_sec, 2),
                "percentage": 0.0,  # 아래에서 재계산
                "turn_count": turn_count,
                "avg_turn_seconds": round(avg_turn, 2),
            })
            use_diar = True
        total_duration = sum(s["total_seconds"] for s in result_speakers)

    # --- 2) transcript 폴백 ---
    if not use_diar:
        transcript: str = job.get("transcript") or ""
        import re as _re
        pattern = _re.compile(r"^\[(\d{1,3}):(\d{2})\]\s*(.+?):\s", _re.MULTILINE)
        matches = list(pattern.finditer(transcript))

        if matches:
            # 각 발언의 시작 시각(초)과 화자
            entries: list[tuple[float, str]] = []
            for m in matches:
                mm, ss, spk = int(m.group(1)), int(m.group(2)), m.group(3)
                entries.append((mm * 60 + ss, spk))

            # 각 발언 구간 = 다음 발언 시작까지, 마지막은 10초 기본값
            from collections import defaultdict
            spk_stats: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "turns": 0})

            for i, (start, spk) in enumerate(entries):
                if i + 1 < len(entries):
                    dur = entries[i + 1][0] - start
                else:
                    dur = 10.0  # 마지막 발언 기본 10초
                if dur < 0:
                    dur = 0
                spk_stats[spk]["total"] += dur
                spk_stats[spk]["turns"] += 1

            for label, stats in spk_stats.items():
                total_sec = stats["total"]
                turn_count = stats["turns"]
                avg_turn = total_sec / turn_count if turn_count else 0.0
                result_speakers.append({
                    "label": label,
                    "display_name": speaker_map.get(label, label),
                    "total_seconds": round(total_sec, 2),
                    "percentage": 0.0,
                    "turn_count": turn_count,
                    "avg_turn_seconds": round(avg_turn, 2),
                })
            total_duration = sum(s["total_seconds"] for s in result_speakers)

    # --- percentage 계산 ---
    if total_duration > 0:
        for sp in result_speakers:
            sp["percentage"] = round(sp["total_seconds"] / total_duration * 100, 2)

    # --- total_seconds 내림차순 정렬 ---
    result_speakers.sort(key=lambda s: s["total_seconds"], reverse=True)

    return {
        "speakers": result_speakers,
        "total_duration": round(total_duration, 2),
    }


@app.post("/api/jobs/{job_id}/save-speaker-profile")
async def save_speaker_profile(job_id: str, body: dict):
    """완료된 회의의 화자를 프로필로 저장.

    body: {speaker_label: "SPEAKER_00", profile_name: "김팀장", profile_id?: "기존ID"}
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    speaker_label = body.get("speaker_label", "").strip()
    profile_name = body.get("profile_name", "").strip()
    profile_id = body.get("profile_id")

    if not speaker_label:
        raise HTTPException(status_code=422, detail="speaker_label이 필요합니다.")
    if not profile_name and not profile_id:
        raise HTTPException(status_code=422, detail="profile_name 또는 profile_id가 필요합니다.")

    # diarization 데이터 로드: DB 우선 → 파일 폴백(+ lazy migration) → WAV 재실행
    from .database import get_job_diarization
    diar_data = get_job_diarization(job_id)
    if not diar_data:
        diar_path = INPUT_DIR / f"{job_id}_diarization.json"
        if diar_path.exists():
            diar_data = json.loads(diar_path.read_text(encoding="utf-8"))
            # lazy migration: 파일 → DB 저장
            update_job_result(job_id, diarization=diar_data)
        else:
            wav_path_for_diar = INPUT_DIR / f"{job_id}_16k.wav"
            if wav_path_for_diar.exists():
                from .audio_processor import run_diarization_and_save
                try:
                    await run_diarization_and_save(str(wav_path_for_diar), job_id)
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"화자 분리 재실행에 실패했습니다: {e}",
                    )
                diar_path = INPUT_DIR / f"{job_id}_diarization.json"
                if diar_path.exists():
                    diar_data = json.loads(diar_path.read_text(encoding="utf-8"))
                    update_job_result(job_id, diarization=diar_data)
            else:
                raise HTTPException(
                    status_code=422,
                    detail="텍스트로 업로드된 회의는 음성 프로필을 추출할 수 없습니다. 음성 녹음 회의에서 추출해주세요.",
                )

    if not diar_data:
        raise HTTPException(status_code=422, detail="화자 분리 데이터를 찾을 수 없습니다.")

    speaker_segs = diar_data.get(speaker_label)

    # speaker_label이 매핑된 이름(예: "김팀장")인 경우, job.speakers에서 역조회
    if not speaker_segs:
        job_speakers = job.get("speakers") or {}
        for key, val in job_speakers.items():
            if val == speaker_label and key in diar_data:
                speaker_label = key
                speaker_segs = diar_data[key]
                break

    # identity mapping ({아빠: 아빠}) 등으로 SPEAKER_XX 매핑이 소실된 경우,
    # transcript 구간과 diarization 세그먼트를 교차 비교하여 추론
    if not speaker_segs:
        transcript = job.get("transcript") or ""
        # transcript의 모든 발화 시작 시각을 파싱하여 각 화자의 구간을 구성
        utterances: list[tuple[float, str]] = []  # (start_sec, speaker_name)
        for line in transcript.split("\n"):
            m = re.match(r"\[(\d+):(\d+)\]\s*(.+?):", line)
            if m:
                t = int(m.group(1)) * 60 + int(m.group(2))
                utterances.append((t, m.group(3).strip()))
        if utterances:
            # 각 발화의 시작~다음 발화 시작까지를 해당 화자의 구간으로 설정
            target_ranges: list[tuple[float, float]] = []
            for i, (t, name) in enumerate(utterances):
                if name == speaker_label:
                    end_t = utterances[i + 1][0] if i + 1 < len(utterances) else t + 30.0
                    target_ranges.append((t, end_t))
            if target_ranges:
                # 각 SPEAKER_XX의 세그먼트가 target 구간에 겹치는 비율로 점수 계산
                best_key = None
                best_score = 0.0
                for diar_key, segs in diar_data.items():
                    score = 0.0
                    for seg in segs:
                        for rng_start, rng_end in target_ranges:
                            overlap = min(seg["end"], rng_end) - max(seg["start"], rng_start)
                            if overlap > 0:
                                score += overlap
                                break
                    if score > best_score:
                        best_score = score
                        best_key = diar_key
                if best_key and best_score > 0:
                    speaker_segs = diar_data[best_key]

    if not speaker_segs:
        raise HTTPException(status_code=422, detail=f"화자 {speaker_label}의 구간을 찾을 수 없습니다.")

    # WAV 파일 경로
    wav_path = INPUT_DIR / f"{job_id}_16k.wav"
    if not wav_path.exists():
        raise HTTPException(status_code=422, detail="WAV 파일이 없어 음성 프로필을 추출할 수 없습니다. 음성 녹음 회의에서 추출해주세요.")

    from .audio_processor import extract_speaker_embedding

    # 길이 기준 상위 3개 구간에서 embedding 추출
    sorted_segs = sorted(speaker_segs, key=lambda s: s["end"] - s["start"], reverse=True)
    selected = sorted_segs[:3]

    embeddings = []
    for seg in selected:
        try:
            emb = await asyncio.to_thread(
                extract_speaker_embedding, str(wav_path), seg["start"], seg["end"]
            )
            embeddings.append(emb)
        except Exception:
            continue

    if not embeddings:
        raise HTTPException(status_code=500, detail="Embedding 추출에 실패했습니다.")

    new_emb = np.mean(embeddings, axis=0).astype(np.float32)

    if profile_id:
        # 기존 프로필에 샘플 추가
        profile = get_voice_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
        existing_emb = np.frombuffer(profile["embedding"], dtype=np.float32)
        count = profile["sample_count"]
        averaged = ((existing_emb * count + new_emb) / (count + 1)).astype(np.float32)
        result = update_voice_profile_embedding(profile_id, averaged.tobytes(), count + 1)
        return result
    else:
        # 새 프로필 생성
        result = create_voice_profile(profile_name, new_emb.tobytes(), len(new_emb))
        return result


# ---------------------------------------------------------------------------
# 노이즈 제거 설정
# ---------------------------------------------------------------------------

@app.get("/api/settings/denoise")
async def get_denoise_setting():
    value = get_setting("AUDIO_DENOISE") or "false"
    return {"enabled": value == "true"}


@app.put("/api/settings/denoise")
async def set_denoise_setting(body: dict):
    enabled = bool(body.get("enabled", False))
    set_setting("AUDIO_DENOISE", "true" if enabled else "false")
    return {"enabled": enabled}


# ---------------------------------------------------------------------------
# 요약 품질 피드백 (별점)
# ---------------------------------------------------------------------------

@app.patch("/api/jobs/{job_id}/rating")
async def rate_job(job_id: str, body: dict):
    """별점(1~5) 저장."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    rating = body.get("rating")
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise HTTPException(status_code=422, detail="rating은 1~5 정수여야 합니다.")
    update_job_rating(job_id, rating)
    return {"ok": True, "rating": rating}


@app.get("/api/stats/ratings")
async def get_ratings_stats():
    """카테고리별 평균 평점."""
    from .database import _get_conn as _db_conn
    conn = _db_conn()
    try:
        rows = conn.execute("""
            SELECT category_id, AVG(rating) as avg_rating, COUNT(rating) as count
            FROM meetings
            WHERE rating IS NOT NULL AND status = 'done'
            GROUP BY category_id
        """).fetchall()
    finally:
        conn.close()
    return [
        {"category_id": r[0] or "meeting", "avg_rating": round(r[1], 1), "count": r[2]}
        for r in rows
    ]
