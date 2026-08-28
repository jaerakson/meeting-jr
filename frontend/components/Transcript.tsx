'use client'

import { useMemo, useEffect, useRef, useState, useCallback, ReactNode } from 'react'

interface TranscriptProps {
  transcript: string
  currentTime: number
  onTimeClick: (sec: number) => void
  editable?: boolean
  onTranscriptChange?: (transcript: string) => void
  searchQuery?: string
}

interface TranscriptLine {
  time: number
  timeStr: string
  speaker: string
  text: string
}

const SPEAKER_COLORS: { bg: string; text: string }[] = [
  { bg: 'bg-[#EBF4FF] dark:bg-blue-900/30', text: 'text-[#1D4ED8] dark:text-blue-400' },
  { bg: 'bg-[#F0FDF4] dark:bg-green-900/30', text: 'text-[#166534] dark:text-green-400' },
  { bg: 'bg-[#FFF7ED] dark:bg-orange-900/30', text: 'text-[#9A3412] dark:text-orange-400' },
  { bg: 'bg-[#FAF5FF] dark:bg-purple-900/30', text: 'text-[#6B21A8] dark:text-purple-400' },
]

function parseTranscript(raw: string): TranscriptLine[] {
  const lines: TranscriptLine[] = []
  const regex = /^\[(\d{2}):(\d{2})\]\s*(.+?):\s*(.*)$/

  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(regex)
    if (match) {
      const minutes = parseInt(match[1], 10)
      const seconds = parseInt(match[2], 10)
      lines.push({
        time: minutes * 60 + seconds,
        timeStr: `${match[1]}:${match[2]}`,
        speaker: match[3],
        text: match[4],
      })
    }
  }
  return lines
}

function serializeLines(lines: TranscriptLine[]): string {
  return lines.map(l => `[${l.timeStr}] ${l.speaker}: ${l.text}`).join('\n')
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
  const parsedLines = useMemo(() => parseTranscript(transcript), [transcript])
  const [lastClickedSpeaker, setLastClickedSpeaker] = useState<string | null>(null)
  const [editLines, setEditLines] = useState<TranscriptLine[]>([])
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  // 화자 이름 편집: 어느 라인(idx)의 이름을 편집 중인지
  const [editingSpeakerIdx, setEditingSpeakerIdx] = useState<number | null>(null)
  const [renameText, setRenameText] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)
  const searchMatchRef = useRef<HTMLDivElement>(null)
  const searchScrolledRef = useRef(false)

  // editable 모드 진입 시 로컬 편집 라인 초기화
  useEffect(() => {
    if (editable) {
      setEditLines(parseTranscript(transcript))
      setEditIdx(null)
    }
  }, [editable, transcript])

  const lines = editable ? editLines : parsedLines

  const speakerColorMap = useMemo(() => {
    const map = new Map<string, number>()
    let colorIdx = 0
    for (const line of lines) {
      if (!map.has(line.speaker)) {
        map.set(line.speaker, colorIdx % SPEAKER_COLORS.length)
        colorIdx++
      }
    }
    return map
  }, [lines])

  const activeIdx = useMemo(() => {
    if (editable) return -1
    let idx = -1
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].time <= currentTime) idx = i
      else break
    }
    return idx
  }, [lines, currentTime, editable])

  const handleSpeakerClick = useCallback((speaker: string) => {
    const speakerLines = lines
      .map((line, idx) => ({ time: line.time, idx }))
      .filter((_, idx) => lines[idx].speaker === speaker)

    if (speakerLines.length === 0) return

    if (lastClickedSpeaker === speaker) {
      const nextLine = speakerLines.find(l => l.time > currentTime)
      if (nextLine) {
        onTimeClick(nextLine.time)
      } else {
        onTimeClick(speakerLines[0].time)
      }
    } else {
      onTimeClick(speakerLines[0].time)
    }
    setLastClickedSpeaker(speaker)
  }, [lines, currentTime, lastClickedSpeaker, onTimeClick])

  // 검색어가 포함된 첫 번째 라인 인덱스
  const firstSearchMatchIdx = useMemo(() => {
    if (!searchQuery || editable) return -1
    const q = searchQuery.toLowerCase()
    return lines.findIndex(l => l.text.toLowerCase().includes(q) || l.speaker.toLowerCase().includes(q))
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
    const updated = editLines.map((l, i) => i === idx ? { ...l, text } : l)
    setEditLines(updated)
    setEditIdx(null)
    onTranscriptChange?.(serializeLines(updated))
  }

  // 이 항목만 변경
  const saveSpeakerSingle = (idx: number, newName: string) => {
    const trimmed = newName.trim()
    if (!trimmed) { setEditingSpeakerIdx(null); return }
    const updated = editLines.map((l, i) => i === idx ? { ...l, speaker: trimmed } : l)
    setEditLines(updated)
    setEditingSpeakerIdx(null)
    onTranscriptChange?.(serializeLines(updated))
  }

  // 같은 이름 전체 변경
  const saveSpeakerAll = (oldName: string, newName: string) => {
    const trimmed = newName.trim()
    if (!trimmed || trimmed === oldName) { setEditingSpeakerIdx(null); return }
    const updated = editLines.map(l => l.speaker === oldName ? { ...l, speaker: trimmed } : l)
    setEditLines(updated)
    setEditingSpeakerIdx(null)
    onTranscriptChange?.(serializeLines(updated))
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
        const colorIdx = speakerColorMap.get(line.speaker) ?? 0
        const color = SPEAKER_COLORS[colorIdx]
        const isActive = idx === activeIdx
        const isSearchMatch = !editable && searchQuery && (
          line.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
          line.speaker.toLowerCase().includes(searchQuery.toLowerCase())
        )
        const isFirstMatch = idx === firstSearchMatchIdx

        return (
          <div
            key={idx}
            ref={isFirstMatch ? searchMatchRef : (isActive ? activeRef : undefined)}
            className={`rounded-xl p-3 transition-all ${color.bg} ${
              isActive && !searchQuery ? 'ring-2 ring-accent ring-offset-1' : ''
            } ${isSearchMatch ? 'ring-2 ring-yellow-400 ring-offset-1' : ''}`}
          >
            <div className="mb-1">
              {editable && editingSpeakerIdx === idx ? (
                /* 이름 편집 UI: input + 이 항목만 / 전체 변경 버튼 */
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
                  <div className="flex items-center gap-1.5">
                    <button
                      onMouseDown={e => { e.preventDefault(); saveSpeakerSingle(idx, renameText) }}
                      className="text-xs px-2 py-0.5 bg-white border border-gray-300 hover:bg-gray-50 rounded text-gray-700 font-medium transition-colors"
                    >
                      이 항목만
                    </button>
                    <button
                      onMouseDown={e => { e.preventDefault(); saveSpeakerAll(line.speaker, renameText) }}
                      className="text-xs px-2 py-0.5 bg-blue-50 border border-blue-300 hover:bg-blue-100 rounded text-blue-700 font-medium transition-colors"
                    >
                      전체 변경 ({editLines.filter(l => l.speaker === line.speaker).length}개)
                    </button>
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
                        setEditingSpeakerIdx(idx); setRenameText(line.speaker)
                      } else {
                        handleSpeakerClick(line.speaker)
                      }
                    }}
                    title={editable ? '클릭하여 이름 변경' : '클릭하여 해당 화자의 발언으로 이동'}
                  >
                    {line.speaker}
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
