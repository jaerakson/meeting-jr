'use client'

import { useState, useEffect, useRef } from 'react'
import { SettingsStatus, ClaudeStatus, Category, VoiceProfile, Job } from '@/types'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

interface Props {
  onClose: () => void
  isDirtyRef?: React.MutableRefObject<boolean>
}

const KEY_LABELS: Record<string, string> = {
  HF_TOKEN: 'HuggingFace Token',
  NOTION_API_KEY: 'Notion API Key',
  NOTION_DATABASE_ID: 'Notion Database ID',
}

const KEYS = ['HF_TOKEN', 'NOTION_API_KEY', 'NOTION_DATABASE_ID'] as const

const CLAUDE_MODELS = [
  { value: "claude-sonnet-4-6",         label: "Sonnet 4.6 (기본, 권장)" },
  { value: "claude-opus-4-6",           label: "Opus 4.6 (고품질, 느림)" },
  { value: "claude-haiku-4-5-20251001", label: "Haiku 4.5 (빠름, 경량)" },
]

type Tab = 'general' | 'categories' | 'speakers'

export default function SettingsModal({ onClose, isDirtyRef }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('general')
  const [status, setStatus] = useState<SettingsStatus | null>(null)
  const [values, setValues] = useState<Record<string, string>>({
    HF_TOKEN: '',
    NOTION_API_KEY: '',
    NOTION_DATABASE_ID: '',
  })
  const [showKey, setShowKey] = useState<Record<string, boolean>>({
    HF_TOKEN: false,
    NOTION_API_KEY: false,
    NOTION_DATABASE_ID: false,
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [claudeStatus, setClaudeStatus] = useState<ClaudeStatus | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [denoiseEnabled, setDenoiseEnabled] = useState(false)

  // 화자 관련 상태
  const [speakers, setSpeakers] = useState<string[]>([])
  const [newSpeakerName, setNewSpeakerName] = useState('')
  const [speakerSaving, setSpeakerSaving] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [restoreResult, setRestoreResult] = useState<string | null>(null)

  // 목소리 프로필 관련 상태
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([])
  const [threshold, setThreshold] = useState(0.75)
  const [recordingForProfile, setRecordingForProfile] = useState(false)
  const [newProfileName, setNewProfileName] = useState('')
  const [extractFromJob, setExtractFromJob] = useState<string | null>(null)
  const [doneJobs, setDoneJobs] = useState<Job[]>([])
  const [extractSpeakerLabel, setExtractSpeakerLabel] = useState('')
  const [extractProfileName, setExtractProfileName] = useState('')
  const [extractSpeakers, setExtractSpeakers] = useState<string[]>([])
  const [extractSpeakerMap, setExtractSpeakerMap] = useState<Record<string, string>>({})
  const [extracting, setExtracting] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  useKeyboardShortcuts({ onEscape: onClose })

  const loadSpeakers = () => {
    fetch('/api/speakers').then(r => r.json()).then((data: Record<string, string>) => {
      setSpeakers([...new Set(Object.values(data))])
    }).catch(() => {})
  }

  const handleAddSpeaker = async () => {
    const name = newSpeakerName.trim()
    if (!name) return
    setSpeakerSaving(true)
    try {
      await fetch('/api/speakers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      setNewSpeakerName('')
      loadSpeakers()
    } catch {
      alert('화자 추가 실패')
    } finally {
      setSpeakerSaving(false)
    }
  }

  const handleDeleteSpeaker = async (name: string) => {
    await fetch(`/api/speakers/${encodeURIComponent(name)}`, { method: 'DELETE' })
    loadSpeakers()
  }

  // 목소리 프로필 로드
  const loadVoiceProfiles = () => {
    fetch('/api/voice-profiles').then(r => r.json()).then(setVoiceProfiles).catch(() => {})
  }

  const loadThreshold = () => {
    fetch('/api/voice-profiles/threshold').then(r => r.json()).then(data => {
      setThreshold(data.threshold ?? 0.75)
    }).catch(() => {})
  }

  const handleDeleteProfile = async (id: string) => {
    await fetch(`/api/voice-profiles/${id}`, { method: 'DELETE' })
    loadVoiceProfiles()
  }

  const handleAddSample = async (profileId: string) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []
      recorder.ondataavailable = e => chunks.push(e.data)
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const form = new FormData()
        form.append('audio', blob, 'sample.webm')
        await fetch(`/api/voice-profiles/${profileId}/add-sample`, { method: 'POST', body: form })
        loadVoiceProfiles()
      }
      recorder.start()
      setTimeout(() => recorder.stop(), 10000)
    } catch {
      alert('마이크 접근에 실패했습니다.')
    }
  }

  const startRecordingProfile = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      audioChunksRef.current = []
      recorder.ondataavailable = e => audioChunksRef.current.push(e.data)
      recorder.onstop = () => stream.getTracks().forEach(t => t.stop())
      mediaRecorderRef.current = recorder
      recorder.start()
      setRecordingForProfile(true)
    } catch {
      alert('마이크 접근에 실패했습니다.')
    }
  }

  const stopRecordingProfile = async () => {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state !== 'recording') return
    return new Promise<void>(resolve => {
      recorder.onstop = async () => {
        recorder.stream.getTracks().forEach(t => t.stop())
        setRecordingForProfile(false)
        if (!newProfileName.trim()) { alert('프로필 이름을 입력해주세요.'); resolve(); return }
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const form = new FormData()
        form.append('name', newProfileName.trim())
        form.append('audio', blob, 'profile.webm')
        try {
          await fetch('/api/voice-profiles', { method: 'POST', body: form })
          setNewProfileName('')
          loadVoiceProfiles()
        } catch {
          alert('프로필 등록에 실패했습니다.')
        }
        resolve()
      }
      recorder.stop()
    })
  }

  const handleExtractFromJob = async () => {
    if (!extractFromJob || !extractSpeakerLabel || !extractProfileName.trim()) return
    setExtracting(true)
    try {
      const res = await fetch(`/api/jobs/${extractFromJob}/save-speaker-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speaker_label: extractSpeakerLabel, profile_name: extractProfileName.trim() }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '프로필 추출에 실패했습니다.' }))
        alert(err.detail || '프로필 추출에 실패했습니다.')
        return
      }
      setExtractFromJob(null)
      setExtractSpeakerLabel('')
      setExtractProfileName('')
      loadVoiceProfiles()
    } catch {
      alert('프로필 추출에 실패했습니다.')
    } finally {
      setExtracting(false)
    }
  }

  const saveThreshold = async () => {
    await fetch('/api/voice-profiles/threshold', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold }),
    }).catch(() => {})
  }

  const formatDate = (s: string) => {
    const d = new Date(s)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
  }

  // 카테고리 관련 상태
  const [categories, setCategories] = useState<Category[]>([])
  const [editingCatId, setEditingCatId] = useState<string | null>(null)
  const [editCatForm, setEditCatForm] = useState({ name: '', icon: '', description: '', prompt: '', prompt_template: '', model: 'claude-sonnet-4-6' })
  const [catSaving, setCatSaving] = useState(false)
  const [showNewCatForm, setShowNewCatForm] = useState(false)
  const [newCatForm, setNewCatForm] = useState({ name: '', icon: '📋', description: '', prompt: '{script}', prompt_template: '', model: 'claude-sonnet-4-6' })
  const [previewPrompt, setPreviewPrompt] = useState<string | null>(null)

  // dirty state 추적: 부모 컴포넌트가 참조할 수 있도록 ref에 반영
  useEffect(() => {
    if (!isDirtyRef) return
    const hasApiKeyChanges = Object.values(values).some(v => v !== '')
    const hasCatEdit = editingCatId !== null || showNewCatForm
    const dirty = hasApiKeyChanges || hasCatEdit
    isDirtyRef.current = dirty
  }, [isDirtyRef, values, editingCatId, showNewCatForm])

  const loadCategories = () => {
    fetch('/api/categories').then(r => r.json()).then(setCategories).catch(() => {})
  }

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(setStatus)
      .catch(console.error)
    fetch('/api/settings/claude-status')
      .then(r => r.json())
      .then(setClaudeStatus)
      .catch(console.error)
    fetch('/api/settings/denoise')
      .then(r => r.json())
      .then(data => setDenoiseEnabled(data.enabled))
      .catch(() => {})
    loadCategories()
    loadSpeakers()
    loadVoiceProfiles()
    loadThreshold()
    fetch('/api/jobs').then(r => r.json()).then((jobs: Job[]) => {
      setDoneJobs(jobs.filter(j => j.status === 'done'))
    }).catch(() => {})
  }, [])

  const handleClaudeLogout = async () => {
    if (!confirm('Claude CLI에서 로그아웃하시겠습니까?')) return
    setLoggingOut(true)
    try {
      const res = await fetch('/api/settings/claude-logout', { method: 'POST' })
      if (!res.ok) {
        const data = await res.json()
        alert(`로그아웃 실패: ${data.detail}`)
      } else {
        const updated = await fetch('/api/settings/claude-status').then(r => r.json())
        setClaudeStatus(updated)
      }
    } catch {
      alert('로그아웃 요청에 실패했습니다.')
    } finally {
      setLoggingOut(false)
    }
  }

  const handleDenoiseToggle = async (enabled: boolean) => {
    setDenoiseEnabled(enabled)
    await fetch('/api/settings/denoise', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }).catch(() => {})
  }

  const handleBackup = () => {
    window.open('/api/settings/backup', '_blank')
  }

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setRestoring(true)
    setRestoreResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/settings/restore', { method: 'POST', body: formData })
      if (!res.ok) {
        const data = await res.json()
        setRestoreResult(`복원 실패: ${data.detail}`)
      } else {
        setRestoreResult('설정이 복원되었습니다.')
        const newStatus = await fetch('/api/settings').then(r => r.json())
        setStatus(newStatus)
        loadCategories()
        loadSpeakers()
        setTimeout(() => setRestoreResult(null), 3000)
      }
    } catch {
      setRestoreResult('복원 요청에 실패했습니다.')
    } finally {
      setRestoring(false)
      e.target.value = ''
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const body: Record<string, string> = {}
      for (const key of KEYS) {
        if (values[key] !== '') body[key] = values[key]
      }
      const res = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('저장 실패')
      const newStatus = await fetch('/api/settings').then(r => r.json())
      setStatus(newStatus)
      setValues({ HF_TOKEN: '', NOTION_API_KEY: '', NOTION_DATABASE_ID: '' })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      alert('설정 저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const handleEditCat = (cat: Category) => {
    setEditingCatId(cat.id)
    setEditCatForm({ name: cat.name, icon: cat.icon, description: cat.description, prompt: cat.prompt, prompt_template: cat.prompt_template || '', model: cat.model || 'claude-sonnet-4-6' })
    setShowNewCatForm(false)
  }

  const handleSaveCat = async (catId: string) => {
    if (!editCatForm.prompt.includes('{script}')) {
      alert("프롬프트에 {script} 플레이스홀더가 필요합니다.")
      return
    }
    setCatSaving(true)
    try {
      await fetch(`/api/categories/${catId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editCatForm),
      })
      setEditingCatId(null)
      loadCategories()
    } catch {
      alert('저장 실패')
    } finally {
      setCatSaving(false)
    }
  }

  const handleDeleteCat = async (catId: string) => {
    if (!confirm('이 카테고리를 삭제하시겠습니까?')) return
    await fetch(`/api/categories/${catId}`, { method: 'DELETE' })
    setEditingCatId(null)
    loadCategories()
  }

  const handleResetCatPrompt = async (catId: string) => {
    const res = await fetch(`/api/categories/${catId}/reset`, { method: 'POST' })
    const data = await res.json()
    setEditCatForm(prev => ({ ...prev, prompt: data.prompt }))
  }

  const handleCreateCat = async () => {
    if (!newCatForm.name.trim()) { alert('이름을 입력하세요.'); return }
    if (!newCatForm.prompt.includes('{script}')) {
      alert("프롬프트에 {script} 플레이스홀더가 필요합니다.")
      return
    }
    setCatSaving(true)
    try {
      await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCatForm),
      })
      setNewCatForm({ name: '', icon: '📋', description: '', prompt: '{script}', prompt_template: '', model: 'claude-sonnet-4-6' })
      setShowNewCatForm(false)
      loadCategories()
    } catch {
      alert('생성 실패')
    } finally {
      setCatSaving(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6">
        {/* 헤더 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">설정</h2>
        </div>

        {/* 저장 성공 배너 */}
        {saved && (
          <div className="mb-4 px-4 py-2 bg-green-50 dark:bg-green-900/30 border border-green-100 dark:border-green-800 rounded-lg text-green-700 dark:text-green-300 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
            </svg>
            설정이 저장되었습니다.
          </div>
        )}

        {/* 탭 바 */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 mb-5">
          {([['general', '일반'], ['categories', '카테고리'], ['speakers', '화자']] as [Tab, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 본문 */}
        <div>
          {activeTab === 'general' && (
            <div className="space-y-5">
              {/* Claude CLI 섹션 */}
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Claude CLI</span>
                    {claudeStatus ? (
                      claudeStatus.installed ? (
                        claudeStatus.logged_in ? (
                          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">로그인됨</span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full font-medium">로그아웃됨</span>
                        )
                      ) : (
                        <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">미설치</span>
                      )
                    ) : (
                      <span className="text-xs text-gray-400">확인 중...</span>
                    )}
                  </div>
                  {claudeStatus?.logged_in && (
                    <button
                      onClick={handleClaudeLogout}
                      disabled={loggingOut}
                      className="text-xs px-3 py-1 text-red-600 border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
                    >
                      {loggingOut ? '로그아웃 중...' : '로그아웃'}
                    </button>
                  )}
                </div>
                <div className="px-4 py-3 space-y-2">
                  {claudeStatus?.logged_in && claudeStatus.email && (
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                      <span className="text-gray-400">계정:</span>{' '}
                      <span className="font-mono">{claudeStatus.email}</span>
                      {claudeStatus.subscription_type && (
                        <span className="ml-2 text-xs text-gray-400">({claudeStatus.subscription_type})</span>
                      )}
                    </p>
                  )}
                  {claudeStatus && !claudeStatus.installed && (
                    <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                      <p className="font-medium text-gray-700 dark:text-gray-300">Claude CLI 설치 방법</p>
                      <code className="block bg-gray-100 dark:bg-gray-600 rounded px-3 py-2 text-xs font-mono text-gray-800 dark:text-gray-200">
                        npm install -g @anthropic-ai/claude-code
                      </code>
                    </div>
                  )}
                  {claudeStatus?.installed && !claudeStatus.logged_in && (
                    <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                      <p>터미널에서 아래 명령어를 실행하면 브라우저가 열려 로그인할 수 있습니다:</p>
                      <code className="block bg-gray-100 dark:bg-gray-600 rounded px-3 py-2 text-xs font-mono text-gray-800 dark:text-gray-200">
                        claude auth login
                      </code>
                      <p className="text-xs text-gray-400">로그인 후 설정 화면을 다시 열면 상태가 갱신됩니다.</p>
                    </div>
                  )}
                  {claudeStatus?.logged_in && (
                    <p className="text-xs text-gray-400">
                      회의록 요약에 Claude CLI를 사용합니다. 로그아웃하면 요약 기능이 중단됩니다.
                    </p>
                  )}
                </div>
              </div>

              {/* 노이즈 제거 토글 */}
              <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-100">노이즈 제거</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {denoiseEnabled ? '배경음·에코 감소 활성화됨' : '배경음·에코가 심한 환경에서 STT 품질 향상'}
                  </p>
                </div>
                <button
                  onClick={() => handleDenoiseToggle(!denoiseEnabled)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    denoiseEnabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    denoiseEnabled ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>

              {/* API 키 섹션 */}
              {KEYS.map((key) => {
                const isSet = status?.[key]?.set ?? false
                const preview = status?.[key]?.preview ?? null
                return (
                  <div key={key}>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      {KEY_LABELS[key]}
                    </label>
                    <div className="relative">
                      <input
                        type={showKey[key] ? 'text' : 'password'}
                        value={values[key]}
                        onChange={e => setValues(prev => ({ ...prev, [key]: e.target.value }))}
                        placeholder={preview ?? '값을 입력하세요'}
                        className="w-full pr-10 pl-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 placeholder:text-gray-400 placeholder:font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey(prev => ({ ...prev, [key]: !prev[key] }))}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        tabIndex={-1}
                      >
                        {showKey[key] ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 4.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}

              {/* 백업/복원 섹션 */}
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">설정 백업 / 복원</span>
                  <p className="text-xs text-gray-400 mt-0.5">화자 프로필, 카테고리 설정을 파일로 내보내거나 복원합니다. API 키는 보안상 포함되지 않습니다.</p>
                </div>
                <div className="px-4 py-3 flex items-center gap-2">
                  <button
                    onClick={handleBackup}
                    className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition-colors"
                  >
                    내보내기
                  </button>
                  <label className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition-colors cursor-pointer">
                    {restoring ? '복원 중...' : '가져오기'}
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleRestore}
                      disabled={restoring}
                      className="hidden"
                    />
                  </label>
                </div>
                {restoreResult && (
                  <div className={`px-4 py-2 text-xs border-t ${
                    restoreResult.includes('실패') ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'
                  }`}>
                    {restoreResult}
                  </div>
                )}
              </div>

              {/* 저장 버튼 */}
              <div className="flex justify-end pt-2">
                <button
                  onClick={handleSave}
                  disabled={saving || saved}
                  className={`px-4 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 flex items-center gap-1.5 ${
                    saved
                      ? 'bg-green-500'
                      : 'bg-blue-600 hover:bg-blue-700 disabled:opacity-50'
                  }`}
                >
                  {saved ? (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      저장됨
                    </>
                  ) : saving ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                      저장 중...
                    </>
                  ) : '저장'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'categories' && (
            <div className="space-y-3">
              {categories.map(cat => (
                <div key={cat.id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                  {/* 카테고리 헤더 행 */}
                  <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-700">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{cat.icon}</span>
                      <div>
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-100">{cat.name}</span>
                        {cat.description && (
                          <p className="text-xs text-gray-400">{cat.description}</p>
                        )}
                      </div>
                      {cat.is_builtin === 1 && (
                        <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">내장</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => editingCatId === cat.id ? setEditingCatId(null) : handleEditCat(cat)}
                        className="text-xs px-2.5 py-1 border rounded hover:bg-white dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300 transition-colors"
                      >
                        {editingCatId === cat.id ? '접기' : '편집'}
                      </button>
                      {cat.is_builtin === 0 && (
                        <button
                          onClick={() => handleDeleteCat(cat.id)}
                          className="text-xs px-2.5 py-1 border border-red-200 rounded hover:bg-red-50 text-red-500 transition-colors"
                        >
                          삭제
                        </button>
                      )}
                    </div>
                  </div>

                  {/* 편집 패널 — 인라인 펼침 */}
                  {editingCatId === cat.id && (
                    <div className="p-3 space-y-2 border-t border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={editCatForm.icon}
                          onChange={e => setEditCatForm(p => ({ ...p, icon: e.target.value }))}
                          placeholder="아이콘"
                          className="w-16 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-center text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                        />
                        <input
                          type="text"
                          value={editCatForm.name}
                          onChange={e => setEditCatForm(p => ({ ...p, name: e.target.value }))}
                          placeholder="이름"
                          className="flex-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                        />
                      </div>
                      <input
                        type="text"
                        value={editCatForm.description}
                        onChange={e => setEditCatForm(p => ({ ...p, description: e.target.value }))}
                        placeholder="설명 (선택)"
                        className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                      />
                      <div>
                        <label className="text-xs text-gray-500 dark:text-gray-400">요약 모델</label>
                        <select
                          value={editCatForm.model}
                          onChange={e => setEditCatForm(p => ({ ...p, model: e.target.value }))}
                          className="w-full mt-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                        >
                          {CLAUDE_MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                        </select>
                      </div>
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs text-gray-500 dark:text-gray-400">프롬프트</label>
                          {cat.is_builtin === 1 && (
                            <button
                              onClick={() => handleResetCatPrompt(cat.id)}
                              className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                            >
                              기본값으로 초기화
                            </button>
                          )}
                        </div>
                        <textarea
                          value={editCatForm.prompt}
                          onChange={e => setEditCatForm(p => ({ ...p, prompt: e.target.value }))}
                          rows={8}
                          className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-xs font-mono text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                          placeholder="{script} 위치에 스크립트가 삽입됩니다."
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 dark:text-gray-400">요약 프롬프트 템플릿</label>
                        <textarea
                          value={editCatForm.prompt_template}
                          onChange={e => setEditCatForm(p => ({ ...p, prompt_template: e.target.value }))}
                          rows={3}
                          className="w-full mt-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-xs font-mono text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                          placeholder="예) 기술 의사결정 위주로 요약하고, 아키텍처 변경사항을 별도 섹션으로 작성해줘"
                        />
                        <p className="text-xs text-gray-400 mt-0.5">비워두면 기본 프롬프트로 요약합니다</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveCat(cat.id)}
                          disabled={catSaving}
                          className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors"
                        >
                          {catSaving ? '저장 중...' : '저장'}
                        </button>
                        <button
                          onClick={() => setPreviewPrompt(editCatForm.prompt)}
                          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                          미리보기
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* 새 카테고리 추가 */}
              {showNewCatForm ? (
                <div className="border border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2 bg-gray-50 dark:bg-gray-800">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCatForm.icon}
                      onChange={e => setNewCatForm(p => ({ ...p, icon: e.target.value }))}
                      placeholder="아이콘"
                      className="w-16 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-center text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                    />
                    <input
                      type="text"
                      value={newCatForm.name}
                      onChange={e => setNewCatForm(p => ({ ...p, name: e.target.value }))}
                      placeholder="이름"
                      className="flex-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                    />
                  </div>
                  <input
                    type="text"
                    value={newCatForm.description}
                    onChange={e => setNewCatForm(p => ({ ...p, description: e.target.value }))}
                    placeholder="설명 (선택)"
                    className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                  />
                  <div>
                    <label className="text-xs text-gray-500 dark:text-gray-400">요약 모델</label>
                    <select
                      value={newCatForm.model}
                      onChange={e => setNewCatForm(p => ({ ...p, model: e.target.value }))}
                      className="w-full mt-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700"
                    >
                      {CLAUDE_MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                  </div>
                  <textarea
                    value={newCatForm.prompt}
                    onChange={e => setNewCatForm(p => ({ ...p, prompt: e.target.value }))}
                    rows={6}
                    className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-xs font-mono text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                    placeholder="{script} 위치에 스크립트가 삽입됩니다."
                  />
                  <div>
                    <label className="text-xs text-gray-500 dark:text-gray-400">요약 프롬프트 템플릿</label>
                    <textarea
                      value={newCatForm.prompt_template}
                      onChange={e => setNewCatForm(p => ({ ...p, prompt_template: e.target.value }))}
                      rows={3}
                      className="w-full mt-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-xs font-mono text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                      placeholder="예) 기술 의사결정 위주로 요약하고, 아키텍처 변경사항을 별도 섹션으로 작성해줘"
                    />
                    <p className="text-xs text-gray-400 mt-0.5">비워두면 기본 프롬프트로 요약합니다</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleCreateCat}
                      disabled={catSaving}
                      className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium"
                    >
                      {catSaving ? '생성 중...' : '추가'}
                    </button>
                    <button
                      onClick={() => setPreviewPrompt(newCatForm.prompt)}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      미리보기
                    </button>
                    <button
                      onClick={() => setShowNewCatForm(false)}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      취소
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => { setShowNewCatForm(true); setEditingCatId(null) }}
                  className="w-full py-2 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:border-gray-400 transition-colors"
                >
                  + 새 카테고리 추가
                </button>
              )}
            </div>
          )}

          {activeTab === 'speakers' && (
            <div className="space-y-6">
              {/* ── 화자 이름 사전 ── */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">화자 이름 사전</h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newSpeakerName}
                    onChange={e => setNewSpeakerName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleAddSpeaker()}
                    placeholder="화자 이름 입력"
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={handleAddSpeaker}
                    disabled={speakerSaving || !newSpeakerName.trim()}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
                  >
                    추가
                  </button>
                </div>
                <p className="text-xs text-gray-400">저장된 화자 이름은 스크립트 편집 시 드롭다운에 제안됩니다.</p>
                {speakers.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">저장된 화자가 없습니다.</p>
                ) : (
                  <div className="space-y-1.5">
                    {speakers.map(name => (
                      <div key={name} className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg">
                        <span className="text-sm text-gray-800 dark:text-gray-200">{name}</span>
                        <button
                          onClick={() => handleDeleteSpeaker(name)}
                          className="text-xs px-2 py-1 border border-red-200 rounded hover:bg-red-50 text-red-500 transition-colors"
                        >
                          삭제
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <hr className="border-gray-200 dark:border-gray-700" />

              {/* ── 목소리 프로필 ── */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">목소리 프로필</h4>
                <p className="text-xs text-gray-400">목소리 프로필을 등록하면 회의 녹음 시 자동으로 화자를 매칭합니다.</p>

                {/* 프로필 목록 */}
                {voiceProfiles.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">등록된 목소리 프로필이 없습니다.</p>
                ) : (
                  <div className="space-y-1.5">
                    {voiceProfiles.map(profile => (
                      <div key={profile.id} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                        <div>
                          <p className="text-sm font-medium text-gray-800 dark:text-gray-100">🎤 {profile.name}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">샘플 {profile.sample_count}개 · {formatDate(profile.updated_at)}</p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAddSample(profile.id)}
                            className="text-xs px-2 py-1 border border-blue-200 dark:border-blue-700 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 text-blue-600 dark:text-blue-400 transition-colors"
                          >
                            샘플 추가
                          </button>
                          <button
                            onClick={() => handleDeleteProfile(profile.id)}
                            className="text-xs px-2 py-1 border border-red-200 rounded hover:bg-red-50 text-red-500 transition-colors"
                          >
                            삭제
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 새 프로필 등록 */}
                <div className="space-y-2 pt-2">
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-300">새 프로필 등록</p>

                  {/* 직접 녹음 */}
                  <div className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg space-y-2">
                    <p className="text-xs text-gray-500 dark:text-gray-400">직접 녹음 (10~30초)</p>
                    <input
                      type="text"
                      value={newProfileName}
                      onChange={e => setNewProfileName(e.target.value)}
                      placeholder="프로필 이름 (예: 홍길동)"
                      className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    {recordingForProfile ? (
                      <button
                        onClick={stopRecordingProfile}
                        className="w-full py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs rounded transition-colors flex items-center justify-center gap-1.5"
                      >
                        <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                        녹음 중... 클릭하여 중지
                      </button>
                    ) : (
                      <button
                        onClick={startRecordingProfile}
                        disabled={!newProfileName.trim()}
                        className="w-full py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs rounded transition-colors"
                      >
                        녹음 시작
                      </button>
                    )}
                  </div>

                  {/* 기존 회의에서 추출 */}
                  <div className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg space-y-2">
                    <p className="text-xs text-gray-500 dark:text-gray-400">기존 회의에서 추출</p>
                    <select
                      value={extractFromJob || ''}
                      onChange={e => {
                        const jobId = e.target.value || null
                        setExtractFromJob(jobId)
                        setExtractSpeakerLabel('')
                        setExtractProfileName('')
                        if (jobId) {
                          const job = doneJobs.find(j => j.id === jobId)
                          if (job?.speakers) {
                            setExtractSpeakers(Object.keys(job.speakers))
                            setExtractSpeakerMap(job.speakers)
                          } else {
                            fetch(`/api/jobs/${jobId}`).then(r => r.json()).then((j: Job) => {
                              setExtractSpeakers(j.speakers ? Object.keys(j.speakers) : [])
                              setExtractSpeakerMap(j.speakers ?? {})
                            }).catch(() => { setExtractSpeakers([]); setExtractSpeakerMap({}) })
                          }
                        }
                      }}
                      className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="">회의 선택...</option>
                      {doneJobs.map(job => (
                        <option key={job.id} value={job.id}>{job.title || job.filename}</option>
                      ))}
                    </select>
                    {extractFromJob && extractSpeakers.length > 0 && (
                      <>
                        <select
                          value={extractSpeakerLabel}
                          onChange={e => {
                            const label = e.target.value
                            setExtractSpeakerLabel(label)
                            const mappedName = extractSpeakerMap[label]
                            if (mappedName) {
                              setExtractProfileName(mappedName)
                            }
                          }}
                          className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          <option value="">화자 선택...</option>
                          {extractSpeakers.map(sp => (
                            <option key={sp} value={sp}>
                              {extractSpeakerMap[sp] && extractSpeakerMap[sp] !== sp ? `${extractSpeakerMap[sp]} (${sp})` : sp}
                            </option>
                          ))}
                        </select>
                        <input
                          type="text"
                          value={extractProfileName}
                          onChange={e => setExtractProfileName(e.target.value)}
                          placeholder="프로필 이름"
                          className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                        <button
                          onClick={handleExtractFromJob}
                          disabled={!extractSpeakerLabel || !extractProfileName.trim() || extracting}
                          className="w-full py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs rounded transition-colors"
                        >
                          {extracting ? '추출 중...' : '프로필 추출'}
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* 매칭 임계값 */}
                <div className="mt-4 space-y-1">
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-300">
                    매칭 임계값: {threshold.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="0.95"
                    step="0.05"
                    value={threshold}
                    onChange={e => setThreshold(parseFloat(e.target.value))}
                    onMouseUp={saveThreshold}
                    onTouchEnd={saveThreshold}
                    className="w-full h-1.5 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <p className="text-xs text-gray-400">값이 높을수록 엄격하게 매칭 (기본: 0.75)</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 프롬프트 미리보기 모달 */}
      {previewPrompt !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">프롬프트 미리보기</h3>
              <button
                onClick={() => setPreviewPrompt(null)}
                className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <p className="text-xs text-gray-400 mb-3">Claude에게 전송될 실제 프롬프트입니다. <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">{'{script}'}</code> 위치에 회의 스크립트가 삽입됩니다.</p>
              <pre className="text-xs text-gray-700 dark:text-gray-300 font-mono whitespace-pre-wrap bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg p-4 leading-relaxed">
                {previewPrompt.includes('{script}')
                  ? previewPrompt.replace('{script}', '[SPEAKER_00] 안녕하세요, 오늘 회의를 시작하겠습니다.\n[SPEAKER_01] 네, 준비되었습니다.\n[SPEAKER_00] 첫 번째 안건은 프로젝트 일정 검토입니다.\n[SPEAKER_01] 현재 진행률은 70%이고 다음 주까지 완료 예정입니다.\n[SPEAKER_00] 좋습니다. 두 번째 안건으로 넘어가겠습니다.')
                  : previewPrompt + '\n\n---\n회의 스크립트:\n[SPEAKER_00] 안녕하세요, 오늘 회의를 시작하겠습니다.\n[SPEAKER_01] 네, 준비되었습니다.'}
              </pre>
            </div>
            <div className="flex justify-end px-5 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
              <button
                onClick={() => setPreviewPrompt(null)}
                className="px-4 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-gray-100 font-medium"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
