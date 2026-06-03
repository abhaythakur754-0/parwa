# PARWA — Free Tier Deployment Guide

Deploy Parwa for ₹0 using Vercel + Render + Supabase + Upstash.

## Architecture

```
User → Vercel (Next.js frontend) → Render (FastAPI backend) → Supabase (PostgreSQL)
                                  ↘ Upstash (Redis)            ↘ Celery worker (Render)
                                  ↘ Socket.io (on Render)
```

## Step 1: Supabase (PostgreSQL) — 2 minutes

1. Go to [supabase.com](https://supabase.com) → Sign up with GitHub
2. Create new project → Choose region closest to your users
3. Wait ~2 minutes for project to provision
4. Go to **Settings → Database → Connection string → URI**
5. Copy the connection string (looks like `postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:6543/postgres`)
6. Save this as `DATABASE_URL` — you'll need it in Step 3

## Step 2: Upstash (Redis) — 1 minute

1. Go to [upstash.com](https://upstash.com) → Sign up with GitHub
2. Create Redis database → Choose same region as Supabase
3. Copy the **UPSTASH_REDIS_REST_URL** and note the connection string
4. The Redis URL looks like: `rediss://default:TOKEN@region.upstash.io:6379`
5. Save as `REDIS_URL` for Step 3

## Step 3: Render (Backend) — 5 minutes

1. Go to [render.com](https://render.com) → Sign up with GitHub
2. **New → Web Service** → Connect your `parwa` repo
3. Settings:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   - **Plan**: Free
4. Add Environment Variables (from `backend/.env.render.example`):
   - `ENVIRONMENT=production`
   - `DATABASE_URL` = (from Step 1)
   - `REDIS_URL` = (from Step 2)
   - `SECRET_KEY` = generate with `openssl rand -base64 48`
   - `JWT_SECRET_KEY` = generate with `openssl rand -base64 48`
   - `DATA_ENCRYPTION_KEY` = exactly 32 chars (use `openssl rand -hex 16`)
   - `PRICING_SIGNING_KEY` = generate with `openssl rand -base64 48`
   - `REFRESH_TOKEN_PEPPER` = generate with `openssl rand -base64 32`
   - `CORS_ORIGINS` = your Vercel URL (from Step 4)
   - `FRONTEND_URL` = your Vercel URL (from Step 4)
   - `LLM_PROVIDER=litellm`
   - `GOOGLE_AI_API_KEY` = your key
   - `CEREBRAS_API_KEY` = your key
   - `GROQ_API_KEY` = your key
   - `GOOGLE_CLIENT_ID` = your key
   - `GOOGLE_CLIENT_SECRET` = your key
   - `CSRF_ENABLED=true`
   - `PADDLE_CLIENT_TOKEN` = your key
   - `PADDLE_API_KEY` = your key
   - `PADDLE_PRICE_IDS` = your price IDs JSON
5. **Create Web Service** → Wait for build (~3-5 minutes)
6. Note your backend URL: `https://parwa-backend.onrender.com`

### Optional: Celery Worker (same Render account)

1. **New → Background Worker** → Same repo
2. Same root directory: `backend`
3. **Start Command**: `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1`
4. Same env vars as web service + `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`

## Step 4: Vercel (Frontend) — 2 minutes

1. Go to [vercel.com](https://vercel.com) → Sign up with GitHub
2. **Add New Project** → Import `parwa` repo
3. Framework Preset: **Next.js**
4. Root Directory: `.` (leave default — Vercel detects Next.js automatically)
5. Add Environment Variables:
   - `NEXT_PUBLIC_API_URL` = `https://parwa-backend.onrender.com`
   - `NEXT_PUBLIC_WS_URL` = `wss://parwa-backend.onrender.com`
   - `NEXTAUTH_SECRET` = generate with `openssl rand -base64 48`
   - `NEXTAUTH_URL` = your Vercel URL (e.g., `https://parwa.vercel.app`)
   - Any `NEXT_PUBLIC_*` vars you need
6. **Deploy** → Wait for build (~2-3 minutes)

## Step 5: Keep Render Awake (UptimeRobot) — 1 minute

1. Go to [uptimerobot.com](https://uptimerobot.com) → Sign up
2. **Add New Monitor**:
   - Type: HTTP(s)
   - URL: `https://parwa-backend.onrender.com/api/health`
   - Interval: 5 minutes
3. This pings your backend every 5 min → prevents Render from sleeping

## Step 6: Update Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. APIs & Services → Credentials → Your OAuth Client
3. Add **Authorized JavaScript Origins**: `https://your-app.vercel.app`
4. Add **Authorized Redirect URIs**: `https://your-app.vercel.app/api/auth/google`

## Step 7: Run Database Migrations

Alembic migrations run **automatically** on Render startup. But if you need to manually run them:

```bash
# On Render Shell (Dashboard → Shell)
cd /opt/render/project/src
alembic -c database/alembic.ini upgrade head
```

## Cost Summary

| Service | Plan | Monthly Cost |
|---------|------|-------------|
| Vercel | Hobby | $0 |
| Render (Web) | Free | $0 |
| Render (Worker) | Free | $0 |
| Supabase | Free | $0 |
| Upstash | Free | $0 |
| UptimeRobot | Free | $0 |
| **Total** | | **$0** |

## When to Upgrade

- **50+ clients**: Supabase 500MB getting full → Supabase Pro ($25/mo)
- **Cold starts annoying**: Render Standard ($7/mo) — no sleeping
- **More bandwidth**: Vercel Pro ($20/mo) — unlimited bandwidth
- **More Redis**: Upstash Pay-as-you-go (still very cheap)
