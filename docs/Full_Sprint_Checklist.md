# GitHub Dashboard — 8-Day Sprint Checklist

## Project Goal

Build and deploy a GitHub activity dashboard that:

- Uses **FastAPI** for the backend.
- Uses **React + TypeScript** for the frontend.
- Uses **TanStack Query** for server-state management.
- Uses **Supabase PostgreSQL** for persistence.
- Uses **GitHub REST API** for historical sync and reconciliation.
- Uses **GitHub Webhooks** for near-real-time push and pull request activity.
- Uses **GitHub Actions** for scheduled reconciliation and CI.
- Deploys

---

# Day 1 — Project Skeleton + End-to-End Connection

## Goal

Get the entire stack talking to itself before adding GitHub-specific logic.

## Backend Checklist

- [ ] Create the FastAPI project.
- [ ] Add a clean application structure:
  - [ ] `app/main.py`
  - [ ] `app/api/`
  - [ ] `app/models/`
  - [ ] `app/schemas/`
  - [ ] `app/services/`
  - [ ] `app/db/`
- [ ] Add environment-variable configuration.
- [ ] Create a Supabase PostgreSQL project.
- [ ] Add the PostgreSQL connection string to local environment variables.
- [ ] Configure SQLAlchemy 2.
- [ ] Configure Alembic.
- [ ] Create a basic `GET /api/health` endpoint.
- [ ] Create a temporary `GET /api/dashboard` endpoint returning hard-coded JSON.
- [ ] Verify FastAPI can start locally.

## Frontend Checklist

- [ ] Create a React + TypeScript application with Vite.
- [ ] Remove unnecessary starter content.
- [ ] Create a basic project structure:
  - [ ] `src/components/`
  - [ ] `src/pages/`
  - [ ] `src/api/`
  - [ ] `src/types/`
- [ ] Create a basic `DashboardPage`.
- [ ] Fetch data from the temporary FastAPI dashboard endpoint.
- [ ] Render at least one statistic from the backend response.
- [ ] Add basic loading and error states.

## Learning Focus

- [ ] Understand the browser → API → response flow.
- [ ] Understand the difference between frontend state and backend data.
- [ ] Understand how environment variables are separated between frontend and backend.
- [ ] Understand why the database is not accessed directly from React.

## Deliverables

- [ ] FastAPI project runs locally.
- [ ] React + TypeScript project runs locally.
- [ ] Supabase database connection works.
- [ ] Alembic is initialized.
- [ ] React successfully renders JSON returned by FastAPI.
- [ ] Commit the working vertical slice to GitHub.

## End-of-Day Proof

```text
React
  ↓
GET /api/dashboard
  ↓
FastAPI
  ↓
JSON response
  ↓
Dashboard renders successfully
```

---

# Day 2 — Database Models + GitHub REST Backfill

## Goal

Replace fake data with real GitHub data stored in PostgreSQL.

## Backend Checklist

- [ ] Create the `Repository` SQLAlchemy model.
- [ ] Create the `ActivityEvent` SQLAlchemy model.
- [ ] Create the `SyncRun` SQLAlchemy model.
- [ ] Create and run the first Alembic migration.
- [ ] Add a GitHub API token to backend environment variables.
- [ ] Build a small GitHub REST API client.
- [ ] Fetch the authenticated GitHub user.
- [ ] Fetch one to three selected repositories.
- [ ] Fetch recent commits for those repositories.
- [ ] Normalize GitHub commit data into `ActivityEvent` records.
- [ ] Create stable `external_key` values for deduplication.
- [ ] Add a service for initial synchronization.
- [ ] Add `POST /api/sync-runs`.
- [ ] Add `GET /api/sync-runs/{id}`.
- [ ] Update `GET /api/dashboard` to read from PostgreSQL.

## Frontend Checklist

- [ ] Create TypeScript types for the dashboard API response.
- [ ] Replace fake dashboard data with real API data.
- [ ] Add a repository summary section.
- [ ] Add a `Sync Now` button.
- [ ] Display sync status.
- [ ] Display the most recent successful sync time.

## Learning Focus

- [ ] Understand API pagination.
- [ ] Understand data normalization.
- [ ] Understand why GitHub API responses should not become your database schema directly.
- [ ] Understand idempotent inserts and upserts.
- [ ] Understand REST resource naming.

## Deliverables

- [ ] Real GitHub repository data is stored in Supabase.
- [ ] Real commit activity is stored in `ActivityEvent`.
- [ ] Dashboard data comes from PostgreSQL instead of hard-coded JSON.
- [ ] Manual sync can be triggered from the frontend.
- [ ] A second sync does not duplicate existing commits.

## End-of-Day Proof

```text
Click "Sync Now"
      ↓
FastAPI
      ↓
GitHub REST API
      ↓
Normalize data
      ↓
Supabase PostgreSQL
      ↓
GET /api/dashboard
      ↓
React displays real GitHub activity
```

---

# Day 3 — GitHub Webhooks

## Goal

Build the core event-driven path of the application.

## Backend Checklist

- [ ] Create the `WebhookDelivery` model.
- [ ] Add fields for:
  - [ ] GitHub delivery ID.
  - [ ] Event type.
  - [ ] Action.
  - [ ] Raw payload.
  - [ ] Processing status.
  - [ ] Received timestamp.
  - [ ] Processed timestamp.
  - [ ] Error details.
- [ ] Create and run the Alembic migration.
- [ ] Create `POST /api/webhooks/github`.
- [ ] Read the original raw request body.
- [ ] Verify `X-Hub-Signature-256`.
- [ ] Read `X-GitHub-Delivery`.
- [ ] Reject or safely ignore duplicate delivery IDs.
- [ ] Support the GitHub `ping` event.
- [ ] Support the GitHub `push` event.
- [ ] Normalize pushed commits into `ActivityEvent`.
- [ ] Return a `2XX` response quickly.
- [ ] Create tests for:
  - [ ] Valid signature.
  - [ ] Invalid signature.
  - [ ] Missing signature.
  - [ ] Duplicate delivery.
  - [ ] `ping` event.
  - [ ] `push` event.

## GitHub Configuration Checklist

- [ ] Create a webhook secret.
- [ ] Add the webhook secret to Vercel/local environment variables.
- [ ] Configure a GitHub repository webhook.
- [ ] Subscribe to `push` events.
- [ ] Use a temporary HTTPS tunnel if testing locally.
- [ ] Confirm GitHub reports successful webhook deliveries.

## Frontend Checklist

- [ ] Add a recent activity section.
- [ ] Add a manual dashboard refresh action.
- [ ] Display the latest commit activity.
- [ ] Show an `updated at` timestamp.

## Learning Focus

- [ ] Understand HMAC webhook signature verification.
- [ ] Understand why raw request bytes matter.
- [ ] Understand webhook delivery IDs.
- [ ] Understand event-driven architecture.
- [ ] Understand the difference between a webhook and a WebSocket.

## Deliverables

- [ ] GitHub successfully sends webhooks to the application.
- [ ] Invalid signatures are rejected.
- [ ] Duplicate webhook deliveries do not duplicate activity.
- [ ] A real `git push` creates activity in PostgreSQL.
- [ ] The pushed commit appears on the dashboard.

## End-of-Day Proof

```text
git commit
    ↓
git push
    ↓
GitHub
    ↓
POST /api/webhooks/github
    ↓
Verify HMAC
    ↓
Deduplicate delivery
    ↓
Store WebhookDelivery
    ↓
Create ActivityEvent
    ↓
Dashboard displays new commit
```

---

# Day 4 — Pull Requests + Idempotency + Reconciliation

## Goal

Make webhook ingestion more complete and make the system repairable.

## Backend Checklist

- [ ] Subscribe the GitHub webhook to `pull_request`.
- [ ] Process `pull_request.opened`.
- [ ] Process merged pull requests.
- [ ] Create activity types such as:
  - [ ] `commit`
  - [ ] `pr_opened`
  - [ ] `pr_merged`
- [ ] Create deterministic external keys for PR events.
- [ ] Ensure webhook-generated events and REST-sync events use compatible keys.
- [ ] Build a reconciliation service.
- [ ] Reconcile from the most recent successful sync timestamp.
- [ ] Add a small time overlap to reconciliation.
- [ ] Upsert instead of blindly inserting.
- [ ] Track reconciliation results in `SyncRun`.
- [ ] Add guardrails for GitHub API usage.
- [ ] Log GitHub rate-limit headers.

## Frontend Checklist

- [ ] Add PR opened statistics.
- [ ] Add PR merged statistics.
- [ ] Add activity labels for commits and PRs.
- [ ] Add a reconciliation status indicator.
- [ ] Display errors without removing existing dashboard data.

## Testing Checklist

- [ ] Process the same webhook twice.
- [ ] Confirm totals remain unchanged.
- [ ] Run reconciliation after webhook processing.
- [ ] Confirm REST reconciliation does not duplicate webhook data.
- [ ] Simulate a missed event and confirm reconciliation repairs it.

## Learning Focus

- [ ] Understand transport-level idempotency.
- [ ] Understand domain-level idempotency.
- [ ] Understand eventual consistency.
- [ ] Understand why webhooks provide speed while reconciliation provides correctness.

## Deliverables

- [ ] Pull request events are stored correctly.
- [ ] PR opened and PR merged totals are visible.
- [ ] Duplicate deliveries do not change statistics.
- [ ] Reconciliation can recover missing activity.
- [ ] GitHub API usage is visible through logging.

## End-of-Day Proof

```text
Webhook event
      ↓
Activity stored immediately

Later...

Reconciliation
      ↓
GitHub REST API
      ↓
Missing events found
      ↓
Upsert
      ↓
No duplicates
```

---

# Day 5 — Dashboard UI + TanStack Query

## Goal

Turn the backend into a usable dashboard while learning practical frontend patterns.

## Frontend Checklist

- [ ] Install TanStack Query.
- [ ] Configure `QueryClient`.
- [ ] Replace manual data fetching with `useQuery`.
- [ ] Use a query key that includes the selected date range.
- [ ] Add `useMutation` for manual sync/reconciliation.
- [ ] Invalidate dashboard queries after successful sync.
- [ ] Add a 30-second refetch interval.
- [ ] Build a stat-card grid.
- [ ] Add cards for:
  - [ ] Commits.
  - [ ] PRs opened.
  - [ ] PRs merged.
  - [ ] Active repositories.
- [ ] Add a daily activity chart.
- [ ] Add a repository summary table.
- [ ] Add a recent activity feed.
- [ ] Add a 7-day / 30-day selector.
- [ ] Add loading states.
- [ ] Add error states.
- [ ] Add empty states.
- [ ] Make the layout usable on smaller screens.
- [ ] Verify there are no browser console errors.

## Backend Checklist

- [ ] Freeze the basic dashboard response contract for the day.
- [ ] Add daily aggregation queries.
- [ ] Add repository aggregation queries.
- [ ] Add recent activity ordering and limits.
- [ ] Keep all GitHub API access out of `GET /api/dashboard`.

## Learning Focus

- [ ] Understand server state vs local UI state.
- [ ] Understand `useQuery`.
- [ ] Understand `useMutation`.
- [ ] Understand cache invalidation.
- [ ] Understand refetch intervals.
- [ ] Understand TypeScript API contracts.

## Deliverables

- [ ] Dashboard has a clear visual hierarchy.
- [ ] Dashboard includes four stat cards.
- [ ] Dashboard includes one activity chart.
- [ ] Dashboard includes repository summaries.
- [ ] Dashboard includes recent activity.
- [ ] Manual sync refreshes the UI through TanStack Query.
- [ ] Background polling updates the UI without a page reload.

## End-of-Day Proof

```text
FastAPI JSON
     ↓
TypeScript types
     ↓
TanStack Query
     ↓
React components
     ↓
Usable dashboard
```

---

# Day 6 — GitHub Actions + Scheduled Reconciliation + CI

## Goal

Automate correctness checks and recurring reconciliation.

## GitHub Actions Checklist

- [ ] Create `.github/workflows/reconcile.yml`.
- [ ] Add a scheduled workflow.
- [ ] Avoid scheduling exactly at the top of the hour.
- [ ] Add an `API_URL` repository secret.
- [ ] Add a reconciliation secret.
- [ ] Have the workflow call the protected reconciliation endpoint.
- [ ] Run reconciliation multiple times per day if desired.
- [ ] Add manual `workflow_dispatch`.
- [ ] Confirm a workflow run succeeds.

## Backend Checklist

- [ ] Protect the reconciliation endpoint with a secret.
- [ ] Make reconciliation safe to run repeatedly.
- [ ] Add structured logs.
- [ ] Include useful identifiers in logs:
  - [ ] `delivery_id`
  - [ ] `sync_run_id`
  - [ ] repository ID/name
- [ ] Add clear error handling for GitHub API failures.
- [ ] Add clear error handling for database failures.

## CI Checklist

- [ ] Create a backend test workflow.
- [ ] Run Python tests on pull requests or pushes.
- [ ] Create a frontend build/type-check workflow.
- [ ] Run TypeScript checks.
- [ ] Run the Vite production build.
- [ ] Confirm a failing test causes CI to fail.

## Learning Focus

- [ ] Understand CI vs scheduled jobs.
- [ ] Understand repository secrets.
- [ ] Understand protected internal endpoints.
- [ ] Understand why scheduled jobs must also be idempotent.
- [ ] Understand why scheduled workflows are not guaranteed to run at an exact second.

## Deliverables

- [ ] Scheduled reconciliation runs through GitHub Actions.
- [ ] Manual reconciliation can be triggered from GitHub Actions.
- [ ] Backend tests run automatically.
- [ ] Frontend build/type checks run automatically.
- [ ] Secrets are not committed to the repository.

## End-of-Day Proof

```text
GitHub Actions schedule
        ↓
POST /api/reconcile
        ↓
FastAPI
        ↓
GitHub REST API
        ↓
Supabase upserts
        ↓
Dashboard remains correct
```

---

# Day 7 — Deployment + Production Hardening

## Goal

Deploy the complete application and test it under real conditions.

## Backend Deployment Checklist

- [ ] Deploy FastAPI to Vercel.
- [ ] Add required environment variables.
- [ ] Configure the production Supabase database connection.
- [ ] Confirm Alembic migrations are applied.
- [ ] Confirm `/api/health` works in production.
- [ ] Confirm `/api/dashboard` works in production.
- [ ] Confirm the reconciliation endpoint works in production.

## Frontend Deployment Checklist

- [ ] Deploy React + TypeScript to Vercel.
- [ ] Configure the production API base URL if needed.
- [ ] Confirm production requests reach FastAPI.
- [ ] Confirm TanStack Query works after deployment.
- [ ] Confirm the chart renders in production.
- [ ] Confirm responsive layout still works.

## Webhook Checklist

- [ ] Update the GitHub webhook URL to the production endpoint.
- [ ] Confirm GitHub webhook delivery succeeds.
- [ ] Push a real commit.
- [ ] Confirm the event reaches production.
- [ ] Open a test pull request.
- [ ] Confirm PR activity reaches production.
- [ ] Confirm duplicate redelivery remains safe.

## Security + Reliability Checklist

- [ ] Confirm GitHub token exists only on the backend.
- [ ] Confirm webhook secret exists only in server-side environment variables.
- [ ] Confirm reconciliation secret is not exposed in frontend code.
- [ ] Confirm invalid webhook signatures return an error.
- [ ] Confirm raw errors do not expose secrets.
- [ ] Review Vercel usage.
- [ ] Review Supabase storage/database usage.
- [ ] Review GitHub API rate-limit usage.
- [ ] Review GitHub Actions usage.

## Deliverables

- [ ] Frontend is publicly reachable.
- [ ] Backend is publicly reachable.
- [ ] GitHub webhooks reach the deployed backend.
- [ ] Real activity flows into the production database.
- [ ] Scheduled reconciliation works against production.
- [ ] Application remains within free-tier constraints.

## End-of-Day Proof

```text
Real GitHub activity
      ↓
GitHub Webhook
      ↓
Production FastAPI
      ↓
Production Supabase
      ↓
Production React dashboard
```

---

# Day 8 — Documentation + Architecture Review + Final Demo

## Goal

Finish the project as an engineering case study, not just a working application.

## README Checklist

- [ ] Add a project overview.
- [ ] Add the technology stack.
- [ ] Add local setup instructions.
- [ ] Document required environment variables.
- [ ] Document database migration commands.
- [ ] Document frontend startup commands.
- [ ] Document backend startup commands.
- [ ] Explain how to configure the GitHub webhook.
- [ ] Explain how to run a manual reconciliation.
- [ ] Explain the scheduled GitHub Actions workflow.
- [ ] Add screenshots of the dashboard.
- [ ] Add the architecture diagram.
- [ ] Document known limitations.
- [ ] Document future improvements.

## Architecture Decision Record Checklist

### ADR-001 — FastAPI Instead of Django

- [ ] Document context.
- [ ] Document the decision.
- [ ] Document alternatives.
- [ ] Document consequences.
- [ ] Document when the decision should be revisited.

### ADR-002 — Webhooks + Reconciliation

- [ ] Explain why webhooks are used for low latency.
- [ ] Explain why reconciliation is still necessary.
- [ ] Explain eventual consistency.
- [ ] Explain failure recovery.

### ADR-003 — No Celery/Redis in the MVP

- [ ] Explain the free-tier constraint.
- [ ] Explain why webhook work is intentionally small.
- [ ] Explain how the processing service could later move behind a queue.
- [ ] Explain when Celery would become worthwhile.

### ADR-004 — Polling Instead of WebSockets

- [ ] Explain why the browser polls the backend.
- [ ] Explain why polling does not consume GitHub API quota.
- [ ] Explain when WebSockets or SSE would become worthwhile.

### ADR-005 — GitHub Actions Instead of Vercel Cron

- [ ] Explain free-tier considerations.
- [ ] Explain schedule flexibility.
- [ ] Explain CI/CD learning value.
- [ ] Note that scheduled workflow timing is approximate.

## Testing Checklist

- [ ] Run the complete backend test suite.
- [ ] Run frontend type checking.
- [ ] Run the production frontend build.
- [ ] Test the empty-dashboard state.
- [ ] Test API failure handling.
- [ ] Test invalid webhook signatures.
- [ ] Test duplicate webhook delivery.
- [ ] Test reconciliation after a missed event.
- [ ] Test a fresh deployment or fresh database setup if time allows.

## Final Demo Checklist

- [ ] Start from a known dashboard state.
- [ ] Show historical GitHub data.
- [ ] Push a new commit.
- [ ] Show the GitHub webhook delivery.
- [ ] Show the webhook record in the database.
- [ ] Show the new activity on the dashboard.
- [ ] Open or merge a pull request.
- [ ] Show PR statistics changing.
- [ ] Trigger a reconciliation.
- [ ] Explain why reconciliation does not duplicate events.
- [ ] Show the GitHub Actions workflow.
- [ ] Explain the architecture diagram.
- [ ] Explain at least three major tradeoffs you made.

## Deliverables

- [ ] Complete README.
- [ ] Architecture diagram.
- [ ] At least four Architecture Decision Records.
- [ ] Working CI pipeline.
- [ ] Working scheduled reconciliation.
- [ ] Deployed frontend.
- [ ] Deployed backend.
- [ ] Working GitHub webhook integration.
- [ ] Final end-to-end demo.
- [ ] List of future improvements.

## End-of-Day Proof

```text
Fresh or known application state
        ↓
Historical sync works
        ↓
Dashboard displays GitHub data
        ↓
Push a commit
        ↓
GitHub webhook fires
        ↓
FastAPI validates + stores it
        ↓
Dashboard updates
        ↓
Reconciliation runs safely
        ↓
No duplicate activity
        ↓
You can explain every architectural choice
```

---

# Final Definition of Done

The sprint is complete when all of the following are true:

- [ ] The application uses FastAPI, React, TypeScript, TanStack Query, SQLAlchemy, Alembic, Supabase PostgreSQL, GitHub Webhooks, GitHub REST API, GitHub Actions, and Vercel.
- [ ] Historical GitHub data can be synchronized.
- [ ] GitHub `push` events arrive through webhooks.
- [ ] GitHub `pull_request` events arrive through webhooks.
- [ ] Webhook signatures are verified.
- [ ] Duplicate webhook deliveries do not duplicate statistics.
- [ ] Reconciliation can repair missed events.
- [ ] The frontend never receives the GitHub API token.
- [ ] The dashboard includes useful statistics, a chart, repository summaries, and recent activity.
- [ ] TanStack Query manages frontend server state.
- [ ] GitHub Actions performs scheduled reconciliation.
- [ ] CI validates backend tests and frontend builds.
- [ ] The project is deployed.
- [ ] The application stays within the intended free-tier constraints.
- [ ] The README explains how the system works.
- [ ] Architecture decisions and tradeoffs are documented.
- [ ] You can demonstrate the complete end-to-end data flow.

---

# Scope-Cut Order

If the sprint begins slipping, remove features in this order:

1. [ ] Extra issue-event support.
2. [ ] Additional charts.
3. [ ] Repository filtering controls.
4. [ ] UI animations and visual polish.
5. [ ] Multiple date-range options beyond 7 and 30 days.
6. [ ] Additional GitHub Actions schedules.

Do **not** cut:

- [ ] Webhook signature verification.
- [ ] Webhook delivery deduplication.
- [ ] Push-event handling.
- [ ] Pull-request handling.
- [ ] Reconciliation.
- [ ] The real webhook → database → dashboard vertical slice.
- [ ] Basic automated tests.
- [ ] Documentation of architecture decisions.

---

# Final Project Flow

```text
Initial / Reconciliation Path

GitHub Actions or Sync Now
          ↓
       FastAPI
          ↓
   GitHub REST API
          ↓
 Normalize + Upsert
          ↓
 Supabase PostgreSQL
          ↓
    GET /dashboard
          ↓
 TanStack Query
          ↓
       React


Near-Real-Time Path

      git push / PR
            ↓
          GitHub
            ↓
          Webhook
            ↓
          FastAPI
            ↓
   Verify + Deduplicate
            ↓
      Normalize Event
            ↓
   Supabase PostgreSQL
            ↓
    TanStack Query Poll
            ↓
          React
```
