import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import { api, type StylePreset } from '../../lib/api'
import type { SourceFileInput } from '../../hooks/useDeckGeneration'
import { useI18n } from '../../i18n'

interface GenerationFormProps {
  loading: boolean
  error: string | null
  onSubmit: (payload: {
    topic: string
    brief: string
    pageCount: number
    styleId: string
    stylePrompt: string
    enableAiImages: boolean
    outputLanguage: 'auto' | 'zh-CN' | 'en-US'
    sourceFiles: SourceFileInput[]
  }) => Promise<void>
}

interface DraftSourceFile {
  id: string
  file: File
  notes: string
  required: boolean
}

export function GenerationForm({
  loading,
  error,
  onSubmit,
}: GenerationFormProps): React.JSX.Element {
  const { language, t } = useI18n()
  const [topic, setTopic] = useState(() => t('defaultTopic'))
  const [brief, setBrief] = useState(() => t('defaultBrief'))
  const topicTouched = useRef(false)
  const briefTouched = useRef(false)
  const [pageCount, setPageCount] = useState(5)
  const [styleId, setStyleId] = useState('executive')
  const [styles, setStyles] = useState<StylePreset[]>([])
  const [stylePrompt, setStylePrompt] = useState('')
  const [enableAiImages, setEnableAiImages] = useState(false)
  const [sourceFiles, setSourceFiles] = useState<DraftSourceFile[]>([])
  const selectedStyle = useMemo(
    () => styles.find((style) => style.id === styleId) ?? styles[0],
    [styleId, styles],
  )

  useEffect(() => {
    if (!topicTouched.current) {
      setTopic(t('defaultTopic'))
    }
    if (!briefTouched.current) {
      setBrief(t('defaultBrief'))
    }
  }, [language, t])

  useEffect(() => {
    void api.getStyles(language).then((result) => {
      setStyles(result.styles)
      const nextStyle = result.styles.find((style) => style.id === result.default_style_id)
        ?? result.styles[0]
      setStyleId((current) => {
        if (current && result.styles.some((style) => style.id === current)) return current
        return nextStyle?.id ?? 'executive'
      })
      const activeStyle = result.styles.find((style) => style.id === styleId) ?? nextStyle
      setStylePrompt(activeStyle?.prompt ?? '')
    })
  }, [language, styleId])

  const resetStylePrompt = (): void => {
    setStylePrompt(selectedStyle?.prompt ?? '')
  }

  return (
    <form
      className="creator-card"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit({
          topic,
          brief,
          pageCount,
          styleId,
          stylePrompt,
          enableAiImages,
          outputLanguage: 'auto',
          sourceFiles: sourceFiles.map(({ file, notes, required }) => ({
            file,
            notes,
            required,
          })),
        })
      }}
    >
      <label>
        {t('topic')}
        <input
          value={topic}
          onChange={(event) => {
            topicTouched.current = true
            setTopic(event.target.value)
          }}
        />
      </label>
      <label>
        {t('brief')}
        <textarea
          value={brief}
          onChange={(event) => {
            briefTouched.current = true
            setBrief(event.target.value)
          }}
        />
      </label>
      <label>
        {t('slides')}
        <input
          min={1}
          max={40}
          type="number"
          value={pageCount}
          onChange={(event) => setPageCount(Number(event.target.value))}
        />
      </label>
      <label>
        {t('style')}
        <select
          value={styleId}
          onChange={(event) => {
            const nextStyleId = event.target.value
            setStyleId(nextStyleId)
            setStylePrompt(styles.find((style) => style.id === nextStyleId)?.prompt ?? '')
          }}
        >
          {styles.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      {selectedStyle ? (
        <div className="style-skill-panel">
          <div>
            <strong>{selectedStyle.label}</strong>
            <p>{selectedStyle.description}</p>
          </div>
          <label>
            {t('stylePrompt')}
            <textarea
              className="style-prompt-input"
              value={stylePrompt}
              onChange={(event) => setStylePrompt(event.target.value)}
            />
          </label>
          <button type="button" className="secondary-button" onClick={resetStylePrompt}>
            {t('resetStylePrompt')}
          </button>
        </div>
      ) : null}
      <label className="inline-check option-card">
        <input
          type="checkbox"
          checked={enableAiImages}
          onChange={(event) => setEnableAiImages(event.target.checked)}
        />
        <span>
          <strong>{t('allowAiVisuals')}</strong>
          <small>{t('allowAiVisualsHelp')}</small>
        </span>
      </label>
      <div className="source-file-panel">
        <div>
          <strong>{t('sourceFiles')}</strong>
          <p>{t('sourceFilesHelp')}</p>
        </div>
        <input
          multiple
          type="file"
          accept=".txt,.md,.csv,.pdf,.docx,.xlsx,.jpg,.jpeg,.png,.webp,.gif"
          onChange={(event) => {
            const files = Array.from(event.target.files || [])
            setSourceFiles((current) => [
              ...current,
              ...files.map((file) => ({
                id: createDraftFileId(file),
                file,
                notes: '',
                required: false,
              })),
            ])
            event.target.value = ''
          }}
        />
        {sourceFiles.length ? (
          <div className="source-file-list">
            {sourceFiles.map((item) => (
              <div className="source-file-item" key={item.id}>
                <div>
                  <strong>{item.file.name}</strong>
                  <small>{formatBytes(item.file.size)}</small>
                </div>
                <textarea
                  placeholder={t('sourceNotesPlaceholder')}
                  value={item.notes}
                  onChange={(event) => {
                    const notes = event.target.value
                    setSourceFiles((current) =>
                      current.map((source) =>
                        source.id === item.id ? { ...source, notes } : source,
                      ),
                    )
                  }}
                />
                {isImageFile(item.file) ? (
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={item.required}
                      onChange={(event) => {
                        const required = event.target.checked
                        setSourceFiles((current) =>
                          current.map((source) =>
                            source.id === item.id ? { ...source, required } : source,
                          ),
                        )
                      }}
                    />
                    {t('mustAppear')}
                  </label>
                ) : null}
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    setSourceFiles((current) => current.filter((source) => source.id !== item.id))
                  }}
                >
                  {t('remove')}
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <button type="submit" disabled={loading}>
        {loading ? <Loader2 className="spin" size={18} /> : <ArrowRight size={18} />}
        {t('startGeneration')}
      </button>
      {error ? <p className="error-text">{error}</p> : null}
    </form>
  )
}

function isImageFile(file: File): boolean {
  return file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|gif)$/i.test(file.name)
}

function createDraftFileId(file: File): string {
  const randomId =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  return `${file.name}-${file.size}-${file.lastModified}-${randomId}`
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
