import { useEffect, useMemo, useState } from 'react'
import {
  api,
  type Asset,
  type EditableElement,
  type ExportRunState,
  type GenerationEvent,
  type PatchSlideElementPayload,
  type SessionDetail,
  type SessionSummary,
  type Slide,
  type SlideVersion,
} from '../lib/api'

const LAST_RUN_KEY = 'tokenvizppt:last-run'
const EXPORT_POLL_INTERVAL_MS = 1200

export interface DeckGenerationState {
  runId: string | null
  sessionId: string | null
  events: GenerationEvent[]
  deck: SessionDetail | null
  selectedSlide: Slide | null
  selectedSlideId: string | null
  loading: boolean
  error: string | null
  editing: boolean
  editError: string | null
  slideVersions: SlideVersion[]
  historyLoading: boolean
  assets: Asset[]
  assetLoading: boolean
  sessions: SessionSummary[]
  sessionsLoading: boolean
  exporting: boolean
  exportUrl: string | null
  latestProgress: number
  setSelectedSlideId: (slideId: string) => void
  refreshSessions: () => Promise<void>
  openSession: (sessionId: string) => Promise<void>
  deleteSavedSession: (sessionId: string) => Promise<void>
  startGeneration: (payload: {
    topic: string
    brief: string
    pageCount: number
    styleId: string
    stylePrompt: string
    enableAiImages: boolean
    outputLanguage: 'auto' | 'zh-CN' | 'en-US'
    sourceFiles: SourceFileInput[]
  }) => Promise<void>
  editSelectedSlide: (instruction: string) => Promise<void>
  patchSelectedElement: (
    element: EditableElement,
    patch: Omit<PatchSlideElementPayload, 'element_id'>,
  ) => Promise<void>
  uploadAsset: (file: File) => Promise<void>
  insertAssetIntoSelectedSlide: (assetId: string) => Promise<void>
  placeAssetInSelectedSlide: (assetId: string, instruction: string) => Promise<void>
  exportEditablePptx: () => Promise<void>
  rollbackSelectedSlide: (versionId: string) => Promise<void>
}

export interface SourceFileInput {
  file: File
  notes: string
  required: boolean
}

export function useDeckGeneration(options: { enabled?: boolean } = {}): DeckGenerationState {
  const enabled = options.enabled ?? true
  const [runId, setRunId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [events, setEvents] = useState<GenerationEvent[]>([])
  const [deck, setDeck] = useState<SessionDetail | null>(null)
  const [selectedSlideId, setSelectedSlideId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [slideVersions, setSlideVersions] = useState<SlideVersion[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [assets, setAssets] = useState<Asset[]>([])
  const [assetLoading, setAssetLoading] = useState(false)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportUrl, setExportUrl] = useState<string | null>(null)

  const latestProgress = useMemo(() => events.at(-1)?.progress ?? 0, [events])
  const selectedSlide = useMemo<Slide | null>(() => {
    if (!deck?.slides.length) return null
    return deck.slides.find((slide) => slide.id === selectedSlideId) ?? deck.slides[0]
  }, [deck, selectedSlideId])

  const loadDeck = async (nextSessionId: string): Promise<void> => {
    const nextDeck = await api.getSession(nextSessionId)
    setDeck(nextDeck)
    setSelectedSlideId(nextDeck.slides[0]?.id ?? null)
  }

  const refreshSessions = async (): Promise<void> => {
    setSessionsLoading(true)
    try {
      const result = await api.listSessions()
      setSessions(result.sessions)
    } catch {
      setSessions([])
    } finally {
      setSessionsLoading(false)
    }
  }

  const openSession = async (nextSessionId: string): Promise<void> => {
    setLoading(false)
    setError(null)
    setRunId(null)
    setSessionId(nextSessionId)
    setEvents([])
    await loadDeck(nextSessionId)
    await loadAssets(nextSessionId)
    window.localStorage.removeItem(LAST_RUN_KEY)
  }

  const deleteSavedSession = async (targetSessionId: string): Promise<void> => {
    await api.deleteSession(targetSessionId)
    if (targetSessionId === sessionId) {
      setSessionId(null)
      setRunId(null)
      setDeck(null)
      setSelectedSlideId(null)
      setEvents([])
      setAssets([])
      setSlideVersions([])
      window.localStorage.removeItem(LAST_RUN_KEY)
    }
    await refreshSessions()
  }

  const loadSlideHistory = async (nextSessionId: string, slideId: string): Promise<void> => {
    setHistoryLoading(true)
    try {
      const history = await api.getSlideHistory(nextSessionId, slideId)
      setSlideVersions(history.versions)
    } catch {
      setSlideVersions([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const loadAssets = async (nextSessionId: string): Promise<void> => {
    setAssetLoading(true)
    try {
      const result = await api.getAssets(nextSessionId)
      setAssets(result.assets)
    } catch {
      setAssets([])
    } finally {
      setAssetLoading(false)
    }
  }

  useEffect(() => {
    if (!enabled) return
    void refreshSessions()
  }, [enabled])

  useEffect(() => {
    if (!enabled) return
    const saved = window.localStorage.getItem(LAST_RUN_KEY)
    if (!saved) return
    try {
      const parsed = JSON.parse(saved) as { sessionId?: string; runId?: string }
      if (!parsed.sessionId || !parsed.runId) return
      setSessionId(parsed.sessionId)
      setRunId(parsed.runId)
      void api
        .getGenerationState(parsed.runId)
        .then((state) => {
          setEvents(state.events || [])
          if (state.status === 'completed') {
            setLoading(false)
            void loadAssets(state.session_id)
            void refreshSessions()
            return loadDeck(state.session_id)
          }
          if (state.status === 'failed') {
            setLoading(false)
            setError(state.error || 'Generation failed.')
            return
          }
          setLoading(true)
        })
        .catch(() => {
          window.localStorage.removeItem(LAST_RUN_KEY)
        })
    } catch {
      window.localStorage.removeItem(LAST_RUN_KEY)
    }
  }, [enabled])

  useEffect(() => {
    if (!runId) return
    const source = new EventSource(`/api/generation/${runId}/events`)
    source.addEventListener('progress', (event) => {
      const data = JSON.parse((event as MessageEvent).data) as GenerationEvent
      setEvents((current) => [...current, data])
    })
    source.addEventListener('complete', () => {
      source.close()
      setLoading(false)
      if (sessionId) {
        void loadDeck(sessionId)
        void loadAssets(sessionId)
        void refreshSessions()
      }
    })
    source.addEventListener('error', (event) => {
      source.close()
      setLoading(false)
      try {
        const data = JSON.parse((event as MessageEvent).data) as { message?: string }
        setError(data.message || 'Generation failed.')
      } catch {
        setError('Generation failed.')
      }
    })
    source.onerror = () => {
      source.close()
      setLoading(false)
      setError('Generation progress stream disconnected.')
    }
    return () => source.close()
  }, [runId, sessionId])

  useEffect(() => {
    if (!sessionId || !selectedSlideId) {
      setSlideVersions([])
      return
    }
    void loadSlideHistory(sessionId, selectedSlideId)
  }, [sessionId, selectedSlideId])

  const startGeneration = async (payload: {
    topic: string
    brief: string
    pageCount: number
    styleId: string
    stylePrompt: string
    enableAiImages: boolean
    outputLanguage: 'auto' | 'zh-CN' | 'en-US'
    sourceFiles: SourceFileInput[]
  }): Promise<void> => {
    setLoading(true)
    setError(null)
    setEvents([])
    setRunId(null)
    setSessionId(null)
    setDeck(null)
    setSelectedSlideId(null)
    setSlideVersions([])
    setAssets([])
    setExportUrl(null)
    try {
      const session = await api.createSession({
        topic: payload.topic,
        brief: payload.brief,
        page_count: payload.pageCount,
        style_id: payload.styleId,
        style_prompt: payload.stylePrompt,
        enable_ai_images: payload.enableAiImages,
        output_language: payload.outputLanguage,
      })
      setSessionId(session.session_id)
      await refreshSessions()
      for (const source of payload.sourceFiles) {
        const asset = await api.uploadAsset(session.session_id, source.file)
        await api.updateAsset(session.session_id, asset.id, {
          notes: source.notes,
          required: source.required,
        })
      }
      if (payload.sourceFiles.length) {
        await loadAssets(session.session_id)
      }
      const run = await api.startGeneration(session.session_id, payload.brief)
      setRunId(run.run_id)
      window.localStorage.setItem(
        LAST_RUN_KEY,
        JSON.stringify({ sessionId: session.session_id, runId: run.run_id }),
      )
      void refreshSessions()
    } catch (err) {
      setLoading(false)
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  const editSelectedSlide = async (instruction: string): Promise<void> => {
    if (!sessionId || !selectedSlide) return
    setEditing(true)
    setEditError(null)
    try {
      await api.editSlide(sessionId, selectedSlide.id, instruction)
      const nextDeck = await api.getSession(sessionId)
      setDeck(nextDeck)
      setSelectedSlideId(selectedSlide.id)
      await loadSlideHistory(sessionId, selectedSlide.id)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Slide edit failed')
    } finally {
      setEditing(false)
    }
  }

  const uploadAsset = async (file: File): Promise<void> => {
    if (!sessionId) return
    setAssetLoading(true)
    setEditError(null)
    try {
      await api.uploadAsset(sessionId, file)
      await loadAssets(sessionId)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Asset upload failed')
    } finally {
      setAssetLoading(false)
    }
  }

  const insertAssetIntoSelectedSlide = async (assetId: string): Promise<void> => {
    if (!sessionId || !selectedSlide) return
    setEditing(true)
    setEditError(null)
    try {
      await api.insertSlideImage(sessionId, selectedSlide.id, assetId)
      const nextDeck = await api.getSession(sessionId)
      setDeck(nextDeck)
      setSelectedSlideId(selectedSlide.id)
      await loadSlideHistory(sessionId, selectedSlide.id)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Image insert failed')
    } finally {
      setEditing(false)
    }
  }

  const placeAssetInSelectedSlide = async (
    assetId: string,
    instruction: string,
  ): Promise<void> => {
    if (!sessionId || !selectedSlide) return
    setEditing(true)
    setEditError(null)
    try {
      await api.placeSlideImage(sessionId, selectedSlide.id, assetId, instruction)
      const nextDeck = await api.getSession(sessionId)
      setDeck(nextDeck)
      setSelectedSlideId(selectedSlide.id)
      await loadSlideHistory(sessionId, selectedSlide.id)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'AI image placement failed')
    } finally {
      setEditing(false)
    }
  }

  const patchSelectedElement = async (
    element: EditableElement,
    patch: Omit<PatchSlideElementPayload, 'element_id'>,
  ): Promise<void> => {
    if (!sessionId || !selectedSlide) return
    setEditing(true)
    setEditError(null)
    try {
      await api.patchSlideElement(sessionId, selectedSlide.id, {
        element_id: element.id,
        ...patch,
      })
      const nextDeck = await api.getSession(sessionId)
      setDeck(nextDeck)
      setSelectedSlideId(selectedSlide.id)
      await loadSlideHistory(sessionId, selectedSlide.id)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Element edit failed')
    } finally {
      setEditing(false)
    }
  }

  const rollbackSelectedSlide = async (versionId: string): Promise<void> => {
    if (!sessionId || !selectedSlide) return
    setEditing(true)
    setEditError(null)
    try {
      await api.rollbackSlide(sessionId, selectedSlide.id, versionId)
      const nextDeck = await api.getSession(sessionId)
      setDeck(nextDeck)
      setSelectedSlideId(selectedSlide.id)
      await loadSlideHistory(sessionId, selectedSlide.id)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Slide rollback failed')
    } finally {
      setEditing(false)
    }
  }

  const exportEditablePptx = async (): Promise<void> => {
    if (!sessionId) return
    setExporting(true)
    setEditError(null)
    setExportUrl(null)
    try {
      const result = await api.exportPptx(sessionId)
      const completed = await waitForExportRun(result.export_run_id)
      if (!completed.url) {
        throw new Error('PPTX export completed without a download URL')
      }
      setExportUrl(completed.url)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'PPTX export failed')
    } finally {
      setExporting(false)
    }
  }

  const waitForExportRun = async (exportRunId: string): Promise<ExportRunState> => {
    while (true) {
      const state = await api.getExportRun(exportRunId)
      if (state.status === 'completed') return state
      if (state.status === 'failed') {
        throw new Error(state.error || 'PPTX export failed')
      }
      await new Promise((resolve) => window.setTimeout(resolve, EXPORT_POLL_INTERVAL_MS))
    }
  }

  return {
    runId,
    sessionId,
    events,
    deck,
    selectedSlide,
    selectedSlideId,
    loading,
    error,
    editing,
    editError,
    slideVersions,
    historyLoading,
    assets,
    assetLoading,
    sessions,
    sessionsLoading,
    exporting,
    exportUrl,
    latestProgress,
    setSelectedSlideId,
    refreshSessions,
    openSession,
    deleteSavedSession,
    startGeneration,
    editSelectedSlide,
    patchSelectedElement,
    uploadAsset,
    insertAssetIntoSelectedSlide,
    placeAssetInSelectedSlide,
    exportEditablePptx,
    rollbackSelectedSlide,
  }
}
