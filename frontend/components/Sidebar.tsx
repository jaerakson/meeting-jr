'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Job } from '@/types'
import { useTheme } from '@/hooks/useTheme'
import SettingsModal from './SettingsModal'

interface SidebarProps {
  jobs: Job[]
  selectedJobId: string | null
  onSelectJob: (id: string | null) => void
  onJobsChange: () => void
  onNewRecording: () => void
  onClose?: () => void
  onCollapse?: () => void
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatDuration(sec?: number): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m === 0) return `${s}초`
  return `${m}분`
}

export default function Sidebar({ jobs, selectedJobId, onSelectJob, onJobsChange, onNewRecording, onClose, onCollapse }: SidebarProps) {
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; jobId: string } | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [editingJobId, setEditingJobId] = useState<string | null>(null)
  const [editTitleValue, setEditTitleValue] = useState('')
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    if (contextMenu) {
      document.addEventListener('click', handleClick)
      return () => document.removeEventListener('click', handleClick)
    }
  }, [contextMenu])

  const handleBookmark = async (jobId: string) => {
    try {
      await fetch(`/api/jobs/${jobId}/bookmark`, { method: 'PATCH' })
      onJobsChange()
    } catch {
      // silent fail
    }
  }

  const handleDelete = async (jobId: string) => {
    if (!confirm('이 회의를 삭제하시겠습니까?')) return
    try {
      const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('삭제 실패')
      if (selectedJobId === jobId) onSelectJob(null)
      onJobsChange()
    } catch {
      alert('삭제에 실패했습니다.')
    }
  }

  const handleRetry = async (jobId: string) => {
    try {
      const res = await fetch(`/api/jobs/${jobId}/retry`, { method: 'POST' })
      if (!res.ok) throw new Error('재시도 실패')
      onJobsChange()
      onSelectJob(jobId)
    } catch {
      alert('재시도에 실패했습니다.')
    }
  }

  const handleContextMenu = (e: React.MouseEvent, jobId: string) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY, jobId })
  }

  const handleTitleSave = async (jobId: string) => {
    const trimmed = editTitleValue.trim()
    setEditingJobId(null)
    if (!trimmed) return
    try {
      await fetch(`/api/jobs/${jobId}/title`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: trimmed }),
      })
      onJobsChange()
    } catch {
      // silent fail
    }
  }

  const isProcessing = (status: string) =>
    ['pending', 'converting', 'diarizing', 'transcribing', 'summarizing'].includes(status)

  return (
    <aside className="w-72 md:w-60 flex-shrink-0 bg-sidebar-bg text-sidebar-text flex flex-col h-full">
      {/* 로고 */}
      <div className="px-4 py-5 border-b border-slate-600 flex items-center justify-between">
        <h1 className="text-xl font-bold">Meeting Jr.</h1>
        <div className="flex items-center gap-1">
          {onCollapse && (
            <button
              onClick={onCollapse}
              className="hidden md:flex p-1 rounded hover:bg-slate-600 text-slate-300 transition-colors"
              aria-label="사이드바 접기"
              title="사이드바 접기 ( [ )"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              </svg>
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="md:hidden p-1 rounded hover:bg-slate-600 text-slate-300 transition-colors"
              aria-label="닫기"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* 녹음 버튼 */}
      <div className="px-3 py-3">
        <button
          onClick={onNewRecording}
          className="w-full py-2.5 px-4 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
        >
          <span className="w-2 h-2 rounded-full bg-white" />
          새 회의 녹음
        </button>
      </div>

      {/* 전체 목록 보기 */}
      <div className="px-3 pb-2">
        <Link
          href="/meetings"
          className="w-full py-1.5 px-3 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg text-xs transition-colors flex items-center gap-2"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          전체 목록 보기
        </Link>
      </div>

      {/* 회의 목록 */}
      <div className="flex-1 overflow-y-auto">
        {jobs.length === 0 && (
          <p className="text-slate-400 text-sm text-center py-8 px-4">
            아직 회의가 없습니다.
          </p>
        )}
        {jobs.map((job) => (
          <div
            key={job.id}
            onClick={() => onSelectJob(job.id)}
            onContextMenu={(e) => handleContextMenu(e, job.id)}
            className={`group px-4 py-3 cursor-pointer border-b border-slate-700 hover:bg-slate-700 transition-colors ${
              selectedJobId === job.id ? 'bg-slate-600' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              {job.status === 'done' && (
                <span className="w-2.5 h-2.5 rounded-full bg-green-400 flex-shrink-0" />
              )}
              {job.status === 'error' && (
                <span className="w-2.5 h-2.5 rounded-full bg-red-400 flex-shrink-0" />
              )}
              {job.status === 'awaiting_edit' && (
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 flex-shrink-0" title="편집 대기 중" />
              )}
              {isProcessing(job.status) && (
                <svg className="w-3.5 h-3.5 animate-spin text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {editingJobId === job.id ? (
                <input
                  autoFocus
                  value={editTitleValue}
                  onChange={e => setEditTitleValue(e.target.value)}
                  onBlur={() => handleTitleSave(job.id)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleTitleSave(job.id)
                    if (e.key === 'Escape') setEditingJobId(null)
                  }}
                  onClick={e => e.stopPropagation()}
                  className="text-sm font-medium flex-1 bg-transparent outline-none border-b border-blue-400 text-white mr-1"
                />
              ) : (
                <span
                  className="text-sm font-medium truncate flex-1"
                  onDoubleClick={e => {
                    e.stopPropagation()
                    setEditTitleValue(job.title || job.filename || '')
                    setEditingJobId(job.id)
                  }}
                >
                  {job.title || job.filename}
                </span>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); handleBookmark(job.id) }}
                className={`p-0.5 transition-all flex-shrink-0 ${
                  job.bookmarked
                    ? 'text-yellow-400 opacity-100'
                    : 'text-slate-400 opacity-0 group-hover:opacity-100 hover:text-yellow-400'
                }`}
                title="북마크"
              >
                {job.bookmarked ? '★' : '☆'}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(job.id)
                }}
                className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1 md:p-0.5 rounded hover:bg-slate-500 text-slate-400 hover:text-red-300 transition-all flex-shrink-0"
                title="삭제"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
              {job.notion_url && (
                <a
                  href={job.notion_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="text-xs px-1.5 py-0.5 bg-slate-600 hover:bg-slate-500 rounded text-slate-300 flex-shrink-0"
                  title="Notion에서 열기"
                >
                  N
                </a>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
              <span>{formatDate(job.created_at)}</span>
              {job.duration_sec != null && <span>{formatDuration(job.duration_sec)}</span>}
            </div>
            {job.tags && job.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {job.tags.slice(0, 3).map(tag => (
                  <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-slate-600 text-slate-300 rounded-full">{tag}</span>
                ))}
                {job.tags.length > 3 && <span className="text-[10px] text-slate-500">+{job.tags.length - 3}</span>}
              </div>
            )}
            {job.status === 'error' && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleRetry(job.id)
                }}
                className="mt-1.5 text-xs text-red-300 hover:text-red-100 underline"
              >
                재시도
              </button>
            )}
          </div>
        ))}
      </div>

      {/* 하단 버튼 */}
      <div className="px-3 py-3 border-t border-slate-600 flex items-center gap-1">
        <button
          onClick={() => setShowSettings(true)}
          className="flex-1 py-2 px-3 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg text-sm transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          설정
        </button>
        <button
          onClick={toggleTheme}
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg transition-colors"
          title={theme === 'dark' ? '라이트 모드' : '다크 모드'}
        >
          {theme === 'dark' ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
      </div>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      {/* 컨텍스트 메뉴 */}
      {contextMenu && (
        <div
          className="fixed bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg shadow-xl border border-gray-200 dark:border-gray-600 py-1 z-50"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            onClick={() => {
              handleDelete(contextMenu.jobId)
              setContextMenu(null)
            }}
            className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 text-red-600 dark:text-red-400"
          >
            삭제
          </button>
        </div>
      )}
    </aside>
  )
}
