# PROSPECTIQ Theme Guidelines

This document establishes the visual design standards for PROSPECTIQ to ensure consistency across all pages and components.

## Design Philosophy

PROSPECTIQ uses a **dark minimal aesthetic** with subtle luxury touches. The interface emphasizes:
- Clean, spacious layouts with generous padding
- Subtle borders and shadows for depth
- Signature white glow effects on interactive elements
- Professional monospace fonts for technical content
- Smooth transitions and hover states

## Color Palette

### CSS Variables (Use These!)

All pages must use CSS variables defined in `styles.css`. Never hardcode colors.

```css
/* Background Colors */
--background: #0a0a0a;        /* Main page background */
--surface: #151515;           /* Card/panel backgrounds */
--surface-hover: #1a1a1a;     /* Hover state for surfaces */

/* Border Colors */
--border: #2a2a2a;            /* Default borders */
--border-hover: #404040;      /* Hover state borders */
--border-focus: #505050;      /* Focus state borders */

/* Text Colors */
--text-primary: #fafafa;      /* Primary text (headings, important) */
--text-secondary: #d4d4d4;    /* Secondary text (labels, descriptions) */
--text-muted: #a3a3a3;        /* Muted text (hints, placeholders) */

/* Accent Colors */
--primary-color: #262626;     /* Primary buttons, interactive elements */
--primary-hover: #2d2d2d;     /* Primary hover state */
--success: #10b981;           /* Success states, positive badges */
--error: #ef4444;             /* Error states, warnings, delete actions */

/* Shadows */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.5);
```

### Color Usage Rules

1. **Backgrounds**: Always use `--background` for page backgrounds, `--surface` for cards/panels
2. **Borders**: Use `--border` for default, `--border-hover` on hover, `--border-focus` on focus
3. **Text**: Use `--text-primary` for headings, `--text-secondary` for labels, `--text-muted` for hints
4. **Success/Error**: Use `--success` for positive actions (create, confirm), `--error` for negative actions (delete, revoke)

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

The **white glow effect** is a signature element of PROSPECTIQ. Use it on all primary interactive elements (buttons, links, hover states).

### Implementation

```css
.btn-primary {
    padding: 12px 24px;
    background: var(--primary-color);
    border: 1px solid var(--border-hover);
    border-radius: 8px;
    color: var(--text-primary);
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
    background: rgba(255, 255, 255, 0.15);
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
        0 0 40px rgba(250, 250, 250, 0.4),
        0 0 80px rgba(250, 250, 250, 0.2),
        0 0 120px rgba(250, 250, 250, 0.1),
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
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error);
    border-radius: 6px;
    color: var(--error);
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
    font-weight: 500;
}

.btn-danger:hover {
    background: rgba(239, 68, 68, 0.2);
    transform: translateY(-1px);
}
```

## Badges and Tags

### Success Badge

```css
.badge-success {
    font-size: 11px;
    padding: 4px 8px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid var(--success);
    border-radius: 4px;
    color: var(--success);
}
```

### Method Badge (for API docs)

```css
.badge-get {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid #10b981;
    color: #10b981;
}

.badge-post {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid #3b82f6;
    color: #3b82f6;
}

.badge-delete {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid #ef4444;
    color: #ef4444;
}
```

## Alerts and Info Boxes

### Error Alert

```css
.alert-error {
    padding: 12px 16px;
    border-radius: 8px;
    background: rgba(239, 68, 68, 0.1);
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
    background: rgba(16, 185, 129, 0.1);
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
    background: rgba(0, 0, 0, 0.8);
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
    box-shadow: 0 0 0 4px rgba(115, 115, 115, 0.08);
}
```

### Color Contrast

Ensure text meets WCAG AA standards:
- Primary text (#fafafa) on dark backgrounds: ✅ AAA
- Secondary text (#d4d4d4) on dark backgrounds: ✅ AA
- Muted text (#a3a3a3) on dark backgrounds: ✅ AA (large text)

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

When creating new pages:

```
frontend/
├── index.html          # Main search page
├── login.html          # Authentication
├── dashboard.html      # User dashboard
├── api-docs.html       # API documentation
├── styles.css          # Global CSS variables (NEVER modify)
├── auth.js             # Authentication utilities
└── [new-page].html     # Your new page
```

### New Page Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Name - PROSPECTIQ</title>
    <link rel="stylesheet" href="styles.css">
    <style>
        /* Page-specific styles using CSS variables */
        .page-container {
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
    </style>
</head>
<body>
    <div class="page-container">
        <!-- Content here -->
    </div>

    <script src="auth.js"></script>
    <script src="your-script.js"></script>
</body>
</html>
```

## Checklist for New Pages

Before committing a new page, verify:

- [ ] Uses `<link rel="stylesheet" href="styles.css">`
- [ ] All colors use CSS variables (no hardcoded hex values)
- [ ] Primary buttons have glow effect
- [ ] Hover states on all interactive elements
- [ ] Smooth transitions (transition: all 0.2s)
- [ ] Border radius: 12px for cards, 8px for buttons/inputs, 6px for small elements
- [ ] Consistent spacing (multiples of 8px)
- [ ] Monospace font for technical content (API keys, code)
- [ ] Focus states for accessibility
- [ ] Responsive design tested on mobile
- [ ] Navigation links to other pages
- [ ] Matches dark minimal aesthetic

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
    box-shadow: 0 0 40px rgba(250, 250, 250, 0.4);
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
- **Glow buttons**: `frontend/login.html` (line 96-162)
- **Sidebar layout**: `frontend/api-docs.html` (line 25-90)
- **Form elements**: `frontend/dashboard.html` (line 240-273)
- **Cards with hover**: `frontend/dashboard.html` (line 132-145)
- **Badges**: `frontend/api-docs.html` (line 156-183)
- **Alerts**: `frontend/login.html` (line 187-205)

## Questions?

If you're unsure about styling:
1. Check `styles.css` for available CSS variables
2. Reference existing pages (login.html, dashboard.html, api-docs.html)
3. Follow the patterns in this document
4. When in doubt, keep it minimal and use CSS variables
