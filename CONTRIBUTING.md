# Contributing

Follow README native setup. Use a feature branch and focused pull requests. No automatic commits, pushes, deployments or repository rewrites are part of development tooling.

Run backend Ruff/pytest, frontend ESLint/Vitest/TypeScript build and the Playwright workflow. CI adds PostgreSQL + Redis + pgvector integration. New claim rules need positive and false-positive fixtures; changes to archive validation, authorization or provider context require security regression tests. Fixtures must contain synthetic data only. Do not execute imported project samples.

Use Ruff for Python and Prettier for TypeScript/CSS. Keep domain code in its feature/module. PR descriptions should identify the user-visible behavior, evidence/ownership implications, tests actually run and remaining limitations. Schema changes require an explicit Alembic migration. Never use create_all as the production migration path. Never add real `.env` files or raw credentials.
