'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Pagination from '@/components/Pagination'

interface ActionItemRow {
  text: string
  assignee: string
  done: boolean
  job_id: string
  job_title: string
  job_created_at: string
}

interface ActionItemsResponse {
  items: ActionItemRow[]
  total: number
  page: number
  pages: number
  pending_count: number
  assignees: string[]
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function ActionItemsPage() {
  const router = useRouter()
  const [data, setData] = useState<ActionItemsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [assigneeFilter, setAssigneeFilter] = useState('')
  const [doneFilter, setDoneFilter] = useState<string>('')
  const [toggling, setToggling] = useState<string | null>(null)

  const fetchItems = useCallback(async (p: number, assignee: string, done: string) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), limit: '20' })
      if (assignee) params.set('assignee', assignee)
      if (done) params.set('done', done)
      const res = await fetch(`/api/action-items?${params.toString()}`)
      if (res.ok) setData(await res.json())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchItems(page, assigneeFilter, doneFilter)
  }, [page, assigneeFilter, doneFilter, fetchItems])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleToggleDone = async (item: ActionItemRow) => {
    if (!data) return
    const key = `${item.job_id}-${item.text}`
    setToggling(key)

    // Optimistic update
    const newDone = !item.done
    setData(prev => prev ? {
      ...prev,
      items: prev.items.map(i =>
        i.job_id === item.job_id && i.text === item.text && i.assignee === item.assignee
          ? { ...i, done: newDone }
          : i
      ),
      pending_count: prev.pending_count + (newDone ? -1 : 1),
    } : prev)

    try {
      // Collect all items for this job from current data
      const jobItems = data.items.filter(i => i.job_id === item.job_id)
      const actionItems = jobItems.map(i => ({
        text: i.text,
        assignee: i.assignee,
        done: (i.text === item.text && i.assignee === item.assignee) ? newDone : i.done,
      }))

      // If there might be items not on current page, fetch all for this job
      const allRes = await fetch(`/api/action-items?limit=100`)
      if (allRes.ok) {
        const allData: ActionItemsResponse = await allRes.json()
        const allJobItems = allData.items.filter(i => i.job_id === item.job_id)
        const fullActionItems = allJobItems.map(i => ({
          text: i.text,
          assignee: i.assignee,
          done: (i.text === item.text && i.assignee === item.assignee) ? newDone : i.done,
        }))

        await fetch(`/api/jobs/${item.job_id}/action-items`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action_items: fullActionItems.length > 0 ? fullActionItems : actionItems }),
        })
      } else {
        // Fallback: use what we have
        await fetch(`/api/jobs/${item.job_id}/action-items`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action_items: actionItems }),
        })
      }
    } catch {
      // Revert on error
      setData(prev => prev ? {
        ...prev,
        items: prev.items.map(i =>
          i.job_id === item.job_id && i.text === item.text && i.assignee === item.assignee
            ? { ...i, done: item.done }
            : i
        ),
        pending_count: prev.pending_count + (newDone ? 1 : -1),
      } : prev)
    } finally {
      setToggling(null)
    }
  }

  const assignees = data?.assignees ?? []

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
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 flex-1">
            액션 아이템
            {data && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                미완료 {data.pending_count}건
              </span>
            )}
          </h1>
        </div>

        {/* Filter bar */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mb-4">
          <div className="flex flex-wrap gap-3 items-center">
            <select
              value={assigneeFilter}
              onChange={e => { setAssigneeFilter(e.target.value); setPage(1) }}
              className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
            >
              <option value="">전체 담당자</option>
              {assignees.map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>

            <select
              value={doneFilter}
              onChange={e => { setDoneFilter(e.target.value); setPage(1) }}
              className="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
            >
              <option value="">전체 상태</option>
              <option value="false">미완료</option>
              <option value="true">완료</option>
            </select>

            {(assigneeFilter || doneFilter) && (
              <button
                onClick={() => { setAssigneeFilter(''); setDoneFilter(''); setPage(1) }}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1.5 rounded-lg hover:bg-red-50"
              >
                필터 초기화
              </button>
            )}

            {data && (
              <span className="text-xs text-gray-400 ml-auto">
                총 {data.total}건
              </span>
            )}
          </div>
        </div>

        {/* Item list */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
          {loading && !data ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : data && data.items.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-gray-400 dark:text-gray-500 text-base">
                {assigneeFilter || doneFilter ? '조건에 맞는 액션 아이템이 없습니다' : '액션 아이템이 없습니다'}
              </p>
            </div>
          ) : data && (
            <ul className="divide-y divide-gray-100 dark:divide-gray-700">
              {data.items.map((item, idx) => {
                const key = `${item.job_id}-${item.text}-${idx}`
                const isToggling = toggling === `${item.job_id}-${item.text}`
                return (
                  <li
                    key={key}
                    className={`flex items-start gap-3 px-4 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-750 ${
                      item.done ? 'opacity-60' : ''
                    }`}
                  >
                    {/* Checkbox */}
                    <button
                      onClick={() => handleToggleDone(item)}
                      disabled={isToggling}
                      className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        item.done
                          ? 'bg-green-500 border-green-500 text-white'
                          : 'border-gray-300 dark:border-gray-500 hover:border-blue-500'
                      } ${isToggling ? 'opacity-50' : ''}`}
                    >
                      {item.done && (
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm text-gray-800 dark:text-gray-200 ${item.done ? 'line-through' : ''}`}>
                        {item.text}
                      </p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {item.assignee && (
                          <span className="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300">
                            {item.assignee}
                          </span>
                        )}
                        <button
                          onClick={() => router.push(`/?job=${item.job_id}`)}
                          className="text-xs text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors truncate max-w-[200px]"
                          title={item.job_title}
                        >
                          {item.job_title}
                        </button>
                        <span className="text-xs text-gray-300 dark:text-gray-600">
                          {formatDate(item.job_created_at)}
                        </span>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Pagination */}
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
