'use client'

import { useEffect } from 'react'

interface ShortcutHandlers {
  onSpaceRecord?: () => void
  onSpaceAudio?: () => void
  onSeekBack?: () => void
  onSeekForward?: () => void
  onEscape?: () => void
  onHelp?: () => void
  enabled?: boolean
}

export function useKeyboardShortcuts({
  onSpaceRecord,
  onSpaceAudio,
  onSeekBack,
  onSeekForward,
  onEscape,
  onHelp,
  enabled = true,
}: ShortcutHandlers) {
  useEffect(() => {
    if (!enabled) return

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return
      if ((e.target as HTMLElement)?.getAttribute('data-no-shortcut') !== null) return

      switch (e.key) {
        case ' ':
          e.preventDefault()
          if (onSpaceRecord) onSpaceRecord()
          else if (onSpaceAudio) onSpaceAudio()
          break
        case 'ArrowLeft':
          if (onSeekBack) {
            e.preventDefault()
            onSeekBack()
          }
          break
        case 'ArrowRight':
          if (onSeekForward) {
            e.preventDefault()
            onSeekForward()
          }
          break
        case 'Escape':
          if (onEscape) onEscape()
          break
        case '?':
          if (onHelp) {
            e.preventDefault()
            onHelp()
          }
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [enabled, onSpaceRecord, onSpaceAudio, onSeekBack, onSeekForward, onEscape, onHelp])
}
