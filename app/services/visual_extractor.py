"""
Visual content extraction (Phase 4): finds embedded raster images AND
vector-drawn charts/graphs on each page, extracts/renders them, and asks a
vision model to describe them. Each description becomes its own chunk —
element_type="image" for raster figures/photos, element_type="chart" for
vector-drawn charts.

This is intentionally a separate, self-contained module (not merged into
pdf_parser.py or table_extractor.py) — the pipeline stays: TextExtractor,
TableExtractor, and this VisualExtractor each own one concern, and only
VisualExtractor talks to a VisionProvider.
"""
import fitz  # pymupdf
from app.services.caption_utils import find_nearby_caption
from app.services.vision_provider import get_vision_provider

FIGURE_CAPTION_PREFIXES = ("figure", "fig.", "chart", "diagram")
CAPTION_MAX_WORDS = 20

# Raster images below this size are almost always decorative (bullet icons,
# logos, thin divider graphics) rather than meaningful figures — skip them
# so they don't waste a vision-model call on nothing useful.
MIN_IMAGE_DIMENSION_PX = 150

# Vector-drawing clustering: how close two drawing bounding boxes need to be
# (in PDF points) to be treated as parts of the same chart, and how many
# distinct drawing items a cluster needs before it's treated as a real
# chart rather than a simple decorative box/border/underline.
CLUSTER_MERGE_DISTANCE = 15
MIN_DRAWINGS_PER_CHART = 8


def _extract_raster_images(page, doc, page_number: int) -> list[dict]:
    """Finds embedded raster images (photos, scanned figures, logos-sized-up, etc.)."""
    results = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue

        if base_image["width"] < MIN_IMAGE_DIMENSION_PX or base_image["height"] < MIN_IMAGE_DIMENSION_PX:
            continue  # too small to be a meaningful figure

        rects = page.get_image_rects(xref)
        bbox = tuple(rects[0]) if rects else None

        results.append({
            "image_bytes": base_image["image"],
            "bbox": bbox,
            "page": page_number,
            "kind": "image",
        })

    return results


def _cluster_drawings(drawings: list[dict]) -> list[fitz.Rect]:
    """
    Merges nearby/overlapping drawing bounding boxes into clusters. A chart
    is typically made of many small path segments (bars, axis ticks,
    gridlines) scattered close together — clustering turns that scatter
    into one bounding region per chart, and keeps two side-by-side charts
    on the same page as two separate clusters instead of merging them.
    """
    rects = [fitz.Rect(d["rect"]) for d in drawings if d.get("rect")]
    if not rects:
        return []

    clusters: list[list[fitz.Rect]] = [[r] for r in rects]

    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                bbox_i = fitz.Rect()
                for r in clusters[i]:
                    bbox_i |= r
                bbox_j = fitz.Rect()
                for r in clusters[j]:
                    bbox_j |= r
                expanded_i = fitz.Rect(bbox_i.x0 - CLUSTER_MERGE_DISTANCE, bbox_i.y0 - CLUSTER_MERGE_DISTANCE,
                                        bbox_i.x1 + CLUSTER_MERGE_DISTANCE, bbox_i.y1 + CLUSTER_MERGE_DISTANCE)
                if expanded_i.intersects(bbox_j):
                    clusters[i].extend(clusters[j])
                    del clusters[j]
                    merged = True
                    break
            if merged:
                break

    # Only keep clusters with enough drawing items to plausibly be a real
    # chart — a simple box border or a single underline is 1-4 path items,
    # a bar/line chart with axis + gridlines + data series is typically
    # dozens.
    plausible_clusters = [c for c in clusters if len(c) >= MIN_DRAWINGS_PER_CHART]

    bboxes = []
    for cluster in plausible_clusters:
        bbox = fitz.Rect()
        for r in cluster:
            bbox |= r
        bboxes.append(bbox)

    return bboxes


def _extract_vector_charts(page, page_number: int) -> list[dict]:
    """Finds vector-drawn chart regions (matplotlib-style graphs with no embedded image)."""
    drawings = page.get_drawings()
    chart_bboxes = _cluster_drawings(drawings)

    results = []
    for bbox in chart_bboxes:
        pix = page.get_pixmap(clip=bbox, matrix=fitz.Matrix(2, 2))
        results.append({
            "image_bytes": pix.tobytes("png"),
            "bbox": tuple(bbox),
            "page": page_number,
            "kind": "chart",
        })

    return results


def extract_visuals_from_pdf(file_path: str, display_name: str | None = None) -> list[dict]:
    """
    Returns a list of visual-content chunks ready for the chunker:
    {"text": <description>, "page": ..., "source": ..., "element_type": "image"|"chart"}
    """
    filename = display_name or file_path.split("\\")[-1].split("/")[-1]

    doc = fitz.open(file_path)
    candidates = []

    for page_number, page in enumerate(doc, start=1):
        candidates.extend(_extract_raster_images(page, doc, page_number))
        candidates.extend(_extract_vector_charts(page, page_number))

    if not candidates:
        doc.close()
        return []

    # Best-effort caption lookup per candidate, using its own page.
    # PyMuPDF's get_text("words") returns tuples (x0, y0, x1, y1, word, ...);
    # adapt to the {"text", "top"} shape the shared caption utility expects.
    contexts = []
    for c in candidates:
        page = doc[c["page"] - 1]
        if c["bbox"]:
            page_words = [{"text": w[4], "top": w[1]} for w in page.get_text("words")]
            caption = find_nearby_caption(page_words, c["bbox"], FIGURE_CAPTION_PREFIXES, CAPTION_MAX_WORDS)
        else:
            caption = None
        contexts.append(caption)

    provider = get_vision_provider()
    descriptions = provider.describe_batch(
        [c["image_bytes"] for c in candidates],
        contexts,
    )

    results = []
    for c, caption, description in zip(candidates, contexts, descriptions):
        text = f"{caption}\n\n{description}" if caption else description
        results.append({
            "text": text,
            "page": c["page"],
            "source": filename,
            "element_type": c["kind"],
        })

    doc.close()
    return results


if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python visual_extractor.py <path_to_pdf>")
    else:
        visuals = extract_visuals_from_pdf(test_file)
        print(f"Found {len(visuals)} visual(s).")
        for i, v in enumerate(visuals, start=1):
            print(f"\n--- Visual {i} (page {v['page']}, {v['element_type']}) ---")
            print(v["text"])