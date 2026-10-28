"""图片型（扫描件）PDF 的 OCR 兜底。

链路：pypdfium2 把每页渲染成位图 → RapidOCR（ONNX Runtime，复用镜像里已有的
onnxruntime）识别 → 按行重排成文本。

明确的能力边界：
- **只把图变成字**，不恢复表格结构（列对齐在渲染那一刻就丢了）；
- 页数有上限（默认 10 页，环境变量 OCR_MAX_PAGES 可调），且**不会自动调大**——
  单页约 2.5s（CPU），200 页扫描件同步请求会直接超时；
- 识别错字会被后续出题放大，导入后建议人工过一眼。

未安装 OCR 依赖时 `is_available()` 返回 False，调用方保持原有报错行为。
"""

from __future__ import annotations

import logging
import os

LOG = logging.getLogger(__name__)

# 单页渲染倍率：2.0 ≈ 144 DPI，正文小四号字识别率与速度的折中
RENDER_SCALE = 2.0
# 低于该置信度的行直接丢弃（多为噪点、页边装饰）
MIN_LINE_SCORE = 0.35
# 同一行内碎片的纵向容差（像素）
LINE_Y_TOLERANCE = 14
DEFAULT_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "10"))

_engine = None


def is_available() -> bool:
    """OCR 依赖是否可导入（缺依赖时上层要给出明确提示，而不是静默失败）。"""
    try:
        import pypdfium2  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def looks_like_scan(text: str, page_count: int) -> bool:
    """文本层几乎为空即按扫描件处理。

    阈值取「每页平均 50 字符」：正常文字页普遍 800–2000 字，
    而扫描件只剩页眉页码，通常每页 < 30 字。
    """
    stripped = (text or "").strip()
    if page_count <= 0:
        return not stripped
    return len(stripped) / page_count < 50


def _join_line(items: list[tuple[float, float, str, float]]) -> str:
    """把同一纵坐标的碎片拼成一行；中文直接相连，英文之间补空格。"""
    items.sort(key=lambda it: it[0])
    parts: list[str] = []
    for _, _, line, _ in items:
        if parts and _needs_space(parts[-1][-1], line[0]):
            parts.append(" ")
        parts.append(line)
    return "".join(parts).strip()


def _needs_space(prev_char: str, next_char: str) -> bool:
    return prev_char.isascii() and prev_char.isalnum() and next_char.isascii() and next_char.isalnum()


def _recognize(image) -> list[tuple[float, float, str, float]]:
    """对单页位图做识别，返回 [(x, y, 文本, 置信度)]。"""
    engine = _get_engine()
    result, _ = engine(image)
    rows: list[tuple[float, float, str, float]] = []
    for item in result or []:
        try:
            box, text, score = item[0], str(item[1]).strip(), float(item[2])
        except (IndexError, TypeError, ValueError):
            continue
        if not text or score < MIN_LINE_SCORE:
            continue
        ys = [float(p[1]) for p in box]
        xs = [float(p[0]) for p in box]
        rows.append((min(xs), min(ys), text, score))
    return rows


def _rows_to_text(rows: list[tuple[float, float, str, float]]) -> str:
    if not rows:
        return ""
    rows.sort(key=lambda r: (r[1], r[0]))
    lines: list[str] = []
    bucket: list[tuple[float, float, str, float]] = []
    base_y = rows[0][1]
    for row in rows:
        if abs(row[1] - base_y) > LINE_Y_TOLERANCE:
            lines.append(_join_line(bucket))
            bucket = []
            base_y = row[1]
        bucket.append(row)
    if bucket:
        lines.append(_join_line(bucket))

    # 连续重复行（页眉/页脚跨页重复）只保留一次
    deduped: list[str] = []
    for line in lines:
        if not line:
            continue
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return "\n".join(deduped)


def ocr_pdf(raw: bytes, max_pages: int | None = None) -> tuple[str, dict]:
    """对 PDF 逐页 OCR，返回 (文本, 统计信息)。"""
    import numpy as np
    import pypdfium2 as pdfium

    limit = max_pages or DEFAULT_MAX_PAGES
    doc = pdfium.PdfDocument(raw)
    total = len(doc)
    texts: list[str] = []
    try:
        for index in range(min(total, limit)):
            page = doc[index]
            bitmap = page.render(scale=RENDER_SCALE)
            image = np.array(bitmap.to_pil())
            line_text = _rows_to_text(_recognize(image))
            if line_text:
                texts.append(line_text)
            bitmap.close()
            page.close()
    finally:
        doc.close()

    text = "\n\n".join(texts)
    meta = {"pages": total, "pages_ocr": min(total, limit), "truncated": total > limit}
    if meta["truncated"]:
        LOG.warning("扫描件共 %s 页，仅 OCR 前 %s 页（OCR_MAX_PAGES 可调）", total, limit)
    return text, meta
