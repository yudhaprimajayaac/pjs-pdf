"""
Core logic to resize a PDF (e.g. a shipping label of arbitrary size) into a
fixed target size (e.g. 100x100 mm), optionally cropping away blank space
and adding a clean margin — similar to converting a tall A6-ish label PDF
into a compact square 100x100 mm label.

Modes:
- "stretch": non-uniform scaling that fills the whole target area exactly
  (width and height may scale by different factors). Good for turning an
  odd aspect-ratio label into an exact square.
- "fit": uniform scaling that preserves the original aspect ratio and
  centers the content inside the target area (extra space becomes margin).

auto_crop (default True): detects the bounding box of actual content
(text, images/barcodes, vector drawings) on the page and uses that instead
of the full page — this removes trailing blank space so the result looks
"full" like a proper 100x100 label instead of a shrunk mostly-blank page.
"""

from io import BytesIO
import pymupdf  # PyMuPDF

MM_TO_PT = 72.0 / 25.4  # 1 mm in PDF points


def mm_to_pt(mm: float) -> float:
    return mm * MM_TO_PT


def _detect_content_bbox(page):
    """Union bounding box of text, images and vector drawings on the page."""
    rect = None

    for block in page.get_text("blocks"):
        r = pymupdf.Rect(block[:4])
        if not r.is_empty:
            rect = r if rect is None else (rect | r)

    for img in page.get_images(full=True):
        try:
            bbox = page.get_image_bbox(img)
            if bbox and not bbox.is_empty:
                rect = bbox if rect is None else (rect | bbox)
        except Exception:
            pass

    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r and not r.is_empty:
                rect = r if rect is None else (rect | r)
    except Exception:
        pass

    if rect is None:
        rect = page.rect
    else:
        rect = rect & page.rect  # clamp to page bounds

    return rect


def resize_pdf(
    input_bytes: bytes,
    target_width_mm: float = 100.0,
    target_height_mm: float = 100.0,
    margin_mm: float = 0.0,
    mode: str = "stretch",
    auto_crop: bool = True,
) -> bytes:
    """
    Rebuild every page of the input PDF onto a new page of
    target_width_mm x target_height_mm, with margin_mm of blank margin
    on all sides.

    mode: "stretch" (fill exactly, non-uniform scale) or
          "fit" (preserve aspect ratio, centered, extra space becomes margin)
    auto_crop: if True, first crop to the detected content bounding box so
               trailing blank space on the source page is discarded.
    """
    if target_width_mm <= 0 or target_height_mm <= 0:
        raise ValueError("Target width/height must be positive")
    if margin_mm < 0:
        raise ValueError("Margin cannot be negative")
    if mode not in ("stretch", "fit"):
        raise ValueError("mode must be 'stretch' or 'fit'")

    target_w = mm_to_pt(target_width_mm)
    target_h = mm_to_pt(target_height_mm)
    margin = mm_to_pt(margin_mm)

    avail_w = target_w - 2 * margin
    avail_h = target_h - 2 * margin
    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("Margin is too large for the target size")

    src = pymupdf.open(stream=input_bytes, filetype="pdf")
    out = pymupdf.open()

    for page_num in range(len(src)):
        page = src[page_num]

        if auto_crop:
            clip = _detect_content_bbox(page)
        else:
            clip = page.rect

        clip_w = clip.width
        clip_h = clip.height
        if clip_w <= 0 or clip_h <= 0:
            clip = page.rect
            clip_w, clip_h = clip.width, clip.height

        new_page = out.new_page(width=target_w, height=target_h)

        if mode == "stretch":
            dest = pymupdf.Rect(margin, margin, margin + avail_w, margin + avail_h)
        else:  # "fit"
            scale = min(avail_w / clip_w, avail_h / clip_h)
            w = clip_w * scale
            h = clip_h * scale
            x0 = margin + (avail_w - w) / 2
            y0 = margin + (avail_h - h) / 2
            dest = pymupdf.Rect(x0, y0, x0 + w, y0 + h)

        new_page.show_pdf_page(dest, src, page_num, clip=clip)

    result = out.tobytes(garbage=4, deflate=True)
    out.close()
    src.close()
    return result
