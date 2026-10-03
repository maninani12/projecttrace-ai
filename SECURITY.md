# Security policy

This is a pre-release application, not an independently audited production service. The current 0.1.x source is the supported development line. Report suspected issues privately to the repository owner's security contact. No maintainer contact has been configured; do not publish credentials or exploit details in public issues. A deployment owner must supply a real disclosure contact before release.

## Imported repository safety

Uploaded repositories are data. ProjectTrace never installs their dependencies, executes scripts, starts containers, or invokes their binaries. ZIPs are read in place; path traversal, absolute paths, Windows alternate streams/reserved names, symlinks, duplicate filenames, encrypted files, nested archives, excessive compression ratios, file counts and byte limits are rejected. Unsupported binaries and non-UTF-8 files are omitted. Ignored directories still count toward archive safety quotas.

## Secrets and privacy

Heuristic scanners redact credentials and private key blocks. Non-template `.env` files are fully redacted; source/configuration is scanned before persistence and again before external AI transmission. Values are never deliberately logged. Secret detection is not exhaustive: review sensitive projects before enabling a provider. Original ZIPs are private, may still contain raw secrets, and default to 24-hour retention. They are never served by the API. Derived evidence remains until project deletion. Storage must be encrypted and access-restricted by the deployment owner. Configure logs/backup retention separately.

Sessions use Argon2id password hashes and HTTP-only cookies, Secure in production, SameSite=Lax, with 24-hour default expiry and logout invalidation. State-changing authenticated routes require CSRF tokens; origin checks deny foreign origins. Project and nested-resource ownership is checked server-side. Development demo sessions are loopback-only and prohibited in production. Rate limits use Redis in production and a single-process memory adapter locally. If Redis is unavailable in production, requests fail closed.

The published seeded demo login is separate from temporary demo sessions. API startup seeds it only when APP_ENV is development or demo and SEED_DEMO_USER is enabled. The development fixture contains an Argon2id hash, not a plaintext password; its credentials are intentionally public in README. Startup never resets an existing account and concurrent starts are protected by email uniqueness. Production and test skip seeding before opening storage or reading the fixture. Use a separate production database; do not promote a development database containing public demo identities. No admin role or account is provided. Login, registration and demo-session creation share the strict authentication rate limit; session checks and logout use the general API limit.

## Prompt injection and AI limitations

Repository snippets are untrusted data, never system instructions. No provider tools or execution capabilities are offered. External output uses a schema, citation whitelist, bounded confidence and re-redaction. Prompt instructions are a defense layer, not a guarantee of semantic correctness. External summaries remain inferred; operational/security statements require independent verification.

## Release prerequisites

Run PostgreSQL/Redis integration CI and container builds; verify model-backed retrieval and provider failure paths with a real key; provision HTTPS, secrets, backups, retention/monitoring and a disclosure contact. Serve frontend/API under one site so cookies and CSRF are predictable. Prevent direct API bypass of the ingress body limits. Configure trusted proxy/IP handling deliberately; current limits use connection IP and may group users behind a proxy. Do not expose a development demo server publicly.

Public GitHub metadata uses the REST API first. When its public quota is exhausted, a bounded `git ls-remote --symref` lookup resolves HEAD with credential helpers, local/global Git configuration and non-HTTPS protocols disabled. It uses a fresh empty temporary directory, does no clone/checkout and executes no repository hooks or files. [Git reference lookup documentation](https://git-scm.com/docs/git-ls-remote).
