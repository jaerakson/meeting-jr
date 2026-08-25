"""
오디오 처리 파이프라인: FFmpeg 변환 + PyAnnote 화자분리 + MLX-Whisper STT.

처리 흐름:
  1. FFmpeg: 입력 오디오 -> 16kHz 모노 WAV
  2. PyAnnote: 화자 분리 (MPS 우선, CPU 폴백)
  3. MLX-Whisper: 한국어 STT (word_timestamps)
  4. 화자-텍스트 매핑 -> input/{job_id}.txt 저장
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import numpy as np
import ffmpeg
import torch
import torchaudio
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# torchaudio 2.5+ 호환성 패치 (pyannote.audio 3.x가 구버전 API 사용)
# ---------------------------------------------------------------------------
if not hasattr(torchaudio, 'AudioMetaData'):
    from collections import namedtuple
    torchaudio.AudioMetaData = namedtuple(
        'AudioMetaData', ['sample_rate', 'num_frames', 'num_channels', 'bits_per_sample', 'encoding']
    )

import soundfile as _sf
import numpy as _np

if not hasattr(torchaudio, 'list_audio_backends'):
    def _list_audio_backends():
        return ['soundfile']
    torchaudio.list_audio_backends = _list_audio_backends

if not hasattr(torchaudio, 'info'):
    def _torchaudio_info(path, backend=None):
        info = _sf.info(str(path))
        return torchaudio.AudioMetaData(
            sample_rate=info.samplerate,
            num_frames=info.frames,
            num_channels=info.channels,
            bits_per_sample=16,
            encoding='PCM_S',
        )
    torchaudio.info = _torchaudio_info

# torchaudio.load: soundfile 기반 구현으로 교체
_orig_torchaudio_load = torchaudio.load
def _sf_torchaudio_load(path, frame_offset=0, num_frames=-1, normalize=True,
                         channels_first=True, format=None, backend=None, **kwargs):
    """soundfile 기반 torchaudio.load 대체 구현."""
    import torch
    data, sr = _sf.read(str(path), start=frame_offset,
                         frames=num_frames if num_frames > 0 else -1,
                         dtype='float32', always_2d=True)
    # data: (frames, channels) → tensor (channels, frames)
    tensor = torch.from_numpy(data.T if channels_first else data)
    return tensor, sr
torchaudio.load = _sf_torchaudio_load

import functools
import torch as _torch_pre

# PyTorch 2.6+ weights_only 기본값을 False로 설정 (pyannote import 전에 적용)
# None이 명시적으로 전달되어도 False로 처리
_orig_torch_load = getattr(_torch_pre.load, '__wrapped__', _torch_pre.load)

@functools.wraps(_orig_torch_load)
def _safe_torch_load(*args, **kwargs):
    if kwargs.get('weights_only') is None:
        kwargs['weights_only'] = False
    return _orig_torch_load(*args, **kwargs)

_torch_pre.load = _safe_torch_load

import huggingface_hub as _hf_hub

def _make_auth_compat(fn):
    """use_auth_token 키워드를 token으로 변환하는 래퍼."""
    @functools.wraps(fn)
    def _compat(*args, **kwargs):
        if 'use_auth_token' in kwargs:
            token = kwargs.pop('use_auth_token')
            kwargs.setdefault('token', token)
        return fn(*args, **kwargs)
    return _compat

# huggingface_hub 모듈 자체 패치
for _fn_name in ('hf_hub_download', 'snapshot_download', 'cached_download'):
    _orig = getattr(_hf_hub, _fn_name, None)
    if _orig is not None:
        setattr(_hf_hub, _fn_name, _make_auth_compat(_orig))

from pyannote.audio import Pipeline as DiarizationPipeline

# pyannote가 이미 import한 로컬 참조도 패치
import pyannote.audio.core.pipeline as _pyannote_pipeline
if hasattr(_pyannote_pipeline, 'hf_hub_download'):
    _pyannote_pipeline.hf_hub_download = _make_auth_compat(
        _hf_hub.hf_hub_download.__wrapped__ if hasattr(_hf_hub.hf_hub_download, '__wrapped__') else _hf_hub.hf_hub_download
    )

from pyannote.audio import Model as EmbeddingModel, Inference as EmbeddingInference
from pyannote.core import Segment

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
SPEAKERS_FILE = BASE_DIR / "speakers.json"


# ---------------------------------------------------------------------------
# Speaker Embedding 모델 캐시 + 추출 함수
# ---------------------------------------------------------------------------

_embedding_model_cache: dict = {}


def _get_hf_token() -> str:
    """settings_manager에서 HF_TOKEN을 가져온다."""
    from .settings_manager import get_setting
    hf_token = get_setting("HF_TOKEN")
    if not hf_token:
        raise ValueError(
            "HF_TOKEN이 설정되지 않았습니다. "
            "설정 화면에서 HuggingFace 토큰을 입력하세요."
        )
    return hf_token


def _get_embedding_model(hf_token: str) -> EmbeddingModel:
    """Embedding 모델을 캐시하여 반환한다."""
    if "model" not in _embedding_model_cache:
        model = EmbeddingModel.from_pretrained(
            "pyannote/embedding", use_auth_token=hf_token
        )
        try:
            if torch.backends.mps.is_available():
                device = torch.device("mps")
            else:
                device = torch.device("cpu")
        except Exception:
            device = torch.device("cpu")
        _embedding_model_cache["model"] = model.to(device)
    return _embedding_model_cache["model"]


def extract_speaker_embedding(
    wav_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> np.ndarray:
    """
    WAV 파일(또는 특정 구간)에서 speaker embedding 추출.

    Args:
        wav_path: WAV 파일 경로
        start_sec: 시작 시간 (None이면 전체)
        end_sec: 종료 시간 (None이면 전체)

    Returns:
        numpy array (float32), shape: (embedding_dim,) — 보통 192 또는 512
    """
    hf_token = _get_hf_token()
    model = _get_embedding_model(hf_token)
    inference = EmbeddingInference(model, window="whole")

    if start_sec is not None and end_sec is not None:
        duration = end_sec - start_sec
        if duration < 1.0:
            logger.warning(
                "구간이 %.2f초로 너무 짧습니다 (< 1초). "
                "embedding 신뢰도가 낮을 수 있습니다.", duration
            )
        embedding = inference.crop(wav_path, Segment(start_sec, end_sec))
    else:
        embedding = inference(wav_path)

    return np.array(embedding, dtype=np.float32).flatten()


def extract_embeddings_from_diarization(
    wav_path: str,
    diarization_result: dict,
) -> dict[str, np.ndarray]:
    """
    diarization 결과의 각 화자별 embedding 추출.

    각 화자의 구간들 중 5초 이상인 구간을 우선 사용하고,
    여러 구간이 있으면 평균을 낸다.

    Args:
        wav_path: WAV 파일 경로
        diarization_result: {"segments": [{"speaker": "SPEAKER_00", "start": 0.5, "end": 3.2}, ...]}

    Returns:
        {"SPEAKER_00": np.ndarray, "SPEAKER_01": np.ndarray, ...}
    """
    segments = diarization_result.get("segments", [])

    # 화자별 구간 수집
    speaker_segments: dict[str, list[dict]] = {}
    for seg in segments:
        speaker = seg["speaker"]
        speaker_segments.setdefault(speaker, []).append(seg)

    result: dict[str, np.ndarray] = {}

    for speaker, segs in speaker_segments.items():
        # 길이 기준 내림차순 정렬
        segs_sorted = sorted(segs, key=lambda s: s["end"] - s["start"], reverse=True)

        # 5초 이상 구간 우선, 없으면 가장 긴 구간 최대 3개
        long_segs = [s for s in segs_sorted if (s["end"] - s["start"]) >= 5.0]
        selected = long_segs[:3] if long_segs else segs_sorted[:3]

        embeddings = []
        for seg in selected:
            try:
                emb = extract_speaker_embedding(wav_path, seg["start"], seg["end"])
                embeddings.append(emb)
            except Exception as e:
                logger.warning(
                    "화자 %s 구간 [%.1f-%.1f] embedding 추출 실패: %s",
                    speaker, seg["start"], seg["end"], e,
                )

        if embeddings:
            result[speaker] = np.mean(embeddings, axis=0).astype(np.float32)
        else:
            logger.warning("화자 %s의 embedding을 추출할 수 없습니다.", speaker)

    return result


# ---------------------------------------------------------------------------
# 1. FFmpeg 변환
# ---------------------------------------------------------------------------

async def convert_audio(
    input_path: str,
    output_path: str,
    progress_callback,
    job_id: str,
) -> float:
    """입력 오디오를 16kHz 모노 WAV로 변환한다. 오디오 길이(초)를 반환."""
    progress_callback(job_id, {
        "stage": "converting",
        "progress": 0,
        "message": "오디오 변환 시작...",
    })

    def _convert() -> float:
        probe = ffmpeg.probe(str(input_path))
        # format.duration이 없는 webm 등에 대한 폴백
        fmt = probe.get("format", {})
        if "duration" in fmt:
            duration = float(fmt["duration"])
        else:
            # 스트림에서 duration 시도
            streams = probe.get("streams", [])
            duration = 0.0
            for s in streams:
                if "duration" in s:
                    duration = float(s["duration"])
                    break
        (
            ffmpeg
            .input(str(input_path))
            .output(str(output_path), ar=16000, ac=1, f="wav")
            .overwrite_output()
            .run(quiet=True)
        )
        return duration

    duration = await asyncio.to_thread(_convert)

    progress_callback(job_id, {
        "stage": "converting",
        "progress": 100,
        "message": "오디오 변환 완료",
    })
    return duration


# ---------------------------------------------------------------------------
# 2. PyAnnote 화자 분리
# ---------------------------------------------------------------------------

async def run_diarization(
    wav_path: str,
    progress_callback,
    job_id: str,
):
    """PyAnnote로 화자 분리를 수행한다. MPS 우선, 실패 시 CPU 폴백."""
    progress_callback(job_id, {
        "stage": "diarizing",
        "progress": 0,
        "message": "화자 분리 시작...",
    })

    def _diarize():
        from .settings_manager import get_setting
        hf_token = get_setting("HF_TOKEN")
        if not hf_token:
            raise ValueError(
                "HF_TOKEN이 설정되지 않았습니다. "
                "설정 화면에서 HuggingFace 토큰을 입력하세요."
            )

        # MPS 디바이스 선택 (M1 가속), 실패 시 CPU
        try:
            if torch.backends.mps.is_available():
                device = torch.device("mps")
            else:
                device = torch.device("cpu")
                logger.warning("MPS 미지원 환경 — CPU로 화자 분리를 수행합니다.")
        except Exception:
            device = torch.device("cpu")
            logger.warning("MPS 확인 실패 — CPU로 화자 분리를 수행합니다.")

        pipeline = DiarizationPipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )

        try:
            pipeline = pipeline.to(device)
        except Exception:
            logger.warning("MPS 전송 실패 — CPU 폴백으로 화자 분리를 수행합니다.")
            pipeline = pipeline.to(torch.device("cpu"))

        return pipeline(str(wav_path))

    progress_callback(job_id, {
        "stage": "diarizing",
        "progress": 30,
        "message": "화자 분리 모델 로딩...",
    })

    diarization = await asyncio.to_thread(_diarize)

    progress_callback(job_id, {
        "stage": "diarizing",
        "progress": 100,
        "message": "화자 분리 완료",
    })
    return diarization


# ---------------------------------------------------------------------------
# 3. MLX-Whisper STT
# ---------------------------------------------------------------------------

async def run_transcription(
    wav_path: str,
    progress_callback,
    job_id: str,
    language: str | None = "ko",
) -> dict:
    """MLX-Whisper로 음성 인식을 수행한다. language=None이면 자동 감지."""
    progress_callback(job_id, {
        "stage": "transcribing",
        "progress": 0,
        "message": "음성 인식 시작...",
    })

    def _transcribe():
        import mlx_whisper

        return mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            language=language,
            word_timestamps=True,
        )

    progress_callback(job_id, {
        "stage": "transcribing",
        "progress": 30,
        "message": "음성 인식 중...",
    })

    result = await asyncio.to_thread(_transcribe)

    progress_callback(job_id, {
        "stage": "transcribing",
        "progress": 100,
        "message": "음성 인식 완료",
    })
    return result


# ---------------------------------------------------------------------------
# 4. 화자-텍스트 매핑
# ---------------------------------------------------------------------------

def _find_speaker(diarization, time_sec: float) -> str:
    """주어진 시각(초)이 속하는 화자 레이블을 반환한다."""
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if turn.start <= time_sec < turn.end:
            return speaker
    # 매칭 실패 시 가장 가까운 턴의 화자를 반환
    best_speaker = "UNKNOWN"
    best_dist = float("inf")
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        dist = min(abs(turn.start - time_sec), abs(turn.end - time_sec))
        if dist < best_dist:
            best_dist = dist
            best_speaker = speaker
    return best_speaker


def merge_and_save(diarization, transcription: dict, job_id: str):
    """
    화자 분리 결과와 STT 결과를 매핑하여 스크립트 파일로 저장한다.

    형식: [MM:SS] SPEAKER_00: 텍스트

    Returns:
        (script_path, speakers_list)
    """
    segments = transcription.get("segments", [])
    lines: list[str] = []
    speakers_set: set[str] = set()

    # 이전 화자를 추적하여 연속 같은 화자 합침
    prev_speaker: str | None = None
    prev_timestamp: str | None = None
    prev_text: str = ""

    for seg in segments:
        start_sec = seg.get("start", 0.0)
        text = seg.get("text", "").strip()
        if not text:
            continue

        speaker = _find_speaker(diarization, start_sec)
        speakers_set.add(speaker)

        minutes = int(start_sec) // 60
        seconds = int(start_sec) % 60
        timestamp = f"[{minutes:02d}:{seconds:02d}]"

        if speaker == prev_speaker and prev_text:
            # 연속 같은 화자 — 텍스트 합침
            prev_text += " " + text
        else:
            # 이전 화자 저장
            if prev_speaker is not None and prev_text:
                lines.append(f"{prev_timestamp} {prev_speaker}: {prev_text}")
            prev_speaker = speaker
            prev_timestamp = timestamp
            prev_text = text

    # 마지막 화자 저장
    if prev_speaker is not None and prev_text:
        lines.append(f"{prev_timestamp} {prev_speaker}: {prev_text}")

    # 파일 저장
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    script_path = INPUT_DIR / f"{job_id}.txt"
    script_path.write_text("\n".join(lines), encoding="utf-8")

    speakers_list = sorted(speakers_set)
    return script_path, speakers_list


# ---------------------------------------------------------------------------
# 5. speakers.json 로드
# ---------------------------------------------------------------------------

def load_suggested_names() -> dict:
    """speakers.json에서 이전에 사용된 화자 이름을 로드한다."""
    if SPEAKERS_FILE.exists():
        try:
            data = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# ---------------------------------------------------------------------------
# 메인 파이프라인
# ---------------------------------------------------------------------------

async def process_audio(
    file_path: str,
    job_id: str,
    progress_callback,
    language: str | None = "ko",
) -> dict:
    """
    오디오 파일을 처리하여 화자 분리 + STT를 수행한다.

    Args:
        file_path: 업로드된 원본 오디오 파일 경로.
        job_id: 고유 작업 ID.
        progress_callback: progress_callback(job_id, {"stage": ..., "progress": ..., "message": ...})

    Returns:
        {
            "script_path": "input/{job_id}.txt",
            "speakers": ["SPEAKER_00", "SPEAKER_01", ...],
            "suggested_names": {"SPEAKER_00": "김팀장", ...},
            "duration_sec": 1234,
        }
    """
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = INPUT_DIR / f"{job_id}_16k.wav"

    # 1. FFmpeg 변환
    duration = await convert_audio(file_path, str(wav_path), progress_callback, job_id)

    # 2. 화자 분리
    diarization = await run_diarization(str(wav_path), progress_callback, job_id)

    # 3. STT
    transcription = await run_transcription(str(wav_path), progress_callback, job_id, language=language)

    # 4. 매핑 + 저장
    script_path, speakers = merge_and_save(diarization, transcription, job_id)

    # 5. speakers.json에서 제안 이름 로드
    suggested = load_suggested_names()

    # 6. diarization 세그먼트를 JSON으로 저장 (voice profile 매칭용)
    diar_segments: dict[str, list[dict]] = {}
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        diar_segments.setdefault(speaker, []).append({
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "speaker": speaker,
        })
    diar_path = INPUT_DIR / f"{job_id}_diarization.json"
    diar_path.write_text(json.dumps(diar_segments, ensure_ascii=False), encoding="utf-8")

    return {
        "script_path": str(script_path),
        "speakers": speakers,
        "suggested_names": suggested,
        "duration_sec": int(duration),
        "wav_path": str(wav_path),
        "diarization_segments": diar_segments,
    }
