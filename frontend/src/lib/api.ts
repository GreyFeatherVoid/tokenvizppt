export interface CreateSessionPayload {
  topic: string
  brief: string
  page_count: number
  style_id: string
  style_prompt?: string
  enable_ai_images?: boolean
  output_language?: 'auto' | 'zh-CN' | 'en-US'
}

export interface CreateSessionResult {
  session_id: string
  status: string
}

export interface StartGenerationResult {
  run_id: string
  status: string
}

export interface Slide {
  id: string
  page_number: number
  title: string
  html: string
  spec?: Record<string, unknown> | null
}

export interface SessionDetail {
  id: string
  topic: string
  brief: string
  page_count: number
  style_id: string
  style_prompt?: string | null
  enable_ai_images: boolean
  output_language: 'auto' | 'zh-CN' | 'en-US'
  status: string
  latest_run_id?: string | null
  slides: Slide[]
}

export interface SessionSummary {
  id: string
  topic: string
  brief: string
  page_count: number
  style_id: string
  status: string
  latest_run_id?: string | null
  slide_count: number
  output_language: 'auto' | 'zh-CN' | 'en-US'
  enable_ai_images: boolean
  created_at: string
  updated_at: string
}

export interface SessionListResult {
  sessions: SessionSummary[]
}

export interface StylePreset {
  id: string
  label: string
  description: string
  visual_language: string
  prompt: string
}

export interface StylePresetList {
  default_style_id: string
  styles: StylePreset[]
}

export interface GenerationEvent {
  progress: number
  message: string
}

export interface GenerationState {
  run_id: string
  session_id: string
  status: string
  progress: number
  events: GenerationEvent[]
  error?: string | null
}

export interface EditSlideResult {
  session_id: string
  slide_id: string
  title: string
  html: string
}

export interface SlideVersion {
  id: string
  session_id: string
  slide_id: string
  page_number: number
  title: string
  instruction: string
  created_at: string
}

export interface SlideHistoryResult {
  versions: SlideVersion[]
}

export interface EditableElement {
  id: string
  kind: 'text' | 'image'
  text: string
  color: string
  fontFamily: string
  fontSize: string
  fontWeight: string
  src?: string
  left?: string
  top?: string
  width?: string
  height?: string
  opacity?: string
  borderRadius?: string
  zIndex?: string
}

export interface PatchSlideElementPayload {
  element_id: string
  text?: string
  color?: string
  font_family?: string
  font_size?: string
  font_weight?: string
  left?: string
  top?: string
  width?: string
  height?: string
  opacity?: string
  border_radius?: string
  z_index?: string
  delete?: boolean
}

export interface Asset {
  id: string
  session_id: string
  file_name: string
  mime_type: string
  file_size: number
  kind: string
  source: string
  notes: string
  required: boolean
  text: string
  text_char_count: number
  ai_image?: Record<string, unknown>
  url: string
  created_at: string
}

export interface AssetListResult {
  assets: Asset[]
}

export interface PptxExportResult {
  session_id: string
  export_run_id: string
  status: string
}

export interface ExportRunState {
  export_run_id: string
  session_id: string
  status: string
  progress: number
  file_name?: string | null
  url?: string | null
  error?: string | null
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  createSession(payload: CreateSessionPayload): Promise<CreateSessionResult> {
    return requestJson('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listSessions(): Promise<SessionListResult> {
    return requestJson('/api/sessions')
  },

  deleteSession(sessionId: string): Promise<{ status: string }> {
    return requestJson(`/api/sessions/${sessionId}`, {
      method: 'DELETE',
    })
  },

  startGeneration(sessionId: string, prompt: string): Promise<StartGenerationResult> {
    return requestJson('/api/generation/start', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        prompt,
      }),
    })
  },

  getSession(sessionId: string): Promise<SessionDetail> {
    return requestJson(`/api/sessions/${sessionId}`)
  },

  getStyles(locale = 'en-US'): Promise<StylePresetList> {
    return requestJson(`/api/styles?locale=${encodeURIComponent(locale)}`)
  },

  getGenerationState(runId: string): Promise<GenerationState> {
    return requestJson(`/api/generation/${runId}/state`)
  },

  editSlide(sessionId: string, slideId: string, instruction: string): Promise<EditSlideResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/edit`, {
      method: 'POST',
      body: JSON.stringify({ instruction }),
    })
  },

  patchSlideElement(
    sessionId: string,
    slideId: string,
    payload: PatchSlideElementPayload,
  ): Promise<EditSlideResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/elements`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  insertSlideImage(sessionId: string, slideId: string, assetId: string): Promise<EditSlideResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/images`, {
      method: 'POST',
      body: JSON.stringify({ asset_id: assetId }),
    })
  },

  placeSlideImage(
    sessionId: string,
    slideId: string,
    assetId: string,
    instruction: string,
  ): Promise<EditSlideResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/images/place`, {
      method: 'POST',
      body: JSON.stringify({ asset_id: assetId, instruction }),
    })
  },

  getAssets(sessionId: string): Promise<AssetListResult> {
    return requestJson(`/api/assets/${sessionId}`)
  },

  async uploadAsset(sessionId: string, file: File): Promise<Asset> {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`/api/assets/${sessionId}`, {
      method: 'POST',
      body: form,
    })
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.json() as Promise<Asset>
  },

  updateAsset(
    sessionId: string,
    assetId: string,
    payload: { notes?: string; required?: boolean },
  ): Promise<Asset> {
    return requestJson(`/api/assets/${sessionId}/${assetId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  exportPptx(sessionId: string): Promise<PptxExportResult> {
    return requestJson(`/api/exports/${sessionId}/pptx`, {
      method: 'POST',
    })
  },

  getExportRun(exportRunId: string): Promise<ExportRunState> {
    return requestJson(`/api/exports/runs/${exportRunId}`)
  },

  getSlideHistory(sessionId: string, slideId: string): Promise<SlideHistoryResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/history`)
  },

  rollbackSlide(
    sessionId: string,
    slideId: string,
    versionId: string,
  ): Promise<EditSlideResult> {
    return requestJson(`/api/slides/${sessionId}/${slideId}/rollback/${versionId}`, {
      method: 'POST',
    })
  },
}
