# Verification

Executed on 2026-10-21 with Python 3.12, Node 24, MongoDB 7, and Chromium.

- Backend: **29 passed** (`python -m pytest backend/tests -q`), using mongomock.
- Frontend: **11 passed** (`npm test`), covering shuffle mapping, circle order, exact dot count, bounds/non-overlap, and timer expiration/cancellation.
- Production UI: **`npm run build` passed**. Pages are lazy loaded; React and charts have separate chunks.
- Frontend formatting: **`npm run format:check` passed**.
- Python formatting/static unused-import checks: **Ruff passed** (formatter used during development; optional tooling).
- Actual MongoDB started through `docker compose up -d mongo`; actual Flask and Vite servers started.
- **36-trial HTTP smoke passed** against MongoDB. Its hand-computed expected report was accuracy 0.5, confidence 70, bias +20 pp, calibration error 40 pp, r 1.0, overall latency 2000 ms (correct 1000 / incorrect 3000), and feedback change 0 pp. Verification sessions and orphaned participants were deleted afterward.
- **Chromium browser checks passed** for setup, instructions, option keyboard shortcuts, slider confirmation, Enter submission, charts, tablet layout, visual displays and timeouts, memory/filler phases, delayed feedback, session listing, and dashboard. No JavaScript page errors were observed. Browser test sessions are explicitly labelled verification data and cleaned afterward.
- Synthetic seed is tested on a disposable mongomock database for 24 sessions, 864 trials, determinism, repeat prevention, and clearing without deleting real sessions. It was not automatically run on the application database.

Unavailable reference tests could not be run; the user authorized original replacement content, metrics, and tests. This is explicitly documented and is not a claim of equivalence to missing reference materials.

GitHub account identity was verified as `ajay2005k`. Both creation methods failed: GraphQL `createRepository` and REST `POST /user/repos` returned `Resource not accessible by integration` (REST HTTP 403). The local repository is complete; remote creation and push remain blocked on that account permission.
