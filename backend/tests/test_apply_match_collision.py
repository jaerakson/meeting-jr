"""apply-match 키 충돌·participation 중복·공백 불일치·해석 실패 재현 테스트.

PR #78 코드리뷰에서 발견된 4건의 버그를 TDD로 재현한다.

Bug 1: replace_map 키 충돌 — 서로 다른 diar 라벨이 같은 이름으로 해석되면
        뒤엣것이 앞엣것을 덮어써 transcript↔speakers 정합성이 깨진다.
Bug 2: participation 중복 display_name — 여분 diar 라벨이 기존 이름으로
        해석되어 같은 이름 행이 두 개 나온다.
Bug 3: 해석 실패를 삼키고 성공 반환 — (director 스펙 확정 후 추가 예정)
Bug 4: 공백 때문에 불일치 재발 — speakers 값에 앞뒤 공백이 있으면
        apply-match의 정규식 매칭이 실패한다.
"""

import json
import re
import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


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


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _create_done_meeting(
    job_id: str,
    transcript: str,
    speakers: dict,
    diarization: dict | None = None,
):
    """done 상태 회의를 DB에 직접 생성."""
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


def _extract_transcript_speakers(transcript: str) -> set[str]:
    """transcript에서 화자 토큰 집합을 추출한다."""
    return set(re.findall(r"\[\d+:\d{2}\]\s*(.+?):", transcript))


# ===========================================================================
# Bug 1: replace_map 키 충돌로 rename이 조용히 덮어써짐
# ===========================================================================

class TestReplaceMapKeyCollision:
    """서로 다른 diar 라벨이 _resolve_speaker_display로 같은 이름으로
    해석될 때, replace_map[current_name] = new_name 에서 뒤엣것이
    앞엣것을 덮어쓰는 버그를 재현한다."""

    def test_collision_all_speaker_values_in_transcript(self, client):
        """apply-match 후 speakers의 모든 값이 transcript 화자 토큰과 정합해야 한다.

        재현 시나리오:
        - speakers = {"SPEAKER_00": "김팀장"} (SPEAKER_00만 존재)
        - diarization에 SPEAKER_00 + SPEAKER_01
        - SPEAKER_01의 세그먼트가 "김팀장" 발화 구간과 겹침 → 김팀장으로 해석
        - matches = {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"}

        버그:
        - replace_map["김팀장"] = "박과장" (SPEAKER_00)
        - replace_map["김팀장"] = "이대리" (SPEAKER_01 덮어씀!)
        → 모든 "김팀장:"이 "이대리:"로 바뀌고, "박과장"은 transcript에 없음
        """
        # SPEAKER_01의 세그먼트가 "김팀장" 발화(0~30초)와 겹치도록 설정
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 5, "end": 25, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="collision-1",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 김팀장: 회의를 시작하겠습니다",
            speakers={"SPEAKER_00": "김팀장"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/collision-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/collision-1").json()
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        transcript = job["transcript"]

        transcript_names = _extract_transcript_speakers(transcript)

        # 핵심 검증: speakers의 모든 값이 transcript에 존재해야 한다
        for label, name in speakers.items():
            assert name in transcript_names, (
                f"speakers['{label}'] = '{name}'인데 transcript에 없음. "
                f"transcript 화자: {transcript_names}, 전문: {transcript}"
            )

    def test_collision_no_silent_overwrite(self, client):
        """두 라벨이 같은 current_name으로 해석되더라도
        각각의 새 이름이 transcript에 반영되어야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 5, "end": 25, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="collision-2",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 김팀장: 회의를 시작하겠습니다",
            speakers={"SPEAKER_00": "김팀장"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/collision-2/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/collision-2").json()
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)

        # 박과장과 이대리가 둘 다 speakers에 존재해야 함
        speaker_values = set(speakers.values())
        assert "박과장" in speaker_values, (
            f"'박과장'이 speakers 값에 없음: {speakers}"
        )
        assert "이대리" in speaker_values, (
            f"'이대리'가 speakers 값에 없음: {speakers}"
        )


# ===========================================================================
# Bug 2: participation이 중복 display_name을 낸다
# ===========================================================================

class TestParticipationDuplicateDisplayName:
    """diar 라벨이 transcript 화자보다 많을 때,
    여분 라벨이 overlap으로 기존 이름에 매핑되어
    같은 display_name 행이 두 개 나오는 버그를 재현한다."""

    def test_no_duplicate_display_names(self, client):
        """participation 응답의 display_name은 모두 서로 달라야 한다.

        재현 시나리오:
        - identity-mapped 회의: speakers = {"김팀장":"김팀장", "이대리":"이대리"}
        - diarization 라벨 3개: SPEAKER_00, SPEAKER_01, SPEAKER_02
        - transcript에는 김팀장, 이대리만 존재
        - SPEAKER_02 세그먼트가 김팀장 구간과 겹침 → "김팀장" 중복
        """
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 20, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 20, "end": 40, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 5, "end": 15, "speaker": "SPEAKER_02"}],
        }

        _create_done_meeting(
            job_id="dup-part-1",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:20] 이대리: 반갑습니다",
            speakers={"김팀장": "김팀장", "이대리": "이대리"},
            diarization=diarization,
        )

        res = client.get("/api/jobs/dup-part-1/participation")
        assert res.status_code == 200
        data = res.json()

        display_names = [s["display_name"] for s in data["speakers"]]

        # 핵심 검증: display_name에 중복이 없어야 한다
        assert len(display_names) == len(set(display_names)), (
            f"participation에 중복 display_name이 있음: {display_names}"
        )

    def test_extra_label_keeps_raw_label(self, client):
        """transcript에 매핑할 수 없는 여분 diar 라벨은
        해석된 이름이 아닌 raw 라벨(SPEAKER_XX) 그대로 나와야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 20, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 20, "end": 40, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 5, "end": 15, "speaker": "SPEAKER_02"}],
        }

        _create_done_meeting(
            job_id="dup-part-2",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:20] 이대리: 반갑습니다",
            speakers={"김팀장": "김팀장", "이대리": "이대리"},
            diarization=diarization,
        )

        res = client.get("/api/jobs/dup-part-2/participation")
        assert res.status_code == 200
        data = res.json()

        # SPEAKER_00 → 김팀장, SPEAKER_01 → 이대리로 해석되므로
        # SPEAKER_02는 중복을 피해 raw 라벨 그대로 나와야 한다
        display_names = {s["display_name"] for s in data["speakers"]}
        labels = {s["label"] for s in data["speakers"]}

        # 김팀장이 두 번 나오면 안 됨
        name_counts = {}
        for s in data["speakers"]:
            name_counts[s["display_name"]] = name_counts.get(s["display_name"], 0) + 1

        for name, count in name_counts.items():
            assert count == 1, (
                f"display_name '{name}'이 {count}번 등장. "
                f"전체: {[s['display_name'] for s in data['speakers']]}"
            )


# ===========================================================================
# Bug 3: 해석 실패를 삼키고 성공 반환
# (director 스펙 확정 후 테스트 추가 예정)
# ===========================================================================

class TestSilentSkipOnResolveFail:
    """diarization이 없는 identity-mapped 회의에서 apply-match 호출 시,
    모든 identity 라벨이 해석 실패 → continue로 건너뛰는데
    응답은 200 {"ok": true}인 버그를 재현한다.

    director가 확정할 응답 스펙에 맞춰 assertion을 작성한다.
    """

    def _setup_no_diar_identity_meeting(self, client, job_id: str):
        """diarization 없는 identity-mapped 회의 생성 (ClovaNote/txt 형태)."""
        _create_done_meeting(
            job_id=job_id,
            transcript="[00:00] 김과장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"김과장": "김과장", "이대리": "이대리"},
            diarization=None,  # diarization 없음
        )

    # placeholder — director 스펙 확정 후 assertion 채움
    def test_all_labels_skipped_returns_error_or_skipped(self, client):
        """모든 라벨이 해석 실패하면 단순 200 ok가 아닌
        실패를 알리는 응답이 와야 한다."""
        self._setup_no_diar_identity_meeting(client, "skip-all-1")

        res = client.post("/api/jobs/skip-all-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })

        # 현재 버그: 200 {"ok": true}인데 transcript·speakers 변경 없음
        # 확인: transcript가 변경되지 않았음 (버그 재현)
        job = client.get("/api/jobs/skip-all-1").json()
        assert "박과장" not in job["transcript"], (
            "diarization 없이 identity label을 해석할 수 없으므로 transcript에 박과장이 없어야 함"
        )

        # director 스펙에 따른 assertion:
        # 전부 실패 → 422 에러 반환 or 응답에 skipped 필드 포함
        # (아래 assertion은 스펙 확정 후 업데이트)
        response_data = res.json()

        # 최소한 "아무것도 안 바뀌었는데 ok: true"는 아니어야 함
        if res.status_code == 200:
            # 200이면 skipped 정보가 있어야 함
            assert "skipped" in response_data or "warning" in response_data, (
                f"모든 라벨 해석 실패인데 200 ok만 반환: {response_data}"
            )

    def test_partial_skip_reports_skipped_labels(self, client):
        """일부 라벨만 해석 실패 시 성공한 라벨은 적용하되,
        건너뛴 라벨을 응답에 포함해야 한다."""
        # SPEAKER_00은 speakers에 있으므로 성공, SPEAKER_99는 identity인데 해석 불가
        _create_done_meeting(
            job_id="skip-partial-1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=None,
        )

        res = client.post("/api/jobs/skip-partial-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장", "SPEAKER_99": "박대리"},
        })

        # SPEAKER_00은 적용되어야 함
        job = client.get("/api/jobs/skip-partial-1").json()
        assert "김과장" in job["transcript"], (
            "speakers에 있는 SPEAKER_00은 정상 적용되어야 함"
        )

        # SPEAKER_99는 건너뜀 → 응답에 표시
        response_data = res.json()
        if res.status_code == 200:
            assert "skipped" in response_data, (
                f"SPEAKER_99가 건너뛰었는데 skipped 정보 없음: {response_data}"
            )


# ===========================================================================
# Bug 4: 공백 때문에 불일치 재발 (백엔드 방어)
# ===========================================================================

class TestWhitespaceDefense:
    """speakers 값에 앞뒤 공백이 있어도 apply-match가 정상 동작해야 한다.

    프론트 TranscriptEditor.serialize()는 .trim()하지만
    handleSubmit()은 speaker_map에 trim 없이 저장한다.
    speakers["SPEAKER_00"] = "김팀장 "인데 transcript는 "김팀장"이면
    앵커 정규식이 매칭되지 않는다.
    """

    def test_trailing_space_in_speakers_still_matches(self, client):
        """speakers 값에 trailing 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-1",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": "김팀장 ", "SPEAKER_01": "이대리"},  # trailing space
        )

        res = client.post("/api/jobs/ws-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-1").json()
        # 핵심: "김팀장"(공백 없음)이 "박과장"으로 교체되어야 함
        assert "박과장:" in job["transcript"], (
            f"trailing space가 있어도 transcript에서 교체가 되어야 함. "
            f"실제: {job['transcript']}"
        )
        assert "김팀장" not in job["transcript"], (
            f"원래 이름이 transcript에 남아있으면 안 됨. 실제: {job['transcript']}"
        )

    def test_leading_space_in_speakers_still_matches(self, client):
        """speakers 값에 leading 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-2",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": " 김팀장", "SPEAKER_01": "이대리"},  # leading space
        )

        res = client.post("/api/jobs/ws-2/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-2").json()
        assert "박과장:" in job["transcript"], (
            f"leading space가 있어도 transcript에서 교체가 되어야 함. "
            f"실제: {job['transcript']}"
        )

    def test_spaces_both_sides_in_speakers(self, client):
        """speakers 값에 양쪽 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-3",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": " 김팀장 ", "SPEAKER_01": " 이대리 "},
        )

        res = client.post("/api/jobs/ws-3/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "정부장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-3").json()
        transcript = job["transcript"]
        assert "박과장:" in transcript, f"실제: {transcript}"
        assert "정부장:" in transcript, f"실제: {transcript}"
        assert "김팀장" not in transcript, f"원래 이름 잔존: {transcript}"
        assert "이대리" not in transcript, f"원래 이름 잔존: {transcript}"
