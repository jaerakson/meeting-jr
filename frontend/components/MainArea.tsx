'use client'

import { useState, useEffect, useCallback } from 'react'
import { Job, Category, RelatedMeeting } from '@/types'
import { useRouter } from 'next/navigation'
import RecordingZone from './RecordingZone'
import CategorySelect from './CategorySelect'
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
  onExpandSidebar?: () => void
  sidebarCollapsed?: boolean
}

export default function MainArea({ job, onJobsChange, onNewRecording, onOpenSidebar, onExpandSidebar, sidebarCollapsed }: Props) {
  const router = useRouter()
  const [currentTime, setCurrentTime] = useState(0)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState('')
  const [editData, setEditData] = useState<EditData | null>(null)
  const [isEditingTranscript, setIsEditingTranscript] = useState(false)
  const [localTranscript, setLocalTranscript] = useState('')
  const [resummaryLoading, setResummaryLoading] = useState(false)
  const [showResummarizeModal, setShowResummarizeModal] = useState(false)
  const [resummarizeCategory, setResummarizeCategory] = useState<string>('meeting')
  const [categories, setCategories] = useState<Category[]>([])
  const [relatedMeetings, setRelatedMeetings] = useState<RelatedMeeting[]>([])
  const [memo, setMemo] = useState('')
  const [memoSaved, setMemoSaved] = useState(false)
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (job?.status === 'done' && job.id) {
      fetch(`/api/jobs/${job.id}/related`)
        .then(r => r.json())
        .then(data => setRelatedMeetings(data.items || []))
        .catch(() => setRelatedMeetings([]))
    } else {
      setRelatedMeetings([])
    }
  }, [job?.id, job?.status])

  useEffect(() => {
    if (job) setTitleValue(job.title || '')
  }, [job?.id, job?.title])

  useEffect(() => {
    fetch('/api/categories').then(r => r.json()).then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    setIsEditingTranscript(false)
    setLocalTranscript('')
    setNotionUrl(job?.notion_url ?? null)
    setResummarizeCategory(job?.category_id || 'meeting')
    setMemo(job?.memo || '')
    setMemoSaved(false)
    setTags(job?.tags || [])
    setTagInput('')
  }, [job?.id])

  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  const saveTags = async (newTags: string[]) => {
    if (!job) return
    setTags(newTags)
    try {
      await fetch(`/api/jobs/${job.id}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: newTags }),
      })
    } catch {
      // silent fail
    }
  }

  const addTag = (raw: string) => {
    const tag = raw.trim()
    if (!tag || tags.includes(tag)) return
    saveTags([...tags, tag])
  }

  const removeTag = (tag: string) => {
    saveTags(tags.filter(t => t !== tag))
  }

  const saveMemo = async () => {
    if (!job) return
    try {
      await fetch(`/api/jobs/${job.id}/memo`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ memo }),
      })
      setMemoSaved(true)
      setTimeout(() => setMemoSaved(false), 2000)
    } catch {
      // silent fail
    }
  }

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

  const downloadMarkdown = () => {
    if (!job) return
    const date = job.created_at ? new Date(job.created_at).toLocaleDateString('ko-KR') : ''
    const lines = [
      `# ${job.title || '회의록'}`,
      date ? `\n날짜: ${date}` : '',
      job.summary ? `\n## 요약\n\n${job.summary}` : '',
      job.transcript ? `\n## 스크립트\n\n${job.transcript}` : '',
    ]
    const md = lines.filter(Boolean).join('\n')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `${job.title || '회의록'}.md`,
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

  const handleResummarize = async (categoryId?: string) => {
    if (!job) return
    setResummaryLoading(true)
    try {
      const speaker_map = job.speakers || {}
      await fetch(`/api/jobs/${job.id}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: localTranscript || job.transcript,
          speaker_map,
          category_id: categoryId || job.category_id || 'meeting',
        }),
      })
      setIsEditingTranscript(false)
      setLocalTranscript('')
      setShowResummarizeModal(false)
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
        <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-gray-600 dark:text-gray-300 font-medium">회의록 생성 중...</p>
            <p className="text-sm text-gray-400 mt-1">Claude가 요약하고 있습니다</p>
          </div>
        </div>
      )
    }

    if (status === 'error') {
      return (
        <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
          <div className="text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <p className="font-medium text-gray-700 dark:text-gray-200">처리 실패</p>
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
            <div className="md:w-[55%] flex flex-col min-h-0 border-b md:border-b-0 md:border-r border-gray-200 dark:border-gray-700 h-1/2 md:h-auto">
              <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex items-center justify-between flex-shrink-0">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">대화 스크립트</span>
                <div className="flex items-center gap-2">
                  {isEditingTranscript ? (
                    <>
                      <button
                        onClick={handleCancelEditTranscript}
                        disabled={resummaryLoading}
                        className="text-xs px-2 py-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors disabled:opacity-40"
                      >
                        취소
                      </button>
                      <button
                        onClick={handleSaveTranscript}
                        disabled={resummaryLoading}
                        className="text-xs px-3 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 text-gray-700 dark:text-gray-200 rounded-md font-medium transition-colors"
                      >
                        {resummaryLoading ? '저장 중...' : '저장'}
                      </button>
                      <button
                        onClick={() => { setResummarizeCategory(job?.category_id || 'meeting'); setShowResummarizeModal(true) }}
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
                        className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-white dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
                      >
                        ↓ TXT
                      </button>
                      <button
                        onClick={downloadMarkdown}
                        className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-white dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
                      >
                        ↓ MD
                      </button>
                      <a
                        href={`/api/jobs/${job.id}/audio`}
                        download
                        className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-white dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
                      >
                        ↓ 음성
                      </a>
                      <button
                        onClick={handleStartEditTranscript}
                        className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded hover:bg-white dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
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
              <SummaryPanel summary={job.summary || ''} jobId={job.id} onSummaryUpdate={onJobsChange} speakers={job.speakers} actionItems={job.action_items} categoryId={job.category_id} />
              <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
                <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">태그</h3>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {tags.map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 text-xs px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full">
                      {tag}
                      <button onClick={() => removeTag(tag)} className="hover:text-red-500 transition-colors">&times;</button>
                    </span>
                  ))}
                  <input
                    value={tagInput}
                    onChange={e => setTagInput(e.target.value)}
                    onKeyDown={e => {
                      if ((e.key === 'Enter' || e.key === ',') && tagInput.trim()) {
                        e.preventDefault()
                        addTag(tagInput.replace(',', ''))
                        setTagInput('')
                      }
                    }}
                    onBlur={() => { if (tagInput.trim()) { addTag(tagInput); setTagInput('') } }}
                    placeholder="태그 추가..."
                    className="text-xs px-2 py-1 bg-transparent border-b border-gray-200 dark:border-gray-600 focus:border-blue-400 outline-none text-gray-600 dark:text-gray-300 w-24"
                  />
                </div>
              </div>
              <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-4">
                <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">메모</h3>
                <textarea
                  value={memo}
                  onChange={e => setMemo(e.target.value)}
                  placeholder="회의 메모를 입력하세요..."
                  className="w-full h-24 px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
                <button onClick={saveMemo} className="mt-1 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">
                  {memoSaved ? '저장됨 ✓' : '저장'}
                </button>
              </div>
              {relatedMeetings.length > 0 && (
                <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
                  <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
                    관련 회의
                  </h3>
                  <div className="space-y-2">
                    {relatedMeetings.map(m => (
                      <div
                        key={m.id}
                        onClick={() => router.push(`/meetings/${m.id}`)}
                        className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                      >
                        <div>
                          <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{m.title}</p>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {m.matched_keywords.map(kw => (
                              <span key={kw} className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded">
                                {kw}
                              </span>
                            ))}
                          </div>
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0 ml-2">
                          {new Date(m.created_at).toLocaleDateString('ko-KR')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )
    }

    return <RecordingZone onRecordingComplete={onNewRecording} />
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex items-center justify-between flex-shrink-0">
        {/* 햄버거 버튼 (모바일 전용) */}
        <button
          onClick={onOpenSidebar}
          className="md:hidden p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors mr-2 flex-shrink-0"
          aria-label="메뉴 열기"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        {/* 사이드바 펼치기 버튼 (데스크탑, collapsed일 때만) */}
        {sidebarCollapsed && onExpandSidebar && (
          <button
            onClick={onExpandSidebar}
            className="hidden md:flex p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors mr-2 flex-shrink-0"
            aria-label="사이드바 펼치기"
            title="사이드바 펼치기 ( [ )"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        )}
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
                className="text-base md:text-lg font-semibold text-gray-800 dark:text-gray-100 cursor-pointer hover:text-blue-600 flex-1 mr-2 truncate"
                onClick={() => setEditingTitle(true)}
                title="클릭하여 제목 편집"
              >
                {titleValue || '회의'}
              </h1>
            )}
            {job.status === 'done' && (() => {
              const cat = categories.find(c => c.id === (job.category_id || 'meeting'))
              return cat ? (
                <span className="hidden md:inline-flex text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full flex-shrink-0 items-center gap-1">
                  {cat.icon} {cat.name}
                </span>
              ) : null
            })()}
            <div className="flex items-center gap-2 flex-shrink-0">
              {notionUrl ? (
                <a
                  href={notionUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden md:inline-flex text-xs px-2 py-0.5 bg-green-50 text-green-700 rounded-full items-center gap-1 hover:bg-green-100 transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  Notion ↗
                </a>
              ) : job?.status === 'done' && (
                <span className="hidden md:inline-flex text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full">
                  Notion 미등록
                </span>
              )}
              {job.status === 'done' && (
                <button
                  onClick={() => {
                    const url = `${window.location.origin}/meetings/${job.id}`
                    navigator.clipboard.writeText(url)
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  }}
                  className="text-xs md:text-sm px-2 md:px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 flex items-center gap-1.5 transition-colors"
                  title="링크 복사"
                >
                  {copied ? '복사됨!' : '링크'}
                </button>
              )}
              {job.status === 'done' && (
                <button
                  onClick={() => window.open(`/print/${job.id}`, '_blank')}
                  className="text-xs md:text-sm px-2 md:px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 flex items-center gap-1.5 transition-colors"
                  title="PDF로 저장"
                >
                  PDF
                </button>
              )}
              <button
                onClick={handleExportNotion}
                disabled={notionLoading}
                className="text-xs md:text-sm px-2 md:px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 disabled:opacity-60 flex items-center gap-1.5 transition-colors"
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
          <h1 className="text-base font-semibold text-gray-500 dark:text-gray-400">Meeting Jr.</h1>
        )}
      </div>
      {renderContent()}
      {showResummarizeModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-80 space-y-4">
            <h3 className="font-semibold text-gray-800 dark:text-gray-100">재요약 카테고리 선택</h3>
            <p className="text-sm text-gray-500">재요약에 사용할 카테고리를 선택하세요.</p>
            <CategorySelect
              value={resummarizeCategory}
              onChange={setResummarizeCategory}
              className="w-full"
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={() => handleResummarize(resummarizeCategory)}
                disabled={resummaryLoading}
                className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg text-sm font-medium"
              >
                {resummaryLoading ? '처리 중...' : '재요약 실행'}
              </button>
              <button
                onClick={() => setShowResummarizeModal(false)}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
      {showNotionConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-80 space-y-4">
            <h3 className="font-semibold text-gray-800 dark:text-gray-100">Notion 내보내기</h3>
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
