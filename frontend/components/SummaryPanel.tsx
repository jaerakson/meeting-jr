'use client'

import { useState, useMemo, useEffect } from 'react'

interface SummaryPanelProps {
  summary: string
  jobId: string
  onSummaryUpdate?: (newSummary: string) => void
  speakers?: Record<string, string>
}

const TABS = ['핵심 요약', '주요 논의', '결정 사항', '액션 아이템'] as const

const SECTION_HEADERS: Record<string, string> = {
  '핵심 요약': '## 핵심 요약',
  '주요 논의': '## 주요 논의',
  '결정 사항': '## 주요 결정',
  '액션 아이템': '## 액션 아이템',
}

function extractSection(markdown: string, sectionName: string): string {
  const headerPattern = SECTION_HEADERS[sectionName]
  if (!headerPattern) return ''

  const idx = markdown.indexOf(headerPattern)
  if (idx === -1) return ''

  // 헤더 라인 이후부터 다음 ## 또는 끝까지
  const afterHeader = markdown.substring(idx)
  const lines = afterHeader.split('\n')
  // 첫 줄(헤더) 건너뛰기
  const contentLines: string[] = []
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].startsWith('## ')) break
    contentLines.push(lines[i])
  }
  return contentLines.join('\n').trim()
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 빈 줄
    if (!line.trim()) {
      nodes.push(<div key={i} className="h-2" />)
      continue
    }

    // h1
    if (line.startsWith('# ')) {
      nodes.push(
        <h1 key={i} className="text-xl font-bold text-gray-800 mb-2">
          {line.slice(2)}
        </h1>
      )
      continue
    }

    // h2
    if (line.startsWith('## ')) {
      nodes.push(
        <h2 key={i} className="text-lg font-bold text-gray-800 mb-2 mt-3">
          {line.slice(3)}
        </h2>
      )
      continue
    }

    // h3
    if (line.startsWith('### ')) {
      nodes.push(
        <h3 key={i} className="text-base font-semibold text-gray-800 mb-1 mt-2">
          {line.slice(4)}
        </h3>
      )
      continue
    }

    // 체크박스 (미완료)
    if (line.trimStart().startsWith('- [ ] ')) {
      const content = line.trimStart().slice(6)
      nodes.push(
        <div key={i} className="flex items-start gap-2 py-0.5">
          <input type="checkbox" disabled className="mt-1 flex-shrink-0" />
          <span className="text-sm text-gray-700">{content}</span>
        </div>
      )
      continue
    }

    // 체크박스 (완료)
    if (line.trimStart().startsWith('- [x] ') || line.trimStart().startsWith('- [X] ')) {
      const content = line.trimStart().slice(6)
      nodes.push(
        <div key={i} className="flex items-start gap-2 py-0.5">
          <input type="checkbox" disabled checked className="mt-1 flex-shrink-0" />
          <span className="text-sm text-gray-500 line-through">{content}</span>
        </div>
      )
      continue
    }

    // 리스트
    if (line.trimStart().startsWith('- ')) {
      const content = line.trimStart().slice(2)
      nodes.push(
        <div key={i} className="flex items-start gap-2 py-0.5 pl-1">
          <span className="text-gray-400 mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-gray-400" />
          <span className="text-sm text-gray-700">{content}</span>
        </div>
      )
      continue
    }

    // 번호 리스트
    const numberedMatch = line.trimStart().match(/^(\d+)\.\s+(.+)$/)
    if (numberedMatch) {
      nodes.push(
        <div key={i} className="flex items-start gap-2 py-0.5 pl-1">
          <span className="text-sm text-gray-500 flex-shrink-0 font-medium">{numberedMatch[1]}.</span>
          <span className="text-sm text-gray-700">{numberedMatch[2]}</span>
        </div>
      )
      continue
    }

    // 일반 텍스트
    nodes.push(
      <p key={i} className="text-sm text-gray-700 leading-relaxed">
        {line}
      </p>
    )
  }

  return nodes
}

export default function SummaryPanel({ summary, jobId, onSummaryUpdate, speakers }: SummaryPanelProps) {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('핵심 요약')
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState(summary)
  const [isSaving, setIsSaving] = useState(false)
  const [nameMap, setNameMap] = useState<Record<string, string>>({})

  // Bug fix: jobId가 바뀌면 편집 상태 리셋
  useEffect(() => {
    setIsEditing(false)
    setEditContent(summary)
    setNameMap({})
  }, [jobId]) // eslint-disable-line react-hooks/exhaustive-deps

  const sections = useMemo(() => {
    const result: Record<string, string> = {}
    for (const tab of TABS) {
      result[tab] = extractSection(summary, tab)
    }
    return result
  }, [summary])

  const currentContent = sections[activeTab] || '해당 섹션의 내용이 없습니다.'

  const handleDownload = () => {
    window.open(`/api/jobs/${jobId}/download`, '_blank')
  }

  const uniqueNames = useMemo(() => {
    if (!speakers) return []
    return [...new Set(
      Object.values(speakers).filter(
        (v) => v && !/^SPEAKER_\d+$/.test(v)
      )
    )]
  }, [speakers])

  const handleEditStart = () => {
    setEditContent(summary)
    const initialMap: Record<string, string> = {}
    for (const name of uniqueNames) initialMap[name] = name
    setNameMap(initialMap)
    setIsEditing(true)
  }

  const handleApplyNames = () => {
    let updated = editContent
    const newMap: Record<string, string> = {}
    for (const [orig, next] of Object.entries(nameMap)) {
      const trimmed = next.trim()
      if (trimmed && trimmed !== orig) {
        updated = updated.replaceAll(orig, trimmed)
        // 키를 새 이름으로 갱신하여 다음 적용 시에도 올바르게 동작
        newMap[trimmed] = trimmed
      } else {
        newMap[orig] = orig
      }
    }
    setEditContent(updated)
    setNameMap(newMap)
  }

  const handleEditCancel = () => {
    setIsEditing(false)
    setEditContent(summary)
  }

  const handleEditSave = async () => {
    setIsSaving(true)
    try {
      await fetch(`/api/jobs/${jobId}/summary`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: editContent }),
      })
      onSummaryUpdate?.(editContent)
    } finally {
      setIsSaving(false)
      setIsEditing(false)
    }
  }

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* 헤더: 탭 + 버튼 */}
      <div className="flex items-center border-b border-gray-200 px-3 min-w-0">
        {isEditing ? (
          <span className="text-xs text-gray-400 py-2.5 italic flex-1">마크다운 전체 편집 중</span>
        ) : (
          <div className="flex-1 overflow-x-auto min-w-0 flex">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-2.5 text-xs font-medium transition-colors border-b-2 whitespace-nowrap ${
                  activeTab === tab
                    ? 'border-accent text-accent'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1 flex-shrink-0 ml-1">
          {isEditing ? (
            <>
              <button
                onClick={handleEditCancel}
                disabled={isSaving}
                className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleEditSave}
                disabled={isSaving}
                className="px-2.5 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 font-medium"
              >
                {isSaving ? '저장 중...' : '저장'}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleEditStart}
                className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
              >
                편집
              </button>
              <button
                onClick={handleDownload}
                className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                title="마크다운 다운로드"
              >
                다운로드
              </button>
            </>
          )}
        </div>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-y-auto p-4">
        {isEditing ? (
          <div className="flex flex-col h-full gap-3">
            {Object.keys(nameMap).length > 0 && (
              <div className="flex flex-wrap items-center gap-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                {Object.keys(nameMap).map((currentName) => (
                  <div key={currentName} className="flex items-center gap-1 text-xs">
                    <span className="text-gray-500 font-medium">{currentName} →</span>
                    <input
                      type="text"
                      value={nameMap[currentName] ?? currentName}
                      onChange={(e) => setNameMap((prev) => ({ ...prev, [currentName]: e.target.value }))}
                      className="w-24 px-1.5 py-0.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>
                ))}
                <button
                  onClick={handleApplyNames}
                  className="px-2 py-0.5 text-xs bg-gray-700 text-white rounded hover:bg-gray-800 transition-colors"
                >
                  적용
                </button>
              </div>
            )}
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="flex-1 min-h-[200px] text-sm text-gray-700 font-mono p-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        ) : (
          <div>{renderMarkdown(currentContent)}</div>
        )}
      </div>
    </div>
  )
}
