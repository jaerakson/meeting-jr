'use client'

import { useRouter } from 'next/navigation'
import { ReactNode } from 'react'
import { Job } from '@/types'

interface MeetingCardProps {
  job: Job
  searchQuery?: string
  onBookmark?: (jobId: string) => void
  onDelete?: (jobId: string) => void
  selectMode?: boolean
  isSelected?: boolean
  onSelect?: (jobId: string) => void
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

const CATEGORY_COLORS: Record<string, string> = {
  '주간회의': 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  '기획회의': 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  '일일스크럼': 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  '회고': 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  '인터뷰': 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
}
const DEFAULT_CATEGORY_COLOR = 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  done:          { label: '완료',      cls: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-400' },
  pending:       { label: '대기',      cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400' },
  converting:    { label: '변환 중',   cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400' },
  diarizing:     { label: '화자 분리', cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400' },
  transcribing:  { label: 'STT 중',   cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400' },
  awaiting_edit: { label: '편집 대기', cls: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-400' },
  summarizing:   { label: '요약 중',   cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400' },
  error:         { label: '실패',      cls: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-400' },
}

export default function MeetingCard({ job, searchQuery, onBookmark, onDelete, selectMode, isSelected, onSelect }: MeetingCardProps) {
  const router = useRouter()
  const badge = STATUS_BADGE[job.status] ?? { label: job.status, cls: 'bg-gray-100 text-gray-800' }
  const actionCount = job.summary ? countActionItems(job.summary) : 0
  const speakersLabel = getSpeakersLabel(job.speakers)
  const summaryPreview = job.summary
    ? job.summary.replace(/^#+.+$/gm, '').trim().slice(0, 100)
    : ''

  const handleClick = () => {
    if (selectMode && onSelect) {
      onSelect(job.id)
    } else {
      const url = searchQuery
        ? `/meetings/${job.id}?q=${encodeURIComponent(searchQuery)}`
        : `/meetings/${job.id}`
      router.push(url)
    }
  }

  return (
    <div
      onClick={handleClick}
      className={`bg-white dark:bg-gray-800 border rounded-xl p-4 cursor-pointer hover:shadow-sm transition-all flex flex-col gap-2 min-h-[140px] ${
        isSelected
          ? 'border-blue-500 dark:border-blue-400 ring-2 ring-blue-200 dark:ring-blue-800'
          : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
      }`}
    >
      {/* 제목 + 상태 뱃지 + 북마크 */}
      <div className="flex items-start justify-between gap-2">
        {selectMode && (
          <div className="flex-shrink-0 pt-0.5">
            <input
              type="checkbox"
              checked={!!isSelected}
              onChange={() => onSelect?.(job.id)}
              onClick={e => e.stopPropagation()}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </div>
        )}
        <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm leading-snug line-clamp-2 flex-1">
          {highlightText(job.title, searchQuery)}
        </h3>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
            {badge.label}
          </span>
          {onBookmark && (
            <button
              onClick={e => { e.stopPropagation(); onBookmark(job.id) }}
              className={`text-base leading-none transition-colors ${job.bookmarked ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-400'}`}
              title={job.bookmarked ? '북마크 해제' : '북마크'}
            >
              {job.bookmarked ? '★' : '☆'}
            </button>
          )}
          {onDelete && (
            <button
              onClick={e => {
                e.stopPropagation()
                if (confirm(`"${job.title}" 을 삭제할까요?`)) onDelete(job.id)
              }}
              className="text-gray-300 dark:text-gray-600 hover:text-red-400 transition-colors text-sm leading-none"
              title="삭제"
            >
              🗑
            </button>
          )}
        </div>
      </div>

      {/* 날짜 + 시간 + 카테고리 */}
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <span>{formatDate(job.created_at)}</span>
        {job.duration_sec && (
          <>
            <span>·</span>
            <span>{formatDuration(job.duration_sec)}</span>
          </>
        )}
        {job.category && (
          <>
            <span>·</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[job.category] ?? DEFAULT_CATEGORY_COLOR}`}>
              {job.category}
            </span>
          </>
        )}
      </div>

      {/* 참석자 */}
      {speakersLabel && (
        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{speakersLabel}</p>
      )}

      {/* 요약 미리보기 또는 검색 snippet */}
      {(job.snippet || summaryPreview) && (
        <div className="flex-1">
          {job.snippet && job.snippet_source === 'transcript' && (
            <span className="text-[10px] text-orange-600 dark:text-orange-400 font-medium mb-0.5 block">본문에서 발견</span>
          )}
          <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed">
            {job.snippet
              ? highlightText(job.snippet, searchQuery)
              : highlightText(summaryPreview, searchQuery)}
          </p>
        </div>
      )}

      {/* 태그 */}
      {job.tags && job.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {job.tags.slice(0, 3).map(tag => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full">{tag}</span>
          ))}
          {job.tags.length > 3 && <span className="text-[10px] text-gray-400">+{job.tags.length - 3}</span>}
        </div>
      )}

      {/* 하단 상태 배지 */}
      <div className="flex items-center gap-2">
        {actionCount > 0 && (
          <span className="text-xs text-blue-600 font-medium">액션 아이템 {actionCount}건</span>
        )}
        {job.rating && (
          <span className="text-xs text-yellow-500">
            {'★'.repeat(job.rating)}{'☆'.repeat(5 - job.rating)}
          </span>
        )}
        {job.notion_url && (
          <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded-full flex items-center gap-0.5">
            <svg className="w-2.5 h-2.5" viewBox="0 0 100 100" fill="currentColor">
              <path d="M6.6,12.4c4.8,3.5,6.6,3.1,15.6,2.4l64.8-3.9c1.9,0,0.3-1.9-0.3-2.1L78.4,2.7c-2.9-2.1-6.8-4.3-14.2-3.5L4.4,4.8C1.5,5.1,0.9,6.6,2.3,7.7L6.6,12.4z M11.6,23.3v68.4c0,3.7,1.8,5.1,5.9,4.8l70.5-4.1c4.1-0.3,4.6-2.7,4.6-5.7V18.6c0-3-1.2-4.6-3.8-4.3L18,18.5C15.3,18.9,11.6,19.6,11.6,23.3z M78.5,26.9c0.5,2.2,0,4.3-2.2,4.6l-3.4,0.6v50.5c-3,1.6-5.7,2.5-8,2.5c-3.7,0-4.6-1.2-7.4-4.8l-22.6-35.5v34.4l7,1.6c0,0,0,4.3-6,4.3l-16.5,1c-0.5-1-0-3.5,1.7-3.9l4.4-1.2V30.9l-6.1-0.5c-0.5-2.2,0.7-5.3,4.1-5.6L41.2,23l23.6,36.1V26.6l-5.9-0.7c-0.5-2.6,1.4-4.5,3.8-4.7L78.5,26.9z"/>
            </svg>
            Notion
          </span>
        )}
      </div>
    </div>
  )
}
