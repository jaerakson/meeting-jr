/**
 * TDD 테스트: 화자 이름 클릭 → 첫 발언 이동 기능.
 *
 * 그룹 1: Transcript 컴포넌트 — 화자 이름 클릭 시 onTimeClick 호출
 * 그룹 2: ParticipationChart — 범례 화자 이름 클릭 시 onSpeakerClick 호출
 * 그룹 3: 경계면 — identity mapping 케이스
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act, waitFor } from '@testing-library/react'
import Transcript from '../components/Transcript'
import ParticipationChart from '../components/ParticipationChart'

// jsdom에서 scrollIntoView 미지원 — stub
Element.prototype.scrollIntoView = vi.fn()

// recharts의 ResponsiveContainer mock (jsdom에서 width/height 0 문제 해결)
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts')
  return {
    ...(actual as object),
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  }
})

afterEach(() => cleanup())

// ---------------------------------------------------------------------------
// 그룹 1: Transcript 컴포넌트 — 화자 이름 클릭
// ---------------------------------------------------------------------------

describe('Transcript — 화자 이름 클릭 점프', () => {
  it('SPEAKER_XX 형식 이름 클릭 시 해당 화자의 첫 발언 시각으로 onTimeClick 호출', () => {
    const onTimeClick = vi.fn()
    const transcript =
      '[00:00] SPEAKER_00: 안녕하세요\n[00:15] SPEAKER_01: 네\n[00:30] SPEAKER_00: 오늘 주제는'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // SPEAKER_00 이름 텍스트를 찾아 클릭
    const speakerNames = screen.getAllByText('SPEAKER_00')
    fireEvent.click(speakerNames[0])

    // SPEAKER_00의 첫 발언 시각(0초)으로 호출
    expect(onTimeClick).toHaveBeenCalledWith(0)

    onTimeClick.mockClear()

    // SPEAKER_01 클릭 → 첫 발언 시각(15초)
    const speaker01 = screen.getByText('SPEAKER_01')
    fireEvent.click(speaker01)
    expect(onTimeClick).toHaveBeenCalledWith(15)
  })

  it('실명 매핑된 형식에서 이름 클릭 시 첫 발언 시각으로 onTimeClick 호출', () => {
    const onTimeClick = vi.fn()
    const transcript =
      '[00:00] 김팀장: 안녕하세요\n[00:15] 이대리: 네\n[00:30] 김팀장: 오늘 주제는'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // "김팀장" 클릭 → 첫 발언(0초)
    const kimNames = screen.getAllByText('김팀장')
    fireEvent.click(kimNames[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)
  })

  it('같은 화자 반복 클릭 시 현재 위치 이후 다음 발언으로 순환 이동', () => {
    const onTimeClick = vi.fn()
    const transcript =
      '[00:00] SPEAKER_00: 첫번째\n[00:15] SPEAKER_01: 응답\n[00:30] SPEAKER_00: 두번째\n[01:00] SPEAKER_00: 세번째'

    // currentTime=0 (첫번째 발언 재생 중)
    const { rerender } = render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // 첫 클릭: SPEAKER_00의 첫 발언(0초)
    const speakerNames = screen.getAllByText('SPEAKER_00')
    fireEvent.click(speakerNames[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)

    onTimeClick.mockClear()

    // 같은 화자 다시 클릭 (currentTime이 0~14 사이) → 다음 발언(30초)으로
    fireEvent.click(speakerNames[0])
    expect(onTimeClick).toHaveBeenCalledWith(30)
  })

  it('편집 모드에서는 이름 클릭이 점프가 아닌 이름 편집을 트리거', () => {
    const onTimeClick = vi.fn()
    const transcript = '[00:00] SPEAKER_00: 안녕하세요\n[00:15] SPEAKER_01: 네'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={true}
      />
    )

    // 편집 모드에서 화자 이름 클릭
    const speakerNames = screen.getAllByText('SPEAKER_00')
    fireEvent.click(speakerNames[0])

    // onTimeClick이 호출되지 않아야 함 (편집 모드에서는 이름 변경 UI)
    expect(onTimeClick).not.toHaveBeenCalled()
  })

  it('txt 업로드 케이스 — 일반 이름 형식에서도 클릭 점프 동작', () => {
    const onTimeClick = vi.fn()
    const transcript =
      '[00:00] 참석자1: 안녕하세요\n[00:10] 참석자2: 반갑습니다\n[00:20] 참석자1: 시작하죠'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // "참석자1" 클릭 → 첫 발언(0초)
    const names = screen.getAllByText('참석자1')
    fireEvent.click(names[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)
  })

  it('회의 전환(transcript 변경) 후 첫 클릭은 첫 발언으로 이동해야 한다', () => {
    const onTimeClick = vi.fn()
    const transcript1 =
      '[00:00] SPEAKER_00: 회의A 첫발언\n[00:15] SPEAKER_01: 응답\n[00:30] SPEAKER_00: 회의A 두번째'

    const { rerender } = render(
      <Transcript
        transcript={transcript1}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // 회의 A에서 SPEAKER_00 클릭
    const names1 = screen.getAllByText('SPEAKER_00')
    fireEvent.click(names1[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)

    onTimeClick.mockClear()

    // 회의 B로 전환 (다른 transcript)
    const transcript2 =
      '[00:00] SPEAKER_00: 회의B 첫발언\n[00:20] SPEAKER_00: 회의B 두번째'

    rerender(
      <Transcript
        transcript={transcript2}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // 회의 B에서 SPEAKER_00 첫 클릭 → 반드시 첫 발언(0초)으로 가야 함
    // (회의 A의 lastClickedSpeaker 상태가 남아있으면 두번째(20초)로 잘못 이동)
    const names2 = screen.getAllByText('SPEAKER_00')
    fireEvent.click(names2[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)
  })
})

// ---------------------------------------------------------------------------
// 그룹 2: ParticipationChart — 화자 이름 클릭
// ---------------------------------------------------------------------------

describe('ParticipationChart — 범례 화자 이름 클릭', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url: string) => {
      if (typeof url === 'string' && url.includes('/participation')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              speakers: [
                {
                  label: 'SPEAKER_00',
                  display_name: '김팀장',
                  total_seconds: 30,
                  percentage: 50,
                  turn_count: 3,
                  avg_turn_seconds: 10,
                },
                {
                  label: 'SPEAKER_01',
                  display_name: '이대리',
                  total_seconds: 30,
                  percentage: 50,
                  turn_count: 2,
                  avg_turn_seconds: 15,
                },
              ],
              total_duration: 60,
            }),
        } as Response)
      }
      return Promise.resolve(new Response())
    }) as typeof fetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('차트 하단 범례의 화자 이름 클릭 시 onSpeakerClick 호출', async () => {
    const onSpeakerClick = vi.fn()

    await act(async () => {
      render(<ParticipationChart jobId="test-job" onSpeakerClick={onSpeakerClick} />)
    })

    // 데이터 로드 대기
    await waitFor(() => {
      expect(screen.getByText(/김팀장/)).toBeInTheDocument()
    })

    // 범례에서 "김팀장" 텍스트가 포함된 span 클릭
    const legendItem = screen.getByText(/김팀장/)
    fireEvent.click(legendItem)

    expect(onSpeakerClick).toHaveBeenCalledWith('김팀장')
  })

  it('차트 범례 같은 화자 반복 클릭 시 매번 동일한 이름으로 onSpeakerClick 호출 (첫 발언 고정)', async () => {
    const onSpeakerClick = vi.fn()

    await act(async () => {
      render(<ParticipationChart jobId="test-job" onSpeakerClick={onSpeakerClick} />)
    })

    await waitFor(() => {
      expect(screen.getByText(/김팀장/)).toBeInTheDocument()
    })

    const legendItem = screen.getByText(/김팀장/)

    // 첫 클릭
    fireEvent.click(legendItem)
    expect(onSpeakerClick).toHaveBeenCalledWith('김팀장')

    // 두번째 클릭 — 동일하게 '김팀장'으로 호출 (순환 아님, 첫 발언 고정)
    fireEvent.click(legendItem)
    expect(onSpeakerClick).toHaveBeenCalledTimes(2)
    expect(onSpeakerClick).toHaveBeenLastCalledWith('김팀장')
  })
})

// ---------------------------------------------------------------------------
// 그룹 3: 경계면 — identity mapping
// ---------------------------------------------------------------------------

describe('Transcript — identity mapping 경계면', () => {
  it('identity mapping (speakers={아빠: 아빠}) 에서도 이름 클릭 점프 정상 동작', () => {
    const onTimeClick = vi.fn()
    const transcript =
      '[00:00] 아빠: 안녕\n[00:10] 엄마: 그래\n[00:20] 아빠: 다음은'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={onTimeClick}
        editable={false}
      />
    )

    // "아빠" 클릭 → 첫 발언(0초)
    const names = screen.getAllByText('아빠')
    fireEvent.click(names[0])
    expect(onTimeClick).toHaveBeenCalledWith(0)
  })
})
