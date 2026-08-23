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
    mock_proc.communicate = AsyncMock(return_value=("# 테스트".encode("utf-8"), b""))
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
    mock_proc.communicate = AsyncMock(return_value=("# 테스트".encode("utf-8"), b""))
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
