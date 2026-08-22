'use client'

import { useState, useEffect } from 'react'

interface SpeakerMapperProps {
  speakers: string[]
  jobId: string
  suggestedNames: Record<string, string>
  onComplete: () => void
}

export default function SpeakerMapper({ speakers, jobId, suggestedNames, onComplete }: SpeakerMapperProps) {
  const [nameMap, setNameMap] = useState<Record<string, string>>({})
  const [previousNames, setPreviousNames] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)

  // 이전 화자 이름 로드
  useEffect(() => {
    const loadPreviousNames = async () => {
      try {
        const res = await fetch('/api/speakers')
        if (res.ok) {
          const data = await res.json()
          setPreviousNames(data)
        }
      } catch {
        // 실패 시 무시
      }
    }
    loadPreviousNames()
  }, [])

  // 초기값: suggestedNames 또는 이전 이름
  useEffect(() => {
    const initial: Record<string, string> = {}
    speakers.forEach((speaker) => {
      initial[speaker] = suggestedNames[speaker] || previousNames[speaker] || ''
    })
    setNameMap(initial)
  }, [speakers, suggestedNames, previousNames])

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const res = await fetch(`/api/jobs/${jobId}/rename-speakers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speaker_map: nameMap }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || '화자 이름 적용에 실패했습니다.')
      }
      onComplete()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '화자 이름 적용에 실패했습니다.'
      alert(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h3 className="text-base font-bold text-gray-800 mb-4">화자를 확인해 주세요</h3>

      <div className="space-y-3">
        {speakers.map((speaker) => (
          <div key={speaker} className="flex items-center gap-3">
            <span className="text-sm text-gray-500 font-mono w-28 flex-shrink-0">
              {speaker}
            </span>
            <input
              type="text"
              value={nameMap[speaker] || ''}
              onChange={(e) =>
                setNameMap((prev) => ({ ...prev, [speaker]: e.target.value }))
              }
              placeholder={
                suggestedNames[speaker]
                  ? `${suggestedNames[speaker]} (이전 회의에서 기억됨)`
                  : '이름 입력'
              }
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
            />
          </div>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="mt-5 w-full py-2.5 bg-accent hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? '처리 중...' : '적용 및 회의록 생성'}
      </button>
    </div>
  )
}
