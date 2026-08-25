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
} from 'recharts'

interface MonthlyData {
  month: string
  count: number
  total_minutes: number
}

export default function MonthlyChart() {
  const [data, setData] = useState<MonthlyData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/stats/monthly')
      .then(r => (r.ok ? r.json() : []))
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 flex items-center justify-center h-[220px]">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 flex items-center justify-center h-[220px]">
        <p className="text-sm text-gray-400">아직 완료된 회의가 없습니다</p>
      </div>
    )
  }

  const chartData = data.map(d => ({
    ...d,
    label: `${parseInt(d.month.split('-')[1])}월`,
  }))

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
        월별 회의 통계
      </h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as MonthlyData & { label: string }
              return (
                <div className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 shadow-sm text-sm">
                  <p className="font-medium text-gray-700 dark:text-gray-200">{label}</p>
                  <p className="text-gray-500 dark:text-gray-400">
                    회의 {d.count}건 · 총 {d.total_minutes}분
                  </p>
                </div>
              )
            }}
          />
          <Bar
            dataKey="count"
            radius={[4, 4, 0, 0]}
            fill="#2563EB"
            className="dark:[&>path]:fill-blue-400"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
