# Metacognitive Calibration Laboratory

A local teaching and exploratory research tool for cognitive psychology. Participants answer cognitive questions and rate confidence. Instructors configure conditions, inspect calibration reports, compare groups, and export trial data. React 18 + Vite + Tailwind + React Router + Recharts; Python 3.11+ + Flask + PyMongo; MongoDB 7. No authentication, external APIs, cloud services, or browser data storage are used by the application.

**Reference substitution:** The referenced files and mockups were not supplied. The user authorized an original implementation. All 36 questions, metric formulas, tests, and the light blue/white interface were authored for this project. They are not copies of, or validated against, unavailable references. `reference/README.md` records this provenance.

## Prerequisites

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+ and npm
- Docker with Compose (or an existing MongoDB instance)

## Setup and run

Run these commands from the repository root:

```bash
cp .env.example .env
docker compose up -d mongo
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

In one terminal, from the root:

```bash
source .venv/bin/activate
python -m backend.app
```

In another:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. Flask runs at http://127.0.0.1:5000. Vite proxies `/api` to Flask; CORS allows `http://localhost:5173`. Both web servers bind to loopback. MongoDB binds to loopback through Compose and persists in a named volume. Stop it with `docker compose down` (data is preserved). `.env` is loaded from the repository root regardless of the backend working directory. Default: `MONGO_URI=mongodb://localhost:27017/mclab`. Set `FRONTEND_ORIGIN` if needed. Never commit `.env`.

The item bank is validated before database connection: exactly 36 distinct IDs, two items per category/difficulty cell, four distinct options, an in-range integer answer, and valid memory/perceptual stimuli. Invalid banks refuse startup. MongoDB must be available at startup for index creation; a connection error is not silently replaced with an in-memory database.

## Tests and production build

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

Backend tests inject `mongomock`; they do not require MongoDB and never connect to a real database. They test analytical metric examples, bank validation, balanced selection, API validation, sequencing, duplicate protection, completion, timeouts, exports, filters, aggregation, deletion, and deterministic synthetic seeding. Frontend tests cover option mapping, circle ordering, dot count/separation/bounds, and timer expiration/cancellation. Build output is `frontend/dist/`.

With Flask and Vite running, run the full HTTP session check:

```bash
source .venv/bin/activate
python backend/tests/smoke_session.py
```

This smoke check creates a real session and submits intentionally scripted answers under a clearly labelled `SCRIPTED-VERIFICATION` group. It validates a hand-computed report and deletes its session and orphaned verification participant in a `finally` block. It is an explicit verification tool, never part of startup. Do not treat its generated responses as participant evidence. Use a separate test MongoDB database if verifying against a research deployment.

## Session conditions

| Setting | Allowed values | Behavior |
| --- | --- | --- |
| difficulty | easy, hard, mixed | Easy/hard select 12 trials across all categories; mixed selects all levels. |
| feedback | immediate, delayed, none | Correctness and correct text appear for 2 seconds; delayed first waits 5 seconds. None advances directly. |
| time_limit | none, 20 | 20 seconds from options appearing through confidence submission. Timeout records null answer/confidence/latency and false correctness. |
| categories | all, logic, pattern, memory, probability, numerical, perceptual | Single category selects 6 mixed trials or 2 restricted-difficulty trials. |
| interface | slider, buttons | Slider 0–100 step 1 must be touched; buttons 0, 10, …, 100. |
| n_trials | 18 or 36 for mixed/all | 18 samples one item per category/difficulty cell. Restricted conditions determine their own trial count. |

Optional `age_range` is `18-20`, `21-23`, or `24+`; optional `academic_year` is 1–4. Group is at most 80 characters. No names are collected; group labels should identify experimental groups, never people. Participant IDs are generated server-side on Start as `P-` plus five uppercase letters/digits with a unique database index and collision retry. API callers may reuse an existing valid ID; existing demographics are retained.

The first screen explains the task. Each trial is randomized within the session. Option order is freshly shuffled on display and mapped to its original index for storage. Circle position options remain in top-left/top-right/bottom-left/bottom-right order. Memory study duration is bank-defined, followed by a 10-second unscored distraction; its typed input is never sent to the server. Circles display for 2 seconds, dots for 1 second. Four circles use the specified radii. Dots are placed in shuffled, jittered grid cells to guarantee no overlap even with adversarial random sequences.

Latency is measured only in the browser using `performance.now()` from options appearing to the latest answer selection. Confidence time is excluded from latency but included in the submission deadline. Keyboard 1–4 selects, Enter submits when confidence is confirmed. Submit is guarded against double clicks. Every submitted trial is stored immediately. Refreshing resumes the first unanswered item and restarts its presentation phases/deadline; it does not delete submitted trials. Timeout trials skip feedback. There is no localStorage, sessionStorage, or client-side persistence.

## Metrics and units

`backend/metrics.py` is the original source of truth. All timeouts are excluded. Reports include their count separately as `timed_out_count`.

- `accuracy`: mean correctness, 0–1.
- `mean_confidence`: mean on the 0–100 scale.
- `overconfidence`: mean confidence minus 100 × accuracy, in signed percentage points. Negative values indicate underconfidence. `underconfidence` is its negation.
- `calibration_error`: 10-point confidence bins, weighted mean of absolute bin confidence minus bin accuracy × 100. Bins are `[0,10)`, …, `[90,100]`; 100 is included in the top bin. Also in percentage points.
- `point_biserial_r`: Pearson correlation of confidence and binary correctness, null when either has zero variance or fewer than 2 observations.
- `calibration_curve`: populated bins with low/high bounds, mean confidence (0–100), accuracy (0–1), and count.
- `latency`: means in milliseconds overall, by correctness, and by difficulty. Empty cells are null.
- `by_difficulty` / `by_category`: n, accuracy, mean confidence, and `thin` flag for cells with fewer than 3 scored trials.
- `change_after_feedback`: late-half minus early-half signed confidence bias, requiring at least 4 scored trials and a feedback condition. Odd counts place the extra observation in the later half. Descriptive, not a causal estimate.
- `n`: scored, non-timeout trial count. All undefined numeric metrics are JSON null. The interface renders null as “not enough variation”, never zero.

Dashboard metrics average **session-level** metrics equally, separately for each condition/group; null values are omitted from these means. Calibration curves pool **trial-level** data into 20-point bins. Difficulty latencies also pool trials. Only completed sessions contribute to charts. Synthetic and participant sessions are both included by default and clearly flagged; Sessions has an explicit data-source filter, and the API accepts one for dashboard/export too.

Hand-check example: confidence `[100,80,60,20]`, correctness `[1,0,1,0]`, latency `[1000,2000,3000,4000]` gives accuracy `.5`, mean confidence `65`, bias `+15 pp`, calibration error `35 pp`, r `30/sqrt(3500)`, mean latency `2500 ms`, and feedback change `−50 pp`.

## JSON API

All errors return JSON `{ "message": "…" }` with clear HTTP status codes. Malformed input is 400, missing resources 404, and database unavailability/write conflicts 503. No authorization is performed.

| Method and route | Purpose |
| --- | --- |
| GET /api/health | Database connectivity check |
| POST /api/sessions | Create participant (if new) and session; returns session_id, participant_id, n_trials |
| GET /api/sessions/{id}/next | Next item, without answer; or `{done: true}` |
| POST /api/sessions/{id}/trials | Submit original answer index, confidence, browser latency, timed_out; server scores |
| POST /api/sessions/{id}/complete | Require all scheduled trials; store report; a second completion is rejected |
| GET /api/sessions | Session summaries with metrics and answered count |
| GET /api/sessions/{id} | Session and ordered trials |
| DELETE /api/sessions/{id} | Cascade session, trials, and report deletion; participant retained |
| GET /api/reports/{id} | Stored report and session metadata |
| GET /api/dashboard | Mean metrics by feedback/group, pooled curves, mean latency by difficulty |
| GET /api/export?format=csv or json | One row per trial with condition and participant fields |

List, dashboard, and export accept optional exact `group`, `feedback`, and `is_synthetic=true/false` filters. CSV has headers even when empty, encodes nulls as empty cells, and prefixes spreadsheet-formula group labels with an apostrophe. JSON preserves nulls.

Session creation example:

```json
{"n_trials":18,"group":"Group A","age_range":null,"academic_year":null,"condition":{"difficulty":"mixed","feedback":"immediate","time_limit":"20","categories":"all","interface":"slider"}}
```

Trial example:

```json
{"item_id":"logic-easy-1","answer":0,"confidence":80,"latency_ms":2431,"timed_out":false}
```

Timeout example uses `answer:null`, `confidence:null`, `latency_ms:null`, `timed_out:true`. The server validates session membership and item order; rejects unknown, duplicate, completed-session submissions, invalid values, and premature completion. Timeouts are accepted only in timed sessions. Client timing is trusted; the server cannot independently certify response latency.

## MongoDB data model

- **participants**: participant_id (unique), age_range, academic_year, created_at.
- **sessions**: session_id (unique), participant_id (indexed), group, condition, n_trials, item_order, started_at, ended_at, status (`in_progress` / `complete`), is_synthetic (false for real sessions).
- **trials**: session_id, trial_no, item_id, category, difficulty, original answer index/null, correct, confidence/null, latency_ms/null, timed_out, timestamp. Unique compound indexes `(session_id,item_id)` and `(session_id,trial_no)` prevent repeated submissions.
- **reports**: session_id (unique), metrics, generated_at. The unique report key prevents duplicate completion.

IDs are UUID session IDs and anonymous participant IDs. Timestamps are UTC ISO 8601 strings. Participant rows intentionally survive session deletion; demo clearing removes only demo participants. Backup MongoDB's volume before class research collection.

## Explicit synthetic demo data

Never automatic. From the repository root, with MongoDB running:

```bash
source .venv/bin/activate
cd backend
python seed_demo.py
python seed_demo.py --clear
```

Seed creates 24 deterministic sessions (12 immediate, 12 none), 36 trials each, using seed `20261021`. IDs have a `DEMO-` prefix, sessions have `is_synthetic:true`, and groups start with `Demo`. Demographics are null. The simulation has difficulty-dependent accuracy, person-specific confidence bias, larger hard-item bias, bias shrinking with immediate feedback, and slower errors. Existing synthetic sessions prevent accidental duplicate seeding. `--clear` deletes synthetic sessions/trials/reports and demo participants, then exits; it does not reseed or delete real sessions.

## Choices made where unspecified

- Original content/formulas/interface replace unavailable references, with explicit provenance.
- Project/repository name: `metacognitive-calibration-lab`; prefer a private GitHub repository.
- Default: 18 mixed/all trials, no feedback, no time limit, slider confidence.
- Server creates the ID when the session starts; setup previews its format rather than reserving unused participants.
- Timeouts have null latency and receive no feedback; entered confidence is discarded on expiration.
- Selected answer can be changed; latency reflects the latest selection.
- Completion requires every scheduled trial, including timeouts. Refresh restarts only the current unanswered item's phases.
- Fixed 440×240 SVG dot coordinates with responsive scaling; circle positions rendered in a 300×260 SVG at native pixel radii (scaling only when the viewport is narrower).
- Restricted conditions override n_trials based on actual bank selection.
- Session means power aggregate metrics; pooled trials power curves and latency charts.
- UTC timestamps and UUID session IDs; empty group labels form an unlabelled comparison group.
- Maximum JSON body 64 KiB, group 80 characters; no client-supplied synthetic flags.
- `.env` is backend-only; Vite's development proxy keeps API requests same-origin.
- Backend includes dev/test dependencies in one requirements file for simple local installation.

## Known limits

Single-machine local use; no authentication; anyone with API access can read/delete data. Do not expose the app or MongoDB to the internet. The original 36-item bank is illustrative and not psychometrically validated. It can become familiar after repeated use. Small-N calibration bins and category cells are thin. Simulated demo data is not real participant data and must not be used as evidence. Client timers depend on the browser and can be affected by background tabs; deadlines use elapsed performance time and catch up on the next timer callback. Refresh restarts the unanswered trial's viewing phase. Multi-document deletion/completion is designed for a local tool, not distributed concurrent administration; MongoDB transactions and recovery queues are not implemented. Dashboard aggregates read all matching local sessions; no large-study pagination or inferential statistics. Vite's dev server is the documented local UI server; deployment infrastructure is outside scope.

## Optional browser verification

With both servers running, install Playwright into the same Python environment (test tooling only):

```bash
source .venv/bin/activate
pip install playwright==1.62.0
python -m playwright install chromium
python backend/tests/browser_smoke.py
```

The script can use `CHROMIUM_PATH=/path/to/chromium` for an existing browser and `MCLAB_BASE_URL` for a different frontend origin. It checks setup, instructions, keyboard/range entry, the slider guard, report charts, 768px tablet layout, memory/filler phases, delayed feedback, perceptual display hiding, timeout-only completion, Sessions, and Dashboard. Screenshots go to a temporary `mclab-browser-*` folder. Like the HTTP smoke script, it explicitly creates verification sessions and deletes them and their orphaned participants in `finally`; run against a test database. Virtual browser time accelerates presentation phases without changing application code.

## GitHub repository

Source: https://github.com/ajay2005k/metacognitive-calibration-lab

The repository is initialized on `main`. The owner created the remote repository and granted the integration access after its creation API was unavailable. Repository visibility is controlled by the owner.

To get a fresh copy:

```bash
git clone https://github.com/ajay2005k/metacognitive-calibration-lab.git
cd metacognitive-calibration-lab
```

Follow the setup commands above. For subsequent committed changes in an authorized checkout:

```bash
git push origin main
```

The generated source ZIP omits `.git`, installed dependencies, build output, caches, and `.env`. The separate Git bundle preserves all local commits for transfer. Commit author is the neutral `MCLab Project <mclab@localhost>`; no personal Git identity was invented.
