import './globals.css';

export const metadata = {
    title: 'PROSPECTIQ - Semantic Talent Search',
    description: 'Intelligence-Driven Prospecting',
};

/*
 * Theme bootstrap — must run synchronously in <head> BEFORE first paint so
 * the data-theme attribute is set with no flash of the wrong theme.
 *
 * Resolution order: localStorage 'theme' ('light' | 'dark') wins; otherwise
 * the OS preference (prefers-color-scheme). While no explicit choice is
 * stored, OS preference changes apply live.
 *
 * Emits: 'themechange' CustomEvent on window ({ detail: { theme } }) so
 * canvas backgrounds etc. can re-read theme colors. lib/theme.js is the
 * client-side API on top of this.
 */
const themeBootstrap = `
(function () {
    'use strict';
    var stored = null;
    try {
        var value = localStorage.getItem('theme');
        stored = (value === 'light' || value === 'dark') ? value : null;
    } catch (e) { /* localStorage unavailable (private browsing etc.) */ }
    var lightQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
    function systemTheme() { return lightQuery && lightQuery.matches ? 'light' : 'dark'; }
    function apply(theme) {
        document.documentElement.dataset.theme = theme;
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    }
    apply(stored || systemTheme());
    if (lightQuery) {
        var onSystemChange = function () {
            var current = null;
            try { current = localStorage.getItem('theme'); } catch (e) {}
            if (current !== 'light' && current !== 'dark') apply(systemTheme());
        };
        if (lightQuery.addEventListener) {
            lightQuery.addEventListener('change', onSystemChange);
        } else if (lightQuery.addListener) {
            lightQuery.addListener(onSystemChange); // older Safari
        }
    }
})();
`;

export default function RootLayout({ children }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <meta name="color-scheme" content="dark light" />
                <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
            </head>
            <body>{children}</body>
        </html>
    );
}
