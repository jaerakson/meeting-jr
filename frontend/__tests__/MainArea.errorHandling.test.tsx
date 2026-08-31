/**
 * F3 (PR C 2라운드, director 지시): 서버가 422를 반환하면 편집 모드가 유지되고
 * 로컬 상태(편집한 transcript·speakerMap)가 비워지지 않는다 — `handleSaveTranscript`·
 * `handleResummarize` 양쪽.
 *
 * 배경: PR C 초기 버전은 fetch 응답의 `res.ok`를 검사하지 않고 곧바로 편집 모드를
 * 닫고 로컬 상태를 비웠다 — 서버가 라벨 미해소로 422를 반환해 아무것도 저장되지
 * 않았는데도 UI는 성공한 것처럼 편집 화면을 닫아, 사용자가 방금 한 편집이
 * 조용히 사라졌다(차단 2의 피해를 키운 원인). 현재 구현(MainArea.tsx:247-260,
 * 264-289)은 `if (!res.ok) { alert(...); return }`로 이를 막아뒀다 — 이 테스트는
 * 그 방어를 잠근다.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import MainArea from '../components/MainArea'
import { Job } from '../types'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

Element.prototype.scrollIntoView = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

vi.mock('../components/AudioPlayer', () => ({
  default: () => <div data-testid="audio-player-stub" />,
}))
vi.mock('../components/SummaryPanel', () => ({
  default: () => <div data-testid="summary-panel-stub" />,
}))
vi.mock('../components/ParticipationChart', () => ({
  default: () => <div data-testid="participation-chart-stub" />,
}))
vi.mock('../components/SeriesSelect', () => ({
  default: () => <div data-testid="series-select-stub" />,
}))
vi.mock('../components/FollowupPanel', () => ({
  default: () => <div data-testid="followup-panel-stub" />,
}))

function makeJob(overrides: Partial<Job>): Job {
  return {
    id: 'job-a',
    title: '회의 A',
    filename: 'a.mp3',
    status: 'done',
    created_at: new Date().toISOString(),
    transcript: '[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디',
    speakers: { SPEAKER_00: '김팀장', SPEAKER_01: '이대리' },
    ...overrides,
  }
}

function renameFirstSpeaker(newName: string) {
  const nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
  fireEvent.click(nameSpans[0])
  const input = screen.getByPlaceholderText('새 이름')
  fireEvent.change(input, { target: { value: newName } })
  fireEvent.mouseDown(screen.getByText(/전체 변경/))
}

describe('MainArea — 서버 422 시 편집 모드·로컬 상태 보존 (F3)', () => {
  it('PATCH /transcript가 422를 반환하면 편집 모드가 유지되고 방금 한 편집이 사라지지 않는다', async () => {
    const job = makeJob({})
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})

    global.fetch = vi.fn((url: string) => {
      if (typeof url === 'string' && url.includes('/transcript') && !url.includes('jobs?')) {
        return Promise.resolve({
          ok: false,
          status: 422,
          json: () => Promise.resolve({ detail: '화자 라벨을 되돌릴 수 없습니다.' }),
        } as Response)
      }
      if (typeof url === 'string' && (url.includes('/related') )) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
    }) as unknown as typeof fetch

    render(
      <MainArea job={job} onJobsChange={() => {}} onNewRecording={() => {}} onOpenSidebar={() => {}} />
    )

    fireEvent.click(screen.getByText('편집'))
    renameFirstSpeaker('박부장')
    expect(screen.getByText('박부장')).toBeInTheDocument()

    fireEvent.click(screen.getAllByText('저장')[0])

    await waitFor(() => expect(alertSpy).toHaveBeenCalled())
    // alert에 서버 detail이 그대로 전달돼야 한다(성공한 척하지 않는다는 증거).
    expect(alertSpy.mock.calls[0][0]).toContain('화자 라벨을 되돌릴 수 없습니다')

    // 편집 모드가 여전히 유지돼야 한다 — "저장"/"취소" 도구모음이 그대로 있어야 한다.
    expect(screen.getAllByText('저장').length).toBeGreaterThan(0)
    expect(screen.getAllByText('취소').length).toBeGreaterThan(0)
    // 방금 한 편집(박부장)이 사라지지 않아야 한다 — 성공한 척 로컬 상태를 비웠다면
    // 편집 모드가 job.transcript로 재초기화돼 "김팀장"으로 되돌아간다.
    expect(screen.getByText('박부장')).toBeInTheDocument()
  })

  it('POST /finalize(재요약)가 422를 반환하면 모달·편집 모드가 유지되고 방금 한 편집이 사라지지 않는다', async () => {
    const job = makeJob({})
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})

    global.fetch = vi.fn((url: string) => {
      if (typeof url === 'string' && url.includes('/finalize')) {
        return Promise.resolve({
          ok: false,
          status: 422,
          json: () => Promise.resolve({ detail: '화자 라벨을 되돌릴 수 없습니다.' }),
        } as Response)
      }
      if (typeof url === 'string' && url.includes('/related')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
    }) as unknown as typeof fetch

    render(
      <MainArea job={job} onJobsChange={() => {}} onNewRecording={() => {}} onOpenSidebar={() => {}} />
    )

    fireEvent.click(screen.getByText('편집'))
    renameFirstSpeaker('박부장')

    fireEvent.click(await screen.findByText('재요약'))
    expect(await screen.findByText('재요약 카테고리 선택')).toBeInTheDocument()
    fireEvent.click(screen.getByText('재요약 실행'))

    await waitFor(() => expect(alertSpy).toHaveBeenCalled())
    expect(alertSpy.mock.calls[0][0]).toContain('화자 라벨을 되돌릴 수 없습니다')

    // 모달·편집 모드 둘 다 유지돼야 한다.
    expect(screen.getByText('재요약 카테고리 선택')).toBeInTheDocument()
    expect(screen.getAllByText('취소').length).toBeGreaterThan(0)
    // 방금 한 편집이 사라지지 않아야 한다.
    expect(screen.getByText('박부장')).toBeInTheDocument()
  })
})
