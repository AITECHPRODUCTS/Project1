# UI/UX and product design

## Style system
Light canvas `#f8fafc`, white surfaces `#ffffff`, ink `#1e293b`, accent `#6366f1`, gentle neumorphic shadows, subtle glass panels, clear typography and limited meaningful animation. Avoid heavy motion and dense admin tables on mobile.

## Responsive verification
Viewport targets: 390×844, 768×1024, 1366×768, 1440×900 and 1920×1080. Test keyboard-only navigation, focus states, semantic headings/labels, screen-reader accessible errors/statuses, contrast, reduced motion, mobile menu, loading/empty/error/stale/permission states, responsive tables and long provider names.

## Interaction contracts
Every control must call the correct backend/client action and reflect the persisted result. No fake “connected” badges, seed metrics presented as live data, dead controls or silent success. Workflow run/paused/failed/complete, provider readiness, budget, consent and external-write approvals must be visible.

## Current status
Responsive Next.js dashboard has passed TypeScript typecheck and production build in GitHub Actions; full browser/Playwright, accessibility axe, core web vitals and multi-viewport visual regression are not yet recorded.
