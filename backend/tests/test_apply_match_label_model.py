"""apply-match — 라벨 기반 모델 재작성 (PR B).

원본: test_apply_match_collision.py(576줄 14시나리오) + test_apply_match_consistency.py의
Scenario A/B(346줄 중 5시나리오) — apply-match 관련 시나리오를 여기로 재작성했다.
대응표: docs/ai_analysis/20260831_PR_B_시나리오_대응표.md

새 불변식 (director 확정):
    apply_match = 라벨 검증 → speaker_map 갱신 → 재렌더.
    표시 이름은 speaker_map.get(label, label)로만 결정된다. 텍스트 매칭·overlap 휴리스틱 없음.
    라벨 검증: matches의 키가 get_segments(job_id)의 label 집합에 있는지로 판정한다.
    new_name은 쓰기 시점에 strip. 빈/공백뿐이면 speaker_map을 건드리지 않고
    skipped에 담는다 — 그 라벨의 기존 이름은 삭제되지 않고 보존된다(매핑에서
    "제외"가 아니라 "미변경"). 전부 빈 값이면 known이 비어 422.

RED가 정상이다 — 옛 구현(휴리스틱 기반)이 아직 남아있는 동안은 실패한다.
통과시키려고 단언을 되돌리지 말 것. PR A 테스트(test_transcript_module.py 등)를
고쳐야 통과한다면 그건 이 파일이 아니라 구현이 틀린 신호 — director에게 보고.
"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def _create_done_meeting(job_id, transcript, speakers, diarization=None):
    """done 상태 회의를 DB에 직접 생성한다. transcript_segments는 lazy backfill에 맡긴다."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title="테스트 회의")
    db.update_job_result(
        job_id,
        summary="## 요약\n테스트",
        transcript=transcript,
        speakers=speakers,
        diarization=diarization,
        duration_sec=60,
        status="done",
    )


def _get_speakers(job: dict) -> dict:
    speakers = job.get("speakers", {})
    if isinstance(speakers, str):
        speakers = json.loads(speakers)
    return speakers


def _assert_rerender_matches(job_id: str, job: dict):
    """왕복+치환 짝 단언의 '왕복' 축: apply-match 후 저장된 transcript 문자열이
    실제로 render(segments, speaker_map)의 결과와 바이트 동일한지 확인한다.
    (라벨 공백 결함이 왕복만으로는 안 잡혔던 PR A의 교훈 — 여기서는 반대로
    '치환 결과'를 이미 개별 assert로 확인했으니 '왕복(재렌더 정합성)'을 짝으로 붙인다.)"""
    from app.transcript import get_segments, render

    segments = get_segments(job_id)
    assert render(segments, _get_speakers(job)) == job["transcript"]


# ===========================================================================
# #1, #2, #3, #6 — 서로 다른 두 라벨은 항상 독립적으로 갱신된다
#   (원본: TestReplaceMapKeyCollision 3개 + TestNonIdentityCollisionWithDiar 1개)
#   메커니즘(current_name 키 충돌)은 설계상 불가능해짐 — speaker_map은 label 키라
#   서로 다른 두 라벨이 값 충돌을 일으킬 수 없다. 그 사실 자체를 검증한다.
# ===========================================================================

class TestTwoLabelsIndependentUpdate:
    """diar 유무·이전에 같은 이름으로 보였는지 여부와 무관하게, 서로 다른 두 라벨은
    항상 독립적으로 speaker_map에 반영되고 렌더 결과에 각자 다른 이름으로 나타난다."""

    def test_both_new_names_present_in_transcript(self, client):
        """#1+#2: SPEAKER_00→박과장, SPEAKER_01→이대리로 매칭하면 둘 다 나타난다."""
        _create_done_meeting(
            "label-indep-1",
            "[00:00] SPEAKER_00: 첫번째 안건\n[00:30] SPEAKER_01: 두번째 안건",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "김팀장"},  # 과거엔 같은 이름으로 보였음
        )
        res = client.post("/api/jobs/label-indep-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/label-indep-1").json()
        assert "박과장:" in job["transcript"], f"실제: {job['transcript']}"
        assert "이대리:" in job["transcript"], f"실제: {job['transcript']}"
        _assert_rerender_matches("label-indep-1", job)

    def test_speaker_map_updated_correctly_per_label(self, client):
        """#3: speaker_map의 각 라벨 값이 독립적으로 정확히 갱신된다."""
        _create_done_meeting(
            "label-indep-2",
            "[00:00] SPEAKER_00: 첫번째\n[00:30] SPEAKER_01: 두번째",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "김팀장"},
        )
        res = client.post("/api/jobs/label-indep-2/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/label-indep-2").json()
        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "박과장"
        assert speakers.get("SPEAKER_01") == "이대리"
        _assert_rerender_matches("label-indep-2", job)

    def test_result_independent_of_diarization_presence(self, client):
        """#6: diarization이 DB에 있어도 결과가 달라지지 않는다 — apply_match는
        더 이상 diarization을 조회하지 않는다(설계상 폐기)."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            "label-indep-3",
            "[00:00] SPEAKER_00: 첫번째\n[00:30] SPEAKER_01: 두번째",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "김팀장"},
            diarization=diarization,
        )
        res = client.post("/api/jobs/label-indep-3/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/label-indep-3").json()
        assert "박과장:" in job["transcript"]
        assert "이대리:" in job["transcript"]
        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "박과장"
        assert speakers.get("SPEAKER_01") == "이대리"
        _assert_rerender_matches("label-indep-3", job)


# ===========================================================================
# #4 — diar 없이도 존재하지 않는 라벨은 skipped (원본: TestCollisionWithoutDiarization)
# ===========================================================================

class TestUnknownLabelWithoutDiarization:
    def test_unknown_label_is_skipped_known_label_applied(self, client):
        """diarization이 전혀 없어도, segments에 실제로 없는 라벨은 라벨 검증에서
        걸러져 skipped로 보고되고, 존재하는 라벨은 정상 적용된다."""
        _create_done_meeting(
            "unknown-nodia-1",
            "[00:00] SPEAKER_00: 첫번째\n[00:30] SPEAKER_01: 두번째",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
            diarization=None,
        )
        res = client.post("/api/jobs/unknown-nodia-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_99": "존재안함"},
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert data.get("skipped") == ["SPEAKER_99"], f"실제: {data}"

        job = client.get("/api/jobs/unknown-nodia-1").json()
        assert "박과장:" in job["transcript"]
        assert "존재안함" not in job["transcript"]
        _assert_rerender_matches("unknown-nodia-1", job)


# ===========================================================================
# #7 — 하나의 라벨이 비연속 여러 세그먼트에 걸쳐 있어도 전부 일괄 갱신된다
#   (원본: TestSubSecondBoundaryOverlap — overlap-vs-point 배정 로직 자체가
#    _resolve_speaker_display와 함께 삭제되어 재현 불가능해졌다. director에게
#    공격면 소멸을 보고했고, "나머지는 스스로 결정" 지시에 따라 인접 개념
#    — 라벨이 곧 유일한 정체성이라는 새 모델의 핵심 성질 — 로 재정의했다.)
# ===========================================================================

class TestSameLabelMultipleSegments:
    def test_all_occurrences_of_label_updated(self, client):
        """SPEAKER_00이 트랜스크립트 여러 곳에 비연속으로 등장해도 apply-match 한 번으로
        전부 새 이름으로 바뀐다(부분 갱신·순서 의존성 없음). 미매칭 라벨은 그대로."""
        _create_done_meeting(
            "multiseg-1",
            "[00:00] SPEAKER_00: 첫\n[00:05] SPEAKER_01: 끼어들기\n"
            "[00:10] SPEAKER_00: 이어서\n[00:45] SPEAKER_00: 마지막",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        )
        res = client.post("/api/jobs/multiseg-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/multiseg-1").json()
        assert job["transcript"].count("박과장:") == 3
        assert "김팀장" not in job["transcript"]
        assert "이대리:" in job["transcript"]
        _assert_rerender_matches("multiseg-1", job)


# ===========================================================================
# #8 — 세그먼트가 0개인 라벨은 애초에 unknown label로 걸러진다
#   (원본: TestCollisionEmptySegmentConsistency)
# ===========================================================================

class TestZeroSegmentLabel:
    def test_label_with_zero_segments_is_skipped_not_applied(self, client):
        """SPEAKER_01이 transcript에 한 줄도 없으면(=segments 라벨 집합에 없으면)
        라벨 검증에서 걸러져 skipped 처리되고, 그 이름은 transcript에 나타나지 않는다."""
        _create_done_meeting(
            "zeroseg-1",
            "[00:00] SPEAKER_00: 첫번째\n[00:30] SPEAKER_00: 두번째",  # SPEAKER_01 라인 없음
            speakers={"SPEAKER_00": "김팀장"},
        )
        res = client.post("/api/jobs/zeroseg-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "최부장"},
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("skipped") == ["SPEAKER_01"], f"실제: {data}"

        job = client.get("/api/jobs/zeroseg-1").json()
        assert "최부장" not in job["transcript"]
        assert "박과장:" in job["transcript"]
        speakers = _get_speakers(job)
        assert "최부장" not in speakers.values()
        _assert_rerender_matches("zeroseg-1", job)


# ===========================================================================
# #9~#11 — 전체/부분 실패 응답 shape (원본: TestSilentSkipOnResolveFail)
#   "식별 실패"에서 "segments에 없는 라벨"로 setup만 교체. shape 단언은 원본 그대로.
# ===========================================================================

class TestUnknownLabelResponseShape:
    def test_all_labels_unknown_returns_422(self, client):
        """#9: matches의 모든 라벨이 segments에 없으면 422 + skipped, transcript·speakers 불변.

        transcript는 **바이트 단위로 원본과 완전히 동일**해야 한다(부분 문자열 부재 확인만으로는
        불충분 — director 지시). 전체 실패 시 backend는 update_job_result 자체를 호출하지
        않도록 구현한다 — 재렌더가 우연히 같은 문자열을 내는 것에 기대지 않기 위함이다."""
        original_transcript = "[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다"
        _create_done_meeting(
            "shape-all-1",
            original_transcript,
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/shape-all-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        assert res.status_code == 422, f"실제: {res.status_code}, body: {res.json()}"
        data = res.json()
        assert "skipped" in data
        assert "SPEAKER_00" in data["skipped"]

        job = client.get("/api/jobs/shape-all-1").json()
        assert job["transcript"] == original_transcript, (
            f"skipped 시 transcript가 바이트 단위로 불변이어야 함. 실제: {job['transcript']!r}"
        )
        assert _get_speakers(job) == {"아빠": "아빠", "엄마": "엄마"}

    def test_partial_unknown_returns_200_with_skipped_and_warning(self, client):
        """#10: 일부만 알려진 라벨이면 200 + skipped + warning, 알려진 것만 적용."""
        _create_done_meeting(
            "shape-partial-1",
            "[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/shape-partial-1/apply-match", json={
            "matches": {"아빠": "김과장", "SPEAKER_99": "박부장"},
        })
        assert res.status_code == 200, f"실제: {res.status_code}, body: {res.json()}"
        data = res.json()
        assert data.get("ok") is True
        assert data.get("skipped") == ["SPEAKER_99"], f"실제: {data}"
        assert "warning" in data

        job = client.get("/api/jobs/shape-partial-1").json()
        assert "김과장:" in job["transcript"]
        _assert_rerender_matches("shape-partial-1", job)

    def test_all_labels_unknown_multi_returns_422(self, client):
        """#11: 여러 라벨이 모두 unknown이면 전부 skipped에 담겨 422, transcript 바이트 불변."""
        original_transcript = "[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다"
        _create_done_meeting(
            "shape-all-2", original_transcript,
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/shape-all-2/apply-match", json={
            "matches": {"SPEAKER_00": "김과장", "SPEAKER_01": "박부장"},
        })
        assert res.status_code == 422
        data = res.json()
        assert set(data["skipped"]) == {"SPEAKER_00", "SPEAKER_01"}, f"실제: {data}"

        job = client.get("/api/jobs/shape-all-2").json()
        assert job["transcript"] == original_transcript, (
            f"skipped 시 transcript가 바이트 단위로 불변이어야 함. 실제: {job['transcript']!r}"
        )


# ===========================================================================
# #12~#14 — new_name 공백 처리 (원본: TestWhitespaceDefense)
#   원본은 "저장된 옛 이름"의 공백 때문에 텍스트 매칭이 실패하던 버그였다.
#   텍스트 매칭 자체가 사라져 그 공격면은 소멸했다. 설계문서가 명시한 대체 위험
#   ("new_name은 쓰기 시점에 한 곳에서 trim")으로 대상을 교체했다.
# ===========================================================================

class TestNewNameWhitespaceNormalization:
    def test_trailing_whitespace_is_stripped(self, client):
        """#12"""
        _create_done_meeting(
            "ws-new-1", "[00:00] SPEAKER_00: 안녕하세요",
            speakers={"SPEAKER_00": "김팀장"},
        )
        res = client.post("/api/jobs/ws-new-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장 "},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/ws-new-1").json()
        assert "박과장:" in job["transcript"]
        assert "박과장 :" not in job["transcript"]
        assert _get_speakers(job).get("SPEAKER_00") == "박과장"
        _assert_rerender_matches("ws-new-1", job)

    def test_leading_whitespace_is_stripped(self, client):
        """#13"""
        _create_done_meeting(
            "ws-new-2", "[00:00] SPEAKER_00: 안녕하세요",
            speakers={"SPEAKER_00": "김팀장"},
        )
        res = client.post("/api/jobs/ws-new-2/apply-match", json={
            "matches": {"SPEAKER_00": " 박과장"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/ws-new-2").json()
        assert "박과장:" in job["transcript"]
        assert _get_speakers(job).get("SPEAKER_00") == "박과장"
        _assert_rerender_matches("ws-new-2", job)

    def test_both_sides_whitespace_is_stripped(self, client):
        """#14"""
        _create_done_meeting(
            "ws-new-3",
            "[00:00] SPEAKER_00: 안녕하세요\n[00:10] SPEAKER_01: 반갑습니다",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        )
        res = client.post("/api/jobs/ws-new-3/apply-match", json={
            "matches": {"SPEAKER_00": " 박과장 ", "SPEAKER_01": " 정부장 "},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/ws-new-3").json()
        transcript = job["transcript"]
        assert "박과장:" in transcript
        assert "정부장:" in transcript
        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "박과장"
        assert speakers.get("SPEAKER_01") == "정부장"
        _assert_rerender_matches("ws-new-3", job)


# ===========================================================================
# #15~#18 — 기본 치환 정확성 (원본: consistency.py TestApplyMatchNonIdentity)
# ===========================================================================

class TestBasicRematch:
    def test_transcript_and_speaker_map_replaced_correctly(self, client):
        """#15+#16: 치환된 transcript 내용과 speaker_map 값이 둘 다 정확하다."""
        _create_done_meeting(
            "basic-1",
            "[00:00] 아빠: 안녕하세요\n[00:05] 엄마: 반갑습니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/basic-1/apply-match", json={
            "matches": {"아빠": "김과장"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/basic-1").json()
        assert "김과장:" in job["transcript"]
        assert "아빠:" not in job["transcript"]
        assert _get_speakers(job).get("아빠") == "김과장"
        _assert_rerender_matches("basic-1", job)

    def test_partial_match_unmapped_label_unchanged(self, client):
        """#17 (+#5 흡수): 매칭 안 된 라벨의 라인은 그대로 유지된다 — '세그먼트 밖
        라인'이라는 옛 개념 없이도(라인은 이미 자기 라벨을 갖고 생산됨) 동일 결과가 보장된다."""
        _create_done_meeting(
            "basic-2",
            "[00:00] 아빠: 첫번째\n[00:05] 엄마: 두번째\n[00:10] 아빠: 세번째",
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/basic-2/apply-match", json={
            "matches": {"아빠": "김과장"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/basic-2").json()
        transcript = job["transcript"]
        assert transcript.count("김과장:") == 2
        assert "엄마:" in transcript
        _assert_rerender_matches("basic-2", job)

    def test_name_swap_is_atomic(self, client):
        """#18: 두 라벨의 이름을 맞바꿔도(아빠↔엄마) 누적 오염 없이 정확히 반영된다.
        새 모델(재렌더 1회 패스)에서는 설계상 당연하지만 회귀 가드로 유지한다 —
        '당연해졌다'는 사실 자체가 이 테스트의 존재 이유다."""
        _create_done_meeting(
            "basic-3",
            "[00:00] 아빠: 첫번째\n[00:05] 엄마: 두번째\n[00:10] 아빠: 세번째",
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.post("/api/jobs/basic-3/apply-match", json={
            "matches": {"아빠": "엄마", "엄마": "아빠"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/basic-3").json()
        transcript = job["transcript"]
        assert transcript.count("엄마:") == 2, f"실제: {transcript}"
        assert transcript.count("아빠:") == 1, f"실제: {transcript}"
        _assert_rerender_matches("basic-3", job)


# ===========================================================================
# #19 — identity-mapped 레거시 행에서 matches 키는 segment의 실제 label이다
#   (원본: TestApplyMatchIdentity — diar-label↔transcript-label 브릿지가
#    PR A로 사라졌으므로, 옛 diar 라벨 키는 더 이상 유효하지 않아야 한다.)
# ===========================================================================

class TestIdentityMappedRowUsesOwnLabel:
    def test_legacy_diar_label_key_rejected_segment_label_key_accepted(self, client):
        """레거시 diarization이 SPEAKER_00/01로 남아있어도 apply_match는 이를
        조회하지 않는다 — matches 키는 반드시 segment의 실제 label("아빠")이어야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 5, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 5, "end": 10, "speaker": "SPEAKER_01"}],
        }
        original_transcript = "[00:00] 아빠: 안녕하세요\n[00:05] 엄마: 반갑습니다"
        _create_done_meeting(
            "identity-1", original_transcript,
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

        # 옛 diar 라벨(SPEAKER_00)로 보내면 segments 라벨("아빠")과 안 맞아 unknown 처리된다.
        res_old_key = client.post("/api/jobs/identity-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        assert res_old_key.status_code == 422, (
            f"레거시 diar 라벨 키는 더 이상 유효하지 않아야 함. 실제: {res_old_key.status_code}"
        )
        # 전체 skipped 시 transcript는 바이트 단위로 원본과 완전히 동일해야 한다.
        job_after_skip = client.get("/api/jobs/identity-1").json()
        assert job_after_skip["transcript"] == original_transcript, (
            f"skipped 시 transcript가 바이트 단위로 불변이어야 함. 실제: {job_after_skip['transcript']!r}"
        )

        # 실제 segment label("아빠")로 보내야 정상 적용된다.
        res = client.post("/api/jobs/identity-1/apply-match", json={
            "matches": {"아빠": "김과장"},
        })
        assert res.status_code == 200
        job = client.get("/api/jobs/identity-1").json()
        assert "김과장:" in job["transcript"]
        assert _get_speakers(job).get("아빠") == "김과장"
        _assert_rerender_matches("identity-1", job)


# ===========================================================================
# 신규 (26개와 무관, director 확정 사양) — apply-match의 new_name이
# 빈 문자열/공백뿐인 경우. 관문 정규화(update_job_result)에 그대로 맡기면
# 기존 이름이 사라진다(판정 3 위반) — apply_match 자신이 빈 new_name을
# speaker_map에 쓰기 전에 걸러 skipped로 돌려야 한다.
#
#   - new_name.strip()이 비면: speaker_map을 건드리지 않고 skipped에 담는다.
#     그 라벨의 기존 이름은 보존된다.
#   - 전부 빈 값이면: known이 비어 422 (조용한 이름 삭제보다 명시적 거부).
# ===========================================================================

class TestBlankNewNameIsSkipped:
    def test_blank_new_name_skipped_existing_name_preserved(self, client):
        """공백뿐인 new_name은 skipped 처리되고 그 라벨의 기존 이름이 보존된다.
        같은 요청의 다른 정상 라벨은 정상 적용된다."""
        _create_done_meeting(
            "blank-name-1",
            "[00:00] SPEAKER_00: 첫번째\n[00:05] SPEAKER_01: 두번째",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        )
        res = client.post("/api/jobs/blank-name-1/apply-match", json={
            "matches": {"SPEAKER_00": "   ", "SPEAKER_01": "박과장"},
        })
        assert res.status_code == 200, f"실제: {res.status_code}, body: {res.json()}"
        data = res.json()
        assert data.get("skipped") == ["SPEAKER_00"], f"실제: {data}"

        job = client.get("/api/jobs/blank-name-1").json()
        assert "김팀장:" in job["transcript"], (
            f"공백 new_name은 기존 이름을 지우면 안 됨. 실제: {job['transcript']}"
        )
        assert "박과장:" in job["transcript"]
        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "김팀장", f"실제: {speakers}"
        assert speakers.get("SPEAKER_01") == "박과장", f"실제: {speakers}"
        _assert_rerender_matches("blank-name-1", job)

    def test_all_new_names_blank_returns_422(self, client):
        """모든 new_name이 빈/공백뿐이면 known이 비어 422로 명시 거부한다 —
        조용한 이름 삭제 대신 명시적 실패. transcript·speakers는 바이트 단위로 불변."""
        original_transcript = "[00:00] SPEAKER_00: 첫번째\n[00:05] SPEAKER_01: 두번째"
        _create_done_meeting(
            "blank-name-2", original_transcript,
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        )
        res = client.post("/api/jobs/blank-name-2/apply-match", json={
            "matches": {"SPEAKER_00": "", "SPEAKER_01": "   "},
        })
        assert res.status_code == 422, f"실제: {res.status_code}, body: {res.json()}"
        data = res.json()
        assert set(data["skipped"]) == {"SPEAKER_00", "SPEAKER_01"}, f"실제: {data}"

        job = client.get("/api/jobs/blank-name-2").json()
        assert job["transcript"] == original_transcript, (
            f"전체 skipped 시 transcript가 바이트 단위로 불변이어야 함. 실제: {job['transcript']!r}"
        )
        assert _get_speakers(job) == {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
