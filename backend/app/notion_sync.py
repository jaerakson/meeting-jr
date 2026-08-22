"""
Notion API 연동: 마크다운 회의록을 Notion 데이터베이스에 등록.

선택 기능 — Notion 환경변수 미설정 시 에러를 반환하되 앱은 중단하지 않는다.
"""

import logging
import os
import re

from dotenv import load_dotenv
from notion_client import AsyncClient

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 마크다운 -> Notion 블록 변환
# ---------------------------------------------------------------------------

# 섹션 키워드 → (h2 색상, 이모지)
_SECTION_STYLES: dict[str, tuple[str, str]] = {
    "핵심 요약":      ("blue",   "💡"),
    "주요 논의":      ("blue",   "🗣️"),
    "주요 결정":      ("green",  "✅"),
    "액션 아이템":    ("orange", "📌"),
    "이슈":           ("red",    "⚠️"),
    "리스크":         ("red",    "⚠️"),
}


def _get_section_style(title: str) -> tuple[str, str]:
    for keyword, style in _SECTION_STYLES.items():
        if keyword in title:
            return style
    return ("default", "")


def _rich_text(text: str) -> list[dict]:
    """Notion rich_text 배열을 생성한다."""
    return [{"type": "text", "text": {"content": text}}]


def _spacer() -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}


def md_to_notion_blocks(md_text: str) -> list[dict]:
    """
    마크다운 문자열을 Notion API 블록 배열로 변환한다.

    지원 문법:
      - # heading   -> heading_1
      - ## heading  -> heading_2 (섹션별 색상 + 이모지)
      - ### heading -> heading_3
      - - [ ] text  -> to_do (unchecked)
      - - [x] text  -> to_do (checked)
      - - text      -> bulleted_list_item
      - 일반 텍스트  -> paragraph (핵심 요약 섹션 내에서는 callout)
      - 빈 줄       -> 무시
      - ---         -> divider
    """
    blocks: list[dict] = []
    lines = md_text.split("\n")
    current_section: str = ""

    for line in lines:
        stripped = line.strip()

        # 빈 줄 무시
        if not stripped:
            continue

        # 구분선
        if re.match(r"^-{3,}$", stripped):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            current_section = ""
            continue

        # 헤딩 (### 먼저 검사)
        h3_match = re.match(r"^###\s+(.+)$", stripped)
        if h3_match:
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": _rich_text(h3_match.group(1))},
            })
            continue

        h2_match = re.match(r"^##\s+(.+)$", stripped)
        if h2_match:
            section_title = h2_match.group(1)
            current_section = section_title
            color, emoji = _get_section_style(section_title)
            label = f"{emoji} {section_title}" if emoji else section_title
            blocks.append(_spacer())
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": _rich_text(label),
                    "color": color,
                },
            })
            continue

        h1_match = re.match(r"^#\s+(.+)$", stripped)
        if h1_match:
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": _rich_text(h1_match.group(1))},
            })
            continue

        # 체크박스 (to_do) — checked
        todo_checked = re.match(r"^-\s+\[x\]\s+(.+)$", stripped, re.IGNORECASE)
        if todo_checked:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": _rich_text(todo_checked.group(1)),
                    "checked": True,
                },
            })
            continue

        # 체크박스 (to_do) — unchecked
        todo_unchecked = re.match(r"^-\s+\[\s?\]\s+(.+)$", stripped)
        if todo_unchecked:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": _rich_text(todo_unchecked.group(1)),
                    "checked": False,
                },
            })
            continue

        # 불릿 리스트
        bullet_match = re.match(r"^-\s+(.+)$", stripped)
        if bullet_match:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": _rich_text(bullet_match.group(1)),
                },
            })
            continue

        # 일반 텍스트: 핵심 요약 섹션 → callout, 나머지 → paragraph
        if "핵심 요약" in current_section:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": _rich_text(stripped),
                    "icon": {"type": "emoji", "emoji": "💡"},
                    "color": "yellow_background",
                },
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(stripped)},
            })

    return blocks


# ---------------------------------------------------------------------------
# Notion 페이지 생성
# ---------------------------------------------------------------------------

async def export_to_notion(title: str, summary_md: str) -> dict:
    """
    마크다운 회의록을 Notion 데이터베이스에 등록한다.

    Args:
        title: 페이지 제목.
        summary_md: 마크다운 형식 회의록 문자열.

    Returns:
        {"url": "생성된 Notion 페이지 URL"}.

    Raises:
        ValueError: NOTION_API_KEY 또는 NOTION_DATABASE_ID 미설정 시.
    """
    from .settings_manager import get_setting
    api_key = get_setting("NOTION_API_KEY")
    database_id = get_setting("NOTION_DATABASE_ID")

    if not api_key:
        raise ValueError(
            "NOTION_API_KEY가 설정되지 않았습니다. "
            "설정 화면에서 Notion API 키를 입력하세요."
        )
    if not database_id:
        raise ValueError(
            "NOTION_DATABASE_ID가 설정되지 않았습니다. "
            "설정 화면에서 Notion 데이터베이스 ID를 입력하세요."
        )

    notion = AsyncClient(auth=api_key)

    # 마크다운 -> Notion 블록 변환
    children = md_to_notion_blocks(summary_md)

    # Notion API는 한 번에 최대 100개 블록만 추가 가능
    # 초과 시 분할 처리
    first_batch = children[:100]
    remaining = children[100:]

    try:
        # 데이터베이스에서 실제 title 속성 이름 조회
        db_meta = await notion.databases.retrieve(database_id=database_id)
        title_prop_name = "title"  # fallback
        for prop_name, prop_info in db_meta.get("properties", {}).items():
            if prop_info.get("type") == "title":
                title_prop_name = prop_name
                break

        page = await notion.pages.create(
            parent={"database_id": database_id},
            icon={"type": "emoji", "emoji": "📋"},
            properties={
                title_prop_name: {
                    "title": [{"text": {"content": title}}],
                },
            },
            children=first_batch,
        )

        page_id = page["id"]

        # 100개 초과 블록 추가
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            await notion.blocks.children.append(
                block_id=page_id,
                children=batch,
            )

        page_url = page.get("url", "")
        logger.info("Notion 페이지 생성 완료: %s", page_url)
        return {"url": page_url, "page_id": page_id}

    except Exception as e:
        err_str = str(e)
        logger.error("Notion API 호출 실패: %s", err_str)
        if "Could not find database" in err_str or "object_not_found" in err_str:
            raise ValueError(
                "데이터베이스를 찾을 수 없습니다. "
                "Notion에서 해당 데이터베이스에 Integration을 연결했는지 확인하세요. "
                "(데이터베이스 우상단 ··· → 연결 → Integration 선택)"
            ) from e
        if "Unauthorized" in err_str or "unauthorized" in err_str or "API token" in err_str:
            raise ValueError(
                "Notion API 키가 유효하지 않습니다. 설정에서 API 키를 다시 확인하세요."
            ) from e
        raise


async def update_notion_page(page_id: str, title: str, summary_md: str) -> dict:
    """기존 Notion 페이지의 내용을 교체한다."""
    from .settings_manager import get_setting
    api_key = get_setting("NOTION_API_KEY")
    if not api_key:
        raise ValueError("NOTION_API_KEY가 설정되지 않았습니다.")

    notion = AsyncClient(auth=api_key)

    # 1. 기존 블록 전체 조회 후 삭제
    children_resp = await notion.blocks.children.list(block_id=page_id, page_size=100)
    for block in children_resp.get("results", []):
        await notion.blocks.delete(block_id=block["id"])

    # 2. 제목 갱신 — DB의 실제 title property 이름을 동적으로 조회
    page_info = await notion.pages.retrieve(page_id=page_id)
    parent = page_info.get("parent", {})
    database_id = parent.get("database_id")

    title_prop_name = "title"  # fallback
    if database_id:
        try:
            db_meta = await notion.databases.retrieve(database_id=database_id)
            for prop_name, prop_info in db_meta.get("properties", {}).items():
                if prop_info.get("type") == "title":
                    title_prop_name = prop_name
                    break
        except Exception:
            logger.warning("DB 메타데이터 조회 실패, title property 이름 fallback 사용")

    await notion.pages.update(
        page_id=page_id,
        properties={
            title_prop_name: {"title": [{"text": {"content": title}}]},
        },
    )

    # 3. 새 블록 추가
    new_blocks = md_to_notion_blocks(summary_md)
    remaining = new_blocks
    while remaining:
        batch = remaining[:100]
        remaining = remaining[100:]
        await notion.blocks.children.append(block_id=page_id, children=batch)

    page = await notion.pages.retrieve(page_id=page_id)
    page_url = page.get("url", "")
    logger.info("Notion 페이지 업데이트 완료: %s", page_url)
    return {"url": page_url, "page_id": page_id}
