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

DEFAULT_PROMPT = """다음 회의 스크립트를 분석하여 한국어로 회의록을 작성해주세요.

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
{script}"""


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
        if name and name.strip() and name.strip() != speaker_id:
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
    model: str = "claude-sonnet-4-6",
    prompt_template: str | None = None,
    extra_instructions: str | None = None,
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

    # 2. 화자 이름 치환은 여기서 하지 않는다.
    #    스크립트 파일은 이미 render(segments, speaker_map) 출력이다(main.py의
    #    finalize_job·regenerate_summary). 여기서 한 번 더 치환하면 중복 치환이 되어
    #    이름 맞바꾸기({"아빠":"엄마","엄마":"아빠"})에서 두 화자가 한 명으로 붕괴한다.
    #    (게다가 줄 앵커 없는 전체 문자열 .replace()라 본문 텍스트까지 오염시켰다.)

    # 3. speakers.json 업데이트
    _save_speaker_names(speaker_map)

    if progress_callback:
        progress_callback(job_id, {
            "stage": "summarizing",
            "progress": 30,
            "message": "Claude에게 요약 요청 중...",
        })

    # 4. Claude CLI로 요약 생성
    template = prompt_template if prompt_template else DEFAULT_PROMPT
    if extra_instructions and extra_instructions.strip():
        template = f"## 요약 지침\n{extra_instructions.strip()}\n\n{template}"
    if "{script}" in template:
        prompt = template.replace("{script}", script_content)
    else:
        prompt = template + "\n\n---\n회의 스크립트:\n" + script_content

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt, "--model", model,
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


async def generate_followup_comparison(
    pending_items: list[dict],
    transcript: str,
    summary: str,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """이전 회의 미완료 액션아이템을 현재 회의 transcript/summary와 대조한다.

    Returns:
        [{"text": "...", "assignee": "...", "ai_status": "completed"|"mentioned"|"not_mentioned",
          "ai_evidence": "...", "user_status": null, "confirmed": false}, ...]
    """
    items_text = "\n".join(
        f"- {'@'+it['assignee']+' ' if it.get('assignee') else ''}{it['text']}"
        for it in pending_items
    )

    prompt = f"""다음은 이전 회의에서 남은 미완료 액션아이템입니다:

{items_text}

아래는 이번 회의의 내용입니다:

## 회의 요약
{summary}

## 회의 스크립트
{transcript[:3000]}

위 액션아이템 각각에 대해, 이번 회의에서 어떻게 다뤄졌는지 분석하세요.
반드시 아래 JSON 배열 형식으로만 응답하세요 (다른 텍스트 없이):

[
  {{
    "text": "액션아이템 원문",
    "assignee": "담당자",
    "ai_status": "completed 또는 mentioned 또는 not_mentioned",
    "ai_evidence": "근거 (해당 발언 요약 또는 빈 문자열)"
  }}
]

- completed: 이번 회의에서 완료되었거나 완료 보고된 항목
- mentioned: 언급은 되었으나 완료 여부 불확실
- not_mentioned: 이번 회의에서 전혀 언급되지 않음"""

    import re

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt, "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI 실패: {stderr.decode()}")

    raw = stdout.decode().strip()
    # JSON 파싱 (마크다운 코드블록 안에 있을 수 있음)
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not json_match:
        raise ValueError("JSON 배열을 찾을 수 없습니다")

    items = json.loads(json_match.group())

    # user_status, confirmed 필드 추가
    for item in items:
        item.setdefault("user_status", None)
        item.setdefault("confirmed", False)

    return items
