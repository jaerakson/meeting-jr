'use client'

import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { ParticipationData, ParticipationSpeaker } from '@/types'

const SPEAKER_COLORS = ['#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}m ${s}s`
}

interface Props {
  jobId: string
  onSpeakerClick?: (speakerName: string) => void
}

export default function ParticipationChart({ jobId, onSpeakerClick }: Props) {
  const [data, setData] = useState<ParticipationData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/jobs/${jobId}/participation`)
      .then(r => (r.ok ? r.json() : null))
      .then((d: ParticipationData | null) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [jobId])

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 flex items-center justify-center h-[180px] mt-4">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!data || data.speakers.length === 0) {
    return null
  }

  const chartData = data.speakers.map((s, i) => ({
    ...s,
    name: s.display_name || s.label,
    color: SPEAKER_COLORS[i % SPEAKER_COLORS.length],
  }))

  const chartHeight = Math.max(140, chartData.length * 44 + 40)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const renderBarLabel = (props: any) => {
    const x = Number(props.x ?? 0)
    const y = Number(props.y ?? 0)
    const width = Number(props.width ?? 0)
    const height = Number(props.height ?? 0)
    const value = props.value as number | undefined
    if (value == null) return null
    return (
      <text
        x={x + width + 4}
        y={y + height / 2}
        fill="#9CA3AF"
        fontSize={11}
        dominantBaseline="middle"
      >
        {value.toFixed(1)}%
      </text>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mt-4">
      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
        발언 참여도
      </h3>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 50, left: 0, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#E5E7EB"
            horizontal={false}
            className="dark:[&>line]:stroke-gray-600"
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={80}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as ParticipationSpeaker & { name: string; color: string }
              return (
                <div className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 shadow-sm text-sm">
                  <p className="font-medium text-gray-700 dark:text-gray-200">{d.name}</p>
                  <p className="text-gray-500 dark:text-gray-400">
                    발언 시간: {formatDuration(d.total_seconds)} ({d.percentage.toFixed(1)}%)
                  </p>
                  <p className="text-gray-500 dark:text-gray-400">
                    발언 횟수: {d.turn_count}회 (평균 {formatDuration(d.avg_turn_seconds)})
                  </p>
                </div>
              )
            }}
          />
          <Bar
            dataKey="percentage"
            radius={[0, 4, 4, 0]}
            barSize={20}
            label={renderBarLabel}
          >
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {chartData.map((s) => (
          <span
            key={s.label}
            className={`text-xs text-gray-500 dark:text-gray-400 ${
              onSpeakerClick ? 'cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 transition-colors' : ''
            }`}
            onClick={() => onSpeakerClick?.(s.name)}
          >
            <span
              className="inline-block w-2.5 h-2.5 rounded-full mr-1"
              style={{ backgroundColor: s.color }}
            />
            {s.name} {s.percentage.toFixed(0)}% · {s.turn_count}회
          </span>
        ))}
      </div>
    </div>
  )
}
