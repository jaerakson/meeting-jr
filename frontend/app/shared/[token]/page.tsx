'use client'

import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'next/navigation'
import { useTheme } from '@/hooks/useTheme'
import { parse, formatTimestamp, displayName } from '@/lib/transcript'

interface SharedData {
  title: string
  summary: string
  transcript: string
  speakers: Record<string, string>
  created_at: string
  duration_sec: number | null
}

const SPEAKER_COLORS = [
  { bg: 'bg-[#EBF4FF] dark:bg-blue-900/30', text: 'text-[#1D4ED8] dark:text-blue-400' },
  { bg: 'bg-[#F0FDF4] dark:bg-green-900/30', text: 'text-[#166534] dark:text-green-400' },
  { bg: 'bg-[#FFF7ED] dark:bg-orange-900/30', text: 'text-[#9A3412] dark:text-orange-400' },
  { bg: 'bg-[#FAF5FF] dark:bg-purple-900/30', text: 'text-[#6B21A8] dark:text-purple-400' },
]

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (!line.trim()) { nodes.push(<div key={i} className="h-2" />); continue }
    if (line.startsWith('# ')) { nodes.push(<h1 key={i} className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">{line.slice(2)}</h1>); continue }
    if (line.startsWith('## ')) { nodes.push(<h2 key={i} className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-2 mt-3">{line.slice(3)}</h2>); continue }
    if (line.startsWith('### ')) { nodes.push(<h3 key={i} className="text-base font-semibold text-gray-800 dark:text-gray-100 mb-1 mt-2">{line.slice(4)}</h3>); continue }
    if (line.trimStart().startsWith('- [ ] ')) {
      nodes.push(<div key={i} className="flex items-start gap-2 py-0.5"><input type="checkbox" disabled className="mt-1 flex-shrink-0" /><span className="text-sm text-gray-700 dark:text-gray-300">{line.trimStart().slice(6)}</span></div>)
      continue
    }
    if (line.trimStart().startsWith('- [x] ') || line.trimStart().startsWith('- [X] ')) {
      nodes.push(<div key={i} className="flex items-start gap-2 py-0.5"><input type="checkbox" disabled checked className="mt-1 flex-shrink-0" /><span className="text-sm text-gray-500 line-through">{line.trimStart().slice(6)}</span></div>)
      continue
    }
    if (line.trimStart().startsWith('- ')) {
      nodes.push(<div key={i} className="flex items-start gap-2 py-0.5 pl-1"><span className="text-gray-400 mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-gray-400" /><span className="text-sm text-gray-700 dark:text-gray-300">{line.trimStart().slice(2)}</span></div>)
      continue
    }
    const numMatch = line.trimStart().match(/^(\d+)\.\s+(.+)$/)
    if (numMatch) {
      nodes.push(<div key={i} className="flex items-start gap-2 py-0.5 pl-1"><span className="text-sm text-gray-500 dark:text-gray-400 flex-shrink-0 font-medium">{numMatch[1]}.</span><span className="text-sm text-gray-700 dark:text-gray-300">{numMatch[2]}</span></div>)
      continue
    }
    nodes.push(<p key={i} className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{line}</p>)
  }
  return nodes
}

function formatDuration(sec: number | null): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m === 0) return `${s}초`
  return `${m}분 ${s}초`
}

export default function SharedPage() {
  const params = useParams()
  const token = params.token as string
  useTheme()

  const [data, setData] = useState<SharedData | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/shared/${token}`)
      .then(res => {
        if (!res.ok) throw new Error()
        return res.json()
      })
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [token])

  const segments = useMemo(() => data ? parse(data.transcript || '') : [], [data])

  const speakerColorMap = useMemo(() => {
    const map = new Map<string, number>()
    let idx = 0
    for (const seg of segments) {
      if (seg.label !== null && !map.has(seg.label)) {
        map.set(seg.label, idx % SPEAKER_COLORS.length)
        idx++
      }
    }
    return map
  }, [segments])

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">🔗</div>
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-2">유효하지 않은 공유 링크입니다</h1>
          <p className="text-sm text-gray-400">링크가 만료되었거나 존재하지 않습니다.</p>
        </div>
      </div>
    )
  }

  const date = new Date(data.created_at).toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric',
  })

  return (
    <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900">
      <div className="max-w-4xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">{data.title}</h1>
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>{date}</span>
            {data.duration_sec && <span>{formatDuration(data.duration_sec)}</span>}
          </div>
        </div>

        {/* Summary */}
        {data.summary && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">요약</h2>
            <div>{renderMarkdown(data.summary)}</div>
          </div>
        )}

        {/* Transcript */}
        {segments.length > 0 && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">대화 스크립트</h2>
            <div className="space-y-3">
              {segments.map((seg, idx) => {
                // 매칭 실패 줄(label:null)은 화자 서식 없이 원문 그대로 보존한다(무손실 파싱 계약)
                if (seg.label === null) {
                  return seg.text ? (
                    <p key={idx} className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{seg.text}</p>
                  ) : null
                }
                const colorIdx = speakerColorMap.get(seg.label) ?? 0
                const color = SPEAKER_COLORS[colorIdx]
                return (
                  <div key={idx} className={`rounded-xl p-3 ${color.bg}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-sm font-semibold ${color.text}`}>{displayName(seg.label, data.speakers)}</span>
                      <span className="text-xs text-gray-400 font-mono">{formatTimestamp(seg.start)}</span>
                    </div>
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                      {seg.text || <span className="text-gray-300 italic">(빈 발화)</span>}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Watermark */}
        <div className="text-center py-6">
          <p className="text-xs text-gray-300 dark:text-gray-600">Meeting Jr.로 생성됨</p>
        </div>
      </div>
    </div>
  )
}
