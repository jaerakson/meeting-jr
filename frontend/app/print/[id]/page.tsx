'use client'

import { useEffect, useState, use } from 'react'
import { Job } from '@/types'

// 마크다운을 HTML로 변환 (간단한 파서)
function markdownToHtml(md: string): string {
  return md
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- \[ \] (.+)$/gm, '<li class="todo">☐ $1</li>')
    .replace(/^- \[x\] (.+)$/gm, '<li class="todo done">☑ $1</li>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^(\|.+\|)$/gm, (line) => {
      const cells = line.split('|').filter(Boolean).map(c => c.trim())
      // 구분자 행 (| --- | --- |) 건너뜀
      if (cells.every(c => /^[-: ]+$/.test(c))) return ''
      return '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>'
    })
    .replace(/(<tr>[\s\S]*?<\/tr>\n?)+/gm, (block) => `<table>${block}</table>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^---$/gm, '<hr/>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/^(?!<[hblctp])/gm, '')
}

// 스크립트 파싱 (화자별 컬러)
function parseTranscript(transcript: string) {
  const lines = transcript.split('\n').filter(Boolean)
  const speakerColors: Record<string, string> = {}
  const COLORS = ['#2563EB', '#16A34A', '#EA580C', '#7C3AED', '#DC2626']
  let colorIdx = 0

  return lines.map((line, i) => {
    const match = line.match(/^\[(\d+:\d+(?::\d+)?)\]\s+([^:]+):\s*(.*)$/)
    if (!match) return <p key={i} className="text-gray-500 text-sm">{line}</p>
    const [, time, speaker, text] = match
    if (!speakerColors[speaker]) {
      speakerColors[speaker] = COLORS[colorIdx++ % COLORS.length]
    }
    return (
      <div key={i} className="flex gap-3 py-1.5 border-b border-gray-100">
        <span className="text-xs text-gray-400 w-12 shrink-0 pt-0.5">{time}</span>
        <span className="text-xs font-semibold shrink-0 pt-0.5" style={{ color: speakerColors[speaker] }}>
          {speaker}
        </span>
        <span className="text-sm text-gray-800">{text}</span>
      </div>
    )
  })
}

export default function PrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/jobs/${id}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { setJob(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!loading && job && job.status === 'done') {
      setTimeout(() => window.print(), 500)
    }
  }, [loading, job])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!job) {
    return <div className="p-8 text-gray-500">회의를 찾을 수 없습니다.</div>
  }

  const createdAt = job.created_at
    ? new Date(job.created_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
    : ''

  return (
    <>
      <style>{`
        @page {
          size: A4;
          margin: 20mm 15mm;
        }
        @media print {
          .no-print { display: none !important; }
          body { font-size: 11pt; }
          h1 { font-size: 16pt; }
          h2 { font-size: 13pt; }
          h3 { font-size: 11pt; }
          table { border-collapse: collapse; width: 100%; }
          td, th { border: 1px solid #ccc; padding: 4px 8px; font-size: 9pt; }
          blockquote { border-left: 3px solid #ccc; margin: 0; padding-left: 12px; color: #555; }
          .page-break { page-break-before: always; }
          .transcript-section { page-break-before: always; }
        }
        body { font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; color: #1a1a1a; }
        h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
        h2 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; color: #1e293b; }
        h3 { font-size: 13px; font-weight: 600; margin: 14px 0 6px; }
        p { margin: 6px 0; line-height: 1.6; font-size: 13px; }
        ul, ol { margin: 4px 0; padding-left: 20px; }
        li { margin: 3px 0; font-size: 13px; line-height: 1.5; }
        blockquote { border-left: 3px solid #94a3b8; margin: 8px 0; padding: 6px 12px; background: #f8fafc; color: #475569; border-radius: 0 4px 4px 0; }
        table { border-collapse: collapse; width: 100%; margin: 8px 0; }
        td, th { border: 1px solid #d1d5db; padding: 5px 10px; font-size: 12px; }
        th { background: #f1f5f9; font-weight: 600; }
        code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
        hr { border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }
        .todo { list-style: none; }
      `}</style>

      {/* 인쇄 버튼 (화면에서만 표시) */}
      <div className="no-print fixed top-4 right-4 flex gap-2 z-50">
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium shadow-lg hover:bg-blue-700"
        >
          PDF로 저장
        </button>
        <button
          onClick={() => window.close()}
          className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium shadow-lg hover:bg-gray-300"
        >
          닫기
        </button>
      </div>

      <div className="max-w-[800px] mx-auto px-8 py-10">
        {/* 헤더 */}
        <div className="border-b-2 border-gray-800 pb-4 mb-6">
          <h1>{job.title || '회의록'}</h1>
          <div className="flex gap-6 mt-2 text-sm text-gray-500">
            <span>일시: {createdAt}</span>
            {job.speakers && Object.keys(job.speakers).length > 0 && (
              <span>참석자: {Object.values(job.speakers).join(', ')}</span>
            )}
          </div>
        </div>

        {/* 요약 */}
        {job.summary && (
          <div>
            <div
              dangerouslySetInnerHTML={{
                __html: markdownToHtml(job.summary)
              }}
            />
          </div>
        )}

        {/* 스크립트 */}
        {job.transcript && (
          <div className="transcript-section mt-8">
            <h2>대화 스크립트</h2>
            <div className="mt-3">
              {parseTranscript(job.transcript)}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
