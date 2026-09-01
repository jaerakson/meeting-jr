/**
 * 회귀 테스트 (PR C, director 리뷰): 재요약이 편집 모드를 거치지 않고 호출되는 경로에서
 * speaker_map이 job.speakers로 전송돼야 한다 — {}(빈 맵)로 덮여쓰면 회의의 모든 화자
 * 이름이 영구 소실된다.
 *
 * 배경: MainArea의 `localSpeakerMap`이 `useState<Record<string,string>>({})`(비-null
 * 초기값)이었을 때 `localSpeakerMap ?? job.speakers ?? {}`의 `??`가 절대 발동하지 않아
 * job.speakers로 폴백하지 못했다. 재현 가능한 실제 경로: 재요약 모달을 연 상태에서
 * (모달은 job 전환 시에도 닫히지 않는다 — 별도 결함이지만 이 테스트의 전제는 아니다)
 * 사이드바로 다른 회의로 전환하면, `[job?.id]` 이펙트가 `localSpeakerMap`을 초기값으로
 * 리셋한다. 새 회의는 `handleStartEditTranscript`(=편집 진입)를 거친 적이 없으므로
 * 시드된 적이 없다 — 이 상태에서 "재요약 실행"을 누르면 새 회의의 speaker_map이
 * `{}`로 서버에 전송된다.
 *
 * 수정: `localSpeakerMap`을 `Record<string,string> | null`로 바꿔 "편집으로 갱신된 적
 * 없음"을 null로 표현한다 — 그래야 `??`가 의도대로 job.speakers로 폴백한다.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import MainArea from '../components/MainArea'
import { Job } from '../types'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// jsdom에서 scrollIntoView 미지원 — Transcript가 활성 라인으로 스크롤 시도 시 필요.
Element.prototype.scrollIntoView = vi.fn()

// MainArea가 useRouter()를 호출한다 — RootLayout 없이 단독 렌더하므로 목이 필요하다.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

// 무거운 자식 컴포넌트(자체 fetch·recharts 등)는 이 테스트의 관심사가 아니므로 스텁으로 대체한다.
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
    transcript: '[00:00] SPEAKER_00: 안녕하세요',
    speakers: { SPEAKER_00: '김팀장' },
    ...overrides,
  }
}

describe('MainArea — 재요약 speaker_map 회귀', () => {
  it('재요약 모달이 열린 채로 다른 회의로 전환되면(편집 미진입), 새 회의의 speaker_map은 job.speakers로 전송된다', async () => {
    const jobA = makeJob({ id: 'job-a', speakers: { SPEAKER_00: '김팀장' } })
    const jobB = makeJob({
      id: 'job-b',
      title: '회의 B',
      transcript: '[00:00] SPEAKER_00: 다른 회의',
      speakers: { SPEAKER_00: '박부장', SPEAKER_01: '이대리' },
    })

    const finalizeCalls: { url: string; body: any }[] = []

    global.fetch = vi.fn((url: string, init?: RequestInit) => {
      if (typeof url === 'string' && url.includes('/finalize')) {
        finalizeCalls.push({ url, body: init?.body ? JSON.parse(init.body as string) : null })
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
      }
      if (typeof url === 'string' && url.includes('/related')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) } as Response)
      }
      if (typeof url === 'string' && url.includes('/notes')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
      }
      // /api/categories 등 나머지는 빈 배열로 응답 — 이 테스트는 카테고리 선택에 관여하지 않는다.
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
    }) as unknown as typeof fetch

    const { rerender } = render(
      <MainArea
        job={jobA}
        onJobsChange={() => {}}
        onNewRecording={() => {}}
        onOpenSidebar={() => {}}
      />
    )

    // 회의 A에서 편집 진입 → 재요약 모달 오픈 (모달은 편집 진입 경로로만 열 수 있다).
    fireEvent.click(screen.getByText('편집'))
    fireEvent.click(await screen.findByText('재요약'))
    expect(await screen.findByText('재요약 카테고리 선택')).toBeInTheDocument()

    // 회의 B로 전환 — 모달이 열린 채로 job prop만 바뀐다(사이드바에서 다른 회의를 고른 상황을 재현).
    // 회의 B는 handleStartEditTranscript(편집 진입)를 거친 적이 없다 — localSpeakerMap이 시드되지 않았다.
    rerender(
      <MainArea
        job={jobB}
        onJobsChange={() => {}}
        onNewRecording={() => {}}
        onOpenSidebar={() => {}}
      />
    )

    // 모달은 [job?.id] 이펙트로 닫히지 않는다 — "재요약 실행"이 여전히 눌린다.
    const runButton = await screen.findByText('재요약 실행')
    fireEvent.click(runButton)

    await waitFor(() => expect(finalizeCalls.length).toBe(1))
    expect(finalizeCalls[0].url).toContain('job-b')
    // 핵심 단언: speaker_map이 {}(전멸)가 아니라 회의 B의 job.speakers 그대로여야 한다.
    expect(finalizeCalls[0].body.speaker_map).toEqual(jobB.speakers)
  })

  // [qa-c4, director 지시 — F1 독립 검토] localSpeakerMap 리셋 지점은 세 곳이다:
  // ① job 전환([job?.id] 이펙트, 위 테스트가 커버) ② 편집 취소 ③ 저장 성공.
  // 위 테스트 하나만으로는 ②③이 `null` 대신 `{}`로 되돌아가도 잡히지 않는다(직접
  // 되돌려 확인함) — 부분 수정으로도 통과하는 판별력 없는 안전망이 될 뻔했다.
  // 아래 두 테스트가 ②③을 각각 잠근다.

  function mockFetchWithFinalizeCapture(finalizeCalls: { url: string; body: any }[], extra?: (url: string) => Response | null) {
    return vi.fn((url: string, init?: RequestInit) => {
      const extraRes = extra?.(url)
      if (extraRes) return Promise.resolve(extraRes)
      if (typeof url === 'string' && url.includes('/finalize')) {
        finalizeCalls.push({ url, body: init?.body ? JSON.parse(init.body as string) : null })
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
      }
      if (typeof url === 'string' && url.includes('/related')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) } as Response)
      }
      if (typeof url === 'string' && url.includes('/notes')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)
    }) as unknown as typeof fetch
  }

  it('[리셋 지점 ②] 재요약 모달을 연 채로 편집을 취소해도, "재요약 실행"의 speaker_map은 job.speakers로 전송된다', async () => {
    const jobA = makeJob({ id: 'job-a', speakers: { SPEAKER_00: '김팀장', SPEAKER_01: '이대리' } })
    const finalizeCalls: { url: string; body: any }[] = []
    global.fetch = mockFetchWithFinalizeCapture(finalizeCalls)

    render(
      <MainArea job={jobA} onJobsChange={() => {}} onNewRecording={() => {}} onOpenSidebar={() => {}} />
    )

    fireEvent.click(screen.getByText('편집'))
    fireEvent.click(await screen.findByText('재요약'))
    expect(await screen.findByText('재요약 카테고리 선택')).toBeInTheDocument()

    // 편집 도구모음의 "취소"(handleCancelEditTranscript)를 누른다. 모달 자체의 "취소"
    // (모달 닫기 전용, showResummarizeModal만 건드림)와 텍스트가 같아 getAllByText로
    // 구분한다 — 도구모음 쪽이 JSX상 모달보다 먼저 렌더되므로 index 0.
    const cancelButtons = screen.getAllByText('취소')
    fireEvent.click(cancelButtons[0])

    // 모달은 편집 취소로 닫히지 않는다(showResummarizeModal은 handleCancelEditTranscript가
    // 건드리지 않는다) — "재요약 실행"이 여전히 눌린다.
    const runButton = await screen.findByText('재요약 실행')
    fireEvent.click(runButton)

    await waitFor(() => expect(finalizeCalls.length).toBe(1))
    expect(finalizeCalls[0].body.speaker_map).toEqual(jobA.speakers)
  })

  it('[리셋 지점 ③] 저장 성공 직후 모달이 열린 채로 "재요약 실행"을 눌러도 speaker_map은 job.speakers로 전송된다', async () => {
    const jobA = makeJob({ id: 'job-a', speakers: { SPEAKER_00: '김팀장', SPEAKER_01: '이대리' } })
    const finalizeCalls: { url: string; body: any }[] = []
    const patchCalls: { url: string }[] = []
    global.fetch = mockFetchWithFinalizeCapture(finalizeCalls, (url) => {
      if (typeof url === 'string' && url.includes('/transcript')) {
        patchCalls.push({ url })
        return { ok: true, json: () => Promise.resolve({}) } as Response
      }
      return null
    })

    render(
      <MainArea job={jobA} onJobsChange={() => {}} onNewRecording={() => {}} onOpenSidebar={() => {}} />
    )

    fireEvent.click(screen.getByText('편집'))
    fireEvent.click(await screen.findByText('재요약'))
    expect(await screen.findByText('재요약 카테고리 선택')).toBeInTheDocument()

    // 도구모음의 "저장"(handleSaveTranscript)을 누른다 — PATCH 성공 시
    // isEditingTranscript/localSpeakerMap이 리셋된다. 모달은 그대로 열려 있다.
    // 메모 섹션에도 동명의 "저장" 버튼이 있어 getAllByText로 구분한다 — 도구모음 쪽이
    // DOM상 먼저 렌더되므로 index 0.
    fireEvent.click(screen.getAllByText('저장')[0])
    await waitFor(() => expect(patchCalls.length).toBe(1))

    const runButton = await screen.findByText('재요약 실행')
    fireEvent.click(runButton)

    await waitFor(() => expect(finalizeCalls.length).toBe(1))
    expect(finalizeCalls[0].body.speaker_map).toEqual(jobA.speakers)
  })

  it('[반대 케이스] 편집 중 실제로 이름을 바꾼 경우, 재요약은 job.speakers가 아니라 방금 바꾼 이름을 전송한다', async () => {
    // ??  폴백이 반대 방향으로 과잉 동작해(즉 localSpeakerMap이 있는데도 job.speakers로
    // 덮어써) 방금 한 편집이 사라지는 회귀가 없는지 확인한다.
    const jobA = makeJob({ id: 'job-a', speakers: { SPEAKER_00: '김팀장', SPEAKER_01: '이대리' } })
    const finalizeCalls: { url: string; body: any }[] = []
    global.fetch = mockFetchWithFinalizeCapture(finalizeCalls)

    render(
      <MainArea job={jobA} onJobsChange={() => {}} onNewRecording={() => {}} onOpenSidebar={() => {}} />
    )

    fireEvent.click(screen.getByText('편집'))

    // Transcript 내부 UI로 SPEAKER_00의 이름을 "박부장"으로 실제로 바꾼다("전체 변경").
    const nameSpans = await screen.findAllByTitle('클릭하여 이름 변경')
    fireEvent.click(nameSpans[0])
    const input = screen.getByPlaceholderText('새 이름')
    fireEvent.change(input, { target: { value: '박부장' } })
    fireEvent.mouseDown(screen.getByText(/전체 변경/))

    fireEvent.click(await screen.findByText('재요약'))
    fireEvent.click(await screen.findByText('재요약 실행'))

    await waitFor(() => expect(finalizeCalls.length).toBe(1))
    // 방금 바꾼 이름이 반영돼야 한다 — job.speakers(옛 "김팀장")로 되돌아가면 안 된다.
    expect(finalizeCalls[0].body.speaker_map.SPEAKER_00).toBe('박부장')
    // 건드리지 않은 SPEAKER_01은 시드된 그대로 보존돼야 한다(부분 편집이 나머지를 지우면 안 됨).
    expect(finalizeCalls[0].body.speaker_map.SPEAKER_01).toBe('이대리')
  })
})
