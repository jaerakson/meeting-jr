'use client'

import { useMemo, useEffect, useRef, useState, useCallback, ReactNode } from 'react'
import { parse, render, displayName as resolveDisplayName, formatTimestamp, withoutRaw, TranscriptSegment } from '@/lib/transcript'

interface TranscriptProps {
  transcript: string
  currentTime: number
  onTimeClick: (sec: number) => void
  editable?: boolean
  onTranscriptChange?: (transcript: string) => void
  searchQuery?: string
}

// 화면에 그리기 위한 파생 뷰. label은 세그먼트의 정체성(고정), name은 표시 이름(가변).
interface ViewLine {
  time: number
  timeStr: string
  label: string | null
  name: string
  text: string
}

const SPEAKER_COLORS: { bg: string; text: string }[] = [
  { bg: 'bg-[#EBF4FF] dark:bg-blue-900/30', text: 'text-[#1D4ED8] dark:text-blue-400' },
  { bg: 'bg-[#F0FDF4] dark:bg-green-900/30', text: 'text-[#166534] dark:text-green-400' },
  { bg: 'bg-[#FFF7ED] dark:bg-orange-900/30', text: 'text-[#9A3412] dark:text-orange-400' },
  { bg: 'bg-[#FAF5FF] dark:bg-purple-900/30', text: 'text-[#6B21A8] dark:text-purple-400' },
]
const PASSTHROUGH_COLOR = { bg: 'bg-gray-50 dark:bg-gray-800/40', text: 'text-gray-500 dark:text-gray-400' }

function toViewLines(segments: TranscriptSegment[], speakerMap: Record<string, string>, editable: boolean): ViewLine[] {
  return segments.map(seg => ({
    time: seg.start ?? 0,
    timeStr: formatTimestamp(seg.start),
    label: seg.label,
    name: editable ? resolveDisplayName(seg.label, speakerMap) : (seg.label ?? ''),
    text: seg.text,
  }))
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlightSearchText(text: string, query: string | undefined): ReactNode {
  if (!query || !text) return text
  const escaped = escapeRegExp(query)
  const regex = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(regex)
  if (parts.length === 1) return text
  return parts.map((part, i) =>
    regex.test(part)
      ? <mark key={i} className="bg-yellow-200 dark:bg-yellow-700 text-inherit rounded-sm px-0.5">{part}</mark>
      : part
  )
}

export default function Transcript({ transcript, currentTime, onTimeClick, editable, onTranscriptChange, searchQuery }: TranscriptProps) {
  const parsedSegments = useMemo(() => parse(transcript), [transcript])
  const [lastClickedSpeaker, setLastClickedSpeaker] = useState<string | null>(null)

  // 회의 전환 시 (transcript 변경) 순환 클릭 상태 리셋
  useEffect(() => {
    setLastClickedSpeaker(null)
  }, [transcript])

  // editable 모드 로컬 상태: 세그먼트(라벨 고정) + speakerMap(라벨 → 표시 이름).
  // 라벨은 절대 덮어쓰지 않는다 — 라벨이 정체성이고, speakerMap만 갈아끼운다.
  const [editSegments, setEditSegments] = useState<TranscriptSegment[]>([])
  const [speakerMap, setSpeakerMap] = useState<Record<string, string>>({})
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  // 화자 이름 편집: 어느 라인(idx)의 이름을 편집 중인지
  const [editingSpeakerIdx, setEditingSpeakerIdx] = useState<number | null>(null)
  const [renameText, setRenameText] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)
  const searchMatchRef = useRef<HTMLDivElement>(null)
  const searchScrolledRef = useRef(false)

  // editable 모드 진입 시 로컬 편집 세그먼트 초기화
  useEffect(() => {
    if (editable) {
      setEditSegments(parse(transcript))
      setSpeakerMap({})
      setEditIdx(null)
      setEditingSpeakerIdx(null)
    }
  }, [editable, transcript])

  const segments = editable ? editSegments : parsedSegments
  const lines = useMemo(() => toViewLines(segments, speakerMap, !!editable), [segments, speakerMap, editable])

  const speakerColorMap = useMemo(() => {
    const map = new Map<string, number>()
    let colorIdx = 0
    for (const line of lines) {
      if (line.label !== null && !map.has(line.label)) {
        map.set(line.label, colorIdx % SPEAKER_COLORS.length)
        colorIdx++
      }
    }
    return map
  }, [lines])

  const activeIdx = useMemo(() => {
    if (editable) return -1
    let idx = -1
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].label === null) continue
      if (lines[i].time <= currentTime) idx = i
      else break
    }
    return idx
  }, [lines, currentTime, editable])

  const handleSpeakerClick = useCallback((label: string) => {
    const speakerLines = lines
      .map((line, idx) => ({ time: line.time, idx, label: line.label }))
      .filter(l => l.label === label)

    if (speakerLines.length === 0) return

    if (lastClickedSpeaker === label) {
      const nextLine = speakerLines.find(l => l.time > currentTime)
      if (nextLine) {
        onTimeClick(nextLine.time)
      } else {
        onTimeClick(speakerLines[0].time)
      }
    } else {
      onTimeClick(speakerLines[0].time)
    }
    setLastClickedSpeaker(label)
  }, [lines, currentTime, lastClickedSpeaker, onTimeClick])

  // 검색어가 포함된 첫 번째 라인 인덱스
  const firstSearchMatchIdx = useMemo(() => {
    if (!searchQuery || editable) return -1
    const q = searchQuery.toLowerCase()
    return lines.findIndex(l => l.text.toLowerCase().includes(q) || l.name.toLowerCase().includes(q))
  }, [lines, searchQuery, editable])

  // 검색어 변경 시 스크롤 플래그 리셋
  useEffect(() => {
    searchScrolledRef.current = false
  }, [searchQuery])

  // 검색 매치가 있으면 첫 매치로 자동 스크롤 (최초 1회)
  useEffect(() => {
    if (firstSearchMatchIdx >= 0 && searchMatchRef.current && !searchScrolledRef.current) {
      searchScrolledRef.current = true
      searchMatchRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [firstSearchMatchIdx])

  useEffect(() => {
    if (!editable && !searchQuery && activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [activeIdx, editable, searchQuery])

  const saveEdit = (idx: number, text: string) => {
    const updated = editSegments.map((seg, i) => i === idx ? withoutRaw(seg, { text }) : seg)
    setEditSegments(updated)
    setEditIdx(null)
    onTranscriptChange?.(render(updated, speakerMap))
  }

  // 전체 변경: 이 라벨의 표시 이름을 speakerMap에서만 갱신한다(라벨 자체는 불변).
  const saveSpeakerAll = (label: string, newName: string) => {
    const trimmed = newName.trim()
    if (!trimmed || trimmed === resolveDisplayName(label, speakerMap)) { setEditingSpeakerIdx(null); return }
    const updatedMap = { ...speakerMap, [label]: trimmed }
    setSpeakerMap(updatedMap)
    setEditingSpeakerIdx(null)
    onTranscriptChange?.(render(editSegments, updatedMap))
  }

  // 이 줄만 다른 화자로 재지정: 이 세그먼트의 label을 이미 존재하는 다른 라벨로 바꾼다.
  // ("이 항목만 이름 변경"은 라벨 모델에서 성립하지 않는다 — 라벨이 같으면 같은 화자다.
  //  대신 이 줄을 다른 화자에게 재귀속시키는 조작으로 재해석한다.)
  const reassignLine = (idx: number, targetLabel: string) => {
    const current = editSegments[idx]
    if (!current || current.label === targetLabel) { setEditingSpeakerIdx(null); return }
    const updated = editSegments.map((seg, i) => i === idx ? withoutRaw(seg, { label: targetLabel }) : seg)
    setEditSegments(updated)
    setEditingSpeakerIdx(null)
    onTranscriptChange?.(render(updated, speakerMap))
  }

  const otherLabelsFor = (idx: number): string[] => {
    const current = editSegments[idx]?.label
    const seen = new Set<string>()
    const result: string[] = []
    for (const seg of editSegments) {
      if (seg.label && seg.label !== current && !seen.has(seg.label)) {
        seen.add(seg.label)
        result.push(seg.label)
      }
    }
    return result
  }

  if (lines.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        스크립트가 없습니다.
      </div>
    )
  }

  return (
    <div ref={containerRef} className="h-full overflow-y-auto p-4 space-y-3">
      {lines.map((line, idx) => {
        const hasLabel = line.label !== null
        const colorIdx = hasLabel ? (speakerColorMap.get(line.label as string) ?? 0) : null
        const color = colorIdx !== null ? SPEAKER_COLORS[colorIdx] : PASSTHROUGH_COLOR
        const isActive = idx === activeIdx
        const isSearchMatch = !editable && !!searchQuery && (
          line.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
          line.name.toLowerCase().includes(searchQuery.toLowerCase())
        )
        const isFirstMatch = idx === firstSearchMatchIdx
        const otherLabels = editable && editingSpeakerIdx === idx ? otherLabelsFor(idx) : []

        return (
          <div
            key={idx}
            ref={isFirstMatch ? searchMatchRef : (isActive ? activeRef : undefined)}
            className={`rounded-xl p-3 transition-all ${color.bg} ${
              isActive && !searchQuery ? 'ring-2 ring-accent ring-offset-1' : ''
            } ${isSearchMatch ? 'ring-2 ring-yellow-400 ring-offset-1' : ''}`}
          >
            {hasLabel && (
              <div className="mb-1">
                {editable && editingSpeakerIdx === idx ? (
                  /* 이름 편집 UI: 표시 이름 input(전체 변경) + 다른 화자로 재지정(이 줄만) */
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <input
                        autoFocus
                        value={renameText}
                        onChange={e => setRenameText(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Escape') setEditingSpeakerIdx(null)
                        }}
                        className={`text-sm font-semibold bg-white border-b-2 border-blue-400 outline-none w-32 leading-none ${color.text}`}
                        onClick={e => e.stopPropagation()}
                        placeholder="새 이름"
                      />
                      <button
                        onClick={() => onTimeClick(line.time)}
                        className="text-xs text-gray-400 hover:text-accent transition-colors font-mono ml-auto"
                      >
                        {line.timeStr}
                      </button>
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <button
                        onMouseDown={e => { e.preventDefault(); saveSpeakerAll(line.label as string, renameText) }}
                        className="text-xs px-2 py-0.5 bg-blue-50 border border-blue-300 hover:bg-blue-100 rounded text-blue-700 font-medium transition-colors"
                      >
                        전체 변경 ({editSegments.filter(s => s.label === line.label).length}개)
                      </button>
                      {otherLabels.length > 0 && (
                        <>
                          <span className="text-xs text-gray-400">이 줄만 다른 화자로:</span>
                          {otherLabels.map(l => (
                            <button
                              key={l}
                              onMouseDown={e => { e.preventDefault(); reassignLine(idx, l) }}
                              className="text-xs px-2 py-0.5 bg-white border border-gray-300 hover:bg-gray-50 rounded text-gray-700 font-medium transition-colors"
                            >
                              {resolveDisplayName(l, speakerMap)}
                            </button>
                          ))}
                        </>
                      )}
                      <button
                        onMouseDown={e => { e.preventDefault(); setEditingSpeakerIdx(null) }}
                        className="text-xs text-gray-400 hover:text-gray-600 transition-colors ml-1"
                      >
                        취소
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-semibold ${color.text} ${
                        editable
                          ? 'cursor-pointer hover:underline decoration-dashed'
                          : 'cursor-pointer hover:underline decoration-dotted underline-offset-2'
                      }`}
                      onClick={() => {
                        if (editable) {
                          setEditingSpeakerIdx(idx); setRenameText(line.name)
                        } else {
                          handleSpeakerClick(line.label as string)
                        }
                      }}
                      title={editable ? '클릭하여 이름 변경' : '클릭하여 해당 화자의 발언으로 이동'}
                    >
                      {line.name}
                    </span>
                    <button
                      onClick={() => onTimeClick(line.time)}
                      className="text-xs text-blue-500 hover:text-blue-700 hover:underline transition-colors font-mono bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded"
                    >
                      {line.timeStr}
                    </button>
                  </div>
                )}
              </div>
            )}
            {editable && editIdx === idx ? (
              <input
                autoFocus
                value={editText}
                onChange={e => setEditText(e.target.value)}
                onBlur={() => saveEdit(idx, editText)}
                onKeyDown={e => {
                  if (e.key === 'Enter') saveEdit(idx, editText)
                  if (e.key === 'Escape') setEditIdx(null)
                }}
                className="w-full text-sm text-gray-800 dark:text-gray-200 bg-white dark:bg-gray-700 border-b border-blue-400 outline-none leading-relaxed px-0.5"
              />
            ) : (
              <p
                className={`text-sm text-gray-800 dark:text-gray-200 leading-relaxed ${editable ? 'cursor-text hover:bg-white/60 dark:hover:bg-gray-600/60 rounded px-0.5' : ''}`}
                onClick={() => {
                  if (editable) { setEditIdx(idx); setEditText(line.text) }
                }}
                title={editable ? '클릭하여 편집' : undefined}
              >
                {line.text
                  ? (searchQuery && !editable ? highlightSearchText(line.text, searchQuery) : line.text)
                  : <span className="text-gray-300 italic">(빈 발화)</span>}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
