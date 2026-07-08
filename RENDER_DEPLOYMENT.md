# Knowtis Deployment Guide (Render.com)

This guide explains how to deploy the Knowtis backend and WhatsApp connector services to Render.com for free testing.

## 🆓 Render.com Free Tier Limits

- **PostgreSQL**: 90-day free trial, 1GB storage
- **Redis**: 25MB storage (persists indefinitely)
- **Web Services**: Sleep after 15 minutes of inactivity (auto-wake on request)
- **Worker Services**: Free tier available
- **Persistent Disk**: 1GB free per service

## 📋 Prerequisites

1. Render.com account (sign up at https://render.com)
2. GitHub/GitLab repository with your code
3. This repository must contain `render.yaml` (already created)

## 🚀 Deployment Steps

### Step 1: Prepare Your Repository

Ensure these files exist in your repo (already created):
- ✅ `render.yaml` - Main deployment configuration
- ✅ `backend/Dockerfile` - FastAPI backend image
- ✅ `backend/Dockerfile.worker` - Celery worker image
- ✅ `whatsapp_connector/package.json` - Node.js dependencies
- ✅ `docker/postgres.Dockerfile` - PostgreSQL with pgvector

### Step 2: Connect Repository to Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub/GitLab repository
4. Select the repository containing this code
5. Render will automatically detect `render.yaml`
6. Click **"Apply"**

Render will create all 5 services automatically:
- `knowtis-postgres` (PostgreSQL)
- `knowtis-redis` (Redis)
- `knowtis-backend` (FastAPI)
- `knowtis-worker` (Celery)
- `knowtis-whatsapp` (WhatsApp Connector)

### Step 3: Configure Environment Variables

After deployment, add these **optional** environment variables in the Render Dashboard:

#### For `knowtis-backend` service:

**Google OAuth (Optional)**
```
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
FRONTEND_URL=https://your-frontend-url.vercel.app
```

**AI Features (Optional - Groq API)**
```
GROQ_API_KEY=your_groq_api_key_here
```

**RevenueCat (Optional - for subscription payments)**
```
REVENUECAT_WEBHOOK_SECRET=your_revenuecat_secret_here
```

**Update Backend URL**
```
BACKEND_URL=https://knowtis-backend.onrender.com
```

#### For `knowtis-whatsapp` service:

The WhatsApp connector gets its configuration automatically from the backend service, but verify:
```
FASTAPI_WEBHOOK_URL=https://knowtis-backend.onrender.com/api/v1/whatsapp/webhook
```

### Step 4: Access WhatsApp Connector

1. Find your WhatsApp service URL: `https://knowtis-whatsapp.onrender.com`
2. Open the status page (append your connector secret as a query param:
   `https://knowtis-whatsapp.onrender.com/status?secret=CONNECTOR_API_SECRET`
3. Click the **“Generate / Show QR”** button on the page — it triggers the QR
   request in-page and renders the QR image. Wait up to ~30s.
4. Scan the QR code with WhatsApp → Linked Devices → Link a Device to authenticate
5. The auth state is saved to persistent disk (survives restarts)

> Note: `/status`, `/generate-qr`, `/disconnect` etc. all require the
> `CONNECTOR_API_SECRET` (via `?secret=` query or `X-Connector-Secret` header).
> A bare GET of `/generate-qr` returns "Cannot GET" because it is a POST endpoint
> — use the button on the `/status` page instead.

### Step 5: Verify Deployment

Check each service status:

**Backend Health Check**
```bash
curl https://knowtis-backend.onrender.com/health
```

**WhatsApp Connector Status** (requires secret)
```bash
curl "https://knowtis-whatsapp.onrender.com/status?secret=CONNECTOR_API_SECRET"
```

**WhatsApp Connector Health** (open liveness probe)
```bash
curl https://knowtis-whatsapp.onrender.com/health
```

**API Documentation**
Open: `https://knowtis-backend.onrender.com/docs`

## ⚠️ Important Notes

### Free Tier Sleep Behavior

Free tier web services **sleep after 15 minutes of inactivity**. They automatically wake when receiving a request, but the first request will be slow (~30 seconds).

**To keep services awake (optional)**:

Use a cron job service like **Cron-Job.org** or **UptimeRobot** to ping your services every 10 minutes:

```
GET https://knowtis-backend.onrender.com/health
GET https://knowtis-whatsapp.onrender.com/health
```

⚠️ **Note**: This keeps the service running but uses your free tier hours faster.

### WhatsApp Authentication Persistence

> [!TIP]
> **Auth state is now stored in PostgreSQL** — no persistent disk needed.
> The WhatsApp connector (Node.js/Baileys) stores its credentials via the
> backend's `/api/v1/whatsapp/auth-state` endpoint, which saves them as
> JSONB in the `whatsapp_auth_state` table. This survives Render free-tier
> restarts, sleep/wake cycles, and deploys automatically.
>
> **How it works:**
> 1. On startup, the connector fetches the auth state from the backend
> 2. On every `creds.update` event, the connector debounces and POSTs the
>    updated state to the backend (2-second debounce to avoid hammering)
> 3. The backend stores the full auth object in the `whatsapp_auth_state`
>    table (single row, PK=1) as JSONB
> 4. If the auth state is empty (first-time pair), Baileys generates a QR
> 5. After scanning, credentials persist forever — no re-scan needed
>
> **Only need to re-scan if:** you click "Reset Session" or remove the
> linked device from your phone (WhatsApp → Linked Devices).

### Database Limits

PostgreSQL free tier expires after **90 days**. Before expiration:
1. Export your database
2. Either upgrade to paid tier (~$7/month)
3. Or migrate to another provider

### Redis Limits

25MB storage is enough for basic task queuing, but monitor usage:
```bash
redis-cli INFO memory
```

## 🔧 Troubleshooting

### Service Won't Start

1. Check logs in Render Dashboard
2. Verify environment variables are set correctly
3. Ensure Docker builds succeed locally first

### WhatsApp Won't Connect

1. Check `/status` endpoint shows QR code
2. Verify `FASTAPI_WEBHOOK_URL` points to correct backend URL
3. Check `WEBHOOK_SECRET` matches between services
4. Ensure persistent disk is mounted correctly

### Database Connection Errors

1. Verify `DATABASE_URL` is automatically set by Render
2. Check PostgreSQL service is running
3. Ensure pgvector extension is enabled

### Worker Tasks Not Processing

1. Check `knowtis-worker` service logs
2. Verify Redis connection (`CELERY_BROKER_URL`)
3. Ensure `CELERY_TASK_ALWAYS_EAGER=false`

## 📊 Monitoring

### View Logs

```bash
# Via Render Dashboard
1. Go to your service
2. Click "Logs" tab
3. Real-time streaming logs appear

# Via Render CLI (optional)
render logs knowtis-backend
render logs knowtis-whatsapp
```

### Monitor Resources

Check CPU/Memory usage in Render Dashboard → Service → Metrics

## 🔄 Updates & Redeployment

When you push code changes to your repository:

1. Render automatically detects the push
2. Rebuilds affected services
3. Deploys with zero-downtime (paid tier) or brief downtime (free tier)

**Manual Redeploy**:
1. Go to service in Dashboard
2. Click "Manual Deploy" → "Deploy latest commit"

## 💰 Cost Breakdown (If Upgrading from Free Tier)

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| PostgreSQL | 90 days | $7/month |
| Redis | 25MB | $10/month (500MB) |
| Backend | Sleep after 15min | $7/month |
| Worker | Limited hours | $7/month |
| WhatsApp | Sleep after 15min | $7/month |
| **Total** | **Free (90 days)** | **~$38/month** |

## 🆚 Alternative: Railway (No Free Tier)

If you prefer Railway instead:
- Requires $5 minimum credit
- No sleep behavior
- Similar monthly costs (~$21-38/month)
- Better for production

## ✅ Next Steps

After deployment:
1. Deploy your Next.js frontend to Vercel (free)
2. Update `FRONTEND_URL` in backend environment variables
3. Configure CORS in `backend/app/main.py` if needed
4. Set up domain names (optional, available on paid tier)

## 📚 Useful Links

- Render Docs: https://render.com/docs
- Render Status: https://status.render.com
- PostgreSQL Guide: https://render.com/docs/databases
- Persistent Disk Guide: https://render.com/docs/disks

## 🐛 Getting Help

If you encounter issues:
1. Check Render community forum: https://community.render.com
2. Review service logs in Dashboard
3. Test services locally with `docker-compose up` first
4. Open issue in your repository with error logs
