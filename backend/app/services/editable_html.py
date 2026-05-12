import re
from html import escape
from uuid import uuid4

TEXT_TAGS = "h1|h2|h3|h4|h5|h6|p|li|span|small|strong|em"
EDITABLE_TAGS = f"{TEXT_TAGS}|div"
STYLE_KEYS = {
    "color": "color",
    "font_family": "font-family",
    "font_size": "font-size",
    "font_weight": "font-weight",
    "left": "left",
    "top": "top",
    "width": "width",
    "height": "height",
    "opacity": "opacity",
    "border_radius": "border-radius",
    "z_index": "z-index",
}


class EditableElementNotFoundError(Exception):
    pass


def ensure_editable_ids(html: str) -> str:
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        tag = match.group("tag")
        attrs = match.group("attrs") or ""
        body = match.group("body")
        if "data-edit-id" in attrs:
            return match.group(0)
        if not _is_editable_body(body):
            return match.group(0)
        counter += 1
        return f'<{tag}{attrs} data-edit-id="text-{counter}">{body}</{tag}>'

    text_pattern = re.compile(
        rf"<(?P<tag>{TEXT_TAGS})(?P<attrs>\s[^>]*)?>(?P<body>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    div_pattern = re.compile(
        r"<(?P<tag>div)(?P<attrs>\s[^>]*)?>(?P<body>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    return div_pattern.sub(replace, text_pattern.sub(replace, html))


def patch_editable_element(
    html: str,
    element_id: str,
    text: str | None = None,
    styles: dict[str, str | None] | None = None,
) -> str:
    safe_id = re.escape(element_id)
    pattern = re.compile(
        rf"(?P<open><(?P<tag>{EDITABLE_TAGS})(?P<attrs>[^>]*)\sdata-edit-id=[\"']{safe_id}[\"'](?P<tail>[^>]*)>)"
        rf"(?P<body>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        raise EditableElementNotFoundError("Editable element not found")

    attrs = f"{match.group('attrs') or ''} data-edit-id=\"{element_id}\"{match.group('tail') or ''}"
    attrs = _patch_style_attr(attrs, styles or {})
    body = escape(text, quote=False) if text is not None else match.group("body")
    replacement = f"<{match.group('tag')}{attrs}>{body}</{match.group('tag')}>"
    return html[: match.start()] + replacement + html[match.end() :]


def patch_image_element(
    html: str,
    element_id: str,
    styles: dict[str, str | None],
) -> str:
    safe_id = re.escape(element_id)
    pattern = re.compile(
        rf"(?P<img><img(?P<attrs>[^>]*)\sdata-edit-id=[\"']{safe_id}[\"'](?P<tail>[^>]*)/?>)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        raise EditableElementNotFoundError("Editable image not found")

    attrs = f"{match.group('attrs') or ''} data-edit-id=\"{element_id}\"{match.group('tail') or ''}"
    attrs = _patch_style_attr(attrs, styles)
    replacement = f"<img{attrs} />"
    return html[: match.start()] + replacement + html[match.end() :]


def delete_editable_element(html: str, element_id: str) -> str:
    safe_id = re.escape(element_id)
    img_pattern = re.compile(
        rf"<img[^>]*\sdata-edit-id=[\"']{safe_id}[\"'][^>]*/?>",
        re.IGNORECASE | re.DOTALL,
    )
    html, count = img_pattern.subn("", html, count=1)
    if count:
        return html

    element_pattern = re.compile(
        rf"<(?P<tag>{EDITABLE_TAGS})(?P<attrs>[^>]*)\sdata-edit-id=[\"']{safe_id}[\"'](?P<tail>[^>]*)>"
        rf".*?</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    html, count = element_pattern.subn("", html, count=1)
    if not count:
        raise EditableElementNotFoundError("Editable element not found")
    return html


def insert_image_element(html: str, image_url: str, alt_text: str) -> str:
    image_id = f"image-{uuid4().hex[:10]}"
    element = (
        f'<img data-edit-id="{image_id}" src="{escape(image_url, quote=True)}" '
        f'alt="{escape(alt_text, quote=True)}" '
        'style="position: fixed; left: 50%; top: 50%; width: 38%; max-height: 56%; '
        'transform: translate(-50%, -50%); object-fit: contain; border-radius: 18px; '
        'box-shadow: 0 18px 48px rgba(0,0,0,0.22); z-index: 30;" />'
    )
    if re.search(r"</body>", html, re.IGNORECASE):
        return re.sub(r"</body>", f"{element}\n</body>", html, count=1, flags=re.IGNORECASE)
    return f"{html}\n{element}"


def _is_editable_body(body: str) -> bool:
    if re.search(rf"<(?:{EDITABLE_TAGS})\b", body, re.IGNORECASE):
        return False
    text = re.sub(r"<[^>]+>", " ", body)
    return bool(re.sub(r"\s+", "", text))


def _patch_style_attr(attrs: str, styles: dict[str, str | None]) -> str:
    css = _parse_style(attrs)
    for api_key, css_key in STYLE_KEYS.items():
        value = styles.get(api_key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            css[css_key] = value
        else:
            css.pop(css_key, None)

    next_style = "; ".join(f"{key}: {value}" for key, value in css.items())
    if next_style:
        next_attrs = re.sub(
            r"\sstyle=[\"'][^\"']*[\"']",
            "",
            attrs,
            flags=re.IGNORECASE,
        )
        return f'{next_attrs} style="{escape(next_style, quote=True)}"'
    return re.sub(r"\sstyle=[\"'][^\"']*[\"']", "", attrs, flags=re.IGNORECASE)


def _parse_style(attrs: str) -> dict[str, str]:
    match = re.search(r"\sstyle=[\"'](?P<style>[^\"']*)[\"']", attrs, re.IGNORECASE)
    if not match:
        return {}
    result: dict[str, str] = {}
    for item in match.group("style").split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            result[key] = value
    return result
