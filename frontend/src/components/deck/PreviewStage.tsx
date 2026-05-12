import type { EditableElement, Slide } from '../../lib/api'

interface PreviewStageProps {
  slide: Slide | null
  onSelectElement: (element: EditableElement | null) => void
}

export function PreviewStage({ slide, onSelectElement }: PreviewStageProps): React.JSX.Element {
  const handleFrameLoad = (event: React.SyntheticEvent<HTMLIFrameElement>): void => {
    const iframe = event.currentTarget
    const doc = iframe.contentDocument
    if (!doc) return

    injectPreviewFitStyles(doc)
    doc.querySelectorAll('[data-edit-id]').forEach((node) => {
      const element = node as HTMLElement
      const isImage = element.tagName.toLowerCase() === 'img'
      element.style.cursor = isImage ? 'move' : 'text'
      element.addEventListener('click', (clickEvent) => {
        clickEvent.preventDefault()
        clickEvent.stopPropagation()
        const computed = iframe.contentWindow?.getComputedStyle(element)
        const image = isImage ? (element as HTMLImageElement) : null
        onSelectElement({
          id: element.dataset.editId || '',
          kind: isImage ? 'image' : 'text',
          text: element.textContent || '',
          color: computed?.color || '',
          fontFamily: computed?.fontFamily || '',
          fontSize: computed?.fontSize || '',
          fontWeight: computed?.fontWeight || '',
          src: image?.src,
          left: computed?.left || '',
          top: computed?.top || '',
          width: computed?.width || '',
          height: computed?.height || '',
          opacity: computed?.opacity || '',
          borderRadius: computed?.borderRadius || '',
          zIndex: computed?.zIndex || '',
        })
      })
    })
  }

  return (
    <div className="slide-frame-wrap">
      {slide ? (
        <iframe
          className="slide-frame"
          onLoad={handleFrameLoad}
          sandbox="allow-same-origin"
          srcDoc={slide.html}
          title={slide.title}
        />
      ) : (
        <p className="muted">No slide selected.</p>
      )}
    </div>
  )
}

function injectPreviewFitStyles(doc: Document): void {
  doc.getElementById('tokenvizppt-preview-fit')?.remove()
  const style = doc.createElement('style')
  style.id = 'tokenvizppt-preview-fit'
  style.textContent = `
    html,
    body {
      width: 100% !important;
      height: 100% !important;
      min-height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: hidden !important;
    }

    body {
      display: grid !important;
      place-items: center !important;
    }

    body > :where(.slide, .ppt-page, .ppt-page-root, [data-ppt-page], article, main) {
      width: 100vw !important;
      max-width: none !important;
      height: 100vh !important;
      max-height: none !important;
      aspect-ratio: 16 / 9 !important;
      margin: 0 !important;
      transform: none !important;
    }
  `
  doc.head.appendChild(style)
}
