'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import CategorySelect from './CategorySelect'

interface Props {
  jobId: string
  initialTranscript: string
  initialSpeakers: string[]
  suggestedNames: Record<string, string>
  suggestedSpeakers?: Record<string, { name: string; confidence: number }>
  initialCategoryId?: string
  onComplete: () => void
}

interface TLine {
  id: string
  timestamp: string
  timeSec: number
  speaker: string
  text: string
}

// "[MM:SS] SPEAKER_XX: 텍스트" 파싱
function parseTranscript(raw: string): TLine[] {
  const re = /^\[(\d{2}):(\d{2})\]\s+(\S+):\s*(.*)$/
  return raw.split('\n').flatMap((line, i) => {
    const m = line.match(re)
    if (!m) return []
    const [, mm, ss, speaker, text] = m
    return [{ id: `l${i}`, timestamp: `${mm}:${ss}`, timeSec: +mm * 60 + +ss, speaker, text: text.trim() }]
  })
}

function serialize(lines: TLine[], names: Record<string, string>): string {
  return lines.map(l => `[${l.timestamp}] ${names[l.speaker]?.trim() || l.speaker}: ${l.text}`).join('\n')
}

const COLORS = ['blue', 'emerald', 'violet', 'amber', 'rose', 'cyan'] as const
type Color = typeof COLORS[number]

const C: Record<Color, { dot: string; text: string; ring: string; bg: string; rowBg: string }> = {
  blue:    { dot: 'bg-blue-500',    text: 'text-blue-600 dark:text-blue-400',       ring: 'ring-blue-300 dark:ring-blue-700',       bg: 'bg-blue-50 dark:bg-blue-900/30',       rowBg: 'bg-blue-50 dark:bg-blue-900/20' },
  emerald: { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', ring: 'ring-emerald-300 dark:ring-emerald-700', bg: 'bg-emerald-50 dark:bg-emerald-900/30', rowBg: 'bg-emerald-50 dark:bg-emerald-900/20' },
  violet:  { dot: 'bg-violet-500',  text: 'text-violet-600 dark:text-violet-400',   ring: 'ring-violet-300 dark:ring-violet-700',   bg: 'bg-violet-50 dark:bg-violet-900/30',   rowBg: 'bg-violet-50 dark:bg-violet-900/20' },
  amber:   { dot: 'bg-amber-500',   text: 'text-amber-600 dark:text-amber-400',     ring: 'ring-amber-300 dark:ring-amber-700',     bg: 'bg-amber-50 dark:bg-amber-900/30',     rowBg: 'bg-amber-50 dark:bg-amber-900/20' },
  rose:    { dot: 'bg-rose-500',    text: 'text-rose-600 dark:text-rose-400',       ring: 'ring-rose-300 dark:ring-rose-700',       bg: 'bg-rose-50 dark:bg-rose-900/30',       rowBg: 'bg-rose-50 dark:bg-rose-900/20' },
  cyan:    { dot: 'bg-cyan-500',    text: 'text-cyan-600 dark:text-cyan-400',       ring: 'ring-cyan-300 dark:ring-cyan-700',       bg: 'bg-cyan-50 dark:bg-cyan-900/30',       rowBg: 'bg-cyan-50 dark:bg-cyan-900/20' },
}

export default function TranscriptEditor({ jobId, initialTranscript, initialSpeakers, suggestedNames, suggestedSpeakers, initialCategoryId = 'meeting', onComplete }: Props) {
  const [lines, setLines] = useState<TLine[]>(() => parseTranscript(initialTranscript))
  const [categoryId, setCategoryId] = useState(initialCategoryId)
  const [names, setNames] = useState<Record<string, string>>(() => {
    const m: Record<string, string> = {}
    initialSpeakers.forEach(s => {
      // 자동 매칭 결과가 있으면 기본값으로 설정
      if (suggestedSpeakers?.[s]) {
        m[s] = suggestedSpeakers[s].name
      } else {
        m[s] = ''
      }
    })
    return m
  })
  const [selected, setSelected] = useState<string | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)
  const activeLinesRef = useRef<HTMLDivElement>(null)

  // 고유 화자 목록
  const speakers = [...new Set(lines.map(l => l.speaker))]
  const colorOf = (s: string): Color => COLORS[speakers.indexOf(s) % COLORS.length]

  // 현재 재생 위치에 해당하는 라인 강조
  const activeLineId = useCallback(() => {
    for (let i = lines.length - 1; i >= 0; i--) {
      if (currentTime >= lines[i].timeSec) return lines[i].id
    }
    return null
  }, [lines, currentTime])

  const seekTo = (sec: number) => {
    if (!audioRef.current) return
    audioRef.current.currentTime = sec
    audioRef.current.play().catch(() => {})
    setPlaying(true)
  }

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) { audioRef.current.pause(); setPlaying(false) }
    else { audioRef.current.play().catch(() => {}); setPlaying(true) }
  }

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  const saveEdit = (id: string, text: string) => {
    setLines(prev => prev.map(l => l.id === id ? { ...l, text } : l))
    setEditId(null)
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    const speaker_map: Record<string, string> = {}
    speakers.forEach(s => { speaker_map[s] = names[s] || s })
    const transcript = serialize(lines, names)
    try {
      await fetch(`/api/jobs/${jobId}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, speaker_map, category_id: categoryId }),
      })
      onComplete()
    } catch {
      alert('오류가 발생했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  const download = () => {
    const text = serialize(lines, names)
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' })),
      download: `스크립트_${new Date().toISOString().slice(0, 10)}.txt`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const curActive = activeLineId()

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

      {/* ── 오디오 플레이어 ── */}
      <audio
        ref={audioRef}
        src={`/api/jobs/${jobId}/audio`}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime ?? 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration ?? 0)}
        onEnded={() => setPlaying(false)}
      />
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0">
        <button
          onClick={togglePlay}
          className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center flex-shrink-0 transition-colors"
        >
          {playing
            ? <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>
            : <svg className="w-3.5 h-3.5 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          }
        </button>
        <div
          className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full cursor-pointer relative"
          onClick={e => {
            if (!audioRef.current || !duration) return
            const r = e.currentTarget.getBoundingClientRect()
            audioRef.current.currentTime = ((e.clientX - r.left) / r.width) * duration
          }}
        >
          <div
            className="absolute inset-y-0 left-0 bg-blue-500 rounded-full transition-all"
            style={{ width: duration ? `${(currentTime / duration) * 100}%` : '0%' }}
          />
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400 font-mono flex-shrink-0">
          {fmt(currentTime)}{duration > 0 && isFinite(duration) ? ` / ${fmt(duration)}` : ''}
        </span>
        <button onClick={download} className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors flex-shrink-0">
          ↓ 다운로드
        </button>
      </div>

      {/* ── 메인 영역 ── */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0">

        {/* 화자 패널 — 모바일: 수평 스크롤, 데스크탑: 사이드 패널 */}
        <div className="md:w-44 flex-shrink-0 border-b md:border-b-0 md:border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex flex-col">
          <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">참석자</span>
          </div>
          <div className="flex md:flex-col overflow-x-auto md:overflow-y-auto p-2 gap-2 md:space-y-1.5">
            {speakers.map(sp => {
              const c = C[colorOf(sp)]
              const count = lines.filter(l => l.speaker === sp).length
              const isSelected = selected === sp
              return (
                <div
                  key={sp}
                  onClick={() => setSelected(prev => prev === sp ? null : sp)}
                  className={`flex-shrink-0 md:flex-shrink rounded-lg p-2 border cursor-pointer transition-all ${
                    isSelected
                      ? `${c.bg} border-current ring-1 ${c.ring}`
                      : 'bg-white dark:bg-gray-700 border-gray-200 dark:border-gray-600 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${c.dot}`} />
                    <span className="text-xs font-mono text-gray-500 dark:text-gray-400 truncate leading-none">{sp}</span>
                  </div>
                  <input
                    type="text"
                    placeholder={suggestedSpeakers?.[sp]?.name || suggestedNames[sp] || '이름 입력'}
                    value={names[sp] || ''}
                    onChange={e => setNames(prev => ({ ...prev, [sp]: e.target.value }))}
                    onClick={e => e.stopPropagation()}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white dark:bg-gray-600 dark:text-gray-200"
                  />
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-xs text-gray-400 dark:text-gray-500">{count}개 발화</span>
                    {suggestedSpeakers?.[sp] && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">
                        ✓ {Math.round(suggestedSpeakers[sp].confidence)}%
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* 스크립트 라인 목록 */}
        <div className="flex-1 overflow-y-auto" ref={activeLinesRef}>
          <div className="p-3 space-y-0.5">
            {lines.map(line => {
              const c = C[colorOf(line.speaker)]
              const isActive = curActive === line.id
              const isHighlighted = selected === line.speaker
              const isDimmed = selected !== null && selected !== line.speaker
              const displayName = names[line.speaker]?.trim() || line.speaker

              return (
                <div
                  key={line.id}
                  className={`flex gap-2 px-2 py-1.5 rounded-lg transition-all group ${
                    isActive
                      ? `${c.rowBg} ring-1 ring-inset ${c.ring}`
                      : isHighlighted
                      ? c.rowBg
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                  } ${isDimmed ? 'opacity-30' : ''}`}
                >
                  {/* 타임스탬프 — 클릭 시 해당 지점 재생 */}
                  <button
                    onClick={() => seekTo(line.timeSec)}
                    className="font-mono text-xs text-blue-400 hover:text-blue-600 flex-shrink-0 pt-0.5 w-10 text-left hover:underline"
                    title={`${line.timestamp}부터 재생`}
                  >
                    {line.timestamp}
                  </button>

                  {/* 화자명 — 클릭 시 해당 화자 선택/해제 */}
                  <button
                    onClick={() => setSelected(prev => prev === line.speaker ? null : line.speaker)}
                    className={`text-xs font-semibold flex-shrink-0 pt-0.5 w-24 text-left truncate ${c.text} hover:underline`}
                    title="클릭하여 화자 선택"
                  >
                    {displayName}
                  </button>

                  {/* 발화 텍스트 — 클릭 시 인라인 편집 */}
                  <div className="flex-1 text-sm text-gray-800 dark:text-gray-200 min-w-0">
                    {editId === line.id ? (
                      <input
                        autoFocus
                        value={editText}
                        onChange={e => setEditText(e.target.value)}
                        onBlur={() => saveEdit(line.id, editText)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') saveEdit(line.id, editText)
                          if (e.key === 'Escape') setEditId(null)
                        }}
                        className="w-full border-b border-blue-400 outline-none bg-transparent text-sm"
                      />
                    ) : (
                      <span
                        onClick={() => { setEditId(line.id); setEditText(line.text) }}
                        className="cursor-text hover:bg-yellow-50 rounded px-0.5 leading-relaxed"
                        title="클릭하여 편집"
                      >
                        {line.text || <span className="text-gray-300 italic">(빈 발화)</span>}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 하단 버튼 ── */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">카테고리:</span>
          <CategorySelect value={categoryId} onChange={setCategoryId} className="flex-1" />
        </div>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium text-sm transition-colors"
        >
          {submitting ? '처리 중...' : '문서 생성'}
        </button>
      </div>
    </div>
  )
}
