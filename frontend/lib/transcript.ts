/**
 * transcript 문자열 ↔ 구조화 세그먼트 변환.
 *
 * 화자 매핑 라벨 기반 리팩터링 PR C의 핵심 산출물. `backend/app/transcript.py`의
 * `parse`/`render` 계약을 그대로 포팅한다 — 프론트 파서 4개·시리얼라이저 2개가
 * 각자 조금씩 다른 방언으로 흩어져 있던 것이 5라운드 연속 버그의 원인이었다
 * (설계 문서: docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md).
 *
 * ## 세그먼트 표현 — backend/app/transcript.py와 동일
 *   { start: number|null, end: number|null, label: string|null, text: string, raw?: string }
 *   - start: 발화 시작 초. 구조화 실패 줄은 null.
 *   - end:   항상 null. 문자열 파싱만으로는 알 수 없다(diarization 쪽 세그먼트에서만 채워짐 — 프론트는 다루지 않는다).
 *   - label: 화자 라벨(SPEAKER_XX 또는 실명). 구조화 실패 줄은 null.
 *   - text:  발화 본문. 구조화 실패 줄은 원본 줄 전체.
 *   - raw:   정규형 렌더가 원본 줄과 바이트 동일하지 **않을 때만** 존재하는 선택 키.
 *
 * ## 강제 불변식
 *   render(parse(s)) === s   (바이트 동일)
 *
 * ## 프론트 기존 파서 4개 대비 — 채택한 방언과 폐기 근거
 * (TranscriptEditor.tsx / Transcript.tsx / MainArea.tsx / app/shared/[token]/page.tsx)
 * - **라벨: `.+?` 채택.** `TranscriptEditor.tsx`만 `\S+`를 쓰고 있었는데, 공백 포함
 *   실명("김 팀장")이 재편집 시 파싱에서 통째로 빠지는 결함이었다. 나머지 3개는 이미 `.+?`.
 * - **분(minute): `\d+` 채택(무제한).** 4개 전부 `\d{2}`(정확히 2자리)였다 — 100분 초과
 *   회의에서 `[123:45]` 같은 줄을 그냥 놓친다. 백엔드 PR A가 이미 고친 것과 동일한 결함.
 * - **매칭 실패 줄: 버리지 않고 passthrough 보존.** 4개 전부 `flatMap`(빈 배열 반환)이나
 *   `continue`로 완전히 삭제하고 있었다 — 가장 큰 계약 위반. 저장 시 malformed 줄이
 *   조용히 사라지는 데이터 유실로 이어진다.
 * - **text는 trim하지 않는다(원문 보존).** `TranscriptEditor.tsx`만 `.trim()`을 해서
 *   원문 공백이 있는 텍스트의 라운드트립을 깨뜨리고 있었다.
 * - 구분자(`\s` 개수)·빈 발언 2단 매칭 등 나머지는 전부 백엔드 정규식을 그대로 따른다.
 */

export interface TranscriptSegment {
  start: number | null
  end: number | null
  label: string | null
  text: string
  raw?: string
}

// 1단: 표준 줄 `[MM:SS] LABEL: TEXT` — backend _STRICT와 동일
const STRICT = /^\[(\d+):(\d{2})\]\s(.+?):\s(.*)$/
// 2단: 콜론에서 줄이 끝나는 빈 발언만. 1단이 실패했을 때만 시도한다 — backend _EMPTY와 동일.
const EMPTY = /^\[(\d+):(\d{2})\]\s(.+?):$/

function canonicalLine(start: number | null, display: string, text: string): string {
  const total = start ?? 0
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `[${mm}:${ss}] ${display}: ${text}`
}

/**
 * transcript 문자열을 줄 단위로 파싱해 세그먼트 목록을 만든다.
 * 빈 문자열은 []. 그 외에는 세그먼트 개수 == 원본 줄 개수(무손실).
 */
export function parse(transcript: string): TranscriptSegment[] {
  if (!transcript) return []

  const segments: TranscriptSegment[] = []
  for (const line of transcript.split('\n')) {
    let m = line.match(STRICT)
    let textIsEmptyForm = false
    if (!m) {
      m = line.match(EMPTY)
      textIsEmptyForm = !!m
    }

    if (!m) {
      // 구조 파싱 실패 — 원본 줄을 그대로 보존한다(버리지 않는다).
      segments.push({ start: null, end: null, label: null, text: line })
      continue
    }

    // 라벨 앞뒤 공백은 제거한다(내부 공백은 보존 — "김 팀장"은 그대로).
    const label = m[3].trim()
    if (!label) {
      segments.push({ start: null, end: null, label: null, text: line })
      continue
    }

    const minutes = parseInt(m[1], 10)
    const seconds = parseInt(m[2], 10)
    const text = textIsEmptyForm ? '' : m[4]
    const start = minutes * 60 + seconds

    const seg: TranscriptSegment = { start, end: null, label, text }
    if (canonicalLine(start, label, text) !== line) {
      seg.raw = line
    }
    segments.push(seg)
  }

  return segments
}

/**
 * 세그먼트 목록을 transcript 문자열로 되돌린다.
 * - label이 null인 passthrough 세그먼트는 speakerMap과 무관하게 text를 원문 그대로 출력한다.
 * - raw는 표시 이름이 라벨과 같을 때만 쓴다. 치환이 실제로 일어나면 정규형으로 렌더한다.
 */
export function render(segments: TranscriptSegment[], speakerMap?: Record<string, string>): string {
  const lines: string[] = []
  for (const seg of segments) {
    const label = seg.label
    const text = seg.text ?? ''
    if (label === null) {
      lines.push(text)
      continue
    }

    const display = (speakerMap?.[label] ?? '').trim() || label
    if (seg.raw !== undefined && display === label) {
      lines.push(seg.raw)
    } else {
      lines.push(canonicalLine(seg.start, display, text))
    }
  }
  return lines.join('\n')
}

/** 라벨의 표시 이름을 render()와 동일한 규칙으로 계산한다. label이 null이면 빈 문자열. */
export function displayName(label: string | null, speakerMap?: Record<string, string>): string {
  if (label === null) return ''
  return (speakerMap?.[label] ?? '').trim() || label
}

/** 세그먼트의 start(초)를 `MM:SS` 문자열로 포맷한다. canonicalLine과 동일 규칙. */
export function formatTimestamp(seconds: number | null): string {
  const total = seconds ?? 0
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(Math.floor(total % 60)).padStart(2, '0')
  return `${mm}:${ss}`
}

/**
 * 세그먼트의 text(또는 label)를 바꿀 때 쓰는 헬퍼. `raw`를 명시적으로 제거한다.
 *
 * render()의 raw 우선순위 규칙(DEVGUIDE §10 "raw 필드 규칙", PR B에서 확정)은
 * `display(=speakerMap 적용 결과) === label` 일 때만 raw를 그대로 출력한다.
 * 즉 화자 이름을 안 바꾼 세그먼트는 raw가 남아있어도 안전하다 — 하지만 **text 자체를
 * 편집**하면 raw(= parse() 시점의 원본 줄 전체)가 그 편집 이전 내용을 그대로 담고 있어서,
 * display가 label과 같은 한(=이름을 안 바꿨다면) render()가 옛 원문(raw)을 그대로
 * 뱉어버려 방금 한 텍스트 편집이 조용히 사라진다. label을 다른 라벨로 재지정할 때도
 * 마찬가지로 그 줄의 raw는 이제 "다른 화자 소유의 원본 줄"이라 의미가 없다.
 * 그래서 text/label을 바꾸는 모든 지점에서 raw를 함께 지워 정규형 렌더를 강제한다.
 */
export function withoutRaw(seg: TranscriptSegment, patch: Partial<TranscriptSegment>): TranscriptSegment {
  const { raw, ...rest } = seg
  return { ...rest, ...patch }
}
