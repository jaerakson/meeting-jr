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

interface Category {
  id: string
  name: string
  icon: string
}

interface Stats {
  total: number
  this_week: number
  by_category: { id: string; count: number }[]
}

function MeetingsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1)
  const [categoryId, setCategoryId] = useState(searchParams.get('category') || '')
  const [dateFrom, setDateFrom] = useState(searchParams.get('from') || '')
  const [dateTo, setDateTo] = useState(searchParams.get('to') || '')
  const [data, setData] = useState<MeetingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState<Category[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [bookmarkOnly, setBookmarkOnly] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [tagFilter, setTagFilter] = useState(searchParams.get('tag') || '')
  const [allTags, setAllTags] = useState<string[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch('/api/categories')
      .then(r => r.ok ? r.json() : [])
      .then(setCategories)
      .catch(() => {})
    fetch('/api/stats')
      .then(r => r.ok ? r.json() : null)
      .then(setStats)
      .catch(() => {})
    fetch('/api/tags')
      .then(r => r.ok ? r.json() : [])
      .then(setAllTags)
      .catch(() => {})
  }, [])

  const buildUrl = (q: string, p: number, cat: string, from: string, to: string, t: string = '') => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (p > 1) params.set('page', String(p))
    if (cat) params.set('category', cat)
    if (from) params.set('from', from)
    if (to) params.set('to', to)
    if (t) params.set('tag', t)
    return `/meetings${params.toString() ? '?' + params.toString() : ''}`
  }

  const fetchMeetings = useCallback(async (q: string, p: number, cat: string, from: string, to: string, t: string = '') => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), limit: '12' })
      if (q) params.set('q', q)
      if (cat) params.set('category_id', cat)
      if (from) params.set('date_from', from)
      if (to) params.set('date_to', to)
      if (t) params.set('tag', t)
      const res = await fetch(`/api/meetings?${params.toString()}`)
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
      router.replace(buildUrl(query, 1, categoryId, dateFrom, dateTo, tagFilter))
      fetchMeetings(query, 1, categoryId, dateFrom, dateTo, tagFilter)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query]) // eslint-disable-line react-hooks/exhaustive-deps

  // 필터 변경 시 즉시
  useEffect(() => {
    setPage(1)
    router.replace(buildUrl(query, 1, categoryId, dateFrom, dateTo, tagFilter))
    fetchMeetings(query, 1, categoryId, dateFrom, dateTo, tagFilter)
  }, [categoryId, dateFrom, dateTo, tagFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  // 페이지 변경 시 즉시 fetch
  useEffect(() => {
    fetchMeetings(query, page, categoryId, dateFrom, dateTo, tagFilter)
    router.replace(buildUrl(query, page, categoryId, dateFrom, dateTo, tagFilter))
  }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetch('/api/export')
      if (res.ok) {
        const blob = await res.blob()
        const a = Object.assign(document.createElement('a'), {
          href: URL.createObjectURL(blob),
          download: `meetings-export-${new Date().toISOString().slice(0, 10)}.zip`,
        })
        a.click()
        URL.revokeObjectURL(a.href)
      }
    } finally {
      setExporting(false)
    }
  }

  const hasFilters = query || categoryId || dateFrom || dateTo || tagFilter
  const clearFilters = () => {
    setQuery('')
    setCategoryId('')
    setDateFrom('')
    setDateTo('')
    setTagFilter('')
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900">
      <div className="max-w-6xl mx-auto px-4 py-6">

        {/* 헤더 */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/"
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
          >
            ← 돌아가기
          </Link>
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 flex-1">회의 목록</h1>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 disabled:opacity-50 transition-colors"
          >
            {exporting ? '내보내는 중...' : '⬇ 전체 내보내기'}
          </button>
        </div>

        {/* 통계 카드 */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-3">
              <p className="text-xs text-gray-400 mb-0.5">전체 회의</p>
              <p className="text-2xl font-bold text-gray-800 dark:text-gray-100">{stats.total}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-3">
              <p className="text-xs text-gray-400 mb-0.5">이번 주</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.this_week}</p>
            </div>
            {stats.by_category.slice(0, 2).map(bc => {
              const cat = categories.find(c => c.id === bc.id)
              return (
                <div key={bc.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-3">
                  <p className="text-xs text-gray-400 mb-0.5">{cat ? `${cat.icon} ${cat.name}` : bc.id}</p>
                  <p className="text-2xl font-bold text-gray-800 dark:text-gray-100">{bc.count}</p>
                </div>
              )
            })}
          </div>
        )}

        {/* 검색 + 필터 영역 */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mb-4 space-y-3">
          {/* 검색 바 */}
          <div className="relative">
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
              className="w-full pl-10 pr-10 py-2.5 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-600"
            />
            {loading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            )}
          </div>

          {/* 필터 행 — 북마크 토글 포함 */}
          <div className="flex flex-wrap gap-2 items-center">
            {/* 카테고리 필터 */}
            <select
              value={categoryId}
              onChange={e => setCategoryId(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-600 cursor-pointer"
            >
              <option value="">전체 카테고리</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.icon} {cat.name}</option>
              ))}
            </select>

            {/* 날짜 범위 */}
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-600"
              />
              <span>~</span>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                min={dateFrom}
                className="border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-600"
              />
            </div>

            {/* 북마크 필터 */}
            <button
              onClick={() => setBookmarkOnly(b => !b)}
              className={`text-sm px-3 py-2 rounded-lg border transition-colors ${
                bookmarkOnly
                  ? 'border-yellow-400 bg-yellow-50 text-yellow-700'
                  : 'border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100'
              }`}
            >
              ★ 북마크만
            </button>

            {/* 태그 필터 */}
            {allTags.length > 0 && (
              <select
                value={tagFilter}
                onChange={e => setTagFilter(e.target.value)}
                className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-600 cursor-pointer"
              >
                <option value="">전체 태그</option>
                {allTags.map(tag => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
              </select>
            )}

            {/* 필터 초기화 */}
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1.5 rounded-lg hover:bg-red-50"
              >
                필터 초기화
              </button>
            )}
          </div>
        </div>

        {/* 건수 표시 */}
        {data && (
          <p className="text-xs text-gray-400 mb-4">
            총 {data.total}건 &middot; {data.pages}페이지 중 {data.page}페이지
            {categoryId && categories.find(c => c.id === categoryId) && (
              <span className="ml-2 bg-blue-100 text-blue-700 rounded-full px-2 py-0.5">
                {categories.find(c => c.id === categoryId)!.icon} {categories.find(c => c.id === categoryId)!.name}
              </span>
            )}
            {(dateFrom || dateTo) && (
              <span className="ml-2 bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
                {dateFrom || '처음'} ~ {dateTo || '현재'}
              </span>
            )}
          </p>
        )}

        {/* 카드 그리드 */}
        {!loading && data && data.items.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400 dark:text-gray-500 text-base mb-2">검색 결과가 없습니다</p>
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-blue-600 hover:underline"
              >
                필터 초기화
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data?.items
              .filter(job => !bookmarkOnly || job.bookmarked === 1)
              .map(job => <MeetingCard key={job.id} job={job} searchQuery={query} />)}
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
      <div className="min-h-screen bg-[#F8F9FA] dark:bg-gray-900 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <MeetingsContent />
    </Suspense>
  )
}
