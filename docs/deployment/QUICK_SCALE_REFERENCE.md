# PROSPECTIQ - Quick Scaling Reference

**TL;DR**: Start with 1M profiles ($115/mo), scale to 10M when needed ($380/mo)

---

## 🚀 3-Step Quick Start (Deploy 1M Today)

### 1. Extract 1M Best Profiles (10 minutes)
```bash
# Run locally
poetry run python scripts/prepare_best_1m_dataset.py

# Output: data/USA_1M_best.parquet (~500MB)
```

### 2. Deploy to Render (5 minutes)
1. Push to GitHub: `git push origin main`
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your GitHub repo
4. Add environment variables (see below)
5. Click "Create Web Service"

**Environment Variables:**
```bash
OPENAI_API_KEY=sk-your-key
JWT_SECRET_KEY=<paste: openssl rand -hex 32>
ADMIN_PASSWORD=SecurePass2025!
ENVIRONMENT=production
CORS_ORIGINS=https://your-app.onrender.com
```

### 3. Load Data (15 minutes)
```bash
# In Render Shell (Dashboard → Shell)
# Upload USA_1M_best.parquet first via Render Dashboard

poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_best.parquet
```

**Done! 🎉** Your app is live at `https://your-app.onrender.com`

---

## 📊 Scaling Tiers Quick Comparison

| Tier | Profiles | Cost/mo | Use Case | Query Time | Setup Time |
|------|----------|---------|----------|------------|------------|
| **MVP** | 1M | $115 | Launch, validate | 600ms | 30 min |
| **Growth** ⭐ | 10M | $380 | Production | 1000ms | 2 hours |
| **Enterprise** | 51M | $825 | Large contracts | 1500ms | 1 day |

---

## 💰 Monthly Cost Breakdown

### Tier 1: MVP (1M Profiles) - $115/month
```
✅ Render Standard Plus DB:  $90/mo  (4 GB RAM, 512 GB storage)
✅ Render Standard Web:       $25/mo  (2 GB RAM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TOTAL:                    $115/mo
```

### Tier 2: Growth (10M Profiles) - $380/month ⭐ Recommended
```
✅ Render Pro DB:            $200/mo  (8 GB RAM, 1 TB storage)
✅ Render Pro Web x2:        $170/mo  (4 GB RAM each)
✅ Redis Cache:               $10/mo  (256 MB)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TOTAL:                    $380/mo
```

### Tier 3: Enterprise (51M Profiles) - $825/month
```
✅ AWS RDS PostgreSQL:       $480/mo  (db.r6g.2xlarge, 64 GB RAM)
✅ AWS ECS Fargate x4:       $120/mo  (4 containers)
✅ ElastiCache Redis:        $150/mo  (cache.r6g.large)
✅ Load Balancer + CDN:       $75/mo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TOTAL:                    $825/mo
```

---

## 🛠️ Data Extraction Commands

### Extract 1M Best Profiles
```bash
poetry run python scripts/prepare_best_1m_dataset.py

# Output: data/USA_1M_best.parquet (500 MB)
# Time: 5-10 minutes
# Selection: Top 1M by quality_score
```

### Extract 10M Best Profiles
```bash
poetry run python scripts/prepare_best_10m_dataset.py

# Output: data/USA_10M_best.parquet (5 GB)
# Time: 10-15 minutes
# Selection: Top 10M by quality_score
```

### Check Data Quality
```bash
poetry run python scripts/check_data_quality.py

# Shows:
# - Profile count
# - Quality score distribution
# - Data completeness %
# - Industry breakdown
```

---

## 📦 Render Configuration by Tier

### MVP (1M Profiles)

**Database**: Standard Plus
- RAM: 4 GB
- Storage: 512 GB
- Price: $90/mo

**Web Service**: Standard
- RAM: 2 GB
- Instances: 1
- Price: $25/mo

### Growth (10M Profiles) ⭐

**Database**: Pro
- RAM: 8 GB
- Storage: 1 TB
- Price: $200/mo

**Web Service**: Pro
- RAM: 4 GB
- Instances: 2
- Price: $85/mo each = $170/mo

**Redis**: Standard
- RAM: 256 MB
- Price: $10/mo

---

## 📈 Performance Optimizations

### After Loading 10M+ Profiles

Run performance optimization migration:
```bash
psql $DATABASE_URL < migrations/009_performance_optimizations_10m.sql
```

This adds:
- ✅ Composite indexes for common queries
- ✅ Partial indexes for high-quality profiles
- ✅ Materialized views for popular searches
- ✅ GIN indexes for array/text searches
- ✅ Monitoring views

### Monitor Performance
```sql
-- Check index usage
SELECT * FROM v_index_usage;

-- Check table size
SELECT * FROM v_table_bloat;

-- Get region stats
SELECT * FROM get_region_stats();
```

---

## 🔄 Scaling Path

### Week 1: Deploy MVP (1M)
```bash
1. Extract 1M: poetry run python scripts/prepare_best_1m_dataset.py
2. Deploy to Render with Standard Plus DB ($115/mo)
3. Load data
4. Test and validate
```

### Month 3: Scale to Growth (10M)
```bash
1. Extract 10M: poetry run python scripts/prepare_best_10m_dataset.py
2. Upgrade Render DB to Pro ($200/mo)
3. Add second web instance ($85/mo)
4. Add Redis ($10/mo)
5. Load data
6. Run optimization migration
```

### Year 1+: Enterprise (51M)
```bash
1. Evaluate AWS vs Render Enterprise
2. Plan migration if going AWS
3. Load full dataset
4. Implement partitioning
5. Add monitoring and alerting
```

---

## ⚡ Performance Expectations

### 1M Profiles (MVP)
- Query time: 600-1200ms
- Concurrent users: 50-100
- Database size: ~2 GB
- Memory usage: ~1.5 GB

### 10M Profiles (Growth)
- Query time: 800-1500ms
- Concurrent users: 200-500
- Database size: ~120 GB
- Memory usage: ~4-6 GB

### 51M Profiles (Enterprise)
- Query time: 1000-2000ms
- Concurrent users: 1000+
- Database size: ~400 GB
- Memory usage: ~16-32 GB

---

## 🎯 My Recommendation

**For Most Users**: Start with 1M, scale to 10M

**Why?**
- ✅ 1M is enough to validate product-market fit
- ✅ 10M covers 99% of US professional market needs
- ✅ Much cheaper than 51M ($380 vs $825/mo)
- ✅ Better performance (faster queries)
- ✅ Easier to manage
- ✅ Can always add more later

**When to use 51M?**
- 💼 Large enterprise contracts requiring full coverage
- 💰 Revenue > $10K/month justifies cost
- 📊 Specific use cases needing long-tail profiles

---

## 🔗 Documentation Links

- **Full Scaling Guide**: `SCALING_TO_51M_GUIDE.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Deployment Readiness**: `DEPLOYMENT_READINESS_REPORT.md`

---

## ❓ Quick FAQ

**Q: Can I start free?**
A: Render has a free tier, but it's too limited for production. Start with $115/mo 1M tier.

**Q: How long to deploy?**
A: 30 minutes for 1M profiles (mostly data loading time)

**Q: Can I switch later?**
A: Yes! Easy to upgrade Render plans. Just load more data.

**Q: What about embeddings?**
A: Optional. Costs ~$10-20 in OpenAI credits per 1M profiles. Can skip for MVP.

**Q: GitHub auto-deploy working?**
A: Yes! Render detects `render.yaml` and auto-deploys on git push.

---

**Ready to Deploy?**

```bash
# 1. Extract data
poetry run python scripts/prepare_best_1m_dataset.py

# 2. Commit and push
git add scripts/ SCALING_TO_51M_GUIDE.md
git commit -m "feat: add scaling infrastructure for 1M-51M profiles"
git push origin main

# 3. Deploy on Render
# Go to render.com → New → Blueprint → Connect GitHub
```

**Status**: 🚀 Ready to scale from 1M → 10M → 51M!
