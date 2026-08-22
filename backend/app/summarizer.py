"""
Claude CLI subprocess를 사용한 회의록 요약 생성.

흐름:
  1. 스크립트 파일 로드 + 화자 이름 치환
  2. claude -p 명령으로 Claude 요약 생성
  3. output/{job_id}_요약.md 저장
  4. speakers.json 업데이트 (이름 기억)
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
SPEAKERS_FILE = BASE_DIR / "speakers.json"


def _replace_speakers(script_content: str, speaker_map: dict) -> str:
    """스크립트 내 SPEAKER_XX를 실제 이름으로 치환한다."""
    result = script_content
    for speaker_id, name in speaker_map.items():
        if name and name.strip():
            result = result.replace(speaker_id, name.strip())
    return result


def _save_speaker_names(speaker_map: dict) -> None:
    """speaker_map의 이름을 speakers.json에 저장하여 다음 회의에서 제안한다."""
    existing: dict = {}
    if SPEAKERS_FILE.exists():
        try:
            existing = json.loads(SPEAKERS_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}

    for speaker_id, name in speaker_map.items():
        if name and name.strip():
            existing[speaker_id] = name.strip()

    SPEAKERS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def generate_summary(
    script_path: str,
    speaker_map: dict,
    job_id: str,
    progress_callback=None,
) -> str:
    """
    화자 이름이 매핑된 스크립트를 Claude CLI로 요약한다.

    Args:
        script_path: 스크립트 파일 경로 (input/{job_id}.txt).
        speaker_map: {"SPEAKER_00": "김팀장", "SPEAKER_01": "손재락"}.
        job_id: 고유 작업 ID.
        progress_callback: 선택적 SSE 콜백.

    Returns:
        마크다운 문자열.
    """
    if progress_callback:
        progress_callback(job_id, {
            "stage": "summarizing",
            "progress": 0,
            "message": "회의록 생성 시작...",
        })

    # 1. 스크립트 파일 로드
    script_file = Path(script_path)
    if not script_file.exists():
        raise FileNotFoundError(f"스크립트 파일을 찾을 수 없습니다: {script_path}")

    script_content = script_file.read_text(encoding="utf-8")

    # 2. 화자 이름 치환
    script_content = _replace_speakers(script_content, speaker_map)

    # 3. speakers.json 업데이트
    _save_speaker_names(speaker_map)

    if progress_callback:
        progress_callback(job_id, {
            "stage": "summarizing",
            "progress": 30,
            "message": "Claude에게 요약 요청 중...",
        })

    # 4. Claude CLI로 요약 생성
    prompt = f"""다음 회의 스크립트를 분석하여 한국어로 회의록을 작성해주세요.

반드시 아래 마크다운 형식을 정확히 따르세요:

# [회의 주제 / 제목]

- 일시: (날짜 추정)
- 참석자: (화자 목록)
- 회의 목적: ...

## 핵심 요약

1~2줄 핵심 요약

## 주요 논의 및 안건

- 안건 1: ...

## 주요 결정 사항

- 결정 1

## 액션 아이템 (To-Do)

- [ ] @담당자 - 작업 내용 (기한: MM/DD)

## 이슈 및 리스크

- 이슈 1

---
회의 스크립트:
{script_content}"""

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI 실패: {stderr.decode()}")

    summary_md = stdout.decode().strip()

    # 5. output/{job_id}_요약.md 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{job_id}_요약.md"
    output_path.write_text(summary_md, encoding="utf-8")
    logger.info("요약 저장 완료: %s", output_path)

    if progress_callback:
        progress_callback(job_id, {
            "stage": "summarizing",
            "progress": 100,
            "message": "회의록 생성 완료",
        })

    return summary_md
