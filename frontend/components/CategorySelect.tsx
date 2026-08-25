'use client'
import { useState, useEffect } from 'react'
import { Category } from '@/types'

interface Props {
  value: string
  onChange: (id: string) => void
  className?: string
}

export default function CategorySelect({ value, onChange, className = '' }: Props) {
  const [categories, setCategories] = useState<Category[]>([])

  useEffect(() => {
    fetch('/api/categories')
      .then(r => r.json())
      .then(setCategories)
      .catch(() => {})
  }, [])

  if (categories.length === 0) return null

  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className={`px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${className}`}
    >
      {categories.map(cat => (
        <option key={cat.id} value={cat.id} title={cat.description}>
          {cat.icon} {cat.name}
        </option>
      ))}
    </select>
  )
}
