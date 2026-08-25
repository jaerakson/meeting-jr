'use client'

import { useState, useEffect } from 'react'
import { VoiceProfile } from '@/types'

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
  const [saveAsProfile, setSaveAsProfile] = useState<Record<string, boolean>>({})
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([])
  const [profileTarget, setProfileTarget] = useState<Record<string, string>>({}) // 'new' or profile id

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
    fetch('/api/voice-profiles').then(r => r.json()).then(setVoiceProfiles).catch(() => {})
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

      // 프로필 저장 요청
      const savePromises = speakers
        .filter(sp => saveAsProfile[sp] && nameMap[sp]?.trim())
        .map(async sp => {
          const target = profileTarget[sp] || 'new'
          if (target === 'new') {
            await fetch(`/api/jobs/${jobId}/save-speaker-profile`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ speaker_label: sp, profile_name: nameMap[sp].trim() }),
            })
          } else {
            await fetch(`/api/jobs/${jobId}/save-speaker-profile`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ speaker_label: sp, profile_id: target }),
            })
          }
        })
      await Promise.allSettled(savePromises)

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
          <div key={speaker} className="space-y-1.5">
            <div className="flex items-center gap-3">
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
            <div className="ml-[7.5rem] flex items-center gap-2">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={saveAsProfile[speaker] || false}
                  onChange={e => setSaveAsProfile(prev => ({ ...prev, [speaker]: e.target.checked }))}
                  className="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-xs text-gray-500">이 목소리를 프로필로 저장</span>
              </label>
              {saveAsProfile[speaker] && (
                <select
                  value={profileTarget[speaker] || 'new'}
                  onChange={e => setProfileTarget(prev => ({ ...prev, [speaker]: e.target.value }))}
                  className="px-2 py-0.5 border border-gray-300 rounded text-xs text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="new">새 프로필 ({nameMap[speaker] || speaker})</option>
                  {voiceProfiles.map(vp => (
                    <option key={vp.id} value={vp.id}>기존: {vp.name}</option>
                  ))}
                </select>
              )}
            </div>
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
