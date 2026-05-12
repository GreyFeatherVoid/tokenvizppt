import re

FORBIDDEN_PATTERNS = [
    r"<script\b",
    r"\bon\w+\s*=",
    r"javascript:",
    r"<iframe\b",
    r"<object\b",
    r"<embed\b",
    r"<link\b",
]

FORBIDDEN_IMAGE_SRC_PATTERNS = [
    r"<img\b[^>]*\ssrc=[\"'](?!/api/assets/)",
]


def validate_slide_html(html: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    text = html.strip()
    if not text:
        errors.append("HTML is empty")
    if not re.search(r"<!doctype html>|<html[\s>]", text, re.IGNORECASE):
        errors.append("Missing HTML document shell")
    if not re.search(r"<body[\s>]", text, re.IGNORECASE):
        errors.append("Missing body")
    if not re.search(r"</body>", text, re.IGNORECASE):
        errors.append("Missing closing body")
    if len(re.sub(r"<[^>]+>", " ", text).strip()) < 80:
        errors.append("Slide has too little visible text")
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"Forbidden HTML pattern: {pattern}")
    for pattern in FORBIDDEN_IMAGE_SRC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            errors.append("Image src must reference an uploaded asset")
    return len(errors) == 0, errors


def extract_html_document(content: str) -> str:
    text = content.strip()
    fenced = re.search(r"```(?:html)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    shell_positions = [text.lower().find("<!doctype"), text.lower().find("<html")]
    start = min([index for index in shell_positions if index >= 0], default=-1)
    if start > 0:
        text = text[start:]
    return text
