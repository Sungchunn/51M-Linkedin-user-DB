# PROSPECTIQ - Deployment Guide

Complete guide for deploying PROSPECTIQ to production (Railway, Render, or Fly.io).

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

- [x] Dockerfile and .dockerignore created
- [x] Deployment configs (Procfile, railway.json, render.yaml, fly.toml)
- [x] Frontend config.js for environment-aware API URLs
- [x] CORS configuration for production
- [x] Secure JWT secret key generated
- [x] Production .env.example template
- [ ] OpenAI API key (for embeddings)
- [ ] Production database ready (PostgreSQL 17 with pgvector)
- [ ] Custom domain (optional)

---

## 🚀 Deployment Options

### Option 1: Railway (Recommended) ⭐

**Best for**: Quick deployment with managed PostgreSQL + Redis

#### Prerequisites
- Railway account (free tier available)
- Railway CLI installed: `npm install -g @railway/cli`

#### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

#### Step 2: Create New Project
```bash
cd "/path/to/51M-Linkedin-user-DB"
railway init
```

#### Step 3: Add PostgreSQL Database
```bash
railway add postgresql
```

The database will automatically create a `DATABASE_URL` environment variable.

#### Step 4: Add Redis (Optional)
```bash
railway add redis
```

#### Step 5: Configure Environment Variables

Go to Railway Dashboard → Your Project → Variables and add:

```bash
# Auto-configured by Railway
DATABASE_URL=<auto-configured>
REDIS_URL=<auto-configured>
PORT=<auto-configured>

# You must add these:
OPENAI_API_KEY=sk-your-openai-api-key
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
ADMIN_PASSWORD=<secure-password>

# Production settings
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://your-domain.railway.app

# Optional
ADMIN_USERNAME=admin
ALLOW_USER_REGISTRATION=true
```

#### Step 6: Deploy
```bash
railway up
```

Railway will:
1. Build Docker image from Dockerfile
2. Deploy to production
3. Provide a public URL: `https://your-app.railway.app`

#### Step 7: Run Database Migrations
```bash
railway run psql $DATABASE_URL < migrations/001_init_schema.sql
railway run psql $DATABASE_URL < migrations/002_indexes.sql
railway run psql $DATABASE_URL < migrations/003_vector_index.sql
railway run psql $DATABASE_URL < migrations/008_users_and_api_keys.sql
```

#### Step 8: Load Data (if needed)
```bash
# Connect to Railway
railway link

# Load data
railway run poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_test.parquet
```

#### Cost Estimate
- **Hobby Plan**: $5/month
- **PostgreSQL**: $5-10/month
- **Redis**: $5/month
- **Total**: ~$15-20/month

---

### Option 2: Render

**Best for**: Automatic deploys from GitHub with generous free tier

#### Step 1: Connect GitHub Repository
1. Go to [render.com](https://render.com)
2. Sign in with GitHub
3. Click "New" → "Blueprint"
4. Select your repository

#### Step 2: Configure Blueprint
The `render.yaml` file is already configured. Render will:
1. Create PostgreSQL database with pgvector
2. Create web service for FastAPI backend
3. Create Redis instance (optional)

#### Step 3: Set Environment Variables
In Render Dashboard → Your Service → Environment:

```bash
# Database (auto-configured)
DATABASE_URL=<auto-configured>

# Required secrets
OPENAI_API_KEY=sk-your-openai-api-key
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
ADMIN_PASSWORD=<secure-password>

# Production settings
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://your-app.onrender.com
```

#### Step 4: Deploy
Click "Create Web Service" and Render will automatically:
1. Build Docker image
2. Run migrations (if configured)
3. Deploy to production
4. Provide URL: `https://your-app.onrender.com`

#### Step 5: Run Migrations
Using Render Shell (Dashboard → Shell):
```bash
psql $DATABASE_URL < migrations/001_init_schema.sql
psql $DATABASE_URL < migrations/002_indexes.sql
psql $DATABASE_URL < migrations/003_vector_index.sql
psql $DATABASE_URL < migrations/008_users_and_api_keys.sql
```

#### Cost Estimate
- **Free Tier**: $0/month (with limitations)
- **Starter**: $7/month
- **PostgreSQL Standard**: $7/month
- **Total**: $14-20/month

---

### Option 3: Fly.io

**Best for**: Global edge deployment with built-in CDN

#### Step 1: Install Fly CLI
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

#### Step 2: Create App
```bash
cd "/path/to/51M-Linkedin-user-DB"
fly launch --no-deploy
```

This creates `fly.toml` (already exists in your repo).

#### Step 3: Create PostgreSQL Database
```bash
fly postgres create --name prospectiq-db
fly postgres attach prospectiq-db
```

#### Step 4: Set Secrets
```bash
fly secrets set OPENAI_API_KEY=sk-your-openai-api-key
fly secrets set JWT_SECRET_KEY=$(openssl rand -hex 32)
fly secrets set ADMIN_PASSWORD=secure-password-here
fly secrets set ENVIRONMENT=production
fly secrets set CORS_ORIGINS=https://your-app.fly.dev
```

#### Step 5: Deploy
```bash
fly deploy
```

#### Step 6: Run Migrations
```bash
fly ssh console
# Inside the container:
psql $DATABASE_URL < migrations/001_init_schema.sql
psql $DATABASE_URL < migrations/002_indexes.sql
psql $DATABASE_URL < migrations/003_vector_index.sql
psql $DATABASE_URL < migrations/008_users_and_api_keys.sql
```

#### Cost Estimate
- **Free Allowance**: 3 shared-cpu-1x 256MB VMs
- **PostgreSQL**: ~$10/month
- **Total**: $10-15/month

---

## 🌐 Frontend Deployment

### Option A: Serve Static Files from Backend

Add this to `backend/api/app.py`:

```python
from fastapi.staticfiles import StaticFiles

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

Then rebuild and deploy.

### Option B: Deploy Frontend Separately (Recommended)

**Vercel** (Recommended for frontend):

1. Create `vercel.json` in `frontend/`:
```json
{
  "routes": [
    { "src": "/(.*)", "dest": "/$1" }
  ]
}
```

2. Deploy:
```bash
cd frontend
npx vercel --prod
```

**Netlify**:
```bash
cd frontend
npx netlify deploy --prod --dir .
```

3. Update backend CORS:
```bash
CORS_ORIGINS=https://your-frontend.vercel.app
```

---

## 🔐 Security Best Practices

### 1. Generate Secure Secrets
```bash
# JWT Secret
openssl rand -hex 32

# Admin Password
openssl rand -base64 24
```

### 2. Never Commit Secrets
Add to `.gitignore`:
```
.env
.env.local
.env.production
```

### 3. Use Secrets Manager
- Railway: Use Railway variables
- Render: Use Render environment variables
- Fly.io: Use `fly secrets set`

### 4. Enable HTTPS
All platforms provide automatic SSL/TLS certificates.

### 5. Configure CORS Properly
In production .env:
```bash
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
ENVIRONMENT=production
```

### 6. Rate Limiting (TODO)
Implement Redis-based rate limiting:
```python
# In backend/api/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

---

## 📊 Post-Deployment Tasks

### 1. Verify Health Check
```bash
curl https://your-app.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "profiles_total": 497552,
  "timestamp": "2025-11-02T10:30:00Z"
}
```

### 2. Test Authentication
```bash
# Register user
curl -X POST https://your-app.railway.app/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Test User"
  }'

# Login
curl -X POST https://your-app.railway.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!"
  }'
```

### 3. Test Search
```bash
curl -X POST https://your-app.railway.app/search \
  -H "Content-Type: application/json" \
  -d '{"query": "software engineer", "limit": 10}'
```

### 4. Load Data (if needed)
```bash
# Prepare 1M dataset
poetry run python scripts/prepare_1m_dataset.py

# Load data
poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_test.parquet
```

### 5. Generate Embeddings
```bash
# Generate embeddings for profiles without them
poetry run python -m backend.data_pipeline.embeddings.generate
```

---

## 🔧 Troubleshooting

### Database Connection Issues

**Problem**: `asyncpg.exceptions.CannotConnectNowError`

**Solution**:
```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# Should be: postgresql://user:pass@host:port/dbname
# If using Render/Railway, it's auto-configured
```

### CORS Errors

**Problem**: `Access-Control-Allow-Origin` errors

**Solution**:
```bash
# Update CORS_ORIGINS in production
CORS_ORIGINS=https://your-frontend.vercel.app,https://your-app.railway.app
ENVIRONMENT=production
```

### Port Binding Issues

**Problem**: Application not listening on correct port

**Solution**:
```bash
# Railway/Render auto-set $PORT
# Ensure your app uses it:
API_PORT=${PORT:-8000}
```

### Migrations Not Running

**Problem**: Tables don't exist

**Solution**:
```bash
# Run migrations manually
psql $DATABASE_URL < migrations/001_init_schema.sql
psql $DATABASE_URL < migrations/002_indexes.sql
psql $DATABASE_URL < migrations/003_vector_index.sql
psql $DATABASE_URL < migrations/008_users_and_api_keys.sql
```

---

## 📈 Monitoring & Logging

### Application Logs
```bash
# Railway
railway logs

# Render
# View in dashboard

# Fly.io
fly logs
```

### Database Monitoring
```bash
# Check connection count
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Check table sizes
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_total_relation_size('profiles'));"
```

### Performance Monitoring
Add to your app:
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

---

## 🚀 Scaling Tips

### 1. Increase Worker Count
In `Procfile` or Dockerfile CMD:
```bash
uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT --workers 4
```

### 2. Add Redis Caching
```bash
# Enable in .env
REDIS_ENABLED=true
REDIS_URL=${REDIS_URL}
```

### 3. Database Optimization
```sql
-- Add more indexes
CREATE INDEX CONCURRENTLY idx_profiles_quality ON profiles(quality_score);
CREATE INDEX CONCURRENTLY idx_profiles_industry ON profiles(industry);
```

### 4. CDN for Frontend
Use Cloudflare or your platform's CDN for static assets.

---

## 📝 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings |
| `JWT_SECRET_KEY` | Yes | - | Secret key for JWT tokens |
| `ADMIN_PASSWORD` | Yes | - | Admin account password |
| `PORT` | No | 8000 | Application port (auto-set by platforms) |
| `ENVIRONMENT` | No | development | Set to "production" |
| `CORS_ORIGINS` | No | * | Comma-separated allowed origins |
| `REDIS_URL` | No | - | Redis connection string |
| `DEBUG` | No | false | Debug mode |
| `ADMIN_USERNAME` | No | admin | Admin username |
| `ALLOW_USER_REGISTRATION` | No | true | Enable user registration |

---

## 🎉 Success!

Your PROSPECTIQ application is now deployed and ready for production use!

**Next steps:**
1. Set up custom domain
2. Configure email notifications (optional)
3. Add monitoring (Sentry, DataDog, etc.)
4. Set up automated backups
5. Configure CI/CD for automatic deployments

---

## 📞 Support

If you encounter issues:
1. Check application logs
2. Review this guide
3. Check platform-specific documentation:
   - [Railway Docs](https://docs.railway.app)
   - [Render Docs](https://render.com/docs)
   - [Fly.io Docs](https://fly.io/docs)

---

**Built with** ❤️ **using PostgreSQL 17, FastAPI, and OpenAI Embeddings**
