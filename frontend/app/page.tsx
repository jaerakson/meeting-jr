'use client'

import { useState, useEffect, useCallback } from 'react'
import { Job } from '@/types'
import Sidebar from '@/components/Sidebar'
import MainArea from '@/components/MainArea'
import ShortcutHelpModal from '@/components/ShortcutHelpModal'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showShortcutHelp, setShowShortcutHelp] = useState(false)

  useEffect(() => {
    setSidebarCollapsed(localStorage.getItem('sidebar-collapsed') === 'true')
  }, [])

  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsed(prev => {
      const next = !prev
      localStorage.setItem('sidebar-collapsed', String(next))
      return next
    })
  }, [])

  useKeyboardShortcuts({
    onHelp: () => setShowShortcutHelp(true),
    onEscape: () => setShowShortcutHelp(false),
    onToggleSidebar: toggleSidebarCollapsed,
  })

  // /meetings 에서 카드 클릭 시 /?job=<id> 로 이동 — 해당 job 자동 선택
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const jobId = params.get('job')
    if (jobId) {
      setSelectedJobId(jobId)
      window.history.replaceState({}, '', '/')
    }
  }, [])

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs')
      if (res.ok) {
        const data: Job[] = await res.json()
        setJobs(data)
      }
    } catch {
      // API 실패 시 조용히 무시 (폴링이므로 다음 주기에 재시도)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 3000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  const selectedJob = jobs.find((j) => j.id === selectedJobId) ?? null

  const handleNewRecording = (jobId: string) => {
    fetchJobs()
    setSelectedJobId(jobId)
    setSidebarOpen(false)
  }

  // Sidebar 클릭 시 URL 동기화
  const handleSelectJob = (id: string | null) => {
    setSelectedJobId(id)
    setSidebarOpen(false)
    if (id) {
      window.history.pushState({ jobId: id }, '', `/meetings/${id}`)
    } else {
      window.history.pushState({ jobId: null }, '', '/')
    }
  }

  // 뒤로 가기 시 이전 상태 복원
  useEffect(() => {
    const handlePopState = (e: PopStateEvent) => {
      const jobId = e.state?.jobId ?? null
      setSelectedJobId(jobId)
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* 모바일 오버레이 배경 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 사이드바 — 모바일: 슬라이드 오버, 데스크탑: width transition */}
      <div className={`
        fixed inset-y-0 left-0 z-30 transition-all duration-200
        md:relative md:translate-x-0 md:flex md:flex-shrink-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        overflow-hidden
        ${sidebarCollapsed ? 'md:w-0' : 'md:w-60'}
      `}>
        <Sidebar
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelectJob={handleSelectJob}
          onJobsChange={fetchJobs}
          onNewRecording={() => { setSelectedJobId(null); setSidebarOpen(false) }}
          onClose={() => setSidebarOpen(false)}
          onCollapse={toggleSidebarCollapsed}
        />
      </div>

      <MainArea
        job={selectedJob}
        onJobsChange={fetchJobs}
        onNewRecording={handleNewRecording}
        onOpenSidebar={() => setSidebarOpen(true)}
        sidebarCollapsed={sidebarCollapsed}
        onExpandSidebar={toggleSidebarCollapsed}
      />

      {showShortcutHelp && <ShortcutHelpModal onClose={() => setShowShortcutHelp(false)} />}
    </div>
  )
}
