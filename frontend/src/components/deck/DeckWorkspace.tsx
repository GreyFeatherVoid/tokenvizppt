import { useEffect, useState } from 'react'
import type {
  Asset,
  EditableElement,
  PatchSlideElementPayload,
  SessionDetail,
  Slide,
  SlideVersion,
} from '../../lib/api'
import { EditorPanel } from './EditorPanel'
import { PreviewStage } from './PreviewStage'
import { SlideSidebar } from './SlideSidebar'

interface DeckWorkspaceProps {
  deck: SessionDetail
  selectedSlide: Slide | null
  selectedSlideId: string | null
  editing: boolean
  editError: string | null
  slideVersions: SlideVersion[]
  historyLoading: boolean
  assets: Asset[]
  assetLoading: boolean
  exporting: boolean
  exportUrl: string | null
  onSelectSlide: (slideId: string) => void
  onEditSlide: (instruction: string) => Promise<void>
  onPatchElement: (
    element: EditableElement,
    patch: Omit<PatchSlideElementPayload, 'element_id'>,
  ) => Promise<void>
  onUploadAsset: (file: File) => Promise<void>
  onInsertAsset: (assetId: string) => Promise<void>
  onPlaceAsset: (assetId: string, instruction: string) => Promise<void>
  onExportPptx: () => Promise<void>
  onRollbackSlide: (versionId: string) => Promise<void>
}

export function DeckWorkspace({
  deck,
  selectedSlide,
  selectedSlideId,
  editing,
  editError,
  slideVersions,
  historyLoading,
  assets,
  assetLoading,
  exporting,
  exportUrl,
  onSelectSlide,
  onEditSlide,
  onPatchElement,
  onUploadAsset,
  onInsertAsset,
  onPlaceAsset,
  onExportPptx,
  onRollbackSlide,
}: DeckWorkspaceProps): React.JSX.Element {
  const [selectedElement, setSelectedElement] = useState<EditableElement | null>(null)

  useEffect(() => {
    setSelectedElement(null)
  }, [selectedSlide?.id])

  return (
    <section className="deck-preview">
      <div className="deck-header">
        <div>
          <span className="eyebrow compact">Generated deck</span>
          <h2>{deck.topic}</h2>
        </div>
        <p>
          {deck.slides.length} slides · {deck.status}
        </p>
        <div className="export-actions">
          <button disabled={exporting || !deck.slides.length} type="button" onClick={onExportPptx}>
            {exporting ? 'Exporting...' : 'Export editable PPTX'}
          </button>
          {exportUrl ? (
            <a href={exportUrl} rel="noreferrer">
              Download PPTX
            </a>
          ) : null}
        </div>
      </div>

      <div className="deck-grid workbench-grid">
        <SlideSidebar
          slides={deck.slides}
          selectedSlideId={selectedSlideId}
          onSelectSlide={onSelectSlide}
        />
        <PreviewStage slide={selectedSlide} onSelectElement={setSelectedElement} />
        <EditorPanel
          slide={selectedSlide}
          editing={editing}
          error={editError}
          versions={slideVersions}
          historyLoading={historyLoading}
          assets={assets}
          assetLoading={assetLoading}
          selectedElement={selectedElement}
          onEditSlide={onEditSlide}
          onPatchElement={onPatchElement}
          onUploadAsset={onUploadAsset}
          onInsertAsset={onInsertAsset}
          onPlaceAsset={onPlaceAsset}
          onRollbackSlide={onRollbackSlide}
        />
      </div>
    </section>
  )
}
