'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

interface ReferencedMeeting {
  id: string
  title: string
  created_at: string
}

interface InsightResult {
  answer: string
  meeting_count: number
  meetings: ReferencedMeeting[]
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function InsightsPage() {
  const router = useRouter()
  const [question, setQuestion] = useState('')
  const [keyword, setKeyword] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<InsightResult | null>(null)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    if (!question.trim() || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const body: Record<string, string> = { question: question.trim() }
      if (keyword.trim()) body.keyword = keyword.trim()
      if (dateFrom) body.date_from = dateFrom
      if (dateTo) body.date_to = dateTo

      const res = await fetch('/api/insights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 404) {
        setError('관련 회의를 찾을 수 없습니다')
        return
      }
      if (!res.ok) {
        setError('분석에 실패했습니다')
        return
      }
      setResult(await res.json())
    } catch {
      setError('분석에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900">
      <div className="max-w-4xl mx-auto px-4 py-6">

        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/"
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
          >
            &larr; 돌아가기
          </Link>
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">크로스 회의 인사이트</h1>
        </div>

        {/* Filter area */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mb-6 space-y-3">
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="키워드로 관련 회의 필터..."
            className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-400">~</span>
            <input
              type="date"
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
              min={dateFrom}
              className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <textarea
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAnalyze() }
            }}
            placeholder="여러 회의를 종합해서 질문하세요..."
            rows={3}
            className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
          <button
            onClick={handleAnalyze}
            disabled={loading || !question.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg font-medium disabled:opacity-50 transition-colors"
          >
            분석하기
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">회의를 분석하고 있습니다...</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-white dark:bg-gray-800 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-4">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
              <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed">{result.answer}</p>
            </div>

            {result.meetings.length > 0 && (
              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-3">{result.meeting_count}개 회의를 분석했습니다</p>
                <div className="space-y-2">
                  {result.meetings.map(m => (
                    <div
                      key={m.id}
                      className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
                      onClick={() => router.push(`/?job=${m.id}`)}
                    >
                      <span className="text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                        {m.title}
                      </span>
                      <span className="text-xs text-gray-400 flex-shrink-0 ml-3">
                        {formatDate(m.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
