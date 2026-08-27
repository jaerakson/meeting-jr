'use client'

import { useState, useEffect } from 'react'
import { FollowupData, FollowupItem } from '@/types'

interface Props {
  jobId: string
}

const AI_STATUS_BADGE: Record<FollowupItem['ai_status'], { icon: string; color: string; darkColor: string }> = {
  completed: { icon: '✅', color: 'bg-green-100 text-green-700', darkColor: 'dark:bg-green-900/30 dark:text-green-400' },
  mentioned: { icon: '⚠️', color: 'bg-amber-100 text-amber-700', darkColor: 'dark:bg-amber-900/30 dark:text-amber-400' },
  not_mentioned: { icon: '❌', color: 'bg-red-100 text-red-700', darkColor: 'dark:bg-red-900/30 dark:text-red-400' },
}

const USER_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: '미확인' },
  { value: 'completed', label: '완료' },
  { value: 'in_progress', label: '진행중' },
  { value: 'not_addressed', label: '미처리' },
]

export default function FollowupPanel({ jobId }: Props) {
  const [data, setData] = useState<FollowupData | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  const fetchData = () => {
    setLoading(true)
    fetch(`/api/jobs/${jobId}/followup`)
      .then(r => (r.ok ? r.json() : null))
      .then((d: FollowupData | null) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchData()
  }, [jobId])

  const handleUserStatusChange = async (index: number, userStatus: string) => {
    if (!data) return
    const updated = { ...data, items: data.items.map((item, i) =>
      i === index ? { ...item, user_status: (userStatus || null) as FollowupItem['user_status'] } : item
    )}
    setData(updated)
    try {
      await fetch(`/api/jobs/${jobId}/followup`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: updated.items }),
      })
    } catch {
      // silent fail
    }
  }

  const handleConfirm = async (index: number, confirmed: boolean) => {
    if (!data) return
    const updated = { ...data, items: data.items.map((item, i) =>
      i === index ? { ...item, confirmed } : item
    )}
    setData(updated)
    try {
      await fetch(`/api/jobs/${jobId}/followup`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: updated.items }),
      })
    } catch {
      // silent fail
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await fetch(`/api/jobs/${jobId}/followup/generate`, { method: 'POST' })
      if (res.ok) fetchData()
    } catch {
      // silent fail
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 flex items-center justify-center h-[120px] mt-4">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return null
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300">
          후속조치 추적
        </h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 disabled:opacity-50 transition-colors"
        >
          {generating ? '분석 중...' : '재분석'}
        </button>
      </div>
      {data.source_job_title && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          이전 회의: <span className="text-gray-500 dark:text-gray-400">{data.source_job_title}</span> 의 액션아이템
        </p>
      )}
      <div className="space-y-3">
        {data.items.map((item, idx) => {
          const badge = AI_STATUS_BADGE[item.ai_status]
          return (
            <div
              key={idx}
              className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-2"
            >
              <div className="flex items-start gap-2">
                <label className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                  <input
                    type="checkbox"
                    checked={item.confirmed}
                    onChange={e => handleConfirm(idx, e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                  />
                </label>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full ${badge.color} ${badge.darkColor}`}>
                      {badge.icon} {item.ai_status === 'completed' ? '완료' : item.ai_status === 'mentioned' ? '언급됨' : '미언급'}
                    </span>
                    {item.assignee && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        @{item.assignee}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-200 mt-1">
                    {item.text}
                  </p>
                  {item.ai_evidence && (
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 italic">
                      &quot;{item.ai_evidence}&quot;
                    </p>
                  )}
                </div>
                <select
                  value={item.user_status || ''}
                  onChange={e => handleUserStatusChange(idx, e.target.value)}
                  className="flex-shrink-0 text-xs px-1.5 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {USER_STATUS_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
