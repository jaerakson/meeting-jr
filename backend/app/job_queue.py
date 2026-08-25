"""
asyncio Queue 기반 단일 순차 처리.
- 전역 asyncio.Queue 에서 job_id를 꺼내 audio_processor.process_audio() 호출
- progress_store: SSE용 진행률 메모리 저장
"""

import asyncio
import traceback
from pathlib import Path
from typing import Dict

from .database import update_job_status, update_job_result

# ---------------------------------------------------------------------------
# 전역 Queue & 진행률 저장소
# ---------------------------------------------------------------------------

job_queue: asyncio.Queue = asyncio.Queue(maxsize=0)

progress_store: Dict[str, dict] = {}


def update_progress(job_id: str, data: dict) -> None:
    """SSE 진행률 데이터를 갱신한다."""
    progress_store[job_id] = data


# ---------------------------------------------------------------------------
# Worker 코루틴
# ---------------------------------------------------------------------------

async def start_worker() -> None:
    """
    Queue에서 job_id를 하나씩 꺼내 audio_processor.process_audio()를 호출한다.
    처리 완료 후 status를 'awaiting_edit'으로 변경한다.
    """
    while True:
        job_id: str = await job_queue.get()
        try:
            update_progress(job_id, {
                "stage": "pending",
                "progress": 0,
                "message": "처리 대기 중...",
            })

            from .audio_processor import process_audio
            from .database import get_job as _get_job

            job_data = _get_job(job_id)
            if not job_data:
                raise ValueError(f"Job {job_id}을 찾을 수 없습니다.")

            # input/ 디렉토리에서 job_id로 시작하는 오디오 파일 찾기 (.webm 포함)
            input_dir = Path(__file__).resolve().parent.parent / "input"
            audio_exts = {'.mp3', '.m4a', '.wav', '.webm', '.mp4', '.ogg'}
            audio_files = [f for f in input_dir.glob(f"{job_id}.*")
                           if f.suffix.lower() in audio_exts]
            if not audio_files:
                raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {job_id}")
            file_path = str(audio_files[0])

            language = job_data.get("language") or "ko"
            result = await process_audio(file_path, job_id, lambda jid, data: update_progress(jid, data), language=language)

            # transcript + duration DB 저장
            script_path = result.get("script_path", "")
            transcript_text = ""
            if script_path:
                transcript_text = Path(script_path).read_text(encoding="utf-8")
                update_job_result(
                    job_id,
                    transcript=transcript_text,
                    duration_sec=result.get("duration_sec"),
                )

            # Voice Profile 자동 매칭
            suggested_speakers: dict = {}
            wav_path = result.get("wav_path")
            diar_segments = result.get("diarization_segments", {})
            if wav_path and diar_segments:
                try:
                    from .audio_processor import extract_speaker_embedding
                    from .main import match_speaker_to_profiles
                    import numpy as _np

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
                            avg_emb = _np.mean(embeddings, axis=0).astype(_np.float32)
                            match_result = await match_speaker_to_profiles(avg_emb)
                            if match_result:
                                suggested_speakers[speaker_label] = match_result
                except Exception:
                    traceback.print_exc()

            # awaiting_edit 상태로 전환 — suggested_names를 DB에 저장해 페이지 새로고침 후에도 복원
            update_job_result(job_id, speakers=result.get("suggested_names", {}), suggested_speakers=suggested_speakers)
            update_job_status(job_id, "awaiting_edit")
            update_progress(job_id, {
                "stage": "awaiting_edit",
                "progress": 100,
                "message": "텍스트를 확인하고 편집해주세요.",
                "transcript": transcript_text,
                "speakers": result.get("speakers", []),
                "suggested_names": result.get("suggested_names", {}),
                "suggested_speakers": suggested_speakers,
            })

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            update_job_status(job_id, "error", error_msg)
            update_progress(job_id, {
                "stage": "error",
                "progress": 0,
                "message": error_msg,
            })

        finally:
            job_queue.task_done()
