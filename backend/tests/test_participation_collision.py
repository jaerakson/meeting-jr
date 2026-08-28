"""participation 중복 display_name 재현 테스트.

PR #78 코드리뷰 발견 Bug 2:
diar 라벨이 transcript 화자보다 많을 때, 여분 라벨이 overlap으로
기존 이름에 매핑되어 같은 display_name 행이 두 개 나온다.

재현 시나리오:
- identity-mapped 회의: speakers = {"아빠": "아빠", "엄마": "엄마"}
- diarization 라벨 3개: SPEAKER_00(0~30), SPEAKER_01(30~55), SPEAKER_02(55~60)
- transcript에는 아빠, 엄마만 존재 (3행, 엄마가 55초 이후 발화)
- SPEAKER_02(55~60)가 "엄마"(55초 발화)와 overlap → "엄마"로 해석 → 중복

검증:
- participation speakers의 display_name이 모두 고유해야 함
- 이미 다른 라벨에 할당된 이름으로 해석된 여분 라벨은
  raw 라벨(SPEAKER_02) 그대로 폴백
"""

import json
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


# ===========================================================================
# Bug 2: participation이 중복 display_name을 낸다
# ===========================================================================

class TestParticipationDuplicateDisplayName:
    """diar 라벨이 transcript 화자보다 많을 때,
    여분 라벨이 overlap으로 기존 이름에 매핑되어
    같은 display_name 행이 두 개 나오는 버그를 재현한다."""

    def test_no_duplicate_display_names(self, client):
        """participation 응답의 display_name은 모두 서로 달라야 한다.

        SPEAKER_02(55~60초)가 엄마(55초 발화)와 overlap → "엄마" 중복.
        """
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 55, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 55, "end": 60, "speaker": "SPEAKER_02"}],
        }

        _create_done_meeting(
            job_id="dup-part-1",
            transcript="[00:00] 아빠: 안녕\n[00:30] 엄마: 반가워\n[00:55] 엄마: 마무리",
            speakers={"아빠": "아빠", "엄마": "엄마"},
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

    def test_extra_label_falls_back_to_raw_label(self, client):
        """이미 할당된 이름으로 해석된 여분 diar 라벨은
        raw 라벨(SPEAKER_02) 그대로 나와야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 55, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 55, "end": 60, "speaker": "SPEAKER_02"}],
        }

        _create_done_meeting(
            job_id="dup-part-2",
            transcript="[00:00] 아빠: 안녕\n[00:30] 엄마: 반가워\n[00:55] 엄마: 마무리",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

        res = client.get("/api/jobs/dup-part-2/participation")
        assert res.status_code == 200
        data = res.json()

        # SPEAKER_02는 중복 방지를 위해 raw 라벨로 폴백해야 한다
        sp02 = next(
            (s for s in data["speakers"] if s["label"] == "SPEAKER_02"),
            None,
        )
        assert sp02 is not None, "SPEAKER_02가 participation에 있어야 함"

        # display_name이 "엄마"가 아닌 "SPEAKER_02"여야 함
        other_names = {
            s["display_name"]
            for s in data["speakers"]
            if s["label"] != "SPEAKER_02"
        }
        assert sp02["display_name"] not in other_names, (
            f"SPEAKER_02의 display_name '{sp02['display_name']}'이 "
            f"다른 라벨과 중복됨. 전체: "
            f"{[(s['label'], s['display_name']) for s in data['speakers']]}"
        )

    def test_duplicate_count_check(self, client):
        """모든 display_name이 정확히 1번씩만 등장해야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 55, "speaker": "SPEAKER_01"}],
            "SPEAKER_02": [{"start": 55, "end": 60, "speaker": "SPEAKER_02"}],
        }

        _create_done_meeting(
            job_id="dup-part-3",
            transcript="[00:00] 아빠: 안녕\n[00:30] 엄마: 반가워\n[00:55] 엄마: 마무리",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

        res = client.get("/api/jobs/dup-part-3/participation")
        assert res.status_code == 200
        data = res.json()

        name_counts = {}
        for s in data["speakers"]:
            name_counts[s["display_name"]] = name_counts.get(s["display_name"], 0) + 1

        for name, count in name_counts.items():
            assert count == 1, (
                f"display_name '{name}'이 {count}번 등장 (1번이어야 함). "
                f"전체: {[(s['label'], s['display_name']) for s in data['speakers']]}"
            )
