import { clientPasswordDigest } from './password'

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
  type?: string
  timestamp?: string
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

export interface AuthUser {
  id: string
  email: string
  role: string
  status: string
  points_balance: number
  invite_code?: string | null
}

export interface AuthMeResult {
  authenticated: boolean
  user?: AuthUser | null
}

export interface SendCodeResult {
  email: string
  expires_at: string
  resend_after_seconds: number
  dev_code?: string | null
}

export interface LoginResult {
  user: AuthUser
}

export interface CreditBalance {
  user_id: string
  points_balance: number
  can_checkin: boolean
  checkin_credits: number
}

export interface CreditHistoryEntry {
  id: string
  user_id: string
  amount: number
  reason: string
  balance_after: number
  reference_type?: string | null
  reference_id?: string | null
  created_at: string
}

export interface CreditHistoryResult {
  entries: CreditHistoryEntry[]
}

export interface AdminMeResult {
  authorized: boolean
  user_id: string
  email: string
  role: string
}

export interface AdminUser {
  id: string
  email: string
  role: string
  status: string
  points_balance: number
  invite_code?: string | null
  created_at: string
  last_login_at?: string | null
  session_count: number
  generation_count: number
}

export interface AdminUserListResult {
  total: number
  users: AdminUser[]
}

export interface AdminCreditHistoryResult {
  total: number
  entries: CreditHistoryEntry[]
}

export interface AdminSessionSummary extends SessionSummary {}

export interface AdminSessionListResult {
  total: number
  sessions: AdminSessionSummary[]
}

export interface AdminGenerationRun {
  id: string
  session_id: string
  user_id?: string | null
  user_email?: string | null
  topic: string
  page_count: number
  status: string
  progress: number
  error?: string | null
  failure_category?: string | null
  failure_title?: string | null
  failure_detail?: string | null
  duration_ms: number
  charge_amount: number
  charge_settled: boolean
  anonymous: boolean
  session_status: string
  slide_count: number
  refunded_credits: number
  created_at: string
  updated_at: string
}

export interface AdminGenerationRunListResult {
  total: number
  runs: AdminGenerationRun[]
}

export interface AdminAuditLog {
  id: string
  admin_user_id: string
  action: string
  target_type: string
  target_id?: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface AdminAuditLogListResult {
  total: number
  logs: AdminAuditLog[]
}

export interface Announcement {
  id: string
  title: string
  body: string
  status: string
  published_at?: string | null
  created_by_user_id?: string
  created_at: string
  updated_at: string
}

export interface AnnouncementListResult {
  total?: number
  announcements: Announcement[]
}

export interface CreditRule {
  id?: string | null
  action: string
  label: string
  description: string
  amount: number
  enabled: boolean
  source: string
  effective_from?: string | null
  metadata: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface CreditRuleListResult {
  total: number
  rules: CreditRule[]
}

export interface ProviderConfig {
  id: string
  provider: 'llm' | 'ai_image'
  name: string
  base_url?: string | null
  model: string
  status: string
  api_key_masked: string
  has_api_key: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ProviderConfigListResult {
  total: number
  configs: ProviderConfig[]
}

export interface AdminDashboardStats {
  users: Record<string, number>
  projects: Record<string, number>
  generation_runs: {
    total?: number
    by_status?: Record<string, number>
  }
  credits: {
    total_balance?: number
    by_reason?: Array<{ reason: string; amount: number }>
  }
}

export interface InviteStats {
  invite_code: string
  inviter_credits: number
  invitee_credits: number
  total_invites: number
  rewarded_invites: number
  pending_invites: number
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response))
  }
  return response.json() as Promise<T>
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
  } catch {
    // Fall back to the HTTP status below when the response body is empty or not JSON.
  }
  return `Request failed: ${response.status} ${response.statusText}`
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
      credentials: 'same-origin',
      body: form,
    })
    if (!response.ok) {
      throw new Error(await responseErrorMessage(response))
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

  getMe(): Promise<AuthMeResult> {
    return requestJson('/api/auth/me')
  },

  sendAuthCode(email: string, purpose: 'login' | 'register' = 'login'): Promise<SendCodeResult> {
    return requestJson('/api/auth/send-code', {
      method: 'POST',
      body: JSON.stringify({ email, purpose }),
    })
  },

  register(email: string, password: string, code: string, referralCode?: string): Promise<LoginResult> {
    return requestJson('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password_digest: clientPasswordDigest(password),
        code,
        referral_code: referralCode || undefined,
      }),
    })
  },

  login(email: string, password: string, code?: string): Promise<LoginResult> {
    return requestJson('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password_digest: password ? clientPasswordDigest(password) : undefined,
        code: code || undefined,
      }),
    })
  },

  logout(): Promise<{ status: string }> {
    return requestJson('/api/auth/logout', {
      method: 'POST',
    })
  },

  getCreditBalance(): Promise<CreditBalance> {
    return requestJson('/api/credits/balance')
  },

  getCreditHistory(limit = 20): Promise<CreditHistoryResult> {
    return requestJson(`/api/credits/history?limit=${encodeURIComponent(limit)}`)
  },

  checkin(): Promise<CreditBalance> {
    return requestJson('/api/credits/checkin', {
      method: 'POST',
    })
  },

  getAdminMe(): Promise<AdminMeResult> {
    return requestJson('/api/admin/me')
  },

  listAdminUsers(params: {
    q?: string
    status?: string
    role?: string
    limit?: number
    offset?: number
  } = {}): Promise<AdminUserListResult> {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.status) search.set('status', params.status)
    if (params.role) search.set('role', params.role)
    search.set('limit', String(params.limit ?? 50))
    search.set('offset', String(params.offset ?? 0))
    return requestJson(`/api/admin/users?${search.toString()}`)
  },

  updateAdminUser(userId: string, payload: { status?: string; role?: string }): Promise<AdminUser> {
    return requestJson(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  adjustAdminUserCredits(
    userId: string,
    payload: { amount: number; reason: string },
  ): Promise<{ user: AdminUser; ledger: CreditHistoryEntry }> {
    return requestJson(`/api/admin/users/${userId}/credits`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getAdminUserCredits(userId: string, limit = 50): Promise<AdminCreditHistoryResult> {
    return requestJson(`/api/admin/users/${userId}/credits?limit=${encodeURIComponent(limit)}`)
  },

  getAdminUserSessions(userId: string, limit = 50): Promise<AdminSessionListResult> {
    return requestJson(`/api/admin/users/${userId}/sessions?limit=${encodeURIComponent(limit)}`)
  },

  getAdminGenerationRuns(params: {
    status?: string
    limit?: number
    offset?: number
  } = {}): Promise<AdminGenerationRunListResult> {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    search.set('limit', String(params.limit ?? 50))
    search.set('offset', String(params.offset ?? 0))
    return requestJson(`/api/admin/generation-runs?${search.toString()}`)
  },

  cancelAdminGenerationRun(runId: string, reason: string): Promise<AdminGenerationRun> {
    return requestJson(`/api/admin/generation-runs/${runId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  getAdminAuditLogs(limit = 50): Promise<AdminAuditLogListResult> {
    return requestJson(`/api/admin/audit-logs?limit=${encodeURIComponent(limit)}`)
  },

  getAnnouncements(limit = 5): Promise<AnnouncementListResult> {
    return requestJson(`/api/announcements?limit=${encodeURIComponent(limit)}`)
  },

  getAdminDashboard(): Promise<AdminDashboardStats> {
    return requestJson('/api/admin/dashboard')
  },

  getAdminAnnouncements(status?: string): Promise<AnnouncementListResult> {
    const search = new URLSearchParams()
    if (status && status !== 'all') search.set('status', status)
    search.set('limit', '50')
    return requestJson(`/api/admin/announcements?${search.toString()}`)
  },

  saveAdminAnnouncement(payload: {
    id?: string
    title: string
    body: string
    status: string
  }): Promise<Announcement> {
    const endpoint = payload.id
      ? `/api/admin/announcements/${payload.id}`
      : '/api/admin/announcements'
    return requestJson(endpoint, {
      method: payload.id ? 'PATCH' : 'POST',
      body: JSON.stringify({
        title: payload.title,
        body: payload.body,
        status: payload.status,
      }),
    })
  },

  getAdminCreditRules(): Promise<CreditRuleListResult> {
    return requestJson('/api/admin/credit-rules')
  },

  updateAdminCreditRule(
    action: string,
    payload: { amount: number; enabled: boolean },
  ): Promise<CreditRule> {
    return requestJson(`/api/admin/credit-rules/${encodeURIComponent(action)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  getAdminProviderConfigs(): Promise<ProviderConfigListResult> {
    return requestJson('/api/admin/provider-configs')
  },

  saveAdminProviderConfig(payload: {
    id?: string
    provider: 'llm' | 'ai_image'
    name: string
    base_url?: string
    model: string
    api_key?: string
    status: string
  }): Promise<ProviderConfig> {
    return requestJson('/api/admin/provider-configs', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getMyInvite(): Promise<InviteStats> {
    return requestJson('/api/invites/me')
  },
}
