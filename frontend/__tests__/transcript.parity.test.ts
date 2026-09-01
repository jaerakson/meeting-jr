/**
 * frontend/lib/transcript.ts ↔ backend/app/transcript.py 계약 일치 테스트 (PR C).
 *
 * 배경 (director 지시, 최우선 과제): PR C는 프론트 파서 4벌 + 시리얼라이저 2벌을
 * frontend/lib/transcript.ts 한 곳으로 통합하고, backend/app/transcript.py의
 * parse()/render() 계약을 그대로 포팅했다고 주장한다. "포팅했다"는 주장과 "실제로
 * 같은 입력에 같은 출력을 낸다"는 사실은 다르다.
 *
 * 케이스는 backend/frontend 양쪽에 따로 적지 않고 레포 루트의
 * `tests/fixtures/transcript_parity_cases.json` 하나를 양쪽이 읽는다 — 갈라짐을
 * 구조적으로 막는다. `expected_round_trip`/`expected_with_map`은 backend/app/
 * transcript.py(이 리팩터링의 기준 구현)를 실제로 실행해 얻은 golden 값이다
 * (수기 계산 아님) — `backend/tests/test_transcript_frontend_parity.py`가 backend
 * 자신의 드리프트를 잡고, 이 파일이 frontend가 그 golden 값과 실제로 일치하는지를
 * 검증하는 계약 대조축이다.
 *
 * 왕복(`render(parse(s)) === s`)만으로는 안 잡히는 부류가 있다 — PR A에서 라벨 공백
 * 결함이 왕복 성립 + 치환 실패로 전부 초록이었다. 그래서 각 케이스마다 왕복과
 * 치환(speakerMap 적용 결과)을 반드시 짝으로 확인한다.
 *
 * 단언을 통과시키려고 약화하지 말 것.
 */

import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { parse, render } from '../lib/transcript'

interface ParityCase {
  id: string
  description: string
  transcript: string
  speaker_map: Record<string, string>
  expected_round_trip: string
  expected_with_map: string
  segment_count: number
}

const FIXTURE_PATH = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'transcript_parity_cases.json')

function loadCases(): ParityCase[] {
  const raw = fs.readFileSync(FIXTURE_PATH, 'utf-8')
  return JSON.parse(raw).cases
}

const CASES = loadCases()

describe('frontend/lib/transcript.ts — backend 계약 일치 (golden fixture)', () => {
  it('픽스처에 필수 5개 카테고리가 전부 있다', () => {
    const ids = new Set(CASES.map(c => c.id))
    const required = [
      'standard_lines',
      'label_with_internal_space',
      'over_100_minutes',
      'empty_utterance_and_blank_display_name',
      'passthrough_mixed_failure_lines',
    ]
    for (const id of required) {
      expect(ids.has(id)).toBe(true)
    }
  })

  for (const c of CASES) {
    describe(`[${c.id}] ${c.description}`, () => {
      it('세그먼트 개수가 backend와 일치한다', () => {
        const segments = parse(c.transcript)
        expect(segments.length).toBe(c.segment_count)
      })

      it('왕복(render(parse(s)) === s)이 backend golden 값과 일치한다', () => {
        const segments = parse(c.transcript)
        const roundTrip = render(segments)
        expect(roundTrip).toBe(c.expected_round_trip)
      })

      it('치환(speakerMap 적용) 결과가 backend golden 값과 일치한다', () => {
        const segments = parse(c.transcript)
        const withMap = render(segments, c.speaker_map)
        expect(withMap).toBe(c.expected_with_map)
      })
    })
  }

  it('passthrough 줄은 speakerMap과 무관하게 치환되지 않는다 (본문 오염 봉쇄)', () => {
    const c = CASES.find(x => x.id === 'passthrough_mixed_failure_lines')!
    const segments = parse(c.transcript)
    const passthroughTexts = segments.filter(s => s.label === null).map(s => s.text)
    expect(passthroughTexts).toContain('메모: SPEAKER_00 관련 논의 계속')

    const rendered = render(segments, c.speaker_map)
    expect(rendered).toContain('메모: SPEAKER_00 관련 논의 계속')
  })

  it('공백/빈 표시 이름은 라벨을 유지한다 (이름 삭제 방지)', () => {
    const c = CASES.find(x => x.id === 'empty_utterance_and_blank_display_name')!
    const segments = parse(c.transcript)
    const rendered = render(segments, c.speaker_map)
    expect(rendered).toContain('SPEAKER_00:')
    expect(rendered).not.toContain('   :')
  })
})
