# Railway Deployment Guide for Knowtis

## Overview

This guide walks you through deploying the Knowtis backend and WhatsApp connector services on Railway.

**Important:** Railway no longer offers a free tier. You'll need to add at least **$5 credit** to your account.

**Estimated monthly cost:** $21-38 depending on usage.

---

## Prerequisites

- Railway account with $5+ credit ([railway.app](https://railway.app))
- GitHub/GitLab account (for connecting your repository)
- This repository pushed to a Git remote

---

## Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `knowtis` repository
5. Railway will create a new project

---

## Step 2: Add Database Services

### Add PostgreSQL with pgvector

1. In your Railway project, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway will provision a database
4. After deployment, you need to enable pgvector extension:
   - Click on the PostgreSQL service
   - Go to **"Connect"** tab
   - Copy the connection string
   - Use a PostgreSQL client to connect and run:
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```

### Add Redis

1. Click **"+ New"** again
2. Select **"Database" → "Redis"**
3. Railway will provision Redis
4. Both `DATABASE_URL` and `REDIS_URL` will be automatically injected as environment variables

---

## Step 3: Deploy Backend Service (FastAPI)

1. Click **"+ New"** → **"GitHub Repo"** (or select existing connection)
2. Railway will detect the `backend/Dockerfile`
3. Configure the service:
   - **Name:** `backend` or `api`
   - **Root Directory:** `backend`
   - **Dockerfile Path:** `Dockerfile`
4. Add environment variables (see section below)
5. Click **"Deploy"**

### Backend Environment Variables

Go to the backend service → **"Variables"** tab and add:

**Required:**
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-referenced
REDIS_URL=${{Redis.REDIS_URL}}            # Auto-referenced
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
REFRESH_TOKEN_SECRET=<generate-with-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

WHATSAPP_CONNECTOR_URL=<will-set-after-whatsapp-deployment>
WHATSAPP_CONNECTOR_WEBHOOK_SECRET=<generate-random-secret>

FRONTEND_URL=<your-frontend-url-or-localhost-for-testing>
BACKEND_URL=${{RAILWAY_PUBLIC_DOMAIN}}

CELERY_TASK_ALWAYS_EAGER=False
LOG_LEVEL=INFO
LOG_FORMAT=json
DEBUG=False
```

**Optional (for full features):**
```bash
GOOGLE_CLIENT_ID=<from-google-cloud-console>
GOOGLE_CLIENT_SECRET=<from-google-cloud-console>
GROQ_API_KEY=<from-groq-console>
REVENUECAT_WEBHOOK_SECRET=<from-revenuecat-dashboard>
```

---

## Step 4: Deploy Celery Worker

1. Click **"+ New"** → **"GitHub Repo"**
2. Configure:
   - **Name:** `worker`
   - **Root Directory:** `backend`
   - **Dockerfile Path:** `Dockerfile.worker`
3. Add the **same environment variables** as the backend service
4. Click **"Deploy"**

**Note:** This service doesn't expose an HTTP port - it only processes background tasks.

---

## Step 5: Deploy WhatsApp Connector (Node.js)

1. Click **"+ New"** → **"GitHub Repo"**
2. Configure:
   - **Name:** `whatsapp-connector`
   - **Root Directory:** `whatsapp_connector`
3. Add environment variables:
   ```bash
   PORT=${{PORT}}  # Railway auto-assigns
   FASTAPI_WEBHOOK_URL=https://<your-backend-url>/api/v1/whatsapp/webhook
   WEBHOOK_SECRET=<same-as-backend-WHATSAPP_CONNECTOR_WEBHOOK_SECRET>
   NODE_ENV=production
   ```
4. Click **"Deploy"**

### ⚠️ CRITICAL: Add Persistent Volume for WhatsApp Auth

The WhatsApp connector stores authentication state that must survive restarts:

1. Go to WhatsApp service → **"Settings"** → **"Volumes"**
2. Click **"+ New Volume"**
3. Configure:
   - **Mount Path:** `/app/auth_info_baileys`
   - **Size:** 1GB (minimum)
4. Save and redeploy

**Without this volume, you'll need to re-scan the QR code after every deployment.**

---

## Step 6: Link Services Together

### Update Backend with WhatsApp Connector URL

1. Go to WhatsApp connector service
2. Copy the **Public URL** (e.g., `https://your-connector.up.railway.app`)
3. Go to backend service → **"Variables"**
4. Update `WHATSAPP_CONNECTOR_URL` with the WhatsApp connector URL

### Verify Webhook Connection

The backend expects webhooks from WhatsApp connector at:
```
https://<your-backend-url>/api/v1/whatsapp/webhook
```

Ensure both services use the same `WEBHOOK_SECRET`.

---

## Step 7: Verify Deployment

### Test Backend Health
```bash
curl https://<your-backend-url>/health
# Expected: {"status":"healthy"}
```

### Test WhatsApp Connector Status
```bash
curl https://<your-whatsapp-url>/status
# Expected: JSON with connection status and QR code
```

### Scan QR Code
1. Open `https://<your-whatsapp-url>/status` in browser
2. Scan the QR code with WhatsApp (Linked Devices)
3. Connector should show `CONNECTED` status

---

## Step 8: Database Migrations

Run database migrations from your local machine or Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run migrations
railway run --service backend alembic upgrade head
```

---

## Monitoring & Logs

### View Logs
- Click on any service in Railway dashboard
- Go to **"Deployments"** tab
- Click on latest deployment to view logs

### Monitor Resource Usage
- Go to service → **"Metrics"** tab
- Monitor CPU, Memory, Network usage
- Adjust resources if needed (will affect cost)

---

## Cost Management

Railway charges based on:
- **vCPU usage** (per second)
- **Memory usage** (per GB-hour)
- **Network egress** (per GB)
- **Volume storage** (per GB-month)

### Tips to Reduce Costs:
1. Scale down worker replicas during low traffic
2. Use smaller PostgreSQL instance for testing
3. Enable auto-sleep for non-critical services (though this requires Hobby plan)
4. Monitor usage in Railway dashboard

---

## Troubleshooting

### Backend Won't Connect to Database
- Verify `DATABASE_URL` is correctly referenced: `${{Postgres.DATABASE_URL}}`
- Check PostgreSQL service is running
- Verify pgvector extension is installed

### WhatsApp Keeps Disconnecting
- Check persistent volume is mounted at `/app/auth_info_baileys`
- Verify `WEBHOOK_SECRET` matches between services
- Check logs for ban/rate-limit warnings

### Worker Not Processing Tasks
- Verify `REDIS_URL` is correctly set
- Check worker service logs for connection errors
- Ensure `CELERY_TASK_ALWAYS_EAGER=False`

### QR Code Not Appearing
- Wait 30-60 seconds after deployment
- Check WhatsApp connector logs
- Refresh the `/status` page

---

## Alternative: Keep Running Locally

If Railway costs are too high for testing, you can continue using Docker Compose locally:

```bash
# Start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down
```

This is **completely free** and matches production architecture.

---

## Security Checklist

Before going to production:

- [ ] Generate strong `JWT_SECRET_KEY` and `REFRESH_TOKEN_SECRET`
- [ ] Set `DEBUG=False` in production
- [ ] Enable HTTPS (Railway provides this automatically)
- [ ] Rotate `WEBHOOK_SECRET` periodically
- [ ] Set up database backups in Railway
- [ ] Configure proper CORS in FastAPI (`FRONTEND_URL`)
- [ ] Enable PostgreSQL connection pooling
- [ ] Set up monitoring/alerting (e.g., Better Stack, Sentry)

---

## Next Steps

After successful deployment:

1. Deploy your Next.js frontend (Vercel recommended)
2. Update `FRONTEND_URL` in backend environment
3. Configure Google OAuth credentials with production URLs
4. Set up CI/CD with GitHub Actions (optional)
5. Configure custom domain (Railway supports this)

---

## Support

- Railway Docs: https://docs.railway.app
- Knowtis Issues: Check your repository's issues tab
- Railway Discord: https://discord.gg/railway
