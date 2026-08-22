'use client'

import { useState, useEffect } from 'react'
import { SettingsStatus, ClaudeStatus } from '@/types'

interface Props {
  onClose: () => void
}

const KEY_LABELS: Record<string, string> = {
  HF_TOKEN: 'HuggingFace Token',
  NOTION_API_KEY: 'Notion API Key',
  NOTION_DATABASE_ID: 'Notion Database ID',
}

const KEYS = ['HF_TOKEN', 'NOTION_API_KEY', 'NOTION_DATABASE_ID'] as const

export default function SettingsModal({ onClose }: Props) {
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

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(setStatus)
      .catch(console.error)
    fetch('/api/settings/claude-status')
      .then(r => r.json())
      .then(setClaudeStatus)
      .catch(console.error)
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
      const body: Record<string, string> = {}
      for (const key of KEYS) {
        if (values[key] !== '') body[key] = values[key]
      }
      if (Object.keys(body).length === 0) {
        setSaving(false)
        return
      }
      const res = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('저장 실패')
      // 저장 후 status 갱신
      const newStatus = await fetch('/api/settings').then(r => r.json())
      setStatus(newStatus)
      setValues({ HF_TOKEN: '', NOTION_API_KEY: '', NOTION_DATABASE_ID: '' })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      alert('설정 저장에 실패했습니다.')
    } finally {
      setSaving(false)
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

        {/* 본문 */}
        <div className="px-6 py-5 space-y-5">

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

        {/* 푸터 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 rounded-b-xl">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving || saved || KEYS.every(k => values[k] === '')}
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
    </div>
  )
}
