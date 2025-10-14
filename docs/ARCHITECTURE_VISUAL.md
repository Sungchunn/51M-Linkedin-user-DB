# INSIGHT - Visual Architecture Design

**Last Updated:** October 12, 2025
**Status:** Migrating to Vue.js 3 Frontend
**Version:** v1.1.0 (Vue.js upgrade)

---

## 🎨 High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USERS / CLIENTS                            │
│  👨‍💼 GTM Teams  |  👨‍💻 Recruiters  |  👨‍🔬 Data Scientists  |  🤖 APIs  │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ↓ HTTPS
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │         Vue.js 3 Frontend (NEW)                          │    │
│   ├──────────────────────────────────────────────────────────┤    │
│   │  • Components: Search, Results, Filters, Export          │    │
│   │  • State: Pinia (store management)                       │    │
│   │  • Routing: Vue Router                                   │    │
│   │  • HTTP: Axios (API client)                              │    │
│   │  • UI: Tailwind CSS (utility-first)                      │    │
│   │  • Build: Vite (fast dev server)                         │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                     │
│   Deployment: Netlify / Vercel (CDN + Edge Functions)              │
│   Bundle Size: ~150 KB gzipped                                     │
│   Load Time: <1 second (first paint)                               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ↓ REST API (JSON)
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │         FastAPI Backend                                  │    │
│   ├──────────────────────────────────────────────────────────┤    │
│   │  Endpoints:                                              │    │
│   │    POST /api/v1/search       - Hybrid search            │    │
│   │    GET  /api/v1/stats        - Statistics               │    │
│   │    GET  /api/v1/filters      - Filter options           │    │
│   │    POST /api/v1/export       - Async CSV export         │    │
│   │    GET  /api/v1/health       - Health check             │    │
│   │                                                          │    │
│   │  Features:                                               │    │
│   │    • CORS configured for Vue.js origin                   │    │
│   │    • JWT auth (future)                                   │    │
│   │    • Rate limiting (Redis)                               │    │
│   │    • Request validation (Pydantic)                       │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                     │
│   Deployment: Railway / AWS ECS Fargate                            │
│   Instances: Auto-scaling (2-20 containers)                        │
│   Performance: 200-500 req/sec per instance                        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ↓ AsyncPG / Redis
┌─────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌───────────────────────────┐    ┌───────────────────────────┐  │
│   │   PostgreSQL 17           │    │   Redis 7 (Cache)         │  │
│   ├───────────────────────────┤    ├───────────────────────────┤  │
│   │  Tables:                  │    │  Use Cases:               │  │
│   │    • profiles (497K rows) │    │    • Query result cache   │  │
│   │    • companies            │    │    • Session store        │  │
│   │    • saved_searches       │    │    • Rate limit counter   │  │
│   │                           │    │    • Bloom filter (dedup) │  │
│   │  Indexes:                 │    │                           │  │
│   │    • GIN (full-text)      │    │  TTL: 5-60 minutes        │  │
│   │    • HNSW (vector)        │    │  Memory: 2-8 GB           │  │
│   │    • B-tree (filters)     │    │                           │  │
│   │                           │    │                           │  │
│   │  Size: 5-100 GB           │    │                           │  │
│   │  Connections: 20-50       │    │                           │  │
│   └───────────────────────────┘    └───────────────────────────┘  │
│                                                                     │
│   Deployment: Railway PostgreSQL / AWS RDS Multi-AZ                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Component Interaction Flow

### **User Search Flow**

```
┌──────────────┐
│   Browser    │
│  (Vue.js 3)  │
└──────┬───────┘
       │
       │ 1. User enters "senior software engineer"
       │    + filters (location, experience, skills)
       ↓
┌──────────────────────────────────────────────────────────────┐
│  SearchForm.vue Component                                    │
├──────────────────────────────────────────────────────────────┤
│  <template>                                                  │
│    <form @submit.prevent="handleSearch">                     │
│      <input v-model="query" placeholder="Search..." />       │
│      <FilterPanel :filters="filters" />                      │
│      <button type="submit">Search</button>                   │
│    </form>                                                   │
│  </template>                                                 │
│                                                              │
│  <script setup>                                              │
│  import { useSearchStore } from '@/stores/search'            │
│  const store = useSearchStore()                             │
│                                                              │
│  const handleSearch = async () => {                          │
│    await store.executeSearch(query, filters)                │
│    router.push('/results')                                  │
│  }                                                           │
│  </script>                                                   │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ 2. Pinia store dispatches API call
               ↓
┌──────────────────────────────────────────────────────────────┐
│  Pinia Store (stores/search.js)                              │
├──────────────────────────────────────────────────────────────┤
│  export const useSearchStore = defineStore('search', {       │
│    state: () => ({                                           │
│      query: '',                                              │
│      filters: {},                                            │
│      results: [],                                            │
│      totalCount: 0,                                          │
│      loading: false,                                         │
│      error: null                                             │
│    }),                                                       │
│                                                              │
│    actions: {                                                │
│      async executeSearch(query, filters) {                   │
│        this.loading = true                                   │
│        try {                                                 │
│          const response = await apiClient.post('/search', { │
│            query, ...filters                                 │
│          })                                                  │
│          this.results = response.data.results                │
│          this.totalCount = response.data.total_count         │
│        } catch (error) {                                     │
│          this.error = error.message                          │
│        } finally {                                           │
│          this.loading = false                                │
│        }                                                     │
│      }                                                       │
│    }                                                         │
│  })                                                          │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ 3. HTTP POST /api/v1/search
               ↓
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend (backend/api/app.py)                        │
├──────────────────────────────────────────────────────────────┤
│  @app.post("/api/v1/search")                                 │
│  async def search_profiles(                                  │
│      request: SearchRequest,                                 │
│      db: AsyncPGConnection = Depends(get_db)                 │
│  ):                                                          │
│      # Check Redis cache first                               │
│      cache_key = f"search:{hash(request)}"                   │
│      cached = await redis.get(cache_key)                     │
│      if cached:                                              │
│          return cached                                       │
│                                                              │
│      # Execute hybrid search                                 │
│      results, total = await hybrid_search(db, request)       │
│                                                              │
│      # Cache results (TTL: 5 min)                            │
│      await redis.setex(cache_key, 300, results)              │
│                                                              │
│      return SearchResponse(                                  │
│          results=results,                                    │
│          total_count=total,                                  │
│          query_time_ms=elapsed                               │
│      )                                                       │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ 4. Query PostgreSQL
               ↓
┌──────────────────────────────────────────────────────────────┐
│  PostgreSQL (profiles table)                                 │
├──────────────────────────────────────────────────────────────┤
│  WITH vector_results AS (                                    │
│    SELECT *, 1 - (embedding <=> $1) AS vector_similarity     │
│    FROM profiles                                             │
│    WHERE location_country = $2                               │
│      AND years_experience >= $3                              │
│    ORDER BY embedding <=> $1                                 │
│    LIMIT 500                                                 │
│  ),                                                          │
│  lexical_results AS (                                        │
│    SELECT *, ts_rank(...) AS lexical_rank                    │
│    FROM profiles                                             │
│    WHERE to_tsvector(...) @@ plainto_tsquery($4)             │
│  )                                                           │
│  SELECT * FROM vector_results v                              │
│  LEFT JOIN lexical_results l ON l.id = v.id                 │
│  ORDER BY (v.vector_similarity * 0.8 +                       │
│            l.lexical_rank * 0.2) DESC                        │
│  LIMIT 100;                                                  │
│                                                              │
│  Execution time: 200-800ms                                   │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ 5. Results returned to FastAPI
               ↓
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Response                                            │
├──────────────────────────────────────────────────────────────┤
│  {                                                           │
│    "results": [                                              │
│      {                                                       │
│        "id": "uuid",                                         │
│        "full_name": "John Doe",                              │
│        "job_title": "Senior Software Engineer",              │
│        "company_name": "Tech Corp",                          │
│        "location_country": "united states",                  │
│        "skills": ["python", "sql"],                          │
│        "score": 0.92,                                        │
│        "data_completeness_pct": 75                           │
│      },                                                      │
│      ...                                                     │
│    ],                                                        │
│    "total_count": 1250,                                      │
│    "returned_count": 100,                                    │
│    "query_time_ms": 345.2                                    │
│  }                                                           │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ 6. Response received by Pinia store
               ↓
┌──────────────────────────────────────────────────────────────┐
│  ResultsTable.vue Component                                  │
├──────────────────────────────────────────────────────────────┤
│  <template>                                                  │
│    <div v-if="store.loading">Loading...</div>                │
│    <div v-else-if="store.error">Error: {{ store.error }}</div>│
│    <div v-else>                                              │
│      <ResultsSummary :count="store.totalCount" />            │
│      <DataTable                                              │
│        :data="store.results"                                 │
│        :columns="columns"                                    │
│      />                                                      │
│      <Pagination                                             │
│        :total="store.totalCount"                             │
│        :page-size="100"                                      │
│      />                                                      │
│    </div>                                                    │
│  </template>                                                 │
│                                                              │
│  <script setup>                                              │
│  import { useSearchStore } from '@/stores/search'            │
│  const store = useSearchStore()                             │
│  </script>                                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎨 Vue.js 3 Frontend Architecture

### **Project Structure**

```
frontend/
├── public/
│   ├── favicon.ico
│   └── index.html
│
├── src/
│   ├── main.js                 # App entry point
│   ├── App.vue                 # Root component
│   │
│   ├── router/
│   │   └── index.js            # Vue Router config
│   │       Routes:
│   │         / → SearchView
│   │         /results → ResultsView
│   │         /saved → SavedSearchesView
│   │
│   ├── stores/                 # Pinia state management
│   │   ├── search.js           # Search state & actions
│   │   ├── filters.js          # Filter options
│   │   └── user.js             # User preferences (future auth)
│   │
│   ├── views/                  # Page components
│   │   ├── SearchView.vue      # Search page
│   │   ├── ResultsView.vue     # Results page
│   │   └── SavedSearchesView.vue
│   │
│   ├── components/             # Reusable components
│   │   ├── search/
│   │   │   ├── SearchForm.vue
│   │   │   ├── FilterPanel.vue
│   │   │   ├── LocationFilter.vue
│   │   │   ├── ExperienceFilter.vue
│   │   │   └── SkillsFilter.vue
│   │   │
│   │   ├── results/
│   │   │   ├── ResultsTable.vue
│   │   │   ├── ResultsCard.vue
│   │   │   ├── ResultsSummary.vue
│   │   │   ├── Pagination.vue
│   │   │   └── ExportButton.vue
│   │   │
│   │   └── shared/
│   │       ├── LoadingSpinner.vue
│   │       ├── ErrorMessage.vue
│   │       └── EmptyState.vue
│   │
│   ├── composables/            # Reusable logic (Vue 3 Composition API)
│   │   ├── useSearch.js        # Search logic
│   │   ├── useFilters.js       # Filter management
│   │   ├── usePagination.js    # Pagination logic
│   │   └── useExport.js        # CSV export logic
│   │
│   ├── services/               # API clients
│   │   ├── api.js              # Axios instance + interceptors
│   │   ├── searchService.js    # Search API calls
│   │   └── statsService.js     # Stats API calls
│   │
│   ├── utils/                  # Helper functions
│   │   ├── formatters.js       # Date, number formatting
│   │   ├── validators.js       # Input validation
│   │   └── csvExport.js        # CSV generation
│   │
│   └── assets/                 # Static assets
│       ├── styles/
│       │   ├── main.css        # Tailwind imports
│       │   └── custom.css      # Custom styles
│       └── images/
│
├── package.json                # Dependencies
├── vite.config.js              # Vite build config
├── tailwind.config.js          # Tailwind CSS config
└── tsconfig.json               # TypeScript config (optional)
```

---

## 📦 Vue.js 3 Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Stack                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Core Framework:                                            │
│    • Vue.js 3.3+              - Composition API, <script setup> │
│    • Vue Router 4             - Client-side routing         │
│    • Pinia 2                  - State management            │
│                                                             │
│  HTTP Client:                                               │
│    • Axios 1.6+               - API calls with interceptors │
│                                                             │
│  UI Framework:                                              │
│    • Tailwind CSS 3           - Utility-first CSS           │
│    • Heroicons                - Icon library                │
│                                                             │
│  Build Tool:                                                │
│    • Vite 5                   - Fast dev server + HMR       │
│                                                             │
│  Optional Enhancements:                                     │
│    • TypeScript               - Type safety (optional)      │
│    • VueUse                   - Composition utilities       │
│    • Chart.js + vue-chartjs   - Data visualization          │
│                                                             │
│  Bundle Size: ~150 KB gzipped (production)                  │
│  Build Time: <10 seconds                                    │
└─────────────────────────────────────────────────────────────┘
```

### **package.json**

```json
{
  "name": "insight-frontend",
  "version": "1.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.3.8",
    "vue-router": "^4.2.5",
    "pinia": "^2.1.7",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.5.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.3.5",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.31"
  }
}
```

---

## 🔄 Data Flow Architecture

### **State Management (Pinia)**

```
┌─────────────────────────────────────────────────────────────┐
│                    Pinia Store Architecture                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  stores/search.js                                            │
├──────────────────────────────────────────────────────────────┤
│  state:                                                      │
│    • query: string                                           │
│    • filters: FilterState                                    │
│    • results: ProfileResult[]                                │
│    • totalCount: number                                      │
│    • pagination: { limit, offset }                           │
│    • loading: boolean                                        │
│    • error: string | null                                    │
│                                                              │
│  getters:                                                    │
│    • filteredResults - Apply client-side filters             │
│    • hasResults - Check if results exist                     │
│    • currentPage - Calculate page number                     │
│                                                              │
│  actions:                                                    │
│    • executeSearch(query, filters)                           │
│    • loadMore()                                              │
│    • clearResults()                                          │
│    • exportToCSV()                                           │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  stores/filters.js                                           │
├──────────────────────────────────────────────────────────────┤
│  state:                                                      │
│    • countries: string[]                                     │
│    • industries: string[]                                    │
│    • skillsOptions: string[]                                 │
│                                                              │
│  actions:                                                    │
│    • loadFilterOptions()                                     │
│    • resetFilters()                                          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  stores/user.js (Future)                                     │
├──────────────────────────────────────────────────────────────┤
│  state:                                                      │
│    • isAuthenticated: boolean                                │
│    • token: string | null                                    │
│    • savedSearches: SavedSearch[]                            │
│                                                              │
│  actions:                                                    │
│    • login(email, password)                                  │
│    • logout()                                                │
│    • saveSearch(name, params)                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎨 Component Hierarchy

```
App.vue
│
├─ NavBar.vue
│  ├─ Logo
│  ├─ Navigation Links
│  └─ User Menu (future auth)
│
├─ Router View
│  │
│  ├─ SearchView.vue
│  │  │
│  │  ├─ SearchForm.vue
│  │  │  ├─ Input (keyword)
│  │  │  └─ FilterPanel.vue
│  │  │     ├─ LocationFilter.vue
│  │  │     │  ├─ CountrySelect
│  │  │     │  ├─ RegionSelect
│  │  │     │  └─ CitySelect
│  │  │     │
│  │  │     ├─ ExperienceFilter.vue
│  │  │     │  ├─ MinYears
│  │  │     │  └─ MaxYears
│  │  │     │
│  │  │     ├─ IndustryFilter.vue
│  │  │     │  └─ IndustrySelect
│  │  │     │
│  │  │     ├─ SkillsFilter.vue
│  │  │     │  └─ SkillsInput (tags)
│  │  │     │
│  │  │     └─ DataCompletenessFilter.vue ⭐ NEW
│  │  │        └─ Slider (0-100%)
│  │  │
│  │  └─ StatsSection.vue
│  │     ├─ TotalProfiles
│  │     ├─ TopCountries
│  │     └─ TopIndustries
│  │
│  ├─ ResultsView.vue
│  │  │
│  │  ├─ ResultsSummary.vue
│  │  │  ├─ ResultCount
│  │  │  ├─ QueryTime
│  │  │  └─ AppliedFilters
│  │  │
│  │  ├─ ResultsActions.vue
│  │  │  ├─ ExportButton
│  │  │  ├─ SaveSearchButton
│  │  │  └─ ViewToggle (table/cards)
│  │  │
│  │  ├─ ResultsTable.vue (default view)
│  │  │  ├─ TableHeader (sortable)
│  │  │  ├─ TableRow (v-for results)
│  │  │  │  └─ ProfileCell
│  │  │  └─ TableFooter
│  │  │
│  │  ├─ ResultsCards.vue (alternate view)
│  │  │  └─ ProfileCard (v-for results)
│  │  │
│  │  └─ Pagination.vue
│  │     ├─ PrevButton
│  │     ├─ PageInfo
│  │     ├─ NextButton
│  │     └─ PageSizeSelect
│  │
│  └─ SavedSearchesView.vue (future)
│     ├─ SavedSearchList
│     └─ SavedSearchCard
│
└─ Footer.vue
```

---

## 🚀 Deployment Architecture (With Vue.js)

### **Development Environment**

```
┌────────────────────────────────────────────────────────────┐
│               Local Development                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Frontend (Vite Dev Server)                                │
│    • URL: http://localhost:5173                            │
│    • Hot Module Replacement (HMR)                          │
│    • Proxy: /api → http://localhost:8000                   │
│                                                            │
│  Backend (FastAPI)                                         │
│    • URL: http://localhost:8000                            │
│    • Auto-reload on code changes                           │
│    • Swagger docs: /docs                                   │
│                                                            │
│  Database (PostgreSQL)                                     │
│    • URL: localhost:5432                                   │
│    • Docker container                                      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### **Production Deployment**

```
┌─────────────────────────────────────────────────────────────┐
│                   Cloudflare / CDN                          │
│  Global Edge Network (200+ locations)                       │
│    • Cache static assets (Vue.js bundle)                    │
│    • DDoS protection                                        │
│    • SSL/TLS termination                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴────────────┐
         │                        │
         ↓                        ↓
┌─────────────────┐      ┌─────────────────┐
│  Netlify/Vercel │      │   API Gateway   │
│  (Vue.js SPA)   │      │  (AWS/Railway)  │
├─────────────────┤      ├─────────────────┤
│  • SSG/SPA      │      │  • Rate limiting│
│  • Edge         │      │  • Auth check   │
│  • A/B testing  │      │  • Logging      │
└─────────────────┘      └────────┬────────┘
                                  │
                         ┌────────┴────────┐
                         │                 │
                         ↓                 ↓
              ┌──────────────────┐  ┌──────────────┐
              │  FastAPI (ECS)   │  │  Redis       │
              │  Auto-scaling    │←─│  ElastiCache │
              │  2-20 instances  │  │              │
              └────────┬─────────┘  └──────────────┘
                       │
                       ↓
              ┌──────────────────┐
              │  PostgreSQL RDS  │
              │  Multi-AZ        │
              │  + Read Replica  │
              └──────────────────┘
```

---

## 🔧 Vue.js Migration Plan

### **Phase 1: Setup & Structure** (Week 1)

```bash
# 1. Initialize Vue.js project with Vite
npm create vue@latest insight-frontend
cd insight-frontend

# 2. Install dependencies
npm install vue-router pinia axios
npm install -D tailwindcss postcss autoprefixer

# 3. Initialize Tailwind
npx tailwindcss init -p

# 4. Project structure
mkdir -p src/{views,components,stores,services,composables,utils}
```

### **Phase 2: Core Components** (Week 2)
- ✅ Convert SearchForm (index.html → SearchView.vue)
- ✅ Convert ResultsTable (results.html → ResultsView.vue)
- ✅ Create Pinia stores (search, filters)
- ✅ Set up Vue Router
- ✅ Configure Axios client

### **Phase 3: Enhanced Features** (Week 3)
- ✅ Add data completeness filter
- ✅ Add saved searches
- ✅ Add export functionality
- ✅ Add loading states & animations
- ✅ Add error handling

### **Phase 4: Polish & Deploy** (Week 4)
- ✅ Tailwind styling (match current design)
- ✅ Responsive design
- ✅ Performance optimization
- ✅ Deploy to Netlify

---

**Want me to start the Vue.js migration?** I can:

1. Generate the complete Vue.js project structure
2. Create initial components (SearchView, ResultsView)
3. Set up Pinia stores for state management
4. Configure Axios for API calls
5. Add Tailwind CSS styling

Let me know if you want to proceed! 🚀
