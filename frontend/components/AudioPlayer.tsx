'use client'

import { useRef, useState, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

export interface AudioPlayerHandle {
  seekTo: (seconds: number) => void
}

interface AudioPlayerProps {
  audioSrc: string
  onTimeUpdate: (sec: number) => void
}

const SPEEDS = [0.75, 1, 1.25, 1.5, 2]

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(function AudioPlayer({ audioSrc, onTimeUpdate }, ref) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)

  const handleTimeUpdate = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    setCurrentTime(audio.currentTime)
    onTimeUpdate(audio.currentTime)
  }, [onTimeUpdate])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onLoaded = () => setDuration(audio.duration || 0)
    const onEnded = () => setIsPlaying(false)

    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', onEnded)
    }
  }, [handleTimeUpdate])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return
    const time = Number(e.target.value)
    audio.currentTime = time
    setCurrentTime(time)
  }

  const handleSpeedChange = () => {
    const audio = audioRef.current
    if (!audio) return
    const nextIdx = (SPEEDS.indexOf(speed) + 1) % SPEEDS.length
    const nextSpeed = SPEEDS[nextIdx]
    audio.playbackRate = nextSpeed
    setSpeed(nextSpeed)
  }

  useKeyboardShortcuts({
    onSpaceAudio: useCallback(() => {
      const audio = audioRef.current
      if (!audio) return
      if (audio.paused) {
        audio.play()
        setIsPlaying(true)
      } else {
        audio.pause()
        setIsPlaying(false)
      }
    }, []),
    onSeekBack: useCallback(() => {
      const audio = audioRef.current
      if (!audio) return
      audio.currentTime = Math.max(0, audio.currentTime - 5)
    }, []),
    onSeekForward: useCallback(() => {
      const audio = audioRef.current
      if (!audio) return
      audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 5)
    }, []),
  })

  useImperativeHandle(ref, () => ({
    seekTo: (seconds: number) => {
      const audio = audioRef.current
      if (!audio) return
      audio.currentTime = seconds
      setCurrentTime(seconds)
      if (!isPlaying) {
        audio.play()
        setIsPlaying(true)
      }
    },
  }), [isPlaying])

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <audio ref={audioRef} src={audioSrc} preload="metadata" />

      {/* 재생/일시정지 버튼 */}
      <button
        onClick={togglePlay}
        className="w-10 h-10 flex items-center justify-center rounded-full bg-accent hover:bg-blue-700 text-white transition-colors flex-shrink-0"
      >
        {isPlaying ? (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
          </svg>
        ) : (
          <svg className="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
            <polygon points="5,3 19,12 5,21" />
          </svg>
        )}
      </button>

      {/* 시크바 */}
      <input
        type="range"
        min={0}
        max={isFinite(duration) && duration > 0 ? duration : 100}
        step={0.1}
        value={currentTime}
        onChange={handleSeek}
        disabled={!isFinite(duration) || duration === 0}
        className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full appearance-none cursor-pointer accent-accent disabled:opacity-40"
      />

      {/* 시간 */}
      <span className="text-sm text-gray-500 font-mono whitespace-nowrap flex-shrink-0">
        {formatTime(currentTime)}{isFinite(duration) && duration > 0 ? ` / ${formatTime(duration)}` : ''}
      </span>

      {/* 재생 속도 버튼 (클릭마다 순환: 0.75→1→1.25→1.5→2→0.75) */}
      <button
        onClick={handleSpeedChange}
        className="text-xs font-semibold text-gray-500 hover:text-blue-600 transition-colors flex-shrink-0 w-10 text-center border border-gray-200 rounded px-1 py-0.5 hover:border-blue-400"
        title="재생 속도 변경"
      >
        {speed === 1 ? '1x' : `${speed}x`}
      </button>

      <span className="text-[10px] text-gray-400 hidden md:inline flex-shrink-0">
        Space: 재생/일시정지 &nbsp; ←→: 5초
      </span>
    </div>
  )
})

export default AudioPlayer
