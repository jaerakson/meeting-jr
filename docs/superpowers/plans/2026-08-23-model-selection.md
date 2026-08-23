# Claude 모델 선택 + 프롬프트 커스터마이징 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정 모달에서 Claude 모델과 요약 프롬프트를 커스터마이징할 수 있다. 프롬프트는 소스 기본값을 보유하며 초기화 버튼으로 언제든 복원된다.

**Architecture:**
- `CLAUDE_MODEL`, `CLAUDE_PROMPT` 두 키를 기존 settings 시스템(암호화 DB)에 추가
- `summarizer.py`에 `DEFAULT_PROMPT` 상수 정의 (소스 기본값)
- `GET /api/settings/claude-model`, `GET /api/settings/claude-prompt` 엔드포인트 추가 (실제 값 반환)
- `generate_summary(model, prompt_template)`으로 파라미터 전달
- 프롬프트 내 `{script}` 플레이스홀더에 회의 스크립트 삽입
- 설정 모달: 모델 드롭다운 + 프롬프트 textarea + 초기화 버튼 (저장 전 로컬 리셋만)

**Tech Stack:** Python (FastAPI), Next.js/React, Tailwind CSS

## Global Constraints

- Claude CLI 호출 방식 유지 (`claude -p`) — API 키 방식 변경 금지
- 기존 settings 암호화 저장 시스템 그대로 사용 (`settings_manager.py`)
- 모델 미선택 시 기본값: `claude-sonnet-4-6`
- 선택 가능 모델 (하드코딩 고정):
  - `claude-opus-4-6` — Claude Opus 4.6 (고품질, 느림)
  - `claude-sonnet-4-6` — Claude Sonnet 4.6 (기본, 권장)
  - `claude-haiku-4-5-20251001` — Claude Haiku 4.5 (빠름, 경량)
- 프롬프트 플레이스홀더: `{script}` — 스크립트 삽입 위치. 미포함 시 프롬프트 끝에 자동 추가
- 초기화 버튼: DB 저장 없이 textarea 값만 DEFAULT_PROMPT로 복원 (저장은 사용자가 직접)
- 설정 모달 스크롤 가능하도록 본문 영역에 `overflow-y-auto max-h-[80vh]` 적용
- 새 파일 생성 금지 — 기존 파일만 수정

---

### Task 1: 백엔드 — settings 키 추가 + summarizer 파라미터화

**Files:**
- Modify: `backend/app/settings_manager.py`
- Modify: `backend/app/summarizer.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_model_prompt_setting.py`

**Interfaces:**
- Produces:
  - `DEFAULT_PROMPT: str` — summarizer.py 모듈 상수
  - `generate_summary(script_path, speaker_map, job_id, progress_callback=None, model="claude-sonnet-4-6", prompt_template=None) -> str`
  - `GET /api/settings/claude-model` → `{"value": str}`
  - `GET /api/settings/claude-prompt` → `{"value": str, "default": str}`

- [ ] **Step 1: 테스트 작성**

```python
# backend/tests/test_model_prompt_setting.py
import pytest
from unittest.mock import patch, AsyncMock
import asyncio, os, tempfile

def test_setting_keys_include_model_and_prompt():
    from app.settings_manager import SETTING_KEYS
    assert "CLAUDE_MODEL" in SETTING_KEYS
    assert "CLAUDE_PROMPT" in SETTING_KEYS

def test_default_prompt_constant_exists():
    from app.summarizer import DEFAULT_PROMPT
    assert isinstance(DEFAULT_PROMPT, str)
    assert len(DEFAULT_PROMPT) > 100
    assert "{script}" in DEFAULT_PROMPT

@pytest.mark.asyncio
async def test_generate_summary_passes_model_to_cli():
    from app.summarizer import generate_summary
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("[00:00] SPEAKER_00: 테스트입니다.")
        path = f.name
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"# \xed\x85\xec\x8a\xa4\xed\x8a\xb8", b""))
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await generate_summary(path, {}, "job-1", model="claude-opus-4-6")
        args = mock_exec.call_args[0]
        assert "--model" in args
        assert args[list(args).index("--model") + 1] == "claude-opus-4-6"
    os.unlink(path)

@pytest.mark.asyncio
async def test_generate_summary_uses_custom_prompt_template():
    from app.summarizer import generate_summary
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("[00:00] SPEAKER_00: 테스트입니다.")
        path = f.name
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"# \xed\x85\xec\x8a\xa4\xed\x8a\xb8", b""))
    custom_template = "짧게 요약해줘.\n{script}"
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await generate_summary(path, {}, "job-2", prompt_template=custom_template)
        args = mock_exec.call_args[0]
        # -p 다음 인자가 실제 프롬프트
        prompt_idx = list(args).index("-p") + 1
        actual_prompt = args[prompt_idx]
        assert "짧게 요약해줘" in actual_prompt
        assert "[00:00] SPEAKER_00" in actual_prompt
    os.unlink(path)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_model_prompt_setting.py -v
```
Expected: 4개 FAIL

- [ ] **Step 3: settings_manager.py 수정**

```python
SETTING_KEYS = [
    "HF_TOKEN",
    "NOTION_API_KEY",
    "NOTION_DATABASE_ID",
    "DEFAULT_MEETING_TITLE",
    "CLAUDE_MODEL",
    "CLAUDE_PROMPT",
]
```

- [ ] **Step 4: summarizer.py 수정**

파일 상단에 `DEFAULT_PROMPT` 상수 추가 (기존 prompt 문자열을 그대로 추출):

```python
DEFAULT_PROMPT = """다음 회의 스크립트를 분석하여 한국어로 회의록을 작성해주세요.

반드시 아래 마크다운 형식을 정확히 따르세요:

# [회의 주제 / 제목]

- 일시: (날짜 추정)
- 참석자: (화자 목록)
- 회의 목적: ...

## 핵심 요약

1~2줄 핵심 요약

## 주요 논의 및 안건

- 안건 1: ...

## 주요 결정 사항

- 결정 1

## 액션 아이템 (To-Do)

- [ ] @담당자 - 작업 내용 (기한: MM/DD)

## 이슈 및 리스크

- 이슈 1

---
회의 스크립트:
{script}"""
```

`generate_summary` 시그니처 변경:

```python
async def generate_summary(
    script_path: str,
    speaker_map: dict,
    job_id: str,
    progress_callback=None,
    model: str = "claude-sonnet-4-6",
    prompt_template: str | None = None,
) -> str:
```

프롬프트 조립 로직 교체 (기존 `prompt = f"""..."""` 블록 전체 대체):

```python
    template = prompt_template if prompt_template else DEFAULT_PROMPT
    if "{script}" in template:
        prompt = template.replace("{script}", script_content)
    else:
        prompt = template + "\n\n---\n회의 스크립트:\n" + script_content
```

CLI 호출 변경:

```python
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt, "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
```

- [ ] **Step 5: main.py 수정**

`generate_summary` 호출부(약 244번 줄) 수정:

```python
        from .summarizer import generate_summary
        _model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"
        _prompt = get_setting("CLAUDE_PROMPT") or None  # None이면 summarizer에서 DEFAULT_PROMPT 사용

        summary = await generate_summary(
            script_path,
            speaker_map,
            job_id,
            lambda jid, data: update_progress(jid, data),
            model=_model,
            prompt_template=_prompt,
        )
```

`get_setting`이 상단 import에 포함되어 있는지 확인. 없으면 추가:
```python
from .settings_manager import get_settings_status, get_setting, set_setting, SETTING_KEYS
```

엔드포인트 추가 (기존 `/api/settings/default-title` 엔드포인트 아래):

```python
@app.get("/api/settings/claude-model")
async def get_claude_model():
    """현재 설정된 Claude 모델 반환. 미설정 시 기본값."""
    return {"value": get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"}


@app.get("/api/settings/claude-prompt")
async def get_claude_prompt():
    """현재 설정된 프롬프트 반환. 미설정 시 빈 문자열. default도 함께 반환."""
    from .summarizer import DEFAULT_PROMPT
    return {
        "value": get_setting("CLAUDE_PROMPT") or "",
        "default": DEFAULT_PROMPT,
    }
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
cd backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_model_prompt_setting.py -v
```
Expected: 4/4 PASS

- [ ] **Step 7: 기존 테스트 회귀 확인**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 8: 커밋**

```bash
git add backend/app/settings_manager.py backend/app/summarizer.py backend/app/main.py backend/tests/test_model_prompt_setting.py
git commit -m "feat: Claude 모델/프롬프트 설정 키 추가 + generate_summary 파라미터화"
```

---

### Task 2: 프론트엔드 — 설정 모달 모델/프롬프트 UI 추가

**Files:**
- Modify: `frontend/components/SettingsModal.tsx`

**Interfaces:**
- Consumes:
  - `GET /api/settings/claude-model` → `{"value": string}`
  - `GET /api/settings/claude-prompt` → `{"value": string, "default": string}`
  - `PATCH /api/settings` body에 `CLAUDE_MODEL`, `CLAUDE_PROMPT` 포함

- [ ] **Step 1: state 및 fetch 추가**

추가할 상수 (컴포넌트 외부):
```typescript
const CLAUDE_MODELS = [
  { value: "claude-sonnet-4-6",        label: "Claude Sonnet 4.6 (기본, 권장)" },
  { value: "claude-opus-4-6",          label: "Claude Opus 4.6 (고품질, 느림)" },
  { value: "claude-haiku-4-5-20251001",label: "Claude Haiku 4.5 (빠름, 경량)" },
]
```

추가할 state:
```typescript
const [claudeModel, setClaudeModel] = useState("claude-sonnet-4-6")
const [initialClaudeModel, setInitialClaudeModel] = useState("claude-sonnet-4-6")
const [claudePrompt, setClaudePrompt] = useState("")
const [initialClaudePrompt, setInitialClaudePrompt] = useState("")
const [defaultPrompt, setDefaultPrompt] = useState("")  // 서버에서 받은 DEFAULT_PROMPT
```

useEffect에 추가:
```typescript
fetch('/api/settings/claude-model')
  .then(r => r.json())
  .then(d => { setClaudeModel(d.value); setInitialClaudeModel(d.value) })
  .catch(console.error)
fetch('/api/settings/claude-prompt')
  .then(r => r.json())
  .then(d => {
    setClaudePrompt(d.value)        // 커스텀 프롬프트 (없으면 빈 문자열)
    setInitialClaudePrompt(d.value)
    setDefaultPrompt(d.default)     // 소스 기본값 (초기화용)
  })
  .catch(console.error)
```

- [ ] **Step 2: handleSave 수정**

```typescript
const body: Record<string, string> = {
  DEFAULT_MEETING_TITLE: defaultTitle,
  CLAUDE_MODEL: claudeModel,
  CLAUDE_PROMPT: claudePrompt,   // 빈 문자열이면 DB에서 삭제 → 기본값 사용
}
```

`setInitialClaudeModel`, `setInitialClaudePrompt` 저장 후 갱신:
```typescript
setInitialDefaultTitle(defaultTitle)
setInitialClaudeModel(claudeModel)
setInitialClaudePrompt(claudePrompt)
```

저장 버튼 disabled 조건:
```typescript
disabled={saving || saved || (
  KEYS.every(k => values[k] === '') &&
  defaultTitle === initialDefaultTitle &&
  claudeModel === initialClaudeModel &&
  claudePrompt === initialClaudePrompt
)}
```

- [ ] **Step 3: UI 추가**

모달 본문(`<div className="px-6 py-5 space-y-5">`) 에 `overflow-y-auto max-h-[70vh]` 추가:
```tsx
<div className="px-6 py-5 space-y-5 overflow-y-auto max-h-[70vh]">
```

기본 회의 제목 아래에 **모델 선택** 섹션 추가:
```tsx
{/* 모델 선택 */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1.5">
    회의록 생성 모델
  </label>
  <select
    value={claudeModel}
    onChange={e => setClaudeModel(e.target.value)}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
  >
    {CLAUDE_MODELS.map(m => (
      <option key={m.value} value={m.value}>{m.label}</option>
    ))}
  </select>
  <p className="mt-1 text-xs text-gray-400">회의록 요약 시 사용할 Claude 모델을 선택합니다.</p>
</div>
```

모델 선택 아래에 **프롬프트 커스터마이징** 섹션 추가:
```tsx
{/* 프롬프트 커스터마이징 */}
<div>
  <div className="flex items-center justify-between mb-1.5">
    <label className="text-sm font-medium text-gray-700">
      요약 프롬프트
    </label>
    <button
      type="button"
      onClick={() => setClaudePrompt(defaultPrompt)}
      className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
    >
      초기화
    </button>
  </div>
  <textarea
    value={claudePrompt || defaultPrompt}
    onChange={e => setClaudePrompt(e.target.value)}
    rows={10}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs text-gray-800 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
    placeholder="프롬프트를 입력하세요. {script} 위치에 회의 스크립트가 삽입됩니다."
  />
  <p className="mt-1 text-xs text-gray-400">
    <code className="bg-gray-100 px-1 rounded">{'{script}'}</code> 플레이스홀더 위치에 회의 스크립트가 삽입됩니다. 미포함 시 자동으로 끝에 추가됩니다.
  </p>
</div>
```

- [ ] **Step 4: 동작 확인 (수동)**

1. 브라우저 `http://localhost:3000` 설정 모달 열기
2. 모델 드롭다운 정상 표시 확인
3. 프롬프트 textarea에 기본값 표시 확인
4. "초기화" 클릭 → textarea가 기본값으로 복원되는지 확인 (DB 저장 안 됨)
5. 모델 변경 + 저장 → 새로고침 후 선택값 유지 확인
6. 프롬프트 수정 + 저장 → 새로고침 후 수정값 유지 확인
7. 프롬프트 전체 삭제 + 저장 → 기본 프롬프트로 동작하는지 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/components/SettingsModal.tsx
git commit -m "feat: 설정 모달에 모델 선택 드롭다운 + 프롬프트 커스터마이징 추가"
```

---

### Task 3: 통합 검증

**Files:**
- Test: `backend/tests/test_model_prompt_setting.py` (확장)

- [ ] **Step 1: API 엔드포인트 응답 확인**

```bash
# 모델 엔드포인트
curl -s http://localhost:8000/api/settings/claude-model
# Expected: {"value":"claude-sonnet-4-6"}

# 프롬프트 엔드포인트
curl -s http://localhost:8000/api/settings/claude-prompt | python3 -c "import json,sys; d=json.load(sys.stdin); print('value len:', len(d['value']), '/ default len:', len(d['default']))"
# Expected: default len > 100

# 설정 저장
curl -s -X PATCH http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"CLAUDE_MODEL":"claude-opus-4-6"}' | python3 -c "import json,sys; print(json.load(sys.stdin))"
# Expected: {"status":"ok"}

# 저장 확인
curl -s http://localhost:8000/api/settings/claude-model
# Expected: {"value":"claude-opus-4-6"}
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
cd backend
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 3: 커밋**

```bash
git add .
git commit -m "test: 모델/프롬프트 설정 통합 검증 완료"
```
