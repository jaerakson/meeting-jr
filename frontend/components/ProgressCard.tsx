'use client'

import { useState, useEffect, useRef } from 'react'

interface ProgressCardProps {
  jobId: string
  onDone: () => void
  onAwaitingEdit: (transcript: string, speakers: string[], suggestedNames: Record<string, string>) => void
}

interface StageInfo {
  key: string
  label: string
}

const STAGES: StageInfo[] = [
  { key: 'converting', label: 'FFmpeg 변환' },
  { key: 'diarizing', label: '화자 분리' },
  { key: 'transcribing', label: 'STT 변환' },
]

interface ProgressState {
  stage: string
  progress: number
  message: string
  transcript?: string
  speakers?: string[]
  suggested_names?: Record<string, string>
}

export default function ProgressCard({ jobId, onDone, onAwaitingEdit }: ProgressCardProps) {
  const [state, setState] = useState<ProgressState>({
    stage: 'pending',
    progress: 0,
    message: '대기 중...',
  })
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  useEffect(() => {
    const connect = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }

      const es = new EventSource(`/api/progress/${jobId}`)
      eventSourceRef.current = es

      es.onmessage = (event) => {
        try {
          const data: ProgressState = JSON.parse(event.data)
          setState(data)

          if (data.stage === 'awaiting_edit') {
            es.close()
            onAwaitingEdit(
              data.transcript || '',
              data.speakers || [],
              data.suggested_names || {},
            )
          }

          if (data.stage === 'done') {
            es.close()
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification('회의록 완성', {
                body: '회의록이 완성됐습니다.',
                icon: '/favicon.ico',
              })
            }
            onDone()
          }

          if (data.stage === 'error') {
            es.close()
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification('처리 실패', {
                body: '처리 중 오류가 발생했습니다.',
                icon: '/favicon.ico',
              })
            }
          }
        } catch {
          // JSON 파싱 실패 무시
        }
      }

      es.onerror = () => {
        es.close()
        reconnectTimeoutRef.current = setTimeout(() => connect(), 3000)
      }
    }

    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [jobId, onDone, onAwaitingEdit])

  const getStageStatus = (stageKey: string): 'done' | 'active' | 'waiting' => {
    if (state.stage === 'awaiting_edit' || state.stage === 'done') {
      const transcribingIdx = STAGES.findIndex((s) => s.key === 'transcribing')
      const stageIdx = STAGES.findIndex((s) => s.key === stageKey)
      if (state.stage === 'done') return 'done'
      return stageIdx <= transcribingIdx ? 'done' : 'waiting'
    }

    const currentIdx = STAGES.findIndex((s) => s.key === state.stage)
    const stageIdx = STAGES.findIndex((s) => s.key === stageKey)

    if (stageIdx < currentIdx) return 'done'
    if (stageIdx === currentIdx) return 'active'
    return 'waiting'
  }

  return (
    <div className="flex items-center justify-center h-full p-4 md:p-8">
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-sm p-5 md:p-8">
        <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-6">처리 중...</h2>

        <div className="space-y-4">
          {STAGES.map((stage) => {
            const status = getStageStatus(stage.key)
            return (
              <div key={stage.key} className="flex items-center gap-3">
                {status === 'done' && (
                  <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {status === 'active' && (
                  <svg className="w-5 h-5 animate-spin text-accent flex-shrink-0" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                {status === 'waiting' && (
                  <span className="w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 flex-shrink-0" />
                )}

                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium ${
                      status === 'done' ? 'text-green-600 dark:text-green-400' :
                      status === 'active' ? 'text-gray-800 dark:text-gray-100' :
                      'text-gray-400'
                    }`}>
                      {stage.label}
                    </span>
                    <span className="text-xs text-gray-400">
                      {status === 'done' && '100%'}
                      {status === 'active' && `${state.progress}%`}
                      {status === 'waiting' && '대기 중...'}
                    </span>
                  </div>
                  {status === 'active' && (
                    <div className="mt-1.5 w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                      <div
                        className="bg-accent h-2 rounded-full transition-all duration-300"
                        style={{ width: `${state.progress}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {state.message && state.stage !== 'pending' && (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">{state.message}</p>
        )}

        {state.stage === 'error' && (
          <p className="mt-4 text-sm text-red-500">오류가 발생했습니다. 사이드바에서 재시도해 주세요.</p>
        )}
      </div>
    </div>
  )
}
