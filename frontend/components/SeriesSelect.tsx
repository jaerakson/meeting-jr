'use client'

import { useState, useEffect, useRef } from 'react'
import { Series } from '@/types'

interface Props {
  jobId: string
  currentSeriesId?: string
  onSeriesChange?: (seriesId: string | null) => void
}

export default function SeriesSelect({ jobId, currentSeriesId, onSeriesChange }: Props) {
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selected, setSelected] = useState<string>(currentSeriesId || '')
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch('/api/series')
      .then(r => (r.ok ? r.json() : []))
      .then((data: Series[] | { items: Series[] }) =>
        setSeriesList(Array.isArray(data) ? data : data.items || [])
      )
      .catch(() => setSeriesList([]))
  }, [])

  useEffect(() => {
    setSelected(currentSeriesId || '')
  }, [currentSeriesId])

  useEffect(() => {
    if (creating && inputRef.current) inputRef.current.focus()
  }, [creating])

  const handleChange = async (value: string) => {
    if (value === '__new__') {
      setCreating(true)
      return
    }
    const seriesId = value || null
    setSelected(value)
    try {
      await fetch(`/api/jobs/${jobId}/series`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ series_id: seriesId }),
      })
      onSeriesChange?.(seriesId)
    } catch {
      // silent fail
    }
  }

  const handleCreateSeries = async () => {
    const name = newName.trim()
    if (!name) {
      setCreating(false)
      setNewName('')
      return
    }
    try {
      const res = await fetch('/api/series', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      if (res.ok) {
        const created: Series = await res.json()
        setSeriesList(prev => [...prev, created])
        setSelected(created.id)
        setCreating(false)
        setNewName('')
        await fetch(`/api/jobs/${jobId}/series`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ series_id: created.id }),
        })
        onSeriesChange?.(created.id)
      }
    } catch {
      // silent fail
    }
  }

  if (creating) {
    return (
      <div className="flex items-center gap-1">
        <input
          ref={inputRef}
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') handleCreateSeries()
            if (e.key === 'Escape') { setCreating(false); setNewName('') }
          }}
          placeholder="시리즈 이름..."
          className="px-2 py-0.5 border border-gray-300 dark:border-gray-600 rounded text-xs bg-white dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500 w-28"
        />
        <button
          onClick={handleCreateSeries}
          className="text-xs px-1.5 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          추가
        </button>
        <button
          onClick={() => { setCreating(false); setNewName('') }}
          className="text-xs px-1.5 py-0.5 text-gray-400 hover:text-gray-600"
        >
          취소
        </button>
      </div>
    )
  }

  return (
    <select
      value={selected}
      onChange={e => handleChange(e.target.value)}
      className="px-2 py-0.5 border border-gray-300 dark:border-gray-600 rounded text-xs bg-white dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      <option value="">시리즈 없음</option>
      {seriesList.map(s => (
        <option key={s.id} value={s.id}>
          {s.name}{s.meeting_count != null ? ` (${s.meeting_count})` : ''}
        </option>
      ))}
      <option value="__new__">+ 새 시리즈 만들기</option>
    </select>
  )
}
