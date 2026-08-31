"""participation — 라벨 기반 모델 재작성 (PR B).

원본: test_apply_match_consistency.py의 Scenario C/D(4시나리오) +
test_participation_collision.py(3시나리오) = 7개. 대응표:
docs/ai_analysis/20260831_PR_B_시나리오_대응표.md

새 불변식 (director 확정): display_name은 speaker_map.get(label, label)로만 결정된다.
seen_display_names / _resolve_speaker_display는 전부 제거됐다 — 라벨마다 독립적으로
조회하므로 애초에 이름 충돌이 발생할 수 없다. **`_is_identity_mapped`는 삭제되지
않고 존치한다** — 설계 정정(2026-08-31) 이후 이 함수는 이름 해석 휴리스틱이 아니라
"diar_data를 조회할지 transcript/segments 경로를 탈지" 결정하는 경로 선택에만
쓰인다(main.py 참고). #23(`TestIdentityLabelNoResolutionNeeded`)이 이 경로 선택
자체를 검증한다.

구현 완료 상태에서는 이 파일 전체가 GREEN이어야 한다. 단언을 통과시키려고
되돌리지 말 것.
"""

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


# ===========================================================================
# #20~#22 — apply-match 후 participation↔transcript 정합성
#   (원본: consistency.py TestApplyMatchParticipationConsistency)
# ===========================================================================

class TestParticipationAfterRematch:
    def test_participation_matches_transcript_after_rematch(self, client):
        """#20: apply-match 후 participation display_name이 transcript 화자 토큰과 일치."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            "part-rematch-1",
            "[00:00] SPEAKER_00: 안녕하세요\n[00:30] SPEAKER_01: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )
        client.post("/api/jobs/part-rematch-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        res = client.get("/api/jobs/part-rematch-1/participation")
        assert res.status_code == 200
        data = res.json()

        import re
        job = client.get("/api/jobs/part-rematch-1").json()
        transcript_speakers = set(re.findall(r"\[\d{2}:\d{2}\]\s*(.+?):", job["transcript"]))
        participation_names = {s["display_name"] for s in data["speakers"]}
        for name in transcript_speakers:
            assert name in participation_names, (
                f"transcript 화자 '{name}'이 participation에 없음. "
                f"participation: {participation_names}, transcript: {transcript_speakers}"
            )

    def test_no_stale_names_in_participation(self, client):
        """#21: apply-match 후 이전 이름(아빠)이 participation에 남아있으면 안 된다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            "part-rematch-2",
            "[00:00] SPEAKER_00: 안녕하세요\n[00:30] SPEAKER_01: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )
        client.post("/api/jobs/part-rematch-2/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        res = client.get("/api/jobs/part-rematch-2/participation")
        data = res.json()
        names = {s["display_name"] for s in data["speakers"]}
        assert "김과장" in names
        assert "아빠" not in names

    def test_partial_match_unmapped_label_keeps_display_name(self, client):
        """#22: 부분 매칭 후 미매칭 라벨의 display_name은 원래 이름을 유지한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            "part-rematch-3",
            "[00:00] SPEAKER_00: 안녕하세요\n[00:30] SPEAKER_01: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )
        client.post("/api/jobs/part-rematch-3/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        res = client.get("/api/jobs/part-rematch-3/participation")
        data = res.json()
        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")
        assert sp00["display_name"] == "김과장"
        assert sp01["display_name"] == "엄마", (
            f"미매칭 화자의 display_name이 원래 이름을 유지해야 함. 실제: {sp01['display_name']}"
        )


# ===========================================================================
# #23 — identity-mapped 라벨은 추측 없이 speaker_map.get(label,label)로 직접 결정된다
#   (원본: consistency.py TestResolveMultiSegment — _resolve_speaker_display가
#    삭제 대상이라 "초반 짧은 세그먼트에 속지 않는 overlap 추측"이라는 개념 자체가
#    사라졌다. 공식 하나로 결정된다는 사실을 직접 검증하는 형태로 재정의했다.)
#
#   2026-08-31 설계 정정 반영(설계문서 참고): `_is_identity_mapped`는 삭제되지 않고
#   "경로 선택"으로만 남는다 — speaker_map이 실명 키(identity-mapped)면 diar_data를
#   아예 조회하지 않고 transcript/segments 경로를 탄다. 이 테스트의 diar_data는
#   그래서 "있어도 무시된다"는 것 자체가 검증 대상이다 — 비연속 세그먼트든 뭐든
#   identity-mapped 행에는 영향을 줄 수 없다.
# ===========================================================================

class TestIdentityLabelNoResolutionNeeded:
    def test_identity_mapped_row_ignores_diarization_uses_own_label(self, client):
        """speaker_map이 실명 키(identity-mapped)면 diar_data에 비연속·기묘한 세그먼트가
        있어도 참조하지 않는다 — label은 이미 segments에서 온 실명("아빠"/"엄마")이고
        display_name == speaker_map.get(label, label) 공식이 추측 없이 바로 성립한다."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0, "end": 3, "speaker": "SPEAKER_00"},
                {"start": 35, "end": 60, "speaker": "SPEAKER_00"},
            ],
            "SPEAKER_01": [{"start": 3, "end": 35, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            "no-resolve-1",
            "[00:00] 아빠: 짧은 인사\n[00:03] 아빠: 이어서\n[00:35] 엄마: 본론입니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},  # 실명 키 → identity-mapped → transcript 경로
            diarization=diarization,
        )
        res = client.get("/api/jobs/no-resolve-1/participation")
        assert res.status_code == 200
        data = res.json()

        # transcript 경로이므로 label 자체가 diar 라벨(SPEAKER_00/01)이 아니라
        # 이미 segments에서 온 실명이어야 한다 — diar_data가 조회되지 않았다는 증거.
        labels = {s["label"] for s in data["speakers"]}
        assert labels == {"아빠", "엄마"}, (
            f"identity-mapped 행은 diar 라벨이 아니라 segment 라벨을 써야 함. 실제: {labels}"
        )

        speaker_map = {"아빠": "아빠", "엄마": "엄마"}
        for s in data["speakers"]:
            expected = speaker_map.get(s["label"], s["label"])
            assert s["display_name"] == expected, (
                f"공식 위반: label={s['label']!r} display_name={s['display_name']!r} "
                f"기대={expected!r}"
            )


# ===========================================================================
# #24~#26 — 중복 display_name 방지 (원본: participation_collision.py
#   TestParticipationDuplicateDisplayName)
#   추측(_resolve_speaker_display) 자체가 삭제되어, 라벨별 독립 조회
#   (speaker_map.get(label,label))만으로 중복이 구조적으로 불가능해진다.
# ===========================================================================

class TestNoDuplicateDisplayNames:
    """입력 데이터는 원본(participation_collision.py)과 완전히 동일하게 유지한다
    (director 지시 — 손대지 않음). speakers={"아빠":"아빠","엄마":"엄마"}는 실명 키라
    identity-mapped로 판정되어 **transcript(segments) 경로**를 탄다(diar 경로 아님) —
    2026-08-31 설계 정정(`_is_identity_mapped`는 경로 선택에만 존치) 반영.

    이 경로 전환이 세 시나리오의 기대값을 바꾼다 — 대응표의 재작성 표 참고:
      - transcript에 라벨이 "아빠"/"엄마" 둘뿐이라 참가자 항목도 2개만 생긴다.
      - 과분할 diar 라벨(SPEAKER_02)은 transcript 어디에도 없어 항목 자체가 사라진다.
      - 숫자(total_seconds/percentage)는 diar 정밀시간 → transcript 추정시간으로
        바뀐다. "다음 발언까지, 마지막 10초" 규칙(변경 없음)을 그대로 적용하면:
        아빠(0시)=다음(엄마,30초)까지=30s / 엄마(30초 줄)=다음(엄마,55초)까지=25s +
        엄마(55초 줄, 마지막)=기본 10s → 엄마 합계 35s, turn_count=2.
        total_duration = 30+35 = 65 (기존 60에서 변경). 원인은 경로 전환 하나뿐이어야
        한다 — 계산 규칙에서 기인한 차이가 보이면 구현이 조건을 어긴 것이니 보고 대상.
    """

    def _setup(self, job_id):
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 55, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 55, "end": 60, "speaker": "SPEAKER_02"}],
        }
        _create_done_meeting(
            job_id,
            "[00:00] 아빠: 안녕\n[00:30] 엄마: 반가워\n[00:55] 엄마: 마무리",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

    def test_no_duplicate_display_names_and_names_not_lost(self, client):
        """#24: display_name은 모두 서로 달라야 하고(구조적으로 불가능해짐), **레거시 행이
        설정해둔 이름을 잃지 않아야 한다** — SPEAKER_00/01로 퇴화하면 실패(설계문서 위험 2번).
        이게 이 세 시나리오의 새로운 핵심 단언이다."""
        self._setup("nodupe-1")
        res = client.get("/api/jobs/nodupe-1/participation")
        assert res.status_code == 200
        display_names = [s["display_name"] for s in res.json()["speakers"]]
        assert len(display_names) == len(set(display_names)), (
            f"중복 display_name: {display_names}"
        )
        assert set(display_names) == {"아빠", "엄마"}, (
            f"레거시 행의 이름이 유지돼야 함(SPEAKER_XX로 퇴화 금지). 실제: {display_names}"
        )

    def test_over_split_diar_label_has_no_participation_entry(self, client):
        """#25 (재해석): speaker_map에 없는 여분 diar 라벨(SPEAKER_02)은 더 이상
        raw 라벨로 폴백해 나타나지 않는다 — transcript 경로는 diar_data를 아예 조회하지
        않으므로, transcript에 없는 라벨은 참가자 항목 자체가 생기지 않는다."""
        self._setup("nodupe-2")
        res = client.get("/api/jobs/nodupe-2/participation")
        data = res.json()
        labels = {s["label"] for s in data["speakers"]}
        assert labels == {"아빠", "엄마"}, (
            f"SPEAKER_02 항목이 생기면 안 됨(과분할 diar 라벨은 transcript에 없음). 실제: {labels}"
        )

    def test_display_name_appears_exactly_once_and_timing_matches_transcript_path(self, client):
        """#26: 모든 display_name이 정확히 1회씩만 등장하고, "숫자 변경 기록"에 적은
        예상값(아빠 30s/엄마 35s, total_duration 65)과 실제 응답이 일치한다 —
        변경 원인이 경로 전환 하나뿐임을 숫자로 못박는다."""
        self._setup("nodupe-3")
        res = client.get("/api/jobs/nodupe-3/participation")
        data = res.json()

        counts: dict[str, int] = {}
        for s in data["speakers"]:
            counts[s["display_name"]] = counts.get(s["display_name"], 0) + 1
        for name, count in counts.items():
            assert count == 1, f"'{name}'이 {count}번 등장 (1번이어야 함): {counts}"

        by_name = {s["display_name"]: s for s in data["speakers"]}
        assert by_name["아빠"]["total_seconds"] == 30, f"실제: {by_name['아빠']}"
        assert by_name["아빠"]["turn_count"] == 1
        assert by_name["엄마"]["total_seconds"] == 35, f"실제: {by_name['엄마']}"
        assert by_name["엄마"]["turn_count"] == 2
        assert data["total_duration"] == 65, f"실제: {data['total_duration']}"


# ===========================================================================
# 신규 (교체로 생긴 위험 대응 — 시나리오 추가, 26개 보존과 무관)
#   participation의 transcript 경로를 get_segments()로 교체하면, PR A 계약상
#   구조화 실패 줄이 label=None 통과 세그먼트로 보존되어 화자로 잘못 집계될 위험이
#   새로 생긴다. 현행 정규식 경로는 매칭 실패 줄을 버려서 이 문제가 없었다.
# ===========================================================================

class TestPassthroughSegmentsExcludedFromParticipation:
    def test_non_speech_lines_are_not_counted_as_speakers(self, client):
        """(웃음)·빈 줄·형식 없는 줄이 섞여도 화자 항목으로 집계되지 않고,
        turn_count·total_seconds도 실제 발화 줄만으로 계산된다."""
        transcript = (
            "[00:00] 아빠: 안녕\n"
            "(웃음)\n"
            "\n"
            "[00:30] 엄마: 반가워\n"
            "아무 형식 없는 줄"
        )
        _create_done_meeting(
            "passthrough-1", transcript,
            speakers={"아빠": "아빠", "엄마": "엄마"},
        )
        res = client.get("/api/jobs/passthrough-1/participation")
        assert res.status_code == 200
        data = res.json()

        labels = {s["label"] for s in data["speakers"]}
        assert labels == {"아빠", "엄마"}, (
            f"passthrough 줄이 화자로 집계되면 안 됨. 실제: {labels}"
        )
        turn_counts = {s["label"]: s["turn_count"] for s in data["speakers"]}
        assert turn_counts == {"아빠": 1, "엄마": 1}, f"실제: {turn_counts}"
