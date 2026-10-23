"""知识库内容处理：分块（chunking）。"""

import re

from ..config import get_settings

_BLANK_LINE_RE = re.compile(r"\n\s*\n")
_SENTENCE_END_RE = re.compile(r"(?<=[。！？；!?;])")


def _split_long_paragraph(paragraph: str, max_size: int) -> list[str]:
    """超长段落按句读二次切分；仍超长的单句硬切。"""
    sentences = [s for s in _SENTENCE_END_RE.split(paragraph) if s]
    if not sentences:
        return [paragraph[i : i + max_size] for i in range(0, len(paragraph), max_size)]
    blocks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_size:
            if current:
                blocks.append(current)
                current = ""
            blocks.extend(sentence[i : i + max_size] for i in range(0, len(sentence), max_size))
            continue
        if current and len(current) + len(sentence) > max_size:
            blocks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        blocks.append(current)
    return blocks


def chunk_text(text: str, target: int | None = None, max_size: int | None = None) -> list[str]:
    """把长文本切分为目标大小的块。

    策略：先按空行分段；小段直接作为块，超长段按句读细切；
    然后顺序合并相邻块，达到 target 即收块，单个块不超过 max_size。
    """
    settings = get_settings()
    target = target or settings.chunk_target_size
    max_size = max_size or settings.chunk_max_size

    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(normalized) if p.strip()]
    blocks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_size:
            blocks.append(paragraph)
        else:
            blocks.extend(_split_long_paragraph(paragraph, max_size))

    chunks: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) >= target:
            chunks.append(current)
            current = ""
        if not current:
            current = block
        elif len(current) + len(block) + 1 <= max_size:
            current = f"{current}\n{block}"
        else:
            chunks.append(current)
            current = block
    if current:
        chunks.append(current)
    return chunks
