'use client'

import { useRouter } from 'next/navigation'
import { ReactNode } from 'react'
import { Job } from '@/types'

interface MeetingCardProps {
  job: Job
  searchQuery?: string
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlightText(text: string, query: string | undefined): ReactNode {
  if (!query || !text) return text
  const escaped = escapeRegExp(query)
  const regex = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(regex)
  if (parts.length === 1) return text
  return parts.map((part, i) =>
    regex.test(part)
      ? <mark key={i} className="bg-yellow-200 dark:bg-yellow-700 text-inherit rounded-sm px-0.5">{part}</mark>
      : part
  )
}

function countActionItems(summary: string): number {
  return (summary.match(/- \[ \]/g) || []).length
}

function formatDuration(sec?: number): string {
  if (!sec) return ''
  return `${Math.floor(sec / 60)}분`
}

function formatDate(iso: string): string {
  return iso.slice(0, 10)
}

function getSpeakersLabel(speakers?: Record<string, string>): string {
  if (!speakers) return ''
  const names = Object.values(speakers).filter(v => v && !/^SPEAKER_\d+$/.test(v))
  if (names.length === 0) return ''
  const visible = names.slice(0, 3)
  const rest = names.length - 3
  return rest > 0 ? `${visible.join(', ')} 외 ${rest}명` : visible.join(', ')
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  done:          { label: '완료',      cls: 'bg-green-100 text-green-800' },
  pending:       { label: '대기',      cls: 'bg-blue-100 text-blue-800' },
  converting:    { label: '변환 중',   cls: 'bg-blue-100 text-blue-800' },
  diarizing:     { label: '화자 분리', cls: 'bg-blue-100 text-blue-800' },
  transcribing:  { label: 'STT 중',   cls: 'bg-blue-100 text-blue-800' },
  awaiting_edit: { label: '편집 대기', cls: 'bg-yellow-100 text-yellow-800' },
  summarizing:   { label: '요약 중',   cls: 'bg-blue-100 text-blue-800' },
  error:         { label: '실패',      cls: 'bg-red-100 text-red-800' },
}

export default function MeetingCard({ job, searchQuery }: MeetingCardProps) {
  const router = useRouter()
  const badge = STATUS_BADGE[job.status] ?? { label: job.status, cls: 'bg-gray-100 text-gray-800' }
  const actionCount = job.summary ? countActionItems(job.summary) : 0
  const speakersLabel = getSpeakersLabel(job.speakers)
  const summaryPreview = job.summary
    ? job.summary.replace(/^#+.+$/gm, '').trim().slice(0, 100)
    : ''

  return (
    <div
      onClick={() => router.push(`/meetings/${job.id}`)}
      className="bg-white border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all flex flex-col gap-2 min-h-[140px]"
    >
      {/* 제목 + 상태 뱃지 */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-800 text-sm leading-snug line-clamp-2 flex-1">
          {highlightText(job.title, searchQuery)}
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${badge.cls}`}>
          {badge.label}
        </span>
      </div>

      {/* 날짜 + 시간 */}
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <span>{formatDate(job.created_at)}</span>
        {job.duration_sec && (
          <>
            <span>·</span>
            <span>{formatDuration(job.duration_sec)}</span>
          </>
        )}
      </div>

      {/* 참석자 */}
      {speakersLabel && (
        <p className="text-xs text-gray-500 truncate">{speakersLabel}</p>
      )}

      {/* 요약 미리보기 */}
      {summaryPreview && (
        <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed flex-1">
          {highlightText(summaryPreview, searchQuery)}
        </p>
      )}

      {/* 태그 */}
      {job.tags && job.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {job.tags.slice(0, 3).map(tag => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded-full">{tag}</span>
          ))}
          {job.tags.length > 3 && <span className="text-[10px] text-gray-400">+{job.tags.length - 3}</span>}
        </div>
      )}

      {/* 액션 아이템 수 */}
      {actionCount > 0 && (
        <p className="text-xs text-blue-600 font-medium">액션 아이템 {actionCount}건</p>
      )}
    </div>
  )
}
