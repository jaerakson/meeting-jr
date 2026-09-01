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

바꾸는 것: `transcript_segments` 의 `label` — 실명 → 그 이름을 가리키는 diar 라벨. **그것뿐이다.**
바꾸지 않는 것: `transcript` 문자열, `speakers`(중복 이름 병합 경로에서도 건드리지 않는다 —
`_merge_duplicate_names` docstring 참조), `diarization`, 그 외 모든 컬럼. `raw` 키도 그대로 둔다.

표시 이름은 speaker_map 이 나르므로 **사용자 화면은 한 글자도 바뀌지 않아야 정상이다.**
이것을 희망이 아니라 **검사**로 강제한다 — 재키잉한 segments 를 `render(new_segments,
speaker_map)` 한 결과가 현재 transcript 와 **바이트 동일**하지 않으면 그 행은 쓰지 않는다.
안 맞으면 우리가 이 행에 대해 뭔가 잘못 알고 있는 것이다.

## 판정 순서 — 라벨 공간 판정이 사전조건보다 **먼저**다

먼저 "손댈 필요가 있는가"를 판정하고, 없으면 **조치불필요**로 분류하고 사전조건은 검사하지 않는다.

    기준: 세그먼트 라벨이 **diar 라벨 공간** 안에 있는가.
    (apply-match 의 `matches` 키가 항상 diar 라벨이므로, 이것이 실제로 요구되는 성질이다.)

"라벨이 speaker_map 키에 있는가"로 판별하면 **깨진 행을 정상으로 숨긴다** — 실명 키를
identity 로 함께 들고 있는 레거시 행(`{"손주환":"손주환"}`)이 그 기준으로는 통과하지만
apply-match 는 여전히 422 다. 순서도 중요하다 — 사전조건 ②를 먼저 걸면, 매핑되지 않은
diar 라벨이 본문에 남아 있을 뿐인 **정상 행**(`5ab8e338`)이 "건너뜀"으로 잘못 보고된다.

## 행별 사전조건 (하나라도 불성립이면 그 행 **전체**를 건너뛴다 — 부분 복구 금지)

    ① speaker_map 값이 유일할 것            (중복이면 스킵이 아니라 아래 병합 경로로 분기)
    ② speaker_map 값 집합 == segment 라벨 집합
    ③ speaker_map 키 ⊆ diarization 키
    ④ 매핑 실패 라벨 0건                    (모든 실명 라벨이 라벨로 되돌려질 것)

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

## `--write` 실행 조건 — **백엔드 서버를 중지하고 실행할 것**

판정은 읽은 시점의 `transcript` 를 근거로 한다. 서버가 떠 있으면 읽기~쓰기 사이의 편집이
낡은 근거로 덮어써질 수 있다. `_write` 에 낙관적 잠금(`WHERE ... AND transcript = ?`)을
두었지만 그건 **감지**일 뿐 **방지가 아니다** — 되돌릴 수 없는 조작이므로 감지만으로는
부족하다. 실행 전 DB 백업도 권장한다.
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
OK_DIRECT = "자동복구"
OK_MERGED = "병합복구"
NO_OP = "조치불필요"
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


def _merge_duplicate_names(speaker_map: dict, diar: dict) -> tuple[dict, list[str], str]:
    """speaker_map 값이 중복이면 이름마다 대표 라벨 하나만 남긴다.

    이 대표 라벨 선택은 PR B에서 삭제한 overlap 휴리스틱과 다르다.
    삭제한 것은 "어느 줄이 누구 발화인지"를 추측하는 방식이었다.
    이것은 사용자가 이미 선언한 이름 하나에 대해, 그 이름이 실려 있던
    여러 diarization 클러스터 중 대표를 고르는 결정적 규칙일 뿐이다.
    줄 배정은 추측하지 않는다 — 줄의 라벨은 역맵으로 유일하게 결정되며,
    결정되지 않는 줄이 하나라도 있으면(조건 ④) 그 행 전체를 건너뛴다.

    대표 = diarization 총 발화 길이(sum(end-start)) 최대. 동률이면 키 문자열 정렬로
    tie-break 하여 같은 입력이면 항상 같은 출력이 나온다.

    ## 비대표 키는 speaker_map 에 **남긴다** — 지우지 말 것

    여기서 만드는 축소 map 은 **역맵 계산용 중간값이고 DB 에 쓰지 않는다.**
    `--write` 는 `transcript_segments` 만 기록하고 `speakers` 는 건드리지 않는다.

    **지우면 안 되는 이유**: `participation` 의 diar 경로(main.py:2268~)는 **`diar_data`
    키를 순회**하며 `display = (speaker_map.get(label) or "").strip() or label` 로 이름을
    찾는다. 비대표 키를 map 에서 지우면 그 클러스터가 참여도 화면에 **raw `SPEAKER_XX` 로
    표시된다**(실측: `6c5acaa2` 66초/5%, `5938f69c` 145초/3%).
    **이 스크립트는 "화면은 한 글자도 안 바뀐다"를 약속하고 실행된다.** 소수 구간이라도
    그 약속을 깨므로 받아들일 수 없다.

    **남겨도 안전한 이유**: transcript 라벨은 대표 라벨로 통일되므로 본문 렌더에 비대표 키가
    등장하지 않고, 표시 이름 중복은 PR B 가 이미 허용하기로 한 상태이며, apply-match 는 키가
    diar 라벨이라 값이 중복이어도 동작한다. **"안 쓰이는 키"로 보고 정리하지 말 것.**

    반환: (역맵 계산용 축소 map — **쓰기 대상 아님**, 중복이던 이름들, 사람이 읽을 메모)
    """
    counts = Counter(speaker_map.values())
    duplicated = sorted(n for n, c in counts.items() if c > 1)
    if not duplicated:
        return dict(speaker_map), [], ""

    seconds = _diar_seconds(diar)
    by_name: dict[str, list[str]] = {}
    for key, name in speaker_map.items():
        by_name.setdefault(name, []).append(key)

    reduced: dict[str, str] = {}
    notes: list[str] = []
    for name, keys in by_name.items():
        rep = _representative(keys, seconds)
        reduced[rep] = name
        if len(keys) > 1:
            dropped = [k for k in sorted(keys) if k != rep]
            notes.append(
                f"{name}: {sorted(keys)} → 대표 {rep}"
                f"(총 {seconds.get(rep, 0.0):.1f}초), 비대표 {dropped} 는 map 에 유지"
            )
    return reduced, duplicated, "중복 이름 병합 — " + " / ".join(notes)


def judge(row: dict) -> dict:
    """행 하나를 판정한다. DB 를 건드리지 않는다.

    판정 순서(사양): 레거시 서명 → (중복이면) 병합 → 조건 ②③④ → 재키잉 → 안전장치.
    **조건 검사보다 레거시 서명이 먼저다.** 순서를 바꾸면, 매핑되지 않은 diar 라벨이 본문에
    남아 있을 뿐인 정상 행(실측 `5ab8e338`)이 조건 ②에 걸려 "건너뜀"으로 잘못 보고된다.

    반환: {verdict, reason, new_segments, new_speaker_map}
    """
    transcript = row.get("transcript") or ""
    speaker_map = _json_obj(row.get("speakers"), {}) or {}
    diar = _json_obj(row.get("diarization"), {}) or {}
    segments = _segments_of(row)
    labels = {s.get("label") for s in segments if s.get("label")}

    none = dict(new_segments=None, new_speaker_map=None)

    # --- 레거시 서명: 손댈 필요가 있는가 -------------------------------------
    # 기준은 **"세그먼트 라벨이 diar 라벨 공간 안에 있는가"** 다 — apply-match 가 실제로
    # 요구하는 성질이 그것이기 때문이다(`matches` 의 키는 항상 diar 라벨이다).
    #
    # "라벨이 speaker_map 키에 있는가" 로 판별하면 안 된다: 레거시 행 중에는 실명 키를
    # identity 로 함께 들고 있는 것이 있어({"손주환":"손주환", ...}) 그 기준으로는 정상으로
    # 보이지만 apply-match 는 여전히 422 다 — **깨진 행을 정상으로 숨긴다.**
    #
    # diar 가 없는 행은 대조할 실물이 없으므로 `SPEAKER_\d+` 형태를 공간으로 본다.
    # **이 형태 폴백이 잘못된 쓰기로 이어질 수는 없다**: diar 가 비어 있으면 조건③의
    # `stray` 가 반드시 비어있지 않고(speaker_map 이 비면 조건②에서 걸린다) 항상 SKIP 이다.
    # 즉 폴백은 **보고 분류에만** 영향한다. "형태 판별이 남아있다"는 이유로 고치지 말 것 —
    # 고치려면 위의 두 문단이 말하는 성질을 유지하는지 먼저 확인해야 한다.
    if diar:
        in_label_space = labels <= set(diar)
        space_desc = f"diarization 키 {sorted(diar)}"
        outside = sorted(l for l in labels if l not in diar)
    else:
        in_label_space = all(re.fullmatch(r"SPEAKER_\d+", l) for l in labels)
        space_desc = "SPEAKER_XX 형태(diarization 없음)"
        outside = sorted(l for l in labels if not re.fullmatch(r"SPEAKER_\d+", l))

    if in_label_space:
        return dict(verdict=NO_OP,
                    reason=f"모든 segment 라벨이 이미 라벨 공간 안에 있다 — {space_desc}.",
                    **none)

    detail = f"라벨 공간({space_desc}) 밖 라벨 {outside}"

    # --- 조건 ①: 값 유일. 중복이면 병합 경로로 분기(스킵이 아니다) -----------
    working_map, duplicated, merge_note = _merge_duplicate_names(speaker_map, diar)

    # --- 조건 ②: 값 집합 == 라벨 집합 ---------------------------------------
    values = set(working_map.values())
    if values != labels:
        return dict(verdict=SKIP,
                    reason=f"[조건② 불성립] speaker_map 값 집합 != segment 라벨 집합. "
                           f"값에만 있음 {sorted(values - labels)}, 라벨에만 있음 {sorted(labels - values)}. {detail}",
                    **none)

    # --- 조건 ③: 키 ⊆ diarization 키 ----------------------------------------
    stray = sorted(k for k in working_map if k not in diar)
    if stray:
        return dict(verdict=SKIP,
                    reason=f"[조건③ 불성립] speaker_map 키가 diarization 키의 부분집합이 아니다: {stray} "
                           f"(diar 키: {sorted(diar) or '없음'}). 이 키들은 되돌릴 diar 라벨이 없다. {detail}",
                    **none)

    # --- 역맵 + 조건 ④: 매핑 실패 라벨 0건 -----------------------------------
    inverse = {name: key for key, name in working_map.items()}
    unmapped = sorted(l for l in labels if l not in inverse)
    if unmapped:
        return dict(verdict=SKIP,
                    reason=f"[조건④ 불성립] 되돌릴 라벨을 찾지 못한 segment 라벨 {unmapped}. {detail}",
                    **none)

    # --- 재키잉 (raw 키는 있던 그대로 둔다) ----------------------------------
    new_segments = []
    for seg in segments:
        new_seg = dict(seg)
        label = seg.get("label")
        if label is not None and label in inverse:
            new_seg["label"] = inverse[label]
        new_segments.append(new_seg)

    # --- 핵심 안전장치: 사용자 화면이 한 글자도 바뀌지 않아야 한다 -----------
    # 축소 map 이 아니라 **DB 에 실제로 남을 speaker_map** 으로 렌더해 검사한다.
    # (동명 키는 같은 이름을 가리키므로 결과는 같지만, 런타임이 쓰는 값으로 재는 편이 정직하다.)
    rendered = render(new_segments, speaker_map)
    if rendered != transcript:
        return dict(verdict=SKIP,
                    reason="[안전장치 불성립] 재키잉 후 render() 결과가 현재 transcript 와 바이트 동일하지 "
                           "않다. 이 행에 대해 우리가 뭔가 잘못 알고 있는 것이므로 쓰지 않는다. "
                           + _first_diff(transcript, rendered),
                    **none)

    reason = "조건 ②③④ 성립 + render 바이트 동일. 재키잉 " + \
             ", ".join(f"{n}→{inverse[n]}" for n in sorted(labels))
    if merge_note:
        reason += f". {merge_note}"
    # new_speaker_map 은 항상 None 이다 — speakers 컬럼은 쓰지 않는다(위 병합 함수 docstring).
    return dict(verdict=OK_MERGED if duplicated else OK_DIRECT,
                reason=reason,
                new_segments=new_segments,
                new_speaker_map=None)


def _first_diff(a: str, b: str) -> str:
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return f"최초 불일치 offset={i}: 기존 {a[max(0,i-30):i+30]!r} vs 렌더 {b[max(0,i-30):i+30]!r}"
    return f"길이 불일치: 기존 {len(a)}자 vs 렌더 {len(b)}자"


def _write(db_path: Path, job_id: str, segments: list[dict], expected_transcript: str) -> bool:
    """재키잉된 segments 만 기록한다. 기록했으면 True.

    `transcript` 도 `speakers` 도 쓰지 않는다 — 안전장치가 이미 바이트 동일을 보장했고,
    두 컬럼을 건드리지 않는 것이 "화면은 한 글자도 안 바뀐다"는 약속의 가장 강한 보장이다.
    (`speakers` 를 건드리면 안 되는 이유는 `_merge_duplicate_names` docstring 참조.)

    **낙관적 잠금**: 판정은 읽은 시점의 `transcript` 를 근거로 하므로, 읽기~쓰기 사이에
    누가 편집하면 낡은 근거로 덮어쓰게 된다. `WHERE ... AND transcript = ?` 로 쓰기 직전
    재검증하고 `rowcount == 0` 이면 쓰지 않는다.

    **이건 방지가 아니라 감지다.** 되돌릴 수 없는 조작이므로 감지만으로는 부족하다 —
    실행 조건은 **서버 중지**다(모듈 docstring·`--help` 참조).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "UPDATE meetings SET transcript_segments = ? WHERE id = ? AND transcript = ?",
            (json.dumps(segments, ensure_ascii=False), job_id, expected_transcript),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog="[실행 조건] --write 는 **백엔드 서버를 중지한 상태에서** 실행할 것. "
               "낙관적 잠금은 동시 편집을 감지만 하고 방지하지 못한다. DB 백업 권장.",
    )
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
    stale = 0
    for row in rows:
        result = judge(row)
        verdict = result["verdict"]
        tally[verdict] += 1
        title = (row.get("title") or "").strip() or "(제목 없음)"
        print(f"[{verdict}] {row['id'][:8]}  status={row.get('status')}  {title[:40]}")
        print(f"    사유: {result['reason']}")
        if args.write and result["new_segments"] is not None:
            if _write(db_path, row["id"], result["new_segments"], row.get("transcript") or ""):
                print(f"    → transcript_segments {len(result['new_segments'])}건 기록 완료"
                      f" (transcript·speakers 는 건드리지 않음)")
            else:
                stale += 1
                print("    → **기록하지 않음**: 판정에 쓴 transcript 와 현재 DB 값이 다르다. "
                      "읽은 뒤 이 행이 편집됐다(서버가 떠 있었을 가능성). "
                      "서버를 중지하고 다시 실행하세요.")
        print()

    print("== 요약 ==")
    for key in (OK_DIRECT, OK_MERGED, NO_OP, SKIP):
        print(f"  {key}: {tally[key]}건")
    print(f"  전체: {len(rows)}건")
    if stale:
        print(f"  ** 낙관적 잠금으로 기록하지 않은 행: {stale}건 — 서버를 중지하고 재실행하세요 **")
    if not args.write:
        print("\n(dry-run 이었다. 실제 반영하려면 --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
