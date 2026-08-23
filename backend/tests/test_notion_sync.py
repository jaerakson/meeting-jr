"""md_to_notion_blocks 파싱 테스트."""
import pytest
from app.notion_sync import md_to_notion_blocks


def test_heading_1():
    blocks = md_to_notion_blocks("# 제목")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "제목"


def test_heading_2_adds_spacer():
    blocks = md_to_notion_blocks("## 섹션")
    types = [b["type"] for b in blocks]
    assert "paragraph" in types  # spacer
    assert "heading_2" in types


def test_heading_3():
    blocks = md_to_notion_blocks("### 소제목")
    assert blocks[0]["type"] == "heading_3"
    assert blocks[0]["heading_3"]["rich_text"][0]["text"]["content"] == "소제목"


def test_bulleted_list():
    blocks = md_to_notion_blocks("- 항목")
    assert blocks[0]["type"] == "bulleted_list_item"
    assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "항목"


def test_numbered_list():
    blocks = md_to_notion_blocks("1. 첫째\n2. 둘째")
    types = [b["type"] for b in blocks]
    assert types == ["numbered_list_item", "numbered_list_item"]
    assert blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "첫째"
    assert blocks[1]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "둘째"


def test_todo_unchecked():
    blocks = md_to_notion_blocks("- [ ] 할 일")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False
    assert blocks[0]["to_do"]["rich_text"][0]["text"]["content"] == "할 일"


def test_todo_checked():
    blocks = md_to_notion_blocks("- [x] 완료")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is True


def test_quote_block():
    blocks = md_to_notion_blocks("> 인용 텍스트")
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["quote"]["rich_text"][0]["text"]["content"] == "인용 텍스트"


def test_divider():
    blocks = md_to_notion_blocks("---")
    assert blocks[0]["type"] == "divider"


def test_table_basic():
    md = "| 항목 | 내용 |\n|------|------|\n| 일시 | 2024-01-01 |"
    blocks = md_to_notion_blocks(md)
    assert len(blocks) == 1
    tbl = blocks[0]
    assert tbl["type"] == "table"
    assert tbl["table"]["table_width"] == 2
    assert tbl["table"]["has_column_header"] is True
    rows = tbl["table"]["children"]
    assert len(rows) == 2  # 헤더행 + 데이터행 (구분자 행 제외)
    assert rows[0]["table_row"]["cells"][0][0]["text"]["content"] == "항목"
    assert rows[1]["table_row"]["cells"][0][0]["text"]["content"] == "일시"


def test_table_3col():
    md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
    blocks = md_to_notion_blocks(md)
    assert blocks[0]["table"]["table_width"] == 3


def test_bold_annotation():
    blocks = md_to_notion_blocks("- **중요** 텍스트")
    rich = blocks[0]["bulleted_list_item"]["rich_text"]
    bold_parts = [r for r in rich if r.get("annotations", {}).get("bold")]
    assert len(bold_parts) == 1
    assert bold_parts[0]["text"]["content"] == "중요"


def test_plain_text_becomes_paragraph():
    blocks = md_to_notion_blocks("일반 텍스트 줄")
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "일반 텍스트 줄"


def test_table_at_end_of_document():
    """파일 마지막이 테이블인 경우 flush_table()로 처리되는지 확인."""
    md = "# 제목\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    blocks = md_to_notion_blocks(md)
    types = [b["type"] for b in blocks]
    assert "heading_1" in types
    assert "table" in types


def test_empty_lines_ignored():
    blocks = md_to_notion_blocks("\n\n\n")
    assert len(blocks) == 0


def test_callout_in_summary_section():
    """핵심 요약 섹션 내 일반 텍스트는 callout 블록이 된다."""
    md = "## 핵심 요약\n\n일반 텍스트"
    blocks = md_to_notion_blocks(md)
    callouts = [b for b in blocks if b["type"] == "callout"]
    assert len(callouts) == 1
