# INSIGHT Documentation

Welcome to the INSIGHT Semantic Talent Finder documentation. This directory contains all project documentation organized by topic.

## 📖 Documentation Index

### Planning & Architecture

- **[claude.md](./claude.md)** ⚠️ LOCAL ONLY - DO NOT COMMIT
  - Project context for AI assistance
  - Git workflow policies
  - Negative spaces philosophy summary
  - Code organization rules

- **[PROJECT_PHASES.md](./PROJECT_PHASES.md)**
  - Complete 6-phase breakdown
  - Detailed test cases for each phase
  - Success criteria and deliverables
  - Timeline estimates

### Programming Philosophy

- **[NEGATIVE_SPACES_GUIDE.md](./NEGATIVE_SPACES_GUIDE.md)**
  - Core philosophy explained
  - 10 Commandments of Negative Spaces
  - Practical examples for this project
  - Anti-patterns to avoid
  - Implementation checklist

### Database Design

- **[SCHEMA_REPORT.md](./SCHEMA_REPORT.md)** (To be created in Phase 1)
  - Entity-Relationship diagrams
  - Table definitions with rationale
  - Normalization strategy
  - Field mapping (staging → core)
  - Data type decisions

- **[INDEX_REPORT.md](./INDEX_REPORT.md)** (To be created in Phase 1)
  - Index definitions and purposes
  - HNSW parameters for vector search
  - GIN indexes for arrays and FTS
  - B-tree indexes for filters
  - Performance analysis

### API Documentation

- **[API_REFERENCE.md](./API_REFERENCE.md)** (To be created in Phase 4)
  - Endpoint specifications
  - Request/response schemas
  - Authentication
  - Rate limiting
  - Error codes

### Operations

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** (To be created in Phase 6)
  - Production deployment guide
  - Docker Compose production setup
  - Environment configuration
  - SSL/TLS setup
  - Monitoring and logging

- **[PERFORMANCE_TUNING.md](./PERFORMANCE_TUNING.md)** (To be created in Phase 6)
  - Query optimization tips
  - Index tuning
  - Connection pool sizing
  - Cache configuration
  - Troubleshooting slow queries

## 📋 Quick Navigation

### I'm new to the project
Start here:
1. [../README.md](../README.md) - Project overview and quick start
2. [PROJECT_PHASES.md](./PROJECT_PHASES.md) - Understand the roadmap
3. [NEGATIVE_SPACES_GUIDE.md](./NEGATIVE_SPACES_GUIDE.md) - Learn the coding philosophy

### I'm implementing a feature
Check:
1. [PROJECT_PHASES.md](./PROJECT_PHASES.md) - Find your phase and test cases
2. [NEGATIVE_SPACES_GUIDE.md](./NEGATIVE_SPACES_GUIDE.md) - Follow the patterns
3. [SCHEMA_REPORT.md](./SCHEMA_REPORT.md) - Understand data model

### I'm debugging an issue
Look at:
1. [NEGATIVE_SPACES_GUIDE.md](./NEGATIVE_SPACES_GUIDE.md) - Debugging with negative spaces
2. [PERFORMANCE_TUNING.md](./PERFORMANCE_TUNING.md) - Performance issues
3. [API_REFERENCE.md](./API_REFERENCE.md) - API errors

### I'm deploying to production
Follow:
1. [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment guide
2. [PERFORMANCE_TUNING.md](./PERFORMANCE_TUNING.md) - Optimization
3. [../README.md](../README.md) - Configuration reference

## 🎯 Documentation Standards

### Format
- All docs use Markdown
- Code blocks specify language for syntax highlighting
- Links use relative paths
- Tables for structured data
- Emojis for visual organization (sparingly)

### Structure
Each document should have:
- Clear title and purpose
- Table of contents (if >500 lines)
- Examples with context
- "Why" not just "what"
- Last updated date

### Code Examples
```python
# Good example: Includes context and negative space
def quality_score(row: dict) -> float:
    """
    Calculate quality score.
    NEGATIVE SPACE: Result must be [0.0, 1.0]
    """
    # ... implementation
    if not (0.0 <= score <= 1.0):
        raise AssertionError(f"INVARIANT VIOLATION: score={score}")
    return score
```

### Updates
- Update "Last Updated" date when modifying
- Reference related docs with links
- Mark sections as "(To be created)" if planned but not yet written

## 🔐 Security Notes

### Do NOT Commit
- `claude.md` - Contains AI context (in .gitignore)
- Any files with credentials or API keys
- Database connection strings
- Personal information

### Safe to Commit
- All other documentation
- Example configurations (without secrets)
- Schema definitions
- API specifications

## 📚 External Resources

### Technologies
- [PostgreSQL 17 Docs](https://www.postgresql.org/docs/17/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [asyncpg Docs](https://magicstack.github.io/asyncpg/)
- [Pydantic Docs](https://docs.pydantic.dev/)

### Best Practices
- [The Twelve-Factor App](https://12factor.net/)
- [REST API Best Practices](https://restfulapi.net/)
- [PostgreSQL Performance](https://www.postgresql.org/docs/current/performance-tips.html)

## ✅ Documentation Checklist

Use this checklist when creating new documentation:

- [ ] Clear title and purpose statement
- [ ] Target audience identified
- [ ] Examples included
- [ ] Code snippets tested
- [ ] Links verified (no 404s)
- [ ] "Last Updated" date added
- [ ] Cross-references to related docs
- [ ] Follows Negative Spaces philosophy (where applicable)
- [ ] Reviewed for clarity
- [ ] No sensitive information

## 🤝 Contributing to Docs

### Process
1. Create/update doc following standards above
2. Test all code examples
3. Verify all links
4. Update this index if adding new doc
5. Commit with clear message

### Commit Messages
```bash
# Good
git commit -m "docs: add schema report with ER diagrams"
git commit -m "docs: update API reference with new endpoints"

# Bad
git commit -m "updated docs"
git commit -m "stuff"
```

---

**Last Updated**: 2025-10-07
**Status**: Documentation structure established
**Next**: Complete Phase 1 docs (SCHEMA_REPORT.md, INDEX_REPORT.md)
