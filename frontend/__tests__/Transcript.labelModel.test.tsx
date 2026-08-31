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

// jsdom에서 scrollIntoView 미지원 — 비편집 모드 렌더 시 활성 라인 스크롤 시도에 필요.
Element.prototype.scrollIntoView = vi.fn()

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

// ---------------------------------------------------------------------------
// F1 — 차단 1 회귀 잠금 (director 지시, 2026-09-01): 비편집 모드에서 speakerMap 미적용.
//
// 수정 전에는 `toViewLines`가 `name: editable ? resolveDisplayName(...) : (seg.label ?? '')`로
// 비편집 모드에서 speakers prop을 아예 무시하고 라벨을 그대로 표시했다(완료 화면이
// SPEAKER_00 raw 라벨을 노출). 이 테스트가 없으면 누군가 그 editable 분기를 되돌려도
// 나머지 vitest 스위트가 전부 초록불이라 회귀를 잡지 못한다.
// ---------------------------------------------------------------------------

describe('Transcript — 비편집 모드 표시 계약 (차단 1 회귀 잠금)', () => {
  it('editable=false여도 speakers prop으로 표시 이름을 렌더한다 — 라벨 그대로 노출하지 않는다', () => {
    const transcript =
      '[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable={false}
        speakers={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
      />
    )

    // 표시 이름이 렌더돼야 한다.
    expect(screen.getByText('김팀장')).toBeInTheDocument()
    expect(screen.getByText('이대리')).toBeInTheDocument()
    // 라벨이 그대로 화면에 남아있으면 안 된다(회귀 시 이 부분이 다시 보인다).
    expect(screen.queryByText('SPEAKER_00')).not.toBeInTheDocument()
    expect(screen.queryByText('SPEAKER_01')).not.toBeInTheDocument()
  })

  it('speakers에 없는 라벨은 라벨 자체로 폴백한다(displayName과 동일 규칙)', () => {
    const transcript = '[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable={false}
        speakers={{ SPEAKER_00: '김팀장' }}
      />
    )

    expect(screen.getByText('김팀장')).toBeInTheDocument()
    // SPEAKER_01은 매핑이 없으므로 라벨 그대로 폴백 렌더돼야 한다.
    expect(screen.getByText('SPEAKER_01')).toBeInTheDocument()
  })

  it('speakers prop이 없으면(undefined) 라벨 그대로 폴백한다', () => {
    const transcript = '[00:00] SPEAKER_00: 안녕하세요'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable={false}
      />
    )

    expect(screen.getByText('SPEAKER_00')).toBeInTheDocument()
  })
})

// [F2, qa-c4] 편집 진입 시 speakerMap이 job.speakers(=speakers prop)로 시드되는지.
// 8c47a56이 구현했지만(Transcript.tsx:93 `setSpeakerMap({ ...(speakers ?? {}) })`)
// 이 계약을 직접 잠그는 테스트가 없었다 — 시드가 없으면 편집 진입 즉시 모든 화자가
// 라벨(SPEAKER_00)로 보이고, 사용자가 한 화자만 개명해도 저장 시 나머지 화자의
// 기존 이름이 speakerMap에서 빠져 유실된다(차단 3의 근본 원인과 같은 축).
describe('Transcript — 편집 모드 진입 시 speakerMap 시드 (차단 3 근본원인 회귀 잠금)', () => {
  it('editable 진입 즉시(어떤 편집도 하기 전) speakers prop의 이름이 화면에 보인다 — 라벨이 아니다', () => {
    const transcript = '[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네'

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        speakers={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
      />
    )

    // 시드가 안 되면 speakerMap은 {}로 시작해 라벨이 그대로 보인다(회귀 시 재현).
    expect(screen.getByText('김팀장')).toBeInTheDocument()
    expect(screen.getByText('이대리')).toBeInTheDocument()
    expect(screen.queryByText('SPEAKER_00')).not.toBeInTheDocument()
    expect(screen.queryByText('SPEAKER_01')).not.toBeInTheDocument()
  })

  it('한 화자만 개명해 저장해도, 시드된 나머지 화자의 기존 이름이 speakerMap payload에서 유실되지 않는다', () => {
    const transcript = '[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디'
    const onTranscriptChange = vi.fn()

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        speakers={{ SPEAKER_00: '김팀장', SPEAKER_01: '이대리' }}
        onTranscriptChange={onTranscriptChange}
      />
    )

    // SPEAKER_00("김팀장")만 "박부장"으로 개명한다 — SPEAKER_01은 건드리지 않는다.
    const nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    renameByIndex(nameSpans, 0, '박부장')

    const payload = onTranscriptChange.mock.calls.at(-1)![0]
    expect(payload.speakerMap['SPEAKER_00']).toBe('박부장')
    // 시드가 없었다면 SPEAKER_01 키 자체가 payload.speakerMap에 없어(빈 맵에서 출발)
    // 저장 시 "이대리"라는 기존 이름이 사라진다 — 시드가 있어야 이 키가 살아있다.
    expect(payload.speakerMap['SPEAKER_01']).toBe('이대리')
  })
})

// [qa-c4, director 지시] 차단 3(중복 표시 이름 회의의 줄 재지정)의 유일한 실제
// 안전망. 백엔드 T3(patch_transcript 레벨)는 판별력이 없다고 강등됐다 — 라벨 그대로인
// 본문을 보내면 restore_segment_labels의 (a)가 트리비얼하게 통과해 재지정이 이미
// 보존되고, 그 지점만 봐서는 차단 3을 재현할 수 없다. 실제 위험은 **여기**(프론트가
// 표시 이름이 중복인 상태에서 reassignLine payload를 무엇으로 만드는가)에 있다 —
// 이름이 본문에 구워지면(구계약) 파싱 단계에서 이미 SPEAKER_01/02 구분이 사라진다.
// 지금 계약(render(seg, {})로 항상 라벨 그대로 렌더)이 그 손실 자체를 구조적으로
// 막는다는 걸 여기서 직접 확인한다.
describe('Transcript — 중복 표시 이름 회의에서 reassignLine (차단 3 실제 안전망)', () => {
  it('표시 이름이 전부 같아도(대표님×3) 재지정된 줄은 라벨 그대로 전송되고 원래 라벨로 되돌아가지 않는다', () => {
    const transcript =
      '[00:00] SPEAKER_00: 첫마디\n' +
      '[00:05] SPEAKER_01: 끼어들기\n' +
      '[00:10] SPEAKER_02: 셋째마디'
    const dupSpeakers = { SPEAKER_00: '대표님', SPEAKER_01: '대표님', SPEAKER_02: '대표님' }
    const onTranscriptChange = vi.fn()

    render(
      <Transcript
        transcript={transcript}
        currentTime={0}
        onTimeClick={() => {}}
        editable
        speakers={dupSpeakers}
        onTranscriptChange={onTranscriptChange}
      />
    )

    // idx 0("SPEAKER_00: 첫마디")의 이름 편집 UI를 연다.
    const nameSpans = screen.getAllByTitle('클릭하여 이름 변경')
    fireEvent.click(nameSpans[0])

    // "이 줄만 다른 화자로:" 후보 라벨(SPEAKER_01, SPEAKER_02)의 표시 이름이 전부
    // "대표님"으로 같다 — 텍스트로는 구분이 안 되므로(이 자체가 중복 이름 UX의
    // 한계) DOM 순서(otherLabelsFor가 세그먼트 등장 순서로 만든다 — SPEAKER_01이
    // 먼저)로 골라 SPEAKER_01로 재지정한다.
    const dupButtons = screen.getAllByText('대표님', { selector: 'button' })
    expect(dupButtons.length).toBe(2)
    fireEvent.mouseDown(dupButtons[0]) // SPEAKER_01로 재지정

    const payload = onTranscriptChange.mock.calls.at(-1)![0]
    // 핵심 단언: transcript는 라벨 그대로다 — "대표님"이라는 표시 이름 문자열이
    // 본문에 구워지지 않는다. 구워졌다면 이후 어떤 편집에서도 SPEAKER_00/01/02를
    // 구분할 방법이 없어져 차단 3이 재발한다.
    expect(payload.transcript).not.toContain('대표님')
    expect(payload.transcript.match(/SPEAKER_01:/g)?.length).toBe(2)
    expect(payload.transcript.match(/SPEAKER_00:/g)?.length ?? 0).toBe(0)
    expect(payload.transcript).toContain('SPEAKER_02: 셋째마디')

    // speakerMap은 시드된 중복 맵 그대로 보존돼야 한다(재지정이 이름 자체를
    // 바꾸는 게 아니라 줄의 라벨 소속만 옮긴다는 증거).
    expect(payload.speakerMap).toEqual(dupSpeakers)
  })
})
