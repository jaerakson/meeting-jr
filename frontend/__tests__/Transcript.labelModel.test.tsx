/**
 * components/Transcript.tsx 라벨 모델 회귀 테스트 (PR C, director 지시).
 *
 * 배경: PR C 이전 버전은 화자 이름을 바꿀 때 라인의 화자 필드(`l.speaker`)를
 * 직접 덮어써 라벨(정체성)이 소멸했다. 지금은 세그먼트의 `label`은 절대 바뀌지
 * 않고, 표시 이름은 `speakerMap`(label → name)에서만 갈아끼운다.
 *
 * 검증은 항상 **최종 산출물**(onTranscriptChange가 실제로 내보내는 문자열)로 한다 —
 * 내부 state가 아니다. PR B에서 중간 산출물(main.py의 렌더된 스크립트 파일)은
 * 올바른데 최종 입력(summarizer.py가 다시 치환한 Claude 프롬프트)이 깨진 결함을
 * 바로 이 방식(mock으로 최종 산출물을 캡처)으로 잡았다.
 *
 * 단언을 통과시키려고 약화하지 말 것.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import Transcript from '../components/Transcript'

afterEach(() => {
  cleanup()
})

function renameByIndex(nameSpans: HTMLElement[], idx: number, newName: string) {
  fireEvent.click(nameSpans[idx])
  const input = screen.getByPlaceholderText('새 이름')
  fireEvent.change(input, { target: { value: newName } })
  const applyAllButton = screen.getByText(/전체 변경/)
  fireEvent.mouseDown(applyAllButton)
}

describe('Transcript 라벨 모델 — 최종 산출물 검증', () => {
  it('전체 변경 후에도 라벨이 보존된다 — 같은 라벨을 두 번 연속 개명해도 전체 개수가 유지된다', () => {
    const transcript =
      '[00:00] SPEAKER_00: 첫번째\n' +
      '[00:05] SPEAKER_01: 끼어들기\n' +
      '[00:10] SPEAKER_00: 두번째\n' +
      '[00:15] SPEAKER_00: 세번째'
    const onTranscriptChange = vi.fn()

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        onTranscriptChange={onTranscriptChange}
      />
    )

    // 1차 개명: SPEAKER_00 → 김팀장 (전체 변경)
    let nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 0, '김팀장')

    let output = onTranscriptChange.mock.calls.at(-1)![0] as string
    expect(output.match(/김팀장:/g)?.length).toBe(3)
    expect(output).not.toContain('SPEAKER_00:')

    // 2차 개명: 같은 라벨(SPEAKER_00, 지금은 "김팀장"으로 표시)을 "박부장"으로.
    // 라벨이 진짜 보존됐다면 line.label은 여전히 "SPEAKER_00"이라 이번에도
    // 3개 전부가 다시 바뀐다. 라벨이 과거에 "김팀장" 문자열로 덮어써졌다면
    // speakerMap에 새 키("김팀장")가 잘못 생겨 일부만 바뀌거나 개수가 어긋난다.
    nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 0, '박부장')

    output = onTranscriptChange.mock.calls.at(-1)![0] as string
    expect(output.match(/박부장:/g)?.length).toBe(3)
    expect(output).not.toContain('김팀장')
    expect(output).toContain('SPEAKER_01: 끼어들기')
  })

  it('연속 개명(맞바꾸기)에서 두 화자가 병합되지 않는다', () => {
    const transcript =
      '[00:00] 아빠: 첫번째 발언\n' +
      '[00:05] 엄마: 두번째 발언\n' +
      '[00:10] 아빠: 세번째 발언'
    const onTranscriptChange = vi.fn()

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        onTranscriptChange={onTranscriptChange}
      />
    )

    // 1단계: "아빠" 라벨을 "엄마"로 개명
    let nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 0, '엄마') // idx 0 = 라벨 "아빠"

    // 2단계: 원래 "엄마" 라벨(현재도 "엄마"로 표시 중, idx 1)을 "아빠"로 개명 — 맞바꾸기 완성
    nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 1, '아빠') // idx 1 = 라벨 "엄마" (아직 개명 전이라 원래 이름 그대로 표시 중)

    const output = onTranscriptChange.mock.calls.at(-1)![0] as string
    // 맞바꾸기가 완성됐다: 원래 "아빠"였던 라인 2개는 "엄마"로, 원래 "엄마"였던 라인 1개는 "아빠"로.
    // 붕괴(전부 한 이름으로 수렴)됐다면 이 두 카운트 중 하나가 0이 되거나 3:0으로 쏠린다.
    expect(output.match(/엄마:/g)?.length).toBe(2)
    expect(output.match(/아빠:/g)?.length).toBe(1)
  })

  it('텍스트 편집 후 raw가 제거돼 편집 내용이 무시되지 않는다', () => {
    // "[00:00]  SPEAKER_00: 안녕하세요" — ']' 다음 공백이 2칸이라 정규형과 바이트가
    // 달라 parse()가 raw를 채운다(라벨 앞뒤 공백 방어, PR A 문서화된 결함과 동일 축).
    const transcript = '[00:00]  SPEAKER_00: 안녕하세요'
    const onTranscriptChange = vi.fn()

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        onTranscriptChange={onTranscriptChange}
      />
    )

    // 텍스트 클릭 → 인라인 편집 인풋 노출 → 새 텍스트 입력 → Enter로 저장
    const textEl = screen.getByText('안녕하세요')
    fireEvent.click(textEl)
    const editInput = screen.getByDisplayValue('안녕하세요')
    fireEvent.change(editInput, { target: { value: '안녕하세요 수정됨' } })
    fireEvent.keyDown(editInput, { key: 'Enter' })

    expect(onTranscriptChange).toHaveBeenCalled()
    const output = onTranscriptChange.mock.calls.at(-1)![0] as string
    expect(output).toContain('수정됨')
    // raw(옛 2-스페이스 원문)를 그대로 뱉으면 편집이 조용히 사라진다 — 그 문자열이
    // 결과에 남아있으면 안 된다.
    expect(output).not.toBe(transcript)
    expect(output).not.toContain('안녕하세요\n')
  })
})
