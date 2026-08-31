"""app.transcript (`parse` / `render`) 계약 테스트 — PR A.

이 파일은 구현(backend-dev)보다 먼저 작성된 명세다. 설계 문서:
docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md

## 가정한 API 계약 (설계 문서가 함수명만 정하고 시그니처는 비워둠 — QA가 아래로 확정)

    parse(raw: str) -> list[dict]
        각 세그먼트: {"start": int(초) | None, "end": None, "label": str | None, "text": str}
        - 표준 줄 `[MM:SS] LABEL: TEXT` (MM은 자릿수 무제한, SS는 정확히 2자리,
          LABEL과 TEXT 사이 구분자는 정확히 ": " 한 칸)에 매칭되면 구조화된 세그먼트.
        - 매칭 실패(타임스탬프 없음/깨진 형식/빈 줄)는 원본 줄을 그대로 보존하는
          passthrough 세그먼트: {"start": None, "end": None, "label": None, "text": <원본 줄>}.
        - raw == "" 이면 [] 반환.
        - 줄바꿈(\\n) 기준으로 줄 단위 파싱. 세그먼트 개수 == 원본 줄 개수(빈 문자열 제외 규칙 없음).

    render(segments: list[dict], speaker_map: dict | None = None) -> str
        - label이 있는 세그먼트: f"[{MM:02d}:{SS:02d}] {speaker_map.get(label, label) if speaker_map else label}: {text}"
        - label이 None인 세그먼트(passthrough): text를 그대로 한 줄로 출력.
        - "\\n".join(lines) 로 재조립.
        - speaker_map을 넘기지 않거나 빈 값이면 label을 그대로 사용 (identity) →
          render(parse(s)) == s 를 보장하는 핵심 성질.

    이 두 함수만으로 "PR A 합격 기준: render(parse(s)) == s" 를 검증한다.
    get_segments()의 백필 계약은 test_transcript_backfill.py 에서 별도 검증.
"""

import pytest

# app.transcript는 PR A 구현 전까지 존재하지 않는다 (TDD red 상태).
# 모듈 자체가 없으면 skip으로 표시해 다른 테스트 파일의 수집을 막지 않는다.
# 모듈이 생기고 나면 정상적으로 import되어 실제 실패/통과가 드러난다.
pytest.importorskip("app.transcript")
from app.transcript import parse, render


# ---------------------------------------------------------------------------
# 왕복 무손실 코퍼스 — render(parse(s)) == s
# ---------------------------------------------------------------------------

ROUNDTRIP_CASES = {
    "표준 단일 세그먼트": "[00:00] SPEAKER_00: 안녕하세요",
    "표준 다중 세그먼트": (
        "[00:00] SPEAKER_00: 안녕하세요\n"
        "[00:03] SPEAKER_01: 반갑습니다\n"
        "[00:07] SPEAKER_00: 오늘 회의 시작하겠습니다"
    ),
    "ClovaNote 유래 변환 결과 (멀티라인 병합 텍스트)": (
        "[00:00] SPEAKER_00: 어떤 위세 메타나 뭐 쓰고 계세요?\n"
        "[00:03] SPEAKER_01: 아니요. 기관 행안부에서 내려\n"
        "[00:05] SPEAKER_00: 그걸 쓰고 계신 거죠? 그러면 표준 사전이 따로 있진 않으시겠네요."
    ),
    "화자 이름에 콜론 포함 (naive replace가 남긴 실데이터 형태)": (
        "[00:00] PM:김철수: 오늘 안건은 세 가지입니다\n"
        "[00:10] SPEAKER_01: 네 알겠습니다"
    ),
    "화자 이름에 대괄호 포함": (
        "[00:00] PM[신규]: 시작하겠습니다\n"
        "[00:05] SPEAKER_01: 넵"
    ),
    "공백 포함 실명": (
        "[00:00] 김 팀장: 회의 시작합니다\n"
        "[00:12] 이 대리: 네 준비됐습니다"
    ),
    "100분 초과 회의 (자릿수 무제한)": (
        "[98:30] SPEAKER_00: 슬슬 마무리하죠\n"
        "[123:45] SPEAKER_01: 네 마지막 안건입니다\n"
        "[130:02] SPEAKER_00: 좋습니다 여기서 마치겠습니다"
    ),
    "빈 줄이 세그먼트 사이에 섞임": (
        "[00:00] SPEAKER_00: 시작\n"
        "\n"
        "[00:05] SPEAKER_01: 이어서"
    ),
    "타임스탬프 없는 순수 텍스트 라인이 섞임": (
        "[00:00] SPEAKER_00: 시작\n"
        "(웃음)\n"
        "[00:05] SPEAKER_01: 이어서"
    ),
    "깨진 타임스탬프 (초가 1자리)": (
        "[00:0] SPEAKER_00: 깨진 줄\n"
        "[00:05] SPEAKER_01: 정상 줄"
    ),
    "깨진 형식 (콜론 구분자 없음)": (
        "[00:00] SPEAKER_00 콜론이없는줄\n"
        "[00:05] SPEAKER_01: 정상 줄"
    ),
    "완전히 빈 transcript": "",
    "공백 텍스트 (개행만)": "\n\n",
    "라벨은 있으나 텍스트가 빈 세그먼트": "[00:00] SPEAKER_00: ",
    "단일 깨진 라인만 존재": "이것은 그냥 메모입니다. 타임스탬프가 전혀 없습니다.",
}


@pytest.mark.parametrize("raw", ROUNDTRIP_CASES.values(), ids=list(ROUNDTRIP_CASES.keys()))
def test_roundtrip_lossless(raw):
    """render(parse(s)) == s — 바이트 단위 동일."""
    segments = parse(raw)
    assert render(segments) == raw


# ---------------------------------------------------------------------------
# parse() 구조 검증 — label/text가 의도대로 분리되는지
# ---------------------------------------------------------------------------

def test_parse_standard_multi_segment_structure():
    raw = "[00:00] SPEAKER_00: 안녕\n[00:03] SPEAKER_01: 반갑습니다"
    segs = parse(raw)
    assert len(segs) == 2
    assert segs[0]["label"] == "SPEAKER_00"
    assert segs[0]["text"] == "안녕"
    assert segs[0]["start"] == 0
    assert segs[1]["label"] == "SPEAKER_01"
    assert segs[1]["text"] == "반갑습니다"
    assert segs[1]["start"] == 3


def test_parse_over_99_minutes_start_seconds():
    """100분 초과 타임스탬프가 정확한 초 단위로 파싱된다 (기존 \\d{2} 정규식 불일치 수정 확인)."""
    raw = "[123:45] SPEAKER_00: 텍스트"
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["start"] == 123 * 60 + 45
    assert segs[0]["label"] == "SPEAKER_00"


def test_parse_colon_in_label_still_splits_at_last_meaningful_boundary():
    """콜론이 포함된 라벨도 원본 separator(': ')를 기준으로 정확히 분리된다."""
    raw = "[00:00] PM:김철수: 오늘 안건은 세 가지입니다"
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["label"] == "PM:김철수"
    assert segs[0]["text"] == "오늘 안건은 세 가지입니다"


def test_parse_space_in_label():
    raw = "[00:00] 김 팀장: 회의 시작합니다"
    segs = parse(raw)
    assert segs[0]["label"] == "김 팀장"
    assert segs[0]["text"] == "회의 시작합니다"


def test_parse_broken_line_is_passthrough():
    """구조 파싱에 실패한 줄은 label=None, text=원본 그대로 보존된다."""
    raw = "그냥 일반 텍스트입니다. 타임스탬프가 없습니다."
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["label"] is None
    assert segs[0]["text"] == raw


def test_parse_empty_string_returns_empty_list():
    assert parse("") == []


def test_render_empty_list_returns_empty_string():
    assert render([]) == ""


# ---------------------------------------------------------------------------
# render() — speaker_map 치환 (PR B/C가 사용할 표시 이름 전환 경로 사전 검증)
# ---------------------------------------------------------------------------

def test_render_with_speaker_map_substitutes_label():
    segs = [
        {"start": 0, "end": None, "label": "SPEAKER_00", "text": "안녕"},
        {"start": 3, "end": None, "label": "SPEAKER_01", "text": "반갑습니다"},
    ]
    out = render(segs, speaker_map={"SPEAKER_00": "김 팀장"})
    assert out == "[00:00] 김 팀장: 안녕\n[00:03] SPEAKER_01: 반갑습니다"


def test_render_without_speaker_map_is_identity():
    """speaker_map 생략 시 label 그대로 사용 — 이것이 PR A의 '동작 변화 0' 보증의 근거."""
    segs = parse("[00:00] SPEAKER_00: 안녕")
    assert render(segs) == render(segs, speaker_map=None) == render(segs, speaker_map={})


def test_render_passthrough_segment_ignores_speaker_map():
    """label=None 세그먼트는 speaker_map과 무관하게 원본 텍스트 그대로 나온다."""
    segs = [{"start": None, "end": None, "label": None, "text": "(웃음)"}]
    assert render(segs, speaker_map={"SPEAKER_00": "김 팀장"}) == "(웃음)"
