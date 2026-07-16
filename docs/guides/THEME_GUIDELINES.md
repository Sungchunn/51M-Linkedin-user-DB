# PROSPECTIQ Theme Guidelines

This document establishes the visual design standards for PROSPECTIQ to ensure consistency across all pages and components.

## Design Philosophy

PROSPECTIQ uses a **dark minimal aesthetic** with subtle luxury touches, plus a **light theme** that users can switch to. The interface emphasizes:
- Clean, spacious layouts with generous padding
- Subtle borders and shadows for depth
- Signature glow effects on interactive elements (white glow in dark mode, soft dark halo in light mode)
- Professional monospace fonts for technical content
- Smooth transitions and hover states

## Theming System (light/dark)

Dark is the baseline theme, defined on `:root` in `frontend/app/globals.css`. Light
mode is a `[data-theme="light"]` override block that re-declares every token. The
attribute lives on `<html>` and is set **before first paint** by an inline bootstrap
script in `frontend/app/layout.js` (no flash of the wrong theme), then managed by
`frontend/lib/theme.js`.

**Every page must** include the shared `<ThemeToggle />` component
(`frontend/components/ThemeToggle.js`) somewhere in its chrome — see `app/page.js`
(header via `components/Header.js`), `app/login/page.js` (floating top-right), or
`app/api-docs/page.js` (sidebar header).

**Resolution order:** a stored `localStorage.theme` choice wins; otherwise the OS
`prefers-color-scheme` applies (and tracks live OS changes until the user toggles).

**JS API:** `import { getTheme, setTheme, toggleTheme } from '@/lib/theme'`. Every
change dispatches a `themechange` CustomEvent on `window` (detail: `{ theme }`) —
canvas code like `lib/squares-background.js` listens to it and re-reads the
`--canvas-*` tokens.

## Color Palette

### CSS Variables (Use These!)

All pages must use CSS variables defined in `app/globals.css`. Never hardcode colors.
**New colors must be added as a token pair — a dark value in `:root` and a light value
in `[data-theme="light"]` — never as a literal in page styles or JS.**

Core tokens, both themes (contrast ratios are against `--background`):

| Token | Dark | Light | Light contrast |
|---|---|---|---|
| `--background` | `#0a0a0a` | `#fafafa` | — |
| `--surface` | `#171717` | `#ffffff` | — |
| `--surface-hover` | `#262626` | `#f5f5f5` | — |
| `--border` / `--border-hover` / `--border-focus` | `#262626` / `#404040` / `#525252` | `#e5e5e5` / `#d4d4d4` / `#a3a3a3` | decorative |
| `--text-primary` | `#fafafa` | `#171717` | 17.2:1 AAA |
| `--text-secondary` | `#a3a3a3` | `#525252` | 7.5:1 AAA |
| `--text-muted` | `#737373` | `#6b6b6b` | 5.1:1 AA |
| `--text-subtle` | `#525252` | `#707070` | 4.7:1 AA |
| `--primary-color` / `--primary-hover` | `#262626` / `#404040` | `#171717` / `#262626` | dark chip in both themes |
| `--text-on-primary` | `#fafafa` | `#fafafa` | 17.2:1 on the chip |
| `--success` | `#10b981` | `#047857` | 5.25:1 AA |
| `--error` | `#ef4444` | `#b91c1c` | 6.2:1 AA |
| `--info` | `#60a5fa` | `#1d4ed8` | 6.7:1 AA |
| `--nav-link` | `#9aa6c7` | `#475569` | 7.3:1 AAA |
| `--link-accent` | `#60d5ff` | `#0e7490` | 5.1:1 AA |

Supporting tokens (see `app/globals.css` for values in both themes): tints
(`--success-tint`, `--success-tint-strong`, `--error-tint`, `--error-tint-strong`,
`--info-tint`, `--link-accent-tint`/`-border`), warning box
(`--warning-bg`/`-text`/`-border`/`-accent`), effects (`--glow-1/2/3`, `--ripple`,
`--focus-ring`, `--overlay`), code (`--code-bg`, `--code-text`), GitHub badge
(`--badge-*`), canvas background (`--canvas-line`, `--canvas-hover`,
`--canvas-vignette-rgb`), and shadows (`--shadow-sm/md/lg`,
`--shadow-inset-sm/md`).

### Color Usage Rules

1. **Backgrounds**: Always use `--background` for page backgrounds, `--surface` for cards/panels
2. **Borders**: Use `--border` for default, `--border-hover` on hover, `--border-focus` on focus
3. **Text**: Use `--text-primary` for headings, `--text-secondary` for labels, `--text-muted` for hints
4. **Success/Error**: Use `--success` for positive actions (create, confirm), `--error` for negative actions (delete, revoke)
5. **Buttons on `--primary-color`**: always pair with `--text-on-primary`, never `--text-primary` — the button stays a dark chip in light mode, where `--text-primary` flips to near-black and would vanish
6. **Links**: `--nav-link` for chrome/navigation links, `--link-accent` for links inside content (result tables, tips)

## Typography

### Font Families

```css
/* Body Text */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Monospace (for code, API keys, technical data) */
font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', monospace;
```

### Font Sizes

```css
/* Headings */
--font-size-h1: 32px;  /* Page titles */
--font-size-h2: 24px;  /* Section titles */
--font-size-h3: 18px;  /* Subsection titles */

/* Body */
--font-size-base: 15px;      /* Default body text */
--font-size-small: 14px;     /* Labels, secondary text */
--font-size-tiny: 13px;      /* Hints, metadata */
```

### Font Weights

- **700**: Page titles, important headings
- **600**: Section headings, emphasized text
- **500**: Labels, buttons, interactive text
- **400**: Regular body text

## Signature Glow Effect

The **glow effect** is a signature element of PROSPECTIQ. Use it on all primary interactive elements (buttons, links, hover states). It is token-driven: a white glow in dark mode, a soft dark elevation halo in light mode — same CSS either way.

### Implementation

```css
.btn-primary {
    padding: 12px 24px;
    background: var(--primary-color);
    border: 1px solid var(--border-hover);
    border-radius: 8px;
    color: var(--text-on-primary);
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

/* Ripple effect on hover */
.btn-primary::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: var(--ripple);
    transform: translate(-50%, -50%);
    transition: width 0.6s ease-out, height 0.6s ease-out;
    z-index: 0;
}

.btn-primary:hover::before {
    width: 400px;
    height: 400px;
}

/* Glow effect */
.btn-primary:hover {
    background: var(--primary-hover);
    box-shadow:
        0 0 40px var(--glow-1),
        0 0 80px var(--glow-2),
        0 0 120px var(--glow-3),
        var(--shadow-md);
    border-color: var(--text-primary);
    transform: translateY(-2px);
}

/* Ensure text stays on top */
.btn-primary span {
    position: relative;
    z-index: 1;
}
```

### Where to Use Glow Effect

- ✅ Primary action buttons (Create, Submit, Search)
- ✅ Navigation buttons with important actions
- ✅ Interactive cards on hover
- ❌ Small utility buttons (Cancel, Close)
- ❌ Destructive actions (Delete, Revoke) - use red theme instead

## Layout Patterns

### Container Widths

```css
/* Standard page container */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 20px;
}

/* Narrow content (forms, documentation) */
.narrow-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 40px 20px;
}

/* Full width with sidebar */
.sidebar-layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 40px;
    max-width: 1400px;
    margin: 0 auto;
}
```

### Cards and Panels

```css
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
    box-shadow: var(--shadow-sm);
    transition: all 0.2s;
}

.card:hover {
    border-color: var(--border-hover);
}
```

### Spacing

Use multiples of 8px for consistency:
- 8px: Tight spacing (checkbox labels, inline elements)
- 16px: Standard spacing (between form fields, list items)
- 24px: Section spacing (between subsections)
- 32px: Major spacing (between sections, card padding)
- 40px: Page margins

## Form Elements

### Input Fields

```css
.form-input {
    width: 100%;
    padding: 12px 16px;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 15px;
    box-sizing: border-box;
    transition: all 0.2s;
}

.form-input:hover {
    border-color: var(--border-hover);
}

.form-input:focus {
    outline: none;
    border-color: var(--border-focus);
    box-shadow: 0 0 0 4px rgba(115, 115, 115, 0.08);
}

.form-input::placeholder {
    color: var(--text-muted);
}
```

### Select Dropdowns

```css
.form-select {
    width: 100%;
    padding: 12px 16px;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 15px;
    transition: all 0.2s;
}
```

### Checkboxes and Labels

```css
.checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    color: var(--text-secondary);
    transition: all 0.2s;
}

.checkbox-label:hover {
    border-color: var(--border-hover);
    background: var(--surface-hover);
}
```

## Buttons

### Primary Button (with glow)

See "Signature Glow Effect" section above.

### Secondary Button

```css
.btn-secondary {
    padding: 12px 24px;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
}

.btn-secondary:hover {
    background: var(--surface-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
}
```

### Danger Button (delete, revoke)

```css
.btn-danger {
    padding: 8px 16px;
    background: var(--error-tint);
    border: 1px solid var(--error);
    border-radius: 6px;
    color: var(--error);
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
    font-weight: 500;
}

.btn-danger:hover {
    background: var(--error-tint-strong);
    transform: translateY(-1px);
}
```

## Badges and Tags

### Success Badge

```css
.badge-success {
    font-size: 11px;
    padding: 4px 8px;
    background: var(--success-tint);
    border: 1px solid var(--success);
    border-radius: 4px;
    color: var(--success);
}
```

### Method Badge (for API docs)

```css
.badge-get {
    background: var(--success-tint-strong);
    color: var(--success);
}

.badge-post {
    background: var(--info-tint);
    color: var(--info);
}

.badge-delete {
    background: var(--error-tint-strong);
    color: var(--error);
}
```

## Alerts and Info Boxes

### Error Alert

```css
.alert-error {
    padding: 12px 16px;
    border-radius: 8px;
    background: var(--error-tint);
    border: 1px solid var(--error);
    color: var(--error);
    font-size: 14px;
}
```

### Success Alert

```css
.alert-success {
    padding: 12px 16px;
    border-radius: 8px;
    background: var(--success-tint);
    border: 1px solid var(--success);
    color: var(--success);
    font-size: 14px;
}
```

### Info Box

```css
.info-box {
    background: var(--surface);
    border-left: 4px solid var(--border-hover);
    padding: 16px 20px;
    border-radius: 8px;
    margin: 16px 0;
}
```

## Animations and Transitions

### Standard Transition

```css
transition: all 0.2s;
```

### Smooth Scroll

```css
html {
    scroll-behavior: smooth;
}
```

### Hover Effects

Always include subtle transforms on hover:
```css
transform: translateY(-2px);  /* Lift effect */
```

## Code Blocks

### Inline Code

```css
code {
    font-family: 'SF Mono', Monaco, monospace;
    background: var(--surface-hover);
    padding: 2px 8px;
    border-radius: 4px;
    color: var(--text-secondary);
    font-size: 13px;
}
```

### Code Blocks

```css
pre {
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
}

pre code {
    background: none;
    padding: 0;
    color: var(--text-secondary);
}
```

## Tables

```css
table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
}

th {
    background: var(--surface);
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    color: var(--text-primary);
    border-bottom: 2px solid var(--border);
}

td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
}

tr:hover td {
    background: var(--surface-hover);
}
```

## Modals

```css
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: var(--overlay);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-content {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
    max-width: 600px;
    width: 90%;
    box-shadow: var(--shadow-lg);
}
```

## Navigation

### Sidebar Navigation

```css
.sidebar {
    position: sticky;
    top: 20px;
    height: fit-content;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
}

.sidebar-link {
    display: block;
    padding: 8px 12px;
    color: var(--text-secondary);
    text-decoration: none;
    border-radius: 6px;
    transition: all 0.2s;
}

.sidebar-link:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
}

.sidebar-link.active {
    background: var(--primary-color);
    color: var(--text-primary);
}
```

## Accessibility

### Focus States

Always provide visible focus states:
```css
:focus {
    outline: none;
    box-shadow: 0 0 0 4px var(--focus-ring);
}
```

### Color Contrast

Text must meet WCAG AA (≥ 4.5:1 for normal text, ≥ 3:1 for large text/UI).
The light-theme values were chosen to pass — ratios are in the token table above.
Dark theme: `--text-primary` 17.9:1 AAA, `--text-secondary` 8.6:1 AAA,
`--text-muted` 4.6:1 AA.

Known dark-theme shortfalls (pre-existing, tracked as follow-up): `--text-subtle`
placeholders (~2.5:1) and `--success`/`--error` text on `--surface` (~3–4:1).

## Responsive Design

### Breakpoints

```css
/* Mobile */
@media (max-width: 640px) {
    .container {
        padding: 20px 16px;
    }

    .sidebar-layout {
        grid-template-columns: 1fr;
    }
}

/* Tablet */
@media (max-width: 1024px) {
    .container {
        padding: 32px 20px;
    }
}
```

## File Structure

When creating new pages (Next.js App Router):

```
frontend/
├── app/
│   ├── layout.js            # Root layout: metadata + pre-paint theme bootstrap
│   ├── globals.css          # Global stylesheet — owns ALL token definitions
│   ├── page.js              # Main search page (/)
│   ├── login/page.js        # Authentication (/login)
│   ├── dashboard/page.js    # API key dashboard (/dashboard)
│   ├── api-docs/page.js     # API documentation (/api-docs)
│   └── [new-page]/
│       ├── page.js          # Your new page
│       └── [new-page].module.css   # Page-specific styles (CSS Module)
├── components/              # ThemeToggle, Header, Footer, GitHubStars, SquaresBackground
└── lib/                     # config, auth, theme, squares-background
```

`app/globals.css` owns the token definitions. Extend it by adding tokens as a
dark + light pair (`:root` and `[data-theme="light"]`) — don't scatter color
values into page styles.

### New Page Template

```jsx
// app/my-page/page.js
'use client';

import ThemeToggle from '@/components/ThemeToggle';
import styles from './my-page.module.css';

export default function MyPage() {
    return (
        <div className={styles.pageContainer}>
            {/* include <ThemeToggle /> in the page chrome */}
            {/* Content here */}
        </div>
    );
}
```

```css
/* app/my-page/my-page.module.css — page-specific styles using CSS variables */
.pageContainer {
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 20px;
}

/* Always use var(--variable-name) for colors */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
}
```

## Checklist for New Pages

Before committing a new page, verify:

- [ ] Page-specific styles live in a CSS Module next to `page.js` (globals only in `app/globals.css`)
- [ ] Includes the `<ThemeToggle />` component in the page chrome
- [ ] All colors use CSS variables (no hardcoded hex values)
- [ ] Page reviewed in BOTH themes (toggle + hard reload)
- [ ] Text on `--primary-color` chips uses `--text-on-primary`
- [ ] Primary buttons have glow effect
- [ ] Hover states on all interactive elements
- [ ] Smooth transitions (transition: all 0.2s)
- [ ] Border radius: 12px for cards, 8px for buttons/inputs, 6px for small elements
- [ ] Consistent spacing (multiples of 8px)
- [ ] Monospace font for technical content (API keys, code)
- [ ] Focus states for accessibility
- [ ] Responsive design tested on mobile
- [ ] Navigation links to other pages
- [ ] Matches the minimal aesthetic in both themes

## Common Mistakes to Avoid

❌ **DON'T**: Hardcode colors
```css
background: #151515; /* BAD */
```

✅ **DO**: Use CSS variables
```css
background: var(--surface); /* GOOD */
```

---

❌ **DON'T**: Use default button styles
```css
<button>Click me</button>
```

✅ **DO**: Apply proper button classes
```css
<button class="btn-primary"><span>Click me</span></button>
```

---

❌ **DON'T**: Forget the ripple effect wrapper
```css
.btn-primary:hover {
    box-shadow: 0 0 40px var(--glow-1);
}
```

✅ **DO**: Include both ripple and glow
```css
.btn-primary::before { /* ripple */ }
.btn-primary:hover { /* glow */ }
.btn-primary span { /* text on top */ }
```

---

❌ **DON'T**: Use inconsistent spacing
```css
margin: 15px; /* BAD */
padding: 13px; /* BAD */
```

✅ **DO**: Use multiples of 8px
```css
margin: 16px; /* GOOD */
padding: 12px; /* GOOD (exception for specific sizes) */
```

## Examples

See these files for reference implementations:
- **Glow buttons**: `frontend/app/login/login.module.css` (`.loginButton`)
- **Sidebar layout**: `frontend/app/api-docs/api-docs.module.css`
- **Form elements**: `frontend/app/dashboard/dashboard.module.css` (`.formInput`, `.formSelect`)
- **Cards with hover**: `frontend/app/dashboard/dashboard.module.css` (`.apiKeyCard`)
- **Badges**: `frontend/app/api-docs/api-docs.module.css` (method badges)
- **Alerts**: `frontend/app/login/login.module.css` (`.alert*`)

## Questions?

If you're unsure about styling:
1. Check `app/globals.css` for available CSS variables
2. Reference existing pages (`app/login`, `app/dashboard`, `app/api-docs`)
3. Follow the patterns in this document
4. When in doubt, keep it minimal and use CSS variables
