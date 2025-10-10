# INSIGHT - Frontend

Clean, modern web interface for browsing 51M+ LinkedIn profiles using DuckDB + S3.

## Features

✅ **Zero Local Storage** - Queries S3 directly via DuckDB
✅ **Fast Keyword Search** - Search across all text fields
✅ **Advanced Filters** - Country, industry, experience, skills
✅ **Responsive Design** - Works on desktop and mobile
✅ **Browser Navigation** - Full support for back button
✅ **Pagination** - Browse results in pages

## Quick Start

### 1. Start the API Server

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication"
./start_duckdb_api.sh
```

The API will start at `http://localhost:8000`

### 2. Open Frontend

Open `frontend/index.html` in your browser:

**Option A: File Protocol (Simple)**
```bash
open frontend/index.html
```

**Option B: Local Server (Recommended)**
```bash
cd frontend
python3 -m http.server 3000
```

Then visit: `http://localhost:3000`

## Pages

### Search Page (`index.html`)
- Keyword search across all fields
- Filter dropdowns (auto-populated from dataset)
- Experience range filters
- Skills filter
- Dataset statistics

### Results Page (`results.html`)
- Scrollable results table
- Shows 50 results per page
- Pagination controls
- Query time display
- Active filters display
- Browser back button returns to search

## Architecture

```
Frontend (Static HTML/CSS/JS)
    ↓
API (FastAPI @ localhost:8000)
    ↓
DuckDB (In-Memory)
    ↓
S3 Parquet File (51M profiles)
```

## Files

- `index.html` - Search page
- `results.html` - Results page
- `styles.css` - Clean, modern styling
- `search.js` - Search page logic
- `results.js` - Results page logic

## API Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /search` | Execute search with filters |
| `GET /stats` | Get dataset statistics |
| `GET /countries` | Get list of countries |
| `GET /industries` | Get list of industries |
| `GET /health` | Check API health |

## Customization

### Change Results Per Page
Edit `search.js`:
```javascript
params.limit = 100; // Default is 50
```

### Change API URL
Edit both `search.js` and `results.js`:
```javascript
const API_BASE_URL = 'http://your-api-url:8000';
```

### Styling
All styles in `styles.css` use CSS variables for easy theming:
```css
:root {
    --primary-color: #2563eb;
    --background: #f8fafc;
    --surface: #ffffff;
    /* etc... */
}
```

## Browser Compatibility

- ✅ Chrome/Edge (Latest)
- ✅ Firefox (Latest)
- ✅ Safari (Latest)
- ⚠️ IE11 (Not supported)

## Performance

- **Initial load:** ~500-1000ms (loads filters + stats)
- **Search query:** ~500-2000ms (depends on filters)
- **Pagination:** ~500-1000ms (cached filters)

Query times depend on:
- Number of matching results
- S3 network latency
- Filter complexity

## Troubleshooting

### CORS Errors
Make sure the API is running at `http://localhost:8000`

### No Results Loading
1. Check API is running: `curl http://localhost:8000/health`
2. Check browser console for errors (F12)
3. Verify `.env` has correct AWS credentials

### Slow Queries
- Add more specific filters to reduce result set
- Use country/industry filters (indexed in Parquet)
- Avoid very broad keyword searches

## Next Steps

### Add Features:
- Export results to CSV
- Profile detail modal
- Save search filters
- Bookmark/favorite profiles
- Share search URLs

### Optimize:
- Add result caching
- Implement infinite scroll
- Add search suggestions
- Client-side result filtering

## License

Internal tool - not for public distribution
