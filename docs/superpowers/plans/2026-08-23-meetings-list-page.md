# 회의 목록 페이지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/meetings` 경로에 검색(제목+요약) + 페이지 번호 네비게이션을 갖춘 전용 회의 목록 페이지를 추가한다.

**Architecture:** 백엔드에 `search_jobs` DB 함수와 `GET /api/meetings` 엔드포인트를 추가하고, 프론트엔드에 `Pagination`, `MeetingCard`, `/meetings/page.tsx` 3개 파일을 신규 생성한다. 기존 사이드바와 홈 페이지는 최소 수정(각 1~5줄)으로 연결한다.

**Tech Stack:** Python 3.11, FastAPI, SQLite(sqlite3), Next.js 15 App Router, TypeScript, Tailwind CSS, pytest, httpx

## Global Constraints

- Python 경로: `/opt/homebrew/bin/python3.11`
- 백엔드 서버: `uvicorn app.main:app --reload --port 8000` (backend/ 디렉토리에서 실행)
- 프론트엔드 서버: `npm run dev` (frontend/ 디렉토리에서 실행, 포트 3000)
- `ANTHROPIC_API_KEY` 사용 금지 — Claude 호출은 `claude -p` CLI subprocess 방식만 허용
- 기존 `GET /api/jobs` 엔드포인트 변경 금지 (사이드바 3초 폴링에 사용 중)
- 컬러: 페이지 배경 #F8F9FA, 카드 배경 #FFFFFF, 액센트 #2563EB, Tailwind 클래스 사용
- 페이지당 카드: 12개 고정

---

## 파일 구조

### 신규 생성
```
backend/tests/__init__.py
backend/tests/test_search_jobs.py
backend/tests/test_meetings_endpoint.py
frontend/components/Pagination.tsx
frontend/components/MeetingCard.tsx
frontend/app/meetings/page.tsx
```

### 수정
```
backend/app/database.py       — search_jobs() 함수 추가 (끝에 append)
backend/app/main.py           — GET /api/meetings 엔드포인트 추가 (끝에 append)
frontend/components/Sidebar.tsx — "전체 목록 보기" 링크 1개 추가 (99번째 줄 이후)
frontend/app/page.tsx          — mount 시 ?job=<id> param 읽어 선택 처리 (useEffect 1개 추가)
```

---

## Task 1: 백엔드 — search_jobs DB 함수

**Files:**
- Modify: `backend/app/database.py` (파일 끝에 추가)
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_search_jobs.py`

**Interfaces:**
- Produces:
  ```python
  def search_jobs(q: str = "", page: int = 1, limit: int = 12) -> dict:
      # 반환: {"items": list[dict], "total": int, "page": int, "pages": int}
  ```

- [ ] **Step 1: pytest 설치 확인 및 tests 디렉토리 생성**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pip install pytest httpx --quiet
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_search_jobs.py` 생성:

```python
import sys
import os
import tempfile
import pytest

# backend/ 를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 테스트용 임시 DB 경로를 환경변수로 주입
@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path

from app.database import create_job, update_job_result, search_jobs


def _make_job(job_id: str, title: str, summary: str = ""):
    create_job(job_id, f"{job_id}.webm", title=title)
    if summary:
        update_job_result(job_id, summary=summary)


def test_search_jobs_returns_all_when_no_query():
    _make_job("a1", "팀 주간회의")
    _make_job("a2", "기획 킥오프")
    result = search_jobs(q="", page=1, limit=12)
    assert result["total"] == 2
    assert result["pages"] == 1
    assert len(result["items"]) == 2


def test_search_jobs_filters_by_title():
    _make_job("b1", "팀 주간회의")
    _make_job("b2", "기획 킥오프")
    result = search_jobs(q="기획", page=1, limit=12)
    assert result["total"] == 1
    assert result["items"][0]["title"] == "기획 킥오프"


def test_search_jobs_filters_by_summary():
    _make_job("c1", "회의A", summary="액션 아이템 검토 필요")
    _make_job("c2", "회의B", summary="별다른 내용 없음")
    result = search_jobs(q="액션", page=1, limit=12)
    assert result["total"] == 1
    assert result["items"][0]["id"] == "c1"


def test_search_jobs_pagination():
    for i in range(15):
        _make_job(f"d{i}", f"회의 {i}")
    result = search_jobs(q="", page=1, limit=12)
    assert result["total"] == 15
    assert result["pages"] == 2
    assert len(result["items"]) == 12

    result2 = search_jobs(q="", page=2, limit=12)
    assert len(result2["items"]) == 3


def test_search_jobs_empty_result():
    _make_job("e1", "팀 회의")
    result = search_jobs(q="존재하지않는검색어", page=1, limit=12)
    assert result["total"] == 0
    assert result["pages"] == 1
    assert result["items"] == []
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_search_jobs.py -v
```

예상 결과: `ImportError` 또는 `AttributeError: module 'app.database' has no attribute 'search_jobs'`

- [ ] **Step 4: search_jobs 함수 구현**

`backend/app/database.py` 파일 끝에 추가:

```python
def search_jobs(q: str = "", page: int = 1, limit: int = 12) -> dict:
    """제목+요약 LIKE 검색 + 페이지네이션.

    반환: {"items": list[dict], "total": int, "page": int, "pages": int}
    """
    if page < 1:
        page = 1
    offset = (page - 1) * limit
    conn = _get_conn()
    try:
        if q:
            pattern = f"%{q}%"
            rows = conn.execute(
                """
                SELECT * FROM meetings
                WHERE (title LIKE ? OR summary LIKE ?)
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (pattern, pattern, limit, offset),
            ).fetchall()
            total: int = conn.execute(
                "SELECT COUNT(*) FROM meetings WHERE (title LIKE ? OR summary LIKE ?)",
                (pattern, pattern),
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM meetings ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]

        pages = max(1, (total + limit - 1) // limit)
        return {
            "items": [_row_to_dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": pages,
        }
    finally:
        conn.close()
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_search_jobs.py -v
```

예상 결과: `5 passed`

- [ ] **Step 6: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add backend/app/database.py backend/tests/
git commit -m "feat: add search_jobs function with pagination to database.py"
```

---

## Task 2: 백엔드 — GET /api/meetings 엔드포인트

**Files:**
- Modify: `backend/app/main.py` (파일 끝에 추가)
- Create: `backend/tests/test_meetings_endpoint.py`

**Interfaces:**
- Consumes: `search_jobs(q, page, limit)` from `app.database`
- Produces:
  ```
  GET /api/meetings?q=&page=1&limit=12
  → 200 {"items": [...], "total": int, "page": int, "pages": int}
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_meetings_endpoint.py` 생성:

```python
import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_get_meetings_empty(client):
    res = client.get("/api/meetings")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["pages"] == 1


def test_get_meetings_with_query(client, tmp_db):
    import app.database as db
    db.create_job("x1", "x1.webm", title="팀 주간회의")
    db.create_job("x2", "x2.webm", title="기획 회의")

    res = client.get("/api/meetings?q=기획")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "기획 회의"


def test_get_meetings_pagination(client, tmp_db):
    import app.database as db
    for i in range(14):
        db.create_job(f"p{i}", f"p{i}.webm", title=f"회의 {i}")

    res = client.get("/api/meetings?page=1&limit=12")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 14
    assert data["pages"] == 2
    assert len(data["items"]) == 12

    res2 = client.get("/api/meetings?page=2&limit=12")
    assert len(res2.json()["items"]) == 2
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_meetings_endpoint.py -v
```

예상 결과: `404 Not Found` 또는 엔드포인트 미존재 에러

- [ ] **Step 3: 엔드포인트 구현**

`backend/app/main.py` 파일 끝(`_save_speakers` 함수 이전 또는 이후)에 추가:

```python
# ---------------------------------------------------------------------------
# 16) GET /api/meetings  — 검색 + 페이지네이션
# ---------------------------------------------------------------------------

@app.get("/api/meetings")
async def list_meetings(q: str = "", page: int = 1, limit: int = 12):
    """제목+요약 검색 + 페이지네이션. 기존 /api/jobs 와 독립적으로 동작."""
    from .database import search_jobs
    return search_jobs(q=q, page=page, limit=limit)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_meetings_endpoint.py -v
```

예상 결과: `3 passed`

- [ ] **Step 5: 전체 백엔드 테스트 통과 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```

예상 결과: `8 passed`

- [ ] **Step 6: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add backend/app/main.py backend/tests/test_meetings_endpoint.py
git commit -m "feat: add GET /api/meetings endpoint with search and pagination"
```

---

## Task 3: 프론트엔드 — Pagination 컴포넌트

**Files:**
- Create: `frontend/components/Pagination.tsx`

**Interfaces:**
- Produces:
  ```tsx
  interface PaginationProps {
    page: number      // 현재 페이지 (1-based)
    pages: number     // 총 페이지 수
    onPageChange: (page: number) => void
  }
  export default function Pagination(props: PaginationProps): JSX.Element | null
  ```

- [ ] **Step 1: Pagination.tsx 생성**

`frontend/components/Pagination.tsx` 생성:

```tsx
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
```

- [ ] **Step 2: 수동 동작 확인 (렌더링 테스트는 Task 5에서 통합 확인)**

`getPageNumbers` 로직을 빠르게 확인:
- page=1, pages=1 → `null` 반환 (컴포넌트 미렌더)
- page=5, pages=10 → `[1, '...', 3, 4, 5, 6, 7, '...', 10]`
- page=1, pages=3 → `[1, 2, 3]`

- [ ] **Step 3: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add frontend/components/Pagination.tsx
git commit -m "feat: add Pagination component with ellipsis page number logic"
```

---

## Task 4: 프론트엔드 — MeetingCard 컴포넌트

**Files:**
- Create: `frontend/components/MeetingCard.tsx`

**Interfaces:**
- Consumes: `Job` from `@/types`
- Produces:
  ```tsx
  interface MeetingCardProps { job: Job }
  export default function MeetingCard(props: MeetingCardProps): JSX.Element
  // 클릭 시 router.push(`/?job=${job.id}`) 실행
  ```

- [ ] **Step 1: MeetingCard.tsx 생성**

`frontend/components/MeetingCard.tsx` 생성:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { Job } from '@/types'

interface MeetingCardProps {
  job: Job
}

function countActionItems(summary: string): number {
  return (summary.match(/- \[ \]/g) || []).length
}

function formatDuration(sec?: number): string {
  if (!sec) return ''
  return `${Math.floor(sec / 60)}분`
}

function formatDate(iso: string): string {
  return iso.slice(0, 10)
}

function getSpeakersLabel(speakers?: Record<string, string>): string {
  if (!speakers) return ''
  const names = Object.values(speakers).filter(v => v && !/^SPEAKER_\d+$/.test(v))
  if (names.length === 0) return ''
  const visible = names.slice(0, 3)
  const rest = names.length - 3
  return rest > 0 ? `${visible.join(', ')} 외 ${rest}명` : visible.join(', ')
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  done:          { label: '완료',      cls: 'bg-green-100 text-green-800' },
  pending:       { label: '대기',      cls: 'bg-blue-100 text-blue-800' },
  converting:    { label: '변환 중',   cls: 'bg-blue-100 text-blue-800' },
  diarizing:     { label: '화자 분리', cls: 'bg-blue-100 text-blue-800' },
  transcribing:  { label: 'STT 중',   cls: 'bg-blue-100 text-blue-800' },
  awaiting_edit: { label: '편집 대기', cls: 'bg-yellow-100 text-yellow-800' },
  summarizing:   { label: '요약 중',   cls: 'bg-blue-100 text-blue-800' },
  error:         { label: '실패',      cls: 'bg-red-100 text-red-800' },
}

export default function MeetingCard({ job }: MeetingCardProps) {
  const router = useRouter()
  const badge = STATUS_BADGE[job.status] ?? { label: job.status, cls: 'bg-gray-100 text-gray-800' }
  const actionCount = job.summary ? countActionItems(job.summary) : 0
  const speakersLabel = getSpeakersLabel(job.speakers)
  const summaryPreview = job.summary
    ? job.summary.replace(/^#+.+$/gm, '').trim().slice(0, 100)
    : ''

  return (
    <div
      onClick={() => router.push(`/?job=${job.id}`)}
      className="bg-white border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all flex flex-col gap-2 min-h-[140px]"
    >
      {/* 제목 + 상태 뱃지 */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-800 text-sm leading-snug line-clamp-2 flex-1">
          {job.title}
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${badge.cls}`}>
          {badge.label}
        </span>
      </div>

      {/* 날짜 + 시간 */}
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <span>{formatDate(job.created_at)}</span>
        {job.duration_sec && (
          <>
            <span>·</span>
            <span>{formatDuration(job.duration_sec)}</span>
          </>
        )}
      </div>

      {/* 참석자 */}
      {speakersLabel && (
        <p className="text-xs text-gray-500 truncate">{speakersLabel}</p>
      )}

      {/* 요약 미리보기 */}
      {summaryPreview && (
        <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed flex-1">
          {summaryPreview}
        </p>
      )}

      {/* 액션 아이템 수 */}
      {actionCount > 0 && (
        <p className="text-xs text-blue-600 font-medium">액션 아이템 {actionCount}건</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript 컴파일 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/frontend
npx tsc --noEmit
```

예상 결과: 오류 없음

- [ ] **Step 3: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add frontend/components/MeetingCard.tsx
git commit -m "feat: add MeetingCard component with status badge and summary preview"
```

---

## Task 5: 프론트엔드 — /meetings 페이지

**Files:**
- Create: `frontend/app/meetings/page.tsx`

**Interfaces:**
- Consumes:
  - `GET /api/meetings?q=&page=&limit=12` → `{items, total, page, pages}`
  - `MeetingCard` from `@/components/MeetingCard`
  - `Pagination` from `@/components/Pagination`
- URL: `/meetings?q=<검색어>&page=<번호>`

- [ ] **Step 1: meetings/page.tsx 생성**

```bash
mkdir -p /Users/liche/Documents/dev/meeting-jr/frontend/app/meetings
```

`frontend/app/meetings/page.tsx` 생성:

```tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Suspense } from 'react'
import { Job } from '@/types'
import MeetingCard from '@/components/MeetingCard'
import Pagination from '@/components/Pagination'

interface MeetingsResponse {
  items: Job[]
  total: number
  page: number
  pages: number
}

function MeetingsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1)
  const [data, setData] = useState<MeetingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchMeetings = useCallback(async (q: string, p: number) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/meetings?q=${encodeURIComponent(q)}&page=${p}&limit=12`)
      if (res.ok) setData(await res.json())
    } finally {
      setLoading(false)
    }
  }, [])

  // 검색어 변경 시 debounce 300ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPage(1)
      router.replace(`/meetings?q=${encodeURIComponent(query)}&page=1`)
      fetchMeetings(query, 1)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query]) // eslint-disable-line react-hooks/exhaustive-deps

  // 페이지 변경 시 즉시 fetch
  useEffect(() => {
    fetchMeetings(query, page)
  }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    router.replace(`/meetings?q=${encodeURIComponent(query)}&page=${newPage}`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA]">
      <div className="max-w-6xl mx-auto px-4 py-6">

        {/* 헤더 */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/"
            className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            ← 돌아가기
          </Link>
          <h1 className="text-xl font-semibold text-gray-800">회의 목록</h1>
        </div>

        {/* 검색 바 */}
        <div className="relative mb-3">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="회의 제목 또는 내용으로 검색..."
            className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        {/* 건수 표시 */}
        {data && (
          <p className="text-xs text-gray-400 mb-4">
            총 {data.total}건 &middot; {data.pages}페이지 중 {data.page}페이지
          </p>
        )}

        {/* 카드 그리드 */}
        {!loading && data && data.items.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400 text-base mb-2">검색 결과가 없습니다</p>
            {query && (
              <button
                onClick={() => setQuery('')}
                className="text-sm text-blue-600 hover:underline"
              >
                검색어 초기화
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data?.items.map(job => <MeetingCard key={job.id} job={job} />)}
          </div>
        )}

        {/* 페이지네이션 */}
        {data && (
          <Pagination
            page={data.page}
            pages={data.pages}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </div>
  )
}

export default function MeetingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <MeetingsContent />
    </Suspense>
  )
}
```

- [ ] **Step 2: TypeScript 컴파일 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/frontend
npx tsc --noEmit
```

예상 결과: 오류 없음

- [ ] **Step 3: 수동 동작 확인**

```bash
# 터미널 1
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000

# 터미널 2
cd /Users/liche/Documents/dev/meeting-jr/frontend
npm run dev
```

브라우저에서 `http://localhost:3000/meetings` 접속 확인:
- [ ] 페이지 로드, 검색바 표시
- [ ] 검색어 입력 시 300ms 후 필터링
- [ ] 결과 없으면 "검색 결과가 없습니다" + 초기화 버튼

- [ ] **Step 4: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add frontend/app/meetings/
git commit -m "feat: add /meetings page with search and pagination"
```

---

## Task 6: 네비게이션 연결 — Sidebar + page.tsx

**Files:**
- Modify: `frontend/components/Sidebar.tsx` (99번째 줄 이후 — 녹음 버튼 div 닫힌 직후)
- Modify: `frontend/app/page.tsx` (useEffect 1개 추가)

**Interfaces:**
- Sidebar: `Link href="/meetings"` 추가 — next/link import 필요
- page.tsx: mount 시 `?job=<id>` 읽어 `setSelectedJobId` 호출, URL 정리

- [ ] **Step 1: Sidebar.tsx 수정 — "전체 목록 보기" 링크 추가**

`frontend/components/Sidebar.tsx` 상단 import에 `Link` 추가:

```tsx
// 기존 import 문 아래에 추가
import Link from 'next/link'
```

녹음 버튼 `</div>` (99번째 줄, `px-3 py-3` div 닫힘) 직후에 추가:

```tsx
      {/* 전체 목록 보기 */}
      <div className="px-3 pb-2">
        <Link
          href="/meetings"
          className="w-full py-1.5 px-3 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg text-xs transition-colors flex items-center gap-2"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          전체 목록 보기
        </Link>
      </div>
```

- [ ] **Step 2: page.tsx 수정 — ?job=<id> 처리**

`frontend/app/page.tsx`의 `Home` 컴포넌트에 useEffect 1개 추가.

기존 `const [sidebarOpen, setSidebarOpen] = useState(false)` 줄 아래에 추가:

```tsx
  // /meetings 에서 카드 클릭 시 /?job=<id> 로 이동 — 해당 job 자동 선택
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const jobId = params.get('job')
    if (jobId) {
      setSelectedJobId(jobId)
      window.history.replaceState({}, '', '/')
    }
  }, [])
```

- [ ] **Step 3: TypeScript 컴파일 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/frontend
npx tsc --noEmit
```

예상 결과: 오류 없음

- [ ] **Step 4: 전체 플로우 수동 확인**

```bash
# 터미널 1 (이미 실행 중이 아닌 경우)
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000

# 터미널 2
cd /Users/liche/Documents/dev/meeting-jr/frontend
npm run dev
```

확인 순서:
- [ ] `http://localhost:3000` → 사이드바에 "전체 목록 보기" 링크 표시
- [ ] 링크 클릭 → `/meetings` 이동
- [ ] 회의가 있으면 카드 그리드 표시, 없으면 빈 상태
- [ ] 카드 클릭 → `/?job=<id>` 이동 후 해당 회의 자동 선택
- [ ] `/meetings?q=기획&page=1` URL 직접 입력 → 검색어 복원
- [ ] 검색 후 다른 페이지 이동 → 검색어 유지, URL 반영
- [ ] 브라우저 뒤로가기 → URL 상태 복원

- [ ] **Step 5: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add frontend/components/Sidebar.tsx frontend/app/page.tsx
git commit -m "feat: wire /meetings page to sidebar and handle ?job= param on home"
```

---

## 자체 검토

### Spec 커버리지
| 스펙 요구사항 | 구현 Task |
|-------------|----------|
| `/meetings` 독립 페이지 | Task 5 |
| 제목+요약 검색 (300ms debounce) | Task 5 |
| 페이지당 12개 | Task 1, 2, 5 |
| 페이지 번호 UI (ellipsis 포함) | Task 3 |
| URL searchParams 연동 | Task 5 |
| 카드: 제목/날짜/시간/참석자/요약/액션수/뱃지 | Task 4 |
| 사이드바 "전체 목록 보기" 링크 | Task 6 |
| 카드 클릭 → `/?job=<id>` | Task 4, 6 |
| 돌아가기 링크 | Task 5 |
| 결과 0건 빈 상태 + 초기화 버튼 | Task 5 |

모든 요구사항 커버됨.

### 타입 일관성
- `Job` 타입: `frontend/types/index.ts`에 정의된 것을 MeetingCard, page.tsx 모두 동일하게 사용
- `search_jobs` 반환 타입: `MeetingsResponse` 인터페이스와 일치
- `Pagination` props: Task 3 정의 → Task 5 사용 일치
