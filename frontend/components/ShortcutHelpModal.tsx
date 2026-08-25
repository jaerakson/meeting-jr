'use client'

interface Props {
  onClose: () => void
}

const shortcuts = [
  { key: 'Space', desc: '녹음 시작/중지 또는 오디오 재생/일시정지' },
  { key: '\u2190', desc: '오디오 5초 뒤로' },
  { key: '\u2192', desc: '오디오 5초 앞으로' },
  { key: 'Esc', desc: '현재 작업 취소 / 모달 닫기' },
  { key: '?', desc: '이 도움말 열기' },
]

export default function ShortcutHelpModal({ onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-96 max-w-[90vw]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">키보드 단축키</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="space-y-3">
          {shortcuts.map(s => (
            <div key={s.key} className="flex items-center justify-between">
              <span className="text-sm text-gray-600 dark:text-gray-300">{s.desc}</span>
              <kbd className="px-2.5 py-1 text-xs font-mono bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-md border border-gray-200 dark:border-gray-600 shadow-sm min-w-[2.5rem] text-center">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-4 text-center">
          입력 필드에 포커스된 경우 단축키가 비활성화됩니다
        </p>
      </div>
    </div>
  )
}
