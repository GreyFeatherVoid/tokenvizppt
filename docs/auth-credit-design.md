# Auth And Credit Design

## Scope

This document defines the first multi-user step for tokenvizPPT:

- Email verification-code login.
- Registration limited to configured email domains.
- Anonymous daily trial limits by IP.
- Registered-user credit balance, ledger, and daily check-in.
- Backend ownership and quota enforcement for generation, slide edits, image generation, assets, and
  exports.

PostgreSQL remains the application database. Redis remains the queue/broker backend.

## Product Rules

- Anonymous visitors can use one free deck generation per day per IP.
- Anonymous visitors can use one free single-slide AI edit per day per IP.
- Registered users get 200 signup credits.
- Registered users can check in once per day for 30 credits.
- Inviting users can earn referral credits after the invited user completes their first deck
  generation.
- One text/planning/edit AI action costs 1 credit.
- One AI image generation costs 5 credits.
- Failed work should refund pre-charged credits.
- Admin users can manage users, credits, announcements, model/provider configuration, and credit
  rules.
- Admin two-factor authentication is deferred for now.
- Advanced verification-code anti-abuse, such as captcha, is deferred until usage patterns are
  clearer.

Recommended billing semantics:

- Deck generation should charge by user-visible work, not raw provider calls.
- Initial deck generation: charge `page_count` credits.
- Page-level AI edit: charge 1 credit.
- AI-assisted image placement without generating a new image: charge 1 credit.
- AI image generation: charge 5 credits per generated image.
- Referral bonus: invitee completes first deck generation before inviter receives credits.
- Uploaded file parsing and deterministic export remain free initially.

## Configuration

Add backend settings:

```bash
TOKENVIZPPT_AUTH_ENABLED=true
TOKENVIZPPT_ALLOWED_EMAIL_DOMAINS=["example.com","school.edu"]
TOKENVIZPPT_AUTH_CODE_TTL_SECONDS=600
TOKENVIZPPT_AUTH_CODE_RESEND_SECONDS=60
TOKENVIZPPT_AUTH_SESSION_TTL_DAYS=30
TOKENVIZPPT_AUTH_COOKIE_NAME=tokenvizppt_session
TOKENVIZPPT_AUTH_COOKIE_SECURE=false
TOKENVIZPPT_SIGNUP_CREDITS=200
TOKENVIZPPT_DAILY_CHECKIN_CREDITS=30
TOKENVIZPPT_REFERRAL_INVITER_CREDITS=50
TOKENVIZPPT_REFERRAL_INVITEE_CREDITS=20
TOKENVIZPPT_ANON_DAILY_GENERATION_LIMIT=1
TOKENVIZPPT_ANON_DAILY_EDIT_LIMIT=1
TOKENVIZPPT_IP_HASH_SECRET=replace-with-random-secret
TOKENVIZPPT_ADMIN_EMAILS=["admin@example.com"]

TOKENVIZPPT_SMTP_HOST=smtp.163.com
TOKENVIZPPT_SMTP_PORT=465
TOKENVIZPPT_SMTP_USERNAME=your-address@163.com
TOKENVIZPPT_SMTP_PASSWORD=your-smtp-authorization-code
TOKENVIZPPT_SMTP_FROM=your-address@163.com
```

For production, set secure cookies and use HTTPS:

```bash
TOKENVIZPPT_AUTH_COOKIE_SECURE=true
```

## Database Tables

### users

- `id`: string primary key.
- `email`: unique, lowercase.
- `email_domain`: indexed.
- `status`: active, disabled.
- `role`: user, admin.
- `points_balance`: integer cached balance.
- `signup_credits_granted`: boolean.
- `invite_code`: unique nullable.
- `referred_by_user_id`: nullable foreign key to users.
- `last_login_at`: timestamptz nullable.
- `metadata_json`: text.
- timestamps.

### email_verification_codes

- `id`: string primary key.
- `email`: indexed lowercase.
- `code_hash`: string.
- `purpose`: login.
- `request_ip_hash`: string nullable.
- `expires_at`: timestamptz.
- `consumed_at`: timestamptz nullable.
- `attempt_count`: integer.
- timestamps.

Only store hashed codes. Never store raw verification codes.

### auth_sessions

- `id`: string primary key.
- `user_id`: foreign key to users.
- `token_hash`: unique.
- `expires_at`: timestamptz.
- `revoked_at`: timestamptz nullable.
- `request_ip_hash`: string nullable.
- `user_agent`: text nullable.
- timestamps.

The cookie stores the raw session token. The database stores only `token_hash`.

### anonymous_usage

- `id`: string primary key.
- `ip_hash`: indexed.
- `usage_date`: date.
- `generation_count`: integer.
- `edit_count`: integer.
- timestamps.

Unique constraint: `(ip_hash, usage_date)`.

### credit_ledger

- `id`: string primary key.
- `user_id`: foreign key to users.
- `amount`: integer, positive for grant/refund, negative for charge.
- `reason`: signup_bonus, daily_checkin, deck_generation, slide_edit, ai_image_generation, refund.
- `reference_type`: generation_run, slide_edit, asset, checkin, manual.
- `reference_id`: string nullable.
- `idempotency_key`: unique nullable.
- `balance_after`: integer.
- `metadata_json`: text.
- timestamps.

All balance changes go through this table. `users.points_balance` is a cached value updated in the
same transaction.

### daily_checkins

- `id`: string primary key.
- `user_id`: foreign key to users.
- `checkin_date`: date.
- `points_awarded`: integer.
- timestamps.

Unique constraint: `(user_id, checkin_date)`.

### invite_codes

- `id`: string primary key.
- `user_id`: foreign key to users.
- `code`: unique.
- `status`: active, disabled.
- `metadata_json`: text.
- timestamps.

Each registered user can have one active invitation code in the first implementation.

### referrals

- `id`: string primary key.
- `inviter_user_id`: foreign key to users.
- `invitee_user_id`: unique foreign key to users.
- `invite_code`: string.
- `status`: pending, rewarded, rejected.
- `rewarded_at`: timestamptz nullable.
- `metadata_json`: text.
- timestamps.

Referral rewards should be granted after the invitee completes their first successful deck
generation. This reduces abuse from throwaway registrations.

### credit_rules

- `id`: string primary key.
- `action`: deck_generation_page, slide_edit, ai_image_generation, daily_checkin, signup_bonus,
  referral_inviter, referral_invitee.
- `amount`: integer.
- `enabled`: boolean.
- `effective_from`: timestamptz nullable.
- `metadata_json`: text.
- timestamps.

Changing rules must not rewrite historical ledger rows. The ledger records the actual amount charged
or granted at the time.

### announcements

- `id`: string primary key.
- `title`: string.
- `body`: text.
- `status`: draft, published, archived.
- `published_at`: timestamptz nullable.
- `created_by_user_id`: foreign key to users.
- timestamps.

### admin_audit_logs

- `id`: string primary key.
- `admin_user_id`: foreign key to users.
- `action`: string.
- `target_type`: user, credit_rule, provider_config, announcement, session, manual_credit.
- `target_id`: string nullable.
- `payload_json`: text.
- timestamps.

All admin mutations must write an audit log entry.

### provider_configs

- `id`: string primary key.
- `provider`: openai-compatible, image.
- `name`: string.
- `base_url`: text nullable.
- `model`: string.
- `encrypted_api_key`: text nullable.
- `status`: active, disabled.
- `metadata_json`: text.
- timestamps.

Provider configuration in the database is optional for the first pass. It can start as `.env` only.
If API keys become editable in admin, store only encrypted secrets and show masked values in the UI.

## Ownership Changes

Add nullable ownership columns:

- `sessions.user_id`
- `generation_runs.user_id`
- `assets.user_id`
- `messages.user_id`
- `slides` can inherit ownership from session.
- slide versions should inherit ownership from session or include `user_id`.

For anonymous sessions, use metadata:

```json
{
  "guest": {
    "ip_hash": "...",
    "created_date": "2026-05-15"
  }
}
```

Later, if anonymous history needs to survive across IPs, add a signed guest cookie.

## API Design

### Auth

```text
POST /api/auth/send-code
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

`send-code`:

- Lowercase and validate email.
- Check domain allowlist.
- Rate-limit resend by email and IP.
- Store hashed code with TTL.
- Send code via SMTP.

`login`:

- Verify email and code.
- Create user if absent and domain is allowed.
- Grant signup credits exactly once.
- Create auth session.
- Set HTTP-only cookie.

`me`:

- Returns user profile, balance, check-in status, and allowed domains.
- Returns anonymous quota state when not logged in.

### Credits

```text
GET  /api/credits/balance
GET  /api/credits/history
POST /api/credits/checkin
```

`checkin`:

- Requires login.
- Unique per user per local date.
- Grants configured daily credits through ledger.

### Invites

```text
GET  /api/invites/me
POST /api/invites/accept
```

First pass:

- `me` returns the user's invite code and referral stats.
- `accept` can be driven by a referral code captured before login and applied during signup.
- Referral reward is granted after the invitee's first successful deck generation.

### Admin

```text
GET  /api/admin/users
GET  /api/admin/users/{user_id}
PATCH /api/admin/users/{user_id}
POST /api/admin/users/{user_id}/credits
GET  /api/admin/users/{user_id}/credits
GET  /api/admin/users/{user_id}/sessions
GET  /api/admin/rules/credits
PATCH /api/admin/rules/credits/{rule_id}
GET  /api/admin/announcements
POST /api/admin/announcements
PATCH /api/admin/announcements/{announcement_id}
GET  /api/admin/audit-logs
```

Admin access requires `role=admin` or an email listed in `TOKENVIZPPT_ADMIN_EMAILS`.

Provider/API-key admin endpoints should be added only after encrypted secret storage is implemented.

### Existing APIs

Update these endpoints to read current identity:

- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `POST /api/generation/start`
- `GET /api/generation/{run_id}/state`
- `GET /api/generation/{run_id}/events`
- `/api/slides/*`
- `/api/assets/*`
- `/api/exports/*`

Rules:

- Logged-in users can only access resources with their `user_id`.
- Anonymous users can only access sessions created under the same anonymous identity.
- Mutating AI endpoints must check quota or credits before work is queued.

## Backend Services

### AuthService

Responsibilities:

- Normalize and validate email.
- Generate and verify codes.
- Hash codes and session tokens.
- Create/revoke auth sessions.
- Resolve current user from cookie.

### Identity Dependency

FastAPI dependency:

```python
CurrentIdentity(
    user_id: str | None,
    email: str | None,
    ip_hash: str,
    is_authenticated: bool,
)
```

All quota and ownership checks consume this dependency.

### CreditService

Responsibilities:

- Grant credits.
- Charge credits.
- Refund credits.
- Enforce idempotency.
- Update `users.points_balance` and insert `credit_ledger` rows in one transaction.
- Load active credit rules and apply default fallback values from settings.

### AnonymousUsageService

Responsibilities:

- Get current anonymous usage by IP hash and date.
- Reserve/consume anonymous generation quota.
- Reserve/consume anonymous edit quota.
- Roll back anonymous usage on failed work when appropriate.

### ReferralService

Responsibilities:

- Create and resolve invite codes.
- Attach inviter to new users when a valid referral code is present.
- Grant referral credits after first successful deck generation.
- Enforce referral idempotency and anti-self-invite checks.

### AdminService

Responsibilities:

- Enforce admin roles.
- Mutate user status and manual credits.
- Manage credit rules and announcements.
- Write audit logs for all admin mutations.
- Keep provider/API-key changes behind super-admin checks and encrypted storage.

## Charging Points

Recommended first pass:

- `POST /api/generation/start`
  - Logged-in: pre-charge `page_count` credits.
  - Anonymous: consume 1 daily generation.
  - Refund on generation task failure.

- `POST /api/slides/{session_id}/{slide_id}/edit`
  - Logged-in: charge 1 credit.
  - Anonymous: consume 1 daily edit.
  - Refund on edit failure.

- `POST /api/slides/{session_id}/{slide_id}/images/place`
  - Logged-in: charge 1 credit.
  - Anonymous: disallow initially or consume edit quota.

- AI image generation during deck generation
  - Logged-in: charge 5 credits per generated image.
  - Anonymous: disabled initially.

## Frontend Changes

Add:

- Home-first layout.
- Login modal with email and verification code steps.
- Balance display.
- Daily check-in button.
- Invite link display and referral reward copy.
- Anonymous free-trial state.
- Register/login callouts after anonymous usage.
- Admin entry point for admin/super-admin users.

Admin UI first pass:

- User search and detail view.
- Credit ledger and manual credit grant/deduct form.
- Account enable/disable controls.
- User-generated sessions/projects list.
- Credit rule editor.
- Announcement editor.
- Audit log view.

Keep:

- Backend-only model configuration.
- Existing generation form and workspace, but make logged-in/anonymous quota visible.

## Implementation Order

1. Add settings for auth, SMTP, credits, anonymous limits, and IP hashing.
2. Add SQLAlchemy models and Alembic migration for auth and credit tables.
3. Add AuthService and auth APIs.
4. Add current-identity dependency.
5. Add user ownership to sessions and update create/list/get/delete session APIs.
6. Add anonymous usage table and enforce anonymous generation/edit limits.
7. Add CreditService, signup credit grant, balance/history/check-in APIs.
8. Charge generation and slide edit endpoints.
9. Add referral tables/service and grant inviter rewards after invitee's first successful deck.
10. Add admin role, admin audit logs, manual credit adjustments, user disable/enable, and credit rule
    management.
11. Add announcement publishing.
12. Add frontend login/balance/check-in/invite UI.
13. Add admin UI first pass.
14. Add Nginx/production notes and secure cookie defaults.

Deferred:

- Admin 2FA.
- Captcha or advanced verification-code anti-abuse.
- Database-editable provider/API-key configuration until encrypted secret storage is implemented.
