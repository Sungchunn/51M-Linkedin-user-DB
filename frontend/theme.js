/**
 * Theme manager — light/dark switching for all pages.
 *
 * Load synchronously in <head> BEFORE the stylesheet link so the
 * data-theme attribute is set before first paint (no flash of the
 * wrong theme).
 *
 * Resolution order: localStorage 'theme' ('light' | 'dark') wins;
 * otherwise the OS preference (prefers-color-scheme). While no explicit
 * choice is stored, OS preference changes apply live.
 *
 * API: window.themeUtils = { get(), set(theme), toggle() }
 * Emits: 'themechange' CustomEvent on window ({ detail: { theme } })
 * so canvas backgrounds etc. can re-read theme colors.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'theme';
    var lightQuery = window.matchMedia
        ? window.matchMedia('(prefers-color-scheme: light)')
        : null;

    function storedTheme() {
        try {
            var value = localStorage.getItem(STORAGE_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch (e) {
            return null; // localStorage unavailable (private browsing etc.)
        }
    }

    function systemTheme() {
        return lightQuery && lightQuery.matches ? 'light' : 'dark';
    }

    function apply(theme) {
        document.documentElement.dataset.theme = theme;
        updateToggles(theme);
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    }

    function updateToggles(theme) {
        if (!document.body) return;
        var label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
        var toggles = document.querySelectorAll('.theme-toggle');
        for (var i = 0; i < toggles.length; i++) {
            toggles[i].setAttribute('aria-label', label);
            toggles[i].setAttribute('title', label);
        }
    }

    var themeUtils = {
        get: function () {
            return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
        },
        set: function (theme) {
            if (theme !== 'light' && theme !== 'dark') {
                throw new Error('themeUtils.set: theme must be "light" or "dark", got: ' + theme);
            }
            try {
                localStorage.setItem(STORAGE_KEY, theme);
            } catch (e) {
                // Persistence unavailable; still apply for this page view.
            }
            apply(theme);
        },
        toggle: function () {
            themeUtils.set(themeUtils.get() === 'light' ? 'dark' : 'light');
        }
    };

    window.themeUtils = themeUtils;

    // Set the attribute immediately — this runs before <body> is parsed.
    apply(storedTheme() || systemTheme());

    // Follow OS changes only while the user has not made an explicit choice.
    if (lightQuery) {
        var onSystemChange = function () {
            if (!storedTheme()) apply(systemTheme());
        };
        if (lightQuery.addEventListener) {
            lightQuery.addEventListener('change', onSystemChange);
        } else if (lightQuery.addListener) {
            lightQuery.addListener(onSystemChange); // older Safari
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        updateToggles(themeUtils.get());
        var toggles = document.querySelectorAll('.theme-toggle');
        for (var i = 0; i < toggles.length; i++) {
            toggles[i].addEventListener('click', themeUtils.toggle);
        }
    });
})();
