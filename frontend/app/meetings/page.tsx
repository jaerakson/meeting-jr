'use client'

import { useState, useEffect, useCallback, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Job } from '@/types'
import MeetingCard from '@/components/MeetingCard'
import Pagination from '@/components/Pagination'

interface MeetingsResponse {
  items: Job[]
  total: number
  page: number
  pages: number
}

function MeetingsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1)
  const [data, setData] = useState<MeetingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchMeetings = useCallback(async (q: string, p: number) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/meetings?q=${encodeURIComponent(q)}&page=${p}&limit=12`)
      if (res.ok) setData(await res.json())
    } finally {
      setLoading(false)
    }
  }, [])

  // 검색어 변경 시 debounce 300ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPage(1)
      router.replace(`/meetings?q=${encodeURIComponent(query)}&page=1`)
      fetchMeetings(query, 1)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query]) // eslint-disable-line react-hooks/exhaustive-deps

  // 페이지 변경 시 즉시 fetch
  useEffect(() => {
    fetchMeetings(query, page)
  }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    router.replace(`/meetings?q=${encodeURIComponent(query)}&page=${newPage}`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA]">
      <div className="max-w-6xl mx-auto px-4 py-6">

        {/* 헤더 */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/"
            className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            ← 돌아가기
          </Link>
          <h1 className="text-xl font-semibold text-gray-800">회의 목록</h1>
        </div>

        {/* 검색 바 */}
        <div className="relative mb-3">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="회의 제목 또는 내용으로 검색..."
            className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        {/* 건수 표시 */}
        {data && (
          <p className="text-xs text-gray-400 mb-4">
            총 {data.total}건 &middot; {data.pages}페이지 중 {data.page}페이지
          </p>
        )}

        {/* 카드 그리드 */}
        {!loading && data && data.items.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400 text-base mb-2">검색 결과가 없습니다</p>
            {query && (
              <button
                onClick={() => setQuery('')}
                className="text-sm text-blue-600 hover:underline"
              >
                검색어 초기화
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data?.items.map(job => <MeetingCard key={job.id} job={job} />)}
          </div>
        )}

        {/* 페이지네이션 */}
        {data && (
          <Pagination
            page={data.page}
            pages={data.pages}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </div>
  )
}

export default function MeetingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <MeetingsContent />
    </Suspense>
  )
}
