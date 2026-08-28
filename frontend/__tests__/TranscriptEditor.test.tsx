/**
 * TranscriptEditor names 초기화 테스트.
 *
 * PR #62: suggestedNames가 names 초기값에 반영.
 * PR #67: suggestedSpeakers 자동 채우기 제거 → 수동 적용/되돌리기 버튼 방식으로 변경.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import TranscriptEditor from '../components/TranscriptEditor'

// CategorySelect mock (fetch 의존성 제거)
vi.mock('../components/CategorySelect', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select data-testid="category-select" value={value} onChange={e => onChange(e.target.value)}>
      <option value="meeting">회의</option>
    </select>
  ),
}))

// fetch mock (audio 등)
global.fetch = vi.fn(() => Promise.resolve(new Response())) as any

const TRANSCRIPT = '[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다'

describe('TranscriptEditor names 초기화', () => {
  afterEach(() => cleanup())
  it('suggestedNames가 names 초기값에 반영되어야 한다', () => {
    render(
      <TranscriptEditor
        jobId="test-job"
        initialTranscript={TRANSCRIPT}
        initialSpeakers={['SPEAKER_00', 'SPEAKER_01']}
        suggestedNames={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
        onComplete={() => {}}
      />
    )

    // 모든 text input 찾기
    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const nameInputs = inputs.filter(i => i.type === 'text')

    // 디버그: 실제 value와 placeholder 출력
    console.log('Name inputs:', nameInputs.map(i => ({ value: i.value, placeholder: i.placeholder })))

    // suggestedNames가 value로 사전 입력되어야 함 (빈 문자열이면 버그)
    const values = nameInputs.map(i => i.value).filter(v => v !== '')
    expect(values.length).toBeGreaterThan(0)
    expect(values).toContain('김팀장')
    expect(values).toContain('이대리')
  })

  it('suggestedSpeakers가 있어도 초기값은 suggestedNames이고, 자동 적용되지 않아야 한다', () => {
    render(
      <TranscriptEditor
        jobId="test-job"
        initialTranscript={TRANSCRIPT}
        initialSpeakers={['SPEAKER_00', 'SPEAKER_01']}
        suggestedNames={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
        suggestedSpeakers={{
          SPEAKER_00: { name: '박과장', confidence: 0.9 },
        }}
        onComplete={() => {}}
      />
    )

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const nameInputs = inputs.filter(i => i.type === 'text')

    console.log('Test 2 inputs:', nameInputs.map(i => ({ value: i.value, placeholder: i.placeholder })))

    const values = nameInputs.map(i => i.value)

    // input value는 suggestedNames에서 온다 (suggestedSpeakers 자동 적용 안 됨)
    expect(values).toContain('김팀장')
    expect(values).toContain('이대리')

    // suggestedSpeakers 이름은 value가 아니라 placeholder에 나타난다
    const speaker00Input = nameInputs.find(i => i.placeholder === '박과장')
    expect(speaker00Input).toBeDefined()

    // '박과장'은 value에 없다 (수동 적용 전)
    expect(values).not.toContain('박과장')
  })
})
