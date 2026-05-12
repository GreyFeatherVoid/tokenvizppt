import { useEffect, useState } from 'react'
import { History, ImagePlus, Loader2, MousePointer2, RotateCcw } from 'lucide-react'
import type {
  Asset,
  EditableElement,
  PatchSlideElementPayload,
  Slide,
  SlideVersion,
} from '../../lib/api'

interface EditorPanelProps {
  slide: Slide | null
  editing: boolean
  error: string | null
  versions: SlideVersion[]
  historyLoading: boolean
  assets: Asset[]
  assetLoading: boolean
  selectedElement: EditableElement | null
  onEditSlide: (instruction: string) => Promise<void>
  onPatchElement: (
    element: EditableElement,
    patch: Omit<PatchSlideElementPayload, 'element_id'>,
  ) => Promise<void>
  onUploadAsset: (file: File) => Promise<void>
  onInsertAsset: (assetId: string) => Promise<void>
  onPlaceAsset: (assetId: string, instruction: string) => Promise<void>
  onRollbackSlide: (versionId: string) => Promise<void>
}

export function EditorPanel({
  slide,
  editing,
  error,
  versions,
  historyLoading,
  assets,
  assetLoading,
  selectedElement,
  onEditSlide,
  onPatchElement,
  onUploadAsset,
  onInsertAsset,
  onPlaceAsset,
  onRollbackSlide,
}: EditorPanelProps): React.JSX.Element {
  const [instruction, setInstruction] = useState('')
  const [manualText, setManualText] = useState('')
  const [fontSize, setFontSize] = useState('')
  const [fontWeight, setFontWeight] = useState('')
  const [color, setColor] = useState('')
  const [placementAssetId, setPlacementAssetId] = useState('')
  const [placementInstruction, setPlacementInstruction] = useState('')

  useEffect(() => {
    setManualText(selectedElement?.text || '')
    setFontSize(selectedElement?.fontSize || '')
    setFontWeight(selectedElement?.fontWeight || '')
    setColor(selectedElement?.color || '')
  }, [selectedElement])

  const canSubmit = Boolean(slide && instruction.trim() && !editing)
  const pickerColor = toPickerColor(color)

  return (
    <aside className="editor-panel">
      <span className="eyebrow compact">Editor</span>
      <h3>Page edit</h3>
      <p>{slide ? `Editing ${slide.title}` : 'Select a slide to edit.'}</p>
      <form
        className="edit-form"
        onSubmit={(event) => {
          event.preventDefault()
          const value = instruction.trim()
          if (!value) return
          void onEditSlide(value).then(() => setInstruction(''))
        }}
      >
        <textarea
          disabled={!slide || editing}
          placeholder="Example: make the title warmer, reduce text, add a stronger metric card"
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
        />
        <button type="submit" disabled={!canSubmit}>
          {editing ? <Loader2 className="spin" size={18} /> : null}
          Apply edit
        </button>
      </form>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="asset-panel">
        <div className="history-title">
          <ImagePlus size={16} />
          <span>Images</span>
        </div>
        <label>
          Upload image
          <input
            accept="image/png,image/jpeg,image/webp,image/gif"
            disabled={!slide || assetLoading}
            type="file"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (!file) return
              void onUploadAsset(file).then(() => {
                event.target.value = ''
              })
            }}
          />
        </label>
        {assetLoading ? <p>Loading images...</p> : null}
        {!assetLoading && !assets.length ? <p>No uploaded images yet.</p> : null}
        {assets.length ? (
          <form
            className="asset-placement-form"
            onSubmit={(event) => {
              event.preventDefault()
              const assetId = placementAssetId || assets[0]?.id
              const value = placementInstruction.trim()
              if (!assetId || !value) return
              void onPlaceAsset(assetId, value).then(() => setPlacementInstruction(''))
            }}
          >
            <label>
              AI place image
              <select
                disabled={!slide || editing}
                value={placementAssetId}
                onChange={(event) => setPlacementAssetId(event.target.value)}
              >
                <option value="">Use first image</option>
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.file_name}
                  </option>
                ))}
              </select>
            </label>
            <textarea
              disabled={!slide || editing}
              placeholder="Example: place this as a product screenshot on the right, reduce text, keep the headline strong"
              value={placementInstruction}
              onChange={(event) => setPlacementInstruction(event.target.value)}
            />
            <button disabled={!slide || editing || !placementInstruction.trim()} type="submit">
              {editing ? <Loader2 className="spin" size={18} /> : null}
              Place with AI
            </button>
          </form>
        ) : null}
        <div className="asset-list">
          {assets.map((asset) => (
            <button
              className="asset-item"
              disabled={!slide || editing}
              key={asset.id}
              type="button"
              onClick={() => {
                void onInsertAsset(asset.id)
              }}
            >
              <img alt={asset.file_name} src={asset.url} />
              <span>
                {asset.file_name}
                {asset.source === 'ai_generated' ? (
                  <em className="asset-badge">AI generated</em>
                ) : null}
              </span>
              <small>
                {asset.source === 'ai_generated'
                  ? 'Generated during deck creation'
                  : 'Insert as fallback image'}
              </small>
            </button>
          ))}
        </div>
      </div>
      <div className="manual-panel">
        <div className="history-title">
          <MousePointer2 size={16} />
          <span>Manual text edit</span>
        </div>
        {selectedElement?.kind === 'text' ? (
          <form
            className="manual-form"
            onSubmit={(event) => {
              event.preventDefault()
              void onPatchElement(selectedElement, {
                text: manualText,
                font_size: fontSize,
                font_weight: fontWeight,
                color,
              }).then(() => {
                setManualText('')
                setFontSize('')
                setFontWeight('')
                setColor('')
              })
            }}
          >
            <label>
              Text
              <textarea
                disabled={editing}
                value={manualText}
                onChange={(event) => setManualText(event.target.value)}
              />
            </label>
            <div className="manual-grid">
              <label>
                Font size
                <input
                  disabled={editing}
                  placeholder="48px"
                  value={fontSize}
                  onChange={(event) => setFontSize(event.target.value)}
                />
              </label>
              <label>
                Weight
                <select
                  disabled={editing}
                  value={fontWeight}
                  onChange={(event) => setFontWeight(event.target.value)}
                >
                  <option value="">Keep</option>
                  <option value="400">400</option>
                  <option value="600">600</option>
                  <option value="700">700</option>
                  <option value="800">800</option>
                  <option value="900">900</option>
                </select>
              </label>
            </div>
            <label>
              Color
              <div className="color-field">
                <input
                  aria-label="Pick text color"
                  className="color-picker"
                  disabled={editing}
                  type="color"
                  value={pickerColor}
                  onChange={(event) => setColor(event.target.value)}
                />
                <span
                  aria-hidden="true"
                  className="color-swatch"
                  style={{ backgroundColor: color || 'transparent' }}
                />
                <input
                  disabled={editing}
                  placeholder="#243426 or rgb(36, 52, 38)"
                  value={color}
                  onChange={(event) => setColor(event.target.value)}
                />
              </div>
            </label>
            <button type="submit" disabled={editing}>
              {editing ? <Loader2 className="spin" size={18} /> : null}
              Save text style
            </button>
          </form>
        ) : (
          <p>Click a text element in the slide preview to edit content and style.</p>
        )}
      </div>
      <div className="manual-panel">
        <div className="history-title">
          <ImagePlus size={16} />
          <span>Selected image</span>
        </div>
        {selectedElement?.kind === 'image' ? (
          <div className="manual-form">
            {selectedElement.src ? (
              <img className="selected-image-preview" alt="" src={selectedElement.src} />
            ) : null}
            <p>
              Manual placement controls are intentionally hidden for now. Use uploaded images as a
              fallback/replacement path; AI-assisted placement will become the main workflow later.
            </p>
            <button
              className="danger-button"
              disabled={editing}
              type="button"
              onClick={() => {
                void onPatchElement(selectedElement, { delete: true })
              }}
            >
              Delete image
            </button>
          </div>
        ) : (
          <p>Click an inserted image in the slide preview to remove it if needed.</p>
        )}
      </div>
      <div className="history-panel">
        <div className="history-title">
          <History size={16} />
          <span>Edit history</span>
        </div>
        {historyLoading ? <p>Loading versions...</p> : null}
        {!historyLoading && !versions.length ? (
          <p>No edits yet. Versions are created only when slide content changes.</p>
        ) : null}
        <div className="history-list">
          {versions.map((version) => (
            <button
              className="history-item"
              disabled={editing}
              key={version.id}
              type="button"
              onClick={() => {
                void onRollbackSlide(version.id)
              }}
            >
              <span>
                {new Date(version.created_at).toLocaleString()}
                <small>{version.instruction}</small>
              </span>
              <RotateCcw aria-label="Restore this version" size={15} />
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}

function toPickerColor(value: string): string {
  const trimmed = value.trim()
  if (/^#[0-9a-f]{6}$/i.test(trimmed)) return trimmed
  if (/^#[0-9a-f]{3}$/i.test(trimmed)) {
    const [, r, g, b] = trimmed
    return `#${r}${r}${g}${g}${b}${b}`
  }
  const rgb = trimmed.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i)
  if (!rgb) return '#243426'
  return `#${[rgb[1], rgb[2], rgb[3]]
    .map((item) => Math.max(0, Math.min(255, Number(item))).toString(16).padStart(2, '0'))
    .join('')}`
}
