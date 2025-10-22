# CRITICAL ISSUES & DEPLOYMENT READINESS

## 🚨 CRITICAL ISSUES FOUND

### 1. **API Key System Disconnect** (BLOCKING)
**Problem**: Two separate API key systems that don't communicate:
- Database-backed API keys (via `APIKeyManager` + `users` & `api_keys` tables)
- Environment variable API keys (via `API_KEYS` JSON in `auth.py`)

**Impact**:
- Users can generate API keys via dashboard, but they won't work!
- Rate limiting uses `resolve_auth_context()` which only reads from `API_KEYS` env var
- Tier-based limits (public: 10/min, basic: 200/min, trusted: 1000/min) not enforced

**Root Cause**:
- `backend/api/auth.py:48` - `resolve_auth_context()` only checks environment variable
- `backend/api/user_manager.py` - `APIKeyManager` stores keys in PostgreSQL
- No bridge between these two systems

**Fix Required**:
1. Update `resolve_auth_context()` to check database first before falling back to env vars
2. Implement tier-based rate limiting using `ctx.tier` from AuthContext
3. Update rate limiter calls to use tier-specific limits

---

### 2. **Rate Limiting Not Tier-Based** (BLOCKING)
**Problem**: All rate limiting uses global env var limits, ignoring API key tiers

**Current State**:
```python
# app.py:426 - Same rate limit for everyone!
limiter.allow(rl_key, int(os.getenv("RATE_LIMIT_SEARCH_PER_MIN", "60")), ...)
```

**Should Be**:
```python
# Tier-based limits
TIER_LIMITS = {
    "public": 10,
    "basic": 200,
    "trusted": 1000
}
limiter.allow(rl_key, TIER_LIMITS[ctx.tier], ...)
```

**Impact**: No differentiation between free vs paid tiers

---

### 3. **Dashboard Tier Dropdown Missing "Public"** (FIXED ✅)
**Problem**: Frontend tier selector had "basic" and "trusted" but not "public"
**Status**: Fixed in `frontend/dashboard.html:454`

---

## 📋 DEPLOYMENT CHECKLIST

### Phase 1: Critical Fixes (DO NOT DEPLOY WITHOUT THESE)
- [ ] **Fix API key resolution** - Connect database keys to auth system
- [ ] **Implement tier-based rate limiting** - Use `ctx.tier` for limits
- [ ] **Test auth flow end-to-end** - Registration → Login → Create Key → Use Key → Rate Limit

### Phase 2: Data Preparation
- [ ] **Extract 1M best profiles**
  - Script: `scripts/prepare_1m_dataset.py`
  - Criteria: Quality score, completeness, email/linkedin availability
  - Target: Top 1M from 51M dataset
- [ ] **Generate embeddings for 1M profiles**
  - Current: 5,002 profiles with embeddings (from 10K test)
  - Need: 1M profiles with embeddings for semantic search

### Phase 3: Security & Infrastructure
- [ ] **Environment Variables Management**
  - Move from `.env` to secrets manager (Railway Secrets / Render Env Vars)
  - Required vars:
    - `DATABASE_URL` (PostgreSQL connection)
    - `JWT_SECRET_KEY` (token signing)
    - `OPENAI_API_KEY` (for embeddings - if needed)
    - `CORS_ORIGINS` (production domain)
    - `RATE_REDIS_HOST` (Redis for rate limiting)
- [ ] **Setup Redis**
  - Currently using in-memory rate limiting (not persistent)
  - Need Redis for multi-instance deployments
  - Options: Redis Cloud, Upstash, Railway Redis
- [ ] **CORS Configuration**
  - Current: `CORS_ORIGINS=*` (allows all - INSECURE)
  - Update to production domain: `https://prospectiq.com`
- [ ] **HTTPS/SSL**
  - Auto-enabled on Railway/Render
  - Verify cert after deployment

### Phase 4: Monitoring & Reliability
- [ ] **Add Error Tracking**
  - Sentry for backend errors
  - LogRocket for frontend issues
  - Setup alerts for 5xx errors
- [ ] **Database Backups**
  - Automated daily backups
  - Point-in-time recovery
  - Test restore process
- [ ] **Health Checks**
  - `/health` endpoint exists ✅
  - Add database connectivity check
  - Add Redis connectivity check
- [ ] **Logging**
  - Structured JSON logs for production
  - Log aggregation (Logtail, Papertrail)
  - Set log retention policy

### Phase 5: Performance
- [ ] **Database Optimization**
  - Verify indexes on `profiles` table
  - Check query performance with EXPLAIN ANALYZE
  - Consider connection pooling settings (min=5, max=40 currently)
- [ ] **Caching**
  - Filter endpoints already cached (10min)
  - Consider caching popular searches
- [ ] **CDN for Static Assets**
  - Frontend files (HTML, CSS, JS)
  - CloudFlare or similar

### Phase 6: Final Testing
- [ ] **Load Testing**
  - Test with 100 concurrent users
  - Verify rate limiting works correctly
  - Check response times under load
- [ ] **Security Audit**
  - OWASP Top 10 checks
  - SQL injection protection (using parameterized queries ✅)
  - XSS protection
  - CSRF protection
- [ ] **Penetration Testing**
  - Test API authentication
  - Test rate limit bypass attempts
  - Test export data limits

---

## 🎯 CURRENT STATUS

### ✅ What's Working
1. **Authentication System**
   - User registration ✅
   - Login with JWT tokens ✅
   - Token refresh ✅
   - Database schema (users, api_keys tables) ✅

2. **API Key Generation**
   - Create keys via dashboard ✅
   - List user's keys ✅
   - Revoke keys ✅
   - Keys stored in PostgreSQL with bcrypt hashing ✅

3. **Search Functionality**
   - Hybrid search (vector + lexical) ✅
   - Advanced filters (8 new filters added) ✅
   - Pagination ✅
   - Export (CSV, NDJSON) ✅

4. **Frontend**
   - Search interface ✅
   - Results page ✅
   - Dashboard for key management ✅
   - API documentation with cURL generator ✅

### ❌ What's Broken
1. **API keys don't work** - Database keys not recognized by auth system
2. **Rate limiting ignores tiers** - Everyone gets same limits
3. **No Redis** - In-memory rate limiting won't work across multiple instances

### ⚠️ What's Missing
1. **1M profile dataset** - Still using 497K test dataset
2. **Production secrets management** - Using .env files
3. **Monitoring** - No error tracking
4. **Backups** - No automated backup strategy
5. **Load testing** - Unknown capacity

---

## 🔧 IMMEDIATE ACTION PLAN

### Step 1: Fix API Key System (1-2 hours)
**File to modify**: `backend/api/auth.py`

```python
async def resolve_auth_context(header_key: Optional[str]) -> AuthContext:
    """
    Resolve auth context from API key.
    Priority:
    1. Check database (user-generated keys)
    2. Fall back to env var (admin keys)
    """
    require = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"

    # Try database first
    if header_key:
        from backend.api.user_manager import APIKeyManager
        db_key_data = await APIKeyManager.validate_api_key(header_key)
        if db_key_data:
            return AuthContext(
                api_key=header_key,
                scopes=set(db_key_data['scopes']),
                tier=db_key_data['tier'],
                max_limit=_get_tier_limit(db_key_data['tier']),
                max_offset=int(os.getenv("MAX_OFFSET", "100000"))
            )

    # Fall back to env vars for admin keys
    # ... existing code ...
```

### Step 2: Implement Tier-Based Rate Limiting (30 min)
**File to modify**: `backend/api/app.py`

```python
TIER_RATE_LIMITS = {
    "public": {"search": 10, "export": 1},
    "basic": {"search": 200, "export": 6},
    "trusted": {"search": 1000, "export": 20}
}

# In search endpoint:
rate_limit = TIER_RATE_LIMITS[ctx.tier]["search"]
if not limiter.allow(rl_key, rate_limit, rate_limit * 2):  # burst = 2x
    raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({rate_limit}/min for {ctx.tier} tier)")
```

### Step 3: Test End-to-End (30 min)
1. Register user
2. Login
3. Create API key (public tier)
4. Make 11 search requests in 1 minute → Should be rate limited
5. Create API key (basic tier - requires manual upgrade in DB)
6. Make 201 search requests in 1 minute → Should be rate limited

---

## 📊 DEPLOYMENT TIMELINE ESTIMATE

| Phase | Duration | Blockers |
|-------|----------|----------|
| Fix API keys + Rate limiting | 3 hours | None |
| Extract 1M profiles | 2 hours | Need 51M dataset access |
| Generate 1M embeddings | 24 hours | OpenAI API costs (~$400) |
| Setup production infra | 4 hours | Need Railway/Render account |
| Security hardening | 4 hours | None |
| Testing & QA | 8 hours | Need QA plan |
| **TOTAL** | **~45 hours** | **+ 24h embedding generation** |

---

## 💰 ESTIMATED COSTS (Monthly)

### Infrastructure
- **Database**: Railway PostgreSQL ~$20/month (10GB)
- **Redis**: Upstash ~$10/month
- **Backend Hosting**: Railway ~$20/month
- **Frontend Hosting**: Vercel Free tier
- **Total**: ~$50/month

### API Costs (Ongoing)
- **OpenAI Embeddings** (if regenerating): ~$400 one-time for 1M profiles
- **Monitoring** (Sentry): Free tier (5K events/month)

---

## 🚀 GO/NO-GO DECISION CRITERIA

### ✅ Ready to Deploy When:
- [ ] All users can create and use API keys successfully
- [ ] Rate limiting enforces tier limits correctly
- [ ] 1M profiles loaded with embeddings
- [ ] Redis configured for rate limiting
- [ ] Production secrets in env vars
- [ ] CORS restricted to production domain
- [ ] Health checks passing
- [ ] Load test shows <1s response times for 95th percentile

### 🛑 DO NOT Deploy If:
- [ ] API keys still don't work
- [ ] Rate limiting not tier-based
- [ ] Using .env files instead of secrets manager
- [ ] CORS = "*" (open to all origins)
- [ ] No database backups configured
- [ ] No error monitoring

---

## 📝 NOTES

1. **Database Migration**: Current 497K profiles → 1M profiles
   - Keep existing data
   - Add 503K new profiles
   - Regenerate embeddings for new profiles only (incremental)

2. **Redis Strategy**:
   - Start with Upstash (serverless, pay-per-request)
   - Scale to dedicated Redis if needed
   - Alternative: Railway Redis addon

3. **Monitoring Priority**:
   - High: 429 rate limit errors (indicates tier issues)
   - High: 500 errors (backend failures)
   - Medium: Slow queries (>1s)
   - Low: 4xx client errors

---

**Last Updated**: 2025-10-22
**Status**: 🔴 NOT READY FOR PRODUCTION
**Blockers**: API key system, Rate limiting, 1M dataset
