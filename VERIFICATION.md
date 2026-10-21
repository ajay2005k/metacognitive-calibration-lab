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

GitHub account identity was verified as `ajay2005k`. The owner created `ajay2005k/metacognitive-calibration-lab` and granted the integration push access after repository creation through the integration returned HTTP 403. Source repository: https://github.com/ajay2005k/metacognitive-calibration-lab.

## AWS deployment preparation

- Production backend (Gunicorn) and frontend (Caddy/static React) Docker images build successfully. Build-time CA secrets are mounted only during installation and are not copied into images.
- The generated CloudFormation template passes offline `cfn-lint` validation. It includes CloudFront HTTPS/access gate, a restricted EC2 origin, a stable Elastic IP, and persistent encrypted root EBS storage for MongoDB.
- Three new tests cover anonymous access denial, bad-credential rejection, and preserving authenticated requests while removing the access credential before origin forwarding. Frontend total is now **14 passing tests**.
- Refreshed React Router, Vite, Vitest, PostCSS, and Tailwind patch versions; React remains 18. The production dependency audit reports **zero advisories**. The full install still reports 7 development-only advisories; Node/npm and those build dependencies are not shipped in the Caddy runtime image.
- Production-container integration passed: requests without the origin secret receive 403; valid requests reach health and SPA routes; a two-trial session produces the expected report through Caddy → Gunicorn → MongoDB; that report survives a MongoDB restart. Verification data was isolated in a disposable Compose project.
- Chromium smoke checks pass again with the updated frontend dependencies, including all trial phases, keyboard controls, charts, and tablet layout. Production builds pass with Vite 8.
- **Not deployed on AWS yet.** The current environment has no configured AWS outbound identity, secret binding, or cloud identity manifest. No AWS stack was created and no live AWS URL has been verified. See `deploy/aws/README.md` for account requirements, deployment, credentials, costs, and teardown.

## GitHub continuous deployment preparation

- Added a push-to-main GitHub Actions workflow: test/build first, then an OIDC-authenticated release job if repository connection variables are configured.
- Added a one-time CloudShell setup script that creates the hosting stack when needed and a repository/main-scoped IAM release role. No long-lived AWS keys are required in GitHub or chat.
- Added S3/SSM releases to the existing instance with a fixed Compose project, persistent data directory, deployment lock, and a success marker written only after origin health passes.
- Release unit tests use mocked AWS calls; they check command-input validation, shell syntax, and that failed SSM execution never produces a successful release summary. Actual IAM trust, GitHub-to-AWS token exchange, and remote releases cannot be verified until the owner performs the one-time AWS setup.
