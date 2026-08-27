'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { ClaudeStatus, RecordingNote } from '@/types'
import CategorySelect from './CategorySelect'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

interface Props {
  onRecordingComplete: (jobId: string) => void
}

const CATEGORY_KEY = 'meeting-jr-last-category'
const ALLOWED_EXTENSIONS = '.mp3,.m4a,.wav,.mp4,.webm,.ogg,.txt'
const ALLOWED_DISPLAY = 'mp3, m4a, wav, mp4, webm, ogg, txt'

export default function RecordingZone({ onRecordingComplete }: Props) {
  const [claudeStatus, setClaudeStatus] = useState<ClaudeStatus | null>(null)
  const [activeTab, setActiveTab] = useState<'record' | 'upload'>('record')
  const [isRecording, setIsRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [categoryId, setCategoryId] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(CATEGORY_KEY) || 'meeting'
    }
    return 'meeting'
  })
  const [seconds, setSeconds] = useState(0)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [fileUploading, setFileUploading] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [language, setLanguage] = useState('ko')
  const [notes, setNotes] = useState<RecordingNote[]>([])
  const [noteInput, setNoteInput] = useState('')
  const notesRef = useRef<RecordingNote[]>([])
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const isCancelRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const updateNotes = (updater: (prev: RecordingNote[]) => RecordingNote[]) => {
    setNotes(prev => {
      const next = updater(prev)
      notesRef.current = next
      return next
    })
  }

  const addBookmark = () => {
    const note: RecordingNote = {
      id: crypto.randomUUID(),
      timestamp: seconds,
    }
    updateNotes(prev => [...prev, note])
  }

  const addNote = () => {
    const text = noteInput.trim()
    if (!text) return
    const note: RecordingNote = {
      id: crypto.randomUUID(),
      timestamp: seconds,
      content: text,
    }
    updateNotes(prev => [...prev, note])
    setNoteInput('')
  }

  const removeNote = (id: string) => {
    updateNotes(prev => prev.filter(n => n.id !== id))
  }

  const sendNotes = async (jobId: string) => {
    const current = notesRef.current
    if (current.length === 0) return
    try {
      await fetch(`/api/jobs/${jobId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: current }),
      })
    } catch {
      // silent fail - notes are non-critical
    }
  }

  const handleCategoryChange = (id: string) => {
    setCategoryId(id)
    localStorage.setItem(CATEGORY_KEY, id)
  }

  const formatTime = (s: number) => {
    const h = Math.floor(s / 3600).toString().padStart(2, '0')
    const m = Math.floor((s % 3600) / 60).toString().padStart(2, '0')
    const sec = (s % 60).toString().padStart(2, '0')
    return `${h}:${m}:${sec}`
  }

  const drawWave = () => {
    if (!analyserRef.current || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')!
    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)
    const draw = () => {
      animFrameRef.current = requestAnimationFrame(draw)
      analyserRef.current!.getByteTimeDomainData(dataArray)
      const isDark = document.documentElement.classList.contains('dark')
      ctx.fillStyle = isDark ? '#1E293B' : '#F8F9FA'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.lineWidth = 2
      ctx.strokeStyle = isDark ? '#F87171' : '#EF4444'
      ctx.beginPath()
      const sliceWidth = canvas.width / bufferLength
      let x = 0
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0
        const y = (v * canvas.height) / 2
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
        x += sliceWidth
      }
      ctx.lineTo(canvas.width, canvas.height / 2)
      ctx.stroke()
    }
    draw()
  }

  const getSupportedMimeType = () => {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4;codecs=mp4a.40.2',
      'audio/mp4',
      'audio/ogg;codecs=opus',
    ]
    return candidates.find(t => MediaRecorder.isTypeSupported(t)) || ''
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
      analyserRef.current = analyser
      const mimeType = getSupportedMimeType()
      const recorderOptions = mimeType ? { mimeType } : {}
      const recorder = new MediaRecorder(stream, recorderOptions)
      mediaRecorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        cancelAnimationFrame(animFrameRef.current)
        if (isCancelRef.current) {
          isCancelRef.current = false
          setIsRecording(false)
          setIsPaused(false)
          setSeconds(0)
          updateNotes(() => [])
          setNoteInput('')
          chunksRef.current = []
          return
        }
        const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' })
        setAudioBlob(blob)
        setIsRecording(false)
        await uploadRecording(blob)
      }
      recorder.start(100)
      setIsRecording(true)
      setSeconds(0)
      setAudioBlob(null)
      setUploadDone(false)
      timerRef.current = setInterval(() => setSeconds(s => s + 1), 1000)
    } catch {
      alert('마이크 접근 권한이 필요합니다.')
    }
  }

  const pauseRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.pause()
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = null
      cancelAnimationFrame(animFrameRef.current)
      setIsPaused(true)
    }
  }

  const resumeRecording = () => {
    if (mediaRecorderRef.current?.state === 'paused') {
      mediaRecorderRef.current.resume()
      timerRef.current = setInterval(() => setSeconds(s => s + 1), 1000)
      setIsPaused(false)
    }
  }

  const stopRecording = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setIsPaused(false)
    mediaRecorderRef.current?.stop()
  }

  const cancelRecording = () => {
    isCancelRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    cancelAnimationFrame(animFrameRef.current)
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    } else {
      isCancelRef.current = false
      setIsRecording(false)
      setIsPaused(false)
      setSeconds(0)
    }
  }

  const uploadRecording = async (blob: Blob) => {
    setUploading(true)
    const formData = new FormData()
    formData.append('audio', blob, 'recording.webm')
    formData.append('category_id', categoryId)
    formData.append('language', language)
    try {
      const res = await fetch('/api/record', { method: 'POST', body: formData })
      const data = await res.json()
      await sendNotes(data.job_id)
      updateNotes(() => [])
      setUploadDone(true)
      onRecordingComplete(data.job_id)
    } catch {
      alert('업로드 실패. 다시 시도해주세요.')
    } finally {
      setUploading(false)
    }
  }

  const downloadAudio = () => {
    if (!audioBlob) return
    const url = URL.createObjectURL(audioBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `녹음_${new Date().toISOString().slice(0,10)}.webm`
    a.click()
    URL.revokeObjectURL(url)
  }

  const uploadFile = async (file: File) => {
    setFileUploading(true)
    setFileError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('category_id', categoryId)
      formData.append('language', language)
      const res = await fetch('/api/upload', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '업로드 실패')
      }
      const data = await res.json()
      onRecordingComplete(data.job_id)
    } catch (e: any) {
      setFileError(e.message)
    } finally {
      setFileUploading(false)
    }
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
    e.target.value = ''
  }

  useEffect(() => {
    fetch('/api/settings/claude-status')
      .then(r => r.json())
      .then(setClaudeStatus)
      .catch(() => setClaudeStatus({ installed: false, logged_in: false }))
  }, [])

  useEffect(() => {
    if (isRecording && !isPaused && analyserRef.current && canvasRef.current) {
      drawWave()
    }
    return () => {
      cancelAnimationFrame(animFrameRef.current)
    }
  }, [isRecording, isPaused])

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current)
    cancelAnimationFrame(animFrameRef.current)
  }, [])

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      if (isPaused) {
        resumeRecording()
      } else {
        pauseRecording()
      }
    } else if (!audioBlob) {
      startRecording()
    }
  }, [isRecording, isPaused, audioBlob])

  useKeyboardShortcuts({
    onSpaceRecord: toggleRecording,
    enabled: activeTab === 'record' && !uploading && !uploadDone,
  })

  // Claude 상태 확인 중
  if (!claudeStatus) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="w-6 h-6 border-2 border-gray-300 dark:border-gray-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Claude CLI 미설치
  if (!claudeStatus.installed) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 w-full max-w-md text-center space-y-4">
          <div className="text-3xl">🔧</div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">Claude CLI가 설치되어 있지 않습니다</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">회의록 요약을 위해 Claude CLI 설치가 필요합니다.</p>
          <div className="text-left bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2">
            <p className="text-xs font-medium text-gray-600 dark:text-gray-300">터미널에서 실행하세요:</p>
            <code className="block text-xs font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-600 rounded px-3 py-2">
              npm install -g @anthropic-ai/claude-code
            </code>
          </div>
          <p className="text-xs text-gray-400">설치 후 페이지를 새로고침하세요.</p>
        </div>
      </div>
    )
  }

  // Claude 로그아웃 상태
  if (!claudeStatus.logged_in) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 w-full max-w-md text-center space-y-4">
          <div className="text-3xl">🔐</div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">Claude 로그인이 필요합니다</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">회의록 요약을 위해 Claude CLI 로그인이 필요합니다.</p>
          <div className="text-left bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2">
            <p className="text-xs font-medium text-gray-600 dark:text-gray-300">터미널에서 아래 명령어를 실행하세요:</p>
            <code className="block text-xs font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-600 rounded px-3 py-2">
              claude auth login
            </code>
            <p className="text-xs text-gray-400 pt-1">브라우저가 열리면 Anthropic 계정으로 로그인하세요.</p>
          </div>
          <button
            onClick={() => {
              fetch('/api/settings/claude-status').then(r => r.json()).then(setClaudeStatus)
            }}
            className="text-sm px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            로그인 완료 — 상태 새로고침
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 md:p-10 w-full max-w-lg text-center">
        {/* Tab switcher */}
        <div className="flex gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1 mb-6">
          <button
            onClick={() => setActiveTab('record')}
            className={`flex-1 py-2 px-4 rounded-md text-sm transition-colors ${
              activeTab === 'record'
                ? 'bg-white dark:bg-gray-600 shadow-sm text-gray-800 dark:text-gray-100 font-medium'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            녹음
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex-1 py-2 px-4 rounded-md text-sm transition-colors ${
              activeTab === 'upload'
                ? 'bg-white dark:bg-gray-600 shadow-sm text-gray-800 dark:text-gray-100 font-medium'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            파일 업로드
          </button>
        </div>

        {/* Recording tab */}
        {activeTab === 'record' && (
          <>
            <div className="flex items-center justify-center gap-3 mb-6">
              {isRecording && <span className={`w-3 h-3 rounded-full bg-red-500 flex-shrink-0 ${isPaused ? '' : 'animate-pulse'}`} />}
              <span className="text-4xl md:text-5xl font-mono font-light text-gray-800 dark:text-gray-100 tracking-widest">{formatTime(seconds)}</span>
            </div>
            {isRecording && (
              <div className="relative mb-6">
                <canvas ref={canvasRef} width={400} height={60} className="w-full rounded-lg bg-gray-50 dark:bg-gray-700" />
                {isPaused && (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-50/70 dark:bg-gray-700/70 rounded-lg">
                    <span className="text-sm font-medium text-gray-500 dark:text-gray-400">일시정지됨</span>
                  </div>
                )}
              </div>
            )}
            {!isRecording && !audioBlob && (
              <>
                <div className="mb-3 flex gap-2">
                  <div className="flex-1">
                    <CategorySelect
                      value={categoryId}
                      onChange={handleCategoryChange}
                      className="w-full"
                    />
                  </div>
                  <select
                    value={language}
                    onChange={e => setLanguage(e.target.value)}
                    className="px-2 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="ko">🇰🇷 한국어</option>
                    <option value="en">🇺🇸 English</option>
                    <option value="ja">🇯🇵 日本語</option>
                    <option value="auto">🌐 자동</option>
                  </select>
                </div>
                <button onClick={startRecording} className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center mx-auto mb-4 transition-colors shadow-lg">
                  <span className="w-5 h-5 rounded-full bg-white" />
                </button>
                <p className="text-sm text-gray-400 dark:text-gray-500">버튼을 눌러 녹음을 시작하세요</p>
                <p className="text-xs text-gray-300 dark:text-gray-600 mt-2">Space: 녹음 시작 / 일시정지 / 재개</p>
              </>
            )}
            {isRecording && (
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <input
                    type="text"
                    value={noteInput}
                    onChange={e => setNoteInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addNote() } }}
                    placeholder="메모 입력..."
                    className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={addNote}
                    disabled={!noteInput.trim()}
                    className="px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-40 transition-colors flex-shrink-0"
                    title="메모 추가"
                  >
                    메모
                  </button>
                  <button
                    onClick={addBookmark}
                    className="w-10 h-10 flex items-center justify-center text-lg bg-yellow-100 hover:bg-yellow-200 dark:bg-yellow-900/40 dark:hover:bg-yellow-900/70 text-yellow-600 dark:text-yellow-400 rounded-lg transition-colors flex-shrink-0"
                    title="북마크 추가"
                  >
                    ⚑
                  </button>
                </div>
                {notes.length > 0 && (
                  <div className="max-h-28 overflow-y-auto space-y-1 text-left">
                    {notes.map(n => (
                      <div key={n.id} className="flex items-center gap-2 text-xs px-2 py-1 bg-gray-50 dark:bg-gray-700 rounded">
                        <span className="text-blue-500 font-mono flex-shrink-0">{formatTime(n.timestamp)}</span>
                        <span className="text-gray-600 dark:text-gray-300 flex-1 truncate">
                          {n.content || '⚑ 북마크'}
                        </span>
                        <button onClick={() => removeNote(n.id)} className="text-gray-400 hover:text-red-400 flex-shrink-0">&times;</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {isRecording && (
              <div className="flex items-center justify-center gap-4 mb-4">
                {isPaused ? (
                  <button onClick={resumeRecording} className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors shadow-lg" title="재개">
                    <svg className="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 24 24"><polygon points="8,5 19,12 8,19" /></svg>
                  </button>
                ) : (
                  <button onClick={pauseRecording} className="w-14 h-14 rounded-full bg-yellow-500 hover:bg-yellow-600 text-white flex items-center justify-center transition-colors shadow-lg" title="일시정지">
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14" /><rect x="14" y="5" width="4" height="14" /></svg>
                  </button>
                )}
                <button onClick={stopRecording} className="w-14 h-14 rounded-full bg-gray-700 hover:bg-gray-800 text-white flex items-center justify-center transition-colors shadow-lg" title="중지 및 처리">
                  <span className="w-4 h-4 rounded bg-white" />
                </button>
                <button onClick={cancelRecording} className="w-14 h-14 rounded-full bg-red-100 hover:bg-red-200 dark:bg-red-900/40 dark:hover:bg-red-900/70 text-red-500 dark:text-red-400 flex items-center justify-center transition-colors shadow-sm" title="녹음 삭제">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            )}
            {audioBlob && (
              <div className="space-y-3 mt-2">
                {uploading && <p className="text-blue-500 text-sm animate-pulse">서버로 전송 중...</p>}
                {uploadDone && <p className="text-green-600 text-sm font-medium">전송 완료 -- 처리 중...</p>}
                <button onClick={downloadAudio} className="text-sm px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors">
                  ↓ 음성 다운로드 (.webm)
                </button>
              </div>
            )}
          </>
        )}

        {/* File upload tab */}
        {activeTab === 'upload' && (
          <>
            <div className="mb-3 flex gap-2">
              <div className="flex-1">
                <CategorySelect
                  value={categoryId}
                  onChange={handleCategoryChange}
                  className="w-full"
                />
              </div>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value)}
                className="px-2 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-gray-50 dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ko">🇰🇷 한국어</option>
                <option value="en">🇺🇸 English</option>
                <option value="ja">🇯🇵 日本語</option>
                <option value="auto">🌐 자동</option>
              </select>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_EXTENSIONS}
              onChange={handleFileSelect}
              className="hidden"
            />
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => !fileUploading && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 cursor-pointer transition-colors ${
                isDragging
                  ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 bg-gray-50 dark:bg-gray-700'
              }`}
            >
              {fileUploading ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm text-blue-600 dark:text-blue-400 font-medium">업로드 중...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">파일을 여기에 끌어다 놓거나 클릭하세요</p>
                    <p className="text-xs text-gray-400 mt-1">지원 형식: {ALLOWED_DISPLAY}</p>
                  </div>
                </div>
              )}
            </div>
            {fileError && (
              <p className="text-sm text-red-500 mt-3">{fileError}</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
