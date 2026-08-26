/**
 * TDD 테스트: TranscriptEditor의 names 초기화 버그.
 *
 * 버그: suggestedNames가 names 초기값에 반영되지 않음.
 * suggestedSpeakers만 체크하고 suggestedNames는 무시됨 (line 53-63).
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

  it('suggestedSpeakers가 suggestedNames보다 우선해야 한다', () => {
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

    // SPEAKER_00: suggestedSpeakers 우선 → "박과장"
    expect(values).toContain('박과장')
    // SPEAKER_01: suggestedSpeakers 없음 → suggestedNames fallback → "이대리"
    expect(values).toContain('이대리')
    // "김팀장"은 suggestedSpeakers에 의해 덮어씌워져야 함
    expect(values).not.toContain('김팀장')
  })
})
