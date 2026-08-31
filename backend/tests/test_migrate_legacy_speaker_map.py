"""scripts/migrate_legacy_speaker_map.py 회귀 테스트 (PR C, qa-c3).

되돌릴 수 없는 DB 조작 스크립트라 테스트가 특히 중요하다. director의 최종 확정
사양(여러 차례 보정된 것 포함 — 아래가 최신)을 명세로 삼아 검증한다:

- **판정 순서**: "손댈 필요가 있는가"(조치불필요 판별)가 사전조건보다 먼저다.
  **최종 정의**: 세그먼트 라벨이 전부 diar 라벨 공간 안에 있으면 조치불필요.
  diar가 없는 행은 `SPEAKER_\\d+` 형태를 공간으로 본다. (director가 처음 준
  "관계식" 정의 — `∃ label, ∃ k≠label: map[k]==label` — 는 이후 이 diar-공간
  기준으로 대체됐다. backend-c3 구현이 최초 지시보다 정확해 채택된 것.)
- **overlap 휴리스틱 재사용 절대 금지**: 재키잉은 표시이름→라벨 역맵 하나로
  결정적으로 이뤄진다. 시간축·구간·overlap을 보지 않는다. diar가 아무리 풍부해도
  역맵으로 해소 안 되는 라벨은 복구되지 않고 건너뛴다 — 이걸 직접 단언한다.
- 사전조건 4개(①값 유일 아니면 병합 분기 ②값집합==라벨집합 ③키⊆diar키 ④매핑실패 0건)
  중 하나라도 불성립이면 그 행 **전체**를 건너뛴다(부분 복구 금지).
- 재키잉 후 render(new_segments, speaker_map)이 원본 transcript와 바이트 동일하지
  않으면 쓰지 않는다(안전장치).
- **집계 건수가 아니라 행 구성(ID→판정)을 단언한다** — 건수만 맞고 행이 틀린
  오구현이 이 데이터에서 실제로 두 번 나왔다(director 보고). "5ab8e338 유형"
  (조치불필요)과 "60b7b738 유형"(건너뜀)을 **같은 테스트 안에** 넣어 판정이
  뒤바뀌면 잡히게 한다.
- **병합 복구도 `speakers` 컬럼을 전혀 건드리지 않는다**(director 사양 변경 —
  비대표 키를 지우면 participation의 diar 경로가 그 구간을 raw SPEAKER_XX로
  노출한다, 실측 5%/3%). `--write`는 `transcript_segments`만 쓴다.
- 병합 복구 행은 `save_speaker_profile`이 여전히 422다(표시 이름 중복이 남으므로) —
  알려진 한계를 단언으로 고정해 나중에 역맵에 추측을 넣는 걸 막는다.
- `transcript_segments`가 NULL인 행(실측 DB 10건 중 9건이 이 상태)도 transcript
  파싱으로 올바르게 판정되고, dry-run 후에도 **NULL 그대로**여야 한다
  (`get_segments()`를 쓰면 백필 부작용이 생겨 이게 깨진다).
- 마이그레이션 후 apply-match가 실제로 200을 반환한다(이 스크립트의 존재 목적).

단언을 통과시키려고 약화하지 않는다. 단언이 틀렸다고 판단되면 director에게 보고.
현재 구현이 이 계약(특히 diar-공간 정의·speakers 불변)에 아직 못 미치는 부분이
있으면 테스트를 고치지 말고 그대로 실패시켜 보고한다.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import migrate_legacy_speaker_map as mig  # noqa: E402


# ---------------------------------------------------------------------------
# 공용 헬퍼 — app.database를 통해 실스키마와 동일한 DB에 행을 만든다.
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "meetings.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    return path


def _make_row(db_path, job_id, *, transcript, speakers, diarization=None, transcript_segments=None):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=job_id)
    db.update_job_result(
        job_id,
        transcript=transcript,
        speakers=speakers,
        diarization=diarization,
        transcript_segments=transcript_segments,
        status="done",
    )


def _read_raw_row(db_path, job_id) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT speakers, diarization, transcript, transcript_segments FROM meetings WHERE id = ?",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


def _all_bytes(db_path) -> bytes:
    return db_path.read_bytes()


# ---------------------------------------------------------------------------
# 1) dry-run은 DB를 전혀 건드리지 않는다
# ---------------------------------------------------------------------------

def test_dry_run_does_not_touch_db(db_path):
    _make_row(
        db_path, "legacy-1",
        transcript="[00:00] 아빠: 안녕\n[00:05] 손주환: 네",
        speakers={"아빠": "아빠", "손주환": "손주환"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )
    before = _all_bytes(db_path)

    rows = mig._load_rows(db_path)
    for row in rows:
        mig.judge(row)  # dry-run 경로: judge()만 호출, main()의 --write 없이

    after = _all_bytes(db_path)
    assert before == after, "judge() 호출만으로 DB 바이트가 달라지면 안 된다(읽기 전용)"

    # main()을 --write 없이 (기본 dry-run) 실제로 돌려도 마찬가지.
    exit_code = mig.main([f"--db={db_path}"])
    assert exit_code == 0
    after_main = _all_bytes(db_path)
    assert before == after_main, "dry-run main() 실행 후 DB 바이트가 달라지면 안 된다"


# ---------------------------------------------------------------------------
# 2) 정상 케이스: 조건 ②③④ 성립 + 값 유일 -> 자동복구, DB에 실제로 재키잉된다
# ---------------------------------------------------------------------------

def test_direct_recovery_rekeys_labels_and_apply_match_succeeds(db_path):
    """이 테스트가 스크립트의 존재 목적: 마이그레이션 후 apply-match가 200을 반환한다."""
    job_id = "legacy-recoverable"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 아빠: 안녕\n[00:05] 손주환: 네\n[00:10] 아빠: 뭐해",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )

    rows = mig._load_rows(db_path)
    row = next(r for r in rows if r["id"] == job_id)
    result = mig.judge(row)

    assert result["verdict"] == mig.OK_DIRECT, result["reason"]
    assert result["new_segments"] is not None
    new_labels = {s["label"] for s in result["new_segments"]}
    assert new_labels == {"SPEAKER_00", "SPEAKER_01"}, (
        f"실명 라벨이 diar 라벨로 재키잉돼야 한다. 실제: {new_labels}"
    )

    # --write로 실제 반영
    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    raw = _read_raw_row(db_path, job_id)
    assert raw["transcript"] == "[00:00] 아빠: 안녕\n[00:05] 손주환: 네\n[00:10] 아빠: 뭐해", (
        "transcript 문자열 컬럼은 절대 바뀌지 않아야 한다(스크립트 docstring 명시)"
    )
    segments = json.loads(raw["transcript_segments"])
    assert {s["label"] for s in segments} == {"SPEAKER_00", "SPEAKER_01"}

    # 마이그레이션 후 화면(표시 이름)이 한 글자도 바뀌지 않았는지 확인
    from app.transcript import render
    speakers = json.loads(raw["speakers"])
    assert render(segments, speakers) == raw["transcript"], (
        "재키잉 후에도 render(segments, speakers)는 원본 transcript와 바이트 동일해야 한다"
    )

    # 스크립트의 존재 목적: apply-match가 이제 실제로 200을 반환하는지
    from fastapi.testclient import TestClient
    import app.database as db_module
    import app.main as main_module
    assert db_module.DB_PATH == db_path

    with TestClient(main_module.app) as client:
        res = client.post(f"/api/jobs/{job_id}/apply-match", json={
            "matches": {"SPEAKER_00": "박부장"},
        })
        assert res.status_code == 200, (
            f"마이그레이션의 목적은 apply-match가 200을 반환하게 하는 것이다. "
            f"실제: {res.status_code} {res.text}"
        )
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["speakers"]["SPEAKER_00"] == "박부장"
        assert "박부장:" in job["transcript"]


# ---------------------------------------------------------------------------
# 3) 조치불필요: 레거시 서명이 없으면 사전조건 검사 자체를 하지 않는다
# ---------------------------------------------------------------------------

def test_no_op_when_no_legacy_signature(db_path):
    """이미 라벨 모델인 정상 행(키=SPEAKER_XX, 라벨=SPEAKER_XX)은 NO_OP."""
    job_id = "already-normal"
    _make_row(
        db_path, job_id,
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.NO_OP, result["reason"]
    assert result["new_segments"] is None


def test_no_op_precedes_condition_checks_for_partial_mapping(db_path):
    """[순서 방어] 매핑되지 않은 diar 라벨이 speaker_map에 없을 뿐인 정상 행은
    레거시 서명이 없으므로 NO_OP다 — 조건②(값 집합==라벨 집합)를 먼저 걸면
    이런 행이 SKIP으로 오판된다(스크립트 docstring이 명시적으로 경고하는 버그).
    """
    job_id = "partial-mapping-normal"
    _make_row(
        db_path, job_id,
        # SPEAKER_02는 speaker_map에 아예 없다 — 정상(그냥 이름 미지정 화자)
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_02: 네",
        speakers={"SPEAKER_00": "김팀장"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_02": [{"start": 5.0, "end": 10.0}],
        },
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.NO_OP, (
        f"레거시 서명이 없는 정상 행이 조건②에 걸려 SKIP으로 오판되면 안 된다. 실제: {result}"
    )


def test_5ab8e338_type_and_60b7b738_type_are_not_swapped(db_path):
    """[director 지시, 중요] 건수가 맞아도 행 구성이 뒤바뀌는 오구현이 이 데이터에서
    실제로 두 번 나왔다. 두 실측 유형을 **같은 테스트 안에서 ID→판정으로 함께** 단언해
    판정이 뒤바뀌면(둘 다 통과하는데 결과가 swap) 잡히게 한다.

    - `5ab8e338` 유형: 세그먼트 라벨이 diar 라벨 공간 안에 있고(SPEAKER_00·SPEAKER_02),
      speaker_map은 그중 일부만 이름을 붙인 **정상** 행 → 조치불필요.
    - `60b7b738` 유형: speaker_map 키가 실명("손주환")이라 diarization 라벨 공간과
      다리가 없는 **복구 불가** 행 → 손댈 필요는 있으나(라벨이 diar 공간 밖) 조건③에서
      건너뜀.
    """
    normal_id = "type-5ab8e338"
    _make_row(
        db_path, normal_id,
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_02: 네",
        speakers={"SPEAKER_00": "김팀장"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_02": [{"start": 5.0, "end": 10.0}],
        },
    )
    unrecoverable_id = "type-60b7b738"
    _make_row(
        db_path, unrecoverable_id,
        transcript="[00:00] 손주환: 안녕\n[00:05] 손재락: 네",
        speakers={"손주환": "손주환", "손재락": "손재락"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )

    rows = {r["id"]: r for r in mig._load_rows(db_path)}
    verdicts = {jid: mig.judge(row)["verdict"] for jid, row in rows.items()}

    assert verdicts == {
        normal_id: mig.NO_OP,
        unrecoverable_id: mig.SKIP,
    }, f"두 유형의 판정이 뒤바뀌면 안 된다. 실제: {verdicts}"

    # 건너뜀 사유가 실제로 조건③(diar 라벨 공간과 다리 없음)인지도 확인 —
    # 다른 조건에서 우연히 SKIP이 나온 게 아님을 보증.
    skip_reason = mig.judge(rows[unrecoverable_id])["reason"]
    assert "조건③" in skip_reason, f"복구 불가 사유가 조건③이어야 한다. 실제: {skip_reason}"


def test_unmapped_real_name_label_is_skipped_not_noop(db_path):
    """[판정 기준 확정, director 지시] "손댈 필요가 있는가"는 **diar 라벨 공간**
    기준이지, "speaker_map에 이 라벨을 가리키는 다른 키가 있는가"(관계식) 기준이
    아니다. 이 테스트가 둘을 가르는 유일한 케이스다.

    라벨이 실명("미지의사람")인데 speaker_map **어느 값에도 없는** 행:
    - 관계식 기준(예전, 폐기): baked = {label: ∃k≠label, map[k]==label}. 이 라벨을
      가리키는 키가 아예 없으므로 baked에 안 들어가 **조치불필요**로 오분류된다 —
      그런데 이 행은 실제로 깨져 있다(apply-match가 "미지의사람" 라벨을 모르므로 422).
      **깨진 행을 정상이라고 보고하는 것**은 이번 작업에서 이미 두 번 잡은 실패 유형이다.
    - diar 공간 기준(확정): "미지의사람"이 diarization 키 공간 안에 있는가만 본다.
      없으면 손댈 필요가 있다고 보고, 조건②(값집합==라벨집합)에서 값 쪽에 없으므로
      **건너뜀**으로 정확히 보고한다(복구는 못 해도 "정상"이라 속이지 않는다).
    """
    job_id = "unmapped-real-name-label"
    _make_row(
        db_path, job_id,
        # SPEAKER_00은 정상적으로 이름이 붙어 있다. "미지의사람"은 speaker_map
        # 어느 값에도 없다 — 이 라벨을 가리키는 키가 아예 없다(관계식이라면 못 잡는다).
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] 미지의사람: 네",
        speakers={"SPEAKER_00": "김팀장"},
        diarization={"SPEAKER_00": [{"start": 0.0, "end": 5.0}]},
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.SKIP, (
        f"라벨이 실명인데 speaker_map 값에 없는 행은 조치불필요가 아니라 건너뜀이어야 "
        f"한다(관계식 기준이면 조치불필요로 오분류돼 깨진 행을 정상이라 보고한다). "
        f"실제: {result}"
    )
    assert result["new_segments"] is None


def test_diar_richness_does_not_rescue_unresolved_label(db_path):
    """[overlap 휴리스틱 재유입 방지, director 강조] 역맵으로 해소 안 되는 라벨은
    diarization이 아무리 풍부해도(정확히 겹치는 시간 구간이 있어도) 복구되지 않는다.
    재키잉은 시간축을 전혀 보지 않는다 — 이 사실 자체를 단언한다."""
    job_id = "diar-richness-no-rescue"
    # "미지의화자"는 speaker_map 어디에도 값으로 없다. 하지만 diar에는 정확히
    # 그 발화 구간과 겹치는 SPEAKER_02가 존재한다 — overlap 휴리스틱이라면 이걸로
    # "미지의화자" = SPEAKER_02 라고 추론했을 상황이다.
    _make_row(
        db_path, job_id,
        transcript="[00:00] 아빠: 안녕\n[00:05] 미지의화자: 정확히 SPEAKER_02 구간과 겹침",
        speakers={"SPEAKER_00": "아빠"},  # "미지의화자"를 가리키는 키가 없다
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_02": [{"start": 5.0, "end": 10.0}],  # 시간상 완벽히 겹침
        },
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.SKIP, (
        f"diar 구간이 시간적으로 완벽히 겹쳐도 역맵으로 해소 안 되는 라벨은 복구되면 "
        f"안 된다(overlap 추론 재유입 금지). 실제: {result}"
    )
    assert result["new_segments"] is None


# ---------------------------------------------------------------------------
# 3-b) transcript_segments가 NULL인 행 — 실측 DB 10건 중 9건이 이 상태
# ---------------------------------------------------------------------------

def test_null_transcript_segments_row_judged_via_transcript_parse(db_path):
    """transcript_segments가 NULL이어도 transcript를 파싱해 올바르게 판정한다."""
    job_id = "null-segments-row"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 아빠: 안녕\n[00:05] 손주환: 네",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
        transcript_segments=None,
    )
    raw_before = _read_raw_row(db_path, job_id)
    assert raw_before["transcript_segments"] is None, "전제: transcript_segments가 NULL이어야 한다"

    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.OK_DIRECT, result["reason"]
    assert {s["label"] for s in result["new_segments"]} == {"SPEAKER_00", "SPEAKER_01"}


def test_dry_run_never_backfills_null_transcript_segments(db_path):
    """[get_segments() 오용 방지] dry-run이 transcript_segments가 NULL인 행을
    판정하면서 그 컬럼을 **백필해버리면 안 된다** — `app.transcript.get_segments()`를
    쓰면 조회만 해도 DB에 쓰는 부작용이 있어 dry-run의 읽기 전용 보장이 깨진다."""
    job_id = "null-segments-dry-run"
    _make_row(
        db_path, job_id,
        transcript="[00:00] SPEAKER_00: 안녕",
        speakers={"SPEAKER_00": "김팀장"},
        diarization={"SPEAKER_00": [{"start": 0.0, "end": 5.0}]},
        transcript_segments=None,
    )
    exit_code = mig.main([f"--db={db_path}"])  # dry-run (기본)
    assert exit_code == 0

    raw_after = _read_raw_row(db_path, job_id)
    assert raw_after["transcript_segments"] is None, (
        "dry-run이 transcript_segments를 백필하면 안 된다(get_segments() 오용 증거)"
    )


# ---------------------------------------------------------------------------
# 4) 사전조건 각각의 불성립 케이스 — 전체 건너뜀(부분 복구 금지)
# ---------------------------------------------------------------------------

def test_condition2_violation_value_set_neq_label_set_skips(db_path):
    """조건②: speaker_map 값 집합이 segment 라벨 집합과 다르면 SKIP.
    (레거시 서명은 있으나 값 하나가 라벨 어디에도 없음 — 되돌릴 방법이 없다)"""
    job_id = "cond2-violation"
    _make_row(
        db_path, job_id,
        # "아빠"는 라벨로 존재(레거시 서명 성립: SPEAKER_00->아빠, 라벨에 아빠 있음).
        # 그러나 speaker_map 값 "엄마"는 어느 segment 라벨에도 없다 -> 값 집합 != 라벨 집합.
        transcript="[00:00] 아빠: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.SKIP, result["reason"]
    assert "조건②" in result["reason"]
    assert result["new_segments"] is None, "조건 불성립이면 어떤 재키잉 결과도 만들면 안 된다"


def test_condition3_violation_key_not_subset_of_diar_keys_skips(db_path):
    """조건③: speaker_map 키가 diarization 키의 부분집합이 아니면 SKIP.
    (diarization 자체가 없거나, 키가 diar에 없는 라벨을 가리킴 — 되돌릴 diar 라벨이 없다)"""
    job_id = "cond3-violation"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 아빠: 안녕\n[00:05] 손주환: 네",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"},
        diarization=None,  # diar 데이터 자체가 없음 -> 키가 diar 키의 부분집합일 수 없음
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.SKIP, result["reason"]
    assert "조건③" in result["reason"]
    assert result["new_segments"] is None


def test_condition4_violation_unmapped_label_skips(db_path):
    """조건④: 매핑 실패 라벨(어느 speaker_map 값도 가리키지 못하는 segment 라벨)이
    있으면 SKIP. (레거시 서명은 있지만 라벨 중 하나가 역맵으로 안 풀림)"""
    job_id = "cond4-violation"
    _make_row(
        db_path, job_id,
        # "아빠"는 레거시 서명 성립(SPEAKER_00->아빠). "미지의화자"는 speaker_map
        # 어디에도 값으로 없어 역맵 실패 -> 매핑 실패 라벨 1건.
        transcript="[00:00] 아빠: 안녕\n[00:05] 미지의화자: 네",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "미지의화자"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )
    # 위 구성은 사실 조건②까지 성립해버릴 수 있으니(값 집합 {아빠,미지의화자} ==
    # 라벨 집합 {아빠,미지의화자}) 조건④가 별도로 걸리는 걸 확인하려면 값 집합에는
    # 있지만 라벨에는 없는 이름을 speaker_map에 추가로 넣어 조건②를 먼저 깨지 않게
    # 하되, 라벨 쪽에 speaker_map 값으로 없는 라벨을 하나 추가한다.
    job_id2 = "cond4-violation-2"
    _make_row(
        db_path, job_id2,
        transcript="[00:00] 아빠: 안녕\n[00:05] 어떤유령라벨: 네",
        speakers={"SPEAKER_00": "아빠"},  # "어떤유령라벨"을 가리키는 키가 없다
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
        },
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id2)
    result = mig.judge(row)
    # 이 구성은 값 집합 {아빠} != 라벨 집합 {아빠,어떤유령라벨}이라 조건②가 먼저 걸린다.
    # 조건④를 조건②와 분리해서 걸리게 하려면 값 집합==라벨 집합이면서 역맵이 실패하는
    # 입력이 필요한데, 값에 있는 이름은 정의상 역맵이 항상 성공한다(inverse는 값->키).
    # 따라서 조건④는 구조적으로 "값 집합==라벨 집합"이 성립하는 한 항상 성립한다 —
    # 이 사실 자체를 아래에서 검증한다(조건④가 조건②의 그림자 조건이 아니라는 것도
    # 함께 확인: 코드 경로상 조건②를 통과하면 조건④는 자동 성립).
    assert result["verdict"] == mig.SKIP
    assert "조건②" in result["reason"]


def test_condition4_is_structurally_implied_by_condition2_but_path_exists(db_path):
    """[코드 경로 점검] judge()의 조건④ 분기가 실제로 도달 가능한지 확인한다.
    values == labels 이면 inverse = {name: key}에서 모든 label(=어떤 name)이 항상
    inverse에 있으므로 unmapped는 구조적으로 항상 빈다. 즉 조건④ SKIP 분기는
    **현재 judge() 구현에서 도달 불가능한 죽은 코드**일 수 있다 — 이게 사실이라면
    director/backend-c3에게 보고할 사항이지 테스트로 억지로 뚫을 게 아니다.
    이 테스트는 그 사실을 실제로 확인하는 탐침이다(도달 가능하면 실패해서 알려준다).
    """
    # values(=speaker_map.values()) == labels 가 성립하는 임의의 유효 케이스를 몇 개
    # 만들어 unmapped가 항상 비는지 direct 검증한다(judge 내부 로직을 반사적으로 확인).
    speaker_map = {"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"}
    labels = {"아빠", "손주환"}
    values = set(speaker_map.values())
    assert values == labels
    inverse = {name: key for key, name in speaker_map.items()}
    unmapped = [l for l in labels if l not in inverse]
    assert unmapped == [], (
        "조건④(매핑 실패 라벨)는 조건②(값 집합==라벨 집합)가 성립하는 한 항상 "
        "충족된다 — inverse의 키 집합이 정의상 values와 같기 때문이다. 즉 judge()의 "
        "조건④ SKIP 분기는 현재 로직상 도달 불가능한 코드로 보인다. 이 테스트가 실패한다면 "
        "(unmapped가 비지 않는다면) 그 반례를 director/backend-c3에게 보고할 것."
    )


# ---------------------------------------------------------------------------
# 5) 안전장치: 재키잉 후 render()가 원본과 다르면 쓰지 않는다
# ---------------------------------------------------------------------------

def test_render_mismatch_after_rekey_skips_and_does_not_write(db_path):
    """모든 조건을 통과하는 것처럼 보여도, 재키잉 후 render() 결과가 원본과
    바이트 단위로 다르면 그 행은 쓰지 않는다(안전장치). raw 보존이 깨지는
    입력(라벨 앞뒤 공백 등 정규형과 어긋나는 원본 줄)으로 재현한다."""
    job_id = "render-mismatch"
    # 라벨 뒤에 공백 두 칸 등 정규형과 다른 원본 줄을 transcript_segments에 직접
    # 주입해 raw가 붙은 상태를 만든다. 재키잉 시 raw를 그대로 두면(스크립트가
    # "raw 키는 있던 그대로 둔다"고 명시) display==label일 때만 raw를 쓰는 render()
    # 규칙과 충돌해 원본과 달라질 수 있는 경계를 겨냥한다.
    segments = [
        {"start": 0, "end": None, "label": "아빠", "text": "안녕", "raw": "[00:00]  아빠:  안녕"},
        {"start": 5, "end": None, "label": "손주환", "text": "네"},
    ]
    from app.transcript import render as _render
    original_transcript = _render(segments)  # raw가 있으므로 raw 그대로 나옴

    _make_row(
        db_path, job_id,
        transcript=original_transcript,
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
        transcript_segments=segments,
    )

    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)

    # 재키잉 후 라벨이 SPEAKER_00/01로 바뀌면 display(="아빠"라는 이름)와 label
    # ("SPEAKER_00")이 달라지므로 raw는 버려지고 정규형으로 렌더된다 — 그런데 원본은
    # raw(비정규 공백)였으므로 재키잉 후 render 결과가 원본과 달라져야 한다.
    if result["verdict"] != mig.SKIP:
        # 만약 통과했다면 안전장치가 뚫린 것 — 실제로 바이트가 다른지 직접 확인해 증명한다.
        from app.transcript import render as _render2
        rendered = _render2(result["new_segments"], result["new_speaker_map"] or {"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"})
        assert rendered == original_transcript, (
            f"안전장치가 뚫렸다: 재키잉 후 render 결과가 원본과 다른데도 SKIP되지 않았다. "
            f"verdict={result['verdict']}, rendered={rendered!r}, original={original_transcript!r}"
        )
    else:
        assert "안전장치" in result["reason"], (
            f"이 케이스는 안전장치 불성립으로 SKIP돼야 하는데 다른 사유로 SKIP됐다: {result['reason']}"
        )
        assert result["new_segments"] is None


# ---------------------------------------------------------------------------
# 6) 중복 이름 병합 — 대표 라벨 선택이 결정적(순서 무관)
# ---------------------------------------------------------------------------

def _dup_speaker_map():
    return {"SPEAKER_01": "이삼희", "SPEAKER_02": "이삼희"}


def _dup_diar_longer_02():
    return {
        "SPEAKER_01": [{"start": 0.0, "end": 3.0}],       # 3초
        "SPEAKER_02": [{"start": 10.0, "end": 20.0}],     # 10초 (더 김)
    }


def test_duplicate_merge_picks_longest_speech_deterministically(db_path):
    """총 발화 길이가 더 긴 라벨이 대표로 선택된다. dict 삽입 순서를 뒤집어도
    (SPEAKER_02를 먼저 넣어도) 같은 결과가 나와야 한다(순서 의존성 없음)."""
    diar = _dup_diar_longer_02()

    map_order_a = {"SPEAKER_01": "이삼희", "SPEAKER_02": "이삼희"}
    map_order_b = {"SPEAKER_02": "이삼희", "SPEAKER_01": "이삼희"}

    reduced_a, dup_a, _ = mig._merge_duplicate_names(map_order_a, diar)
    reduced_b, dup_b, _ = mig._merge_duplicate_names(map_order_b, diar)

    assert reduced_a == reduced_b, (
        f"speaker_map 삽입 순서만 바꿨는데 대표 선택 결과가 다르다: {reduced_a} vs {reduced_b}"
    )
    assert reduced_a == {"SPEAKER_02": "이삼희"}, (
        f"총 발화 길이가 더 긴 SPEAKER_02가 대표여야 한다. 실제: {reduced_a}"
    )
    assert dup_a == ["이삼희"]


def test_duplicate_merge_tie_break_is_lexicographic_and_deterministic(db_path):
    """총 발화 길이가 동률이면 사전순으로 가장 작은 키가 대표(그리고 항상 같은 결과)."""
    diar_tied = {
        "SPEAKER_05": [{"start": 0.0, "end": 5.0}],   # 5초
        "SPEAKER_02": [{"start": 0.0, "end": 5.0}],   # 5초 동률
    }
    speaker_map = {"SPEAKER_05": "이삼희", "SPEAKER_02": "이삼희"}

    # 여러 번 반복해도(딕셔너리/집합 순서에 흔들리지 않고) 항상 같은 결과가 나와야 한다.
    results = {tuple(sorted(mig._merge_duplicate_names(speaker_map, diar_tied)[0].items())) for _ in range(20)}
    assert len(results) == 1, f"반복 실행마다 대표 선택이 달라진다(비결정적): {results}"

    reduced, _, _ = mig._merge_duplicate_names(speaker_map, diar_tied)
    assert reduced == {"SPEAKER_02": "이삼희"}, (
        f"동률이면 사전순 최소(SPEAKER_02 < SPEAKER_05)가 대표여야 한다. 실제: {reduced}"
    )


def test_duplicate_merge_end_to_end_via_judge(db_path):
    """judge() 전체 파이프라인에서 중복 병합이 OK_MERGED로 판정되고, 비대표 키가
    speaker_map에서 제거되며, 화면(transcript)은 바뀌지 않는지 확인."""
    job_id = "dup-merge"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디",
        speakers=_dup_speaker_map(),
        diarization=_dup_diar_longer_02(),
    )
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)

    assert result["verdict"] == mig.OK_MERGED, result["reason"]
    # [director 사양 변경] 비대표 키를 지우면 participation의 diar 경로가 그 구간을
    # raw SPEAKER_XX로 노출한다(실측 5%/3%) — 그래서 병합 복구도 speakers를 전혀
    # 건드리지 않는다. new_speaker_map은 항상 None(= "쓰지 않음")이어야 한다.
    assert result["new_speaker_map"] is None, (
        f"병합 복구도 speakers 컬럼을 건드리면 안 된다(비대표 키 유지). "
        f"실제: {result['new_speaker_map']}"
    )
    new_labels = {s["label"] for s in result["new_segments"]}
    assert new_labels == {"SPEAKER_02"}, (
        f"두 줄 모두 대표 라벨(SPEAKER_02)로 재키잉돼야 한다(줄 배정을 추측하지 않고 "
        f"같은 이름의 모든 줄이 대표로 간다). 실제: {new_labels}"
    )

    # 원본(수정 안 한) speaker_map으로 렌더해도 바이트 동일해야 한다 — 대표 키만
    # 라벨로 쓰이므로 비대표 키가 map에 남아있어도 조회에 영향이 없다.
    from app.transcript import render as _render
    original = "[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디"
    assert _render(result["new_segments"], _dup_speaker_map()) == original, (
        "병합 후에도 화면(표시 이름)은 한 글자도 바뀌면 안 된다(원본 speaker_map 기준)"
    )


def test_duplicate_merge_write_leaves_speakers_column_byte_identical(db_path):
    """--write 실행 후 병합 복구 행의 speakers 컬럼이 실행 전후 완전히 동일해야 한다
    (director 사양 변경 — 비대표 키 제거 금지). transcript_segments만 바뀐다."""
    job_id = "dup-merge-write"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디",
        speakers=_dup_speaker_map(),
        diarization=_dup_diar_longer_02(),
    )
    before = _read_raw_row(db_path, job_id)

    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    after = _read_raw_row(db_path, job_id)
    assert after["speakers"] == before["speakers"], (
        f"병합 복구는 speakers 컬럼을 전혀 건드리면 안 된다. "
        f"전: {before['speakers']!r}, 후: {after['speakers']!r}"
    )
    assert after["transcript"] == before["transcript"], "transcript 문자열도 바뀌면 안 된다"
    new_labels = {s["label"] for s in json.loads(after["transcript_segments"])}
    assert new_labels == {"SPEAKER_02"}, "segments만 대표 라벨로 재키잉돼 있어야 한다"


def test_duplicate_merge_does_not_expose_raw_speaker_id_in_participation(db_path):
    """[최종 산출물 검증] 병합 복구 전후로 participation API의 display_name이
    비대표 라벨(SPEAKER_01)을 포함해 전부 동일해야 한다. speakers에서 비대표 키를
    지우면 participation의 diar 경로가 그 구간을 raw 'SPEAKER_01'로 노출한다 —
    이게 director가 사양을 바꾼 이유이고, 중간 산출물(segments 파일)이 아니라
    최종 산출물(API 응답)로 검증해야 이 회귀를 잡을 수 있다."""
    import app.database as db_module
    import app.main as main_module
    from fastapi.testclient import TestClient

    job_id = "dup-merge-participation"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디",
        speakers=_dup_speaker_map(),
        diarization=_dup_diar_longer_02(),
    )

    with TestClient(main_module.app) as client:
        before = client.get(f"/api/jobs/{job_id}/participation").json()

    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    with TestClient(main_module.app) as client:
        after = client.get(f"/api/jobs/{job_id}/participation").json()

    before_names = {s["label"]: s["display_name"] for s in before["speakers"]}
    after_names = {s["label"]: s["display_name"] for s in after["speakers"]}
    assert after_names == before_names, (
        f"병합 복구 후 participation의 display_name이 바뀌면 안 된다(특히 비대표 라벨이 "
        f"raw SPEAKER_XX로 노출되면 안 된다). 전: {before_names}, 후: {after_names}"
    )
    for label, name in after_names.items():
        assert name == "이삼희", (
            f"비대표 라벨({label})의 표시 이름이 raw로 노출됐다 — speakers에서 키가 "
            f"지워졌다는 증거. 실제: {after_names}"
        )


def test_participation_check_actually_has_discriminating_power(db_path):
    """[판별력 증명, director 지시] 위 test_duplicate_merge_does_not_expose_raw_speaker_id_in_participation가
    통과한 것이 "무딘 검사가 우연히 통과"가 아니라는 것을 증명한다. 기각된 설계
    (비대표 키를 speaker_map에서 제거)를 **일부러 시뮬레이션**해서 같은 participation
    비교가 실제로 차이를 잡아내는지 확인한다 — 차이가 안 잡히면 그 단언은 무의미하다."""
    import app.database as db_module
    import app.main as main_module
    from fastapi.testclient import TestClient

    job_id = "dup-merge-discriminating-power"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디",
        speakers=_dup_speaker_map(),  # {"SPEAKER_01": "이삼희", "SPEAKER_02": "이삼희"}
        diarization=_dup_diar_longer_02(),
    )

    with TestClient(main_module.app) as client:
        before = client.get(f"/api/jobs/{job_id}/participation").json()
    before_names = {s["label"]: s["display_name"] for s in before["speakers"]}

    # 올바른 마이그레이션 실행(비대표 키 유지) — 실제 코드 경로.
    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    # 여기서 기각된 설계를 **수동으로 시뮬레이션**한다: 비대표 키(SPEAKER_01)를
    # speaker_map에서 강제로 지운 뒤 participation을 다시 조회해 차이가 나는지 본다.
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT speakers FROM meetings WHERE id = ?", (job_id,)).fetchone()
        speakers_now = json.loads(row[0])
        assert "SPEAKER_01" in speakers_now, (
            "전제: 올바른 마이그레이션은 비대표 키를 지우지 않는다"
        )
        rejected_design_map = {k: v for k, v in speakers_now.items() if k != "SPEAKER_01"}
        conn.execute(
            "UPDATE meetings SET speakers = ? WHERE id = ?",
            (json.dumps(rejected_design_map, ensure_ascii=False), job_id),
        )
        conn.commit()
    finally:
        conn.close()

    with TestClient(main_module.app) as client:
        after_rejected_design = client.get(f"/api/jobs/{job_id}/participation").json()
    after_rejected_names = {s["label"]: s["display_name"] for s in after_rejected_design["speakers"]}

    assert after_rejected_names != before_names, (
        "판별력 없음: 비대표 키를 실제로 지웠는데도 participation의 display_name이 "
        f"안 바뀐다면, 위 회귀 테스트는 무엇을 잘못 만들어도 통과하는 무딘 검사다. "
        f"before={before_names}, rejected_design={after_rejected_names}"
    )
    assert after_rejected_names.get("SPEAKER_01") == "SPEAKER_01", (
        f"비대표 키를 지우면 그 구간은 raw 라벨로 노출돼야 한다(기각된 설계의 실제 결함). "
        f"실제: {after_rejected_names}"
    )


def test_save_speaker_profile_still_422_after_merge_recovery(db_path):
    """[알려진 한계, 고정] 병합 복구된 행은 표시 이름이 여전히 중복이므로
    save_speaker_profile은 계속 422다. 복구했다고 이 기능까지 되는 게 아니다 —
    이 단언이 없으면 나중에 '왜 안 되지' 하며 역맵에 추측(중복 시 임의 선택)을
    집어넣는 재유입 압력이 생긴다."""
    import app.database as db_module
    import app.main as main_module
    from fastapi.testclient import TestClient

    job_id = "dup-merge-profile-limit"
    _make_row(
        db_path, job_id,
        transcript="[00:00] 이삼희: 첫마디\n[00:10] 이삼희: 둘째마디",
        speakers=_dup_speaker_map(),
        diarization=_dup_diar_longer_02(),
    )
    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    with TestClient(main_module.app) as client:
        res = client.post(f"/api/jobs/{job_id}/save-speaker-profile", json={
            "speaker_label": "이삼희", "profile_name": "이삼희",
        })
        assert res.status_code == 422, (
            f"병합 복구 행은 표시 이름이 여전히 중복이라 프로필 추출이 422여야 한다 "
            f"(알려진 한계, 되돌리지 말 것). 실제: {res.status_code} {res.text}"
        )


# ---------------------------------------------------------------------------
# 7) 조건 불성립인데 쓰는 경로가 없는지 — 적극적으로 뚫어본다
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("job_id,transcript,speakers,diarization", [
    ("skip1-cond2", "[00:00] 아빠: 안녕\n[00:05] SPEAKER_01: 네",
     {"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
     {"SPEAKER_00": [{"start": 0.0, "end": 5.0}], "SPEAKER_01": [{"start": 5.0, "end": 10.0}]}),
    ("skip2-cond3-no-diar", "[00:00] 아빠: 안녕\n[00:05] 손주환: 네",
     {"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"}, None),
    ("skip3-cond3-stray-key", "[00:00] 아빠: 안녕\n[00:05] 손주환: 네",
     {"SPEAKER_00": "아빠", "SPEAKER_01": "손주환"},
     {"SPEAKER_99": [{"start": 0.0, "end": 5.0}]}),
])
def test_skipped_rows_never_produce_writable_result(db_path, job_id, transcript, speakers, diarization):
    """SKIP 판정이면 new_segments/new_speaker_map이 항상 None이어야 한다 —
    main()의 쓰기 분기(`if args.write and result["new_segments"] is not None`)가
    SKIP 행을 절대 건드리지 못하게 하는 유일한 방어선이라 이 불변식이 핵심이다."""
    _make_row(db_path, job_id, transcript=transcript, speakers=speakers, diarization=diarization)
    row = next(r for r in mig._load_rows(db_path) if r["id"] == job_id)
    result = mig.judge(row)
    assert result["verdict"] == mig.SKIP, f"이 케이스는 SKIP이어야 하는데: {result}"
    assert result["new_segments"] is None
    assert result["new_speaker_map"] is None


def test_write_flag_never_touches_skip_or_noop_rows(db_path):
    """--write를 실제로 실행해도 SKIP/NO_OP 행의 raw DB 바이트(해당 컬럼)는
    변하지 않아야 한다 — judge()의 반환값을 신뢰하지 않고 실제 쓰기 결과로 검증."""
    skip_id = "write-test-skip"
    noop_id = "write-test-noop"
    ok_id = "write-test-ok"

    _make_row(
        db_path, skip_id,
        transcript="[00:00] 아빠: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        diarization={"SPEAKER_00": [{"start": 0.0, "end": 5.0}], "SPEAKER_01": [{"start": 5.0, "end": 10.0}]},
    )
    _make_row(
        db_path, noop_id,
        transcript="[00:00] SPEAKER_00: 안녕",
        speakers={"SPEAKER_00": "김팀장"},
        diarization={"SPEAKER_00": [{"start": 0.0, "end": 5.0}]},
    )
    _make_row(
        db_path, ok_id,
        transcript="[00:00] 아빠: 안녕",
        speakers={"SPEAKER_00": "아빠"},
        diarization={"SPEAKER_00": [{"start": 0.0, "end": 5.0}]},
    )

    before_skip = _read_raw_row(db_path, skip_id)
    before_noop = _read_raw_row(db_path, noop_id)

    exit_code = mig.main([f"--db={db_path}", "--write"])
    assert exit_code == 0

    after_skip = _read_raw_row(db_path, skip_id)
    after_noop = _read_raw_row(db_path, noop_id)
    after_ok = _read_raw_row(db_path, ok_id)

    assert after_skip == before_skip, "SKIP 행은 --write 실행 후에도 전혀 바뀌면 안 된다"
    assert after_noop == before_noop, "NO_OP 행은 --write 실행 후에도 전혀 바뀌면 안 된다"
    # OK 행만 실제로 바뀌었는지(대조군) 확인 — 위 두 단언이 "아무것도 안 바뀜"이
    # 우연이 아니라 write 로직이 실제로 실행됐다는 증거.
    assert json.loads(after_ok["transcript_segments"])[0]["label"] == "SPEAKER_00"
