# QABuddyAI — Web UI (Next.js, for Vercel)

Next.js chat UI for QABuddyAI. It talks to the FastAPI backend through its own
**server-side API routes** (`/api/ask`, `/api/health`), which proxy to the
backend. The browser never calls the backend directly — this avoids CORS,
avoids mixed-content, and keeps the backend URL hidden.

## Local dev

```bash
cp .env.local.example .env.local   # set BACKEND_URL (defaults to http://localhost/api)
npm install
npm run dev                        # http://localhost:3000
```

With the docker-compose backend running locally, `BACKEND_URL=http://localhost/api`
lets the UI answer questions end-to-end.

## Environment variables (set these in Vercel too)

| Var           | Meaning                                            | Example |
|---------------|----------------------------------------------------|---------|
| `BACKEND_URL` | Base URL of the FastAPI backend (server-side only) | `https://api.your-domain.com` |
| `BACKEND_KEY` | Shared secret sent as `X-QAB-Key` (blank for now)  | `super-secret` |

> A UI deployed to Vercel **cannot reach `http://localhost`** — set `BACKEND_URL`
> to a publicly reachable HTTPS backend (Phase B: droplet + Let's Encrypt + API key)
> before questions will work. Until then the UI loads fine and shows
> "backend unreachable".

## Deploy to Vercel

```bash
vercel login          # one-time, interactive
vercel                # preview deploy (link project on first run)
vercel --prod         # production deploy
```

Or import the repo at vercel.com and set the env vars in the dashboard.
