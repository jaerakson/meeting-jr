"""transcript 문자열 ↔ 구조화 세그먼트 변환.

PR A(화자 매핑 라벨 기반 리팩터링)의 기반 모듈. 설계 문서:
docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md

## 세그먼트 표현
    {"start": int|None, "end": float|None, "label": str|None, "text": str, "raw": str}
    - start: 발화 시작 초. 구조화 실패 줄은 None.
    - end:   발화 종료 초. 문자열 파싱으로는 알 수 없으므로 항상 None이고,
             merge_and_save(diarization 경로)에서만 실제 값이 채워진다.
    - label: 화자 라벨(SPEAKER_XX 또는 실명). 구조화 실패 줄은 None.
    - text:  발화 본문. 구조화 실패 줄은 원본 줄 전체.
    - raw:   정규형 렌더가 원본 줄과 바이트 동일하지 **않을 때만** 존재하는 선택 키.
             동일하면 키 자체를 넣지 않는다(JSON 비대화 방지).

## 강제 불변식
    render(parse(s)) == s   (바이트 동일)

구조화 실패 줄을 버리지 않고 passthrough로 보존하고, 정규형으로 복원되지 않는 줄만
`raw`에 원문을 담아 무손실을 보장한다.
"""

import json
import logging
import re
from typing import Optional, Union

logger = logging.getLogger(__name__)

# 1단: 표준 줄 `[MM:SS] LABEL: TEXT`
#   - 분(minute)은 자릿수 무제한 `\d+` — 100분 초과 회의 대응
#     (기존 finalize의 `\d{2}`가 [123:45]를 놓치던 결함의 고정 지점)
#   - 라벨은 `.+?` — 공백 포함 실명("김 팀장") 통과 필수. `\S+` 금지.
#     비탐욕이므로 최초의 ": "에서 끊긴다 → "PM:김철수: 본문"은 label="PM:김철수"로 정확히 갈린다.
_STRICT = re.compile(r'^\[(\d+):(\d{2})\]\s(.+?):\s(.*)$')

# 2단: 콜론에서 줄이 끝나는 빈 발언만. 1단이 실패했을 때만 시도한다.
#   `\s?` 식의 완화는 쓰지 않는다 — "[00:00] 결론:다음주로" 가 label="결론"으로 잡히는
#   오탐(이 리팩터링이 없애려는 바로 그 부류)이 생기기 때문이다.
_EMPTY = re.compile(r'^\[(\d+):(\d{2})\]\s(.+?):$')


def _canonical_line(start: Optional[int], display: str, text: str) -> str:
    """정규형 한 줄. 생산자 2곳의 출력 포맷과 바이트 동일해야 한다.

    audio_processor.merge_and_save: f"[{minutes:02d}:{seconds:02d}] {speaker}: {text}"
    main._parse_txt_transcript:     f"[{normalized_ts}] {speaker_id}: {combined_text}"
    """
    total = int(start or 0)
    return f"[{total // 60:02d}:{total % 60:02d}] {display}: {text}"


def parse(transcript: str) -> list[dict]:
    """transcript 문자열을 줄 단위로 파싱해 세그먼트 목록을 만든다.

    빈 문자열은 []. 그 외에는 세그먼트 개수 == 원본 줄 개수(무손실).
    """
    if not transcript:
        return []

    segments: list[dict] = []
    for line in transcript.split("\n"):
        m = _STRICT.match(line)
        text_is_empty_form = False
        if not m:
            m = _EMPTY.match(line)
            text_is_empty_form = bool(m)

        if not m:
            # 구조 파싱 실패 — 원본 줄을 그대로 보존한다(버리지 않는다).
            segments.append({"start": None, "end": None, "label": None, "text": line})
            continue

        # 라벨 앞뒤 공백은 제거한다(내부 공백은 보존 — "김 팀장"은 그대로).
        # 공백 한 칸 때문에 ' SPEAKER_00' 이 되면 speaker_map 치환이 조용히 실패하고,
        # 그 줄만 화자 이름 변경 대상에서 빠진다 — 이 리팩터링이 없애려는 버그 계열이다.
        label = m.group(3).strip()
        if not label:
            # 라벨이 공백뿐이면 라벨로 인정하지 않는다.
            segments.append({"start": None, "end": None, "label": None, "text": line})
            continue

        minutes, seconds = int(m.group(1)), int(m.group(2))
        text = "" if text_is_empty_form else m.group(4)
        start = minutes * 60 + seconds

        seg: dict = {"start": start, "end": None, "label": label, "text": text}
        # 정규형으로 되돌려 원본과 다를 때만 raw를 남긴다(빈 발언 줄, 탭·비정규 자릿수 등).
        if _canonical_line(start, label, text) != line:
            seg["raw"] = line
        segments.append(seg)

    return segments


def render(segments: list[dict], speaker_map: Optional[dict] = None) -> str:
    """세그먼트 목록을 transcript 문자열로 되돌린다.

    - label이 None인 passthrough 세그먼트는 speaker_map과 **무관하게** text를 원문 그대로 출력한다.
      본문에 'SPEAKER_00' 같은 문자열이 있어도 치환하지 않는다(나이브 .replace 본문 오염 봉쇄점).
    - raw는 표시 이름이 라벨과 같을 때만 쓴다. 치환이 실제로 일어나면 정규형으로 렌더한다
      — raw의 목적은 "아무도 안 건드렸을 때 바이트 동일"이지 치환 차단이 아니다.
    """
    lines: list[str] = []
    for seg in segments:
        label = seg.get("label")
        text = seg.get("text") or ""
        if label is None:
            lines.append(text)
            continue

        # 빈 문자열·공백뿐인 매핑 값은 매핑이 없는 것으로 취급한다.
        # (rename-speakers의 프론트 초기값이 ''이라 실제로 도달 가능한 입력이고,
        #  그대로 치환하면 화자 이름을 지운다.) 빈 값은 display == label 로 수렴해
        # 아래 raw 우선순위 규칙에 자연히 흡수된다.
        display = ((speaker_map or {}).get(label) or "").strip() or label
        raw = seg.get("raw")
        if raw is not None and display == label:
            lines.append(raw)
        else:
            lines.append(_canonical_line(seg.get("start"), display, text))
    return "\n".join(lines)


def get_segments(job_or_id: Union[str, dict]) -> list[dict]:
    """job의 세그먼트를 반환한다. 없으면 transcript를 lazy 파싱하고 DB에 백필한다.

    diarization의 DB→파일 폴백 + update_job_result 백필과 동일한 패턴(main.py:2364-2367).
    일괄 마이그레이션하지 않는다.

    저장된 segments가 빈 리스트면 재파싱한다 — 빈 transcript로 만들어진 행이 []로 굳어
    이후 transcript가 채워져도 계속 []를 반환하는 것을 막기 위함이다(재파싱 결과도 []라 부작용 없음).

    백필 전 `render(parsed) == transcript` 를 검증하고, 불일치하면 **DB에 쓰지 않고**
    파싱 결과만 반환한다(조용한 오염 방지).
    """
    from .database import get_job, update_job_result

    if isinstance(job_or_id, dict):
        job = job_or_id
        job_id = job.get("id")
    else:
        job_id = job_or_id
        job = get_job(job_id)
    if not job:
        return []

    stored = job.get("transcript_segments")
    if stored:
        # database._row_to_dict 를 거친 job은 이미 list다. 다만 이 함수는 dict를 직접
        # 받는 시그니처라(job_or_id), _row_to_dict를 거치지 않고 만들어진 dict가 들어올 수
        # 있어 문자열 방어를 남긴다.
        if isinstance(stored, str):
            try:
                stored = json.loads(stored)
            except (json.JSONDecodeError, TypeError):
                stored = None
        if isinstance(stored, list) and stored:
            return stored

    transcript = job.get("transcript") or ""
    if not transcript:
        return []

    segments = parse(transcript)
    if job_id:
        if render(segments) == transcript:
            update_job_result(job_id, transcript_segments=segments)
        else:
            logger.warning(
                "transcript_segments 백필 생략 — 왕복 불일치 (job_id=%s)", job_id
            )
    return segments
