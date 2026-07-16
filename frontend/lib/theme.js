/**
 * Theme manager — light/dark switching for all pages.
 *
 * The initial theme is applied pre-paint by the inline bootstrap script in
 * app/layout.js. This module is the client-side API used by components.
 *
 * Emits: 'themechange' CustomEvent on window ({ detail: { theme } })
 * so canvas backgrounds etc. can re-read theme colors.
 */
const STORAGE_KEY = 'theme';

export function getTheme() {
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

export function setTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') {
        throw new Error(`setTheme: theme must be "light" or "dark", got: ${theme}`);
    }
    try {
        localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
        // Persistence unavailable; still apply for this page view.
    }
    document.documentElement.dataset.theme = theme;
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

export function toggleTheme() {
    setTheme(getTheme() === 'light' ? 'dark' : 'light');
}
