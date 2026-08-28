#!/usr/bin/env python3
"""DEVGUIDE.md 섹션 6의 API 목록을 backend/app/main.py 에서 자동 생성한다.

DEVGUIDE 섹션 6은 손으로 관리하다 실제 코드와 어긋난 이력이 있다
(2026-08-29 시점 30개 누락). 이 스크립트로 코드에서 직접 뽑아 드리프트를 막는다.

사용법:
    python3 scripts/gen_api_table.py          # 차이만 확인 (CI/점검용, 변경 없음)
    python3 scripts/gen_api_table.py --write  # DEVGUIDE.md 갱신

DEVGUIDE.md 의 아래 두 마커 사이만 교체한다:
    <!-- API_TABLE:BEGIN -->
    <!-- API_TABLE:END -->
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "backend" / "app" / "main.py"
DEVGUIDE = ROOT / "DEVGUIDE.md"

BEGIN = "<!-- API_TABLE:BEGIN -->"
END = "<!-- API_TABLE:END -->"

DECORATOR = re.compile(r'^@app\.(get|post|put|patch|delete)\(\s*"([^"]+)"')


DEF_LINE = re.compile(r"\s*(async\s+)?def\s")


def extract_endpoints(src: str) -> list[tuple[str, str, str]]:
    """(메서드, 경로, 설명) 목록을 소스 등장 순서대로 반환한다.

    설명은 핸들러 docstring 첫 줄. 없으면 빈 문자열.
    """
    lines = src.splitlines()
    out: list[tuple[str, str, str]] = []

    for i, line in enumerate(lines):
        m = DECORATOR.match(line)
        if not m:
            continue
        method, path = m.group(1).upper(), m.group(2)

        # 데코레이터 다음의 def 줄을 찾는다 (사이에 다른 데코레이터가 있을 수 있음)
        j = i + 1
        while j < len(lines) and not DEF_LINE.match(lines[j]):
            if lines[j].startswith("@app."):  # 핸들러 없이 다음 라우트로 넘어감
                j = -1
                break
            j += 1

        desc = ""
        if 0 < j < len(lines):
            # 시그니처가 여러 줄일 수 있으므로 ':' 로 끝나는 줄까지 전진
            while j < len(lines) and not lines[j].rstrip().endswith(":"):
                j += 1
            if j + 1 < len(lines):
                doc = lines[j + 1].strip()
                if doc.startswith('"""'):
                    desc = doc[3:].split('"""')[0].strip()

        out.append((method, path, desc))

    return out


def existing_descriptions(guide: str) -> dict[tuple[str, str], str]:
    """현재 DEVGUIDE 표에 적힌 수기 설명을 (메서드, 경로) → 설명 으로 읽어둔다.

    코드에 docstring 이 없는 엔드포인트는 기존 설명을 그대로 살린다.
    """
    if BEGIN not in guide or END not in guide:
        return {}
    body = guide.split(BEGIN, 1)[1].split(END, 1)[0]
    found: dict[tuple[str, str], str] = {}
    for row in re.finditer(
        r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`([^`]+)`\s*\|(.*?)\|\s*$",
        body,
        re.M,
    ):
        found[(row.group(1), row.group(2))] = row.group(3).strip()
    return found


def render(endpoints: list[tuple[str, str, str]]) -> str:
    rows = [
        "| 메서드 | 경로 | 설명 |",
        "|--------|------|------|",
    ]
    for method, path, desc in endpoints:
        # 표 안에서 파이프는 이스케이프. 이미 이스케이프된 것을 다시 감싸지 않도록
        # 먼저 풀고 한 번만 적용한다(재실행 시 \\| 가 누적되는 것을 방지).
        safe_desc = desc.replace("\\|", "|").replace("|", "\\|")
        rows.append(f"| {method} | `{path}` | {safe_desc} |")
    return "\n".join(rows)


def main() -> int:
    write = "--write" in sys.argv

    guide = DEVGUIDE.read_text(encoding="utf-8")
    if BEGIN not in guide or END not in guide:
        print(f"오류: DEVGUIDE.md 에 {BEGIN} / {END} 마커가 없다.", file=sys.stderr)
        return 2

    endpoints = extract_endpoints(MAIN_PY.read_text(encoding="utf-8"))

    # docstring 이 없으면 기존 수기 설명을 유지한다
    prev = existing_descriptions(guide)
    endpoints = [
        (m, p, d or prev.get((m, p), "")) for m, p, d in endpoints
    ]
    table = render(endpoints)

    missing = [f"{m} {p}" for m, p, d in endpoints if not d]
    if missing:
        print(f"설명 없음 {len(missing)}건 (핸들러에 docstring 추가 권장):")
        for x in missing[:10]:
            print(f"  - {x}")
        if len(missing) > 10:
            print(f"  ... 외 {len(missing) - 10}건")

    head, rest = guide.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new_guide = f"{head}{BEGIN}\n{table}\n{END}{tail}"

    if new_guide == guide:
        print(f"최신 상태 (엔드포인트 {len(endpoints)}개)")
        return 0

    if write:
        DEVGUIDE.write_text(new_guide, encoding="utf-8")
        print(f"DEVGUIDE.md 갱신 완료 (엔드포인트 {len(endpoints)}개)")
        return 0

    print(f"DEVGUIDE.md 가 코드와 다르다 (엔드포인트 {len(endpoints)}개).")
    print("갱신하려면: python3 scripts/gen_api_table.py --write")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
