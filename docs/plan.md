# tokenvizPPT Implementation Plan

## Goal

Build `tokenvizPPT` as a new web application that provides the same core PPT generation, preview, editing, and export workflow as `oh-my-ppt`, without reusing or modifying the original project files.

The frontend must be model-agnostic. All LLM provider, model, base URL, and API key configuration lives on the backend.

## Target Stack

- Frontend: React + Vite + TypeScript
- Backend: Python 3.12 + FastAPI
- Python environment: Conda environment named `tokenvizppt`
- Database: PostgreSQL
- ORM and migrations: SQLAlchemy 2.x + Alembic
- Queue: Redis + Celery
- Progress stream: Server-Sent Events
- Export renderer: Playwright for Python
- Development storage: local `storage/`
- Production storage: S3/R2/OSS/MinIO compatible object storage

## Architecture

```text
tokenvizPPT/
  frontend/                 # React/Vite frontend
  backend/                  # FastAPI backend
    app/
      api/                  # HTTP routes
      core/                 # settings, config, app lifecycle
      models/               # database models
      schemas/              # pydantic contracts
      services/             # business services
      workers/              # Celery tasks
      templates/            # slide HTML templates
  storage/                  # local dev storage
  docs/                     # planning and technical notes
```

## Migration Lessons From oh-my-ppt

The original codebase has several god-nodes that should not be recreated:

- `src/main/ipc/context.ts`: main-process capability aggregation.
- `src/main/ipc/engine/generate.ts`: AI planning and generation orchestration.
- `src/main/db/database.ts`: oversized database access class.
- `src/renderer/src/pages/session-detail.tsx`: editor page with too many responsibilities.
- `src/main/utils/pptx-importer.ts`: complex PPTX import logic.
- `src/main/tools/page-writer.ts`: coupled page writing and validation.
- `src/main/ipc/io/document-parse-handlers.ts`: heavy document parsing pipeline.
- `src/main/utils/html-to-pptx.ts`: complex PPTX export pipeline.

In `tokenvizPPT`, these responsibilities must be split by service boundary.

## Phases

### Phase 0: Project Skeleton

- Create `tokenvizPPT/`.
- Add React/Vite frontend.
- Add FastAPI backend.
- Add Conda Python 3.12 environment definition.
- Add basic health API.
- Add README with startup commands.

### Phase 1: Generation MVP

- Create session API.
- Start generation API.
- Stream progress with SSE.
- Generate slide HTML files on the backend.
- Show generation progress in React.
- Preview generated slides in the browser.
- Keep LLM credentials entirely on the backend.

Current Phase 1 implementation uses local file storage, backend-configured cloud LLM slide
planning, and deterministic HTML rendering. If LLM configuration is missing or the provider
returns invalid JSON, generation falls back to a deterministic local planner so the main flow
remains testable. PostgreSQL and Celery are still Phase 2 work.

### Phase 1.5: Generation Quality

- Generate a deck outline with richer per-page intent.
- Generate a design contract with theme, palette, typography, layout rules, and visual language.
- Generate complete HTML for each slide instead of rendering every page through one fixed template.
- Add first-pass style presets on the frontend and backend.
- Validate generated HTML before saving.
- Retry or fall back per page when generation fails.
- Keep the current file-backed storage until Phase 2.

Phase 1.5 is an expansion of Phase 1, not a change to the overall roadmap. It improves output
quality before investing in database persistence, queueing, editing, upload, and export.

### Phase 2: Persistence And Task Stability

- Add PostgreSQL schema.
- Add SQLAlchemy models and Alembic migrations.
- Add Redis + Celery for long-running generation tasks.
- Persist sessions, slides, messages, generation runs, and events.
- Support failed task state, retry, cancel, and resumed progress view.

Phase 2 should be introduced incrementally. The first step is database infrastructure only:
SQLAlchemy models, Alembic migration, and local Postgres/Redis setup. The file-backed generation
flow remains active until the database-backed repository is verified.

Current Phase 2 progress:

- PostgreSQL schema and Alembic migration are in place.
- Redis is available through Docker for Celery.
- Generation metadata is mirrored to PostgreSQL.
- Session reads are DB-first for metadata and file-backed for slide HTML.
- Generation execution runs in Celery instead of inside the SSE request.
- Run state and frontend refresh recovery are being added before editor work begins.

### Phase 3: React Editor

- Add session detail page.
- Add slide sidebar.
- Add preview stage.
- Add chat panel for page-level and deck-level edits.
- Add text editing.
- Add drag-based layout editing.
- Add asset upload.
- Keep editor state split into focused components/stores.

Current Phase 3 progress:

- Frontend generation state has been moved into `useDeckGeneration`.
- `App.tsx` is now only a thin page entry.
- Generation form, progress panel, slide sidebar, preview stage, and editor panel are split into
  dedicated components.
- The editor panel now supports a first page-level edit loop: user instruction -> backend LLM edit
  -> HTML validation -> slide file overwrite -> DB metadata update -> preview refresh.
- Page-level edits now create slide version snapshots before overwriting HTML.
- The editor panel can list edit history and roll back a slide to a previous version.
- Generated, AI-edited, and rolled-back slide HTML now passes through a lightweight editable-element
  protocol using `data-edit-id`.
- The preview iframe supports selecting text elements, and the editor panel can manually update text,
  font size, font weight, and color. Manual edits also create version snapshots.
- The editor panel now supports user-uploaded image assets and can insert an uploaded image into the
  current slide. Image insertion also creates a version snapshot.
- Manual image insertion is retained as a fallback/replacement path, not the primary image workflow.
- Uploaded assets can now be placed by the backend LLM with a user instruction, allowing the model to
  re-layout the current slide around the selected image.
- Image replacement, AI image generation, document-extracted images, search images, drag-based layout
  edits, and export controls are still upcoming.

### Phase 4: Export

- Add editable PPTX export as the primary export path.
- Extract visible slide text, uploaded images, and simple shape blocks from rendered HTML.
- Write real PowerPoint text boxes, image objects, and shapes instead of screenshot-only slides.
- Keep PDF and PNG optional/non-primary unless needed later.
- Queue export jobs to protect server resources.
- Add download links and file expiration.

Current Phase 4 progress:

- Editable PPTX MVP is implemented with Playwright DOM extraction and `python-pptx` writing.
- Frontend has an `Export editable PPTX` action and download link.
- Current MVP exports text boxes, uploaded images, background color, and simple filled/bordered
  blocks. Complex gradients, SVG, charts, formulas, exact shadows, and full CSS fidelity are still
  follow-up work.
- Editable PPTX export now runs as a Celery task. The API creates an export run, the frontend polls
  status, and the download link appears after the worker completes the file.

### Phase 4.5: Shared Source Rendering

- Move new deck generation toward a structured `SlideSpec` instead of treating HTML as the source of
  truth.
- Render HTML preview and editable PPTX from the same `SlideSpec` coordinates, colors, typography,
  and shape definitions.
- Keep old HTML-to-PPTX exporters as fallback for legacy decks and HTML-edited slides.
- Next: migrate manual edits, image placement, and AI slide edits to update `SlideSpec` directly
  instead of rewriting HTML.

Current Phase 4.5 progress:

- New generation writes `slide-*.spec.json` beside each generated HTML slide.
- New generated HTML preview is rendered from `SlideSpec`.
- New generation now calls the backend LLM once per slide to produce structured `SlideSpec` JSON.
- After the deck outline is planned, per-slide SlideSpec generation now runs concurrently with a
  backend-configured limit to reduce total generation latency without losing deck-level planning.
- SlideSpec generation is strict quality mode: validation failures retry up to 3 times; after 3
  failures the generation task fails instead of falling back to a low-quality program template.
- The program validates SlideSpec coordinates, element counts, hex colors, text lengths, bounds, and
  basic text overlap before rendering.
- PPTX export now prefers direct `SlideSpec` rendering through `python-pptx`, then falls back to
  `dom-to-pptx`, then the previous DOM extraction exporter.
- Uploaded image insertion now writes image elements into `SlideSpec`, regenerates preview HTML from
  the spec, and exports those images through the direct `SlideSpec` PPTX path.
- Manual text edits and image deletion on spec-backed slides now update `SlideSpec` first, keeping
  preview and PPTX export aligned.
- Page-level AI edits on spec-backed slides now update `SlideSpec` directly, retry validation up to
  3 times, and regenerate preview HTML from the accepted spec.
- AI-assisted uploaded image placement on spec-backed slides now updates `SlideSpec` directly,
  including the uploaded asset URL as an image element for direct PPTX export.
- Style presets now use an oh-my-ppt-like Style Skill model: each built-in style has a visible
  prompt, users can temporarily edit that prompt before generation, and reset restores the built-in
  prompt without permanently modifying the style.
- Current limitation: legacy HTML-only slides still use the older HTML edit/export path until they
  are regenerated or migrated to spec.

### Phase 5: Document And PPTX Import

- Add txt/md/csv/docx parsing.
- Generate briefing content from uploaded documents.
- Add PPTX import as a separate, later pipeline.
- Extract style hints from imported PPTX when feasible.

Current Phase 5 progress:

- Generation form now supports uploading source files before starting generation.
- Supported source inputs now include txt, md, csv, pdf, docx, xlsx, and common image formats.
- Uploaded documents are parsed on the backend and injected into the outline/SlideSpec generation
  prompts as grounding context.
- Uploaded images can include user notes and a "must appear in the PPT" constraint.
- Uploaded images are analyzed with the backend vision model before outline planning. The extracted
  caption, OCR text, key points, recommended usage, and placement guidance are injected into the
  outline and SlideSpec prompts.
- Required image constraints are validated after generation by checking SlideSpec image URLs. If a
  required image is missing, the backend asks the model to choose the best existing slide and return
  a re-laid-out SlideSpec for that slide, rather than hard-inserting the image.
- Search images are intentionally deferred because source quality, copyright, and attribution risks
  are higher than uploaded or AI-generated assets.
- AI-generated images are planned as an opt-in backend capability. They should be used sparingly as
  intentional visual anchors, not as filler.
- PPTX import is still upcoming.

### Phase 5.4: AI Image Generation

Add AI-generated images to the same asset pipeline as uploaded images, but only after the slide
generation step determines that a specific page genuinely needs one.

Backend configuration:

- `TOKENVIZPPT_AI_IMAGE_ENABLED`
- `TOKENVIZPPT_AI_IMAGE_PROVIDER`
- `TOKENVIZPPT_AI_IMAGE_MODEL`
- `TOKENVIZPPT_AI_IMAGE_API_KEY`
- `TOKENVIZPPT_AI_IMAGE_BASE_URL`
- `TOKENVIZPPT_AI_IMAGE_TIMEOUT_SECONDS`
- `TOKENVIZPPT_AI_IMAGE_DEFAULT_SIZE`
- `TOKENVIZPPT_AI_IMAGE_MAX_PER_DECK`

Usage rules:

- Default is off. The frontend stays model-agnostic.
- Generate at most 1-2 images per deck by default.
- Let the slide-generation model decide whether the current page needs an AI image before calling
  the image API.
- The decision must name the target slide, visual purpose, intended placement, and why text/shapes
  alone are insufficient.
- Use generated images only when they create a strong visual anchor for cover, concept,
  scenario, process, mood, metaphor, or section-divider slides.
- Do not generate images for data that should be represented as text, charts, tables, screenshots,
  uploaded evidence, or user-required assets.
- Do not generate portraits, real people, logos, copyrighted characters, medical/legal/financial
  evidence, or images that imply factual proof.
- Prefer wide 16:9-compatible sizes, usually `1536x1024`, then crop/fit into SlideSpec.

- Every generated image should be saved as an asset with metadata describing prompt, model, size,
  target slide, intended slide role, placement guidance, and generation reason.
- The generated image should go through the same vision analysis path before final SlideSpec
  rendering so the slide generator can reason about the actual pixels, not only the prompt.
- If the model cannot justify a generated image for the current slide, skip generation. Quality is
  more important than filling every deck with visuals.

Execution steps:

1. Add an image generation client using the OpenAI-compatible `/v1/images/generations` endpoint.
2. Add a per-slide visual-need decision before each SlideSpec call. The decision returns either
   `skip` or a concrete image brief for that page.
3. Enforce usage rules and `AI_IMAGE_MAX_PER_DECK` before calling the image API.
4. Generate only approved page-specific images.
5. Save generated images into the asset store as `kind=image` with `source=ai_generated`.
6. Run vision analysis on generated assets.
7. Generate that page's SlideSpec with the generated image analysis and exact asset URL available
   in context, so the image is created for the slide rather than matched after the fact.

Current Phase 5.4 progress:

- AI image API configuration is backend-only and disabled by default.
- The image generation client is implemented as `app/services/ai_image_generator.py`.
- Generated images are saved into the normal asset store as `source=ai_generated` images with
  prompt/model/size/target-page metadata.
- Before SlideSpec generation, each slide is conservatively evaluated by the backend LLM for whether
  it genuinely needs an AI-generated visual.
- Only approved slide-specific image briefs are generated, capped by `AI_IMAGE_MAX_PER_DECK`.
- Generated images are vision-analyzed before the target slide's SlideSpec is generated.
- The target slide receives the generated image asset, vision analysis, and placement guidance in
  its prompt context.

### Phase 6: Accounts, Guests, And Credits

Move tokenvizPPT from a local/single-user prototype toward a public multi-user web app.

Product rules:

- Users log in with email verification codes.
- Only configured email domains can register.
- Anonymous visitors can try the product once per day per IP.
- Anonymous usage includes one deck generation and one single-slide AI edit.
- Registered users receive 200 credits on signup.
- Daily check-in grants 30 credits once per calendar day.
- Referrals can grant credits after the invited user completes their first deck generation.
- One text/planning/edit AI action costs 1 credit.
- One AI image generation costs 5 credits.
- Admin users can manage accounts, credits, announcements, credit rules, and eventually provider
  configuration.

Architecture rules:

- PostgreSQL remains the primary application database.
- Backend APIs must enforce authentication, resource ownership, anonymous limits, and credit
  charging. The frontend only displays state and errors.
- Sessions, assets, generation runs, export runs, slide versions, and messages must be owned by
  either a user or an anonymous guest identity.
- Credits must be tracked with an append-only ledger, not only a mutable balance field.
- Failed AI work should not consume credits permanently; pre-charged work must be refunded when the
  backend reports failure.
- Anonymous limits should use hashed IP plus date. Raw IP addresses should not be stored unless
  explicitly needed for abuse review.
- Production deployment should use Nginx with only HTTP/HTTPS exposed publicly. FastAPI, PostgreSQL,
  and Redis remain private.

Implementation path:

1. Add auth schema: users, email verification codes, auth sessions/tokens.
2. Add auth APIs: send code, login, logout, current user.
3. Add ownership columns to user content tables and enforce ownership checks in all session, asset,
   slide, generation, and export APIs.
4. Add anonymous daily usage tracking by hashed IP and local date.
5. Add credit schema: credit ledger, daily check-ins, cached user balance.
6. Add credit service with charge/refund/grant operations and idempotency keys.
7. Add referral schema and grant invitation rewards after first successful generation.
8. Charge deck generation, page edits, and AI image generation through the credit service.
9. Add admin role, audit logs, manual credit adjustment, account disable/enable, credit rules, and
   announcements.
10. Add homepage/login UI that supports anonymous trial, signup/login, balance display, invite links,
   check-in.
11. Add admin UI for user management, usage review, credit rules, announcements, and audit logs.
12. Add production deployment notes for Nginx, SMTP, secure cookies, and allowed email domains.

Current Phase 6 design status:

- PostgreSQL is retained instead of switching to MySQL.
- First design step is email-code authentication with an allowlist of email domains.
- SMTP can start with a 163 mailbox for testing, but a production mail provider is preferred before
  broader launch because consumer mailboxes can hit throttling, spam-folder, and authorization-code
  issues.
- Detailed first-step design is recorded in `docs/auth-credit-design.md`.
- Admin 2FA is deferred.
- Captcha or advanced verification-code anti-abuse is deferred until usage patterns are clearer.
- Database-editable provider/API-key configuration is deferred until encrypted secret storage is in
  place.

### Phase 7: Multi-User Production Hardening

- Add user/session isolation.
- Add rate limits and task concurrency limits.
- Add file size limits.
- Add storage cleanup jobs.
- Add structured logs and task error reporting.
- Add admin-facing task inspection if needed.

## Immediate Execution Order

1. Finish skeleton.
2. Define API contracts.
3. Build the minimal create-session and generation-progress flow.
4. Implement mock generation first.
5. Replace mock generation with LLM-backed generation.
6. Add preview.
7. Add editing and export after the core loop is stable.
