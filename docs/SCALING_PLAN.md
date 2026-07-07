# INSIGHT - Scaling & Cloud Deployment Plan

**Goal:** Scale from 497K → 1M → 10M → 51M profiles with cloud deployment

This document outlines the strategy for importing more data and deploying to production.

---

## 📊 Current State Analysis

### **Local Machine Constraints**
```bash
# Check current disk usage
df -h

# Current PostgreSQL size
docker exec -it postgres psql -U postgres -d insight -c "
  SELECT pg_size_pretty(pg_database_size('insight')) AS database_size;
"
```

**Current Usage:**
- PostgreSQL DB: ~5 GB (497K profiles)
- Parquet files: ~2 GB
- Docker images: ~2 GB
- **Total: ~9 GB used of 42 GB available**

### **Storage Capacity Assessment**

| Data Size | Profiles | Est. DB Size | Local Feasible? | Recommended Approach |
|-----------|----------|--------------|-----------------|---------------------|
| 500K      | 497K     | 5 GB         | ✅ Yes         | **CURRENT** - Local |
| 1M        | 1M       | 10 GB        | ✅ Yes         | Local or Cloud      |
| 5M        | 5M       | 50 GB        | ⚠️ Tight      | **Cloud Required**  |
| 10M       | 10M      | 100 GB       | ❌ No          | Cloud Only          |
| 51M       | 51M      | 500 GB       | ❌ No          | Cloud Only          |

**Decision Point:** Move to cloud at 1M-2M profiles to ensure smooth scaling.

---

## 🎯 Scaling Strategy

### **Phase 1: Local Development (COMPLETE)** ✅
**Data:** 497K profiles
**Timeline:** Complete
**Cost:** $0

**Achievements:**
- PostgreSQL 17 with full-text search
- FastAPI backend with filters
- Web UI with 15 data columns
- CSV export functionality
- <1s query performance

---

### **Phase 2: Cloud Deployment + 1M Profiles** 🚀 NEXT

**Objective:** Deploy to cloud and scale to 1M profiles

#### **2.1 Cloud Platform Selection**

**Option A: Railway.app** ⭐ RECOMMENDED
- **Pros:**
  - One-command deployment
  - Managed PostgreSQL included
  - Auto-scaling
  - GitHub integration
  - $5/month trial credit
- **Cons:**
  - Limited free tier
  - Cost: ~$20-50/month for 1M profiles
- **Best for:** Quick MVP, testing, demo

**Option B: Render.com**
- **Pros:**
  - Generous free tier (PostgreSQL free up to 1GB)
  - Easy setup
  - Auto-deploy from Git
- **Cons:**
  - Free tier too small for 1M profiles
  - Cost: ~$7/month PostgreSQL + $7/month web service
- **Best for:** Starting small, then scaling

**Option C: Fly.io**
- **Pros:**
  - Edge deployment (fast globally)
  - PostgreSQL with replication
  - Good pricing
- **Cons:**
  - More complex setup
- **Best for:** Global deployment

**DECISION: Start with Railway for Phase 2**

#### **2.2 Data Import Strategy**

**Step 1: Prepare 1M Dataset**
```bash
# Extract next 500K profiles from S3 (to reach 1M total)
poetry run python3 scripts/prepare_1m_dataset.py
```

**Step 2: Cloud Database Setup**
```bash
# Option A: Railway CLI
railway add postgresql

# Get database URL
railway variables

# Set DATABASE_URL in .env
export DATABASE_URL="postgresql://user:pass@host:port/db"
```

**Step 3: Incremental Load** (prevents duplicates)
```bash
# Load additional 500K profiles incrementally
poetry run python3 backend/data_pipeline/ingestion/load_incremental.py \
  data/linkedin_profiles_500k_batch2.parquet
```

**Step 4: Verify Data**
```bash
# Check total count
curl https://your-app.railway.app/stats
```

#### **2.3 Deployment Steps (Railway)**

**A. Prepare for Deployment**
```bash
# 1. Create railway.json config
cat > railway.json <<EOF
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn backend.api.app:app --host 0.0.0.0 --port \$PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF

# 2. Create Procfile
echo "web: uvicorn backend.api.app:app --host 0.0.0.0 --port \$PORT" > Procfile
```

**B. Deploy Backend**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Add PostgreSQL
railway add postgresql

# Deploy
railway up

# Get deployed URL
railway status
```

**C. Configure Frontend**
```javascript
// Update frontend/search.js and frontend/results.js
const API_BASE_URL = 'https://your-app.railway.app';
```

**D. Deploy Frontend** (Options)
- **Option 1:** GitHub Pages (free, static hosting)
- **Option 2:** Netlify/Vercel (free tier, CI/CD)
- **Option 3:** Railway static site (paid)

#### **2.4 Cost Estimate (Phase 2)**

| Service | Tier | Cost/Month |
|---------|------|------------|
| Railway PostgreSQL | Starter (8GB RAM, 100GB) | $15-25 |
| Railway Web Service | Starter (1GB RAM) | $5-10 |
| Frontend (Netlify) | Free | $0 |
| **Total** | | **$20-35/month** |

---

### **Phase 3: Production Scale (10M+ Profiles)** 🏢

**Objective:** Enterprise-grade deployment for 10M-51M profiles

#### **3.1 Infrastructure: AWS**

**Architecture:**
```
┌─────────────────────┐
│  CloudFront (CDN)   │ ← Frontend static assets
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Route 53 (DNS)    │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Application Load   │
│  Balancer (ALB)     │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │   ECS/EKS   │ ← FastAPI containers (auto-scaling)
    │  (3+ tasks) │
    └──────┬──────┘
           │
    ┌──────▼──────────────┐
    │  ElastiCache Redis  │ ← Query caching (500ms → 50ms)
    └─────────────────────┘
           │
    ┌──────▼──────────────┐
    │  RDS PostgreSQL     │ ← 100GB+ SSD, read replicas
    │  (db.r6g.xlarge)    │
    └─────────────────────┘
           │
    ┌──────▼──────────────┐
    │  S3 Bucket          │ ← Parquet files (51M dataset)
    └─────────────────────┘
```

#### **3.2 Infrastructure as Code (Terraform)**

**Create `terraform/main.tf`:**
```hcl
# VPC
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "insight-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false
}

# RDS PostgreSQL
resource "aws_db_instance" "insight_db" {
  identifier = "insight-postgres"

  engine         = "postgres"
  engine_version = "17"
  instance_class = "db.r6g.xlarge"

  allocated_storage     = 200
  max_allocated_storage = 1000
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "insight"
  username = var.db_username
  password = var.db_password

  multi_az               = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name = "insight-postgres"
  }
}

# Read Replica for scaling
resource "aws_db_instance" "insight_db_replica" {
  identifier          = "insight-postgres-replica"
  replicate_source_db = aws_db_instance.insight_db.identifier
  instance_class      = "db.r6g.large"
  publicly_accessible = false

  tags = {
    Name = "insight-postgres-replica"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "insight_cache" {
  cluster_id           = "insight-cache"
  engine               = "redis"
  node_type            = "cache.r6g.large"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379

  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

# ECS Cluster
resource "aws_ecs_cluster" "insight" {
  name = "insight-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "insight_api" {
  family                   = "insight-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048"
  memory                   = "4096"

  container_definitions = jsonencode([{
    name      = "insight-api"
    image     = "${aws_ecr_repository.insight_api.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.insight_db.endpoint}/insight" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.insight_cache.cache_nodes[0].address}:6379" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/insight-api"
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# Auto Scaling
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.insight.name}/${aws_ecs_service.insight_api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_policy_cpu" {
  name               = "cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# S3 Bucket for Parquet files
resource "aws_s3_bucket" "insight_data" {
  bucket = "insight-linkedin-data-${var.environment}"

  tags = {
    Name = "insight-data"
  }
}

# CloudFront for frontend
resource "aws_cloudfront_distribution" "insight_frontend" {
  enabled             = true
  default_root_object = "index.html"

  origin {
    domain_name = aws_s3_bucket.insight_frontend.bucket_regional_domain_name
    origin_id   = "S3-insight-frontend"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-insight-frontend"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
```

#### **3.3 Data Migration Strategy (51M Profiles)**

**Challenge:** Cannot load 51M profiles on local machine

**Solution: Cloud-Native Loading**

**Step 1: Upload Parquet to S3**
```bash
# Use AWS CLI to upload 51M dataset
aws s3 cp s3://brighthire-linkedin-public-data/ \
          s3://insight-linkedin-data-prod/ \
          --recursive \
          --profile production
```

**Step 2: EC2 Data Loader**
```bash
# Launch EC2 instance for one-time data load
# Instance type: m5.2xlarge (8 vCPU, 32 GB RAM)

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip postgresql-client

# Clone repo
git clone https://github.com/yourusername/insight.git
cd insight

# Install Python dependencies
pip3 install poetry
poetry install

# Configure database connection
export DATABASE_URL="postgresql://user:pass@your-rds-endpoint.amazonaws.com/insight"

# Load data in batches (10M profiles per batch)
for i in {1..5}; do
  echo "Loading batch $i..."
  poetry run python3 backend/data_pipeline/ingestion/load_incremental.py \
    --s3-bucket insight-linkedin-data-prod \
    --s3-key batch_${i}.parquet \
    --batch-size 100000
done
```

**Step 3: Parallel Loading with EMR** (for 51M profiles)
```python
# Use AWS EMR (Spark) for parallel loading
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("InsightDataLoader") \
    .getOrCreate()

# Read Parquet from S3
df = spark.read.parquet("s3://insight-linkedin-data-prod/*.parquet")

# Write to PostgreSQL in parallel
df.write \
    .format("jdbc") \
    .option("url", "jdbc:postgresql://your-rds-endpoint/insight") \
    .option("dbtable", "profiles") \
    .option("user", "postgres") \
    .option("password", "password") \
    .option("batchsize", 10000) \
    .mode("append") \
    .save()
```

#### **3.4 Performance Optimizations**

**A. Redis Caching**
```python
# Add to backend/api/app.py
import redis
from functools import lru_cache

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    decode_responses=True
)

@app.post("/search")
async def search(request: SearchRequest):
    # Create cache key from request
    cache_key = f"search:{hash(str(request.dict()))}"

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Execute search
    results = await hybrid_search(conn, request)

    # Cache for 5 minutes
    redis_client.setex(cache_key, 300, json.dumps(results))

    return results
```

**B. Connection Pooling**
```python
# Already implemented in backend/api/database.py
# Pool size: 40 connections
# Good for 100-200 concurrent requests
```

**C. Database Indexes**
```sql
-- Already implemented in migrations/004_indexes.sql
CREATE INDEX idx_profiles_fulltext ON profiles
  USING GIN(to_tsvector('english', full_name || ' ' || headline || ' ' || summary));

CREATE INDEX idx_profiles_location_country ON profiles(location_country);
CREATE INDEX idx_profiles_industry ON profiles(industry);
CREATE INDEX idx_profiles_skills ON profiles USING GIN(skills);
```

#### **3.5 Monitoring & Observability**

**A. CloudWatch Dashboards**
- API latency (p50, p95, p99)
- Database CPU/memory usage
- Redis hit rate
- ECS task count
- RDS connections

**B. Alarms**
```yaml
# Example CloudWatch alarms
- API P95 latency > 1000ms
- Database CPU > 80%
- ECS healthy task count < 2
- RDS storage < 20%
```

**C. Application Logging**
```python
# Add structured logging
import structlog

logger = structlog.get_logger()

@app.post("/search")
async def search(request: SearchRequest):
    logger.info("search_request",
                query=request.query,
                filters=request.dict(exclude={"query"}))
    # ...
    logger.info("search_complete",
                results_count=len(results),
                query_time_ms=query_time)
```

#### **3.6 Cost Estimate (Phase 3 - 10M Profiles)**

| Service | Tier | Cost/Month |
|---------|------|------------|
| RDS PostgreSQL (db.r6g.xlarge) | 200GB, Multi-AZ | $450 |
| RDS Read Replica (db.r6g.large) | | $200 |
| ECS Fargate (2-10 tasks) | 2GB RAM each | $100-500 |
| ElastiCache Redis (r6g.large) | | $150 |
| Application Load Balancer | | $20 |
| CloudFront | 1TB transfer | $100 |
| S3 Storage | 100GB | $3 |
| Data Transfer | 1TB/month | $90 |
| **Total** | | **$1,113-1,513/month** |

**For 51M Profiles:** Add $500-800/month (larger RDS, more ECS tasks)

---

## 🚦 Decision Tree: When to Move to Cloud?

```
Current: 497K profiles locally
    │
    ├─ Want 1M profiles?
    │   ├─ YES → Railway ($20-35/month) ✅ RECOMMENDED
    │   └─ NO  → Stay local
    │
    ├─ Want 5M+ profiles?
    │   ├─ YES → AWS Phase 3 setup required
    │   └─ NO  → Railway is sufficient
    │
    └─ Want 10M-51M profiles?
        └─ YES → AWS with EMR, RDS, Redis, CDN
```

---

## 📋 Action Plan

### **Immediate Next Steps** (Phase 2)

1. **Choose Cloud Platform** (Railway recommended)
2. **Deploy to cloud with current 497K**
   ```bash
   railway init
   railway add postgresql
   railway up
   ```
3. **Test in production** with real users
4. **Load 1M profiles** incrementally
5. **Monitor costs** and performance
6. **Decision point:** Stay on Railway or migrate to AWS?

### **Prepare for Phase 3** (when ready for 10M+)

1. **Set up AWS account** and billing alerts
2. **Create Terraform configs** (provided above)
3. **Test EMR data loading** with sample data
4. **Implement caching layer** (Redis)
5. **Set up monitoring** (CloudWatch, alerts)
6. **Load data in batches** (1M → 5M → 10M → 51M)

---

## 💡 Key Takeaways

1. **Local is fine for 1M profiles** - You have 42GB available, only using 9GB
2. **Move to cloud at 1M-2M** - For reliability and scaling flexibility
3. **Railway for Phase 2** - Easiest deployment, good for 1M-5M profiles
4. **AWS for Phase 3** - Required for 10M+ profiles, enterprise features
5. **Incremental loading** - Already implemented, prevents duplicates
6. **Monitor costs** - Start small, scale based on actual usage

---

## 🔗 Resources

- [Railway Docs](https://docs.railway.app/)
- [AWS RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)

---

**Status:** Ready to deploy Phase 2 (Railway) or continue local with 1M profiles

**Recommendation:** Deploy to Railway now to test cloud infrastructure, then scale incrementally.
