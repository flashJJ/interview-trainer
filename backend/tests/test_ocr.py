"""图片型 PDF 的 OCR 兜底：扫描件判定 + 端到端识别。

端到端用例用 PIL 合成「只有图像、没有文本层」的 PDF，走完整的
`extract_pdf_text → looks_like_scan → ocr_pdf → pypdfium2 + RapidOCR` 链路。
用英文样本是为了在无中文字体的 CI（ubuntu）上也能跑。
"""

from __future__ import annotations

import io
import os

import pytest

from app.services import ocr
from app.services.importers import extract_pdf_text

SCAN_LINES = [
    "Cache penetration means querying keys that do not exist.",
    "A bloom filter can reject those keys before hitting database.",
]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


class TestLooksLikeScan:
    def test_text_pdf_is_not_scan(self):
        assert not ocr.looks_like_scan("正文内容" * 500, 1)

    def test_empty_text_is_scan(self):
        assert ocr.looks_like_scan("", 3)
        assert ocr.looks_like_scan("   \n  ", 1)

    def test_page_numbers_only_is_scan(self):
        # 扫描件常只剩页眉/页码，别被这点文字骗过去
        assert ocr.looks_like_scan("第 1 页\n第 2 页\n第 3 页", 3)

    def test_zero_page_edge_case(self):
        assert ocr.looks_like_scan("", 0)
        assert not ocr.looks_like_scan("有正文" * 100, 0)


def _font(size: int = 36):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_scanned_pdf(lines: list[str], pages: int = 1) -> bytes:
    """生成没有文本层（纯图像）的 PDF，模拟扫描件。"""
    from PIL import Image, ImageDraw

    images = []
    for _ in range(pages):
        img = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(img)
        y = 90
        for line in lines:
            draw.text((80, y), line, font=_font(), fill="black")
            y += 65
        images.append(img)

    buffer = io.BytesIO()
    images[0].save(
        buffer, format="PDF", save_all=True, append_images=images[1:], resolution=150
    )
    return buffer.getvalue()


@pytest.mark.skipif(not ocr.is_available(), reason="未安装 OCR 依赖（pypdfium2 / rapidocr）")
class TestScannedPdfEndToEnd:
    def test_image_only_pdf_has_no_text_layer(self):
        from pypdf import PdfReader

        raw = make_scanned_pdf(SCAN_LINES)
        text = PdfReader(io.BytesIO(raw)).pages[0].extract_text() or ""
        assert len(text.strip()) == 0  # 确认样本确实是「图片型」

    def test_extract_pdf_text_falls_back_to_ocr(self):
        raw = make_scanned_pdf(SCAN_LINES)
        text = extract_pdf_text(raw)
        assert len(text.strip()) >= 30
        assert "bloom" in text.lower()  # 关键词能识别出来

    def test_too_many_pages_is_capped(self, monkeypatch):
        monkeypatch.setattr(ocr, "DEFAULT_MAX_PAGES", 1)
        raw = make_scanned_pdf(SCAN_LINES, pages=2)
        text, meta = ocr.ocr_pdf(raw, max_pages=1)
        assert meta["truncated"] is True
        assert meta["pages"] == 2 and meta["pages_ocr"] == 1
        assert text.strip()
