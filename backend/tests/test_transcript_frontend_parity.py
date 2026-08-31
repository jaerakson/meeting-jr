"""backend/app/transcript.py ↔ frontend/lib/transcript.ts 계약 일치 테스트 (PR C).

배경 (director 지시, 최우선 과제): PR C는 프론트 파서 4벌 + 시리얼라이저 2벌을
frontend/lib/transcript.ts 한 곳으로 통합하고, 그 계약을 backend/app/transcript.py의
parse()/render()에서 그대로 포팅했다고 주장한다. "포팅했다"는 주장과 "실제로 같은
입력에 같은 출력을 낸다"는 사실은 다르다 — 같은 문자열에 두 구현이 다른 결과를 내면
그게 다음 라운드 버그다.

케이스는 backend/frontend 양쪽 소스에 따로 적지 않고 `tests/fixtures/
transcript_parity_cases.json`(레포 루트) 하나에 두고 양쪽이 그걸 읽는다 — 갈라짐을
구조적으로 막는다. `expected_round_trip`/`expected_with_map`는 이 JSON을 생성할 때
backend/app/transcript.py(현재 이 리팩터링의 기준 구현)를 실제로 실행해 얻은 값이다
(수기 계산 아님). 이 테스트는 backend가 그 golden 값과 계속 일치하는지를 지키는
가드이고, `frontend/__tests__/transcript.parity.test.ts`가 같은 golden 값으로
frontend 구현을 검증한다 — 그게 실제 "계약 일치" 축이다.

왕복(`render(parse(s)) == s`)만으로는 안 잡히는 부류가 있다 — PR A에서 라벨 공백
결함이 왕복 성립 + 치환 실패로 258개 전부 초록이었다. 그래서 각 케이스마다 왕복과
치환(`speaker_map` 적용 결과)을 반드시 짝으로 확인한다.

단언을 통과시키려고 약화하지 말 것. 단언이 틀렸다고 판단되면 director에게 보고.
"""

import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "transcript_parity_cases.json"


def _load_cases():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)["cases"]


CASES = _load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_backend_matches_golden_fixture(case):
    """backend/app/transcript.py가 golden 픽스처(스스로 생성한 기준값)와 계속
    일치하는지 확인한다 — 이 파일이 드리프트를 잡는 가드, frontend 쪽이 계약 준수를
    검증하는 실제 대조축이다."""
    from app.transcript import parse, render

    segments = parse(case["transcript"])

    assert len(segments) == case["segment_count"], (
        f"[{case['id']}] 세그먼트 개수 불일치. 실제: {len(segments)}, 기대: {case['segment_count']}"
    )

    round_trip = render(segments)
    assert round_trip == case["expected_round_trip"], (
        f"[{case['id']}] 왕복 실패. 실제: {round_trip!r}, 기대: {case['expected_round_trip']!r}"
    )

    with_map = render(segments, case["speaker_map"])
    assert with_map == case["expected_with_map"], (
        f"[{case['id']}] 치환 결과 불일치. 실제: {with_map!r}, 기대: {case['expected_with_map']!r}"
    )


def test_fixture_covers_five_required_categories():
    """대응표 요구사항(director 지시) — 최소 5개 카테고리가 실제로 픽스처에 있는지
    확인한다. 카테고리가 조용히 줄어드는 것을 막는 앵커."""
    ids = {c["id"] for c in CASES}
    required = {
        "standard_lines",
        "label_with_internal_space",
        "over_100_minutes",
        "empty_utterance_and_blank_display_name",
        "passthrough_mixed_failure_lines",
    }
    missing = required - ids
    assert not missing, f"필수 카테고리 누락: {missing}"


def test_passthrough_lines_are_never_substituted():
    """실패줄 혼합 케이스: speaker_map에 있는 값이라도 passthrough 줄(label=None)
    본문에 우연히 나타나면 치환되면 안 된다(나이브 .replace 본문 오염 봉쇄점).
    "메모: SPEAKER_00 관련 논의 계속" 줄이 이 케이스의 핵심 방어 대상이다."""
    from app.transcript import parse, render

    case = next(c for c in CASES if c["id"] == "passthrough_mixed_failure_lines")
    segments = parse(case["transcript"])

    passthrough_texts = [seg["text"] for seg in segments if seg["label"] is None]
    assert "메모: SPEAKER_00 관련 논의 계속" in passthrough_texts, (
        f"실제 passthrough 텍스트들: {passthrough_texts}"
    )

    rendered = render(segments, case["speaker_map"])
    assert "메모: SPEAKER_00 관련 논의 계속" in rendered, (
        f"passthrough 줄의 'SPEAKER_00'이 speaker_map에 의해 치환되면 안 됨. 실제: {rendered!r}"
    )


def test_blank_and_whitespace_display_name_keeps_label():
    """빈 발언 케이스: speaker_map 값이 공백뿐이면(예: '   ') 그 라벨은 이름이
    아니라 라벨 그대로 렌더돼야 한다(display == label 규칙, 이름 삭제 방지)."""
    from app.transcript import parse, render

    case = next(c for c in CASES if c["id"] == "empty_utterance_and_blank_display_name")
    segments = parse(case["transcript"])
    rendered = render(segments, case["speaker_map"])

    assert "SPEAKER_00:" in rendered, f"공백뿐인 표시 이름은 라벨을 유지해야 함. 실제: {rendered!r}"
    assert "   :" not in rendered, f"공백 이름이 그대로 렌더되면 안 됨. 실제: {rendered!r}"
