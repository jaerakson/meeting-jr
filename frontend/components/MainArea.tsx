'use client'

import { useState, useEffect, useCallback } from 'react'
import { Job } from '@/types'
import RecordingZone from './RecordingZone'
import ProgressCard from './ProgressCard'
import TranscriptEditor from './TranscriptEditor'
import AudioPlayer from './AudioPlayer'
import Transcript from './Transcript'
import SummaryPanel from './SummaryPanel'

interface EditData {
  transcript: string
  speakers: string[]
  suggestedNames: Record<string, string>
}

interface Props {
  job: Job | null
  onJobsChange: () => void
  onNewRecording: (jobId: string) => void
  onOpenSidebar: () => void
}

export default function MainArea({ job, onJobsChange, onNewRecording, onOpenSidebar }: Props) {
  const [currentTime, setCurrentTime] = useState(0)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState('')
  const [editData, setEditData] = useState<EditData | null>(null)
  const [isEditingTranscript, setIsEditingTranscript] = useState(false)
  const [localTranscript, setLocalTranscript] = useState('')
  const [resummaryLoading, setResummaryLoading] = useState(false)

  useEffect(() => {
    if (job) setTitleValue(job.title || '')
  }, [job?.id, job?.title])

  useEffect(() => {
    setIsEditingTranscript(false)
    setLocalTranscript('')
    setNotionUrl(job?.notion_url ?? null)
  }, [job?.id])

  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  const handleTitleSave = async () => {
    if (!job || !titleValue.trim()) { setEditingTitle(false); return }
    setEditingTitle(false)
    await fetch(`/api/jobs/${job.id}/title`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: titleValue }),
    })
    onJobsChange()
  }

  const handleTimeClick = useCallback((sec: number) => {
    window.dispatchEvent(new CustomEvent('audio-seek', { detail: { time: sec } }))
  }, [])

  const downloadTranscript = () => {
    if (!job?.transcript) return
    const blob = new Blob([job.transcript], { type: 'text/plain;charset=utf-8' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `${job.title || '스크립트'}_스크립트.txt`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const handleStartEditTranscript = () => {
    setLocalTranscript(job?.transcript || '')
    setIsEditingTranscript(true)
  }

  const handleCancelEditTranscript = () => {
    setIsEditingTranscript(false)
    setLocalTranscript('')
  }

  const handleSaveTranscript = async () => {
    if (!job) return
    setResummaryLoading(true)
    try {
      await fetch(`/api/jobs/${job.id}/transcript`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: localTranscript || job.transcript }),
      })
      setIsEditingTranscript(false)
      setLocalTranscript('')
      onJobsChange()
    } catch {
      alert('저장에 실패했습니다.')
    } finally {
      setResummaryLoading(false)
    }
  }

  const handleResummarize = async () => {
    if (!job) return
    setResummaryLoading(true)
    try {
      const speaker_map = job.speakers || {}
      await fetch(`/api/jobs/${job.id}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: localTranscript || job.transcript, speaker_map }),
      })
      setIsEditingTranscript(false)
      setLocalTranscript('')
      onJobsChange()
    } catch {
      alert('재요약 요청에 실패했습니다.')
    } finally {
      setResummaryLoading(false)
    }
  }

  const [notionUrl, setNotionUrl] = useState<string | null>(null)
  const [showNotionConfirm, setShowNotionConfirm] = useState(false)
  const [notionLoading, setNotionLoading] = useState(false)

  const handleExportNotion = async () => {
    if (!job) return
    if (job.notion_page_id) {
      setShowNotionConfirm(true)
      return
    }
    await doExportNotion('new')
  }

  const doExportNotion = async (mode: 'update' | 'new') => {
    setShowNotionConfirm(false)
    if (!job) return
    setNotionLoading(true)
    try {
      const res = await fetch(`/api/jobs/${job.id}/export-notion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      })
      const data = await res.json()
      if (!res.ok) {
        alert(`Notion 내보내기 실패:\n${data.detail || '알 수 없는 오류'}`)
      } else {
        setNotionUrl(data.url || null)
        onJobsChange()
      }
    } catch {
      alert('Notion 내보내기 요청에 실패했습니다.')
    } finally {
      setNotionLoading(false)
    }
  }

  const handleAwaitingEdit = (transcript: string, speakers: string[], suggestedNames: Record<string, string>) => {
    if (transcript) {
      setEditData({ transcript, speakers, suggestedNames })
    }
    onJobsChange()
  }

  const renderContent = () => {
    if (!job) return <RecordingZone onRecordingComplete={onNewRecording} />

    const status = job.status
    if (['pending', 'converting', 'diarizing', 'transcribing'].includes(status)) {
      return (
        <ProgressCard
          jobId={job.id}
          onDone={() => { onJobsChange() }}
          onAwaitingEdit={handleAwaitingEdit}
        />
      )
    }

    if (status === 'awaiting_edit') {
      if (editData) {
        return (
          <TranscriptEditor
            jobId={job.id}
            initialTranscript={editData.transcript}
            initialSpeakers={editData.speakers}
            suggestedNames={editData.suggestedNames}
            initialCategoryId={job.category_id || 'meeting'}
            onComplete={() => { setEditData(null); onJobsChange() }}
          />
        )
      }
      if (job.transcript) {
        return (
          <TranscriptEditor
            jobId={job.id}
            initialTranscript={job.transcript}
            initialSpeakers={Object.keys(job.speakers || {})}
            suggestedNames={job.speakers || {}}
            initialCategoryId={job.category_id || 'meeting'}
            onComplete={() => { setEditData(null); onJobsChange() }}
          />
        )
      }
    }

    if (status === 'summarizing') {
      return (
        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-gray-600 font-medium">회의록 생성 중...</p>
            <p className="text-sm text-gray-400 mt-1">Claude가 요약하고 있습니다</p>
          </div>
        </div>
      )
    }

    if (status === 'error') {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <p className="font-medium text-gray-700">처리 실패</p>
            <p className="text-sm text-gray-400 mt-1">{job.error_msg}</p>
            <button
              onClick={async () => { await fetch(`/api/jobs/${job.id}/retry`, { method: 'POST' }); onJobsChange() }}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            >재시도</button>
          </div>
        </div>
      )
    }

    if (status === 'done') {
      return (
        <div className="flex-1 flex flex-col min-h-0">
          <AudioPlayer
            audioSrc={`/api/jobs/${job.id}/audio`}
            onTimeUpdate={setCurrentTime}
          />
          <div className="flex-1 flex flex-col md:flex-row min-h-0">
            <div className="md:w-[55%] flex flex-col min-h-0 border-b md:border-b-0 md:border-r h-1/2 md:h-auto">
              <div className="px-4 py-2 border-b bg-gray-50 flex items-center justify-between flex-shrink-0">
                <span className="text-xs font-medium text-gray-500">대화 스크립트</span>
                <div className="flex items-center gap-2">
                  {isEditingTranscript ? (
                    <>
                      <button
                        onClick={handleCancelEditTranscript}
                        disabled={resummaryLoading}
                        className="text-xs px-2 py-1 text-gray-500 hover:text-gray-700 transition-colors disabled:opacity-40"
                      >
                        취소
                      </button>
                      <button
                        onClick={handleSaveTranscript}
                        disabled={resummaryLoading}
                        className="text-xs px-3 py-1 border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-700 rounded-md font-medium transition-colors"
                      >
                        {resummaryLoading ? '저장 중...' : '저장'}
                      </button>
                      <button
                        onClick={handleResummarize}
                        disabled={resummaryLoading}
                        className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md font-medium transition-colors"
                      >
                        {resummaryLoading ? '처리 중...' : '재요약'}
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={downloadTranscript}
                        className="text-xs px-2 py-1 border rounded hover:bg-white text-gray-600 transition-colors"
                      >
                        ↓ TXT
                      </button>
                      <a
                        href={`/api/jobs/${job.id}/audio`}
                        download
                        className="text-xs px-2 py-1 border rounded hover:bg-white text-gray-600 transition-colors"
                      >
                        ↓ 음성
                      </a>
                      <button
                        onClick={handleStartEditTranscript}
                        className="text-xs px-2 py-1 border rounded hover:bg-white text-gray-600 transition-colors"
                      >
                        편집
                      </button>
                    </>
                  )}
                </div>
              </div>
              <Transcript
                transcript={job.transcript || ''}
                currentTime={currentTime}
                onTimeClick={handleTimeClick}
                editable={isEditingTranscript}
                onTranscriptChange={setLocalTranscript}
              />
            </div>
            <div className="md:w-[45%] flex flex-col min-h-0 p-4 h-1/2 md:h-auto">
              <SummaryPanel summary={job.summary || ''} jobId={job.id} onSummaryUpdate={onJobsChange} speakers={job.speakers} />
            </div>
          </div>
        </div>
      )
    }

    return <RecordingZone onRecordingComplete={onNewRecording} />
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="px-4 py-3 border-b bg-white flex items-center justify-between flex-shrink-0">
        {/* 햄버거 버튼 (모바일 전용) */}
        <button
          onClick={onOpenSidebar}
          className="md:hidden p-1.5 rounded-lg hover:bg-gray-100 text-gray-600 transition-colors mr-2 flex-shrink-0"
          aria-label="메뉴 열기"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        {job ? (
          <>
            {editingTitle ? (
              <input
                autoFocus
                value={titleValue}
                onChange={e => setTitleValue(e.target.value)}
                onBlur={handleTitleSave}
                onKeyDown={e => e.key === 'Enter' && handleTitleSave()}
                className="text-lg font-semibold outline-none border-b-2 border-blue-500 bg-transparent flex-1 mr-4"
              />
            ) : (
              <h1
                className="text-base md:text-lg font-semibold text-gray-800 cursor-pointer hover:text-blue-600 flex-1 mr-2 truncate"
                onClick={() => setEditingTitle(true)}
                title="클릭하여 제목 편집"
              >
                {titleValue || '회의'}
              </h1>
            )}
            <div className="flex items-center gap-2 flex-shrink-0">
              {notionUrl && (
                <a
                  href={notionUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs md:text-sm text-blue-600 hover:text-blue-700 underline"
                >
                  Notion에서 보기 ↗
                </a>
              )}
              <button
                onClick={handleExportNotion}
                disabled={notionLoading}
                className="text-xs md:text-sm px-2 md:px-3 py-1.5 border rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-60 flex items-center gap-1.5 transition-colors"
              >
                {notionLoading ? (
                  <>
                    <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {job?.notion_page_id ? '업데이트 중...' : '전송 중...'}
                  </>
                ) : (
                  job?.notion_page_id ? '노션 업데이트' : '노션 보내기'
                )}
              </button>
            </div>
          </>
        ) : (
          <h1 className="text-base font-semibold text-gray-500">Meeting Jr.</h1>
        )}
      </div>
      {renderContent()}
      {showNotionConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
            <h3 className="font-semibold text-gray-800">Notion 내보내기</h3>
            <p className="text-sm text-gray-500">이미 Notion에 등록된 회의입니다.<br/>어떻게 진행할까요?</p>
            <div className="flex flex-col gap-2">
              <button onClick={() => doExportNotion('update')}
                disabled={notionLoading}
                className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg text-sm font-medium">
                기존 페이지 업데이트
              </button>
              <button onClick={() => doExportNotion('new')}
                disabled={notionLoading}
                className="w-full py-2 px-4 border border-gray-300 hover:bg-gray-50 disabled:opacity-60 text-gray-700 rounded-lg text-sm font-medium">
                새 페이지로 추가
              </button>
              <button onClick={() => setShowNotionConfirm(false)}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600">
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
