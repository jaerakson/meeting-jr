'use client'

import { useState, useEffect } from 'react'
import { SettingsStatus, ClaudeStatus, Category } from '@/types'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

interface Props {
  onClose: () => void
}

const KEY_LABELS: Record<string, string> = {
  HF_TOKEN: 'HuggingFace Token',
  NOTION_API_KEY: 'Notion API Key',
  NOTION_DATABASE_ID: 'Notion Database ID',
}

const KEYS = ['HF_TOKEN', 'NOTION_API_KEY', 'NOTION_DATABASE_ID'] as const

const CLAUDE_MODELS = [
  { value: "claude-sonnet-4-6",         label: "Claude Sonnet 4.6 (기본, 권장)" },
  { value: "claude-opus-4-6",           label: "Claude Opus 4.6 (고품질, 느림)" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 (빠름, 경량)" },
]

type Tab = 'general' | 'claude' | 'categories' | 'speakers'

export default function SettingsModal({ onClose }: Props) {
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
  const [defaultTitle, setDefaultTitle] = useState('')
  const [initialDefaultTitle, setInitialDefaultTitle] = useState('')
  const [claudeModel, setClaudeModel] = useState('claude-sonnet-4-6')
  const [initialClaudeModel, setInitialClaudeModel] = useState('claude-sonnet-4-6')
  const [claudePrompt, setClaudePrompt] = useState('')
  const [initialClaudePrompt, setInitialClaudePrompt] = useState('')
  const [defaultPrompt, setDefaultPrompt] = useState('')

  // 화자 관련 상태
  const [speakers, setSpeakers] = useState<string[]>([])
  const [newSpeakerName, setNewSpeakerName] = useState('')
  const [speakerSaving, setSpeakerSaving] = useState(false)

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

  // 카테고리 관련 상태
  const [categories, setCategories] = useState<Category[]>([])
  const [editingCatId, setEditingCatId] = useState<string | null>(null)
  const [editCatForm, setEditCatForm] = useState({ name: '', icon: '', description: '', prompt: '' })
  const [catSaving, setCatSaving] = useState(false)
  const [showNewCatForm, setShowNewCatForm] = useState(false)
  const [newCatForm, setNewCatForm] = useState({ name: '', icon: '📋', description: '', prompt: '{script}' })

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
    fetch('/api/settings/default-title')
      .then(r => r.json())
      .then(d => {
        setDefaultTitle(d.value ?? '')
        setInitialDefaultTitle(d.value ?? '')
      })
      .catch(console.error)
    fetch('/api/settings/claude-model')
      .then(r => r.json())
      .then(d => { setClaudeModel(d.value); setInitialClaudeModel(d.value) })
      .catch(console.error)
    fetch('/api/settings/claude-prompt')
      .then(r => r.json())
      .then(d => {
        setClaudePrompt(d.value)
        setInitialClaudePrompt(d.value)
        setDefaultPrompt(d.default)
      })
      .catch(console.error)
    loadCategories()
    loadSpeakers()
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

  const handleSave = async () => {
    setSaving(true)
    try {
      const body: Record<string, string> = {
        DEFAULT_MEETING_TITLE: defaultTitle,
        CLAUDE_MODEL: claudeModel,
        CLAUDE_PROMPT: claudePrompt,
      }
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
      setInitialDefaultTitle(defaultTitle)
      setInitialClaudeModel(claudeModel)
      setInitialClaudePrompt(claudePrompt)
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
    setEditCatForm({ name: cat.name, icon: cat.icon, description: cat.description, prompt: cat.prompt })
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
      setNewCatForm({ name: '', icon: '📋', description: '', prompt: '{script}' })
      setShowNewCatForm(false)
      loadCategories()
    } catch {
      alert('생성 실패')
    } finally {
      setCatSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-800">설정</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 저장 성공 배너 */}
        {saved && (
          <div className="px-6 py-2 bg-green-50 border-b border-green-100 text-green-700 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
            </svg>
            설정이 저장되었습니다.
          </div>
        )}

        {/* 탭 바 */}
        <div className="flex border-b px-2">
          {([['general', '일반'], ['claude', 'Claude'], ['categories', '카테고리'], ['speakers', '화자']] as [Tab, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 본문 */}
        <div className="px-6 py-5 overflow-y-auto max-h-[60vh]">
          {activeTab === 'general' && (
            <div className="space-y-5">
              {/* 기본 회의 제목 섹션 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  기본 회의 제목
                </label>
                <input
                  type="text"
                  value={defaultTitle}
                  onChange={e => setDefaultTitle(e.target.value)}
                  placeholder="회의록 (미입력 시 기본값)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="mt-1 text-xs text-gray-400">새 녹음 시작 시 이 제목이 자동으로 설정됩니다.</p>
              </div>

              {/* Claude CLI 섹션 */}
              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">Claude CLI</span>
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
                    <p className="text-sm text-gray-600">
                      <span className="text-gray-400">계정:</span>{' '}
                      <span className="font-mono">{claudeStatus.email}</span>
                      {claudeStatus.subscription_type && (
                        <span className="ml-2 text-xs text-gray-400">({claudeStatus.subscription_type})</span>
                      )}
                    </p>
                  )}
                  {claudeStatus && !claudeStatus.installed && (
                    <div className="text-sm text-gray-600 space-y-1">
                      <p className="font-medium text-gray-700">Claude CLI 설치 방법</p>
                      <code className="block bg-gray-100 rounded px-3 py-2 text-xs font-mono text-gray-800">
                        npm install -g @anthropic-ai/claude-code
                      </code>
                    </div>
                  )}
                  {claudeStatus?.installed && !claudeStatus.logged_in && (
                    <div className="text-sm text-gray-600 space-y-2">
                      <p>터미널에서 아래 명령어를 실행하면 브라우저가 열려 로그인할 수 있습니다:</p>
                      <code className="block bg-gray-100 rounded px-3 py-2 text-xs font-mono text-gray-800">
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

              {/* API 키 섹션 */}
              {KEYS.map((key) => {
                const isSet = status?.[key]?.set ?? false
                const preview = status?.[key]?.preview ?? null
                return (
                  <div key={key}>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      {KEY_LABELS[key]}
                    </label>
                    <div className="relative">
                      <input
                        type={showKey[key] ? 'text' : 'password'}
                        value={values[key]}
                        onChange={e => setValues(prev => ({ ...prev, [key]: e.target.value }))}
                        placeholder={preview ?? '값을 입력하세요'}
                        className="w-full pr-10 pl-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 placeholder:text-gray-400 placeholder:font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
            </div>
          )}

          {activeTab === 'claude' && (
            <div className="space-y-5">
              {/* 모델 선택 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  회의록 생성 모델
                </label>
                <select
                  value={claudeModel}
                  onChange={e => setClaudeModel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {CLAUDE_MODELS.map(m => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-400">회의록 요약 시 사용할 Claude 모델을 선택합니다.</p>
              </div>

              {/* 프롬프트 커스터마이징 */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-sm font-medium text-gray-700">
                    요약 프롬프트
                  </label>
                  <button
                    type="button"
                    onClick={() => setClaudePrompt(defaultPrompt)}
                    className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                  >
                    초기화
                  </button>
                </div>
                <textarea
                  value={claudePrompt || defaultPrompt}
                  onChange={e => setClaudePrompt(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs text-gray-800 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                  placeholder="프롬프트를 입력하세요. {script} 위치에 회의 스크립트가 삽입됩니다."
                />
                <p className="mt-1 text-xs text-gray-400">
                  <code className="bg-gray-100 px-1 rounded">{'{script}'}</code> 플레이스홀더 위치에 회의 스크립트가 삽입됩니다. 미포함 시 자동으로 끝에 추가됩니다.
                </p>
              </div>
            </div>
          )}

          {activeTab === 'categories' && (
            <div className="space-y-3">
              {categories.map(cat => (
                <div key={cat.id} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* 카테고리 헤더 행 */}
                  <div className="flex items-center justify-between px-3 py-2 bg-gray-50">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{cat.icon}</span>
                      <div>
                        <span className="text-sm font-medium text-gray-800">{cat.name}</span>
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
                        className="text-xs px-2.5 py-1 border rounded hover:bg-white text-gray-600 transition-colors"
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
                    <div className="p-3 space-y-2 border-t bg-white">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={editCatForm.icon}
                          onChange={e => setEditCatForm(p => ({ ...p, icon: e.target.value }))}
                          placeholder="아이콘"
                          className="w-16 px-2 py-1.5 border rounded text-sm text-center"
                        />
                        <input
                          type="text"
                          value={editCatForm.name}
                          onChange={e => setEditCatForm(p => ({ ...p, name: e.target.value }))}
                          placeholder="이름"
                          className="flex-1 px-2 py-1.5 border rounded text-sm"
                        />
                      </div>
                      <input
                        type="text"
                        value={editCatForm.description}
                        onChange={e => setEditCatForm(p => ({ ...p, description: e.target.value }))}
                        placeholder="설명 (선택)"
                        className="w-full px-2 py-1.5 border rounded text-sm"
                      />
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs text-gray-500">프롬프트</label>
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
                          className="w-full px-2 py-1.5 border rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                          placeholder="{script} 위치에 스크립트가 삽입됩니다."
                        />
                      </div>
                      <button
                        onClick={() => handleSaveCat(cat.id)}
                        disabled={catSaving}
                        className="w-full py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors"
                      >
                        {catSaving ? '저장 중...' : '저장'}
                      </button>
                    </div>
                  )}
                </div>
              ))}

              {/* 새 카테고리 추가 */}
              {showNewCatForm ? (
                <div className="border border-dashed border-gray-300 rounded-lg p-3 space-y-2 bg-gray-50">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCatForm.icon}
                      onChange={e => setNewCatForm(p => ({ ...p, icon: e.target.value }))}
                      placeholder="아이콘"
                      className="w-16 px-2 py-1.5 border rounded text-sm text-center bg-white"
                    />
                    <input
                      type="text"
                      value={newCatForm.name}
                      onChange={e => setNewCatForm(p => ({ ...p, name: e.target.value }))}
                      placeholder="이름"
                      className="flex-1 px-2 py-1.5 border rounded text-sm bg-white"
                    />
                  </div>
                  <input
                    type="text"
                    value={newCatForm.description}
                    onChange={e => setNewCatForm(p => ({ ...p, description: e.target.value }))}
                    placeholder="설명 (선택)"
                    className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                  />
                  <textarea
                    value={newCatForm.prompt}
                    onChange={e => setNewCatForm(p => ({ ...p, prompt: e.target.value }))}
                    rows={6}
                    className="w-full px-2 py-1.5 border rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y bg-white"
                    placeholder="{script} 위치에 스크립트가 삽입됩니다."
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleCreateCat}
                      disabled={catSaving}
                      className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium"
                    >
                      {catSaving ? '생성 중...' : '추가'}
                    </button>
                    <button
                      onClick={() => setShowNewCatForm(false)}
                      className="px-3 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-100"
                    >
                      취소
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => { setShowNewCatForm(true); setEditingCatId(null) }}
                  className="w-full py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:bg-gray-50 hover:border-gray-400 transition-colors"
                >
                  + 새 카테고리 추가
                </button>
              )}
            </div>
          )}

          {activeTab === 'speakers' && (
            <div className="space-y-3">
              {/* 새 화자 추가 */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newSpeakerName}
                  onChange={e => setNewSpeakerName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddSpeaker()}
                  placeholder="화자 이름 입력"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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

              {/* 화자 목록 */}
              {speakers.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">저장된 화자가 없습니다.</p>
              ) : (
                <div className="space-y-1.5">
                  {speakers.map(name => (
                    <div key={name} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
                      <span className="text-sm text-gray-800">{name}</span>
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
          )}
        </div>

        {/* 푸터 */}
        {activeTab !== 'categories' && activeTab !== 'speakers' && (
          <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 rounded-b-xl">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium transition-colors"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={saving || saved || (KEYS.every(k => values[k] === '') && defaultTitle === initialDefaultTitle && claudeModel === initialClaudeModel && claudePrompt === initialClaudePrompt)}
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
        )}
        {(activeTab === 'categories' || activeTab === 'speakers') && (
          <div className="flex justify-end px-6 py-4 border-t bg-gray-50 rounded-b-xl">
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium">
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
