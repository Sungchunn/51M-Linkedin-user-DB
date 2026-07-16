# PROSPECTIQ - Frontend

Next.js (App Router) frontend for the PROSPECTIQ semantic talent-search platform.

## Stack

- **Next.js 16** (App Router), plain JavaScript — no TypeScript
- **Bun 1.3.9** for frontend package management and scripts (`bun.lock`)
- **Plain CSS**: global theme tokens in `app/globals.css` (dark default + light via `[data-theme="light"]`), page-specific styles in CSS Modules
- **No component library / no Tailwind** — styling follows `docs/guides/THEME_GUIDELINES.md`

## Quick Start

```bash
cd frontend
bun install
bun run dev        # http://localhost:5500
```

Or from the repo root: `scripts/serve_frontend_bg.sh` (background, logs to `.tmp/frontend_http.log`).

The backend API must be running at `http://localhost:8000` (`./start_api.sh` from the repo root).

## Production

```bash
bun run build
bun run start      # serves the production build on :5500
```

## Routes

| Route | Purpose |
|-------|---------|
| `/` | Search page (keyword + advanced filters) |
| `/results` | Search results table with pagination + CSV export |
| `/login` | Login / registration |
| `/dashboard` | API key management (requires login) |
| `/api-docs` | API documentation + cURL generator (requires login) |
| `/test-api-key` | Dev utility: login / create key / list keys |

Legacy `*.html` URLs (e.g. `/login.html`) redirect to the new routes via `next.config.mjs`.

## Structure

```
frontend/
├── app/                    # App Router pages
│   ├── layout.js           # Root layout + pre-paint theme bootstrap
│   ├── globals.css         # Theme tokens + shared styles (old styles.css)
│   ├── page.js             # Search page
│   ├── results/
│   ├── login/
│   ├── dashboard/
│   ├── api-docs/
│   └── test-api-key/
├── components/             # Header, Footer, ThemeToggle, GitHubStars, SquaresBackground
└── lib/                    # config (API base URL), auth (JWT), theme, squares-background
```

## Configuration

API base URL resolution (see `lib/config.js`):

1. `NEXT_PUBLIC_API_URL` env var (set at build time)
2. `localhost` / `127.0.0.1` → `http://localhost:8000`
3. otherwise same origin

## Theming

The theme (dark/light) is applied before first paint by an inline script in
`app/layout.js` (localStorage `theme` wins, otherwise OS preference). Components
use `lib/theme.js`; a `themechange` CustomEvent fires on `window` so the canvas
background can re-read the `--canvas-*` tokens. Always use CSS variables — never
hardcode colors (see `docs/guides/THEME_GUIDELINES.md`).
