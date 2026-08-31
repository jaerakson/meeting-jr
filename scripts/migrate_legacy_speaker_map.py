#!/usr/bin/env python3
"""레거시 행 복구 마이그레이션 — transcript_segments 의 라벨을 실명에서 diar 라벨로 되돌린다.

## 무엇을 고치는가

PR C 이전의 `TranscriptEditor` 는 화자 이름을 **본문에 구워서** 보냈다. 그래서 저장된 행이
    speaker_map = {"SPEAKER_00": "아빠", ...}      (키 = diar 라벨)
    transcript  = "[00:03] 아빠: ..."              (라벨 = 실명)
처럼 **키 공간과 라벨 공간이 어긋난** 상태가 됐다. 라벨 모델(PR B)에서 표시 이름은
`speaker_map.get(label, label)` 하나로만 결정되므로, 이런 행에서는 `matches` 의 키
(항상 `SPEAKER_XX`)가 segment 라벨 집합에 없어 apply-match 가 **422 로 거부**된다.

원인(본문에 이름을 굽던 프론트 계약)은 PR C 가 막았다. 이 스크립트는 **이미 깨진 행**을
되살린다. 새로 생기는 행은 없으므로 모집단은 고정이다.

## 무엇을 바꾸는가 (그리고 무엇을 바꾸지 않는가)

바꾸는 것: `transcript_segments` 의 `label` 뿐이다. 실명 → 그 이름을 가리키는 diar 라벨.
바꾸지 않는 것: `transcript` 문자열, `speaker_map`, `diarization`, 그 외 모든 컬럼.

표시 이름은 speaker_map 이 나르므로 **사용자 화면은 한 글자도 바뀌지 않아야 정상이다.**
이것을 희망이 아니라 **검사**로 강제한다 — 재키잉한 segments 를 `render(new_segments,
speaker_map)` 한 결과가 현재 transcript 와 **바이트 동일**하지 않으면 그 행은 쓰지 않는다.
안 맞으면 우리가 이 행에 대해 뭔가 잘못 알고 있는 것이다.

## 행별 사전조건 (하나라도 불성립이면 그 행 **전체**를 건너뛴다 — 부분 복구 금지)

    1. speaker_map 값이 유일할 것            (중복은 아래 '중복 이름 병합' 경로로)
    2. speaker_map 값 집합 == segment 라벨 집합
    3. speaker_map 키 ⊆ diarization 키
    4. 매핑 실패 라벨 0건                    (모든 실명 라벨이 라벨로 되돌려질 것)

## 중복 이름 병합 — 지운 overlap 휴리스틱과 무엇이 다른가  ★ 반드시 읽을 것

여러 diar 라벨이 한 이름으로 지정된 행이 있다(예: SPEAKER_01·SPEAKER_02 = "이삼희").
이때 대표 라벨은 **diar 총 발화 길이가 가장 긴 키**로 고른다(동률이면 사전순 최소 —
같은 입력이면 항상 같은 출력).

이것은 우리가 PR B 에서 지운 overlap 휴리스틱과 **다르다.**
  - 지운 것: *어느 줄이 누구의 발화인지* 를 transcript 줄 구간과 diar 구간의 시간 겹침으로
    **추측**하는 것. 줄마다 다른 답이 나오고, 틀려도 조용히 틀린다.
  - 이것: 사용자가 이미 "이 라벨들은 같은 사람"이라고 **선언한** 이름에 대해, 그 이름을
    대표할 **클러스터 하나를 고르는** 것. **줄 배정은 추측하지 않는다** — 같은 이름의 줄은
    전부 같은 대표 라벨로 간다.
그리고 어느 쪽으로 고르든 표시 이름은 동일하므로(같은 이름의 라벨들이니까) 위의 바이트
동일 검사가 그대로 성립한다. **폐기된 방식의 재유입이 아니다.** 이 문단을 지우지 말 것.

## 사용법

    python3 scripts/migrate_legacy_speaker_map.py              # dry-run (기본, 읽기 전용)
    python3 scripts/migrate_legacy_speaker_map.py --write      # 실제 기록
    python3 scripts/migrate_legacy_speaker_map.py --db PATH    # DB 경로 지정

**기본은 dry-run 이다. 자동 실행 금지** — 서버 시작·요청 처리 경로에서 부르지 말 것.
사람이 결과 리포트를 읽고 판단한 뒤 `--write` 로 한 번 돌리는 일회성 도구다.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.transcript import parse, render  # noqa: E402  (sys.path 조정 후여야 한다)

DEFAULT_DB = BACKEND / "meetings.db"

# 판정 코드
OK_DIRECT = "복구(단순 재키잉)"
OK_MERGED = "복구(중복 이름 병합)"
NO_OP = "조치 불필요"
SKIP = "건너뜀"


def _load_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, title, status, speakers, diarization, transcript, "
            "transcript_segments FROM meetings ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _json_obj(raw, default):
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _segments_of(row: dict) -> list[dict]:
    """저장된 segments 를 쓰되, 없으면 transcript 를 파싱한다.

    `transcript.get_segments` 를 쓰지 않는다 — 그쪽은 백필로 DB 에 쓰기 때문에
    dry-run 의 읽기 전용 보장이 깨진다.
    """
    stored = _json_obj(row.get("transcript_segments"), [])
    if isinstance(stored, list) and stored:
        return stored
    return parse(row.get("transcript") or "")


def _diar_seconds(diar: dict) -> dict:
    """diar 라벨별 총 발화 길이(초)."""
    totals: dict[str, float] = {}
    for label, segs in (diar or {}).items():
        total = 0.0
        for seg in segs or []:
            try:
                total += float(seg.get("end", 0)) - float(seg.get("start", 0))
            except (TypeError, ValueError):
                continue
        totals[label] = total
    return totals


def _representative(keys: list[str], diar_seconds: dict) -> str:
    """같은 이름을 가리키는 키들 중 대표 라벨. 총 발화 길이 최대, 동률이면 사전순 최소.

    (윗부분 '중복 이름 병합' 문단 참조 — 줄 배정을 추측하는 폐기 휴리스틱이 아니다.)
    """
    return max(sorted(keys), key=lambda k: (diar_seconds.get(k, 0.0), ))


def judge(row: dict) -> dict:
    """행 하나를 판정한다. DB 를 건드리지 않는다.

    반환: {verdict, reason, new_segments|None, detail}
    """
    job_id = row["id"]
    transcript = row.get("transcript") or ""
    speaker_map = _json_obj(row.get("speakers"), {}) or {}
    diar = _json_obj(row.get("diarization"), {}) or {}
    segments = _segments_of(row)
    labels = {s.get("label") for s in segments if s.get("label")}

    if not labels:
        return dict(verdict=NO_OP, reason="구조화된 화자 라벨이 없다(빈 transcript 또는 passthrough 전용).",
                    new_segments=None)

    # 이미 라벨 모델과 정합한 행 — 모든 segment 라벨이 **diar 라벨 공간**에 있다.
    #
    # 판정 기준을 "라벨이 speaker_map 키에 있는가"로 두면 안 된다. 레거시 행 중에는
    # 실명 키를 identity로 함께 들고 있는 것이 있어({"아빠":"아빠", "SPEAKER_00":"아빠"})
    # 그 기준으로는 정상으로 보이지만, `matches` 의 키는 항상 diar 라벨이므로
    # apply-match 는 여전히 422 다. 즉 **깨진 행을 정상으로 숨긴다.**
    # diar 가 없는 행(txt 업로드 등)은 대조할 실물이 없으므로 `SPEAKER_\d+` 형태를 공간으로 본다.
    if diar:
        label_space_ok = labels <= set(diar)
        space_desc = f"diarization 키 {sorted(diar)}"
    else:
        label_space_ok = all(re.fullmatch(r"SPEAKER_\d+", l) for l in labels)
        space_desc = "SPEAKER_XX 형태(diarization 없음)"
    if label_space_ok:
        return dict(verdict=NO_OP,
                    reason=f"모든 segment 라벨이 이미 라벨 공간 안에 있다 — {space_desc}.",
                    new_segments=None)

    if diar:
        outside = sorted(l for l in labels if l not in diar)
    else:
        outside = sorted(l for l in labels if not re.fullmatch(r"SPEAKER_\d+", l))
    detail = f"라벨 공간({space_desc}) 밖 라벨 {outside}"

    # --- 사전조건 3: 키 ⊆ diarization 키 -----------------------------------
    stray_keys = sorted(k for k in speaker_map if k not in diar)
    if stray_keys:
        return dict(verdict=SKIP,
                    reason=f"[사전조건3 불성립] speaker_map 키가 diarization 키의 부분집합이 아니다: "
                           f"{stray_keys} (diar 키: {sorted(diar) or '없음'}). "
                           f"이 키들은 되돌릴 diar 라벨이 없다. {detail}",
                    new_segments=None)

    # --- 사전조건 1: 값 유일성 → 단순 재키잉 / 병합 경로 분기 ---------------
    counts = Counter(speaker_map.values())
    duplicated = sorted(n for n, c in counts.items() if c > 1)
    merged_note = ""
    if duplicated:
        merged_note = (f"중복 이름 {duplicated} → 대표 라벨을 diar 총 발화 길이로 선정")

    # --- 사전조건 2: 값 집합 == 라벨 집합 ------------------------------------
    values = set(speaker_map.values())
    if values != labels:
        return dict(verdict=SKIP,
                    reason=f"[사전조건2 불성립] speaker_map 값 집합 != segment 라벨 집합. "
                           f"값에만 있음 {sorted(values - labels)}, 라벨에만 있음 {sorted(labels - values)}. {detail}",
                    new_segments=None)

    # --- 역맵 구성 (중복 이름은 대표 라벨로) --------------------------------
    diar_seconds = _diar_seconds(diar)
    by_name: dict[str, list[str]] = {}
    for key, name in speaker_map.items():
        by_name.setdefault(name, []).append(key)
    inverse = {name: _representative(keys, diar_seconds) for name, keys in by_name.items()}

    # --- 사전조건 4: 매핑 실패 라벨 0건 -------------------------------------
    unmapped = sorted(l for l in labels if l not in inverse)
    if unmapped:
        return dict(verdict=SKIP,
                    reason=f"[사전조건4 불성립] 되돌릴 라벨을 찾지 못한 segment 라벨 {unmapped}. {detail}",
                    new_segments=None)

    # --- 재키잉 -------------------------------------------------------------
    new_segments = []
    for seg in segments:
        label = seg.get("label")
        if label is None or label not in inverse:
            new_segments.append(dict(seg))
            continue
        new_seg = dict(seg)
        new_seg["label"] = inverse[label]
        new_segments.append(new_seg)

    # --- 핵심 안전장치: 사용자 화면이 한 글자도 바뀌지 않아야 한다 ----------
    rendered = render(new_segments, speaker_map)
    if rendered != transcript:
        return dict(verdict=SKIP,
                    reason="[안전장치 불성립] 재키잉 후 render() 결과가 현재 transcript 와 "
                           "바이트 동일하지 않다. 이 행에 대해 우리가 뭔가 잘못 알고 있는 것이므로 "
                           "쓰지 않는다. " + _first_diff(transcript, rendered),
                    new_segments=None)

    verdict = OK_MERGED if duplicated else OK_DIRECT
    reason = f"사전조건 4개 전부 성립 + render 바이트 동일. 재키잉 " + \
             ", ".join(f"{n}→{inverse[n]}" for n in sorted(labels))
    if merged_note:
        reason += f" ({merged_note})"
    return dict(verdict=verdict, reason=reason, new_segments=new_segments)


def _first_diff(a: str, b: str) -> str:
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return f"최초 불일치 offset={i}: 기존 {a[max(0,i-30):i+30]!r} vs 렌더 {b[max(0,i-30):i+30]!r}"
    return f"길이 불일치: 기존 {len(a)}자 vs 렌더 {len(b)}자"


def _write(db_path: Path, job_id: str, segments: list[dict]) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE meetings SET transcript_segments = ? WHERE id = ?",
            (json.dumps(segments, ensure_ascii=False), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="실제로 DB에 기록한다. 기본은 dry-run(읽기 전용).")
    ap.add_argument("--db", default=str(DEFAULT_DB), help=f"DB 경로 (기본: {DEFAULT_DB})")
    args = ap.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB 파일이 없다: {db_path}", file=sys.stderr)
        return 1

    mode = "WRITE" if args.write else "DRY-RUN (읽기 전용 — 아무것도 기록하지 않는다)"
    print(f"== 레거시 화자 라벨 마이그레이션 [{mode}] ==")
    print(f"DB: {db_path}\n")

    rows = _load_rows(db_path)
    tally = Counter()
    for row in rows:
        result = judge(row)
        verdict = result["verdict"]
        tally[verdict] += 1
        title = (row.get("title") or "").strip() or "(제목 없음)"
        print(f"[{verdict}] {row['id'][:8]}  status={row.get('status')}  {title[:40]}")
        print(f"    사유: {result['reason']}")
        if args.write and result["new_segments"] is not None:
            _write(db_path, row["id"], result["new_segments"])
            print(f"    → transcript_segments {len(result['new_segments'])}건 기록 완료")
        print()

    print("== 요약 ==")
    for key in (OK_DIRECT, OK_MERGED, NO_OP, SKIP):
        print(f"  {key}: {tally[key]}건")
    print(f"  전체: {len(rows)}건")
    if not args.write:
        print("\n(dry-run 이었다. 실제 반영하려면 --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
