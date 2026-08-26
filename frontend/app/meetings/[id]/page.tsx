'use client'

import { useState, useEffect, useCallback, use, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { Job } from '@/types'
import Sidebar from '@/components/Sidebar'
import MainArea from '@/components/MainArea'

function MeetingDetailContent({ id }: { id: string }) {
  const searchParams = useSearchParams()
  const searchQuery = searchParams.get('q') || ''
  const [jobs, setJobs] = useState<Job[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs')
      if (res.ok) setJobs(await res.json())
    } catch {
      // silent
    }
  }, [])

  useEffect(() => { fetchJobs() }, [fetchJobs])

  const selectedJob = jobs.find(j => j.id === id) ?? null

  return (
    <div className="flex h-dvh overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className={`
        fixed inset-y-0 left-0 z-30 transition-transform duration-200
        md:relative md:translate-x-0 md:flex md:flex-shrink-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar
          jobs={jobs}
          selectedJobId={id}
          onSelectJob={(newId) => {
            if (newId) window.location.href = `/meetings/${newId}`
            else window.location.href = '/'
          }}
          onJobsChange={fetchJobs}
          onNewRecording={() => { window.location.href = '/' }}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      <MainArea
        job={selectedJob}
        onJobsChange={fetchJobs}
        onNewRecording={(jobId: string) => { window.location.href = `/meetings/${jobId}` }}
        onOpenSidebar={() => setSidebarOpen(true)}
        searchQuery={searchQuery}
      />
    </div>
  )
}

export default function MeetingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  return (
    <Suspense fallback={
      <div className="flex h-dvh items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <MeetingDetailContent id={id} />
    </Suspense>
  )
}
