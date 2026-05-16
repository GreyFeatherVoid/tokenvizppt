import html
import math
import re
from typing import Any

SLIDE_W_IN = 13.333
SLIDE_H_IN = 7.5
HTML_W_PX = 1280
HTML_H_PX = 720
PX_PER_IN_X = HTML_W_PX / SLIDE_W_IN
PX_PER_IN_Y = HTML_H_PX / SLIDE_H_IN

LAYOUT_INTENTS = {
    "cover",
    "data-focus",
    "comparison",
    "timeline",
    "concept",
    "process",
    "summary",
    "quote",
    "image-focus",
}

FONT_FACES = {"Aptos", "Calibri", "Arial", "Georgia"}


class SlideSpecValidationError(ValueError):
    pass


def build_slide_spec(args: dict[str, Any]) -> dict[str, Any]:
    outline = args["outline"]
    slide = args["slide"]
    page_number = int(args["page_number"])
    total_pages = int(args["total_pages"])
    palette = _palette(outline)
    intent = _normalize_intent(slide.get("layout_intent"), page_number, total_pages)
    content = [
        _compact(str(point), 150) for point in slide.get("content") or [] if str(point).strip()
    ][:5]
    title = _compact(str(slide.get("title") or f"Slide {page_number}"), 120)
    message = _compact(str(slide.get("main_message") or ""), 180)

    elements = _base_elements(outline, args, page_number, total_pages, palette, intent)
    if intent == "cover":
        elements.extend(_build_cover(title, message, content, palette))
    elif intent == "comparison":
        elements.extend(_build_comparison(title, message, content, palette))
    elif intent in {"timeline", "process"}:
        elements.extend(_build_timeline(title, message, content, palette))
    elif intent in {"summary", "quote"}:
        elements.extend(_build_summary(title, message, content, palette))
    elif intent == "data-focus":
        elements.extend(_build_data_focus(title, message, content, palette))
    else:
        elements.extend(_build_feature_grid(title, message, content, palette))

    return {
        "version": 1,
        "title": title,
        "layoutIntent": intent,
        "size": {"width": SLIDE_W_IN, "height": SLIDE_H_IN},
        "background": palette["background"],
        "palette": palette,
        "elements": elements,
    }


def normalize_slide_spec(
    spec: dict[str, Any],
    *,
    min_elements: int = 4,
    min_text_elements: int = 2,
) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise SlideSpecValidationError("SlideSpec must be an object")

    title = _compact(str(spec.get("title") or "Untitled slide"), 120)
    intent = _normalize_intent(spec.get("layoutIntent") or spec.get("layout_intent"), 2, 3)
    palette = spec.get("palette") if isinstance(spec.get("palette"), dict) else {}
    background = _valid_hex(spec.get("background")) or _valid_hex(palette.get("background"))
    if not background:
        raise SlideSpecValidationError("SlideSpec background must be a hex color")

    raw_elements = spec.get("elements")
    if not isinstance(raw_elements, list):
        raise SlideSpecValidationError("SlideSpec elements must be an array")
    if not min_elements <= len(raw_elements) <= 42:
        raise SlideSpecValidationError(f"SlideSpec must contain {min_elements}-42 elements")

    elements = [_normalize_element(item, index) for index, item in enumerate(raw_elements)]
    elements = _drop_overlapping_decorative_text(elements)
    elements = fit_text_elements_for_rendering(order_elements_for_rendering(elements))
    elements = _resolve_text_overlaps(elements)
    text_count = sum(1 for item in elements if item["kind"] == "text")
    if text_count < min_text_elements:
        raise SlideSpecValidationError(
            f"SlideSpec must contain at least {min_text_elements} text elements"
        )
    _validate_text_overlap(elements)

    return {
        "version": 1,
        "title": title,
        "layoutIntent": intent,
        "size": {"width": SLIDE_W_IN, "height": SLIDE_H_IN},
        "background": background,
        "palette": _normalize_palette(palette, background),
        "elements": elements,
    }


def insert_image_into_spec(spec: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_slide_spec(spec)
    elements = list(normalized.get("elements") or [])
    image_count = sum(1 for item in elements if item.get("kind") == "image")
    image = _image(
        f"image-{asset['id'][:8]}-{image_count + 1}",
        7.15,
        2.04,
        4.82,
        3.42,
        str(asset["url"]),
        alt=str(asset.get("file_name") or ""),
        radius=0.14,
    )
    if image_count:
        image["x"] = 6.88
        image["y"] = min(5.4, 1.4 + image_count * 0.42)
    elements.append(image)
    normalized["elements"] = elements
    return normalize_slide_spec(normalized)


def patch_element_in_spec(
    spec: dict[str, Any],
    element_id: str,
    *,
    text: str | None = None,
    styles: dict[str, str | None] | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    normalized = normalize_slide_spec(spec)
    elements = list(normalized.get("elements") or [])
    index = next((idx for idx, item in enumerate(elements) if item.get("id") == element_id), -1)
    if index < 0:
        raise SlideSpecValidationError(f"Element {element_id} not found")

    if delete:
        normalized["elements"] = [item for item in elements if item.get("id") != element_id]
        return normalize_slide_spec(normalized, min_elements=2, min_text_elements=1)

    element = {**elements[index]}
    styles = styles or {}
    if element.get("kind") == "text":
        if text is not None:
            element["text"] = text
        if styles.get("color"):
            element["color"] = _css_to_hex(styles["color"])
        if styles.get("font_family"):
            font_face = str(styles["font_family"]).split(",", 1)[0].strip().strip("\"'")
            element["fontFace"] = font_face
        if styles.get("font_size"):
            element["fontSize"] = _css_size_to_points(styles["font_size"])
        if styles.get("font_weight"):
            element["bold"] = _css_weight_to_bold(styles["font_weight"])
    elif element.get("kind") == "image":
        if styles.get("left"):
            element["x"] = _css_size_to_inches(styles["left"], PX_PER_IN_X)
        if styles.get("top"):
            element["y"] = _css_size_to_inches(styles["top"], PX_PER_IN_Y)
        if styles.get("width"):
            element["w"] = _css_size_to_inches(styles["width"], PX_PER_IN_X)
        if styles.get("height"):
            element["h"] = _css_size_to_inches(styles["height"], PX_PER_IN_Y)
        if styles.get("opacity"):
            element["opacity"] = _clamp_float(styles["opacity"], 0.05, 1)
        if styles.get("border_radius"):
            element["radius"] = _css_size_to_inches(styles["border_radius"], PX_PER_IN_X)

    elements[index] = element
    normalized["elements"] = elements
    return normalize_slide_spec(normalized)


def render_slide_spec_html(spec: dict[str, Any]) -> str:
    bg = _css_color(spec.get("background"), "#F6EFE4")
    elements = "\n".join(
        _render_element_html(element)
        for element in prepare_elements_for_rendering(spec.get("elements") or [])
    )
    title = html.escape(str(spec.get("title") or "Slide"))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      * {{ box-sizing: border-box; }}
      html, body {{
        width: 100%;
        height: 100%;
        margin: 0;
        background: #dfe3e8;
        font-family: Aptos, Calibri, Arial, sans-serif;
        color: #1f2937;
      }}
      body {{
        display: grid;
        place-items: center;
        padding: 24px;
      }}
      .slide {{
        position: relative;
        width: {HTML_W_PX}px;
        height: {HTML_H_PX}px;
        overflow: hidden;
        background: {bg};
        border: 1px solid rgba(31, 41, 55, 0.14);
        box-shadow: 0 24px 70px rgba(31, 41, 55, 0.16);
      }}
      .shape, .text-box {{
        position: absolute;
      }}
      .text-box {{
        margin: 0;
        white-space: pre-wrap;
        overflow-wrap: break-word;
        overflow: hidden;
      }}
    </style>
  </head>
  <body>
    <section class="slide" data-ppt-page>
{elements}
    </section>
  </body>
</html>
"""


def prepare_elements_for_rendering(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return fit_text_elements_for_rendering(order_elements_for_rendering(elements))


def order_elements_for_rendering(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        element
        for _, element in sorted(
            enumerate(elements),
            key=lambda item: (_render_layer_rank(item[1]), item[0]),
        )
    ]


def _render_layer_rank(element: dict[str, Any]) -> int:
    kind = element.get("kind")
    if kind == "shape":
        return 0
    if kind == "image":
        return 1
    if kind == "text":
        return 2
    return 3


def fit_text_elements_for_rendering(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fitted = [{**element} for element in elements]
    text_indexes = [index for index, element in enumerate(fitted) if element.get("kind") == "text"]
    shapes = [element for element in fitted if element.get("kind") == "shape"]
    for index in text_indexes:
        element = fitted[index]
        available_h = _available_text_height(
            element,
            [fitted[item] for item in text_indexes],
            shapes,
        )
        current_h = float(element.get("h") or 0)
        element["h"] = max(0.08, min(max(current_h, available_h), available_h))
        font_size = float(element.get("fontSize") or 12)
        line_height = float(element.get("lineHeight") or 1.16)
        while (
            font_size > 8
            and _estimate_text_height(
                str(element.get("text") or ""),
                float(element.get("w") or 0),
                font_size,
                line_height,
                bold=bool(element.get("bold")),
            )
            > float(element["h"])
        ):
            font_size -= 0.5
        element["fontSize"] = round(font_size, 1)
    return fitted


def _available_text_height(
    element: dict[str, Any],
    texts: list[dict[str, Any]],
    shapes: list[dict[str, Any]] | None = None,
) -> float:
    y = float(element.get("y") or 0)
    current_h = float(element.get("h") or 0)
    max_h = SLIDE_H_IN - y - 0.08
    container = _text_container_bounds(element, shapes or [])
    if container:
        max_h = min(max_h, max(0.08, container["bottom"] - y - 0.12))
    required_h = _estimate_text_height(
        str(element.get("text") or ""),
        float(element.get("w") or 0),
        float(element.get("fontSize") or 12),
        float(element.get("lineHeight") or 1.16),
        bold=bool(element.get("bold")),
    )
    for other in texts:
        if other is element:
            continue
        other_y = float(other.get("y") or 0)
        if other_y <= y:
            continue
        if _horizontal_overlap_ratio(element, other) < 0.22:
            continue
        max_h = min(max_h, max(0.08, other_y - y - 0.08))
    return max(0.08, min(max(current_h, required_h), max_h))


def _text_container_bounds(
    element: dict[str, Any],
    shapes: list[dict[str, Any]],
) -> dict[str, float] | None:
    text_x = float(element.get("x") or 0)
    text_y = float(element.get("y") or 0)
    text_w = float(element.get("w") or 0)
    text_h = float(element.get("h") or 0)
    center_x = text_x + text_w / 2
    center_y = text_y + min(text_h / 2, 0.18)
    candidates: list[dict[str, float]] = []
    for shape in shapes:
        shape_x = float(shape.get("x") or 0)
        shape_y = float(shape.get("y") or 0)
        shape_w = float(shape.get("w") or 0)
        shape_h = float(shape.get("h") or 0)
        area = shape_w * shape_h
        if area <= 0 or area > SLIDE_W_IN * SLIDE_H_IN * 0.72:
            continue
        if not (
            shape_x - 0.04 <= center_x <= shape_x + shape_w + 0.04
            and shape_y - 0.04 <= center_y <= shape_y + shape_h + 0.04
        ):
            continue
        if text_w > shape_w + 0.12:
            continue
        candidates.append(
            {
                "x": shape_x,
                "y": shape_y,
                "right": shape_x + shape_w,
                "bottom": shape_y + shape_h,
                "area": area,
            }
        )
    if not candidates:
        return None
    return min(candidates, key=lambda item: item["area"])


def _estimate_text_height(
    text: str,
    width_in: float,
    font_size_pt: float,
    line_height: float,
    *,
    bold: bool = False,
) -> float:
    lines = _estimate_text_lines(text, width_in, font_size_pt, bold=bold)
    return lines * font_size_pt / 72 * line_height + 0.04


def _estimate_text_lines(text: str, width_in: float, font_size_pt: float, *, bold: bool) -> int:
    capacity = _text_line_capacity(width_in, font_size_pt, bold=bold)
    explicit_lines = str(text or "").splitlines() or [""]
    return sum(max(1, math.ceil(_text_visual_units(line) / capacity)) for line in explicit_lines)


def _text_line_capacity(width_in: float, font_size_pt: float, *, bold: bool) -> float:
    chars_per_inch_at_12pt = 5.05 if bold else 5.35
    return max(3.0, width_in * chars_per_inch_at_12pt * 12 / max(font_size_pt, 1))


def _text_visual_units(text: str) -> float:
    total = 0.0
    for char in text:
        if char.isspace():
            total += 0.35
        elif re.match(r"[\u3400-\u9fff\uf900-\ufaff]", char):
            total += 1.0
        elif char in "，。；：！？、“”‘’（）《》—…":
            total += 0.75
        else:
            total += 0.55
    return total


def _horizontal_overlap_ratio(current: dict[str, Any], other: dict[str, Any]) -> float:
    left = max(float(current.get("x") or 0), float(other.get("x") or 0))
    right = min(
        float(current.get("x") or 0) + float(current.get("w") or 0),
        float(other.get("x") or 0) + float(other.get("w") or 0),
    )
    overlap = max(0.0, right - left)
    smaller = min(float(current.get("w") or 0), float(other.get("w") or 0))
    return overlap / smaller if smaller > 0 else 0.0


def _base_elements(
    outline: dict[str, Any],
    args: dict[str, Any],
    page_number: int,
    total_pages: int,
    palette: dict[str, str],
    intent: str,
) -> list[dict[str, Any]]:
    elements = [
        _shape("wash-left", -0.42, -0.28, 3.2, 3.2, palette["wash"], radius=1.6),
        _shape("wash-right", 10.9, 5.3, 3.0, 2.5, palette["soft_accent"], radius=1.2),
        _shape("accent-rule", 0.62, 0.42, 0.68, 0.05, palette["accent"], radius=0.02),
        _text(
            "eyebrow",
            1.42,
            0.36,
            4.6,
            0.24,
            str(outline.get("deck_title") or args.get("topic") or "tokenvizPPT").upper(),
            8.5,
            palette["accent"],
            bold=True,
            letter_spacing=1.1,
        ),
        _text(
            "page",
            12.05,
            0.38,
            0.72,
            0.24,
            f"{page_number} / {total_pages}",
            8.5,
            palette["muted"],
        ),
    ]
    if intent in {"cover", "quote", "summary"}:
        elements.append(_shape("hero-panel", 8.45, 0.0, 4.88, 7.5, palette["ink"], radius=0))
    return elements


def _build_cover(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    kicker = content[0] if content else message
    return [
        _text(
            "title",
            0.72,
            1.72,
            7.25,
            1.6,
            title,
            34,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.78, 3.55, 6.65, 0.62, message or kicker, 15, palette["muted"]),
        _shape(
            "cover-chip",
            0.78,
            4.6,
            3.35,
            0.56,
            palette["surface"],
            border=palette["line"],
            radius=0.18,
        ),
        _text("cover-chip-text", 1.02, 4.78, 2.9, 0.18, kicker, 8.5, palette["accent"], bold=True),
        _text(
            "cover-side",
            8.95,
            1.38,
            3.25,
            1.28,
            "Structured narrative, visual hierarchy, editable output.",
            18,
            palette["surface"],
            bold=True,
            font_face="Georgia",
        ),
        _shape("cover-side-line", 8.95, 3.06, 2.3, 0.04, palette["accent"], radius=0.02),
    ]


def _build_feature_grid(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    items = content or [message]
    elements = [
        _text(
            "title",
            0.72,
            0.86,
            8.3,
            0.58,
            title,
            24,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.72, 1.48, 8.9, 0.34, message, 11.5, palette["muted"]),
    ]
    for index, point in enumerate(items[:4]):
        row = index // 2
        col = index % 2
        x = 0.72 + col * 6.18
        y = 2.24 + row * 2.04
        elements.extend(
            [
                _shape(
                    f"card-{index}",
                    x,
                    y,
                    5.64,
                    1.56,
                    palette["card"],
                    border=palette["line"],
                    radius=0.16,
                ),
                _text(
                    f"card-index-{index}",
                    x + 0.28,
                    y + 0.25,
                    0.45,
                    0.2,
                    f"0{index + 1}",
                    10,
                    palette["accent"],
                    bold=True,
                ),
                _text(
                    f"card-title-{index}",
                    x + 0.86,
                    y + 0.22,
                    4.12,
                    0.26,
                    _short_heading(point, index + 1),
                    13.5,
                    palette["ink"],
                    bold=True,
                    font_face="Georgia",
                ),
                _text(
                    f"card-body-{index}",
                    x + 0.86,
                    y + 0.64,
                    4.4,
                    0.62,
                    point,
                    9.4,
                    palette["muted"],
                ),
            ]
        )
    return elements


def _build_comparison(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    split = max(1, len(content) // 2)
    left = content[:split] or [message]
    right = content[split:] or content[:1] or [message]
    elements = [
        _text(
            "title",
            0.72,
            0.86,
            8.9,
            0.58,
            title,
            24,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.72, 1.5, 8.9, 0.34, message, 11.5, palette["muted"]),
        _shape(
            "left-panel",
            0.72,
            2.14,
            5.78,
            4.22,
            palette["card"],
            border=palette["line"],
            radius=0.18,
        ),
        _shape("right-panel", 6.82, 2.14, 5.78, 4.22, palette["ink"], radius=0.18),
        _text(
            "left-label", 1.08, 2.48, 3.8, 0.24, "Current frame", 10, palette["accent"], bold=True
        ),
        _text(
            "right-label", 7.18, 2.48, 3.8, 0.24, "Target frame", 10, palette["accent"], bold=True
        ),
    ]
    for index, point in enumerate(left[:3]):
        elements.append(
            _text(
                f"left-{index}", 1.08, 3.02 + index * 0.82, 4.72, 0.44, point, 10.4, palette["ink"]
            )
        )
    for index, point in enumerate(right[:3]):
        elements.append(
            _text(
                f"right-{index}",
                7.18,
                3.02 + index * 0.82,
                4.72,
                0.44,
                point,
                10.4,
                palette["surface"],
            )
        )
    return elements


def _build_data_focus(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    items = content or [message]
    elements = [
        _text(
            "title",
            0.72,
            0.86,
            7.5,
            0.56,
            title,
            23,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.72, 1.44, 7.2, 0.36, message, 11.4, palette["muted"]),
        _shape("metric-panel", 0.72, 2.16, 4.7, 3.92, palette["ink"], radius=0.18),
        _text(
            "metric-number",
            1.14,
            2.78,
            3.5,
            0.9,
            _metric_text(items[0]),
            38,
            palette["surface"],
            bold=True,
            font_face="Georgia",
        ),
        _text("metric-label", 1.16, 3.82, 3.58, 0.72, items[0], 11.4, palette["surface"]),
    ]
    for index, point in enumerate(items[1:4]):
        y = 2.28 + index * 1.24
        elements.extend(
            [
                _shape(
                    f"data-bar-bg-{index}", 6.08, y + 0.44, 5.38, 0.16, palette["line"], radius=0.05
                ),
                _shape(
                    f"data-bar-{index}",
                    6.08,
                    y + 0.44,
                    2.9 + index * 0.72,
                    0.16,
                    palette["accent"],
                    radius=0.05,
                ),
                _text(
                    f"data-point-{index}",
                    6.08,
                    y,
                    5.6,
                    0.38,
                    point,
                    10.8,
                    palette["ink"],
                    bold=index == 0,
                ),
            ]
        )
    return elements


def _build_summary(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    items = content or [message]
    elements = [
        _text(
            "title",
            0.76,
            1.1,
            7.15,
            1.02,
            title,
            30,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.82, 2.52, 6.3, 0.56, message, 14, palette["muted"]),
        _text(
            "quote-mark",
            8.92,
            1.0,
            1.2,
            0.72,
            "“",
            46,
            palette["accent"],
            bold=True,
            font_face="Georgia",
        ),
    ]
    for index, point in enumerate(items[:3]):
        elements.append(
            _text(
                f"summary-{index}",
                8.96,
                2.0 + index * 1.1,
                3.12,
                0.58,
                point,
                12.4,
                palette["surface"],
                bold=index == 0,
            )
        )
    return elements


def _build_timeline(
    title: str,
    message: str,
    content: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    items = content or [
        "Open with the situation.",
        "Move into the evidence.",
        "Close with concrete next steps.",
    ]
    elements = [
        _text(
            "title",
            0.72,
            0.86,
            8.5,
            0.56,
            title,
            24,
            palette["ink"],
            bold=True,
            font_face="Georgia",
        ),
        _text("message", 0.72, 1.5, 8.4, 0.34, message, 11.5, palette["muted"]),
        _shape("timeline-line", 1.18, 3.42, 10.9, 0.05, palette["accent"], radius=0.02),
    ]
    for index, point in enumerate(items[:4]):
        x = 0.9 + index * 3.0
        elements.extend(
            [
                _shape(
                    f"timeline-node-{index}", x, 3.17, 0.52, 0.52, palette["accent"], radius=0.26
                ),
                _text(
                    f"timeline-index-{index}",
                    x + 0.15,
                    3.31,
                    0.24,
                    0.12,
                    str(index + 1),
                    8.5,
                    palette["surface"],
                    bold=True,
                ),
                _text(
                    f"timeline-title-{index}",
                    x,
                    4.0,
                    2.36,
                    0.34,
                    _short_heading(point, index + 1),
                    14,
                    palette["ink"],
                    bold=True,
                    font_face="Georgia",
                ),
                _text(f"timeline-body-{index}", x, 4.48, 2.46, 0.82, point, 9.4, palette["muted"]),
            ]
        )
    return elements


def _shape(
    element_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    *,
    border: str | None = None,
    radius: float = 0.08,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "kind": "shape",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "fill": fill,
        "border": border,
        "radius": radius,
    }


def _text(
    element_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    font_size: float,
    color: str,
    *,
    bold: bool = False,
    font_face: str = "Aptos",
    letter_spacing: float = 0,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "kind": "text",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "text": text,
        "fontSize": font_size,
        "fontFace": font_face,
        "color": color,
        "bold": bold,
        "letterSpacing": letter_spacing,
        "lineHeight": 1.16,
    }


def _image(
    element_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    src: str,
    *,
    alt: str = "",
    radius: float = 0,
    opacity: float = 1,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "kind": "image",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "src": src,
        "alt": alt,
        "radius": radius,
        "opacity": opacity,
    }


def _render_element_html(element: dict[str, Any]) -> str:
    x = float(element["x"]) * PX_PER_IN_X
    y = float(element["y"]) * PX_PER_IN_Y
    w = float(element["w"]) * PX_PER_IN_X
    h = float(element["h"]) * PX_PER_IN_Y
    if element["kind"] == "shape":
        styles = [
            f"left:{x:.2f}px",
            f"top:{y:.2f}px",
            f"width:{w:.2f}px",
            f"height:{h:.2f}px",
            f"background:{_css_color(element.get('fill'), '#FFFFFF')}",
            f"border-radius:{float(element.get('radius') or 0) * PX_PER_IN_X:.2f}px",
        ]
        if element.get("border"):
            styles.append(f"border:1px solid {_css_color(element.get('border'), '#000000')}")
        return f'      <div class="shape" style="{";".join(styles)}"></div>'

    if element["kind"] == "image":
        styles = [
            f"left:{x:.2f}px",
            f"top:{y:.2f}px",
            f"width:{w:.2f}px",
            f"height:{h:.2f}px",
            "object-fit:contain",
            f"border-radius:{float(element.get('radius') or 0) * PX_PER_IN_X:.2f}px",
            f"opacity:{float(element.get('opacity') or 1):.3f}",
        ]
        edit_id = html.escape(str(element["id"]), quote=True)
        src = html.escape(str(element.get("src") or ""), quote=True)
        alt = html.escape(str(element.get("alt") or ""), quote=True)
        return (
            f'      <img class="shape" data-edit-id="{edit_id}" '
            f'src="{src}" alt="{alt}" style="{";".join(styles)}" />'
        )

    font = html.escape(str(element.get("fontFace") or "Aptos"))
    styles = [
        f"left:{x:.2f}px",
        f"top:{y:.2f}px",
        f"width:{w:.2f}px",
        f"height:{h:.2f}px",
        f"font-size:{float(element.get('fontSize') or 12) * 96 / 72:.2f}px",
        f"font-family:{font}, Calibri, Arial, sans-serif",
        f"color:{_css_color(element.get('color'), '#111827')}",
        f"font-weight:{'800' if element.get('bold') else '400'}",
        f"line-height:{float(element.get('lineHeight') or 1.16)}",
        f"letter-spacing:{float(element.get('letterSpacing') or 0):.2f}px",
    ]
    text = html.escape(str(element.get("text") or ""))
    return (
        f'      <p class="text-box" data-edit-id="{html.escape(str(element["id"]))}" '
        f'style="{";".join(styles)}">{text}</p>'
    )


def _palette(outline: dict[str, Any]) -> dict[str, str]:
    raw = outline.get("design_contract", {}).get("palette") or []
    colors = [str(color) for color in raw if str(color).startswith("#")]
    while len(colors) < 5:
        colors.append(["#F6EFE4", "#26324A", "#B77A3B", "#5F6E63", "#FFFDF8"][len(colors)])
    return {
        "background": colors[0],
        "ink": colors[1],
        "accent": colors[2],
        "muted": colors[3],
        "surface": "#FFFDF8",
        "card": "#FBF8F2",
        "line": "#D5C7B8",
        "wash": _soften(colors[3], "#E8EEE5"),
        "soft_accent": _soften(colors[2], "#F1DDC7"),
    }


def _normalize_palette(value: dict, background: str) -> dict[str, str]:
    return {
        "background": background,
        "ink": _valid_hex(value.get("ink")) or "#26324A",
        "accent": _valid_hex(value.get("accent")) or "#B77A3B",
        "muted": _valid_hex(value.get("muted")) or "#5F6E63",
        "surface": _valid_hex(value.get("surface")) or "#FFFDF8",
        "card": _valid_hex(value.get("card")) or "#FBF8F2",
        "line": _valid_hex(value.get("line")) or "#D5C7B8",
        "wash": _valid_hex(value.get("wash")) or "#E8EEE5",
        "soft_accent": _valid_hex(value.get("soft_accent")) or "#F1DDC7",
    }


def _normalize_element(item: object, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SlideSpecValidationError(f"Element {index} must be an object")
    kind = str(item.get("kind") or "").strip()
    if kind not in {"text", "shape", "image"}:
        raise SlideSpecValidationError(f"Element {index} kind must be text, shape, or image")
    element_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(item.get("id") or f"element-{index}"))
    x = _clamp_float(item.get("x"), 0, SLIDE_W_IN - 0.1)
    y = _clamp_float(item.get("y"), 0, SLIDE_H_IN - 0.1)
    w = _clamp_float(item.get("w"), 0.08, SLIDE_W_IN - x)
    h = _clamp_float(item.get("h"), 0.08, SLIDE_H_IN - y)

    if kind == "shape":
        fill = _valid_hex(item.get("fill"))
        if not fill:
            raise SlideSpecValidationError(f"Shape {element_id} must have a hex fill")
        element = _shape(
            element_id,
            x,
            y,
            w,
            h,
            fill,
            border=_valid_hex(item.get("border")),
            radius=_clamp_float(item.get("radius"), 0, 1.5),
        )
        return element

    if kind == "image":
        src = str(item.get("src") or "").strip()
        if not src.startswith("/api/assets/"):
            raise SlideSpecValidationError(f"Image {element_id} must reference an uploaded asset")
        return _image(
            element_id,
            x,
            y,
            w,
            h,
            src,
            alt=str(item.get("alt") or ""),
            radius=_clamp_float(item.get("radius"), 0, 1.5),
            opacity=_clamp_float(item.get("opacity"), 0.05, 1),
        )

    text = _compact(str(item.get("text") or ""), 260)
    if not text:
        raise SlideSpecValidationError(f"Text {element_id} must not be empty")
    color = _valid_hex(item.get("color"))
    if not color:
        raise SlideSpecValidationError(f"Text {element_id} must have a hex color")
    return {
        "id": element_id,
        "kind": "text",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "text": text,
        "fontSize": _clamp_float(item.get("fontSize"), 7, 40),
        "fontFace": str(item.get("fontFace") or "Aptos")
        if str(item.get("fontFace") or "Aptos") in FONT_FACES
        else "Aptos",
        "color": color,
        "bold": bool(item.get("bold")),
        "letterSpacing": _clamp_float(item.get("letterSpacing"), -0.5, 2.5),
        "lineHeight": _clamp_float(item.get("lineHeight"), 1.0, 1.45),
    }


def _validate_text_overlap(elements: list[dict[str, Any]]) -> None:
    texts = [item for item in elements if item["kind"] == "text"]
    for index, current in enumerate(texts):
        current_area = current["w"] * current["h"]
        if current_area <= 0:
            continue
        for other in texts[index + 1 :]:
            overlap_w = max(
                0,
                min(current["x"] + current["w"], other["x"] + other["w"])
                - max(current["x"], other["x"]),
            )
            overlap_h = max(
                0,
                min(current["y"] + current["h"], other["y"] + other["h"])
                - max(current["y"], other["y"]),
            )
            overlap = overlap_w * overlap_h
            smaller = min(current_area, other["w"] * other["h"])
            if smaller > 0 and overlap / smaller > 0.18:
                raise SlideSpecValidationError(
                    f"Text elements overlap too much: {current['id']} and {other['id']}"
                )


def _resolve_text_overlaps(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = [{**element} for element in elements]
    shapes = [element for element in resolved if element.get("kind") == "shape"]
    for _ in range(8):
        pair = _first_text_overlap_pair(resolved)
        if not pair:
            return resolved
        current_index, other_index = pair
        current = resolved[current_index]
        other = resolved[other_index]
        if _is_decorative_text(current) and not _is_decorative_text(other):
            current_index, other_index = other_index, current_index
            current = resolved[current_index]
            other = resolved[other_index]
        moved = _move_text_below(current, other, shapes)
        if not moved:
            moved = _move_text_right(current, other)
        if not moved:
            moved = _shrink_text_height(current, other)
        if not moved:
            break
    return fit_text_elements_for_rendering(order_elements_for_rendering(resolved))


def _first_text_overlap_pair(elements: list[dict[str, Any]]) -> tuple[int, int] | None:
    text_indexes = [index for index, item in enumerate(elements) if item["kind"] == "text"]
    for left_pos, current_index in enumerate(text_indexes):
        current = elements[current_index]
        for other_index in text_indexes[left_pos + 1 :]:
            other = elements[other_index]
            if _text_overlap_ratio(current, other) > 0.18:
                return current_index, other_index
    return None


def _move_text_below(
    current: dict[str, Any],
    other: dict[str, Any],
    shapes: list[dict[str, Any]] | None = None,
) -> bool:
    target_y = float(current["y"]) + float(current["h"]) + 0.1
    max_bottom = SLIDE_H_IN - 0.18
    current_container = _text_container_bounds(current, shapes or [])
    other_container = _text_container_bounds(other, shapes or [])
    if current_container and other_container and current_container == other_container:
        max_bottom = min(max_bottom, current_container["bottom"] - 0.12)
    if target_y + float(other["h"]) <= max_bottom:
        other["y"] = round(target_y, 3)
        return True
    return False


def _move_text_right(current: dict[str, Any], other: dict[str, Any]) -> bool:
    target_x = float(current["x"]) + float(current["w"]) + 0.14
    if target_x + float(other["w"]) <= SLIDE_W_IN - 0.18:
        other["x"] = round(target_x, 3)
        return True
    return False


def _shrink_text_height(current: dict[str, Any], other: dict[str, Any]) -> bool:
    if float(current["y"]) <= float(other["y"]):
        available = float(other["y"]) - float(current["y"]) - 0.08
        target = current
    else:
        available = float(current["y"]) - float(other["y"]) - 0.08
        target = other
    if available >= 0.12 and available < float(target["h"]):
        target["h"] = round(available, 3)
        target["fontSize"] = max(7, round(float(target.get("fontSize") or 12) - 1, 1))
        return True
    return False


def _drop_overlapping_decorative_text(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dropped_ids: set[str] = set()
    texts = [item for item in elements if item["kind"] == "text"]
    for index, current in enumerate(texts):
        if current["id"] in dropped_ids:
            continue
        current_area = current["w"] * current["h"]
        if current_area <= 0:
            continue
        for other in texts[index + 1 :]:
            if other["id"] in dropped_ids:
                continue
            overlap_ratio = _text_overlap_ratio(current, other)
            if overlap_ratio <= 0.18:
                continue
            if _is_decorative_text(current) and not _is_decorative_text(other):
                dropped_ids.add(current["id"])
            elif _is_decorative_text(other):
                dropped_ids.add(other["id"])
    if not dropped_ids:
        return elements
    return [item for item in elements if item.get("id") not in dropped_ids]


def _text_overlap_ratio(current: dict[str, Any], other: dict[str, Any]) -> float:
    overlap_w = max(
        0,
        min(current["x"] + current["w"], other["x"] + other["w"])
        - max(current["x"], other["x"]),
    )
    overlap_h = max(
        0,
        min(current["y"] + current["h"], other["y"] + other["h"])
        - max(current["y"], other["y"]),
    )
    overlap = overlap_w * overlap_h
    smaller = min(current["w"] * current["h"], other["w"] * other["h"])
    return overlap / smaller if smaller > 0 else 0


def _is_decorative_text(element: dict[str, Any]) -> bool:
    element_id = str(element.get("id") or "").lower()
    text = str(element.get("text") or "").strip()
    decorative_ids = ("arrow", "icon", "deco", "ornament", "divider", "rule", "line", "dot")
    if any(token in element_id for token in decorative_ids) and len(text) <= 8:
        return True
    decorative_chars = set("→←↑↓↗↘↙↖➜➔➝➞•·●○◦—–-_|/\\")
    return bool(text) and len(text) <= 4 and all(char in decorative_chars for char in text)


def _normalize_intent(value: object, page_number: int, total_pages: int) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    if normalized in LAYOUT_INTENTS:
        return normalized
    if page_number == 1:
        return "cover"
    if page_number == total_pages:
        return "summary"
    return "concept"


def _css_color(value: object, fallback: str) -> str:
    raw = str(value or fallback).strip()
    return raw if raw.startswith("#") else fallback


def _valid_hex(value: object) -> str | None:
    raw = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
        return raw.upper()
    return None


def _css_to_hex(value: object) -> str:
    raw = str(value or "").strip()
    valid = _valid_hex(raw)
    if valid:
        return valid
    match = re.fullmatch(
        r"rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*[\d.]+)?\s*\)",
        raw,
        re.IGNORECASE,
    )
    if not match:
        raise SlideSpecValidationError(f"Invalid CSS color: {raw}")
    return "#" + "".join(
        f"{max(0, min(255, round(float(part)))):02X}" for part in match.groups()[:3]
    )


def _css_size_to_points(value: object) -> float:
    raw = str(value or "").strip().lower()
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|pt)?", raw)
    if not match:
        raise SlideSpecValidationError(f"Invalid CSS font size: {raw}")
    amount = float(match.group(1))
    return amount * 72 / 96 if match.group(2) == "px" else amount


def _css_size_to_inches(value: object, px_per_inch: float) -> float:
    raw = str(value or "").strip().lower()
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|in)?", raw)
    if not match:
        raise SlideSpecValidationError(f"Invalid CSS size: {raw}")
    amount = float(match.group(1))
    return amount / px_per_inch if match.group(2) == "px" else amount


def _css_weight_to_bold(value: object) -> bool:
    raw = str(value or "").strip().lower()
    if raw in {"bold", "bolder"}:
        return True
    if raw in {"normal", "lighter"}:
        return False
    try:
        return int(float(raw)) >= 600
    except ValueError:
        return False


def _clamp_float(value: object, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = low
    return max(low, min(high, round(parsed, 4)))


def _short_heading(text: str, fallback_index: int) -> str:
    words = str(text).replace(":", " ").split()
    if not words:
        return f"Point {fallback_index}"
    return " ".join(words[:3]).strip(".,;")[:32]


def _compact(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip(" ,.;:") + "…"


def _metric_text(text: str) -> str:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?\s*(?:%|x|k|m|bn|万|亿)?", text, flags=re.I)
    return match.group(0) if match else "3"


def _soften(value: str, fallback: str) -> str:
    raw = value.strip().replace("#", "")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        return fallback
    r = int(raw[0:2], 16)
    g = int(raw[2:4], 16)
    b = int(raw[4:6], 16)
    r = round(r * 0.18 + 255 * 0.82)
    g = round(g * 0.18 + 255 * 0.82)
    b = round(b * 0.18 + 255 * 0.82)
    return f"#{r:02X}{g:02X}{b:02X}"
