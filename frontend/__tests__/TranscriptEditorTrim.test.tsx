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

  it('serialize된 transcript의 화자 이름과 speaker_map 값이 일치해야 한다', async () => {
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

      // transcript 내 화자 이름 추출
      const transcriptNames = new Set(
        (body.transcript.match(/\[\d{2}:\d{2}\]\s+(.+?):/g) || []).map(
          (m: string) => m.replace(/\[\d{2}:\d{2}\]\s+/, '').replace(/:$/, '')
        )
      )

      // speaker_map의 모든 값이 transcript 화자 토큰과 일치해야 한다
      for (const [key, value] of Object.entries(body.speaker_map)) {
        const strVal = String(value)
        if (strVal) {
          expect(transcriptNames.has(strVal)).toBe(true)
        }
      }

      // speaker_map 값도 trim 되어야 함
      expect(body.speaker_map['SPEAKER_00']).toBe('박과장')
    })
  })
})
