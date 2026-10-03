# UI and UX review — 3 October 2026

Reviewed the actual browser application in Microsoft Edge on Windows, with fixture-derived evidence. Source code and uploaded fixtures were never executed as target applications.

The visual language uses charcoal/off-white surfaces, restrained teal, compact technical metadata and distinct status shapes. Overview, ledger, source explorer, Q&A, consistency, viva, documentation, deployment audit and settings have different layouts suited to their tasks. Light and dark themes persist locally; authentication tokens do not use localStorage.

## Verified review results

- Captured landing plus all nine workspace screens at 1440px, light overview, and three mobile screens at 390px.
- Automated axe WCAG 2 A/AA and 2.1 AA checks: zero violations across 10 dark screens including landing, plus light overview.
- Responsive document-width checks: all nine workspace pages at 320, 390, 768 and 1024px; no page overflow in 36 checks. Wide ledger/source content scrolls inside its own region.
- No browser page errors during this review.
- Browser workflow and mobile tests passed, including exact source navigation, import, empty search, drawer Escape and focus return.
- Real source remains escaped text. Claim status uses text and shape as well as color. Source and document scroll regions are keyboard reachable.

## Issues found and corrected

The first responsive review exposed an absolute screen-reader label escaping a table's scroll boundary. Positioning the table wrapper fixed document overflow. Generated document/source scroll regions were made keyboard focusable. The mobile drawer now makes hidden navigation inert, traps focus while open, and restores focus on Escape. Snapshot switches cannot display previously selected evidence from another snapshot. Claim filters fetch the entire snapshot instead of filtering only the loaded page. A browser test also exposed a demo initialization race; the workspace now opens only after enqueueing its initial analysis job.

## Scope and reproduction

Run API, worker and Vite, then `node scripts/ui-review.cjs` from the root. This creates a local demo session, source screenshots and `docs/ui-review-results.json`. Run sequentially with other browser/benchmark tools to avoid intentionally shared connection-IP limits. Use `npm run test:e2e` from frontend for the workflow tests.

This is an automated accessibility check and a visual engineering review, not a WCAG certification or a usability study. Mobile screen-reader behavior, Safari/Firefox and long-content edge cases still need human/device evaluation. All light-theme screens were not independently audited.

Screenshots are actual browser captures under `docs/screenshots/`: landing, overview, overview-light, claim-ledger, evidence, ask-project, consistency, viva, documentation, deployment-audit, settings, mobile-overview, mobile-claim-ledger and mobile-evidence.
