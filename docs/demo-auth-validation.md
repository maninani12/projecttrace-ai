# Demo authentication validation — 3 October 2026

The existing authentication system was reused. No admin roles/functionality exist, so no admin account was introduced.

## Implementation

- `backend/dev/demo-user.json` contains the published demo email and an Argon2id hash generated with `app.security.auth.hasher`. No plaintext demo password appears in normal application logic.
- The API lifespan calls `seed_demo_user()` after the operator applies migrations. Only APP_ENV development/demo with SEED_DEMO_USER enabled can seed; production/test return before fixture reads or database access.
- A unique email plus transaction/rollback handles repeated and concurrent API starts. Existing identities/passwords are preserved.
- Password verification, sessions, cookies, ownership and CSRF use the existing authentication system. Timing-only dummy password checks now use a random value.
- Credential attempts retain the strict auth budget. Session checks/logout use the general API budget, preventing ordinary reloads from exhausting sign-in attempts.
- README has a Demo Login section with the requested published development credentials and instructions. Private configuration, storage and databases are excluded from the source archive.

## Verified tests

Eight dedicated backend cases passed: development startup/login/restart, demo startup/login/restart, production exclusion, test exclusion, opt-out, existing-password preservation, concurrent-start uniqueness, and session-check/login rate-budget separation.

Full backend regression: **73 passed**, one pre-existing upstream Starlette/httpx test-client warning, 21.55 seconds. Ruff lint and format passed. Alembic check reported no schema drift; no migration was required.

Playwright using real Microsoft Edge, browser forms, API and local database: **3 passed**, 13.9 seconds. The new seeded-account test verifies incorrect-password rejection, successful login with demo@projecttrace.ai / ProjectTrace@123, HTTP-only session cookie, authenticated reload, /auth/me identity, sign-out and subsequent 401. Existing evidence/upload workflow and mobile tests also passed. Frontend ESLint passed.

The first expanded browser suite exposed session checks consuming the old auth budget. That behavior was corrected and a regression test added; the final suite passed without disabling rate limits.

Live development storage after two API starts: exactly one seeded demo user; Argon2id parameters match the current hasher; zero admin users. Production seeding was tested through the actual startup hook with fixture/database access forbidden. A real production deployment remains unverified, as previously documented.

No commit, push, production account creation or deployment occurred.
