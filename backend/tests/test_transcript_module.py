"""app.transcript (`parse` / `render`) 계약 테스트 — PR A.

director-2 확정 계약 (재정정 반영 완료: 2단 매칭 / raw+speaker_map 우선순위):

    parse(raw: str) -> list[dict]
        각 세그먼트: {"start": int(초)|None, "end": None, "label": str|None, "text": str, "raw": str(선택)}
        2단 매칭:
          1단(STRICT) r'^\\[(\\d+):(\\d{2})\\]\\s(.+?):\\s(.*)$'  — 콜론 뒤 공백 필수, 라벨 non-greedy
          2단(EMPTY)  r'^\\[(\\d+):(\\d{2})\\]\\s(.+?):$'          — 1단 실패 시에만. text="" 로 구조화
            (`[00:00] SPEAKER_00:` 처럼 콜론 뒤 공백 없이 줄이 끝나는 빈 발언 라인용.
             passthrough로 떨어뜨리면 PR B 라벨 치환 대상에서 조용히 빠지므로 반드시 label을 잡는다.)
        1·2단 모두 실패 → passthrough: {"start": None, "end": None, "label": None, "text": <원본 줄>}.
          (`\\s(.+?):\\s`에 맞는 콜론이 아예 없거나, EMPTY처럼 줄 끝 콜론이 아니면 실패 —
           예: "결론:다음주로 미룬다"는 콜론 뒤에 공백도 없고 줄 끝 콜론도 아니므로 passthrough.
           오탐 방지: `.+?`가 아무 콜론이나 라벨 경계로 삼지 않는다.)
        raw == "" 이면 []. 줄바꿈 기준 줄 단위 파싱.
        "raw" 키: 정규형 렌더가 원본 줄과 바이트 동일하지 않을 때만 채운다(같으면 키 생략).

    render(segments: list[dict], speaker_map: dict | None = None) -> str
        label=None(passthrough) → speaker_map과 무관하게 text 그대로 출력 (본문 오염 봉쇄).
        label 있음 → display = (speaker_map or {}).get(label, label) 계산 후:
          - display == label (치환 없음) 이고 raw가 있으면 → raw 그대로 출력 (바이트 보존 우선)
          - display != label (실제 치환) 이면 → raw 무시하고 정규형 `[MM:SS] {display}: {text}` 렌더
            (raw는 "아무도 안 건드렸을 때" 보험이지 치환을 막는 수단이 아니다 — PR B가 이 경로로
             라벨을 실명으로 바꾸므로, raw가 무조건 이기면 치환이 조용히 죽는다.)
        "\\n".join(...). speaker_map 생략/빈 값이면 label 그대로 → render(parse(s)) == s.

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
    "라벨은 있으나 텍스트가 빈 세그먼트 (콜론 뒤 공백 있음, 1단)": "[00:00] SPEAKER_00: ",
    "빈 발언, 콜론 뒤 공백 없이 줄 끝 (2단 EMPTY)": "[00:00] SPEAKER_00:",
    "오탐 방지 — 콜론이 라벨 경계가 아닌 일반 문장": "[00:00] 결론:다음주로 미룬다",
    "라벨 뒤 텍스트에 콜론이 또 있는 경우": "[00:00] 결론: 다음:",
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


# ---------------------------------------------------------------------------
# 판정 4 — 빈 발언 2단 매칭(EMPTY): label을 잃지 않고, 오탐도 만들지 않는다
# ---------------------------------------------------------------------------

def test_parse_empty_utterance_no_trailing_space_keeps_label():
    """`[00:00] SPEAKER_00:` (콜론 뒤 공백 없이 줄 끝)은 passthrough가 아니라
    label="SPEAKER_00", text="" 로 구조화된다 (2단 EMPTY 매칭).
    passthrough로 떨어지면 PR B에서 이 줄의 화자가 조용히 치환 대상에서 빠진다."""
    raw = "[00:00] SPEAKER_00:"
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["label"] == "SPEAKER_00"
    assert segs[0]["text"] == ""
    # 정규형 렌더([00:00] SPEAKER_00: )가 원본과 다르므로 raw로 왕복 보존된다.
    assert segs[0].get("raw") == raw
    assert render(segs) == raw


def test_empty_utterance_segment_is_still_substitutable():
    """2단(EMPTY)으로 잡힌 빈 발언 라인도 실제 화자 치환 대상이다 —
    raw가 있어도 speaker_map 치환이 우선한다(판정 5)."""
    segs = parse("[00:00] SPEAKER_00:")
    out = render(segs, speaker_map={"SPEAKER_00": "김철수"})
    assert out == "[00:00] 김철수: "


def test_parse_false_positive_colon_is_not_treated_as_label():
    """`결론:다음주로 미룬다` — 콜론 뒤에 공백도 없고 줄 끝 콜론도 아니므로
    1단·2단 모두 실패해야 한다. label="결론"으로 잡히면 과잉 완화이자 회귀다."""
    raw = "[00:00] 결론:다음주로 미룬다"
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["label"] is None
    assert segs[0]["text"] == raw
    assert render(segs) == raw


def test_parse_label_with_colon_inside_trailing_text():
    """`결론: 다음:` — 1단이 최초의 ': '(공백 포함)에서 끊으므로
    label="결론", text="다음:" 으로 정확히 분리된다 (콜론이 라벨 뒤에 하나 더 있어도 무관)."""
    raw = "[00:00] 결론: 다음:"
    segs = parse(raw)
    assert len(segs) == 1
    assert segs[0]["label"] == "결론"
    assert segs[0]["text"] == "다음:"
    assert render(segs) == raw


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


def test_render_passthrough_does_not_substitute_speaker_id_inside_text():
    """label=None 통과 라인의 본문 안에 'SPEAKER_00' 문자열이 있어도 치환되지 않는다
    — 나이브 .replace 본문 오염 재유입 봉쇄점(설계문서 지적 결함)."""
    segs = [{"start": None, "end": None, "label": None, "text": "SPEAKER_00 얘기 좀 그만해"}]
    out = render(segs, speaker_map={"SPEAKER_00": "김 팀장"})
    assert out == "SPEAKER_00 얘기 좀 그만해"


# ---------------------------------------------------------------------------
# 판정 5 — raw와 speaker_map 치환의 우선순위
#   display == label(치환 없음) → raw 사용(바이트 보존) / display != label(치환) → 정규형 렌더
# ---------------------------------------------------------------------------

def test_raw_is_used_when_no_substitution_happens():
    """비정규 자릿수(분 앞자리 0 과다)처럼 raw가 생기는 세그먼트는,
    치환이 일어나지 않으면 raw 그대로 왕복된다."""
    raw_line = "[007:05] SPEAKER_00: 안녕"
    segs = parse(raw_line)
    assert segs[0].get("raw") == raw_line  # 비정규 자릿수라 raw가 채워졌는지 사전 확인
    assert render(segs) == raw_line
    assert render(segs, speaker_map={}) == raw_line
    assert render(segs, speaker_map={"SPEAKER_01": "다른사람"}) == raw_line  # 무관한 라벨 치환도 영향 없음


def test_canonical_render_wins_over_raw_when_substitution_happens():
    """같은 세그먼트라도 실제 치환이 일어나면 raw(원본 자릿수)를 포기하고
    정규형으로 렌더한다 — raw가 PR B의 라벨 치환을 조용히 막아서는 안 된다."""
    raw_line = "[007:05] SPEAKER_00: 안녕"
    segs = parse(raw_line)
    out = render(segs, speaker_map={"SPEAKER_00": "김철수"})
    assert out == "[07:05] 김철수: 안녕"
    assert out != raw_line


def test_label_with_leading_whitespace_still_substitutes():
    """회귀 가드 (commit 1ea13c6): `[00:00]  SPEAKER_00:  두칸`처럼 대괄호 뒤 공백이
    2칸이면 라벨이 ' SPEAKER_00'(앞공백 포함)으로 잡혀 speaker_map 조회가 조용히
    실패하던 결함. 라벨은 strip되어야 하고(내부 공백은 보존), strip 후에도 치환은
    정상 동작해야 한다. 왕복만으로는 이 결함이 잡히지 않는다 — 반드시 치환 결과를 확인."""
    raw_line = "[00:00]  SPEAKER_00:  두칸"
    segs = parse(raw_line)
    assert segs[0]["label"] == "SPEAKER_00"  # 앞뒤 공백 없이 순수 라벨
    assert render(segs) == raw_line  # 치환 없으면 raw로 바이트 동일 왕복
    assert render(segs, speaker_map={"SPEAKER_00": "김철수"}) == "[00:00] 김철수:  두칸"


def test_label_with_trailing_whitespace_before_colon_still_substitutes():
    """회귀 가드 (commit 1ea13c6, 반대 방향): `[00:00] SPEAKER_00 : 공백앞콜론`처럼
    콜론 앞에 공백이 끼면 라벨이 'SPEAKER_00 '(뒤공백 포함)으로 잡혀 치환이 조용히
    실패할 수 있었다. strip은 양쪽 다 제거해야 한다."""
    raw_line = "[00:00] SPEAKER_00 : 공백앞콜론"
    segs = parse(raw_line)
    assert segs[0]["label"] == "SPEAKER_00"  # 뒤공백 없이 순수 라벨
    assert render(segs) == raw_line  # 치환 없으면 바이트 동일 왕복 (raw 경유)
    assert render(segs, speaker_map={"SPEAKER_00": "김철수"}) == "[00:00] 김철수: 공백앞콜론"


def test_label_that_is_only_whitespace_becomes_passthrough():
    """콜론 앞이 공백뿐이면(strip 후 빈 문자열) 라벨로 인정하지 않고 passthrough로
    떨어진다 — 빈 라벨을 speaker_map에 억지로 걸지 않는다."""
    raw_line = "[00:00]   : 텍스트"
    segs = parse(raw_line)
    assert len(segs) == 1
    assert segs[0]["label"] is None
    assert segs[0]["text"] == raw_line
    assert render(segs) == raw_line
    assert render(segs, speaker_map={"SPEAKER_00": "김철수"}) == raw_line  # 치환 대상 자체가 아님


def test_internal_space_in_label_preserved_after_strip():
    """strip은 라벨 앞뒤만 제거하고 내부 공백은 보존한다 — "김 팀장"이 "김팀장"으로
    뭉개지면 안 된다."""
    raw_line = "[00:00] 김 팀장: 회의 시작합니다"
    segs = parse(raw_line)
    assert segs[0]["label"] == "김 팀장"
    assert render(segs) == raw_line
    assert render(segs, speaker_map={"김 팀장": "박부장"}) == "[00:00] 박부장: 회의 시작합니다"


# ---------------------------------------------------------------------------
# 보강 1 — 정규형 코퍼스에서는 raw가 생기지 않는다 (raw가 파싱 실패를 은폐하지 못하게)
# ---------------------------------------------------------------------------

CANONICAL_NO_RAW_CASES = {
    "표준 다중 세그먼트": ROUNDTRIP_CASES["표준 다중 세그먼트"],
    "100분 초과 회의": ROUNDTRIP_CASES["100분 초과 회의 (자릿수 무제한)"],
    "공백 포함 실명": ROUNDTRIP_CASES["공백 포함 실명"],
    "이름에 콜론 포함": ROUNDTRIP_CASES["화자 이름에 콜론 포함 (naive replace가 남긴 실데이터 형태)"],
    "이름에 대괄호 포함": ROUNDTRIP_CASES["화자 이름에 대괄호 포함"],
    "ClovaNote 유래 변환 결과": ROUNDTRIP_CASES["ClovaNote 유래 변환 결과 (멀티라인 병합 텍스트)"],
}


@pytest.mark.parametrize(
    "raw", CANONICAL_NO_RAW_CASES.values(), ids=list(CANONICAL_NO_RAW_CASES.keys())
)
def test_canonical_lines_never_produce_raw(raw):
    """생산자가 만드는 정규형 라인들은 raw 키가 전혀 생기지 않는다.
    raw가 여기서 생긴다면 정규형 렌더 로직 자체가 원본과 어긋난다는 뜻 — 파싱 실패 은폐를 조기 발견."""
    segments = parse(raw)
    assert all("raw" not in seg or seg["raw"] is None for seg in segments)
