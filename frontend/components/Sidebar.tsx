'use client'

import { useState, useEffect } from 'react'
import { Job } from '@/types'
import SettingsModal from './SettingsModal'

interface SidebarProps {
  jobs: Job[]
  selectedJobId: string | null
  onSelectJob: (id: string | null) => void
  onJobsChange: () => void
  onNewRecording: () => void
  onClose?: () => void
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

export default function Sidebar({ jobs, selectedJobId, onSelectJob, onJobsChange, onNewRecording, onClose }: SidebarProps) {
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; jobId: string } | null>(null)
  const [showSettings, setShowSettings] = useState(false)

  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    if (contextMenu) {
      document.addEventListener('click', handleClick)
      return () => document.removeEventListener('click', handleClick)
    }
  }, [contextMenu])

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

  const isProcessing = (status: string) =>
    ['pending', 'converting', 'diarizing', 'transcribing', 'summarizing'].includes(status)

  return (
    <aside className="w-72 md:w-60 flex-shrink-0 bg-sidebar-bg text-sidebar-text flex flex-col h-full">
      {/* 로고 */}
      <div className="px-4 py-5 border-b border-slate-600 flex items-center justify-between">
        <h1 className="text-xl font-bold">Meeting Jr.</h1>
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
            className={`px-4 py-3 cursor-pointer border-b border-slate-700 hover:bg-slate-700 transition-colors ${
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
              <span className="text-sm font-medium truncate">{job.title || job.filename}</span>
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

      {/* 설정 버튼 */}
      <div className="px-3 py-3 border-t border-slate-600">
        <button
          onClick={() => setShowSettings(true)}
          className="w-full py-2 px-3 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg text-sm transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          설정
        </button>
      </div>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      {/* 컨텍스트 메뉴 */}
      {contextMenu && (
        <div
          className="fixed bg-white text-gray-800 rounded-lg shadow-xl border border-gray-200 py-1 z-50"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            onClick={() => {
              handleDelete(contextMenu.jobId)
              setContextMenu(null)
            }}
            className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 text-red-600"
          >
            삭제
          </button>
        </div>
      )}
    </aside>
  )
}
