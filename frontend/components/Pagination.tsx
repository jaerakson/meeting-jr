interface PaginationProps {
  page: number
  pages: number
  onPageChange: (page: number) => void
}

function getPageNumbers(page: number, pages: number): (number | '...')[] {
  const delta = 2
  const items: (number | '...')[] = []
  let prev: number | null = null

  for (let i = 1; i <= pages; i++) {
    const inRange = i === 1 || i === pages || (i >= page - delta && i <= page + delta)
    if (inRange) {
      if (prev !== null && i - prev > 1) items.push('...')
      items.push(i)
      prev = i
    }
  }
  return items
}

export default function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null

  const pageNumbers = getPageNumbers(page, pages)

  return (
    <div className="flex items-center justify-center gap-1 py-6">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ←
      </button>

      {pageNumbers.map((p, i) =>
        p === '...' ? (
          <span key={`ellipsis-${i}`} className="px-2 text-sm text-gray-400 select-none">
            ...
          </span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`w-9 h-9 text-sm rounded-lg border transition-colors ${
              p === page
                ? 'bg-blue-600 text-white border-blue-600 font-medium'
                : 'border-gray-300 hover:bg-gray-50 text-gray-700'
            }`}
          >
            {p}
          </button>
        )
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page === pages}
        className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        →
      </button>
    </div>
  )
}
