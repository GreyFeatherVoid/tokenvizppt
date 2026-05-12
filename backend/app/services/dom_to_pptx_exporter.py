import base64
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright

from app.core.settings import get_settings
from app.services.db_session_repository import get_db_session_repository
from app.services.session_store import SessionNotFoundError, get_session_store, safe_session_id

SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5
VIEWPORT_WIDTH = 1600
VIEWPORT_HEIGHT = 900


@dataclass
class ExportedPptx:
    path: Path
    url: str


async def export_session_with_dom_to_pptx(session_id: str) -> ExportedPptx:
    session_id = safe_session_id(session_id)
    session = _load_session(session_id)
    export_root = get_settings().storage_root / "exports" / session_id
    export_root.mkdir(parents=True, exist_ok=True)
    output_path = export_root / f"{session_id}.pptx"

    bundle_path = _dom_to_pptx_bundle_path()
    slide_html = [slide["html"] for slide in session["slides"]]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=1,
            )
            await page.set_content(_export_shell_html(), wait_until="load")
            await page.add_script_tag(path=str(bundle_path))
            pptx_base64 = await page.evaluate(
                _export_script(),
                {
                    "slides": slide_html,
                    "fileName": output_path.name,
                    "width": SLIDE_WIDTH_IN,
                    "height": SLIDE_HEIGHT_IN,
                },
            )
        finally:
            await browser.close()

    output_path.write_bytes(base64.b64decode(pptx_base64))
    return ExportedPptx(
        path=output_path,
        url=f"/api/exports/{session_id}/{output_path.name}",
    )


def _load_session(session_id: str) -> dict:
    try:
        return get_db_session_repository().get_session_detail(session_id)
    except SessionNotFoundError:
        return get_session_store().get_session(session_id)


def _dom_to_pptx_bundle_path() -> Path:
    path = (
        Path(__file__).resolve().parents[2]
        / "node_modules/dom-to-pptx/dist/dom-to-pptx.bundle.js"
    )
    if not path.exists():
        raise RuntimeError(
            "dom-to-pptx is not installed. Run `npm install` inside the backend directory."
        )
    return path


def _export_shell_html() -> str:
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html,
      body {
        width: 1600px;
        min-height: 900px;
        margin: 0;
        padding: 0;
        background: #fff;
      }

      body {
        display: block !important;
        overflow: visible;
      }

      .tokenviz-dom-pptx-page {
        position: relative;
        width: 1600px;
        height: 900px;
        margin: 0;
        padding: 0;
        overflow: hidden;
      }

      .tokenviz-dom-pptx-page
        > :is(.slide, .ppt-page, .ppt-page-root, [data-ppt-page], article, main, section) {
        margin: 0 !important;
      }
    </style>
  </head>
  <body>
    <main id="tokenviz-export-root"></main>
  </body>
</html>
"""


def _export_script() -> str:
    return """
async ({ slides, fileName, width, height }) => {
  if (!window.domToPptx?.exportToPptx) {
    throw new Error('dom-to-pptx browser bundle did not load');
  }

  const root = document.getElementById('tokenviz-export-root');
  const parser = new DOMParser();
  const slideElements = [];

  for (let index = 0; index < slides.length; index += 1) {
    const doc = parser.parseFromString(slides[index], 'text/html');

    for (const style of Array.from(doc.querySelectorAll('style'))) {
      document.head.appendChild(style.cloneNode(true));
    }
    for (const link of Array.from(doc.querySelectorAll('link[rel="stylesheet"]'))) {
      document.head.appendChild(link.cloneNode(true));
    }

    const page = document.createElement('section');
    page.className = 'tokenviz-dom-pptx-page';

    for (const child of Array.from(doc.body.children)) {
      page.appendChild(child.cloneNode(true));
    }
    root.appendChild(page);

    const candidates = Array.from(
      page.querySelectorAll(
        '[data-ppt-page], .ppt-page, .ppt-page-root, .slide, article, main, section'
      )
    );
    const slide = candidates
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter((item) => item.rect.width > 320 && item.rect.height > 180)
      .sort((a, b) => b.rect.width * b.rect.height - a.rect.width * a.rect.height)[0]?.element;
    if (!slide) {
      throw new Error(`No slide root found for slide ${index + 1}`);
    }
    slideElements.push(slide);
  }

  await document.fonts?.ready;
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

  const blob = await window.domToPptx.exportToPptx(slideElements, {
    fileName,
    skipDownload: true,
    autoEmbedFonts: true,
    svgAsVector: true,
    width,
    height,
  });
  const buffer = await blob.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}
"""
