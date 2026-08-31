/**
 * TranscriptEditor 공백 관련 테스트.
 *
 * Bug 4: TranscriptEditor.serialize()는 .trim()하지만
 * handleSubmit()은 speaker_map에 trim 없이 저장한다.
 * speakers["SPEAKER_00"] === "김팀장 "인데 transcript는 "김팀장"이면
 * apply-match 정규식이 매칭되지 않는다.
 *
 * 검증: handleSubmit이 finalize API에 보내는 speaker_map에
 *       trim된 이름이 들어가는지 확인한다.
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import TranscriptEditor from '../components/TranscriptEditor'

// CategorySelect mock
vi.mock('../components/CategorySelect', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select data-testid="category-select" value={value} onChange={e => onChange(e.target.value)}>
      <option value="meeting">회의</option>
    </select>
  ),
}))

const TRANSCRIPT = '[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다'

describe('TranscriptEditor speaker_map trim', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    )
    global.fetch = fetchMock as any
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('handleSubmit이 finalize에 보내는 speaker_map 값에 공백이 없어야 한다', async () => {
    const onComplete = vi.fn()

    render(
      <TranscriptEditor
        jobId="trim-test"
        initialTranscript={TRANSCRIPT}
        initialSpeakers={['SPEAKER_00', 'SPEAKER_01']}
        suggestedNames={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
        onComplete={onComplete}
      />
    )

    // 이름 입력란 찾기
    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const nameInputs = inputs.filter(i => i.type === 'text')

    // SPEAKER_00 이름을 "김팀장 " (trailing space)로 변경
    fireEvent.change(nameInputs[0], { target: { value: '김팀장 ' } })

    // 제출 버튼 클릭
    const submitButton = screen.getByRole('button', { name: /문서 생성/i })
    fireEvent.click(submitButton)

    // finalize API 호출 검증
    await waitFor(() => {
      const finalizeCalls = fetchMock.mock.calls.filter(
        (call: any[]) => typeof call[0] === 'string' && call[0].includes('/finalize')
      )
      expect(finalizeCalls.length).toBeGreaterThan(0)

      const [, opts] = finalizeCalls[0]
      const body = JSON.parse(opts.body)

      // 핵심 검증: speaker_map 값에 공백이 없어야 한다
      for (const [key, value] of Object.entries(body.speaker_map)) {
        const strVal = String(value)
        expect(strVal).toBe(strVal.trim())
      }
    })
  })

  // [계약 뒤집힘, PR C] 이 테스트는 원래 "speaker_map의 값(이름)이 transcript 본문의
  // 화자 토큰과 일치해야 한다"를 단언했다 — 즉 이름이 본문에 구워진다는 옛 계약이다.
  // 커밋 2437583("TranscriptEditor finalize 계약 변경 — 이름을 본문에 굽지 않는다")로
  // handleSubmit이 `render(segments, {})`(빈 맵)를 보내도록 바뀌었으므로, 지금은 이름이
  // 무엇이든 본문에는 항상 원본 라벨(SPEAKER_00 등)만 남는다. 이름은 오직 speaker_map이
  // 나른다. 그래서 "값이 본문에 있는가"는 더 이상 성립하지 않는 계약이고, 구현이 틀린 게
  // 아니라 테스트가 폐기된 계약을 붙들고 있는 것이다.
  //
  // 새 계약에서 실제로 지켜야 하는 불변식은 축이 다르다: "speaker_map의 키 집합이
  // 본문에 남은 라벨 집합과 정확히 일치하는가"다. 이게 깨지면 finalize가 저장하는
  // transcript_segments.label과 speaker_map 키가 어긋나는 레거시 행(PR C가 근본 원인을
  // 제거한 바로 그 문제)이 새로 생긴다. 즉 이 테스트를 이 축으로 옮기면 합격 기준
  // ④(레거시 행이 더 생기지 않음)를 프론트 쪽에서 직접 지키는 감시자가 된다.
  //
  // ⚠️ 이름을 다시 본문에 굽는 방향으로 이 테스트를 되돌리지 말 것 — TranscriptEditor.tsx의
  // `render(segments, {})` 계약과 정면으로 모순되며, finalize identity 재키잉(abf0227에서
  // 삭제됨)을 요구하는 입력을 다시 만들어낸다.
  it('speaker_map의 키 집합이 본문(transcript)에 남은 라벨 집합과 일치해야 한다', async () => {
    const onComplete = vi.fn()

    render(
      <TranscriptEditor
        jobId="trim-test-2"
        initialTranscript={TRANSCRIPT}
        initialSpeakers={['SPEAKER_00', 'SPEAKER_01']}
        suggestedNames={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
        onComplete={onComplete}
      />
    )

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const nameInputs = inputs.filter(i => i.type === 'text')

    // 이름에 양쪽 공백 포함
    fireEvent.change(nameInputs[0], { target: { value: ' 박과장 ' } })

    // 제출
    const submitButton = screen.getByRole('button', { name: /문서 생성/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      const finalizeCalls = fetchMock.mock.calls.filter(
        (call: any[]) => typeof call[0] === 'string' && call[0].includes('/finalize')
      )
      expect(finalizeCalls.length).toBeGreaterThan(0)

      const [, opts] = finalizeCalls[0]
      const body = JSON.parse(opts.body)

      // 핵심 검증: 이름을 입력해도 본문에는 이름이 구워지지 않고 원본 라벨만 남는다.
      expect(body.transcript).not.toMatch(/박과장/)
      expect(body.transcript).toBe(TRANSCRIPT)

      // 본문(transcript)에 남은 라벨 집합
      const transcriptLabels = new Set(
        (body.transcript.match(/\[\d{2}:\d{2}\]\s+(.+?):/g) || []).map(
          (m: string) => m.replace(/\[\d{2}:\d{2}\]\s+/, '').replace(/:$/, '')
        )
      )

      // 새 계약: speaker_map의 키 집합 == 본문 라벨 집합 (값이 아니라 키가 축이다)
      expect(new Set(Object.keys(body.speaker_map))).toEqual(transcriptLabels)

      // speaker_map 값(이름)은 여전히 trim되어야 함 — 이건 옛 계약과 무관하게 유지되는 불변식
      expect(body.speaker_map['SPEAKER_00']).toBe('박과장')
    })
  })

  it('공백만 입력 시 speaker_map이 raw 라벨로 폴백해야 한다', async () => {
    const onComplete = vi.fn()

    render(
      <TranscriptEditor
        jobId="trim-test-ws"
        initialTranscript={TRANSCRIPT}
        initialSpeakers={['SPEAKER_00', 'SPEAKER_01']}
        suggestedNames={{ SPEAKER_00: '', SPEAKER_01: '이대리' }}
        onComplete={onComplete}
      />
    )

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const nameInputs = inputs.filter(i => i.type === 'text')

    // SPEAKER_00 이름을 공백만으로 입력
    fireEvent.change(nameInputs[0], { target: { value: '   ' } })

    const submitButton = screen.getByRole('button', { name: /문서 생성/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      const finalizeCalls = fetchMock.mock.calls.filter(
        (call: any[]) => typeof call[0] === 'string' && call[0].includes('/finalize')
      )
      expect(finalizeCalls.length).toBeGreaterThan(0)

      const [, opts] = finalizeCalls[0]
      const body = JSON.parse(opts.body)

      // 핵심: 공백만 입력 → trim → '' → raw 라벨(SPEAKER_00)로 폴백
      expect(body.speaker_map['SPEAKER_00']).toBe('SPEAKER_00')
      // 정상 입력은 trim된 값
      expect(body.speaker_map['SPEAKER_01']).toBe('이대리')
    })
  })
})
