'use client'
import { useState, useRef, useEffect } from 'react'
import { ClaudeStatus } from '@/types'

interface Props {
  onRecordingComplete: (jobId: string) => void
}

export default function RecordingZone({ onRecordingComplete }: Props) {
  const [claudeStatus, setClaudeStatus] = useState<ClaudeStatus | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)

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
      ctx.fillStyle = '#F8F9FA'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.lineWidth = 2
      ctx.strokeStyle = '#EF4444'
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
      drawWave()
    } catch {
      alert('마이크 접근 권한이 필요합니다.')
    }
  }

  const stopRecording = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    mediaRecorderRef.current?.stop()
  }

  const uploadRecording = async (blob: Blob) => {
    setUploading(true)
    const formData = new FormData()
    formData.append('audio', blob, 'recording.webm')
    try {
      const res = await fetch('/api/record', { method: 'POST', body: formData })
      const data = await res.json()
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

  useEffect(() => {
    fetch('/api/settings/claude-status')
      .then(r => r.json())
      .then(setClaudeStatus)
      .catch(() => setClaudeStatus({ installed: false, logged_in: false }))
  }, [])

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current)
    cancelAnimationFrame(animFrameRef.current)
  }, [])

  // Claude 상태 확인 중
  if (!claudeStatus) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Claude CLI 미설치
  if (!claudeStatus.installed) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-2xl shadow-sm border p-8 w-full max-w-md text-center space-y-4">
          <div className="text-3xl">🔧</div>
          <h2 className="text-lg font-semibold text-gray-800">Claude CLI가 설치되어 있지 않습니다</h2>
          <p className="text-sm text-gray-500">회의록 요약을 위해 Claude CLI 설치가 필요합니다.</p>
          <div className="text-left bg-gray-50 rounded-lg p-4 space-y-2">
            <p className="text-xs font-medium text-gray-600">터미널에서 실행하세요:</p>
            <code className="block text-xs font-mono text-gray-800 bg-gray-100 rounded px-3 py-2">
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
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-2xl shadow-sm border p-8 w-full max-w-md text-center space-y-4">
          <div className="text-3xl">🔐</div>
          <h2 className="text-lg font-semibold text-gray-800">Claude 로그인이 필요합니다</h2>
          <p className="text-sm text-gray-500">회의록 요약을 위해 Claude CLI 로그인이 필요합니다.</p>
          <div className="text-left bg-gray-50 rounded-lg p-4 space-y-2">
            <p className="text-xs font-medium text-gray-600">터미널에서 아래 명령어를 실행하세요:</p>
            <code className="block text-xs font-mono text-gray-800 bg-gray-100 rounded px-3 py-2">
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
    <div className="flex-1 flex items-center justify-center bg-gray-50 p-4">
      <div className="bg-white rounded-2xl shadow-sm border p-6 md:p-10 w-full max-w-lg text-center">
        <div className="flex items-center justify-center gap-3 mb-6">
          {isRecording && <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse flex-shrink-0" />}
          <span className="text-4xl md:text-5xl font-mono font-light text-gray-800 tracking-widest">{formatTime(seconds)}</span>
        </div>
        {isRecording && (
          <canvas ref={canvasRef} width={400} height={60} className="w-full mb-6 rounded-lg bg-gray-50" />
        )}
        {!isRecording && !audioBlob && (
          <>
            <button onClick={startRecording} className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center mx-auto mb-4 transition-colors shadow-lg">
              <span className="w-5 h-5 rounded-full bg-white" />
            </button>
            <p className="text-sm text-gray-400">버튼을 눌러 녹음을 시작하세요</p>
          </>
        )}
        {isRecording && (
          <button onClick={stopRecording} className="w-16 h-16 rounded-full bg-gray-700 hover:bg-gray-800 text-white flex items-center justify-center mx-auto mb-4 transition-colors shadow-lg">
            <span className="w-5 h-5 rounded bg-white" />
          </button>
        )}
        {audioBlob && (
          <div className="space-y-3 mt-2">
            {uploading && <p className="text-blue-500 text-sm animate-pulse">서버로 전송 중...</p>}
            {uploadDone && <p className="text-green-600 text-sm font-medium">전송 완료 -- 처리 중...</p>}
            <button onClick={downloadAudio} className="text-sm px-4 py-2 border rounded-lg hover:bg-gray-50 text-gray-600 transition-colors">
              ↓ 음성 다운로드 (.webm)
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
