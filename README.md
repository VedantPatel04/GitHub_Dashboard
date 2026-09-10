# 

Hi :P Welcome to your GitHub dashboard 


---

## Stack

| | |
|---|---|
| **API** | Python, FastAPI, SQLAlchemy 2, Alembic |
| **UI** | React, TypeScript, Vite, TanStack Query |
| **Database** | Supabase PostgreSQL |
| **Auth** | GitHub OAuth. Token stays in Postgres. The browser only gets a session cookie |
| **Ingest** | GitHub webhook → Lambda Function URL → SQS → worker Lambda |
| **Jobs** | EventBridge runs reconciliation. You can also click Sync Now in the app |
| **Secrets** | Vercel env vars for the API. SSM Parameter Store for Lambdas |
| **Infra** | AWS CDK in `infra/` |
| **CI** | GitHub Actions |
| **Hosting** | Vercel for the UI and API. AWS for webhooks and cron |

---

## Local development

Create a GitHub OAuth App.

- Homepage: `http://127.0.0.1:5173`
- Callback: `http://127.0.0.1:8000/api/auth/github/callback`

Put this in `backend/.env` (gitignored):

```
DATABASE_URL=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/auth/github/callback
GITHUB_ALLOWED_LOGIN=
GITHUB_REPOS=owner/repo,owner/other
SESSION_SECRET=
FRONTEND_ORIGIN=http://127.0.0.1:5173
```

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

cd frontend
npm install
npm run dev
```

For local webhooks, tunnel `POST /api/webhooks/github`. SQS is only used in production.

```bash
cd backend
pytest
```

---



## Project structure

| | |
|---|---|
| `backend/app/api/` | HTTP routes |
| `backend/app/services/` | GitHub client, sync, webhooks, reconciliation |
| `backend/app/models/` | Database models |
| `backend/alembic/` | Migrations |
| `frontend/src/` | React dashboard |
| `infra/` | AWS CDK |
