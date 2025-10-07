.PHONY: help up down restart logs db/init db/migrate db/status db/vacuum embed/openai embed/mps embed/status promote/calculate promote/run api/start api/test stats/size clean

# Default target
help:
	@echo "INSIGHT - Makefile Commands"
	@echo ""
	@echo "Docker:"
	@echo "  make up              Start all services (Postgres, Redis)"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make logs            Tail service logs"
	@echo ""
	@echo "Database:"
	@echo "  make db/init         Initialize database (extensions, schema, indexes)"
	@echo "  make db/migrate      Migrate existing 10M profiles to new schema"
	@echo "  make db/status       Show database stats"
	@echo "  make db/vacuum       Run VACUUM ANALYZE"
	@echo ""
	@echo "Embeddings:"
	@echo "  make embed/openai    Generate embeddings via OpenAI API"
	@echo "  make embed/mps       Generate embeddings locally on MPS (Apple Silicon)"
	@echo "  make embed/status    Check embedding progress"
	@echo ""
	@echo "Jobs:"
	@echo "  make promote/calculate  Calculate hotness scores"
	@echo "  make promote/run        Promote top 5M profiles to hot"
	@echo ""
	@echo "API:"
	@echo "  make api/start       Start FastAPI server"
	@echo "  make api/test        Test API endpoints"
	@echo ""
	@echo "Utilities:"
	@echo "  make stats/size      Show table sizes"
	@echo "  make clean           Clean logs and temp files"

# Docker commands
up:
	docker-compose up -d
	@echo "✅ Services started"
	@echo "   Postgres: localhost:5432"
	@echo "   Redis: localhost:6379"
	@echo "   Pgweb: http://localhost:8081"

down:
	docker-compose down
	@echo "✅ Services stopped"

restart:
	docker-compose restart
	@echo "✅ Services restarted"

logs:
	docker-compose logs -f

# Database commands
db/init:
	@echo "🔧 Initializing database..."
	docker-compose exec postgres psql -U postgres -d profiles -f /sql/01_extensions.sql
	docker-compose exec postgres psql -U postgres -d profiles -f /sql/02_schema.sql
	docker-compose exec postgres psql -U postgres -d profiles -f /sql/03_indexes.sql
	@echo "✅ Database initialized"

db/migrate:
	@echo "🔄 Migrating existing profiles to new schema..."
	@echo "⚠️  This will take 10-30 minutes for 10M profiles"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose exec postgres psql -U postgres -d profiles -f /sql/04_migration_from_existing.sql
	@echo "✅ Migration complete"

db/status:
	@echo "📊 Database Statistics"
	docker-compose exec postgres psql -U postgres -d profiles -c "\
		SELECT \
			'profiles_hot' as table, \
			COUNT(*) FILTER (WHERE is_deleted = FALSE) as active, \
			COUNT(*) as total, \
			COUNT(embedding) FILTER (WHERE is_deleted = FALSE) as with_embeddings, \
			ROUND(AVG(quality_score)::numeric, 2) as avg_quality \
		FROM profiles_hot \
		UNION ALL \
		SELECT \
			'profiles_detail' as table, \
			COUNT(*) as active, \
			COUNT(*) as total, \
			NULL as with_embeddings, \
			NULL as avg_quality \
		FROM profiles_detail;"

db/vacuum:
	@echo "🧹 Running VACUUM ANALYZE..."
	docker-compose exec postgres psql -U postgres -d profiles -c "VACUUM ANALYZE profiles_hot;"
	docker-compose exec postgres psql -U postgres -d profiles -c "VACUUM ANALYZE profiles_detail;"
	@echo "✅ Vacuum complete"

# Embedding commands
embed/openai:
	@echo "🔮 Generating embeddings via OpenAI API..."
	@echo "⚠️  Estimated cost for 5M profiles: ~$200"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	python embeddings/batch_embed.py "batch_$(shell date +%Y%m%d)" --backend openai

embed/mps:
	@echo "🔮 Generating embeddings locally on MPS..."
	python embeddings/batch_embed.py "batch_$(shell date +%Y%m%d)" --backend mps

embed/status:
	@echo "📊 Embedding Progress"
	docker-compose exec postgres psql -U postgres -d profiles -c "\
		SELECT \
			batch_name, \
			rows_processed, \
			rows_embedded, \
			rows_skipped, \
			started_at, \
			completed_at \
		FROM embedding_checkpoint \
		ORDER BY started_at DESC \
		LIMIT 5;"

# Job commands
promote/calculate:
	@echo "🔢 Calculating hotness scores..."
	python jobs/promote_hot.py calculate

promote/run:
	@echo "⭐ Promoting top 5M profiles to hot..."
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	python jobs/promote_hot.py promote --target 5000000 --min-quality 0.5

# API commands
api/start:
	@echo "🚀 Starting FastAPI server..."
	uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

api/test:
	@echo "🧪 Testing API endpoints..."
	curl -s http://localhost:8000/ | jq
	@echo ""
	curl -s http://localhost:8000/health | jq

# Utility commands
stats/size:
	@echo "📊 Table Sizes"
	docker-compose exec postgres psql -U postgres -d profiles -c "\
		SELECT \
			schemaname, \
			tablename, \
			pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size, \
			pg_total_relation_size(schemaname||'.'||tablename) AS bytes \
		FROM pg_tables \
		WHERE schemaname = 'public' \
		ORDER BY bytes DESC;"

clean:
	@echo "🧹 Cleaning temp files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete
	@echo "✅ Cleaned"
