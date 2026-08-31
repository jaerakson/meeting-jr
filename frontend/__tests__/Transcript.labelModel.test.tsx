/**
 * components/Transcript.tsx 라벨 모델 회귀 테스트 (PR C, director 지시).
 *
 * 배경: PR C 이전 버전은 화자 이름을 바꿀 때 라인의 화자 필드(`l.speaker`)를
 * 직접 덮어써 라벨(정체성)이 소멸했다. 지금은 세그먼트의 `label`은 절대 바뀌지
 * 않고, 표시 이름은 `speakerMap`(label → name)에서만 갈아끼운다.
 *
 * 검증은 항상 **최종 산출물**(onTranscriptChange가 실제로 내보내는 payload)로 한다 —
 * 내부 state가 아니다. PR B에서 중간 산출물(main.py의 렌더된 스크립트 파일)은
 * 올바른데 최종 입력(summarizer.py가 다시 치환한 Claude 프롬프트)이 깨진 결함을
 * 바로 이 방식(mock으로 최종 산출물을 캡처)으로 잡았다.
 *
 * PR C 2라운드(2026-09) 확정 계약: onTranscriptChange가 내보내는 `{ transcript, speakerMap }`에서
 * `transcript`는 항상 라벨 그대로다(saveEdit/saveSpeakerAll/reassignLine 모두 render(seg, {})로
 * 렌더한다 — 이름을 본문에 굽지 않는다). 표시 이름은 `speakerMap`(label → name)이 별도로 나른다.
 * 그래서 "이름이 반영됐는지" 검증은 `speakerMap`에서, "라벨(정체성)이 보존/이동됐는지" 검증은
 * `transcript`에서 한다.
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

    // transcript는 항상 라벨 그대로다(이름을 굽지 않는다) — 이름은 speakerMap에서 확인한다.
    let payload = onTranscriptChange.mock.calls.at(-1)![0]
    expect(payload.speakerMap['SPEAKER_00']).toBe('김팀장')
    expect(payload.transcript.match(/SPEAKER_00:/g)?.length).toBe(3)
    expect(payload.transcript).not.toContain('김팀장:')

    // 2차 개명: 같은 라벨(SPEAKER_00, 지금은 "김팀장"으로 표시)을 "박부장"으로.
    // 라벨이 진짜 보존됐다면 line.label은 여전히 "SPEAKER_00"이라 speakerMap의
    // 같은 키가 다시 갱신된다. 라벨이 과거에 "김팀장" 문자열로 덮어써졌다면
    // speakerMap에 새 키("김팀장")가 잘못 생겨 SPEAKER_00 키가 갱신되지 않는다.
    nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 0, '박부장')

    payload = onTranscriptChange.mock.calls.at(-1)![0]
    expect(payload.speakerMap['SPEAKER_00']).toBe('박부장')
    expect(payload.speakerMap['김팀장']).toBeUndefined()
    expect(payload.transcript.match(/SPEAKER_00:/g)?.length).toBe(3)
    expect(payload.transcript).toContain('SPEAKER_01: 끼어들기')
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

    // 맞바꾸기가 완성됐다: "아빠" 라벨은 "엄마"로, "엄마" 라벨은 "아빠"로 표시돼야 한다.
    // 붕괴(전부 한 이름으로 수렴)됐다면 두 키 중 하나가 사라지거나 같은 값으로 겹친다.
    const payload = onTranscriptChange.mock.calls.at(-1)![0]
    expect(payload.speakerMap['아빠']).toBe('엄마')
    expect(payload.speakerMap['엄마']).toBe('아빠')
    // transcript는 라벨 그대로 보존된다(이름 미반영) — 구조(라벨) 자체는 안 바뀌었다.
    expect(payload.transcript.match(/아빠:/g)?.length).toBe(2)
    expect(payload.transcript.match(/엄마:/g)?.length).toBe(1)
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
    const output = onTranscriptChange.mock.calls.at(-1)![0].transcript
    expect(output).toContain('수정됨')
    // raw(옛 2-스페이스 원문)를 그대로 뱉으면 편집이 조용히 사라진다 — 그 문자열이
    // 결과에 남아있으면 안 된다.
    expect(output).not.toBe(transcript)
    expect(output).not.toContain('안녕하세요\n')
  })

  // [보강, qa-c3] "이 줄을 다른 화자로 재지정"(reassignLine) — PR C(54089fb)에서 새로
  // 도입됐지만 이 파일에 커버리지가 없었다. "이 항목만 이름 변경"을 대체한 핵심 UX라
  // §10에 명시적으로 문서화돼 있는데도 회귀 감시자가 없던 공백.
  it('이 줄을 다른 화자로 재지정하면 그 줄만 다른 라벨의 정체성을 갖는다', () => {
    const transcript =
      '[00:00] SPEAKER_00: 첫번째\n' +
      '[00:05] SPEAKER_01: 끼어들기\n' +
      '[00:10] SPEAKER_00: 두번째'
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

    // idx 2 = "[00:10] SPEAKER_00: 두번째" 줄의 이름을 클릭해 편집 UI를 연다.
    const nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    fireEvent.click(nameSpans[2])

    // "이 줄만 다른 화자로:" 목록에서 SPEAKER_01 버튼을 클릭 — 재지정.
    const reassignButton = screen.getByText('SPEAKER_01', { selector: 'button' })
    fireEvent.mouseDown(reassignButton)

    const output = onTranscriptChange.mock.calls.at(-1)![0].transcript
    // 재지정된 줄은 SPEAKER_01 라벨로 렌더되고, 원래 SPEAKER_01 줄과 합쳐 2건이 된다.
    expect(output.match(/SPEAKER_01:/g)?.length).toBe(2)
    // SPEAKER_00에는 idx 0 한 줄만 남는다.
    expect(output.match(/SPEAKER_00:/g)?.length).toBe(1)
    expect(output).toContain('SPEAKER_00: 첫번째')
    expect(output).toContain('SPEAKER_01: 두번째')

    // 재지정 후 SPEAKER_01을 "이대리"로 전체 개명하면, 재지정으로 넘어간 줄도
    // 같은 라벨(정체성)이므로 speakerMap에서 함께 바뀌어야 한다 — reassignLine이
    // 값(텍스트)이 아니라 라벨(정체성) 자체를 옮겼다는 증거.
    const refreshedSpans = screen.getAllByTitle('클릭하여 이름 변경')
    fireEvent.click(refreshedSpans[1]) // idx 1 = 원래 SPEAKER_01 줄("끼어들기")
    const renameInput = screen.getByPlaceholderText('새 이름')
    fireEvent.change(renameInput, { target: { value: '이대리' } })
    fireEvent.mouseDown(screen.getByText(/전체 변경/))

    const finalPayload = onTranscriptChange.mock.calls.at(-1)![0]
    expect(finalPayload.speakerMap['SPEAKER_01']).toBe('이대리')
    // transcript는 여전히 라벨 그대로다 — 재지정으로 옮겨간 줄과 원래 줄 모두 SPEAKER_01.
    expect(finalPayload.transcript.match(/SPEAKER_01:/g)?.length).toBe(2)
    expect(finalPayload.transcript).toContain('SPEAKER_00: 첫번째')
  })
})
