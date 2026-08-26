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
    return <div style={{ padding: 32, color: '#6b7280' }}>회의를 찾을 수 없습니다.</div>
  }

  const createdAt = job.created_at
    ? new Date(job.created_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
    : ''

  return (
    <>
      <style>{`
        /* PDF/인쇄 페이지는 항상 라이트 모드 강제 */
        html, body {
          background: #ffffff !important;
          color: #1a1a1a !important;
          color-scheme: light !important;
        }
        /* 다크모드 Tailwind 클래스 무력화: dark: 프리픽스 스타일 전부 리셋 */
        .dark, [data-theme="dark"] {
          color-scheme: light !important;
          background-color: #ffffff !important;
          color: #1a1a1a !important;
        }
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
          blockquote { border-left: 3px solid #ccc; margin: 0; padding-left: 12px; color: #555 !important; }
          .page-break { page-break-before: always; }
        }
        body { font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; color: #1a1a1a !important; background: #ffffff !important; }
        h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: #1a1a1a !important; }
        h2 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; color: #1e293b !important; }
        h3 { font-size: 13px; font-weight: 600; margin: 14px 0 6px; color: #1a1a1a !important; }
        p { margin: 6px 0; line-height: 1.6; font-size: 13px; color: #1a1a1a !important; }
        ul, ol { margin: 4px 0; padding-left: 20px; }
        li { margin: 3px 0; font-size: 13px; line-height: 1.5; color: #1a1a1a !important; }
        blockquote { border-left: 3px solid #94a3b8; margin: 8px 0; padding: 6px 12px; background: #f8fafc !important; color: #475569 !important; border-radius: 0 4px 4px 0; }
        table { border-collapse: collapse; width: 100%; margin: 8px 0; }
        td, th { border: 1px solid #d1d5db; padding: 5px 10px; font-size: 12px; color: #1a1a1a !important; }
        th { background: #f1f5f9 !important; font-weight: 600; }
        code { background: #f1f5f9 !important; padding: 1px 4px; border-radius: 3px; font-size: 11px; color: #1a1a1a !important; }
        hr { border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }
        .todo { list-style: none; }
        /* 인쇄 페이지 컨테이너 명시적 라이트 색상 */
        .print-container { background: #ffffff !important; color: #1a1a1a !important; }
        .print-container * { background-color: transparent !important; }
        .print-container blockquote { background: #f8fafc !important; }
        .print-container th { background: #f1f5f9 !important; }
        .print-container code { background: #f1f5f9 !important; }
        .print-meta { color: #6b7280 !important; }
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

      <div className="print-container" style={{ maxWidth: 800, margin: '0 auto', padding: '40px 32px', background: '#ffffff', color: '#1a1a1a' }}>
        {/* 헤더 */}
        <div style={{ borderBottom: '2px solid #1f2937', paddingBottom: 16, marginBottom: 24 }}>
          <h1>{job.title || '회의록'}</h1>
          <div className="print-meta" style={{ display: 'flex', gap: 24, marginTop: 8, fontSize: 14 }}>
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

        {/* 대화 스크립트는 PDF에서 제외 (요약만 포함) */}
      </div>
    </>
  )
}
